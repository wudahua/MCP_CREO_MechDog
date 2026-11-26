// Composable Creo feature operations, using the installed Creo 10 Toolkit.
#include "third_party/json.hpp"
#include "callback_identity.h"
#include "recovery_deadline.h"
#include "adoption_source.h"
#include "inspection_units.h"
#include "mass_properties.h"
#include "axis_geometry.h"
#include "assembly_units.h"
#include "assembly_walk.h"
#include "solid_bounds.h"
#include "assembly_pose.h"
#include "constraint_placement.h"
#include "constraint_names.h"
#include "constraint_compare.h"
#include "preview.h"
#include "inspection_sidecar.h"
#include "stl_export.h"
#include <algorithm>
#include <cctype>
#include <chrono>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <limits>
#include <memory>
#include <map>
#include <set>
#include <array>
#include <ProDtmCrv.h>
#include <ProDtmPln.h>
#include <ProDtmAxis.h>
#include <ProAxis.h>
#include <ProRevolve.h>
#include <ProChamfer.h>
#include <ProShell.h>
#include <ProPattern.h>
#include <ProDimension.h>
#include <ProSecconstr.h>
#include <ProParameter.h>
#include <ProParamval.h>
#include <ProRelSet.h>
#include <ProContour.h>
#include <ProEdge.h>
#include <ProCurvedata.h>
#include <ProIntf3dExport.h>
#include <ProPart.h>
#include <ProFeature.h>
#include <ProCollect.h>
#include <ProCrvcollection.h>
#include <ProMirror.h>
#include <ProSweep.h>
#include <ProDraft.h>
#include <ProSrfcollection.h>
#include <ProSmtFlangeWall.h>
#include <ProSmtFlatWall.h>
#include <ProRegularUnbend.h>
#include <ProSmtBendBack.h>
#include <ProAsmcomp.h>
#include <ProAsmcomppath.h>
#include <ProSheetmetal.h>
#include <ProSmtDrvSurf.h>
#include <ProFlatSrf.h>
using J = nlohmann::json;
using V = std::array<double, 3>;
static J aliases = J::object(), gfeatures = J::array(), gsurfaces = J::array(), gedges = J::array();
static std::set<int> visited_edges;
// P08/FEAT-014: bounded wall-contour (candidate edge) discovery. The per-edge
// ProSmtedgeContourGet query runs only while inspecting a sheetmetal part (a
// sheetmetal-related check), never creates a flange and never modifies the
// model. It is capped at WALL_CONTOUR_EDGE_BUDGET edges per inspection and
// lands in the top-level wall_contour_check block keyed by edge id; the
// compared `edges` records keep their exact shape so snapshots taken before
// this block existed still reconcile.
static constexpr int WALL_CONTOUR_EDGE_BUDGET = 256;
static bool wall_contour_query_enabled = false;
static int wall_contour_checked = 0;
static bool wall_contour_bounded = false;
static J wall_contour_edges = J::array();
static std::wstring generic_job;
static int temporarily_suppressed_loft = -1;
static J operation_results = J::array();
// T02: every requested operation publishes exactly one terminal result. The
// dispatch branches stage their detail here and the shared tail appends it
// once; appending from both the branch and the tail duplicated operations.
static J staged_operation_result = J::object();
static bool has_staged_operation_result = false;
// Zero-based position of the operation being executed. Generated model names
// derive from this stable position instead of the result count so deduplicating
// the results cannot rename or collide previously created objects (T02).
static int operation_position = -1;
static void stage_operation_result(const J &detail) {
    staged_operation_result = detail;
    has_staged_operation_result = true;
}
static int generated_identity_index() {
    return operation_position < 0 ? 0 : operation_position;
}
static void append_operation_result(J result) {
    operation_results.push_back(std::move(result));
}
static J datum_axes = J::array();
static J length_unit_json(const InspectionLengthUnits &units, const MillimeterScale &scale);
// T08: deleted-label tombstones and the intentional suppression registry. Both
// are persisted per model; only recorded suppression counts as healthy, and the
// save/reload and rollback comparisons must match the recorded set exactly.
static J feature_tombstones = J::object();
static J suppressed_features = J::object();
static std::set<int> recorded_suppressed;
// Plan-level effects of the feature_state inputs actually executed, used only
// for the committed save/reload comparison (never for rollback evidence).
static J feature_state_effects = J::object();
static bool feature_state_touched = false;
// Rebuild the accepted-suppression set from the model's recorded registry.
// Entries without a real feature ID are ignored here and reported by the
// comparison that needs them (they never grant permission).
static void refresh_recorded_suppressed() {
    recorded_suppressed.clear();
    for (auto &entry : suppressed_features) {
        if (!entry.is_object())
            continue;
        auto id = entry.find("feature_id");
        if (id != entry.end() && id->is_number_integer())
            recorded_suppressed.insert(id->get<int>());
    }
}
// Snapshot of unhealthy features captured by inspection() right before it
// throws, so the failure response can carry feature-level diagnostics
// (BUG-082 H4) instead of only the generic regeneration message.
static J failed_features = J::array();
static std::string generic_phase = "loading_request";
static void generic_stage(const std::string &phase) {
    generic_phase = phase;
    log("PHASE=%s\n", phase.c_str());
}
// BUG-109: verify_model used to be a single phase name covering regeneration,
// inspection, assertions, backup save, erase, reload, comparison and preview, so
// a stalled first build logged nothing new until the whole job budget expired.
// Each step now publishes one bounded STAGE line carrying its own and cumulative
// elapsed time plus the worker's wall clock; nothing here changes the job budget,
// interrupts a Toolkit call or retries anything.
static const auto generic_started_at = std::chrono::steady_clock::now();
static auto generic_step_started_at = generic_started_at;
static J verify_stages = J::array();
static constexpr std::size_t VERIFY_STAGE_LIMIT = 32;
static long long milliseconds_between(const std::chrono::steady_clock::time_point &from) {
    return static_cast<long long>(std::chrono::duration_cast<std::chrono::milliseconds>(
                                      std::chrono::steady_clock::now() - from)
                                      .count());
}
static void generic_substage(const std::string &name) {
    const auto step_point = std::chrono::steady_clock::now();
    const long long elapsed = static_cast<long long>(
        std::chrono::duration_cast<std::chrono::milliseconds>(step_point - generic_step_started_at)
            .count());
    generic_step_started_at = step_point;
    const long long since_start = milliseconds_between(generic_started_at);
    const long long wall =
        static_cast<long long>(std::chrono::duration_cast<std::chrono::milliseconds>(
                                   std::chrono::system_clock::now().time_since_epoch())
                                   .count());
    log("STAGE name=%s elapsed_ms=%lld since_start_ms=%lld ts=%lld\n", name.c_str(), elapsed,
        since_start, wall);
    if (verify_stages.size() < VERIFY_STAGE_LIMIT)
        verify_stages.push_back(
            {{"name", name}, {"elapsed_ms", elapsed}, {"since_start_ms", since_start}});
}
// B3/F06: one bounded line at the start and end of each requested operation is
// the "per-feature log summary" the 0.19.0 report asked for. A polling client
// reads index/total/label/elapsed from the 8192 B tail even when the log grows
// to 3-7.7 MB; this does not make the log itself smaller. It never changes the
// job budget, the operation order, the PHASE lines or the terminal result, and
// it keeps its own clock so STAGE timings stay untouched. Terminal
// BUILD_FAILED/BUILD_SUCCESS lines are never suppressed. Operations without a
// label keep an explicit "-" placeholder instead of an empty field.
static auto generic_progress_last_at = generic_started_at;
static void generic_progress(int index, int total, const J &op, const char *state) {
    const auto point = std::chrono::steady_clock::now();
    const long long elapsed = static_cast<long long>(
        std::chrono::duration_cast<std::chrono::milliseconds>(point - generic_progress_last_at)
            .count());
    generic_progress_last_at = point;
    const long long since_start = milliseconds_between(generic_started_at);
    const long long wall =
        static_cast<long long>(std::chrono::duration_cast<std::chrono::milliseconds>(
                                   std::chrono::system_clock::now().time_since_epoch())
                                   .count());
    const std::string kind = op.value("op", std::string()),
                      label = op.value("label", std::string());
    const char *kind_text = kind.empty() ? "-" : kind.c_str();
    const char *label_text = label.empty() ? "-" : label.c_str();
    log("PROGRESS index=%d total=%d op=%s label=%s state=%s elapsed_ms=%lld "
        "since_start_ms=%lld ts=%lld\n",
        index, total, kind_text, label_text, state, elapsed, since_start, wall);
}
static V vec(const J &j) {
    return {j.at(0).get<double>(), j.at(1).get<double>(), j.at(2).get<double>()};
}
static double dot(const V &a, const V &b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
static V cross(const V &a, const V &b) {
    return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]};
}
static V scale(const V &a, double s) {
    return {a[0] * s, a[1] * s, a[2] * s};
}
static V add(const V &a, const V &b) {
    return {a[0] + b[0], a[1] + b[1], a[2] + b[2]};
}
static V normalized(const V &a) {
    double n = sqrt(dot(a, a));
    if (n < 1e-9)
        throw std::runtime_error("Zero direction vector");
    return scale(a, 1 / n);
}
static J xyz(const double *a) {
    return J::array({a[0], a[1], a[2]});
}
static int constant(const J &value) {
    if (value.is_number_integer())
        return value.get<int>();
    auto it = tk_constants.find(value.get<std::string>());
    if (it == tk_constants.end())
        throw std::runtime_error("Unknown Toolkit constant: " + value.get<std::string>());
    return it->second;
}
// Resolve a user-supplied label to its registered alias entry. Creo
// uppercases PRO_E_STD_FEATURE_NAME, so inspect_model(features).name differs
// in case from the registered alias; both spellings must resolve to the same
// entry, and callers reading alias metadata must use this canonical lookup
// instead of indexing aliases[] with the raw string (which yields null).
static const J *alias_entry(const std::string &label) {
    auto it = aliases.find(label);
    if (it == aliases.end()) {
        std::string lower(label);
        std::transform(lower.begin(), lower.end(), lower.begin(),
                       [](unsigned char c) { return (char)std::tolower(c); });
        if (lower != label)
            it = aliases.find(lower);
    }
    return it == aliases.end() ? nullptr : &it.value();
}
static int feature_id(const J &ref) {
    if (ref.is_number_integer())
        return ref.get<int>();
    std::string label = ref.get<std::string>();
    // Some public clients stringify the integer branch of str|int anyOf
    // (BUG-073); digit-only strings cannot be feature labels, so normalize
    // them to feature IDs like the Python-side LoftOp contract does.
    if (!label.empty() && label.find_first_not_of("0123456789") == std::string::npos) {
        errno = 0;
        char *end = nullptr;
        long long id = std::strtoll(label.c_str(), &end, 10);
        if (!errno && end && !*end && id >= 0 && id <= 2147483647LL)
            return (int)id;
        throw std::runtime_error("Sketch feature ID is not a nonnegative 32-bit integer: " + label);
    }
    if (const J *entry = alias_entry(label))
        return entry->at("feature_id").get<int>();
    // A deleted label is a tombstone: it must never resolve to another
    // feature through a later reference (FEAT-027).
    if (feature_tombstones.contains(label))
        throw std::runtime_error("Feature label '" + label +
                                 "' is a tombstone of a deleted feature and cannot be referenced");
    std::string known;
    int count = 0;
    for (auto it = aliases.begin(); it != aliases.end() && count < 10; ++it, ++count)
        known += (count ? ", " : "") + it.key();
    throw std::runtime_error(
        "Unknown feature label: " + label +
        (known.empty() ? "; this model has no registered aliases; reference features by "
                         "numeric ID from inspect_model(features)"
                       : "; available labels: " + known + (aliases.size() > 10 ? ", ..." : "")));
}
static ProFeature feature(const J &ref) {
    ProFeature f;
    CK(ProModelitemInit(board, feature_id(ref), PRO_FEATURE, &f));
    return f;
}
static std::string type_name(int t) {
    if (t == PRO_FEAT_CURVE)
        return "sketch_or_curve";
    if (t == PRO_FEAT_PROTRUSION || t == PRO_FEAT_FIRST_FEAT)
        return "protrusion";
    if (t == PRO_FEAT_CUT)
        return "cut";
    if (t == PRO_FEAT_ROUND)
        return "round";
    if (t == PRO_FEAT_CHAMFER)
        return "chamfer";
    if (t == PRO_FEAT_HOLE)
        return "hole";
    if (t == PRO_FEAT_SHELL)
        return "shell";
    if (t == PRO_FEAT_DATUM)
        return "datum_plane";
    if (t == PRO_FEAT_DATUM_AXIS)
        return "datum_axis";
    return "other";
}
static ProError dimension_cb(ProDimension *dim, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    J *list = (J *)data;
    double value;
    ProName symbol = L"";
    ProDimensiontype type;
    ProError e = ProDimensionValueGet(dim, &value);
    if (!e) {
        ProDimensionSymbolGet(dim, symbol);
        ProDimensionTypeGet(dim, &type);
        ProBoolean relation_driven = PRO_B_FALSE;
        ProError relation_code = ProDimensionIsReldriven(dim, &relation_driven);
        // FEAT-004: report the owning feature so a guard can pin the owner, and
        // derive editability from the relation state instead of guessing. Both
        // stay null when the query fails.
        ProFeature owner = {};
        ProError owner_code = ProDimensionOwnerfeatureGet(dim, &owner);
        ProName owner_name = L"";
        if (owner_code == PRO_TK_NO_ERROR)
            ProModelitemNameGet(&owner, owner_name);
        list->push_back(
            {{"id", dim->id},
             {"value", value},
             {"symbol", utf8(symbol)},
             {"type", (int)type},
             {"relation_query_code", relation_code},
             {"relation_driven",
              relation_code == PRO_TK_NO_ERROR ? J(relation_driven == PRO_B_TRUE) : J(nullptr)},
             {"owner_feature_id", owner_code == PRO_TK_NO_ERROR ? J(owner.id) : J(nullptr)},
             {"owner_feature_name",
              owner_code == PRO_TK_NO_ERROR ? J(utf8(owner_name)) : J(nullptr)},
             {"owner_query_code", owner_code},
             {"editable",
              relation_code == PRO_TK_NO_ERROR ? J(relation_driven != PRO_B_TRUE) : J(nullptr)}});
    }
    return PRO_TK_NO_ERROR;
}
// FEAT-004 dimension guards. The tolerance and the refusal contract mirror
// src/creo_mechdog/dimension_guards.py; both sides must agree.
static const double kDimensionGuardAbsolute = 1e-8;
static const double kDimensionGuardRelative = 1e-8;

static std::string guard_number(double value) {
    char buffer[64] = {};
    std::snprintf(buffer, sizeof(buffer), "%.10g", value);
    return buffer;
}

static double guard_tolerance(double expected) {
    double relative = std::fabs(expected) * kDimensionGuardRelative;
    return relative > kDimensionGuardAbsolute ? relative : kDimensionGuardAbsolute;
}

struct DimensionTarget {
    ProDimension dim;
    int id;
    double current;
    double requested;
    bool relation_driven;
    bool symbol_known;
    std::string symbol;
    bool owner_known;
    int owner_id;
    std::string owner_name;
};

struct DimensionSymbolScan {
    std::string symbol;
    std::vector<int> ids;
};
static ProError dimension_symbol_visit(ProDimension *dimension, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    auto *scan = (DimensionSymbolScan *)data;
    ProName symbol = L"";
    if (ProDimensionSymbolGet(dimension, symbol) != PRO_TK_NO_ERROR)
        return PRO_TK_NO_ERROR;
    if (utf8(symbol) == scan->symbol)
        scan->ids.push_back(dimension->id);
    return PRO_TK_NO_ERROR;
}
// DEV-089 T4: resolve a dimension by owner feature + Creo symbol. Only the
// feature's own dimensions are searched, and exactly one symbol match is
// required: the first D2 in the whole model is never picked.
static int dimension_id_by_symbol(const J &value) {
    const std::string symbol = value.at("symbol").get<std::string>();
    ProFeature owner = feature(value.at("feature"));
    DimensionSymbolScan scan;
    scan.symbol = symbol;
    CK(ProFeatureDimensionVisit(&owner, dimension_symbol_visit, nullptr, &scan));
    if (scan.ids.size() == 1)
        return scan.ids[0];
    if (scan.ids.empty())
        throw std::runtime_error(
            "Dimension symbol '" + symbol + "' matched no dimension owned by feature id " +
            std::to_string(owner.id) +
            "; read the dimension symbol from creo_inspect_model or pass {id:N}");
    std::string ids;
    for (int id : scan.ids)
        ids += (ids.empty() ? "" : ", ") + std::to_string(id);
    throw std::runtime_error(
        "Dimension symbol '" + symbol + "' matched " + std::to_string(scan.ids.size()) +
        " dimensions owned by feature id " + std::to_string(owner.id) + " (ids " + ids +
        "); the symbol is not unique inside that feature, pass an explicit id");
}

static DimensionTarget read_dimension_target(ProMdl board, const J &value) {
    DimensionTarget target = {};
    target.id = value.contains("id") && !value["id"].is_null() ? value["id"].get<int>()
                                                               : dimension_id_by_symbol(value);
    target.requested = value["value"].get<double>();
    CK(ProModelitemInit(board, target.id, PRO_DIMENSION, &target.dim));
    ProBoolean relation_driven = PRO_B_FALSE;
    CK(ProDimensionIsReldriven(&target.dim, &relation_driven));
    target.relation_driven = relation_driven == PRO_B_TRUE;
    CK(ProDimensionValueGet(&target.dim, &target.current));
    ProName symbol = L"";
    target.symbol_known = ProDimensionSymbolGet(&target.dim, symbol) == PRO_TK_NO_ERROR;
    if (target.symbol_known)
        target.symbol = utf8(symbol);
    ProFeature owner = {};
    target.owner_known = ProDimensionOwnerfeatureGet(&target.dim, &owner) == PRO_TK_NO_ERROR;
    if (target.owner_known) {
        target.owner_id = owner.id;
        ProName owner_name = L"";
        ProModelitemNameGet(&owner, owner_name);
        target.owner_name = utf8(owner_name);
    }
    return target;
}

static std::string guard_owner_text(const DimensionTarget &target) {
    if (!target.owner_known)
        return "unknown";
    return target.owner_name + " (id " + std::to_string(target.owner_id) + ")";
}

// Reads every target before the caller writes the first value, so a mismatch
// leaves the model untouched instead of half-applied.
static void check_dimension_targets(const std::vector<DimensionTarget> &targets, const J &values) {
    for (size_t index = 0; index < targets.size(); ++index) {
        const DimensionTarget &target = targets[index];
        const J &value = values[index];
        if (target.relation_driven)
            throw std::runtime_error(
                "Dimension " + std::to_string(target.id) +
                " is controlled by relations; edit its driving parameter or relation instead");
        const J *expected_value =
            value.contains("expected_value") && !value["expected_value"].is_null()
                ? &value["expected_value"]
                : nullptr;
        if (expected_value) {
            double expected = expected_value->get<double>();
            if (std::fabs(expected - target.current) > guard_tolerance(expected))
                throw std::runtime_error(
                    "Dimension " + std::to_string(target.id) + " guard failed on value: expected " +
                    guard_number(expected) + ", current " + guard_number(target.current) +
                    ", owner " + guard_owner_text(target) +
                    "; re-read the model and resubmit with the current value");
        }
        const J *expected_symbol =
            value.contains("expected_symbol") && !value["expected_symbol"].is_null()
                ? &value["expected_symbol"]
                : nullptr;
        if (expected_symbol) {
            std::string expected = expected_symbol->get<std::string>();
            if (!target.symbol_known)
                throw std::runtime_error(
                    "Dimension " + std::to_string(target.id) +
                    " guard failed on symbol: expected \"" + expected +
                    "\" but the dimension symbol is unknown, owner " + guard_owner_text(target) +
                    "; re-read the model and resubmit with the current symbol");
            if (expected != target.symbol)
                throw std::runtime_error(
                    "Dimension " + std::to_string(target.id) +
                    " guard failed on symbol: expected \"" + expected + "\", current \"" +
                    target.symbol + "\", owner " + guard_owner_text(target) +
                    "; re-read the model and resubmit with the current symbol");
        }
        const J *expected_owner =
            value.contains("expected_owner") && !value["expected_owner"].is_null()
                ? &value["expected_owner"]
                : nullptr;
        if (expected_owner) {
            if (!target.owner_known)
                throw std::runtime_error("Dimension " + std::to_string(target.id) +
                                         " guard failed on owner: the owning feature is unknown; "
                                         "re-read the model and resubmit with the current owner");
            if (expected_owner->is_number_integer()) {
                int expected = expected_owner->get<int>();
                if (expected != target.owner_id)
                    throw std::runtime_error(
                        "Dimension " + std::to_string(target.id) +
                        " guard failed on owner: expected feature id " + std::to_string(expected) +
                        ", current " + guard_owner_text(target) +
                        "; re-read the model and resubmit with the current owner");
            } else {
                std::string expected = expected_owner->get<std::string>();
                if (expected != target.owner_name)
                    throw std::runtime_error(
                        "Dimension " + std::to_string(target.id) +
                        " guard failed on owner: expected \"" + expected + "\", current " +
                        guard_owner_text(target) +
                        "; re-read the model and resubmit with the current owner");
            }
        }
    }
}

static ProError collect_geom_ids(ProGeomitem *item, ProError status, ProAppData data) {
    if (!status)
        ((J *)data)->push_back({{"id", item->id}, {"type", (int)item->type}});
    return PRO_TK_NO_ERROR;
}
static ProError inspect_axis(ProGeomitem *item, ProError status, ProAppData data) {
    J record = {{"id", item->id},
                {"feature_id", *(int *)data},
                {"visit_query_code", status},
                {"origin", nullptr},
                {"direction", nullptr},
                {"geometry_known", false},
                {"data_query_code", nullptr},
                {"line_query_code", nullptr},
                {"free_query_code", nullptr}};
    if (!status) {
        AxisGeometry geometry = inspect_axis_geometry(item);
        record["data_query_code"] = geometry.data_code;
        record["line_query_code"] = geometry.line_code ? J(*geometry.line_code) : J(nullptr);
        record["free_query_code"] = geometry.free_code ? J(*geometry.free_code) : J(nullptr);
        record["geometry_known"] = geometry.known;
        if (geometry.known) {
            record["origin"] = geometry.origin;
            record["direction"] = geometry.direction;
        }
    }
    datum_axes.push_back(record);
    return PRO_TK_NO_ERROR;
}
static J feature_axes(ProFeature *feature) {
    datum_axes = J::array();
    ProError code = ProFeatureGeomitemVisit(feature, PRO_AXIS, inspect_axis, nullptr, &feature->id);
    return {{"datum_axes", datum_axes}, {"axes_query_code", code}};
}
// BUG-172: silent error check for hot inspection loops (logs and throws only on
// failure, avoiding tens of thousands of per-edge fflush() syscalls), plus
// periodic progress logging and safety caps so any true traversal stall names
// the last feature/surface ID instead of hanging silently.
static constexpr int INSPECT_MAX_FEATURES = 200000;
static constexpr int INSPECT_MAX_SURFACES = 500000;
static constexpr int INSPECT_MAX_HALF_EDGES = 5000000;
static constexpr int INSPECT_PROGRESS_STRIDE = 100;
static std::chrono::steady_clock::time_point inspect_started_at = std::chrono::steady_clock::now();
static int inspect_features_seen = 0;
static int inspect_surfaces_seen = 0;
static int inspect_half_edges_seen = 0;
static int inspect_last_feature_id = -1;
static int inspect_last_surface_id = -1;
static double inspect_mm_scale = 1.0;
static bool inspect_mm_scale_known = false;

static void check_quiet(ProError e, const char *op, int item_id = -1) {
    if (e != PRO_TK_NO_ERROR) {
        log("%s=%d item_id=%d\n", op, (int)e, item_id);
        last_toolkit_error = op;
        throw e;
    }
}

static ProError inspect_feature(ProFeature *f, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    inspect_features_seen++;
    inspect_last_feature_id = f->id;
    if (inspect_features_seen > INSPECT_MAX_FEATURES) {
        log("INSPECT_LIMIT_EXCEEDED phase=features count=%d last_id=%d\n", inspect_features_seen,
            inspect_last_feature_id);
        throw std::runtime_error("Model inspection exceeded feature traversal limit at feature " +
                                 std::to_string(inspect_last_feature_id));
    }
    ProFeattype t;
    ProFeatStatus state;
    ProName name = L"";
    ProBoolean incomplete = PRO_B_FALSE;
    check_quiet(ProFeatureTypeGet(f, &t), "ProFeatureTypeGet(f, &t)", f->id);
    check_quiet(ProFeatureStatusGet(f, &state), "ProFeatureStatusGet(f, &state)", f->id);
    check_quiet(ProFeatureIsIncomplete(f, &incomplete), "ProFeatureIsIncomplete(f, &incomplete)",
                f->id);
    ProModelitemNameGet(f, name);
    J item = {{"id", f->id},
              {"type", (int)t},
              {"type_name", type_name(t)},
              {"status", (int)state},
              {"incomplete", incomplete == PRO_B_TRUE},
              {"name", utf8(name)}};
    J dims = J::array();
    ProFeatureDimensionVisit(f, dimension_cb, nullptr, &dims);
    item["dimensions"] = dims;
    if (t == PRO_FEAT_CURVE) {
        ProSection section = nullptr;
        if (!ProFeatureSectionCopy(f, 0, &section)) {
            J sd = J::array();
            ProIntlist ids = nullptr;
            int count = 0;
            if (!ProSecdimIdsGet(section, &ids, &count)) {
                for (int i = 0; i < count; i++) {
                    double v;
                    ProSecdimType dt;
                    if (!ProSecdimValueGet(section, ids[i], &v)) {
                        ProSecdimTypeGet(section, ids[i], &dt);
                        sd.push_back({{"id", ids[i]}, {"value", v}, {"type", (int)dt}});
                    }
                }
                ProArrayFree((ProArray *)&ids);
            }
            item["sketch_dimensions"] = sd;
            ProIntlist cs = nullptr;
            int nc = 0;
            if (!ProSectionConstraintsIdsGet(section, &cs, &nc)) {
                item["sketch_constraint_count"] = nc;
                ProArrayFree((ProArray *)&cs);
            }
            ProSectionFree(&section);
        }
    }
    J geometry = J::array();
    ProFeatureGeomitemVisit(f, PRO_TYPE_UNUSED, collect_geom_ids, nullptr, &geometry);
    // FEAT-039/S04: a datum curve feature (intersect, projection) reports its
    // PRO_CURVE items only through a typed visit; PRO_TYPE_UNUSED answers an
    // empty list for it (live 2026-11-04: feature 120 owned curves 122/123 but
    // inspection showed zero items, so no client could reference the curve).
    // Merge the curve visit by id instead of replacing the generic list.
    J curves = J::array();
    if (!ProFeatureGeomitemVisit(f, PRO_CURVE, collect_geom_ids, nullptr, &curves))
        for (auto &entry : curves) {
            bool seen = false;
            for (auto &known : geometry)
                if (known.at("id") == entry.at("id")) {
                    seen = true;
                    break;
                }
            if (!seen)
                geometry.push_back(entry);
        }
    item["geometry_items"] = geometry;
    // T08 dependency evidence: parent/child feature IDs come from the live
    // model, never from a guess based on feature order. Group, pattern and
    // embedded state decide which targets may be operated on individually.
    int *parents = nullptr;
    int parent_count = 0;
    ProError parents_code = ProFeatureParentsGet(f, &parents, &parent_count);
    J parent_ids = J::array();
    if (!parents_code) {
        for (int i = 0; i < parent_count; i++)
            parent_ids.push_back(parents[i]);
        ProArrayFree((ProArray *)&parents);
    }
    item["parent_ids"] = parent_ids;
    item["parents_query_code"] = parents_code;
    int *children = nullptr;
    int child_count = 0;
    ProError children_code = ProFeatureChildrenGet(f, &children, &child_count);
    J child_ids = J::array();
    if (!children_code) {
        for (int i = 0; i < child_count; i++)
            child_ids.push_back(children[i]);
        ProArrayFree((ProArray *)&children);
    }
    item["child_ids"] = child_ids;
    item["children_query_code"] = children_code;
    ProGroupStatus group_status = PRO_GROUP_NONE;
    ProError group_code = ProFeatureGroupStatusGet(f, &group_status);
    item["group_status"] = group_code ? J(nullptr) : J((int)group_status);
    item["group_query_code"] = group_code;
    ProPatternStatus pattern_status = PRO_PATTERN_NONE;
    ProError pattern_code = ProFeaturePatternStatusGet(f, &pattern_status);
    item["pattern_status"] = pattern_code ? J(nullptr) : J((int)pattern_status);
    item["pattern_query_code"] = pattern_code;
    ProGrppatternStatus grppattern_status = PRO_GRP_PATTERN_NONE;
    ProError grppattern_code = ProFeatureGrppatternStatusGet(f, &grppattern_status);
    item["grppattern_status"] = grppattern_code ? J(nullptr) : J((int)grppattern_status);
    item["grppattern_query_code"] = grppattern_code;
    ProBoolean embedded = PRO_B_FALSE;
    ProError embedded_code = ProFeatureIsEmbedded(f, &embedded);
    item["embedded"] = embedded_code ? J(nullptr) : J(embedded == PRO_B_TRUE);
    item["embedded_query_code"] = embedded_code;
    if (t == PRO_FEAT_DATUM_AXIS) {
        J axes = feature_axes(f);
        item["axes_query_code"] = axes["axes_query_code"];
        item["datum_axes"] = axes["datum_axes"];
    }
    gfeatures.push_back(item);
    if (inspect_features_seen % INSPECT_PROGRESS_STRIDE == 0)
        log("INSPECT_PROGRESS phase=features count=%d last_id=%d elapsed_ms=%lld\n",
            inspect_features_seen, f->id, milliseconds_between(inspect_started_at));
    return PRO_TK_NO_ERROR;
}
static ProError inspect_edge(ProEdge edge, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    inspect_half_edges_seen++;
    if (inspect_half_edges_seen > INSPECT_MAX_HALF_EDGES) {
        log("INSPECT_LIMIT_EXCEEDED phase=edges half_edges=%d last_surface_id=%d\n",
            inspect_half_edges_seen, inspect_last_surface_id);
        throw std::runtime_error("Model inspection exceeded edge traversal limit at surface " +
                                 std::to_string(inspect_last_surface_id));
    }
    int id;
    check_quiet(ProEdgeIdGet(edge, &id), "ProEdgeIdGet(edge, &id)", inspect_last_surface_id);
    if (!visited_edges.insert(id).second)
        return PRO_TK_NO_ERROR;
    J item = {{"id", id}};
    ProGeomitemdata *data = nullptr;
    ProEnttype curve_type;
    ProEdgeTypeGet(edge, &curve_type);
    item["type"] = (int)curve_type;
    if (!ProEdgeDataGet(edge, &data) && data) {
        auto c = data->data.p_curve_data;
        if (c) {
            Pro3dPnt a, b;
            if (!ProLinedataGet(c, a, b)) {
                item["start"] = xyz(a);
                item["end"] = xyz(b);
            } else {
                // FEAT-068 A0: a circular edge is named by its own measured
                // centre/radius, never by pretending a centre point lies on the
                // edge. Raw arc frame vectors stay visible so the selector's
                // optional axis has a measured basis instead of a guess.
                ProVector arc_v1, arc_v2, arc_origin;
                double arc_start = 0, arc_end = 0, arc_radius = 0;
                if (!ProArcdataGet(c, arc_v1, arc_v2, arc_origin, &arc_start, &arc_end,
                                   &arc_radius))
                    item["arc"] = {{"origin", xyz(arc_origin)}, {"radius", arc_radius},
                                   {"start_angle", arc_start},  {"end_angle", arc_end},
                                   {"v1", xyz(arc_v1)},         {"v2", xyz(arc_v2)}};
            }
        }
        ProGeomitemdataFree(&data);
    }
    ProEdge ea = nullptr, eb = nullptr;
    ProSurface sa = nullptr, sb = nullptr;
    if (ProEdgeNeighborsGet(edge, &ea, &eb, &sa, &sb) == PRO_TK_NO_ERROR) {
        J adjacent = J::array();
        for (ProSurface surface : {sa, sb}) {
            int face_id = -1;
            if (surface && ProSurfaceIdGet(surface, &face_id) == PRO_TK_NO_ERROR && face_id >= 0)
                adjacent.push_back(face_id);
        }
        item["adjacent_surfaces"] = std::move(adjacent);
    }
    // P08/FEAT-014 candidate-edge discovery: one read-only contour query per
    // edge on sheetmetal parts. PRO_TK_NO_ERROR means the edge lies on a
    // green/white wall contour, PRO_TK_BAD_CONTEXT means it does not; any
    // other code stays unknown and keeps its real value. Budget-skipped edges
    // simply carry no record here (never a fabricated one).
    if (wall_contour_query_enabled) {
        if (wall_contour_checked >= WALL_CONTOUR_EDGE_BUDGET)
            wall_contour_bounded = true;
        else {
            ProEdge *contour = nullptr;
            ProError code = ProSmtedgeContourGet((ProPart)board, edge, &contour);
            if (contour)
                ProArrayFree((ProArray *)&contour);
            wall_contour_edges.push_back({{"edge_id", id}, {"wall_contour_query_code", code}});
            wall_contour_checked++;
        }
    }
    gedges.push_back(item);
    return PRO_TK_NO_ERROR;
}
static ProError inspect_contour(ProContour contour, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    return ProContourEdgeVisit((ProSurface)data, contour, inspect_edge, nullptr, nullptr);
}
static ProError inspect_surface(ProSurface surface, ProError status, ProAppData body_id) {
    if (status)
        return PRO_TK_NO_ERROR;
    inspect_surfaces_seen++;
    ProGeomitemdata *data = nullptr;
    check_quiet(ProSurfaceDataGet(surface, &data), "ProSurfaceDataGet(surface, &data)",
                inspect_last_surface_id);
    auto p = data->data.p_surface_data;
    int id;
    check_quiet(ProSurfaceIdGet(surface, &id), "ProSurfaceIdGet(surface, &id)",
                inspect_last_surface_id);
    inspect_last_surface_id = id;
    if (inspect_surfaces_seen > INSPECT_MAX_SURFACES) {
        ProGeomitemdataFree(&data);
        log("INSPECT_LIMIT_EXCEEDED phase=surfaces count=%d last_id=%d\n", inspect_surfaces_seen,
            inspect_last_surface_id);
        throw std::runtime_error("Model inspection exceeded surface traversal limit at surface " +
                                 std::to_string(inspect_last_surface_id));
    }
    J item = {{"id", id}, {"body_id", (int)(intptr_t)body_id}};
    if (p) {
        item["type"] = (int)p->type;
        item["bbox"] = J::array({xyz(p->xyz_min), xyz(p->xyz_max)});
        if (p->type == PRO_SRF_PLANE) {
            item["normal"] = xyz(p->srf_shape.plane.e3);
            item["origin"] = xyz(p->srf_shape.plane.origin);
        }
        if (p->type == PRO_SRF_CYL) {
            item["radius"] = p->srf_shape.cylinder.radius;
            item["origin"] = xyz(p->srf_shape.cylinder.origin);
            item["axis"] = xyz(p->srf_shape.cylinder.e3);
        }
    }
    ProSmtSurfType st;
    if (!ProSmtSurfaceTypeGet((ProPart)board, surface, &st))
        item["sheetmetal_type"] = (int)st;
    // FEAT-078: evaluate each surface's area in mm^2 when the model length unit
    // is known; leave null on unknown unit or kernel eval error.
    double surface_area_raw = 0.0;
    if (inspect_mm_scale_known &&
        ProSurfaceAreaEval(surface, &surface_area_raw) == PRO_TK_NO_ERROR &&
        std::isfinite(surface_area_raw) && surface_area_raw >= 0.0) {
        item["area_mm2"] = surface_area_raw * inspect_mm_scale * inspect_mm_scale;
    } else {
        item["area_mm2"] = nullptr;
    }
    gsurfaces.push_back(item);
    ProGeomitemdataFree(&data);
    check_quiet(ProSurfaceContourVisit(surface, inspect_contour, nullptr, surface),
                "ProSurfaceContourVisit(surface, inspect_contour, nullptr, surface)", id);
    if (inspect_surfaces_seen % INSPECT_PROGRESS_STRIDE == 0)
        log("INSPECT_PROGRESS phase=surfaces count=%d last_id=%d unique_edges=%d half_edges=%d "
            "elapsed_ms=%lld\n",
            inspect_surfaces_seen, id, (int)visited_edges.size(), inspect_half_edges_seen,
            milliseconds_between(inspect_started_at));
    return PRO_TK_NO_ERROR;
}
static ProError parameter_cb(ProParameter *param, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProParamvalue value;
    ProUnititem unit;
    J *params = (J *)data;
    if (!ProParameterValueWithUnitsGet(param, &value, &unit)) {
        J v;
        if (value.type == PRO_PARAM_DOUBLE)
            v = value.value.d_val;
        else if (value.type == PRO_PARAM_INTEGER)
            v = value.value.i_val;
        else if (value.type == PRO_PARAM_BOOLEAN)
            v = value.value.l_val != 0;
        else if (value.type == PRO_PARAM_STRING)
            v = utf8(value.value.s_val);
        else
            return PRO_TK_NO_ERROR;
        (*params)[utf8(param->id)] = {{"value", v}, {"type", (int)value.type}};
    }
    return PRO_TK_NO_ERROR;
}
static J assembly_inspection();
static void verify_saved(const J &before, const J &after, bool feature_state_commit = false);
static bool assembly_model() {
    ProMdlType t;
    CK(ProMdlTypeGet(board, &t));
    return t == PRO_MDL_ASSEMBLY;
}
// FEAT-057/T08: real mass properties from the model itself. Volume, surface
// area and the geometric centroid come from a unit-density calculation. Mass
// prefers the density Creo reports for the assigned material, then the density
// the caller supplies as an explicit what-if input; with neither, mass stays
// null and the receipt says why instead of inventing a material.
//
// An assembly is measured by the same native call, but its total only counts
// when every active occurrence contributed. A component whose part has no
// material, whose model did not resolve, or a truncated scan would silently
// understate the sum, so the read-only scan below proves the tree per
// occurrence first. Suppressed occurrences are skipped exactly as the kernel
// skips them; nothing is loaded, activated, regenerated or saved.
struct AssemblyMassScan {
    static constexpr int max_occurrences = 4096;
    static constexpr int max_depth = 32;
    int occurrences = 0;
    int suppressed = 0;
    int missing_material = 0;
    int unresolved = 0;
    bool truncated = false;
    J without_material = J::array();
    J unresolved_items = J::array();
    J visit_codes = J::array();

    bool complete() const {
        return !truncated && missing_material == 0 && unresolved == 0 && visit_codes.empty();
    }
};

static J mass_occurrence_json(const std::vector<int> &path) {
    J out = J::array();
    for (int id : path)
        out.push_back(id);
    return out;
}

struct MaterialScanContext {
    AssemblyMassScan *scan = nullptr;
    std::vector<int> path;
    int depth = 0;
};

static void scan_assembly_materials(ProSolid owner, const std::vector<int> &path, int depth,
                                    AssemblyMassScan &scan);

static ProError material_scan_callback(ProFeature *feature, ProError status, ProAppData data) {
    auto *context = static_cast<MaterialScanContext *>(data);
    AssemblyMassScan &scan = *context->scan;
    if (status)
        return status;
    if (scan.truncated)
        return PRO_TK_NO_ERROR;
    // The candidate path always ends at this feature: a failed type query may
    // hide a component, and an empty path could not name what is unaccounted for.
    std::vector<int> occurrence = context->path;
    occurrence.push_back(feature->id);
    ProFeattype type = PRO_FEAT_COMPONENT;
    ProError type_code = ProFeatureTypeGet(feature, &type);
    if (type_code) {
        scan.unresolved++;
        scan.unresolved_items.push_back(
            {{"occurrence_path", mass_occurrence_json(occurrence)}, {"code", (int)type_code}});
        return PRO_TK_NO_ERROR;
    }
    if (type != PRO_FEAT_COMPONENT)
        return PRO_TK_NO_ERROR;
    ProFeatStatus feature_status = PRO_FEAT_ACTIVE;
    ProError status_code = ProFeatureStatusGet(feature, &feature_status);
    if (status_code) {
        scan.unresolved++;
        scan.unresolved_items.push_back(
            {{"occurrence_path", mass_occurrence_json(occurrence)}, {"code", (int)status_code}});
        return PRO_TK_NO_ERROR;
    }
    if (feature_status == PRO_FEAT_SUPPRESSED || feature_status == PRO_FEAT_FAMTAB_SUPPRESSED ||
        feature_status == PRO_FEAT_SIMP_REP_SUPPRESSED ||
        feature_status == PRO_FEAT_PROG_SUPPRESSED) {
        scan.suppressed++;
        return PRO_TK_NO_ERROR;
    }
    if (scan.occurrences >= AssemblyMassScan::max_occurrences) {
        scan.truncated = true;
        return PRO_TK_NO_ERROR;
    }
    scan.occurrences++;
    ProMdl child = nullptr;
    ProError model_code = ProAsmcompMdlGet((ProAsmcomp *)feature, &child);
    if (model_code || !child) {
        scan.unresolved++;
        scan.unresolved_items.push_back(
            {{"occurrence_path", mass_occurrence_json(occurrence)}, {"code", (int)model_code}});
        return PRO_TK_NO_ERROR;
    }
    ProMdlType kind = PRO_MDL_PART;
    ProError kind_code = ProMdlTypeGet(child, &kind);
    if (kind_code) {
        scan.unresolved++;
        scan.unresolved_items.push_back(
            {{"occurrence_path", mass_occurrence_json(occurrence)}, {"code", (int)kind_code}});
        return PRO_TK_NO_ERROR;
    }
    if (kind == PRO_MDL_ASSEMBLY) {
        if (context->depth + 1 > AssemblyMassScan::max_depth) {
            scan.truncated = true;
            return PRO_TK_NO_ERROR;
        }
        scan_assembly_materials((ProSolid)child, occurrence, context->depth + 1, scan);
        return PRO_TK_NO_ERROR;
    }
    ProMaterial material = {};
    if (ProMaterialCurrentGet((ProSolid)child, &material) != PRO_TK_NO_ERROR) {
        scan.missing_material++;
        scan.without_material.push_back(mass_occurrence_json(occurrence));
    }
    return PRO_TK_NO_ERROR;
}

static void scan_assembly_materials(ProSolid owner, const std::vector<int> &path, int depth,
                                    AssemblyMassScan &scan) {
    MaterialScanContext context;
    context.scan = &scan;
    context.path = path;
    context.depth = depth;
    ProError visit_code =
        ProSolidFeatVisit(owner, material_scan_callback, nullptr, (ProAppData)&context);
    if (visit_code)
        scan.visit_codes.push_back((int)visit_code);
}

static J mass_properties_json(const J &op) {
    const bool assembly = assembly_model();
    J out = {{"volume_mm3", nullptr},
             {"surface_area_mm2", nullptr},
             {"mass_g", nullptr},
             {"density_g_cm3", nullptr},
             {"density_model_units", nullptr},
             {"mass_model_units", nullptr},
             {"center_of_mass_mm", nullptr},
             {"center_of_mass_model_units", nullptr},
             {"center_of_volume_mm", nullptr},
             {"material_assigned", false},
             {"mass_unit", nullptr},
             {"native_mass_unit", nullptr},
             {"mass_value_unit", "g"},
             {"mass_source", "none"},
             {"volume_query_code", nullptr},
             {"mass_query_code", nullptr},
             {"units_query_code", nullptr},
             {"density_source", "none"},
             {"density_is_effective_average", false},
             {"mass_unavailable_reason", nullptr},
             {"hint", nullptr},
             {"model_type", assembly ? "assembly" : "part"},
             {"component_scan", nullptr},
             {"source", "ProSolidMassPropertyWithDensityGet"}};
    auto length_units = inspect_length_units(board);
    out["length_unit"] = preview_utf8(std::wstring(length_units.length.name));
    auto length_scale = length_scale_to_mm(board, length_units);
    auto set_centroid = [&](const char *mm_key, const char *native_key, const ProMassProperty &mp) {
        out[native_key] = xyz(mp.center_of_gravity);
        if (length_scale.known)
            out[mm_key] = J::array({mp.center_of_gravity[0] * length_scale.scale,
                                    mp.center_of_gravity[1] * length_scale.scale,
                                    mp.center_of_gravity[2] * length_scale.scale});
    };
    ProMassProperty unit_density{};
    ProError volume_code = PRO_TK_NO_ERROR;
    volume_code = ProSolidMassPropertyWithDensityGet((ProSolid)board, nullptr,
                                                     PRO_MP_DENS_USE_ALWAYS, 1.0, &unit_density);
    out["volume_query_code"] = (int)volume_code;
    double volume_mm3 = 0.0;
    if (!volume_code) {
        // Unit density weights every point by volume, so this centroid is the
        // geometric centre: with mixed component densities it stays distinct
        // from the mass centroid reported further down.
        set_centroid("center_of_mass_mm", "center_of_mass_model_units", unit_density);
        if (length_scale.known)
            out["center_of_volume_mm"] = out["center_of_mass_mm"];
        if (auto mm3 = length_units.volume_mm3(unit_density.volume)) {
            volume_mm3 = *mm3;
            out["volume_mm3"] = volume_mm3;
        }
        if (auto mm2 = length_units.area_mm2(unit_density.surface_area))
            out["surface_area_mm2"] = *mm2;
    }
    // What Creo's own assembly query sums is only trustworthy when every active
    // occurrence had a material: an unmaterialed component otherwise weighs zero.
    AssemblyMassScan scan;
    if (assembly) {
        scan_assembly_materials((ProSolid)board, std::vector<int>(), 0, scan);
        out["component_scan"] = {{"occurrences", scan.occurrences},
                                 {"suppressed", scan.suppressed},
                                 {"without_material", scan.without_material},
                                 {"unresolved", scan.unresolved_items},
                                 {"truncated", scan.truncated},
                                 {"visit_codes", scan.visit_codes},
                                 {"complete", scan.complete()}};
    }
    // The model's own material first: it is the only density that describes the
    // model rather than a hypothesis about it.
    ProMaterial material = {};
    ProError material_code = ProMaterialCurrentGet((ProSolid)board, &material);
    if (assembly) {
        out["material_assigned"] = scan.complete() && scan.occurrences > 0;
        if (!scan.complete()) {
            if (scan.missing_material > 0) {
                out["mass_unavailable_reason"] = "component_material_missing";
                out["hint"] = "At least one active component has no material; assign a material "
                              "to every component, or pass density_g_cm3 for a uniform what-if";
            } else if (scan.unresolved > 0) {
                out["mass_unavailable_reason"] = "component_unavailable";
                out["hint"] = "At least one active component model did not resolve; mass is not "
                              "summed from an incomplete tree";
            } else {
                out["mass_unavailable_reason"] = "component_scan_incomplete";
                out["hint"] = "The component scan was truncated or a component visit failed; "
                              "mass is not summed from an unproven tree";
            }
        } else if (scan.occurrences == 0) {
            out["mass_unavailable_reason"] = "no_components";
            out["hint"] = "The assembly has no active components; there is no geometry to weigh";
        }
    } else {
        out["material_assigned"] = material_code == PRO_TK_NO_ERROR;
    }
    const bool material_path =
        assembly ? scan.complete() && scan.occurrences > 0 : material_code == PRO_TK_NO_ERROR;
    if (material_path) {
        ProMassProperty material_density{};
        ProError mass_code = ProSolidMassPropertyWithDensityGet(
            (ProSolid)board, nullptr, PRO_MP_DENS_DEFAULT, 0.0, &material_density);
        out["mass_query_code"] = (int)mass_code;
        auto mass_unit = inspect_mass_unit(board);
        out["units_query_code"] = (int)mass_unit.code;
        out["mass_unit"] = preview_utf8(std::wstring(mass_unit.unit.name));
        out["native_mass_unit"] = out["mass_unit"];
        auto grams_per_unit = grams_per_mass_unit(mass_unit.unit.name);
        if (!mass_code && grams_per_unit) {
            double grams = material_density.mass * *grams_per_unit;
            double density = volume_mm3 > 0.0 ? grams / volume_mm3 * 1000.0 : 0.0;
            if (grams > 0.0 && density > 0.0) {
                out["mass_g"] = grams;
                out["density_g_cm3"] = density;
                out["mass_model_units"] = material_density.mass;
                if (!assembly)
                    out["density_model_units"] = material_density.density;
                out["density_source"] = "model_material";
                out["mass_source"] = "native";
                // A mixed-density assembly has no single material density; the
                // reported one is total mass over total volume and is labelled
                // as such instead of passing for a component material.
                out["density_is_effective_average"] = assembly;
                set_centroid("center_of_mass_mm", "center_of_mass_model_units", material_density);
                return out;
            }
        }
        // FEAT-057: a material exists but the mass still failed, so the receipt
        // must say which link broke instead of repeating "assign a material".
        if (mass_code != PRO_TK_NO_ERROR) {
            out["mass_unavailable_reason"] = "material_query_failed";
            out["hint"] = assembly
                              ? "Creo's assembly mass query failed; check every component "
                                "material and its density"
                              : "The model material could not be measured; mass is unavailable";
        } else if (!grams_per_unit) {
            out["mass_unavailable_reason"] = "unsupported_mass_unit";
            out["hint"] = "The model mass unit is not g, kg or tonne; mass is not converted";
        } else if (volume_mm3 <= 0.0) {
            out["mass_unavailable_reason"] = "volume_unavailable";
            out["hint"] = "Volume is unknown, so the native mass cannot be normalized to grams";
        } else {
            out["mass_unavailable_reason"] = "material_density_unavailable";
            out["hint"] = assembly ? "A component material reports no usable density"
                                   : "The model material reports no usable density";
        }
    }
    // Caller-supplied density: geometry stays measured, the density is labelled
    // as a request so nobody mistakes a what-if for the part's material.
    if (op.contains("density_g_cm3") && op["density_g_cm3"].is_number() &&
        op["density_g_cm3"].get<double>() > 0.0) {
        double density = op["density_g_cm3"].get<double>();
        if (volume_mm3 > 0.0) {
            out["mass_g"] = volume_mm3 * density / 1000.0;
            out["density_g_cm3"] = density;
            out["density_source"] = "request";
            out["mass_source"] = "computed_from_density";
            out["mass_unavailable_reason"] = nullptr;
            out["hint"] = nullptr;
            return out;
        }
        out["mass_unavailable_reason"] = "volume_unavailable";
        out["hint"] = "Volume is unknown, so a supplied density cannot yield a mass";
        return out;
    }
    if (!out["mass_unavailable_reason"].is_null())
        return out;
    out["mass_unavailable_reason"] = "no_density";
    out["hint"] = "Assign a material with a density, or pass density_g_cm3, to get mass";
    return out;
}
// Body state names as declared in ProSolidBody.h; the numeric value is kept
// beside the name so a consumer never has to map the magic number itself
// (BUG-040). An unlisted value is reported as "unknown", never guessed.
static const char *body_state_name(ProSolidBodyState state) {
    switch (state) {
    case PRO_BODY_STATE_ACTIVE:
        return "active";
    case PRO_BODY_STATE_NO_GEOMETRY:
        return "no_geometry";
    case PRO_BODY_STATE_NO_CONTR_FEAT:
        return "no_contributing_feature";
    case PRO_BODY_STATE_CONSUMED:
        return "consumed";
    case PRO_BODY_STATE_MISSING:
        return "missing";
    case PRO_BODY_STATE_NONE:
        return "none";
    }
    return "unknown";
}

// FEAT-039/S01: quilt enumeration, shared measurements and quilt reference
// resolution live in quilt_query.h; this is the only include point.
#include "quilt_query.h"
#include "endpoint_weld.h"

// BUG-172: quiet datum-plane collection (same Plane records as datum_cb/geom_cb
// without emitting one fflush()'d line per datum plane).
static ProError geom_cb_quiet(ProGeomitem *gi, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProGeomitemdata *d = nullptr;
    if (ProGeomitemdataGet(gi, &d) == PRO_TK_NO_ERROR && d) {
        if (d->obj_type == PRO_SURFACE && d->data.p_surface_data &&
            d->data.p_surface_data->type == PRO_SRF_PLANE) {
            const ProPlanedata &p = d->data.p_surface_data->srf_shape.plane;
            Plane q = {};
            q.id = gi->id;
            memcpy(q.n, p.e3, sizeof(q.n));
            memcpy(q.o, p.origin, sizeof(q.o));
            planes.push_back(q);
        }
        ProGeomitemdataFree(&d);
    }
    return PRO_TK_NO_ERROR;
}
static ProError datum_cb_quiet(ProFeature *f, ProError status, ProAppData) {
    ProFeattype type;
    if (!status && ProFeatureTypeGet(f, &type) == PRO_TK_NO_ERROR && type == PRO_FEAT_DATUM)
        ProFeatureGeomitemVisit(f, PRO_SURFACE, geom_cb_quiet, nullptr, nullptr);
    return PRO_TK_NO_ERROR;
}
static void collect_datum_planes_quiet() {
    planes.clear();
    CK(ProSolidFeatVisit((ProSolid)board, datum_cb_quiet, nullptr, nullptr));
}

static ProError find_csys_geom_cb(ProGeomitem *gi, ProError status, ProAppData data) {
    if (status || !gi)
        return PRO_TK_NO_ERROR;
    if (gi->type == PRO_CSYS) {
        *(int *)data = gi->id;
        return PRO_TK_E_FOUND;
    }
    return PRO_TK_NO_ERROR;
}
static ProError find_default_csys_feat_cb(ProFeature *f, ProError status, ProAppData data) {
    if (status || !f)
        return PRO_TK_NO_ERROR;
    ProFeattype type;
    if (ProFeatureTypeGet(f, &type) == PRO_TK_NO_ERROR && type == PRO_FEAT_CSYS) {
        int csys_id = -1;
        ProFeatureGeomitemVisit(f, PRO_CSYS, find_csys_geom_cb, nullptr, &csys_id);
        if (csys_id >= 0) {
            *(int *)data = csys_id;
            return PRO_TK_E_FOUND;
        }
    }
    return PRO_TK_NO_ERROR;
}
static int find_default_csys_id() {
    int csys_id = -1;
    ProError visit =
        ProSolidFeatVisit((ProSolid)board, find_default_csys_feat_cb, nullptr, &csys_id);
    if (visit != PRO_TK_NO_ERROR && visit != PRO_TK_E_FOUND)
        check(visit, "FindDefaultCsys");
    if (csys_id < 0)
        throw std::runtime_error("No default coordinate system found");
    return csys_id;
}

static ProError any_surface_cb(ProSurface, ProError status, ProAppData data) {
    if (status)
        return PRO_TK_NO_ERROR;
    *(bool *)data = true;
    return PRO_TK_E_FOUND;
}
static ProError any_component_cb(ProFeature *f, ProError status, ProAppData data) {
    if (status || !f)
        return PRO_TK_NO_ERROR;
    ProFeattype type;
    if (ProFeatureTypeGet(f, &type) == PRO_TK_NO_ERROR && type == PRO_FEAT_COMPONENT) {
        *(bool *)data = true;
        return PRO_TK_E_FOUND;
    }
    return PRO_TK_NO_ERROR;
}
static bool model_has_solid() {
    if (assembly_model()) {
        bool has_component = false;
        ProError visit =
            ProSolidFeatVisit((ProSolid)board, any_component_cb, nullptr, &has_component);
        if (visit != PRO_TK_NO_ERROR && visit != PRO_TK_E_FOUND)
            check(visit, "CheckAssemblyHasComponent");
        return has_component;
    }
    ProSolidBody *list = nullptr;
    int n = 0;
    CK(ProSolidBodiesCollect((ProSolid)board, &list));
    bool solid = false;
    try {
        CK(ProArraySizeGet((ProArray)list, &n));
        for (int i = 0; i < n && !solid; i++) {
            ProSolidBodyState state;
            CK(ProSolidBodyStateGet(&list[i], &state));
            if (state != PRO_BODY_STATE_ACTIVE)
                continue;
            bool has_surface = false;
            ProError visit = ProSolidBodySurfaceVisit(&list[i], any_surface_cb, &has_surface);
            if (visit != PRO_TK_NO_ERROR && visit != PRO_TK_E_FOUND)
                check(visit, "CheckBodyHasSurface");
            if (has_surface)
                solid = true;
        }
    } catch (...) {
        if (list)
            ProArrayFree((ProArray *)&list);
        throw;
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    return solid;
}

static int active_body_count() {
    if (assembly_model())
        return 0;
    ProSolidBody *list = nullptr;
    int n = 0;
    CK(ProSolidBodiesCollect((ProSolid)board, &list));
    int active = 0;
    try {
        CK(ProArraySizeGet((ProArray)list, &n));
        for (int i = 0; i < n; i++) {
            ProSolidBodyState state;
            CK(ProSolidBodyStateGet(&list[i], &state));
            if (state == PRO_BODY_STATE_ACTIVE)
                active++;
        }
    } catch (...) {
        if (list)
            ProArrayFree((ProArray *)&list);
        throw;
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    return active;
}

struct LightHealthState {
    bool healthy = true;
    std::set<int> suppressed_seen;
};
static ProError check_feature_health_cb(ProFeature *f, ProError status, ProAppData data) {
    if (status || !f)
        return PRO_TK_NO_ERROR;
    auto *health = (LightHealthState *)data;
    ProFeatStatus state;
    ProBoolean incomplete = PRO_B_FALSE;
    check_quiet(ProFeatureStatusGet(f, &state), "ProFeatureStatusGet(f, &state)", f->id);
    check_quiet(ProFeatureIsIncomplete(f, &incomplete), "ProFeatureIsIncomplete(f, &incomplete)",
                f->id);
    if (state == PRO_FEAT_SUPPRESSED)
        health->suppressed_seen.insert(f->id);
    if (incomplete == PRO_B_TRUE) {
        health->healthy = false;
        return PRO_TK_NO_ERROR;
    }
    if (state != PRO_FEAT_ACTIVE && recorded_suppressed.count(f->id) == 0 &&
        f->id != temporarily_suppressed_loft) {
        health->healthy = false;
    }
    return PRO_TK_NO_ERROR;
}

static J inspection(bool require_healthy = true);

// BUG-172: lightweight per-operation health gate. Verifies every feature's
// status/incomplete flag and recorded_suppressed registry in O(features) without
// copying sections or traversing surfaces/edges/quilts/mass properties. Only on
// an actual unhealthy model does it fall back to full inspection(true) so the
// failure receipt still publishes the complete failed_features snapshot.
static void check_model_health() {
    LightHealthState health;
    CK(ProSolidFeatVisit((ProSolid)board, check_feature_health_cb, nullptr, &health));
    if (health.healthy) {
        for (int id : recorded_suppressed) {
            if (health.suppressed_seen.count(id) == 0) {
                health.healthy = false;
                break;
            }
        }
    }
    if (!health.healthy)
        inspection(true);
}

static J inspection(bool require_healthy) {
    inspect_started_at = std::chrono::steady_clock::now();
    inspect_features_seen = 0;
    inspect_surfaces_seen = 0;
    inspect_half_edges_seen = 0;
    inspect_last_feature_id = -1;
    inspect_last_surface_id = -1;
    {
        auto scale_info = length_scale_to_mm((ProMdl)board, inspect_length_units(board));
        inspect_mm_scale_known = scale_info.known;
        inspect_mm_scale = scale_info.known ? scale_info.scale : 1.0;
    }
    gfeatures = J::array();
    gsurfaces = J::array();
    gedges = J::array();
    failed_features = J::array();
    visited_edges.clear();
    // P08/FEAT-014: the bounded wall-contour query is a sheetmetal-related
    // check only. A plain part or an assembly never pays for it.
    wall_contour_query_enabled = false;
    wall_contour_checked = 0;
    wall_contour_bounded = false;
    wall_contour_edges = J::array();
    if (!assembly_model()) {
        ProMdlsubtype subtype;
        if (!ProMdlSubtypeGet(board, &subtype) && subtype == PROMDLSTYPE_PART_SHEETMETAL)
            wall_contour_query_enabled = true;
    }
    CK(ProSolidFeatVisit((ProSolid)board, inspect_feature, nullptr, nullptr));
    // System-required objects: the model's default coordinate system and the
    // template datum planes. A template datum is a parentless, non-embedded
    // datum from the model's initial block: sketch/extrude companions created
    // later by this service are also parentless, so only datums preceding the
    // first non-datum, non-csys feature count as template geometry.
    int default_csys_id = -1;
    int first_feature_id = -1;
    for (auto &f : gfeatures) {
        if (f["type"].get<int>() == PRO_FEAT_CSYS && default_csys_id < 0) {
            default_csys_id = f["id"].get<int>();
            continue;
        }
        int type = f["type"].get<int>();
        if (first_feature_id < 0 && type != PRO_FEAT_CSYS && type != PRO_FEAT_DATUM)
            first_feature_id = f["id"].get<int>();
    }
    for (auto &f : gfeatures) {
        int id = f["id"].get<int>();
        bool system = id == default_csys_id;
        if (!system && f["type"].get<int>() == PRO_FEAT_DATUM &&
            (f["embedded"].is_boolean() && !f["embedded"].get<bool>()) &&
            f["parents_query_code"] == 0 && f["parent_ids"].empty() &&
            (first_feature_id < 0 || id < first_feature_id))
            system = true;
        f["system_required"] = system;
    }
    // Suppression is only healthy when the model's recorded intentional set
    // says so. A recorded entry that is missing or no longer suppressed marks
    // the model unhealthy instead of silently widening the accepted state.
    auto accepted_state = [](const J &f) {
        if (f["incomplete"].get<bool>())
            return false;
        int status = f["status"].get<int>();
        if (status == PRO_FEAT_ACTIVE)
            return true;
        int id = f["id"].get<int>();
        return recorded_suppressed.count(id) > 0 || id == temporarily_suppressed_loft;
    };
    bool healthy = true;
    for (auto &f : gfeatures)
        if (!accepted_state(f))
            healthy = false;
    for (int id : recorded_suppressed) {
        bool found = false, suppressed = false;
        for (auto &f : gfeatures)
            if (f["id"].get<int>() == id) {
                found = true;
                suppressed = f["status"].get<int>() == PRO_FEAT_SUPPRESSED;
                break;
            }
        if (!found || !suppressed) {
            healthy = false;
            log("SUPPRESSION_REGISTRY_MISMATCH={\"feature_id\":%d,\"found\":%s,\"suppressed\":%s}"
                "\n",
                id, found ? "true" : "false", suppressed ? "true" : "false");
        }
    }
    if (require_healthy && !healthy) {
        // Preserve the offending features (id/name/type/type_name/status/
        // incomplete/geometry_items) before unwinding so the failure
        // response can publish them (BUG-082 H4).
        for (const auto &f : gfeatures)
            if (!accepted_state(f))
                failed_features.push_back(f);
        log("UNHEALTHY_FEATURES=%s\n", gfeatures.dump().c_str());
        throw std::runtime_error(
            "Regeneration produced a failed, suppressed or incomplete feature");
    }
    J bodies = J::array();
    bool isasm = assembly_model(), solid = false;
    ProSolidBody *list = nullptr;
    int n = 0;
    if (!isasm) {
        CK(ProSolidBodiesCollect((ProSolid)board, &list));
        CK(ProArraySizeGet((ProArray)list, &n));
    }
    int active_bodies = 0, material_bodies = 0;
    for (int i = 0; i < n; i++) {
        ProSolidBodyState state;
        CK(ProSolidBodyStateGet(&list[i], &state));
        J b = {{"id", list[i].id}, {"state", (int)state}, {"state_name", body_state_name(state)}};
        if (state == PRO_BODY_STATE_ACTIVE) {
            active_bodies++;
            size_t previous_surfaces = gsurfaces.size();
            CK(ProSolidBodySurfaceVisit(&list[i], inspect_surface,
                                        (ProAppData)(intptr_t)list[i].id));
            size_t surfaces = gsurfaces.size() - previous_surfaces;
            b["surface_count"] = surfaces;
            b["has_geometry"] = surfaces > 0;
            // Material membership is defined, not guessed: only an active body
            // that contributed at least one surface carries material.
            b["material"] = surfaces > 0;
            if (surfaces > 0) {
                solid = true;
                material_bodies++;
                Pro3dPnt bounds[2];
                CK(ProSolidBodyOutlineGet(&list[i], bounds));
                b["bbox"] = J::array({xyz(bounds[0]), xyz(bounds[1])});
                b["bbox_query_code"] = PRO_TK_NO_ERROR;
            } else {
                b["bbox"] = nullptr;
                b["bbox_query_code"] = nullptr;
            }
        } else {
            // Non-active records keep their object and ID but hold no material.
            // Their geometry is not visited, so presence stays unknown (null)
            // instead of being reported as measured empty (BUG-040).
            b["has_geometry"] = nullptr;
            b["material"] = false;
        }
        bodies.push_back(b);
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    if (isasm)
        for (auto f : gfeatures)
            if (f["type"].get<int>() == PRO_FEAT_COMPONENT)
                solid = true;
    auto length_units = inspect_length_units(board);
    auto length_scale = length_scale_to_mm(board, length_units);
    J length_unit = length_unit_json(length_units, length_scale);
    // FEAT-055/S01: quilts are enumerated per part with their own statuses.
    // Assemblies keep null — quilt records are part-level geometry.
    J quilts = nullptr, quilts_visit = nullptr;
    if (!isasm) {
        J collected = collect_model_quilts((ProSolid)board, length_units, length_scale);
        quilts = collected["records"];
        collected.erase("records");
        quilts_visit = collected;
    }
    // Coordinates/dimensions retain model units. Do not label native in^3 as mm^3.
    J units = length_units.code || !length_units.length.name[0] ? J(nullptr)
                                                                : J(utf8(length_units.length.name));
    // Two different counts, kept apart (BUG-040): `bodies` / `counts.bodies` is
    // the number of enumerated body objects, including non-active records that
    // hold no material; `body_counts` separates objects, active bodies and the
    // ones that actually carry material. Assemblies have no part bodies, so the
    // block is null instead of a zero that would look like an empty solid.
    J body_counts = nullptr;
    if (!isasm) {
        body_counts = {
            {"objects", n},
            {"records", (int)bodies.size()},
            {"active", active_bodies},
            {"with_material", material_bodies},
            {"without_material", (int)bodies.size() - material_bodies},
            {"counts_meaning",
             {{"bodies", "body_objects"}, {"with_material", "active_bodies_with_surfaces"}}}};
    }
    J result = {{"features", gfeatures},
                {"surfaces", gsurfaces},
                {"edges", gedges},
                {"quilts", quilts},
                {"quilts_visit", quilts_visit},
                {"bodies", bodies},
                {"body_counts", body_counts},
                {"healthy", healthy},
                {"units", units},
                {"units_query_code", length_units.code},
                {"length_unit", length_unit},
                {"has_solid", solid},
                {"center_of_gravity", nullptr},
                {"volume_query_code", nullptr},
                {"volume_mm3", nullptr},
                {"total_surface_area_mm2", nullptr},
                {"bounding_box_mm", nullptr}};
    J axes = J::array();
    for (const auto &f : gfeatures)
        if (f.contains("datum_axes")) {
            for (const auto &axis : f["datum_axes"])
                axes.push_back(axis);
        }
    result["datum_axes"] = axes;
    result["model_type"] = isasm ? "assembly" : "part";
    // P08/FEAT-014 candidate-edge discovery result. The per-edge records carry
    // only the real query code here; the eligible|ineligible|unknown status is
    // projected from that code by the Python side (creo_mechdog.sheetmetal),
    // alongside the model revision this check was observed at.
    if (wall_contour_query_enabled)
        log("WALL_CONTOUR_QUERY checked=%d bounded=%d\n", wall_contour_checked,
            wall_contour_bounded ? 1 : 0);
    result["wall_contour_check"] = {
        {"query", "ProSmtedgeContourGet"},       {"enabled", wall_contour_query_enabled},
        {"bounded", wall_contour_bounded},       {"budget", WALL_CONTOUR_EDGE_BUDGET},
        {"checked_edges", wall_contour_checked}, {"edges", wall_contour_edges}};
    if (isasm)
        result["components"] = assembly_inspection();
    else {
        ProMdlsubtype subtype;
        if (!ProMdlSubtypeGet(board, &subtype) && subtype == PROMDLSTYPE_PART_SHEETMETAL)
            result["model_type"] = "sheetmetal";
    }
    if (solid) {
        ProMassProperty mp;
        ProError e = ProSolidMassPropertyWithDensityGet((ProSolid)board, nullptr,
                                                        PRO_MP_DENS_USE_ALWAYS, 1, &mp);
        result["volume_query_code"] = e;
        if (!e) {
            bool finite = true;
            for (double value : mp.center_of_gravity)
                finite = finite && std::isfinite(value);
            if (finite)
                result["center_of_gravity"] = xyz(mp.center_of_gravity);
            auto volume = length_units.volume_mm3(mp.volume);
            if (volume)
                result["volume_mm3"] = *volume;
            auto surface_area = length_units.area_mm2(mp.surface_area);
            if (surface_area && std::isfinite(*surface_area) && *surface_area >= 0.0)
                result["total_surface_area_mm2"] = *surface_area;
        }
    }
    solid_bounds::inspect((ProSolid)board, isasm, length_scale, result);
    collect_datum_planes_quiet();
    J ds = J::array();
    for (auto p : planes)
        ds.push_back({{"id", p.id}, {"normal", xyz(p.n)}, {"origin", xyz(p.o)}});
    result["datum_planes"] = ds;
    ProModelitem owner;
    CK(ProMdlToModelitem(board, &owner));
    J params = J::object();
    ProParameterVisit(&owner, nullptr, parameter_cb, &params);
    result["parameters"] = params;
    log("INSPECT_SUMMARY features=%d surfaces=%d edges=%d half_edges=%d elapsed_ms=%lld\n",
        (int)gfeatures.size(), (int)gsurfaces.size(), (int)gedges.size(), inspect_half_edges_seen,
        milliseconds_between(inspect_started_at));
    return result;
}
#include "geometry_selectors.cpp"

// DEV-089 T1: set only while resolving the assembly side of a constraint that
// names a placed component. The moving component is never described here: it has
// no solved pose yet, so an assembly-space selector on it is refused rather than
// resolved against a guessed position.
static bool occurrence_placement_available = false;
static ProMatrix occurrence_placement = {};

static ProSelection resolve(const J &r) {
    // BUG-094 backstop: fail with a clear message instead of a JSON missing-key error.
    if (!r.is_object() || !r.contains("kind") || !r["kind"].is_string())
        throw std::runtime_error("Reference requires a {kind:...} selection object");
    if (r.at("kind") == "default_csys") {
        return selection(find_default_csys_id(), PRO_CSYS);
    }
    if (r.at("kind") == "geometry_selector") {
        // DEV-089 T1: resolve one physical edge/face by measured geometry so a
        // plan survives a rebuild that renumbers ids. Zero or multiple matches
        // are refused with the candidate count; the first candidate is never
        // chosen. An assembly-space selector is mapped into the placed
        // component's frame first (see occurrence_placement_available).
        const std::string selector_space = r.value("coordinate_space", "model");
        J selector = r;
        if (selector_space == "assembly") {
            if (!occurrence_placement_available)
                throw std::runtime_error(
                    "geometry_selector coordinate_space='assembly' needs a placed component "
                    "context: use it on assembly_reference of a component constraint that names "
                    "assembly_component, not on the moving component or a part feature");
            selector = selector_to_component_model(r, occurrence_placement);
        } else if (selector_space != "model") {
            throw std::runtime_error(
                "geometry_selector coordinate_space must be 'model' or 'assembly', not '" +
                selector_space + "'");
        }
        MillimeterScale selector_scale =
            length_scale_to_mm((ProMdl)board, inspect_length_units(board));
        if (!selector_scale.known)
            throw std::runtime_error(
                "geometry_selector cannot convert the model length unit to millimetres; pass an "
                "explicit geometry id from creo_inspect_model instead");
        J state = inspection(false);
        if (selector.contains("feature")) {
            ProFeature owner = feature(selector.at("feature"));
            J surface_items = J::array();
            const ProError surf_code = ProFeatureGeomitemVisit(
                &owner, PRO_SURFACE, collect_geom_ids, nullptr, &surface_items);
            if (surf_code != PRO_TK_E_NOT_FOUND)
                check(surf_code, "ProFeatureGeomitemVisit(selector owner surfaces)");
            std::set<int> owned_surfaces;
            for (const auto &item : surface_items)
                owned_surfaces.insert(item.at("id").get<int>());
            if (selector.at("target") == "edge") {
                // FEAT-076: include both edges owned directly by the feature and edges
                // bordering any surface owned by that feature (e.g. cut rims).
                J edge_items = J::array();
                const ProError edge_code = ProFeatureGeomitemVisit(
                    &owner, PRO_EDGE, collect_geom_ids, nullptr, &edge_items);
                if (edge_code != PRO_TK_E_NOT_FOUND)
                    check(edge_code, "ProFeatureGeomitemVisit(edge selector owner)");
                std::set<int> owned_edges;
                for (const auto &item : edge_items)
                    owned_edges.insert(item.at("id").get<int>());
                J &edges = state.at("edges");
                J filtered = J::array();
                for (auto &item : edges) {
                    bool belongs = owned_edges.count(item.at("id").get<int>()) > 0;
                    if (!belongs && item.contains("adjacent_surfaces") &&
                        item["adjacent_surfaces"].is_array()) {
                        for (const auto &sid : item["adjacent_surfaces"]) {
                            if (sid.is_number_integer() &&
                                owned_surfaces.count(sid.get<int>()) > 0) {
                                belongs = true;
                                break;
                            }
                        }
                    }
                    if (belongs)
                        filtered.push_back(std::move(item));
                }
                edges = std::move(filtered);
            } else {
                J &surfaces = state.at("surfaces");
                J filtered = J::array();
                for (auto &item : surfaces)
                    if (owned_surfaces.count(item.at("id").get<int>()))
                        filtered.push_back(std::move(item));
                surfaces = std::move(filtered);
            }
        }
        GeometrySelectorOutcome selector_outcome =
            match_geometry_selector(selector, state, selector_scale.scale);
        if (selector.contains("feature"))
            selector_outcome.diagnostic["feature"] = selector["feature"];
        // DEV-098 / BUG-182: keep the caller's coordinate space visible and project
        // nearest_surfaces back into assembly coordinates so callers do not have to
        // guess which frame origin_mm/normal belong to.
        if (selector_space == "assembly") {
            selector_outcome.diagnostic["requested_coordinate_space"] = "assembly";
            selector_outcome.diagnostic["nearest_coordinate_space"] = "component";
            if (selector_outcome.diagnostic.contains("nearest_surfaces") &&
                selector_outcome.diagnostic["nearest_surfaces"].is_array()) {
                for (auto &item : selector_outcome.diagnostic["nearest_surfaces"]) {
                    item["coordinate_space"] = "component";
                    if (item.contains("origin_mm"))
                        item["assembly_origin_mm"] =
                            model_point_to_assembly(item["origin_mm"], occurrence_placement);
                    if (item.contains("normal"))
                        item["assembly_normal"] =
                            model_vector_to_assembly(item["normal"], occurrence_placement);
                    if (item.contains("axis"))
                        item["assembly_axis"] =
                            model_vector_to_assembly(item["axis"], occurrence_placement);
                }
            }
            if (!selector_outcome.matched) {
                selector_outcome.error +=
                    " (requested coordinate_space='assembly' was transformed into the placed "
                    "component's model frame to search component faces; nearest_surfaces carries "
                    "component origin_mm/normal alongside assembly_origin_mm/assembly_normal and "
                    "copyable suggested_reference).";
            }
        }
        if (!selector_outcome.matched) {
            stage_operation_result({{"geometry_selector_diagnostic", selector_outcome.diagnostic}});
            throw std::runtime_error(selector_outcome.error);
        }
        stage_operation_result({{"geometry_selector_resolution", selector_outcome.diagnostic}});
        // BUG-155: validate the matched id against the type the selector asked for.
        // Without this an id/type mismatch only surfaced later as a bare
        // ProModelitemInit -23 with no target or id in the message.
        if (selector_outcome.target == "edge") {
            ProEdge edge;
            const ProError code = ProEdgeInit((ProSolid)board, selector_outcome.id, &edge);
            if (code != PRO_TK_NO_ERROR)
                throw std::runtime_error("geometry_selector matched edge id " +
                                         std::to_string(selector_outcome.id) +
                                         " but ProEdgeInit returned " + std::to_string(code));
        } else {
            ProSurface surface;
            const ProError code = ProSurfaceInit((ProSolid)board, selector_outcome.id, &surface);
            if (code != PRO_TK_NO_ERROR)
                throw std::runtime_error("geometry_selector matched surface id " +
                                         std::to_string(selector_outcome.id) +
                                         " but ProSurfaceInit returned " + std::to_string(code));
        }
        return selection(selector_outcome.id,
                         selector_outcome.target == "edge" ? PRO_EDGE : PRO_SURFACE);
    }
    if (r.at("kind") == "quilt_feature")
        return resolve_quilt_reference(r, (ProSolid)board, inspect_length_units(board),
                                       length_scale_to_mm(board, inspect_length_units(board)));
    if (r.at("kind") == "datum_csys_feature" || r.at("kind") == "datum_point_feature") {
        ProType type = r["kind"] == "datum_csys_feature" ? PRO_CSYS : PRO_POINT;
        ProFeature f = feature(r.at("label"));
        J ids = J::array();
        CK(ProFeatureGeomitemVisit(&f, type, collect_geom_ids, nullptr, &ids));
        if (ids.size() != 1)
            throw std::runtime_error("Feature reference must identify exactly one geometry item");
        return selection(ids[0]["id"], type);
    }
    std::string kind = r.at("kind");
    if (kind == "part") {
        ProModelitem mi;
        CK(ProMdlToModelitem(board, &mi));
        ProSelection s;
        CK(ProSelectionAlloc(nullptr, &mi, &s));
        return s;
    }
    if (kind == "quilt")
        // S00 R1: validated against the real quilt collection, with bounded
        // candidates in the failure message; never a blind PRO_QUILT pick.
        return resolve_quilt_reference(r, (ProSolid)board, inspect_length_units(board),
                                       length_scale_to_mm(board, inspect_length_units(board)));
    if (kind == "csys" || kind == "point")
        return selection(r.at("id"), kind == "csys" ? PRO_CSYS : PRO_POINT);
    if (kind == "feature")
        return selection(feature_id(r.contains("label") ? r["label"] : r["id"]), PRO_FEATURE);
    if (kind == "body") {
        int id = r.value("id", -1);
        if (id < 0) {
            ProSolidBody b;
            CK(ProSolidDefaultBodyGet((ProSolid)board, &b));
            id = b.id;
        }
        return selection(id, PRO_BODY);
    }
    if (kind == "surface" || kind == "edge" || kind == "axis" || kind == "curve" ||
        kind == "dimension") {
        int id = r.at("id");
        return selection(id, kind == "surface" ? PRO_SURFACE
                             : kind == "edge"  ? PRO_EDGE
                             : kind == "axis"  ? PRO_AXIS
                             : kind == "curve" ? PRO_CURVE
                                               : PRO_DIMENSION);
    }
    if (kind == "plane" || kind == "datum_plane") {
        // Backstop for the Python contract: this branch resolves by id/axis/
        // normal only. The 2026-11-04 trim probe submitted
        // {kind:'datum_plane',label:'RIGHT'}; the label was dropped, the default
        // axis filter picked TOP, and the trim never regenerated. Refuse the
        // label instead of choosing a different plane than the caller named.
        if (r.contains("label"))
            throw std::runtime_error(
                std::string("Kind '") + kind +
                "' plane references resolve by id/axis/normal and do not honour a label; use "
                "{kind:'datum_feature',label:...} for a plane feature label");
        J candidates = J::array();
        J datum_list = J::array();
        if (kind == "datum_plane") {
            collect_datum_planes_quiet();
            for (const auto &p : planes)
                datum_list.push_back({{"id", p.id}, {"normal", xyz(p.n)}, {"origin", xyz(p.o)}});
            candidates = datum_list;
        } else {
            J state = inspection(false);
            datum_list = state["datum_planes"];
            candidates = state["surfaces"];
        }
        if (r.contains("id")) {
            if (r.contains("axis") || r.contains("normal") || r.contains("offset"))
                throw std::runtime_error("Plane id cannot be combined with axis, normal or offset");
            const J &raw_id = r.at("id");
            if (!raw_id.is_number_integer() || raw_id < 0 || raw_id > 2147483647)
                throw std::runtime_error("Plane geometry id must be a nonnegative 32-bit integer");
            int id = raw_id.get<int>();
            // A generic plane ID may name either a solid face or a datum plane;
            // datum_plane IDs must appear in the dedicated inspection collection.
            if (kind == "plane")
                for (const auto &datum : datum_list)
                    candidates.push_back(datum);
            for (const auto &candidate : candidates) {
                if (candidate.at("id").get<int>() != id)
                    continue;
                if (!candidate.contains("normal"))
                    throw std::runtime_error("Plane geometry id is not a planar surface: " +
                                             std::to_string(id));
                return selection(id, PRO_SURFACE);
            }
            throw std::runtime_error((kind == "datum_plane" ? "Datum plane geometry id not found: "
                                                            : "Plane geometry id not found: ") +
                                     std::to_string(id));
        }
        V desired;
        if (r.contains("normal"))
            desired = normalized(vec(r["normal"]));
        else {
            std::string axis = r.value("axis", "z");
            desired = axis == "x" ? V{1, 0, 0} : axis == "y" ? V{0, 1, 0} : V{0, 0, 1};
        }
        double offset = r.value("offset", 0.0);
        std::vector<int> matches;
        for (auto &p : candidates) {
            if (!p.contains("normal"))
                continue;
            V normal = normalized(vec(p["normal"])), origin = vec(p["origin"]);
            if (fabs(fabs(dot(normal, desired)) - 1) < 1e-7 &&
                fabs(dot(origin, desired) - offset) < 1e-6)
                matches.push_back(p["id"].get<int>());
        }
        if (kind == "datum_plane" && fabs(offset) < 1e-9 && matches.size() > 1)
            matches = {*std::min_element(matches.begin(), matches.end())};
        if (matches.size() != 1) {
            if (kind == "plane" && candidates.empty()) {
                throw std::runtime_error(
                    "Plane reference {kind:'plane', normal, offset} only matches solid faces, "
                    "and this model has 0 solid surfaces yet (has_solid=false). On an empty "
                    "part or sheetmetal model, use {kind:'datum_plane', axis:'x'|'y'|'z', "
                    "offset:N} or {kind:'datum_plane', id:N} from inspect");
            }
            // BUG-116: report how many faces matched instead of only "not one",
            // and name the form that survives a populated model.
            std::string planes;
            for (size_t i = 0; i < matches.size(); i++)
                planes += (i ? "," : "") + std::to_string(matches[i]);
            throw std::runtime_error(
                "Plane reference must identify exactly one surface; " +
                std::to_string(matches.size()) + " candidate surface(s) match normal/offset " +
                (r.contains("normal") ? J(r["normal"]).dump()
                                      : std::string("axis=") + r.value("axis", "z")) +
                " offset=" + std::to_string(offset) + " (ids: " + planes +
                "). Use an explicit surface or plane id from inspect, or the geometric form "
                "{kind:'plane',normal:[...],offset:N}; the datum_plane axis+offset form needs "
                "exactly one datum plane at that height");
        }
        return selection(matches[0], PRO_SURFACE);
    }
    if (kind == "datum_axis_feature") {
        ProFeature f = feature(r.at("label"));
        J ids = J::array();
        CK(ProFeatureGeomitemVisit(&f, PRO_AXIS, collect_geom_ids, nullptr, &ids));
        if (ids.size() != 1)
            throw std::runtime_error("Datum feature must have one axis");
        return selection(ids[0]["id"], PRO_AXIS);
    }
    if (kind == "datum_feature") {
        int fid = feature_id(r.at("label"));
        ProFeature f = feature(fid);
        ProFeattype type;
        CK(ProFeatureTypeGet(&f, &type));
        if (type != PRO_FEAT_DATUM)
            throw std::runtime_error("Datum feature label does not identify a datum plane");
        planes.clear();
        CK(ProFeatureGeomitemVisit(&f, PRO_SURFACE, geom_cb, nullptr, nullptr));
        if (planes.size() != 1)
            throw std::runtime_error("Datum feature does not contain one plane");
        return selection(planes[0].id, PRO_SURFACE);
    }
    throw std::runtime_error("Unknown model reference kind: " + kind);
}
static void set_refs(ProElement e, const J &refs) {
    ProReference *values = nullptr;
    CK(ProArrayAlloc((int)refs.size(), sizeof(ProReference), 1, (ProArray *)&values));
    for (size_t i = 0; i < refs.size(); i++) {
        ProSelection s = resolve(refs[i]);
        CK(ProSelectionToReference(s, &values[i]));
        ProSelectionFree(&s);
    }
    CK(ProElementReferencesSet(e, values));
    ProArrayFree((ProArray *)&values);
}
static void remember(const J &op, ProFeature f, J extra = J::object()) {
    std::string label = op.at("label");
    extra["feature_id"] = f.id;
    extra["op"] = op.at("op");
    aliases[label] = extra;
}
// Dimension and relation edits reshape sketch entities behind the recorded
// entity payloads; mark every sketch alias so a later byte-identical
// replacement cannot be mistaken for a no-op against the live section.
static void mark_sketch_geometry_stale() {
    for (auto it = aliases.begin(); it != aliases.end(); ++it)
        if (it.value().contains("entity_ids"))
            it.value()["geometry_stale"] = true;
}
// B4/F08: per-body material evidence for a scoped cut. Only active bodies are
// fingerprinted; a body whose surfaces cannot be visited keeps a null
// surface_count so a comparison can answer "unknown" instead of "equal".
static ProError count_body_surface(ProSurface surface, ProError status, ProAppData data) {
    (void)surface;
    if (status == PRO_TK_NO_ERROR)
        (*(int *)data)++;
    return PRO_TK_NO_ERROR;
}
static J body_fingerprints() {
    if (assembly_model())
        return nullptr;
    ProSolidBody *list = nullptr;
    ProError collect = ProSolidBodiesCollect((ProSolid)board, &list);
    if (collect != PRO_TK_NO_ERROR) {
        if (list)
            ProArrayFree((ProArray *)&list);
        return nullptr;
    }
    int n = 0;
    CK(ProArraySizeGet((ProArray)list, &n));
    J out = J::object();
    for (int i = 0; i < n; i++) {
        ProSolidBodyState state;
        CK(ProSolidBodyStateGet(&list[i], &state));
        if (state != PRO_BODY_STATE_ACTIVE)
            continue;
        int surfaces = 0;
        ProError visit = ProSolidBodySurfaceVisit(&list[i], count_body_surface, &surfaces);
        Pro3dPnt bounds[2];
        ProError outline = ProSolidBodyOutlineGet(&list[i], bounds);
        out[std::to_string(list[i].id)] = {
            {"surface_count", visit == PRO_TK_NO_ERROR ? J(surfaces) : J(nullptr)},
            {"visit_code", visit},
            {"bbox_query_code", outline},
            {"bbox",
             outline == PRO_TK_NO_ERROR ? J::array({xyz(bounds[0]), xyz(bounds[1])}) : J(nullptr)}};
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    return out;
}
static bool same_point(const J &a, const J &b) {
    if (!a.is_array() || !b.is_array() || a.size() != b.size())
        return false;
    for (size_t i = 0; i < a.size(); i++)
        if (fabs(a[i].get<double>() - b[i].get<double>()) > 1e-6)
            return false;
    return true;
}
static bool same_bbox(const J &a, const J &b) {
    if (!a.is_array() || !b.is_array() || a.size() != 2 || b.size() != 2)
        return false;
    return same_point(a[0], b[0]) && same_point(a[1], b[1]);
}
// True when every body outside the requested scope kept its surface count and
// bounding box. null means the comparison could not be made; it is never
// reported as true on missing evidence, and a half-known pair (one side's
// query failed) is unknown rather than "changed" or "equal".
static J non_target_bodies_unchanged(const J &before, const J &after, const J &requested) {
    if (!before.is_object() || !after.is_object())
        return nullptr;
    std::set<std::string> targets;
    for (const auto &id : requested)
        targets.insert(std::to_string(id.get<int>()));
    bool unknown = false;
    for (auto it = before.begin(); it != before.end(); ++it) {
        if (targets.count(it.key()))
            continue;
        if (!after.contains(it.key()))
            return false;
        const J &was = it.value(), &now = after[it.key()];
        const J &was_surfaces = was.value("surface_count", J(nullptr));
        const J &now_surfaces = now.value("surface_count", J(nullptr));
        const J &was_bbox = was.value("bbox", J(nullptr));
        const J &now_bbox = now.value("bbox", J(nullptr));
        if (!was_surfaces.is_number() || !now_surfaces.is_number() || !was_bbox.is_array() ||
            !now_bbox.is_array()) {
            unknown = true;
            continue;
        }
        if (was_surfaces != now_surfaces || !same_bbox(was_bbox, now_bbox))
            return false;
    }
    // A body that appeared outside the scope is also a change: a scoped cut
    // cannot create one, so claiming the rest stayed put would hide it.
    for (auto it = after.begin(); it != after.end(); ++it)
        if (!before.contains(it.key()) && !targets.count(it.key()))
            return false;
    return unknown ? J(nullptr) : J(true);
}
static int scope_body_id(const J &op) {
    const J &value = op.at("scope").at("body_ids").at(0);
    if (value.is_number_integer()) {
        constexpr int initial_body_id = -5778;
        const double id = value.get<double>();
        if (id == initial_body_id || (id > 0 && id <= std::numeric_limits<int>::max()))
            return value.get<int>();
    }
    throw std::runtime_error(
        "F08_SCOPE_INVALID_BODY_ID: use a positive 32-bit integer or Creo's initial body ID");
}
// The requested body must exist and hold material before the feature is built;
// otherwise the feature would report success while removing nothing.
static void require_scopable_body(int id) {
    ProSolidBody *list = nullptr;
    int n = 0;
    CK(ProSolidBodiesCollect((ProSolid)board, &list));
    CK(ProArraySizeGet((ProArray)list, &n));
    bool found = false;
    ProSolidBodyState found_state = PRO_BODY_STATE_NONE;
    for (int i = 0; i < n; i++)
        if (list[i].id == id && list[i].owner == board && list[i].type == PRO_BODY) {
            found = true;
            CK(ProSolidBodyStateGet(&list[i], &found_state));
            break;
        }
    if (list)
        ProArrayFree((ProArray *)&list);
    if (!found)
        throw std::runtime_error(
            "F08_SCOPE_RESOLVE_FAILED: scope.body_ids names a body id that this part does not "
            "contain; inspect bodies[].id and retry");
    if (found_state != PRO_BODY_STATE_ACTIVE)
        throw std::runtime_error(
            "F08_SCOPE_RESOLVE_FAILED: scope.body_ids names a body without active material");
}
static void body_options(ProElement root, const J &op) {
    std::string mode = op.value("mode", "add");
    bool new_body = op.value("new_body", false);
    ProElement b = node(root, PRO_E_BODY);
    if (mode == "cut") {
        if (op.contains("scope")) {
            int target = scope_body_id(op);
            require_scopable_body(target);
            integer(b, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
            // Explicit scope is an exact ID. The generic resolver interprets
            // negative IDs as a request for the current default body.
            ProSelection s = selection(target, PRO_BODY);
            ref(b, PRO_E_BODY_SELECT, s);
            ProSelectionFree(&s);
        } else
            integer(b, PRO_E_BODY_USE, PRO_BODY_USE_ALL);
        return;
    }
    if (!model_has_solid() || new_body)
        integer(b, PRO_E_BODY_USE, PRO_BODY_USE_NEW);
    else {
        integer(b, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
        ProSelection s = resolve({{"kind", "body"}});
        ref(b, PRO_E_BODY_SELECT, s);
        ProSelectionFree(&s);
    }
}
static ProFeature offset_plane(const J &reference, double offset, const std::wstring &name,
                               double *angle = nullptr, const J *axis = nullptr,
                               bool flip = false) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM);
    text(root, PRO_E_STD_FEATURE_NAME, name.c_str());
    ProElement constraints = node(root, PRO_E_DTMPLN_CONSTRAINTS);
    ProElement c = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
    ProSelection s = resolve(reference);
    integer(c, PRO_E_DTMPLN_CONSTR_TYPE, angle ? PRO_DTMPLN_ANG : PRO_DTMPLN_OFFS);
    ref(c, PRO_E_DTMPLN_CONSTR_REF, s);
    real(c, angle ? PRO_E_DTMPLN_CONSTR_REF_ANGLE : PRO_E_DTMPLN_CONSTR_REF_OFFSET,
         angle ? *angle : offset);
    ProSelectionFree(&s);
    if (angle) {
        if (!axis)
            throw std::runtime_error("Angled plane requires an axis");
        ProElement through = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
        integer(through, PRO_E_DTMPLN_CONSTR_TYPE, PRO_DTMPLN_THRU);
        s = resolve(*axis);
        ref(through, PRO_E_DTMPLN_CONSTR_REF, s);
        ProSelectionFree(&s);
    }
    // BUG-187: the support normal is not under the caller's control when a
    // sketch is attached to an offset datum plane. An explicit flip keeps the
    // plane in place while publishing the opposite normal, so the sketch v_axis
    // and the extrusion direction stay predictable.
    if (flip)
        integer(root, PRO_E_DTMPLN_FLIP_DIR, PRO_DTMPLN_FLIP_DIR_YES);
    ProFeature f = create(root);
    CK(ProElementFree(&root));
    return f;
}
// FEAT-053/BUG-097 L2: through_points supports have no exactly perpendicular
// datum plane on this SDK, and the kernel then parks the unfinished sketch on
// world XY (identity section location) until CompleteFeature fails with an
// empty ProErrorList. `orientation_exact` says whether the chosen orientation
// reference really is perpendicular, so sketch() can build helper planes.
struct Frame {
    V origin, u, v, n;
    int surface, orientation;
    bool orientation_exact = false;
};
static Frame sketch_frame(const J &op) {
    Frame f = {};
    J p = op.at("plane");
    if (p.is_string()) {
        std::string name = p;
        int axis = name == "XY" ? 2 : name == "XZ" ? 1 : 0;
        f.n = axis == 2 ? V{0, 0, 1} : axis == 1 ? V{0, -1, 0} : V{1, 0, 0};
        f.u = axis == 0 ? V{0, 1, 0} : V{1, 0, 0};
        double offset = op.value("offset", 0.0);
        J reference = {{"kind", "datum_plane"},
                       {"axis", axis == 0   ? "x"
                                : axis == 1 ? "y"
                                            : "z"},
                       {"offset", 0}};
        if (fabs(offset) > 1e-9) {
            auto df =
                offset_plane(reference, offset, wide(op.at("label").get<std::string>() + "_plane"));
            planes.clear();
            CK(ProFeatureGeomitemVisit(&df, PRO_SURFACE, geom_cb, nullptr, nullptr));
            if (planes.size() != 1)
                throw PRO_TK_GENERAL_ERROR;
            f.surface = planes[0].id;
        } else {
            ProSelection s = resolve(reference);
            ProModelitem mi;
            CK(ProSelectionModelitemGet(s, &mi));
            f.surface = mi.id;
            ProSelectionFree(&s);
        }
    } else {
        ProSelection s = resolve(p.at("reference"));
        ProModelitem mi;
        CK(ProSelectionModelitemGet(s, &mi));
        f.surface = mi.id;
        ProSelectionFree(&s);
    }
    // Read the actual selected support once for both named and explicit forms.
    // The reported frame is the frame used to build the section, not an echo
    // of the input selection or an assumed world-XY plane.
    ProSurface support;
    CK(ProSurfaceInit((ProSolid)board, f.surface, &support));
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(support, &data));
    auto shape = data ? data->data.p_surface_data : nullptr;
    bool planar = shape && shape->type == PRO_SRF_PLANE;
    V support_normal = {}, support_origin = {};
    if (planar) {
        support_normal = {shape->srf_shape.plane.e3[0], shape->srf_shape.plane.e3[1],
                          shape->srf_shape.plane.e3[2]};
        support_origin = {shape->srf_shape.plane.origin[0], shape->srf_shape.plane.origin[1],
                          shape->srf_shape.plane.origin[2]};
    }
    if (data)
        ProGeomitemdataFree(&data);
    if (!planar)
        throw std::runtime_error("Sketch support must be planar");
    support_normal = normalized(support_normal);
    if (p.is_string()) {
        if (fabs(fabs(dot(support_normal, f.n)) - 1) > 1e-7)
            throw std::runtime_error("Named sketch plane does not match the resolved support");
        f.n = scale(support_normal, dot(support_normal, f.n) < 0 ? -1 : 1);
        f.origin = support_origin;
        f.u = normalized(add(f.u, scale(f.n, -dot(f.u, f.n))));
    } else {
        // BUG-187: a dict plane may pin the side it publishes. flip keeps the
        // selected support but reverses its normal, which reverses v_axis and
        // the extrusion direction without moving the sketch plane.
        f.n = p.value("flip", false) ? scale(support_normal, -1) : support_normal;
        f.origin = p.contains("origin") ? vec(p["origin"]) : support_origin;
        // BUG-095: an explicit origin is rejected against the actual support
        // plane, and the rejection now carries the measured evidence instead
        // of a bare message. signed_distance is n·(origin - support_origin)
        // with the normalized support normal the sketch frame actually uses;
        // constant_mm completes the plane equation n·x = constant. The
        // suggested origin is an explicit projection of the requested point
        // onto that plane: advice only, never an applied modification. The
        // 1e-6 mm admission threshold is unchanged.
        V origin_delta = add(f.origin, scale(support_origin, -1));
        double signed_distance = dot(f.n, origin_delta);
        if (fabs(signed_distance) > 1e-6) {
            char message[256];
            std::snprintf(message, sizeof(message),
                          "Sketch origin is outside support plane: signed distance %.9g mm "
                          "exceeds the 1e-06 mm tolerance; see sketch_origin_diagnostics in "
                          "the operation result",
                          signed_distance);
            V suggested = add(f.origin, scale(f.n, -signed_distance));
            stage_operation_result(
                {{"sketch_origin_diagnostics",
                  {{"status", "origin_outside_support_plane"},
                   {"distance_to_plane_mm", fabs(signed_distance)},
                   {"signed_distance_to_plane_mm", signed_distance},
                   {"origin_tolerance_mm", 1e-6},
                   {"support_plane",
                    {{"normal", J::array({f.n[0], f.n[1], f.n[2]})},
                     {"constant_mm", dot(f.n, support_origin)}}},
                   {"requested_origin", J::array({f.origin[0], f.origin[1], f.origin[2]})},
                   {"suggested_origin", J::array({suggested[0], suggested[1], suggested[2]})}}}});
            throw std::runtime_error(message);
        }
        V preferred = p.contains("u_axis") ? vec(p["u_axis"])
                                           : (fabs(f.n[0]) < 0.9 ? V{1, 0, 0} : V{0, 1, 0});
        double magnitude = sqrt(dot(preferred, preferred));
        if (magnitude < 1e-9)
            throw std::runtime_error("Sketch u_axis must be a nonzero direction vector");
        V in_plane = add(preferred, scale(f.n, -dot(preferred, f.n)));
        if (sqrt(dot(in_plane, in_plane)) < 1e-9 * magnitude)
            throw std::runtime_error("Sketch u_axis is parallel to the support plane normal");
        f.u = normalized(in_plane);
    }
    f.v = normalized(cross(f.n, f.u));
    if (!p.is_string() && p.contains("v_axis")) {
        // BUG-187: pin the sketch v_axis instead of accepting whatever the
        // support normal implies. When both u_axis and v_axis are supplied,
        // verify orthogonality in the plane and derive normal = u_axis x v_axis
        // so an inverted support normal cannot silently flip v_axis.
        V requested_v = vec(p["v_axis"]);
        double v_magnitude = sqrt(dot(requested_v, requested_v));
        if (v_magnitude < 1e-9)
            throw std::runtime_error("Sketch v_axis must be a nonzero direction vector");
        V v_in_plane = add(requested_v, scale(f.n, -dot(requested_v, f.n)));
        if (sqrt(dot(v_in_plane, v_in_plane)) < 1e-9 * v_magnitude)
            throw std::runtime_error("Sketch v_axis is parallel to the support plane normal");
        f.v = normalized(v_in_plane);
        if (p.contains("u_axis")) {
            if (fabs(dot(f.u, f.v)) > 1e-6)
                throw std::runtime_error(
                    "Sketch u_axis and v_axis must be orthogonal in the plane");
            f.n = normalized(cross(f.u, f.v));
        } else {
            f.u = normalized(cross(f.v, f.n));
        }
    }
    double best = 10;
    f.orientation = -1;
    collect_datum_planes_quiet();
    for (auto p : planes) {
        V normal = {p.n[0], p.n[1], p.n[2]};
        double d = fabs(dot(f.n, normal));
        if (d < best && d < 0.95) {
            best = d;
            f.orientation = p.id;
        }
    }
    if (f.orientation < 0)
        throw std::runtime_error("No sketch orientation reference");
    f.orientation_exact = best < 1e-6;
    return f;
}
// Defined later in this translation unit; declared here so sketch() can create
// the helper support features without moving the whole feature group.
static void generic_points(const J &op);
static J through_points_plane(const J &op);
static std::string helper_label() {
    static int sequence = 0;
    for (;;) {
        std::string label = "mdo" + std::to_string(++sequence);
        if (!aliases.contains(label))
            return label;
    }
}
// BUG-097 L2: two datum planes exactly perpendicular to an oblique support
// fully determine the sketch frame (one orientation reference, one projection
// anchor). They are ordinary datum_point/datum_plane features so the sketch
// keeps a native, editable support instead of a hand-built matrix.
static int build_helper_orientation(Frame &frame) {
    V locations[4] = {frame.origin, add(frame.origin, frame.u), add(frame.origin, frame.v),
                      add(frame.origin, frame.n)};
    std::string labels[4];
    for (int i = 0; i < 4; i++) {
        labels[i] = helper_label();
        J op = {{"op", "datum_points"},
                {"label", labels[i]},
                {"reference", {{"kind", "default_csys"}}},
                {"points", J::array({J{{"name", "p"}, {"position", xyz(locations[i].data())}}})}};
        generic_points(op);
    }
    auto plane = [&](int a, int b, int c) {
        J op = {{"op", "datum_plane"},
                {"label", helper_label()},
                {"reference",
                 {{"kind", "through_points"},
                  {"points", J::array({labels[a], labels[b], labels[c]})}}}};
        J details = through_points_plane(op);
        return details["plane_frame"]["surface_id"].get<int>();
    };
    int normal_u = plane(0, 2, 3);
    plane(0, 1, 3);
    return normal_u;
}
// BUG-173: compute the mean 2D coordinate of the requested sketch entities so a
// helper anchor plane passes through the profile region rather than far away.
static std::array<double, 2> sketch_entity_centroid(const J &op) {
    double sum_u = 0.0, sum_v = 0.0;
    int count = 0;
    auto push_pt = [&](const J &pt) {
        if (pt.is_array() && pt.size() >= 2 && pt[0].is_number() && pt[1].is_number()) {
            const double u = pt[0].get<double>(), v = pt[1].get<double>();
            if (std::isfinite(u) && std::isfinite(v)) {
                sum_u += u;
                sum_v += v;
                count++;
            }
        }
    };
    if (op.contains("entities") && op["entities"].is_array()) {
        for (const auto &e : op["entities"]) {
            if (!e.is_object())
                continue;
            for (const char *key : {"start", "end", "min", "max", "center"})
                if (e.contains(key))
                    push_pt(e[key]);
            for (const char *list_key : {"points", "control_points"})
                if (e.contains(list_key) && e[list_key].is_array())
                    for (const auto &pt : e[list_key])
                        push_pt(pt);
        }
    }
    if (count == 0)
        return {0.0, 0.0};
    return {sum_u / count, sum_v / count};
}
// BUG-173: when a singly-tilted support plane is perpendicular to one existing
// datum plane (so orientation_exact=true and build_helper_orientation did not
// run), no second perpendicular datum plane may exist in the model. Creo's
// ProSectionEntityFromProjection returns PRO_TK_BAD_INPUTS (-2) on oblique
// datum planes, leaving the section with only one reference and causing
// ProSectionSolve to fail with -1 and zero section errors. Build one
// deterministic datum plane perpendicular to BOTH frame.n and orient_normal,
// passing through the profile centroid, before creating the incomplete sketch.
static int build_helper_anchor_plane(const Frame &frame, const V &orient_normal, const J &op) {
    V orient_unit = normalized(orient_normal);
    V anchor_normal = normalized(cross(frame.n, orient_unit));
    const auto centroid = sketch_entity_centroid(op);
    V base = add(frame.origin, add(scale(frame.u, centroid[0]), scale(frame.v, centroid[1])));
    V locations[3] = {base, add(base, scale(orient_unit, 100.0)), add(base, scale(frame.n, 100.0))};
    std::string labels[3];
    for (int i = 0; i < 3; i++) {
        labels[i] = helper_label();
        J pt_op = {
            {"op", "datum_points"},
            {"label", labels[i]},
            {"reference", {{"kind", "default_csys"}}},
            {"points", J::array({J{{"name", "p"}, {"position", xyz(locations[i].data())}}})}};
        generic_points(pt_op);
    }
    J pl_op = {
        {"op", "datum_plane"},
        {"label", helper_label()},
        {"reference",
         {{"kind", "through_points"}, {"points", J::array({labels[0], labels[1], labels[2]})}}}};
    J details = through_points_plane(pl_op);
    int surface_id = details["plane_frame"]["surface_id"].get<int>();
    log("SKETCH_ANCHOR_HELPER=1 support=%d anchor=%d normal=%.6f,%.6f,%.6f\n", frame.surface,
        surface_id, anchor_normal[0], anchor_normal[1], anchor_normal[2]);
    return surface_id;
}
static ProSectionPointType point_type(const std::string &s) {
    return s == "start"    ? PRO_ENT_START
           : s == "end"    ? PRO_ENT_END
           : s == "center" ? PRO_ENT_CENTER
                           : PRO_ENT_WHOLE;
}
// FEAT-034/T02: one explicit direction field. dir=+1 sweeps counterclockwise
// from the logical start to the logical end in the user's sketch frame (the
// legacy meaning of start/end); dir=-1 sweeps clockwise. A stored Pro2dArcdef
// is always counterclockwise, so a clockwise arc or a mirrored section frame
// stores the two angles swapped; the swap map keeps the user's logical
// endpoints under their own names and start/end dimension references.
static std::map<int, bool> arc_endpoint_swapped;
static std::map<std::string, bool> arc_logical_swapped;
static int arc_direction(const J &e) {
    if (!e.contains("dir"))
        return 1;
    const J &value = e.at("dir");
    if (!value.is_number_integer())
        throw std::runtime_error(
            "Arc dir must be the strict integer +1 (counterclockwise) or -1 (clockwise)");
    int dir = value.get<int>();
    if (dir != 1 && dir != -1)
        throw std::runtime_error(
            "Arc dir must be the strict integer +1 (counterclockwise) or -1 (clockwise)");
    return dir;
}
struct ArcRepresentation {
    double start_angle, end_angle; // section frame, counterclockwise, end > start
    bool swapped;                  // the stored start angle is the logical end
};
static ArcRepresentation arc_representation(double logical_start, double logical_end, int dir,
                                            bool mirrored) {
    double start = logical_start, end = logical_end;
    bool swapped = false;
    if (dir == -1) {
        std::swap(start, end);
        swapped = !swapped;
    }
    if (mirrored) {
        std::swap(start, end);
        swapped = !swapped;
    }
    double turn = 2 * acos(-1.0);
    if (fabs(remainder(end - start, turn)) < 1e-12)
        throw std::runtime_error("Arc sweep must be strictly between 0 and 360 degrees; "
                                 "use circle for a complete circle");
    start = fmod(start + turn, turn);
    end = fmod(end + turn, turn);
    if (fabs(start) < 1e-12)
        start = 0;
    if (fabs(end) < 1e-12)
        end = 0;
    if (end <= start)
        end += turn;
    return {start, end, swapped};
}
// FEAT-034/T02: a user start/end reference must stay on the user's own
// endpoint even when the stored representation is swapped.
static ProSectionPointType logical_point(int entity, ProSectionPointType type) {
    if (type != PRO_ENT_START && type != PRO_ENT_END)
        return type;
    auto swapped = arc_endpoint_swapped.find(entity);
    if (swapped != arc_endpoint_swapped.end() && swapped->second)
        return type == PRO_ENT_START ? PRO_ENT_END : PRO_ENT_START;
    return type;
}
// Constraint references need a real location on the referenced entity; the
// section origin degenerates with arcs centered there (BUG-068) and idx_pnt
// must stay unused for non-spline entities per the Toolkit contract.
static ProSelection selected(ProSection section, int id, ProSectionPointType type) {
    type = logical_point(id, type);
    Pro2dEntdef *def = nullptr;
    CK(ProSectionEntityGet(section, id, &def));
    Pro2dPnt p;
    bool have = false;
    if (def->type == PRO_2D_LINE || def->type == PRO_2D_CENTER_LINE) {
        auto line = (Pro2dLinedef *)def;
        if (type == PRO_ENT_END) {
            p[0] = line->end2[0];
            p[1] = line->end2[1];
        } else if (type == PRO_ENT_START) {
            p[0] = line->end1[0];
            p[1] = line->end1[1];
        } else {
            p[0] = (line->end1[0] + line->end2[0]) / 2;
            p[1] = (line->end1[1] + line->end2[1]) / 2;
        }
        have = true;
    } else if (def->type == PRO_2D_CIRCLE) {
        auto circle = (Pro2dCircledef *)def;
        if (type == PRO_ENT_CENTER) {
            p[0] = circle->center[0];
            p[1] = circle->center[1];
        } else {
            p[0] = circle->center[0] + circle->radius;
            p[1] = circle->center[1];
        }
        have = true;
    } else if (def->type == PRO_2D_ARC) {
        auto arc = (Pro2dArcdef *)def;
        if (type == PRO_ENT_START || type == PRO_ENT_END) {
            double a = type == PRO_ENT_START ? arc->start_angle : arc->end_angle;
            p[0] = arc->center[0] + arc->radius * cos(a);
            p[1] = arc->center[1] + arc->radius * sin(a);
        } else if (type == PRO_ENT_CENTER) {
            p[0] = arc->center[0];
            p[1] = arc->center[1];
        } else {
            double a = (arc->start_angle + arc->end_angle) / 2;
            p[0] = arc->center[0] + arc->radius * cos(a);
            p[1] = arc->center[1] + arc->radius * sin(a);
        }
        have = true;
    }
    ProSelection s = nullptr;
    CK(ProSectionEntityGetSelected(section, id, type, have ? p : nullptr, PRO_VALUE_UNUSED, &s));
    return s;
}
// BUG-097 L2: structured failure receipt for feature completion. The
// ProErrorlist traversal in errors() (geometry.cpp) has always logged and
// concatenated element errors; the actual loss point was downstream �?a failed
// CompleteFeature only surfaced "Toolkit call CompleteFeature failed with code
// -1", leaving the element/type/error triples and the original section solver
// messages in native.log. The report below is bounded (element sample cap 20,
// section sample cap 20, totals kept) and every missing piece stays explicitly
// unavailable instead of being fabricated.
static J last_feature_error_report = nullptr;
static J feature_error_report(const char *api, ProError code, const char *failed_stage) {
    J sample = J::array();
    for (const auto &entry : feature_error_entries)
        sample.push_back(
            {{"element", entry.element}, {"type", entry.type}, {"error", entry.error}});
    J section = J::array();
    for (const auto &message : section_error_messages)
        section.push_back(message);
    J section_errors = {{"available", section_error_captured},
                        {"total", section_error_captured ? J(section_error_total) : J(nullptr)},
                        {"truncated", section_error_captured &&
                                          section_error_total > (int)section_error_messages.size()},
                        {"sample", section}};
    if (!section_error_captured)
        section_errors["unavailable_reason"] = "no section solve ran before this failure";
    return {{"api", api},
            {"code", code},
            {"failed_stage", failed_stage},
            {"element_errors",
             {{"total", feature_error_total},
              {"truncated", feature_error_total > (int)feature_error_entries.size()},
              {"sample", sample}}},
            {"section_errors", section_errors}};
}
static void redefine(ProFeature *f, ProElement root) {
    ProFeatureCreateOptions *options = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&options));
    options[0] = PRO_FEAT_CR_NO_OPTS;
    ProErrorlist es = {};
    ProError e = ProFeatureWithoptionsRedefine(nullptr, f, root, options, PRO_REGEN_NO_FLAGS, &es);
    errors(es);
    ProArrayFree((ProArray *)&options);
    if (e != PRO_TK_NO_ERROR)
        last_feature_error_report =
            feature_error_report("ProFeatureWithoptionsRedefine", e, "CompleteFeature");
    check(e, "CompleteFeature");
}
#include "sketch_coordinates.cpp"
#include "sketch_solver.cpp"
// BUG-064/T05: datum-plane projections into a sketch only succeed when the
// plane is orthogonal to the support plane. On a tilted support every
// principal datum plane is oblique, so the sketch is left with the single
// orientation projection and ProSectionSolve fails. A datum axis parallel to
// the support plane still projects to a line reference; collect those axes.
struct AxisRef {
    int id;
    V direction;
};
static std::vector<AxisRef> axis_refs;
static ProError axis_ref_cb(ProGeomitem *item, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    AxisGeometry geometry = inspect_axis_geometry(item);
    if (geometry.known)
        axis_refs.push_back(
            {item->id, {geometry.direction[0], geometry.direction[1], geometry.direction[2]}});
    return PRO_TK_NO_ERROR;
}
static ProError axis_feat_cb(ProFeature *f, ProError status, ProAppData) {
    ProFeattype type;
    if (!status && ProFeatureTypeGet(f, &type) == PRO_TK_NO_ERROR &&
        (type == PRO_FEAT_DATUM_AXIS || type == PRO_FEAT_DATUM))
        ProFeatureGeomitemVisit(f, PRO_AXIS, axis_ref_cb, nullptr, nullptr);
    return PRO_TK_NO_ERROR;
}
// DEV-047 T06: describe the solved section with the entities the kernel will
// actually use. A failed feature creation can then distinguish an open or
// branched contour from a geometry or feature-tree problem without guessing
// the cause from a bare Toolkit code.
struct SectionEdge {
    int entity;
    int first;
    int second;
    std::vector<std::array<double, 2>> samples;
};
static double polygon_signed_area_2d(const std::vector<std::array<double, 2>> &poly) {
    if (poly.size() < 3)
        return 0.0;
    double sum = 0.0;
    for (size_t i = 0; i < poly.size(); i++) {
        const auto &a = poly[i];
        const auto &b = poly[(i + 1) % poly.size()];
        sum += a[0] * b[1] - b[0] * a[1];
    }
    return 0.5 * sum;
}
static bool point_in_polygon_2d(const std::array<double, 2> &p,
                                const std::vector<std::array<double, 2>> &poly) {
    if (poly.size() < 3)
        return false;
    bool inside = false;
    for (size_t i = 0, j = poly.size() - 1; i < poly.size(); j = i++) {
        double xi = poly[i][0], yi = poly[i][1];
        double xj = poly[j][0], yj = poly[j][1];
        bool intersect = ((yi > p[1]) != (yj > p[1])) &&
                         (p[0] < (xj - xi) * (p[1] - yi) / ((yj - yi) + 1e-30) + xi);
        if (intersect)
            inside = !inside;
    }
    return inside;
}
static bool sample_section_entity_2d(ProSection section, int entity, int steps,
                                     std::vector<std::array<double, 2>> &out) {
    out.clear();
    out.reserve((size_t)steps + 1);
    for (int k = 0; k <= steps; k++) {
        double t = (double)k / (double)steps;
        ProVector pt = {0.0, 0.0, 0.0};
        if (ProSectionEntityEval(section, entity, t, pt, nullptr, nullptr) != PRO_TK_NO_ERROR)
            return false;
        if (!std::isfinite(pt[0]) || !std::isfinite(pt[1]))
            return false;
        out.push_back({pt[0], pt[1]});
    }
    return out.size() >= 2;
}
static J section_profile_summary(ProSection section, const char *phase) {
    J summary = {{"available", false}, {"query_code", 0}};
    ProIntlist ids = nullptr;
    int count = 0;
    ProError code = ProSectionEntityIdsGet(section, &ids, &count);
    if (code) {
        summary["query_code"] = code;
        log("SECTION_PROFILE_UNAVAILABLE phase=%s code=%d\n", phase, code);
        return summary;
    }
    const double tolerance = 1e-6;
    std::vector<std::array<double, 2>> points, representatives;
    std::vector<std::vector<int>> members;
    std::vector<int> node_entity;
    std::vector<SectionEdge> edges;
    std::vector<std::pair<std::vector<std::array<double, 2>>, double>> closed_geom;
    bool area_available = true;
    int curves = 0, standalone = 0, construction = 0, references = 0, unsupported = 0, bsplines = 0;
    auto node = [&](const std::array<double, 2> &point, int entity) {
        for (size_t index = 0; index < representatives.size(); index++) {
            if (hypot(point[0] - representatives[index][0], point[1] - representatives[index][1]) <=
                tolerance) {
                int position = (int)points.size();
                points.push_back(point);
                members[index].push_back(position);
                return (int)index;
            }
        }
        int position = (int)points.size();
        points.push_back(point);
        representatives.push_back(point);
        members.push_back({position});
        node_entity.push_back(entity);
        return (int)representatives.size() - 1;
    };
    auto edge = [&](int entity, const std::array<double, 2> &a, const std::array<double, 2> &b,
                    std::vector<std::array<double, 2>> samples) {
        curves++;
        if (samples.size() >= 2) {
            double d_fwd = hypot(samples.front()[0] - a[0], samples.front()[1] - a[1]) +
                           hypot(samples.back()[0] - b[0], samples.back()[1] - b[1]);
            double d_rev = hypot(samples.front()[0] - b[0], samples.front()[1] - b[1]) +
                           hypot(samples.back()[0] - a[0], samples.back()[1] - a[1]);
            if (d_rev < d_fwd)
                std::reverse(samples.begin(), samples.end());
        }
        edges.push_back({entity, node(a, entity), node(b, entity), std::move(samples)});
    };
    for (int index = 0; index < count; index++) {
        int entity = ids[index];
        ProBoolean is_construction = PRO_B_FALSE, is_projection = PRO_B_FALSE;
        if (!ProSectionEntityIsConstruction(section, entity, &is_construction) && is_construction) {
            construction++;
            continue;
        }
        if (!ProSectionEntityIsProjection(section, entity, &is_projection) && is_projection) {
            references++;
            continue;
        }
        Pro2dEntdef *def = nullptr;
        if (ProSectionEntityGet(section, entity, &def)) {
            unsupported++;
            continue;
        }
        if (def->type == PRO_2D_CENTER_LINE)
            continue; // Construction axis for revolve; never a profile boundary.
        if (def->type == PRO_2D_LINE) {
            auto line = (Pro2dLinedef *)def;
            std::array<double, 2> a = {line->end1[0], line->end1[1]};
            std::array<double, 2> b = {line->end2[0], line->end2[1]};
            edge(entity, a, b, {a, b});
        } else if (def->type == PRO_2D_ARC) {
            auto arc = (Pro2dArcdef *)def;
            auto at = [&](double angle) {
                return std::array<double, 2>{arc->center[0] + arc->radius * cos(angle),
                                             arc->center[1] + arc->radius * sin(angle)};
            };
            std::vector<std::array<double, 2>> samples;
            if (!sample_section_entity_2d(section, entity, 48, samples))
                area_available = false;
            edge(entity, at(arc->start_angle), at(arc->end_angle), std::move(samples));
        } else if (def->type == PRO_2D_CIRCLE) {
            standalone++;
            auto circle = (Pro2dCircledef *)def;
            double r = fabs(circle->radius);
            std::vector<std::array<double, 2>> poly;
            poly.reserve(64);
            const double two_pi = 2.0 * acos(-1.0);
            for (int k = 0; k < 64; k++) {
                double ang = two_pi * (double)k / 64.0;
                poly.push_back(
                    {circle->center[0] + r * cos(ang), circle->center[1] + r * sin(ang)});
            }
            closed_geom.push_back({std::move(poly), acos(-1.0) * r * r});
        } else if (def->type == PRO_2D_ELLIPSE) {
            standalone++;
            auto ellipse = (Pro2dEllipsedef *)def;
            std::vector<std::array<double, 2>> poly;
            if (!sample_section_entity_2d(section, entity, 64, poly))
                area_available = false;
            else
                closed_geom.push_back(
                    {std::move(poly), acos(-1.0) * fabs(ellipse->x_radius * ellipse->y_radius)});
        } else if (def->type == PRO_2D_SPLINE) {
            auto spline = (Pro2dSplinedef *)def;
            if (spline->n_points < 2)
                unsupported++;
            else if (spline->tangency_type == PRO_2D_SPLINE_TAN_PERIODIC) {
                standalone++;
                std::vector<std::array<double, 2>> poly;
                if (!sample_section_entity_2d(section, entity, 64, poly))
                    area_available = false;
                else
                    closed_geom.push_back({poly, fabs(polygon_signed_area_2d(poly))});
            } else {
                std::vector<std::array<double, 2>> samples;
                if (!sample_section_entity_2d(section, entity, 64, samples))
                    area_available = false;
                edge(entity, {spline->point_arr[0][0], spline->point_arr[0][1]},
                     {spline->point_arr[spline->n_points - 1][0],
                      spline->point_arr[spline->n_points - 1][1]},
                     std::move(samples));
            }
        } else if (def->type == PRO_2D_B_SPLINE) {
            bsplines++;
            // FEAT-066: a clamped B-spline interpolates its first and last
            // control point, so the profile contour endpoints are those two.
            auto bspline = (Pro2dBSplinedef *)def;
            if (bspline->num_c_points < 2 || !bspline->c_pnts)
                unsupported++;
            else {
                std::vector<std::array<double, 2>> samples;
                if (!sample_section_entity_2d(section, entity, 64, samples))
                    area_available = false;
                edge(entity, {bspline->c_pnts[0][0], bspline->c_pnts[0][1]},
                     {bspline->c_pnts[bspline->num_c_points - 1][0],
                      bspline->c_pnts[bspline->num_c_points - 1][1]},
                     std::move(samples));
            }
        } else if (def->type == PRO_2D_POLYLINE) {
            auto polyline = (Pro2dPolylinedef *)def;
            if (polyline->n_points < 2)
                unsupported++;
            else {
                std::vector<std::array<double, 2>> samples;
                samples.reserve((size_t)polyline->n_points);
                for (int k = 0; k < polyline->n_points; k++)
                    samples.push_back({polyline->point_arr[k][0], polyline->point_arr[k][1]});
                edge(entity, {polyline->point_arr[0][0], polyline->point_arr[0][1]},
                     {polyline->point_arr[polyline->n_points - 1][0],
                      polyline->point_arr[polyline->n_points - 1][1]},
                     std::move(samples));
            }
        }
    }
    std::vector<int> degrees(representatives.size(), 0);
    std::vector<std::vector<std::pair<int, int>>> adjacency(representatives.size());
    for (int index = 0; index < (int)edges.size(); index++) {
        degrees[edges[index].first]++;
        degrees[edges[index].second]++;
        adjacency[edges[index].first].push_back({index, edges[index].second});
        adjacency[edges[index].second].push_back({index, edges[index].first});
    }
    std::vector<bool> used(edges.size(), false);
    int contours = 0, closed = 0, open_ends = 0, branched = 0;
    std::string open_log;
    for (size_t seed = 0; seed < edges.size(); seed++) {
        if (used[seed])
            continue;
        contours++;
        bool all_closed = true;
        std::vector<int> stack = {(int)seed}, component_edges, component_nodes;
        while (!stack.empty()) {
            int current = stack.back();
            stack.pop_back();
            if (used[current])
                continue;
            used[current] = true;
            component_edges.push_back(current);
            int nodes[2] = {edges[current].first, edges[current].second};
            for (int end : nodes) {
                component_nodes.push_back(end);
                for (auto neighbour : adjacency[end])
                    if (!used[neighbour.first])
                        stack.push_back(neighbour.first);
            }
        }
        std::sort(component_nodes.begin(), component_nodes.end());
        component_nodes.erase(std::unique(component_nodes.begin(), component_nodes.end()),
                              component_nodes.end());
        for (int current : component_nodes) {
            if (degrees[current] != 2)
                all_closed = false;
            if (degrees[current] == 1) {
                open_ends++;
                char line[256];
                snprintf(line, sizeof(line),
                         "SECTION_PROFILE_OPEN phase=%s entity=%d point=%.9f,%.9f\n", phase,
                         node_entity[current], representatives[current][0],
                         representatives[current][1]);
                open_log += line;
            } else if (degrees[current] > 2)
                branched++;
        }
        if (all_closed) {
            closed++;
            if (area_available && !component_edges.empty()) {
                std::vector<bool> walked(edges.size(), false);
                std::vector<std::array<double, 2>> poly;
                int start_edge = component_edges[0];
                walked[start_edge] = true;
                int curr_node = edges[start_edge].second;
                const auto &s0 = edges[start_edge].samples;
                if (s0.size() < 2) {
                    area_available = false;
                } else {
                    for (size_t k = 0; k + 1 < s0.size(); k++)
                        poly.push_back(s0[k]);
                    size_t walked_count = 1;
                    while (walked_count < component_edges.size()) {
                        int next_edge = -1;
                        bool forward = true;
                        for (auto neighbour : adjacency[curr_node]) {
                            if (!walked[neighbour.first]) {
                                next_edge = neighbour.first;
                                forward = (edges[next_edge].first == curr_node);
                                break;
                            }
                        }
                        if (next_edge < 0) {
                            area_available = false;
                            break;
                        }
                        walked[next_edge] = true;
                        walked_count++;
                        const auto &sk = edges[next_edge].samples;
                        if (sk.size() < 2) {
                            area_available = false;
                            break;
                        }
                        if (forward) {
                            for (size_t k = 0; k + 1 < sk.size(); k++)
                                poly.push_back(sk[k]);
                            curr_node = edges[next_edge].second;
                        } else {
                            for (size_t k = sk.size() - 1; k > 0; k--)
                                poly.push_back(sk[k]);
                            curr_node = edges[next_edge].first;
                        }
                    }
                    if (area_available && poly.size() >= 3) {
                        double area = fabs(polygon_signed_area_2d(poly));
                        if (std::isfinite(area))
                            closed_geom.push_back({std::move(poly), area});
                        else
                            area_available = false;
                    }
                }
            }
        }
    }
    contours += standalone;
    closed += standalone;
    bool has_solved_area = false;
    double solved_section_area_mm2 = 0.0;
    if (area_available && unsupported == 0 && !closed_geom.empty()) {
        double total_area = 0.0;
        for (size_t i = 0; i < closed_geom.size(); i++) {
            int depth = 0;
            const auto &probe = closed_geom[i].first[0];
            for (size_t j = 0; j < closed_geom.size(); j++) {
                if (i == j)
                    continue;
                if (closed_geom[i].second >= closed_geom[j].second - 1e-9)
                    continue;
                if (point_in_polygon_2d(probe, closed_geom[j].first))
                    depth++;
            }
            total_area += closed_geom[i].second * (depth % 2 == 0 ? 1.0 : -1.0);
        }
        if (std::isfinite(total_area) && total_area > 0.0) {
            has_solved_area = true;
            solved_section_area_mm2 = total_area;
        }
    }
    // BUG-049/N03: bounded endpoint-gap diagnostics for the two-stage
    // comparison (input analysis vs solved section). The clustering tolerance
    // above is this diagnostic's own sampling value; it is never claimed to be
    // a kernel welding tolerance. Every open end keeps its total in
    // open_ends; the samples below are capped and flagged when truncated.
    double max_cluster_spread = 0.0;
    for (size_t cluster = 0; cluster < members.size(); cluster++) {
        const std::vector<int> &list = members[cluster];
        for (size_t a = 0; a < list.size(); a++)
            for (size_t b = a + 1; b < list.size(); b++)
                max_cluster_spread =
                    std::max(max_cluster_spread, hypot(points[list[a]][0] - points[list[b]][0],
                                                       points[list[a]][1] - points[list[b]][1]));
    }
    double max_endpoint_gap = 0.0;
    std::vector<J> all_open_samples;
    for (size_t current = 0; current < representatives.size(); current++) {
        if (degrees[current] != 1)
            continue;
        int nearest = -1;
        double nearest_gap = 0.0;
        for (size_t other = 0; other < representatives.size(); other++) {
            if (other == current)
                continue;
            double distance = hypot(representatives[current][0] - representatives[other][0],
                                    representatives[current][1] - representatives[other][1]);
            if (nearest < 0 || distance < nearest_gap) {
                nearest = (int)other;
                nearest_gap = distance;
            }
        }
        max_endpoint_gap = std::max(max_endpoint_gap, nearest_gap);
        all_open_samples.push_back(
            {{"entity", node_entity[current]},
             {"point", {representatives[current][0], representatives[current][1]}},
             {"nearest_entity", nearest < 0 ? J(nullptr) : J(node_entity[nearest])},
             {"nearest_point",
              nearest < 0 ? J(nullptr)
                          : J::array({representatives[nearest][0], representatives[nearest][1]})},
             {"nearest_gap_mm", nearest_gap}});
    }
    std::sort(all_open_samples.begin(), all_open_samples.end(), [](const J &a, const J &b) {
        double ga = a.value("nearest_gap_mm", 0.0), gb = b.value("nearest_gap_mm", 0.0);
        if (ga != gb)
            return ga < gb;
        int ea = a.value("entity", 0), eb = b.value("entity", 0);
        if (ea != eb)
            return ea < eb;
        return a.value("nearest_entity", -1) < b.value("nearest_entity", -1);
    });
    J open_samples = J::array();
    const size_t max_open_samples = 20;
    bool open_samples_truncated = all_open_samples.size() > max_open_samples;
    for (size_t i = 0; i < std::min(all_open_samples.size(), max_open_samples); i++)
        open_samples.push_back(all_open_samples[i]);
    summary = {
        {"available", true},
        {"entities", curves + standalone},
        {"curves", curves},
        {"standalone_curves", standalone},
        {"contours", contours},
        {"closed_contours", closed},
        {"b_spline_entities", bsplines},
        {"solved_section_area_mm2", has_solved_area ? J(solved_section_area_mm2) : J(nullptr)},
        {"open_ends", open_ends},
        {"branched_points", branched},
        {"construction_entities", construction},
        {"reference_entities", references},
        {"unsupported_entities", unsupported},
        {"tolerance_mm", tolerance},
        {"tolerance_scope", "diagnostic_endpoint_clustering"},
        {"max_cluster_spread_mm", max_cluster_spread},
        {"max_endpoint_gap_mm", max_endpoint_gap},
        {"open_end_samples", open_samples},
        {"open_end_samples_truncated", open_samples_truncated}};
    log("SECTION_PROFILE phase=%s entities=%d curves=%d standalone=%d contours=%d closed=%d "
        "open_ends=%d branched=%d construction=%d references=%d unsupported=%d tolerance_mm=%.9g "
        "cluster_spread_mm=%.9g endpoint_gap_mm=%.9g\n",
        phase, curves + standalone, curves, standalone, contours, closed, open_ends, branched,
        construction, references, unsupported, tolerance, max_cluster_spread, max_endpoint_gap);
    if (!open_log.empty())
        log("%s", open_log.c_str());
    if (ids)
        ProArrayFree((ProArray *)&ids);
    return summary;
}
// FEAT-034/T02: report the stored section arc geometry as the user's logical
// start/end, tangents, direction and sweep in the sketch-local frame. A failed
// query keeps its raw code and null values; requested input values are never
// echoed as a measured result.
static J arc_geometry_report(ProSection section, ProError unavailable_code, const J &entity_specs,
                             const std::map<std::string, int> &entities, const V &origin,
                             const V &u, const V &v, const ProMatrix &loc, bool mirrored) {
    J report = J::array();
    auto to_user = [&](const std::array<double, 2> &xy) {
        V w = {loc[3][0] + xy[0] * loc[0][0] + xy[1] * loc[1][0],
               loc[3][1] + xy[0] * loc[0][1] + xy[1] * loc[1][1],
               loc[3][2] + xy[0] * loc[0][2] + xy[1] * loc[1][2]};
        V offset = add(w, scale(origin, -1));
        return J::array({dot(offset, u), dot(offset, v)});
    };
    for (auto e : entity_specs) {
        if (!e.is_object() || e.value("type", "") != "arc")
            continue;
        std::string name = e.value("name", "");
        J entry = {{"name", name},
                   {"source", "unknown"},
                   {"query_code", nullptr},
                   {"frame", nullptr},
                   {"start_uv", nullptr},
                   {"end_uv", nullptr},
                   {"center_uv", nullptr},
                   {"radius_mm", nullptr},
                   {"start_tangent_uv", nullptr},
                   {"end_tangent_uv", nullptr},
                   {"dir", nullptr},
                   {"sweep_deg", nullptr}};
        auto known = entities.find(name);
        Pro2dEntdef *def = nullptr;
        ProError code = PRO_TK_E_NOT_FOUND;
        if (known != entities.end())
            code = section ? ProSectionEntityGet(section, known->second, &def) : unavailable_code;
        else
            code = unavailable_code;
        if (code == PRO_TK_NO_ERROR && def && def->type == PRO_2D_ARC) {
            auto arc = (Pro2dArcdef *)def;
            auto swapped_entry = arc_logical_swapped.find(name);
            bool flip = swapped_entry != arc_logical_swapped.end() && swapped_entry->second;
            auto at = [&](double angle) {
                return std::array<double, 2>{arc->center[0] + arc->radius * cos(angle),
                                             arc->center[1] + arc->radius * sin(angle)};
            };
            std::array<double, 2> s = flip ? at(arc->end_angle) : at(arc->start_angle),
                                  t = flip ? at(arc->start_angle) : at(arc->end_angle);
            J start_uv = to_user(s), end_uv = to_user(t),
              center = to_user({arc->center[0], arc->center[1]});
            double a0 = atan2(start_uv[1].get<double>() - center[1].get<double>(),
                              start_uv[0].get<double>() - center[0].get<double>()),
                   a1 = atan2(end_uv[1].get<double>() - center[1].get<double>(),
                              end_uv[0].get<double>() - center[0].get<double>());
            int dir = (flip ? -1 : 1) * (mirrored ? -1 : 1);
            auto tangent = [&](double angle) {
                return J::array(
                    {dir > 0 ? -sin(angle) : sin(angle), dir > 0 ? cos(angle) : -cos(angle)});
            };
            entry["source"] = "native";
            entry["query_code"] = 0;
            entry["frame"] = "sketch_local";
            entry["start_uv"] = start_uv;
            entry["end_uv"] = end_uv;
            // BUG-049/N03: measured center and radius for the two-stage
            // comparison against the input echo; null when not queryable.
            entry["center_uv"] = center;
            entry["radius_mm"] = arc->radius;
            entry["start_tangent_uv"] = tangent(a0);
            entry["end_tangent_uv"] = tangent(a1);
            entry["dir"] = dir;
            entry["sweep_deg"] = (arc->end_angle - arc->start_angle) * 180 / acos(-1.0);
        } else
            entry["query_code"] = code;
        report.push_back(entry);
    }
    return report;
}
template <typename Project>
static int add_section_bspline(ProSection section, const J &entity, const Project &project) {
    const J &control_points = entity.at("control_points");
    const int degree = entity.at("degree");
    const int count = (int)control_points.size();
    if (degree < 1 || degree >= count)
        throw std::runtime_error("b_spline degree must be between 1 and control_points - 1");

    std::vector<double> knots;
    if (entity.contains("knots") && !entity["knots"].is_null()) {
        knots = entity["knots"].get<std::vector<double>>();
    } else {
        const int spans = count - degree;
        knots.assign((size_t)degree + 1, 0.0);
        for (int i = 1; i < spans; i++)
            knots.push_back((double)i / spans);
        knots.insert(knots.end(), (size_t)degree + 1, 1.0);
    }
    if ((int)knots.size() != count + degree + 1)
        throw std::runtime_error("b_spline knot count must be len(control_points) + degree + 1");
    const J weights = entity.value("weights", J(nullptr));
    if (!weights.is_null() && (int)weights.size() != count)
        throw std::runtime_error("b_spline weights need one value per control point");

    // The SDK's Pro2dBSplinedef arrays carry Toolkit allocation metadata.
    // SectionEntityAdd takes these as inputs, so keep them through the call.
    struct SplineInput {
        Pro2dBSplinedef value{};
        ~SplineInput() {
            if (value.params)
                ProArrayFree((ProArray *)&value.params);
            if (value.c_pnts)
                ProArrayFree((ProArray *)&value.c_pnts);
            if (value.weights)
                ProArrayFree((ProArray *)&value.weights);
        }
    } input;
    auto &spline = input.value;
    spline.type = PRO_2D_B_SPLINE;
    spline.degree = degree;
    spline.num_knots = (int)knots.size();
    spline.num_c_points = count;
    CK(ProArrayAlloc(spline.num_knots, sizeof(double), 1, (ProArray *)&spline.params));
    std::copy(knots.begin(), knots.end(), spline.params);
    CK(ProArrayAlloc(count, sizeof(Pro2dPnt), 1, (ProArray *)&spline.c_pnts));
    for (int i = 0; i < count; i++)
        project(control_points[i], spline.c_pnts[i]);
    if (!weights.is_null()) {
        CK(ProArrayAlloc(count, sizeof(double), 1, (ProArray *)&spline.weights));
        for (int i = 0; i < count; i++)
            spline.weights[i] = weights[i].get<double>();
    }
    int id = 0;
    CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&spline, &id));
    return id;
}

static J bspline_polyline_points(const J &entity, int segments) {
    const J &control = entity.at("control_points");
    const auto knots = entity.at("knots").get<std::vector<double>>();
    const J raw_weights = entity.value("weights", J(nullptr));
    const auto weights = raw_weights.is_null() ? std::vector<double>(control.size(), 1.0)
                                               : raw_weights.get<std::vector<double>>();
    const int degree = entity.at("degree");
    const int count = (int)control.size();
    const double first = knots.at(degree), last = knots.at(count);
    std::vector<V> homogeneous;
    for (int i = 0; i < count; i++) {
        const double w = weights.at(i);
        homogeneous.push_back(
            {control[i][0].get<double>() * w, control[i][1].get<double>() * w, w});
    }
    J points = J::array({control.front()});
    std::vector<V> work(degree + 1);
    for (int i = 1; i < segments; i++) {
        const double t = first + (last - first) * ((double)i / segments);
        const int span = (int)(std::upper_bound(knots.begin(), knots.end(), t) - knots.begin()) - 1;
        if (span < degree || span >= count)
            throw std::runtime_error("B-spline approximation could not resolve the knot span");
        for (int j = 0; j <= degree; j++)
            work[j] = homogeneous[span - degree + j];
        for (int level = 1; level <= degree; level++)
            for (int j = degree; j >= level; j--) {
                const int index = span - degree + j;
                const double alpha =
                    (t - knots[index]) / (knots[index + degree - level + 1] - knots[index]);
                work[j] = add(scale(work[j - 1], 1.0 - alpha), scale(work[j], alpha));
            }
        const auto &p = work[degree];
        const double x = p[0] / p[2], y = p[1] / p[2];
        if (!std::isfinite(x) || !std::isfinite(y))
            throw std::runtime_error("B-spline approximation produced a nonfinite coordinate");
        points.push_back({x, y});
    }
    points.push_back(control.back());
    return points;
}

static J sketch(J op) {
    J approximations = J::array();
    for (auto &entity : op.at("entities")) {
        if (entity.value("type", "") != "b_spline" || !entity.contains("approximation_segments") ||
            entity["approximation_segments"].is_null())
            continue;
        const int segments = entity.at("approximation_segments");
        const J name = entity.at("name");
        J points = bspline_polyline_points(entity, segments);
        entity = {{"type", "polyline"},
                  {"name", name},
                  {"points", std::move(points)},
                  {"construction", entity.value("construction", false)}};
        approximations.push_back({{"entity", name}, {"segments", segments}});
    }
    Frame frame = sketch_frame(op);
    if (!frame.orientation_exact) {
        log("SKETCH_ORIENTATION_HELPER=1 support=%d\n", frame.surface);
        frame.orientation = build_helper_orientation(frame);
    }
    // BUG-173: before opening an incomplete sketch feature, make sure at least
    // one datum plane perpendicular to BOTH the support plane and the
    // orientation plane exists. Standard XY/XZ/YZ supports already satisfy this
    // via the template datum planes (zero extra features created); singly-tilted
    // through_points planes get one reusable helper anchor plane so
    // ProSectionEntityFromProjection succeeds deterministically and
    // pin_coordinate_origin can pin both section axes.
    collect_datum_planes_quiet();
    V orient_normal = frame.n;
    for (const auto &p : planes)
        if (p.id == frame.orientation)
            orient_normal = normalized(V{p.n[0], p.n[1], p.n[2]});
    int helper_anchor_surface_id = -1;
    bool has_orthogonal_anchor = false;
    for (const auto &p : planes) {
        if (p.id == frame.orientation)
            continue;
        V n = normalized(V{p.n[0], p.n[1], p.n[2]});
        if (fabs(dot(n, frame.n)) < 1e-5 && fabs(dot(n, orient_normal)) < 1e-5) {
            has_orthogonal_anchor = true;
            break;
        }
    }
    if (!has_orthogonal_anchor && fabs(dot(orient_normal, frame.n)) < 1e-5) {
        helper_anchor_surface_id = build_helper_anchor_plane(frame, orient_normal, op);
    }
    ProSelection plane_ref = selection(frame.surface, PRO_SURFACE),
                 orient = selection(frame.orientation, PRO_SURFACE);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CURVE);
    integer(root, PRO_E_CURVE_TYPE, PRO_CURVE_TYPE_SKETCHED);
    std::wstring label = wide(op.at("label"));
    text(root, PRO_E_STD_FEATURE_NAME, label.c_str());
    ProElement setup = node(node(root, PRO_E_STD_SECTION), PRO_E_STD_SEC_SETUP_PLANE);
    ref(setup, PRO_E_STD_SEC_PLANE, plane_ref);
    integer(setup, PRO_E_STD_SEC_PLANE_VIEW_DIR, PRO_SEC_VIEW_DIR_SIDE_ONE);
    integer(setup, PRO_E_STD_SEC_PLANE_ORIENT_DIR, PRO_SEC_ORIENT_DIR_UP);
    ref(setup, PRO_E_STD_SEC_PLANE_ORIENT_REF, orient);
    ProFeature f = create(root, PRO_FEAT_CR_INCOMPLETE_FEAT);
    CK(ProElementFree(&root));
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    ProElement sk = get(root, {PRO_E_STD_SECTION, PRO_E_SKETCHER});
    ProSection section = nullptr;
    CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&section));
    int projected;
    CK(ProSectionEntityFromProjection(section, orient, &projected));
    std::vector<int> coordinate_anchors = {projected};
    collect_datum_planes_quiet();
    // BUG-087 + BUG-173: order candidate datum planes so planes perpendicular
    // to both support and orientation (including any helper anchor just built)
    // are tried first, followed by planes perpendicular to the support, and
    // finally general non-parallel planes as a last resort. This avoids
    // hundreds of guaranteed PRO_TK_BAD_INPUTS (-2) calls on oblique planes.
    for (const auto &p : planes)
        if (p.id == frame.orientation)
            orient_normal = normalized(V{p.n[0], p.n[1], p.n[2]});
    std::vector<int> tier0, tier1, tier2;
    for (const auto &p : planes) {
        V n = normalized(V{p.n[0], p.n[1], p.n[2]});
        if (p.id == frame.orientation || fabs(dot(n, frame.n)) >= 0.95)
            continue;
        double to_orientation = fabs(dot(n, orient_normal));
        if (to_orientation >= 1 - 1e-6) {
            log("SKETCH_ANCHOR_SKIPPED=%d parallel_to_orientation=%.9f\n", p.id, to_orientation);
            continue;
        }
        double to_support = fabs(dot(n, frame.n));
        if (p.id == helper_anchor_surface_id)
            tier0.insert(tier0.begin(), p.id);
        else if (to_support < 1e-5 && to_orientation < 1e-5)
            tier0.push_back(p.id);
        else if (to_support < 1e-4)
            tier1.push_back(p.id);
        else
            tier2.push_back(p.id);
    }
    auto try_anchor_planes = [&](const std::vector<int> &ids) {
        for (int pid : ids) {
            if (coordinate_anchors.size() >= 2)
                return;
            ProSelection s = selection(pid, PRO_SURFACE);
            ProError e = ProSectionEntityFromProjection(section, s, &projected);
            ProSelectionFree(&s);
            log("PROJECT_REFERENCE=%d code=%d entity=%d\n", pid, e, projected);
            if (!e) {
                coordinate_anchors.push_back(projected);
                log("SKETCH_ANCHOR_PLANE=%d\n", pid);
                return;
            }
        }
    };
    try_anchor_planes(tier0);
    try_anchor_planes(tier1);
    try_anchor_planes(tier2);
    if (coordinate_anchors.size() == 1) {
        // No usable datum plane existed, so the section carries only the
        // orientation reference and ProSectionSolve fails. Fall back to a
        // datum axis parallel to the support plane; its projection is a line
        // reference. An oblique axis would project to a point and is skipped.
        V orient_line = cross(frame.n, orient_normal);
        double length = sqrt(dot(orient_line, orient_line));
        axis_refs.clear();
        CK(ProSolidFeatVisit((ProSolid)board, axis_feat_cb, nullptr, nullptr));
        for (auto &a : axis_refs) {
            if (fabs(dot(a.direction, frame.n)) > 1e-6)
                continue;
            if (length > 1e-9 && fabs(dot(a.direction, orient_line)) / length > 1 - 1e-6)
                continue;
            ProSelection s = selection(a.id, PRO_AXIS);
            ProError e = ProSectionEntityFromProjection(section, s, &projected);
            ProSelectionFree(&s);
            log("PROJECT_REFERENCE_AXIS=%d code=%d entity=%d\n", a.id, e, projected);
            if (!e) {
                coordinate_anchors.push_back(projected);
                log("SKETCH_ANCHOR_AXIS=%d\n", a.id);
                break;
            }
        }
        if (coordinate_anchors.size() == 1)
            log("SKETCH_REFERENCE_INCOMPLETE axes=%d\n", (int)axis_refs.size());
    }
    ProMatrix loc;
    CK(ProSectionLocationGet(section, loc));
    for (int row = 0; row < 4; row++)
        log("SECTION_MATRIX_%d=%.9f,%.9f,%.9f,%.9f\n", row, loc[row][0], loc[row][1], loc[row][2],
            loc[row][3]);
    // BUG-097 L1: on an incomplete feature over an oblique support,
    // ProSectionLocationGet has been observed returning the identity while the
    // sketch is placed on a plane where the identity cannot be the true
    // location: a true identity would mean the section coordinate system is
    // the world axes with the section plane at world Z=0 through the origin.
    // Mapping world coordinates through that placeholder writes world XY into
    // the section. Detect the full 4x4 identity, but only fall back to the
    // placement frame basis when the identity is actually impossible for this
    // sketch; on a support where identity is a legitimate placement (world XY
    // through the origin, e.g. the named XY plane) the location matrix keeps
    // the mapping and the two projections coincide there anyway. This is not
    // the external patch pasted in: the plausibility guard and diagnostics are
    // derived from the current source and the frame semantics above.
    const bool loc_is_identity = [&]() {
        for (int row = 0; row < 4; row++)
            for (int col = 0; col < 4; col++)
                if (fabs(loc[row][col] - (row == col ? 1.0 : 0.0)) > 1e-12)
                    return false;
        return true;
    }();
    const bool identity_plausible = fabs(frame.n[0]) < 1e-9 && fabs(frame.n[1]) < 1e-9 &&
                                    fabs(frame.n[2] - 1) < 1e-9 && fabs(frame.origin[0]) < 1e-9 &&
                                    fabs(frame.origin[1]) < 1e-9 && fabs(frame.origin[2]) < 1e-9;
    const bool use_frame_basis = loc_is_identity && !identity_plausible;
    log("SECTION_LOCATION_IDENTITY=%d using_%s identity_plausible=%d\n", loc_is_identity ? 1 : 0,
        use_frame_basis ? "frame_basis" : "location_matrix", identity_plausible ? 1 : 0);
    J section_location = {{"matrix_identity", loc_is_identity},
                          {"identity_plausible", identity_plausible},
                          {"uv_mapping", use_frame_basis ? "frame_basis" : "location_matrix"}};
    // The inverse mapping used by the arc/round-trip reports must mirror the
    // projection above: with the frame-basis fallback the location matrix is a
    // placeholder, so report against the placement frame itself instead of the
    // meaningless identity.
    ProMatrix effective_loc;
    if (use_frame_basis) {
        for (int col = 0; col < 3; col++) {
            effective_loc[0][col] = frame.u[col];
            effective_loc[1][col] = frame.v[col];
            effective_loc[2][col] = frame.n[col];
            effective_loc[3][col] = frame.origin[col];
        }
        effective_loc[0][3] = effective_loc[1][3] = effective_loc[2][3] = 0.0;
        effective_loc[3][3] = 1.0;
    } else
        memcpy(effective_loc, loc, sizeof(effective_loc));
    const bool mirrored =
        use_frame_basis ? false : dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) < 0;
    arc_endpoint_swapped.clear();
    arc_logical_swapped.clear();
    auto project = [&](const J &p, double *out) {
        V w = add(frame.origin, add(scale(frame.u, p.at(0).get<double>()),
                                    scale(frame.v, p.at(1).get<double>())));
        if (use_frame_basis) {
            // The location matrix is a placeholder, so project with the exact
            // frame the sketch was placed with: the section coordinates are the
            // user's own frame coordinates until the kernel reports otherwise.
            V d = add(w, scale(frame.origin, -1));
            out[0] = dot(d, frame.u);
            out[1] = dot(d, frame.v);
            return;
        }
        for (int i = 0; i < 2; i++)
            out[i] = (w[0] - loc[3][0]) * loc[i][0] + (w[1] - loc[3][1]) * loc[i][1] +
                     (w[2] - loc[3][2]) * loc[i][2];
    };
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    Pro2dCoordSysdef cs = {};
    cs.type = PRO_2D_COORD_SYS;
    int csid;
    CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&cs, &csid));
    std::map<std::string, int> entities;
    auto add_line = [&](const std::string &name, const J &a, const J &b, bool centerline,
                        bool construction) {
        Pro2dLinedef l = {};
        l.type = centerline ? PRO_2D_CENTER_LINE : PRO_2D_LINE;
        project(a, l.end1);
        project(b, l.end2);
        log("LINE_%s=%.9f,%.9f -> %.9f,%.9f\n", name.c_str(), l.end1[0], l.end1[1], l.end2[0],
            l.end2[1]);
        int id;
        CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&l, &id));
        if (!centerline)
            CK(ProSectionEntityConstructionSet(section, id,
                                               construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    };
    // FEAT-039/W01: a controlled weld regularises the request coordinates
    // before anything is written, so the move is bounded by construction.
    J spec = op.at("entities");
    J weld_report = apply_endpoint_weld(op, spec);
    for (auto e : spec) {
        std::string type = e.at("type"), name = e.at("name");
        bool construction = e.value("construction", false);
        int id = -1;
        if (type == "line" || type == "centerline") {
            add_line(name, e["start"], e["end"], type == "centerline", construction);
            continue;
        }
        if (type == "rectangle" || type == "polyline") {
            J points;
            if (type == "rectangle") {
                auto a = e["min"], b = e["max"];
                points = J::array({a, J::array({b[0], a[1]}), b, J::array({a[0], b[1]})});
            } else
                points = e["points"];
            int count = (int)points.size(),
                segments = count - 1 + ((type == "rectangle" || e.value("closed", false)) ? 1 : 0);
            for (int i = 0; i < segments; i++)
                add_line(name + "_" + std::to_string(i), points[i], points[(i + 1) % count], false,
                         construction);
            continue;
        }
        if (type == "circle") {
            Pro2dCircledef c = {};
            c.type = PRO_2D_CIRCLE;
            project(e["center"], c.center);
            c.radius = e["radius"];
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&c, &id));
        } else if (type == "arc") {
            Pro2dArcdef a = {};
            a.type = PRO_2D_ARC;
            project(e["center"], a.center);
            a.radius = e["radius"];
            double start = e["start_angle"].get<double>() * acos(-1.0) / 180,
                   end = e["end_angle"].get<double>() * acos(-1.0) / 180;
            double p[2], q[2];
            J center = e["center"];
            project(J::array({center[0].get<double>() + a.radius * cos(start),
                              center[1].get<double>() + a.radius * sin(start)}),
                    p);
            project(J::array({center[0].get<double>() + a.radius * cos(end),
                              center[1].get<double>() + a.radius * sin(end)}),
                    q);
            ArcRepresentation rep = arc_representation(
                atan2(p[1] - a.center[1], p[0] - a.center[0]),
                atan2(q[1] - a.center[1], q[0] - a.center[0]), arc_direction(e), mirrored);
            a.start_angle = rep.start_angle;
            a.end_angle = rep.end_angle;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&a, &id));
            arc_endpoint_swapped[id] = rep.swapped;
            arc_logical_swapped[name] = rep.swapped;
        } else if (type == "spline") {
            auto points = e["points"];
            std::vector<std::array<double, 2>> xy(points.size());
            for (size_t i = 0; i < xy.size(); i++)
                project(points[i], xy[i].data());
            Pro2dSplinedef s = {};
            s.type = PRO_2D_SPLINE;
            s.tangency_type =
                e.value("closed", false) ? PRO_2D_SPLINE_TAN_PERIODIC : PRO_2D_SPLINE_TAN_NONE;
            s.n_points = (unsigned)xy.size();
            s.point_arr = (Pro2dPnt *)xy.data();
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&s, &id));
        } else if (type == "b_spline") {
            id = add_section_bspline(section, e, project);
        } else if (type == "ellipse") {
            Pro2dEllipsedef ell = {};
            ell.type = PRO_2D_ELLIPSE;
            project(e["center"], ell.origin);
            // Under the frame-basis fallback the location matrix is a
            // placeholder; the alignment check then follows the assumed
            // section axes (the placement frame) instead of the identity.
            double align = fabs(
                dot(frame.u, V{effective_loc[0][0], effective_loc[0][1], effective_loc[0][2]}));
            if (align > 0.99999) {
                ell.x_radius = e["x_radius"];
                ell.y_radius = e["y_radius"];
            } else if (align < 0.00001) {
                ell.x_radius = e["y_radius"];
                ell.y_radius = e["x_radius"];
            } else
                throw std::runtime_error("Ellipse axes must align with the section axes");
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&ell, &id));
        } else
            throw std::runtime_error("Unknown sketch entity type");
        CK(ProSectionEntityConstructionSet(section, id, construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    }
    if (!op.value("constraints", J::array()).empty()) {
        CK(ProSectionIntentManagerModeSet(section, PRO_B_TRUE));
        std::map<std::string, ProConstraintType> ct = {
            {"coincident", PRO_CONSTRAINT_SAME_POINT},
            {"horizontal", PRO_CONSTRAINT_HORIZONTAL_ENT},
            {"vertical", PRO_CONSTRAINT_VERTICAL_ENT},
            {"point_on", PRO_CONSTRAINT_PNT_ON_ENT},
            {"tangent", PRO_CONSTRAINT_TANGENT_ENTS},
            {"perpendicular", PRO_CONSTRAINT_ORTHOG_ENTS},
            {"equal_radius", PRO_CONSTRAINT_EQUAL_RADII},
            {"parallel", PRO_CONSTRAINT_PARALLEL_ENTS},
            {"equal_length", PRO_CONSTRAINT_EQUAL_SEGMENTS},
            {"collinear", PRO_CONSTRAINT_COLLINEAR_LINES}};
        for (auto c : op["constraints"]) {
            std::vector<ProSelection> refs;
            for (auto r : c["refs"]) {
                ProSelection s = selected(section, entities.at(r["entity"].get<std::string>()),
                                          point_type(r.value("point", "whole")));
                refs.push_back(s);
            }
            int cid;
            ProError err = ProSectionConstraintCreate(section, refs.data(), (int)refs.size(),
                                                      ct.at(c["type"]), &cid);
            for (auto s : refs)
                ProSelectionFree(&s);
            if (err != PRO_TK_E_FOUND)
                check(err, "CreateSketchConstraint");
        }
        CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    }
    std::map<std::string, ProSecdimType> dt = {{"length", PRO_TK_DIM_LINE},
                                               {"radius", PRO_TK_DIM_RAD},
                                               {"diameter", PRO_TK_DIM_DIA},
                                               {"distance", PRO_TK_DIM_PNT_PNT},
                                               {"horizontal", PRO_TK_DIM_PNT_PNT_HORIZ},
                                               {"vertical", PRO_TK_DIM_PNT_PNT_VERT},
                                               {"line_distance", PRO_TK_DIM_LINE_LINE},
                                               {"angle", PRO_TK_DIM_LINES_ANGLE},
                                               {"arc_angle", PRO_TK_DIM_ARC_ANGLE},
                                               {"ellipse_x_radius", PRO_TK_DIM_ELLIPSE_X_RADIUS},
                                               {"ellipse_y_radius", PRO_TK_DIM_ELLIPSE_Y_RADIUS}};
    J dims = J::object();
    J coordinate_plan;
    J solving_op = op;
    last_sketch_solver_info = profile_dimensioning_choice(op);
    solving_op["dimensioning"] = last_sketch_solver_info["used"];
    // FEAT-010/BUG-049: resolve the deviation policy before solving so a
    // malformed explicit tolerance fails before any mutation.
    const DeviationPolicy deviation_policy =
        resolve_geometry_tolerance(op, solving_op["dimensioning"].get<std::string>());
    const char *deviation_context = std::string(deviation_policy.source) == "request"
                                        ? "geometry_tolerance_mm"
                                        : "Coordinate dimensioning";
    J deviation_targets;
    last_sketch_reference_info = {
        {"anchor_count", (int)coordinate_anchors.size()},
        {"reference_incomplete", coordinate_anchors.size() < 2},
        {"helper_orientation_created", !frame.orientation_exact},
        {"helper_anchor_created", helper_anchor_surface_id >= 0},
        {"entity_count", (int)entities.size()},
        {"origin_pin_u", nullptr},
        {"origin_pin_v", nullptr},
        {"origin_pin_available", nullptr},
    };
    if (solving_op["dimensioning"] == "coordinates") {
        if (!op.value("dimensions", J::array()).empty() ||
            !op.value("constraints", J::array()).empty())
            throw std::runtime_error(
                "Coordinate dimensioning cannot be combined with supplied dimensions/constraints");
        // The section axes are whatever Creo picked for the support plane and its
        // orientation reference; the sketch u axis may meet them at any angle.
        // Coordinate dimensions are created and verified in native section
        // coordinates either way, so name the input u/v components after their
        // dominant section axis instead of rejecting unaligned frames. Under
        // the frame-basis fallback the assumed section x axis is frame.u, so
        // the effective matrix (not the placeholder identity) answers here.
        double u_to_section_x =
            dot(frame.u, V{effective_loc[0][0], effective_loc[0][1], effective_loc[0][2]});
        std::array<int, 2> axes =
            fabs(u_to_section_x) >= sqrt(0.5) ? std::array<int, 2>{0, 1} : std::array<int, 2>{1, 0};
        log("COORDINATE_AXES u_to_section_x=%.9f axes=%d,%d\n", u_to_section_x, axes[0], axes[1]);
        coordinate_plan = coordinate_dimensions(section, csid, entities, axes, coordinate_anchors);
        dims = coordinate_plan["dimension_ids"];
        deviation_targets = coordinate_plan["targets"];
    }
    for (auto d : op.value("dimensions", J::array())) {
        std::vector<int> ids;
        std::vector<ProSectionPointType> senses;
        for (auto r : d["refs"]) {
            ids.push_back(entities.at(r["entity"].get<std::string>()));
            senses.push_back(logical_point(ids.back(), point_type(r.value("point", "whole"))));
        }
        double place[2];
        project(d["position"], place);
        int id;
        CK(ProSecdimCreate(section, ids.data(), senses.data(), (int)ids.size(), dt.at(d["type"]),
                           place, &id));
        CK(ProSecdimValueSet(section, id, d["value"]));
        dims[d["name"].get<std::string>()] = id;
    }
    // Non-coordinates modes snapshot the pre-solve section so the solved
    // geometry can be measured against the same named entities afterwards.
    if (deviation_targets.is_null())
        deviation_targets = section_target_snapshot(section, entities);
    J solver_info = solve_profile(section, solving_op);
    solver_info["requested"] = op.value("dimensioning", "auto");
    J deviation_regenerate = geometry_deviation_stage(section, deviation_targets, deviation_policy);
    // FEAT-039/W01: the weld residual is read back while the solved section is
    // still the one the entities were written into.
    double weld_residual = -1.0;
    if (weld_report.value("applied_pairs", 0) > 0)
        weld_residual = endpoint_weld_residual(section, entities, weld_report);
    solver_info["section_location"] = section_location;
    if (!coordinate_plan.is_null())
        solver_info["coordinate_geometry"] = verify_coordinate_plan(
            section, coordinate_plan["targets"], coordinate_plan["origin_id"], deviation_policy);
    CK(ProElementSpecialvalueSet(sk, (ProAppData)section));
    redefine(&f, root);
    CK(ProFeatureElemtreeFree(&f, root));
    ProSelectionFree(&plane_ref);
    ProSelectionFree(&orient);
    ProSection saved = nullptr;
    ProError copy_code = ProFeatureSectionCopy(&f, 0, &saved);
    J native_section = {{"available", false}, {"query_code", copy_code}};
    J arc_geometry = J::array();
    J deviation_feature;
    if (!copy_code) {
        try {
            native_section = section_profile_summary(saved, "sketch");
            arc_geometry =
                arc_geometry_report(saved, copy_code, op["entities"], entities, frame.origin,
                                    frame.u, frame.v, effective_loc, mirrored);
            if (!coordinate_plan.is_null())
                solver_info["coordinate_geometry_after_creation"] =
                    verify_coordinate_plan(saved, coordinate_plan["targets"],
                                           coordinate_plan["origin_id"], deviation_policy);
            deviation_feature =
                geometry_deviation_stage(saved, deviation_targets, deviation_policy);
        } catch (...) {
            ProSectionFree(&saved);
            throw;
        }
        CK(ProSectionFree(&saved));
    } else if (!coordinate_plan.is_null())
        check(copy_code, "CopySketchSection");
    else {
        log("SECTION_PROFILE_UNAVAILABLE phase=sketch copy_code=%d\n", copy_code);
        deviation_feature =
            unavailable_deviation_stage("the solved feature section could not be copied (code " +
                                        std::to_string((int)copy_code) + ")");
    }
    if (arc_geometry.empty())
        arc_geometry = arc_geometry_report(nullptr, copy_code, op["entities"], entities,
                                           frame.origin, frame.u, frame.v, effective_loc, mirrored);
    solver_info["native_section"] = native_section;
    // FEAT-010/BUG-049: publish the two-stage fidelity report on the
    // operation result; an enforced policy rejects before the feature ships.
    J geometry_deviation = geometry_deviation_report(
        deviation_regenerate, deviation_feature, deviation_policy.tolerance,
        deviation_policy.enforce, deviation_policy.source);
    // BUG-108: publish the shift verdict next to geometry_deviation before the
    // policy is enforced, so the coordinates verdict is the one the shape gate
    // sees. A deformed sketch is still rejected; a provable rigid translation
    // inside the limit is accepted and says so.
    J sketch_shifted;
    if (!coordinate_plan.is_null()) {
        const J &verification = solver_info.contains("coordinate_geometry_after_creation")
                                    ? solver_info["coordinate_geometry_after_creation"]
                                    : solver_info["coordinate_geometry"];
        sketch_shifted = sketch_shift_block(verification, deviation_policy);
        geometry_deviation["shift_detected"] = sketch_shifted["detected"];
        geometry_deviation["accepted_by_request"] = sketch_shifted["accepted_by_request"];
        geometry_deviation["accepted_rigid"] = sketch_shifted["accepted_rigid"];
        if (sketch_shifted["rigid"].is_boolean()) {
            geometry_deviation["rigid"] = sketch_shifted["rigid"];
            geometry_deviation["translation_mm"] = sketch_shifted["translation_mm"];
            geometry_deviation["translation_magnitude_mm"] =
                sketch_shifted["translation_magnitude_mm"];
            if (sketch_shifted["residual_mm"].is_number()) {
                geometry_deviation["shape_deviation_mm"] = sketch_shifted["residual_mm"];
                geometry_deviation["residual_mm"] = sketch_shifted["residual_mm"];
            }
        }
    } else {
        geometry_deviation["shift_detected"] = nullptr;
        geometry_deviation["accepted_by_request"] = nullptr;
        // Only a measured coordinates solve can prove a rigid translation.
        geometry_deviation["accepted_rigid"] = false;
    }
    enforce_geometry_deviation(geometry_deviation, deviation_policy, deviation_context);
    solver_info["geometry_deviation"] = geometry_deviation;
    solver_info["sketch_shifted"] = sketch_shifted;
    J ids = J::object();
    for (auto item : entities)
        ids[item.first] = item.second;
    remember(
        op, f,
        {{"feature_id", (int)f.id},
         {"entity_ids", ids},
         {"dimension_ids", dims},
         {"solver", solver_info},
         {"geometry", spec},
         {"geometry_stale", false},
         {"last_dimensioning", op.value("dimensioning", "auto")},
         {"surface_id", frame.surface},
         {"normal", frame.n},
         {"origin", frame.origin},
         {"u_axis", frame.u},
         {"v_axis", frame.v},
         {"section_normal_sign",
          use_frame_basis ? 1 : (dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) > 0 ? 1 : -1)}});
    if (op.contains("profile"))
        aliases[op["label"].get<std::string>()]["airfoil"] = op["profile"];
    // FEAT-008/T09B: publish the section entity ids on the operation record so
    // the reported revolve_axis.id for an internal centerline is verifiable
    // from the client-visible result (same id space, no guessing).
    // BUG-120/T2-B: the curves this section actually owns, read one by one. T2 on
    // Creo 10 showed one straight line reporting two curve-type items (43/45) plus a
    // third non-curve entry (44), and nothing in the public inspect output says which
    // is which. These facts use the same calls the panel route uses, so a client can
    // see why a position has more than one candidate id instead of guessing.
    J curve_facts = J::array();
    {
        J owned = J::array();
        if (!ProFeatureGeomitemVisit(&f, PRO_CURVE, collect_geom_ids, nullptr, &owned))
            for (auto &entry : owned) {
                const int owned_id = entry.value("id", 0);
                ProCurve owned_curve;
                if (ProCurveInit((ProSolid)board, owned_id, &owned_curve) != PRO_TK_NO_ERROR) {
                    curve_facts.push_back({{"id", owned_id}, {"readable", false}});
                    continue;
                }
                ProEnttype owned_kind = (ProEnttype)0;
                const ProError kind_code = ProCurveTypeGet(owned_curve, &owned_kind);
                double owned_length = 0.0;
                const ProError length_code = ProCurveLengthEval(owned_curve, &owned_length);
                curve_facts.push_back(
                    {{"id", owned_id},
                     {"readable", true},
                     {"type", kind_code == PRO_TK_NO_ERROR ? J((int)owned_kind) : J(nullptr)},
                     {"type_code", (int)kind_code},
                     {"composite",
                      kind_code == PRO_TK_NO_ERROR ? J(owned_kind == PRO_ENT_CMP_CRV) : J(nullptr)},
                     {"length_mm", length_code == PRO_TK_NO_ERROR ? J(owned_length) : J(nullptr)},
                     {"length_code", (int)length_code}});
            }
    }
    J sketch_result = {{"feature_id", (int)f.id},
                       {"curve_facts", curve_facts},
                       {"surface_id", frame.surface},
                       {"solver", sketch_solver_receipt(solver_info)},
                       {"section_references", last_sketch_reference_info},
                       {"origin", frame.origin},
                       {"normal", frame.n},
                       {"u_axis", frame.u},
                       {"v_axis", frame.v},
                       {"native_section", native_section},
                       {"arc_geometry", arc_geometry},
                       {"geometry_deviation", geometry_deviation},
                       {"section_location", section_location},
                       {"entity_ids", ids}};
    // FEAT-039/W01: the endpoint weld is reported with what the native side
    // actually did. The coordinates were regularised before the entities were
    // written, so the move is bounded by the request, and the residual is
    // measured on the solved section.
    if (solver_info.contains("weld_requested")) {
        weld_report["epsilon_mm"] = solver_info.value("epsilon_mm", J(nullptr));
        weld_report["epsilon_source"] = solver_info.value("epsilon_source", J(nullptr));
        weld_report["max_residual_mm"] = weld_residual >= 0.0 ? J(weld_residual) : J(nullptr);
        weld_report["applied"] = weld_report.value("applied_pairs", 0) > 0;
        weld_report["note"] =
            "the endpoints were regularised before the entities were written, so the move is "
            "bounded by max_endpoint_move_mm; the residual is measured on the solved section";
        sketch_result["endpoint_weld_native"] = weld_report;
    }
    if (!sketch_shifted.is_null())
        sketch_result["sketch_shifted"] = sketch_shifted;
    if (!approximations.empty())
        sketch_result["b_spline_approximations"] = std::move(approximations);
    return sketch_result;
}
// ProFeatureWithoptionsCreate reports an invalid section only as a bare code;
// Toolkit validation stays authoritative. Report the native section counts
// when they are available and say plainly when they do not identify the cause
// instead of naming one (R3 §4.2: the old text implied an invalid profile).
static std::string section_create_failure(const J &op, bool revolve, ProError error,
                                          const J &section) {
    std::string m = revolve ? "Revolve" : "Extrude";
    m += " feature creation failed (ProFeatureWithoptionsCreate=" + std::to_string(error) + ")";
    if (revolve) {
        m += ". The closed profile must lie entirely on one side of the revolve axis and must "
             "not cross it; entities may touch the axis. The sketch must contain a centerline, "
             "or an explicit axis must be supplied, and the profile must be closed.";
    } else {
        m += ". Toolkit rejected the referenced sketch section; the return code alone does not "
             "identify whether closure, a geometric condition or the feature tree caused it.";
    }
    if (section.value("available", false)) {
        m += " Detected native section: " + std::to_string(section["closed_contours"].get<int>()) +
             " closed contour(s), " + std::to_string(section["contours"].get<int>()) +
             " contour(s), " + std::to_string(section["entities"].get<int>()) + " entity(ies), " +
             std::to_string(section["open_ends"].get<int>()) + " open end(s).";
        if (section["open_ends"].get<int>() > 0) {
            if (!revolve && op.value("mode", std::string("add")) == "surface") {
                int open_contours =
                    section["contours"].get<int>() - section["closed_contours"].get<int>();
                if (open_contours > 1)
                    m += " The section contains multiple open contours. Try one sketch and "
                         "surface extrude per open contour.";
                else
                    m += " The section contains open ends; check the curve geometry and "
                         "surface extrusion settings.";
            } else {
                m += " The section carries open ends, so it is not a closed profile.";
            }
            if (section.contains("max_endpoint_gap_mm")) {
                char gap_text[64];
                snprintf(gap_text, sizeof(gap_text), "%.9g",
                         section["max_endpoint_gap_mm"].get<double>());
                m += " Max open endpoint gap " + std::string(gap_text) +
                     " mm (diagnostic sampling, not a kernel welding tolerance).";
            }
            if (section.contains("open_end_samples") && section["open_end_samples"].is_array() &&
                !section["open_end_samples"].empty()) {
                m += " Nearest open ends:";
                size_t shown = std::min<size_t>(section["open_end_samples"].size(), 5);
                for (size_t i = 0; i < shown; i++) {
                    const J &sample = section["open_end_samples"][i];
                    char item_buf[192];
                    double px = sample["point"][0].get<double>();
                    double py = sample["point"][1].get<double>();
                    double gap = sample.value("nearest_gap_mm", 0.0);
                    int eid = sample.value("entity", -1);
                    if (sample.contains("nearest_entity") &&
                        sample["nearest_entity"].is_number_integer()) {
                        snprintf(item_buf, sizeof(item_buf),
                                 " ent_%d@(%.6g,%.6g)->ent_%d (%.9g mm)", eid, px, py,
                                 sample["nearest_entity"].get<int>(), gap);
                    } else {
                        snprintf(item_buf, sizeof(item_buf), " ent_%d@(%.6g,%.6g) (%.9g mm)", eid,
                                 px, py, gap);
                    }
                    if (i > 0)
                        m += ";";
                    m += item_buf;
                }
                m += ".";
            }
        } else if (section.contains("max_cluster_spread_mm") &&
                   section["max_cluster_spread_mm"].is_number() &&
                   section["max_cluster_spread_mm"].get<double>() > 0.0) {
            // BUG-101: a section can close only through the diagnostic
            // clustering tolerance. Its counts then look perfect while the
            // kernel refuses to weld the endpoints, so name that evidence
            // instead of leaving the cause undetermined.
            char spread_text[64];
            snprintf(spread_text, sizeof(spread_text), "%.9g",
                     section["max_cluster_spread_mm"].get<double>());
            m += std::string(" The section has no open ends, but its endpoint clusters spread up "
                             "to ") +
                 spread_text +
                 " mm at the diagnostic clustering tolerance: endpoints joined only by that "
                 "tolerance are not necessarily welded by the kernel, so a closed-looking count "
                 "can still be rejected. Snap the near-tolerance endpoints (see the sketch "
                 "profile's weldability block) and retry.";
        } else
            m += " These counts do not identify the cause; the cause is not determined.";
    } else
        m += " Native section counts are unavailable (code " +
             std::to_string(section.value("query_code", 0)) + "); the cause is not determined.";
    if (op["sketch"].is_string())
        m += " Sketch: '" + op["sketch"].get<std::string>() + "'.";
    if (!last_feature_errors.empty())
        m += " Element errors: " + last_feature_errors + ".";
    return m;
}
// BUG-083: a malformed revolve axis must fail with an actionable message before
// any keyed access; the Python precheck normally rejects these earlier.
static void validate_revolve_axis(const J &op) {
    if (!op.contains("axis"))
        return; // internal reference: the sketch's construction centerline
    const J &axis = op["axis"];
    std::string problem;
    if (!axis.is_object() || axis.empty())
        problem = "it is not a non-empty object";
    else if (!axis.contains("kind") || !axis["kind"].is_string())
        problem = "the kind key is missing or not a string";
    else if (axis["kind"] == "axis") {
        if (!axis.contains("id") || !axis["id"].is_number_integer() ||
            axis["id"].get<long long>() < 0)
            problem = "kind 'axis' requires a nonnegative integer id";
    } else if (axis["kind"] == "datum_axis_feature") {
        if (!axis.contains("label") || !axis["label"].is_string() ||
            axis["label"].get<std::string>().empty())
            problem = "kind 'datum_axis_feature' requires a nonempty label";
    } else if (axis["kind"] == "sketch_points") {
        auto valid_pt = [](const J &v) {
            return v.is_array() && v.size() == 2 && v[0].is_number() && v[1].is_number() &&
                   std::isfinite(v[0].get<double>()) && std::isfinite(v[1].get<double>());
        };
        if (!axis.contains("start_mm") || !axis.contains("end_mm") || !valid_pt(axis["start_mm"]) ||
            !valid_pt(axis["end_mm"]))
            problem = "kind 'sketch_points' requires finite 2D start_mm and end_mm points";
        else {
            double dx = axis["end_mm"][0].get<double>() - axis["start_mm"][0].get<double>();
            double dy = axis["end_mm"][1].get<double>() - axis["start_mm"][1].get<double>();
            if (hypot(dx, dy) < 1e-6)
                problem = "kind 'sketch_points' start_mm and end_mm must be distinct (>= 1e-6 mm)";
        }
    } else
        problem = "kind '" + axis["kind"].get<std::string>() + "' is not a revolve axis";
    if (!problem.empty())
        throw std::runtime_error(
            "Invalid revolve axis: " + problem +
            ". Use {\"kind\":\"datum_axis_feature\",\"label\":\"axis_label\"} (create that datum "
            "axis feature first), {\"kind\":\"axis\",\"id\":N} from model inspection, "
            "{\"kind\":\"sketch_points\",\"start_mm\":[u1,v1],\"end_mm\":[u2,v2]}, or omit "
            "axis to revolve about the sketch centerline (one construction centerline required)");
}
// FEAT-008/T09B: classify the resolved axis by provenance. ProAxisSurfaceGet
// reports the surface that owns the axis: an owning surface means the axis
// resolves from surface geometry (a cylinder/hole axis), while a datum axis
// has no owning surface. Unknown probes stay unknown.
static std::string classify_axis_provenance(int axis_id, ProError &surface_code) {
    ProAxis handle = nullptr;
    ProError init_code = ProAxisInit((ProSolid)board, axis_id, &handle);
    if (init_code) {
        surface_code = init_code;
        return "unknown";
    }
    ProSurface owner_surface = nullptr;
    surface_code = ProAxisSurfaceGet(board, handle, &owner_surface);
    if (surface_code == PRO_TK_NO_ERROR)
        return "surface";
    if (surface_code == PRO_TK_E_NOT_FOUND)
        return "datum_axis";
    return "unknown";
}
// DEV-093 / 0.27.0 feedback (T4): report how the explicit revolve axis sits
// with respect to the sketch plane it is paired with. Creo revolves about any
// line in space, so a non-coplanar axis is not an error by itself - the numbers
// exist because a regeneration refusal is otherwise a bare kernel sentence and
// the caller cannot tell an axis/plane mismatch from a bad profile. These
// thresholds only classify the report; they never admit or refuse a feature.
static constexpr double REVOLVE_AXIS_PLANE_DISTANCE_MM = 1e-6;
static constexpr double REVOLVE_AXIS_PLANE_ANGLE_DEG = 1e-3;

static J revolve_axis_plane_relation(const J &op, int axis_id, ProError axis_code) {
    J relation = {{"available", false},
                  {"source", "unavailable"},
                  {"reason", nullptr},
                  {"query_code", nullptr},
                  {"axis_origin_mm", nullptr},
                  {"axis_direction", nullptr},
                  {"plane_origin_mm", nullptr},
                  {"plane_normal", nullptr},
                  {"signed_distance_mm", nullptr},
                  {"origin_distance_mm", nullptr},
                  {"direction_angle_to_plane_deg", nullptr},
                  {"direction_angle_to_normal_deg", nullptr},
                  {"axis_lies_in_plane", nullptr},
                  {"thresholds",
                   {{"distance_mm", REVOLVE_AXIS_PLANE_DISTANCE_MM},
                    {"angle_deg", REVOLVE_AXIS_PLANE_ANGLE_DEG}}},
                  {"note",
                   "Measured axis geometry against the sketch alias frame. A non-coplanar axis "
                   "is not an error by itself and these numbers do not on their own show why "
                   "Creo refused the feature."}};
    if (axis_code || axis_id < 0) {
        relation["reason"] = "axis_unresolved";
        relation["query_code"] = axis_code;
        return relation;
    }
    ProGeomitem item = {};
    ProError item_code = ProModelitemInit(board, axis_id, PRO_AXIS, &item);
    if (item_code) {
        relation["reason"] = "axis_item_unavailable";
        relation["query_code"] = item_code;
        return relation;
    }
    AxisGeometry geometry = inspect_axis_geometry(&item);
    if (!geometry.known) {
        relation["reason"] = "axis_geometry_unreadable";
        relation["query_code"] = geometry.data_code;
        return relation;
    }
    const J *entry = op.contains("sketch") && op["sketch"].is_string()
                         ? alias_entry(op["sketch"].get<std::string>())
                         : nullptr;
    // A malformed alias degrades to "unavailable": this report is a diagnosis,
    // never a precondition of the feature.
    auto frame_vector = [](const J &value) {
        return value.is_array() && value.size() == 3 && value[0].is_number() &&
               value[1].is_number() && value[2].is_number();
    };
    if (!entry || !entry->contains("origin") || !entry->contains("normal") ||
        !frame_vector((*entry)["origin"]) || !frame_vector((*entry)["normal"])) {
        relation["reason"] = "sketch_alias_frame_unavailable";
        return relation;
    }
    const V plane_origin = vec((*entry)["origin"]);
    const V plane_normal = normalized(vec((*entry)["normal"]));
    const V axis_origin = {geometry.origin[0], geometry.origin[1], geometry.origin[2]};
    const V axis_direction = {geometry.direction[0], geometry.direction[1], geometry.direction[2]};
    const double signed_distance = dot(plane_normal, add(axis_origin, scale(plane_origin, -1.0)));
    const double along_normal = std::fabs(dot(axis_direction, plane_normal));
    const double half_pi = 3.14159265358979323846;
    const double angle_to_plane = std::asin(std::min(1.0, along_normal)) * 180.0 / half_pi;
    const double angle_to_normal = std::acos(std::min(1.0, along_normal)) * 180.0 / half_pi;
    relation.update(
        {{"available", true},
         {"source", "measured_axis_and_sketch_alias"},
         {"reason", nullptr},
         {"query_code", geometry.line_code ? J(*geometry.line_code) : J(geometry.data_code)},
         {"axis_origin_mm", J::array({axis_origin[0], axis_origin[1], axis_origin[2]})},
         {"axis_direction", J::array({axis_direction[0], axis_direction[1], axis_direction[2]})},
         {"plane_origin_mm", J::array({plane_origin[0], plane_origin[1], plane_origin[2]})},
         {"plane_normal", J::array({plane_normal[0], plane_normal[1], plane_normal[2]})},
         {"signed_distance_mm", signed_distance},
         {"origin_distance_mm", std::fabs(signed_distance)},
         {"direction_angle_to_plane_deg", angle_to_plane},
         {"direction_angle_to_normal_deg", angle_to_normal},
         {"axis_lies_in_plane", std::fabs(signed_distance) <= REVOLVE_AXIS_PLANE_DISTANCE_MM &&
                                    angle_to_plane <= REVOLVE_AXIS_PLANE_ANGLE_DEG}});
    return relation;
}

// The same numbers as one sentence, so a failed revolve does not require opening
// the operation record. Empty when the relation could not be measured.
static std::string revolve_axis_plane_relation_text(const J &relation) {
    if (!relation.is_object() || !relation.value("available", false))
        return "";
    const J &ao = relation["axis_origin_mm"], &ad = relation["axis_direction"];
    const J &po = relation["plane_origin_mm"], &pn = relation["plane_normal"];
    char numbers[640];
    std::snprintf(
        numbers, sizeof(numbers),
        " Revolve axis (mm): origin (%.9g, %.9g, %.9g), direction (%.9g, %.9g, %.9g). Sketch "
        "plane (mm): origin (%.9g, %.9g, %.9g), normal (%.9g, %.9g, %.9g). The axis origin is "
        "%.9g mm from the plane, and the axis is %.9g deg out of the plane (%.9g deg from its "
        "normal). See revolve_axis_plane_relation in the operation result; these measured "
        "numbers do not on their own show why Creo refused the feature.",
        ao[0].get<double>(), ao[1].get<double>(), ao[2].get<double>(), ad[0].get<double>(),
        ad[1].get<double>(), ad[2].get<double>(), po[0].get<double>(), po[1].get<double>(),
        po[2].get<double>(), pn[0].get<double>(), pn[1].get<double>(), pn[2].get<double>(),
        relation["origin_distance_mm"].get<double>(),
        relation["direction_angle_to_plane_deg"].get<double>(),
        relation["direction_angle_to_normal_deg"].get<double>());
    return numbers;
}

// Preserve the original refusal text when a diagnosis has to be appended: a
// Toolkit code is thrown as an int, so a std::exception-only catch would lose it.
static std::string native_exception_text(const std::exception_ptr &error) {
    try {
        std::rethrow_exception(error);
    } catch (const std::exception &typed) {
        return typed.what();
    } catch (ProError code) {
        return "native Toolkit error code " + std::to_string(code);
    } catch (...) {
        return "unrecognized native error";
    }
}

// FEAT-008/T09B: report the axis a revolve actually resolved to. Values come
// only from the executor's own queries (the created feature's axis geomitem,
// the explicit axis geomitem, ProAxisSurfaceGet provenance or the sketch
// section centerline); request parameters are never echoed as measured
// geometry and unknown stays null with raw query codes. Origin/direction are
// model coordinates for frame="model" and sketch section (u,v) coordinates
// for frame="sketch_local".
static J revolve_axis_report(const J &op, ProFeature &created, ProFeature &sketch_f,
                             int explicit_axis_id, ProError explicit_axis_code) {
    bool explicit_source = op.contains("axis") && !op.at("axis").is_null() &&
                           op.at("axis").value("kind", "") != "sketch_points";
    J report = {{"source", explicit_source ? "explicit" : "internal_centerline"},
                {"kind", "unknown"},
                {"id", nullptr},
                {"frame", nullptr},
                {"origin", nullptr},
                {"direction", nullptr},
                {"geometry_known", false},
                {"query_code", nullptr},
                {"resolution",
                 {{"feature_axis_query_code", nullptr},
                  {"axis_item_query_code", nullptr},
                  {"axis_surface_query_code", nullptr},
                  {"section_centerline_count", nullptr},
                  {"section_query_code", nullptr}}}};
    auto units = inspect_length_units(board);
    report["length_unit"] = length_unit_json(units, length_scale_to_mm(board, units));
    // The created revolve feature's own axis geomitem is the most direct
    // statement of the axis actually used.
    J axes = feature_axes(&created);
    report["resolution"]["feature_axis_query_code"] = axes["axes_query_code"];
    const J *feature_axis = nullptr;
    if (axes["datum_axes"].is_array() && axes["datum_axes"].size() == 1 &&
        axes["datum_axes"][0].is_object())
        feature_axis = &axes["datum_axes"][0];
    bool feature_known = feature_axis && feature_axis->contains("geometry_known") &&
                         (*feature_axis)["geometry_known"].is_boolean() &&
                         (*feature_axis)["geometry_known"].get<bool>();
    if (explicit_source) {
        report["resolution"]["axis_item_query_code"] = explicit_axis_code;
        if (explicit_axis_code || explicit_axis_id < 0)
            return report; // resolution failed: honest unknown, raw code kept
        report["id"] = explicit_axis_id;
        ProError surface_code = PRO_TK_NO_ERROR;
        report["kind"] = classify_axis_provenance(explicit_axis_id, surface_code);
        report["resolution"]["axis_surface_query_code"] = surface_code;
        ProGeomitem item = {};
        ProError item_code = ProModelitemInit(board, explicit_axis_id, PRO_AXIS, &item);
        AxisGeometry geometry;
        if (!item_code)
            geometry = inspect_axis_geometry(&item);
        else
            geometry.data_code = item_code;
        if (geometry.known) {
            report["origin"] = geometry.origin;
            report["direction"] = geometry.direction;
            report["frame"] = "model";
            report["geometry_known"] = true;
            report["query_code"] =
                geometry.line_code ? J(*geometry.line_code) : J(geometry.data_code);
        } else if (feature_known) {
            report["origin"] = (*feature_axis)["origin"];
            report["direction"] = (*feature_axis)["direction"];
            report["frame"] = "model";
            report["geometry_known"] = true;
            report["query_code"] = (*feature_axis)["data_query_code"];
        } else
            report["query_code"] = geometry.data_code;
        return report;
    }
    // Internal fallback: the axis decision came from the sketch's construction
    // centerline. Count only user-drawn centerlines so a silent pick stays
    // discoverable; when more than one true user centerline exists the chosen
    // one is not guessable, so id stays null and the caller must supply an
    // explicit axis (the count is reported either way).
    report["kind"] = "section_centerline";
    ProSection saved = nullptr;
    ProError copy_code = ProFeatureSectionCopy(&sketch_f, 0, &saved);
    if (copy_code) {
        report["resolution"]["section_query_code"] = copy_code;
    } else {
        // FEAT-008/T09B (10-31 live run): on the section copied from the
        // created sketch feature the system reference projections no longer
        // report themselves as projections (native log SECTION_CENTERLINE_PROBE
        // entity=3/4/9 is_projection=0 for a sketch with one drawn centerline),
        // so the probe below alone still counted 3. The sketch's own record is
        // authoritative for what the user drew: the ids it registered for
        // entities whose declared type is "centerline". When the record has no
        // centerline entry the projection probe stays the only classifier and
        // a failed probe keeps the entity counted (never silently dropped).
        std::set<int> user_centerlines;
        const J *sketch_meta =
            op.at("sketch").is_string() ? alias_entry(op.at("sketch").get<std::string>()) : nullptr;
        if (sketch_meta && sketch_meta->contains("entity_ids") &&
            sketch_meta->contains("geometry")) {
            const J &record_ids = sketch_meta->at("entity_ids");
            for (const J &e : sketch_meta->at("geometry"))
                if (e.is_object() && e.value("type", "") == "centerline" && e.contains("name") &&
                    record_ids.contains(e.at("name").get<std::string>()))
                    user_centerlines.insert(
                        record_ids.at(e.at("name").get<std::string>()).get<int>());
            if (sketch_meta->contains("revolve_centerline_id") &&
                sketch_meta->at("revolve_centerline_id").is_number_integer())
                user_centerlines.insert(sketch_meta->at("revolve_centerline_id").get<int>());
            log("SECTION_CENTERLINE_META drawn_user_lines=%zu\n", user_centerlines.size());
        }
        ProIntlist ids = nullptr;
        int count = 0;
        ProError ids_code = ProSectionEntityIdsGet(saved, &ids, &count);
        std::vector<int> centerlines;
        std::array<double, 2> start = {}, end = {};
        if (ids_code) {
            report["resolution"]["section_query_code"] = ids_code;
        } else {
            for (int index = 0; index < count; index++) {
                Pro2dEntdef *def = nullptr;
                if (ProSectionEntityGet(saved, ids[index], &def))
                    continue;
                if (def->type != PRO_2D_CENTER_LINE)
                    continue;
                // Sketch creation projects the orientation and anchor
                // references into the section (sketch()), and Creo stores
                // those system references as center-line entities too, so the
                // type alone does not identify a user centerline: the 10-29
                // live run counted 3 for one drawn line. An entity "created by
                // projection" (ProSectionEntityIsProjection, same filter as
                // the profile summary walk) is a system reference, never a
                // user line; a failed probe cannot classify, so the entity
                // stays counted instead of being silently dropped.
                ProBoolean is_projection = PRO_B_FALSE;
                ProError projection_code =
                    ProSectionEntityIsProjection(saved, ids[index], &is_projection);
                log("SECTION_CENTERLINE_PROBE entity=%d code=%d is_projection=%d\n", ids[index],
                    (int)projection_code, is_projection == PRO_B_TRUE ? 1 : 0);
                if (!user_centerlines.empty()) {
                    // The sketch record knows the drawn centerlines; every
                    // other section centerline is a system reference.
                    if (user_centerlines.find(ids[index]) == user_centerlines.end())
                        continue;
                } else if (!projection_code && is_projection == PRO_B_TRUE)
                    continue;
                if (centerlines.empty()) {
                    auto line = (Pro2dLinedef *)def;
                    start = {line->end1[0], line->end1[1]};
                    end = {line->end2[0], line->end2[1]};
                }
                centerlines.push_back(ids[index]);
            }
            report["resolution"]["section_centerline_count"] = (int)centerlines.size();
        }
        ProSectionFree(&saved);
        if (centerlines.size() == 1)
            report["id"] = centerlines[0];
        if (!feature_known && centerlines.size() == 1) {
            double dx = end[0] - start[0], dy = end[1] - start[1];
            double length = std::hypot(dx, dy);
            report["origin"] = J::array({start[0], start[1]});
            report["frame"] = "sketch_local";
            report["query_code"] = PRO_TK_NO_ERROR;
            if (std::isfinite(length) && length > 1e-12) {
                report["direction"] = J::array({dx / length, dy / length});
                report["geometry_known"] = true;
            }
        }
    }
    if (feature_known) {
        report["origin"] = (*feature_axis)["origin"];
        report["direction"] = (*feature_axis)["direction"];
        report["frame"] = "model";
        report["geometry_known"] = true;
        report["query_code"] = (*feature_axis)["data_query_code"];
    }
    return report;
}
static J extrude_depth_report(ProFeature &f, const J &op);
// B2/F11: a zero-material cut publishes the geometry it actually used instead
// of asking the caller to guess it. The frame is read from the sketch alias
// (the same frame sketch() built), the depth from the created feature's own
// element tree, and the volumes from the regeneration comparison. Nothing is
// echoed from the request as a measurement; when the alias or the effective
// depth is unreadable the interval stays explicitly unavailable rather than
// being backfilled from op["depth"]. through_all has no finite interval.
static J cut_geometry_context(const J &op, bool revolve, int direction_sign, double before_volume,
                              double after_volume, double removed, double threshold,
                              const J &depth_report, ProFeature &sketch_feature) {
    J context = {{"status", "no_material_removed"},
                 {"operation", revolve ? "revolve" : "extrude"},
                 {"mode", "cut"},
                 {"sketch", op.at("sketch")},
                 {"direction", op.value("direction", "positive")},
                 {"direction_sign", direction_sign},
                 {"volume_mm3",
                  {{"before", before_volume},
                   {"after", after_volume},
                   {"removed", removed},
                   {"zero_material_threshold", threshold}}},
                 {"note", "The frame is read from the sketch alias and the effective depth from "
                          "the created feature's element tree; the interval is derived from "
                          "those readings, not measured as a swept volume."}};
    const J *entry =
        op["sketch"].is_string() ? alias_entry(op["sketch"].get<std::string>()) : nullptr;
    J frame = {{"available", false}, {"source", "unavailable"}, {"reason", nullptr}};
    V origin = {}, normal = {};
    // vec() reads three doubles without guarding its indices; a malformed alias
    // must degrade to an unavailable frame, never replace the cut failure with
    // an unrelated JSON exception.
    auto frame_vector = [](const J &value) {
        return value.is_array() && value.size() == 3 && value[0].is_number() &&
               value[1].is_number() && value[2].is_number();
    };
    if (entry && entry->is_object() && entry->contains("origin") && entry->contains("normal") &&
        frame_vector((*entry)["origin"]) && frame_vector((*entry)["normal"])) {
        origin = vec((*entry)["origin"]);
        normal = vec((*entry)["normal"]);
        frame = {{"available", true},
                 {"source", "sketch_alias"},
                 {"reason", nullptr},
                 {"origin_mm", (*entry)["origin"]},
                 {"normal", (*entry)["normal"]}};
        for (const char *key : {"u_axis", "v_axis", "surface_id", "section_normal_sign"})
            frame[key] = entry->contains(key) ? (*entry)[key] : J(nullptr);
    } else
        frame["reason"] = op["sketch"].is_string() ? "sketch_alias_unavailable"
                                                   : "sketch_reference_is_not_a_label";
    context["sketch_frame"] = frame;
    context["extrude_depth"] = revolve ? J(nullptr) : depth_report;
    context["revolve_angle_deg"] = revolve ? J(op.value("angle", 360.0)) : J(nullptr);
    J interval = {{"available", false},
                  {"source", "unavailable"},
                  {"reason", nullptr},
                  {"axis", nullptr},
                  {"origin_mm", nullptr},
                  {"start_offset_mm", nullptr},
                  {"end_offset_mm", nullptr},
                  {"start_point_mm", nullptr},
                  {"end_point_mm", nullptr},
                  {"effective_depth_type", nullptr},
                  {"effective_depth_mm", nullptr},
                  {"direction_sign", direction_sign}};
    const J effective_type = depth_report.value("effective_depth_type", J(nullptr));
    const J effective_depth = depth_report.value("effective_depth_mm", J(nullptr));
    if (effective_type.is_string())
        interval["effective_depth_type"] = effective_type;
    if (effective_depth.is_number())
        interval["effective_depth_mm"] = effective_depth;
    if (revolve)
        interval["reason"] = "revolve_cut_has_no_linear_depth";
    else if (!frame["available"].get<bool>())
        interval["reason"] = "sketch_frame_unavailable";
    else if (!effective_depth.is_number() || effective_depth.get<double>() <= 0.0)
        interval["reason"] =
            effective_type.is_string() && effective_type.get<std::string>() == "through_all"
                ? "through_all_has_no_finite_depth"
                : "effective_depth_unreadable";
    else {
        double depth = effective_depth.get<double>();
        bool symmetric =
            effective_type.is_string() && effective_type.get<std::string>() == "symmetric";
        double start = symmetric ? -depth / 2 : 0.0, end = symmetric ? depth / 2 : depth;
        V axis = scale(normal, (double)direction_sign);
        V start_point = add(origin, scale(axis, start));
        V end_point = add(origin, scale(axis, end));
        interval = {{"available", true},           {"source", "feature_tree_and_sketch_alias"},
                    {"reason", nullptr},           {"axis", axis},
                    {"origin_mm", origin},         {"start_offset_mm", start},
                    {"end_offset_mm", end},        {"start_point_mm", start_point},
                    {"end_point_mm", end_point},   {"effective_depth_type", effective_type},
                    {"effective_depth_mm", depth}, {"direction_sign", direction_sign}};
    }
    context["depth_interval_mm"] = interval;
    ProSection section = nullptr;
    const ProError copied = ProFeatureSectionCopy(&sketch_feature, 0, &section);
    if (copied == PRO_TK_NO_ERROR) {
        J summary;
        try {
            summary = section_profile_summary(section, "cut_no_material");
        } catch (...) {
            ProSectionFree(&section);
            throw;
        }
        CK(ProSectionFree(&section));
        for (const char *key : {"available", "query_code", "b_spline_entities", "closed_contours",
                                "open_ends", "solved_section_area_mm2"})
            if (summary.contains(key))
                context["native_section"][key] = summary[key];
        context["solved_section_area_mm2"] = summary.value("solved_section_area_mm2", J(nullptr));
    } else {
        context["native_section"] = {{"available", false}, {"query_code", copied}};
        context["solved_section_area_mm2"] = nullptr;
    }
    return context;
}
// The text stays a readable summary; the structured block is the receipt.
static std::string cut_no_material_failure(bool revolve, const J &context) {
    std::string message =
        std::string(revolve ? "Revolve" : "Extrude") + " cut removes no material.";
    const J &section = context["native_section"];
    if (section.value("b_spline_entities", 0) > 0 && section.value("closed_contours", 0) > 0)
        message += " The solved section contains a closed contour and B-splines. Creo can report "
                   "zero removal for this combination. If an approximation is acceptable, create "
                   "the B-spline with approximation_segments or provide a sampled polyline.";
    else
        message += " Check the sketch position, direction and depth against existing geometry.";
    const J &frame = context["sketch_frame"];
    if (frame.value("available", false)) {
        const J &origin = frame["origin_mm"], &normal = frame["normal"];
        char numbers[256];
        std::snprintf(numbers, sizeof(numbers),
                      " Sketch origin (mm) = (%.6g, %.6g, %.6g); normal = (%.6g, %.6g, %.6g); "
                      "direction sign = %d.",
                      origin[0].get<double>(), origin[1].get<double>(), origin[2].get<double>(),
                      normal[0].get<double>(), normal[1].get<double>(), normal[2].get<double>(),
                      context["direction_sign"].get<int>());
        message += numbers;
    }
    const J &interval = context["depth_interval_mm"];
    if (interval.value("available", false)) {
        char numbers[192];
        std::snprintf(numbers, sizeof(numbers),
                      " Effective depth %.6g mm spans [%.6g, %.6g] mm along the reported axis.",
                      interval["effective_depth_mm"].get<double>(),
                      interval["start_offset_mm"].get<double>(),
                      interval["end_offset_mm"].get<double>());
        message += numbers;
    } else
        message += " Effective depth interval is unavailable (" +
                   interval["reason"].get<std::string>() + ").";
    message += " See cut_geometry_context in the operation result for the structured receipt.";
    return message;
}
// advanced.cpp (included further down this file) defines get_path; the scope
// readback below needs it before that include point.
static ProElement get_path(ProElement root, const J &ids);
// B4/F08: read the applied scope back from the created feature tree. The
// request is never echoed as the applied value: every unreadable step keeps
// applied_body_ids null and stores its own query code, and a receipt whose
// source cannot be read is not labelled "feature_tree".
static J scope_applied_report(const J &op, ProFeature f, const J &before) {
    J requested = op.at("scope").at("body_ids");
    J report = {{"requested_body_ids", requested},
                {"applied_body_ids", nullptr},
                {"source", "feature_tree"},
                {"query_code", nullptr},
                {"non_target_bodies_unchanged", nullptr}};
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    if (code == PRO_TK_NO_ERROR) {
        try {
            ProElement body = get_path(tree, J::array({PRO_E_BODY}));
            ProElement use_element = get_path(body, J::array({PRO_E_BODY_USE}));
            int use = PRO_BODY_USE_ALL;
            ProError use_code = ProElementIntegerGet(use_element, nullptr, &use);
            // A cut whose element no longer says "selected body" did not apply
            // the requested scope; success would claim geometry never scoped.
            if (use_code != PRO_TK_NO_ERROR)
                code = use_code;
            else if (use != PRO_BODY_USE_SELECTED)
                code = PRO_TK_BAD_INPUTS;
            else {
                ProElement select = get_path(body, J::array({PRO_E_BODY_SELECT}));
                ProReference reference = nullptr;
                code = ProElementReferenceGet(select, nullptr, &reference);
                if (code == PRO_TK_NO_ERROR && reference) {
                    ProType type = PRO_TYPE_UNUSED;
                    int id = -1;
                    ProError type_code = ProReferenceTypeGet(reference, &type);
                    ProError id_code = ProReferenceIdGet(reference, &id);
                    code = type_code ? type_code : id_code;
                    // A same-numbered reference of another kind is not the body.
                    if (code == PRO_TK_NO_ERROR && type != PRO_BODY)
                        code = PRO_TK_BAD_INPUTS;
                    if (code == PRO_TK_NO_ERROR)
                        report["applied_body_ids"] = J::array({id});
                } else if (code == PRO_TK_NO_ERROR)
                    code = PRO_TK_BAD_INPUTS;
                if (reference)
                    ProReferenceFree(reference);
            }
        } catch (ProError missing) {
            // get_path throws when the created feature has no such element;
            // that is an unreadable receipt, not a crash.
            code = missing;
        }
    }
    report["query_code"] = code;
    if (code != PRO_TK_NO_ERROR)
        report["source"] = "feature_tree_unreadable";
    if (tree)
        CK(ProFeatureElemtreeFree(&f, tree));
    if (report["applied_body_ids"].is_array())
        report["non_target_bodies_unchanged"] =
            non_target_bodies_unchanged(before, body_fingerprints(), requested);
    return report;
}
// ---------------------------------------------------------------------------
// FEAT-070: rebuild a stale/invalid body reference on an existing solidify /
// patch feature. In Creo a failed PRO_E_BODY_SELECT reference (status
// PRO_REF_INVALID) self-locks the feature GUI and refuses regeneration even
// when a valid solid body exists. The repair extracts the feature element
// tree, validates the current body reference, rewrites PRO_E_BODY_USE /
// PRO_E_BODY_SELECT to a resolvable target body, redefines and regenerates.
// Any failure throws so the job finalizer rolls back to its saved checkpoint;
// the model is never left dirty. Partial receipts are staged before throwing
// so the failed operation record carries old_body / phase / raw Toolkit code.
// ---------------------------------------------------------------------------
static std::string feat070_body_use_label(int use) {
    if (use == PRO_BODY_USE_NEW)
        return "new";
    if (use == PRO_BODY_USE_ALL)
        return "all";
    if (use == PRO_BODY_USE_SELECTED)
        return "selected";
    return "unknown";
}
static std::string feat070_lower(const std::string &s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s)
        out.push_back((c >= 'A' && c <= 'Z') ? char(c - 'A' + 'a') : c);
    return out;
}
// Best-effort body counts + volume for the before/after receipt. A failed
// model may refuse mass-property evaluation; null is reported rather than
// aborting the repair. Also returns the live inspection state (features[]) so
// the target feature can be resolved by its Creo name.
static J feat070_snapshot() {
    J state = nullptr;
    try {
        state = inspection(false);
    } catch (...) {
        state = nullptr;
    }
    J counts = nullptr;
    if (state.is_object() && state.contains("body_counts") && state["body_counts"].is_object())
        counts = {{"objects", state["body_counts"].value("objects", 0)},
                  {"active", state["body_counts"].value("active", 0)},
                  {"with_material", state["body_counts"].value("with_material", 0)}};
    bool vol_ok = true;
    double vol = 0.0;
    try {
        vol = volume();
    } catch (...) {
        vol_ok = false;
    }
    return {
        {"state", state}, {"body_counts", counts}, {"volume_mm3", vol_ok ? J(vol) : J(nullptr)}};
}
// Resolve the target feature by id (int / digit string), MCP-owned label, or
// live Creo feature name (adopted / real parts are not registered aliases).
static int feat070_resolve_feature(const J &target, const J &state, std::string &out_name) {
    out_name.clear();
    bool numeric = target.is_number_integer();
    if (!numeric && target.is_string()) {
        const std::string &s = target.get_ref<const std::string &>();
        numeric = !s.empty() && s.find_first_not_of("0123456789") == std::string::npos;
    }
    int id = -1;
    if (numeric) {
        id = feature_id(target);
    } else if (target.is_string()) {
        try {
            id = feature_id(target);
        } catch (const std::exception &) {
            id = -1;
        }
        if (id < 0 && state.is_object() && state.contains("features")) {
            const std::string want = target.get<std::string>();
            const std::string want_lo = feat070_lower(want);
            for (const auto &f : state["features"]) {
                if (!f.contains("id"))
                    continue;
                const std::string name = f.value("name", "");
                if (name == want || feat070_lower(name) == want_lo) {
                    id = f["id"].get<int>();
                    break;
                }
            }
        }
    }
    if (id < 0)
        throw std::runtime_error(
            "FEAT070_FEATURE_NOT_FOUND: target feature was not found by id or name; run "
            "creo_inspect_model and pass the feature id");
    if (state.is_object() && state.contains("features"))
        for (const auto &f : state["features"])
            if (f.contains("id") && f["id"].get<int>() == id) {
                out_name = f.value("name", "");
                break;
            }
    return id;
}
// Read the current PRO_E_BODY / PRO_E_BODY_USE / PRO_E_BODY_SELECT from an
// extracted tree and decide whether the body reference is valid. Mirrors
// scope_applied_report() and adds the ProReferenceStatus check that catches
// PRO_REF_INVALID (the exact self-locked state FEAT-070 targets).
static J feat070_read_body_reference(ProElement tree, int &query_code) {
    query_code = PRO_TK_NO_ERROR;
    J report = {{"use", nullptr},    {"use_name", nullptr},   {"ref_type_int", nullptr},
                {"ref_id", nullptr}, {"ref_status", nullptr}, {"valid", false}};
    ProElement body = nullptr;
    try {
        body = get_path(tree, {PRO_E_BODY});
    } catch (ProError missing) {
        query_code = missing;
        return report;
    }
    ProElement use_elem = nullptr;
    try {
        use_elem = get_path(body, {PRO_E_BODY_USE});
    } catch (ProError missing) {
        query_code = missing;
        return report;
    }
    int use = PRO_BODY_USE_SELECTED;
    ProError c = ProElementIntegerGet(use_elem, nullptr, &use);
    query_code = c;
    if (c != PRO_TK_NO_ERROR)
        return report;
    report["use"] = use;
    report["use_name"] = feat070_body_use_label(use);
    if (use != PRO_BODY_USE_SELECTED)
        return report;
    ProElement select_elem = nullptr;
    try {
        select_elem = get_path(body, {PRO_E_BODY_SELECT});
    } catch (ProError) {
        // USE=SELECTED without a SELECT child is itself an invalid reference.
        query_code = PRO_TK_NO_ERROR;
        report["ref_status"] = "missing";
        return report;
    }
    ProReference reference = nullptr;
    c = ProElementReferenceGet(select_elem, nullptr, &reference);
    query_code = c;
    if (c != PRO_TK_NO_ERROR || !reference) {
        report["ref_status"] = c == PRO_TK_NO_ERROR ? "null" : "reference_get_failed";
        return report;
    }
    ProType rtype = PRO_TYPE_UNUSED;
    int rid = -1;
    ProError tc = ProReferenceTypeGet(reference, &rtype);
    ProError ic = ProReferenceIdGet(reference, &rid);
    report["ref_type_int"] = tc == PRO_TK_NO_ERROR ? J((int)rtype) : J(nullptr);
    report["ref_id"] = ic == PRO_TK_NO_ERROR ? J(rid) : J(nullptr);
    // ProRefState is the status enum used by ProReferenceStatusGet in both the
    // Creo 10 and Creo 13 Toolkit SDKs (ProRefInfo.h). The type is read here to
    // detect PRO_REF_INVALID, the exact self-locked state FEAT-070 targets.
    ProRefState status;
    ProError sc = ProReferenceStatusGet(reference, &status);
    if (sc == PRO_TK_NO_ERROR) {
        if (status == PRO_REF_INVALID)
            report["ref_status"] = "invalid";
        else if (status == PRO_REF_MISSING)
            report["ref_status"] = "missing";
        else
            report["ref_status"] = "ok";
    } else if (sc == PRO_TK_EMPTY) {
        report["ref_status"] = "ok";
    } else {
        report["ref_status"] = "unknown";
    }
    bool type_ok = (tc == PRO_TK_NO_ERROR && rtype == PRO_BODY);
    bool resolvable = (sc == PRO_TK_EMPTY || (sc == PRO_TK_NO_ERROR && status != PRO_REF_INVALID &&
                                              status != PRO_REF_MISSING));
    report["valid"] = type_ok && resolvable && rid >= 0;
    query_code = PRO_TK_NO_ERROR;
    return report;
}
static J generic_redefine_solidify_body(const J &op) {
    const std::string strategy = op.value("body_strategy", std::string("existing"));
    if (strategy != "existing" && strategy != "body_id" && strategy != "new")
        throw std::runtime_error(
            "FEAT070_BAD_STRATEGY: body_strategy must be 'existing', 'body_id' or 'new'");

    J before = feat070_snapshot();
    const J &state = before["state"];

    std::string feature_name;
    int fid = feat070_resolve_feature(op.at("feature"), state, feature_name);
    ProFeature f = feature(fid);

    ProElement tree = nullptr;
    ProError ec = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    if (ec != PRO_TK_NO_ERROR || !tree) {
        stage_operation_result({{"phase", "extract"},
                                {"feature_id", fid},
                                {"feature_name", feature_name},
                                {"feature_incomplete", true},
                                {"body_counts_before", before["body_counts"]},
                                {"volume_before_mm3", before["volume_mm3"]}});
        throw std::runtime_error("FEAT070_EXTRACT_FAILED: ProFeatureElemtreeExtract failed (code " +
                                 std::to_string((int)ec) + ") for feature " + std::to_string(fid) +
                                 "; the feature tree cannot be read");
    }

    int old_query = PRO_TK_NO_ERROR;
    J old_body = feat070_read_body_reference(tree, old_query);
    old_body["query_code"] = old_query;

    auto free_tree = [&]() {
        if (tree) {
            ProFeatureElemtreeFree(&f, tree);
            tree = nullptr;
        }
    };
    ProSelection target_sel = nullptr;
    auto free_sel = [&]() {
        if (target_sel) {
            ProSelectionFree(&target_sel);
            target_sel = nullptr;
        }
    };
    auto fail = [&](const std::string &phase, const std::string &message, const J &extra) {
        free_sel();
        free_tree();
        J receipt = {{"phase", phase},
                     {"feature_id", fid},
                     {"feature_name", feature_name},
                     {"old_body", old_body},
                     {"feature_incomplete", true},
                     {"body_counts_before", before["body_counts"]},
                     {"volume_before_mm3", before["volume_mm3"]}};
        if (extra.is_object())
            receipt.update(extra);
        stage_operation_result(std::move(receipt));
        throw std::runtime_error(message);
    };

    ProElement body_elem = nullptr;
    try {
        body_elem = get_path(tree, {PRO_E_BODY});
    } catch (ProError missing) {
        fail("locate_body_branch",
             "FEAT070_NO_BODY_BRANCH: feature " + std::to_string(fid) +
                 " has no PRO_E_BODY body-options branch; only solidify/patch features "
                 "carry one (query_code=" +
                 std::to_string(missing) + ")",
             J::object());
    }

    J new_body = {{"strategy", strategy},    {"use", nullptr},    {"use_name", nullptr},
                  {"ref_type_int", nullptr}, {"ref_id", nullptr}, {"ref_resolved", false}};

    if (strategy == "new") {
        new_body["use"] = PRO_BODY_USE_NEW;
        new_body["use_name"] = "new";
        ProElement use_elem = nullptr;
        try {
            use_elem = get_path(body_elem, {PRO_E_BODY_USE});
        } catch (ProError) {
            use_elem = nullptr;
        }
        try {
            if (use_elem)
                CK(ProElementIntegerSet(use_elem, PRO_BODY_USE_NEW));
            else
                integer(body_elem, PRO_E_BODY_USE, PRO_BODY_USE_NEW);
        } catch (ProError pe) {
            fail("write_body_use",
                 "FEAT070_WRITE_USE_FAILED: could not set PRO_E_BODY_USE (code " +
                     std::to_string(pe) + ")",
                 {{"new_body", new_body}});
        }
    } else {
        bool has_solid = state.is_object() && state.value("has_solid", false);
        if (!has_solid)
            fail("resolve_body",
                 "FEAT070_NO_SOLID_BODY: strategy '" + strategy +
                     "' requires a solid body but this part has none; use body_strategy='new'",
                 {{"new_body", new_body}});
        try {
            if (strategy == "existing")
                target_sel = resolve({{"kind", "body"}});
            else {
                int bid = op.value("body_id", -1);
                if (bid < 0)
                    fail("resolve_body",
                         "FEAT070_MISSING_BODY_ID: body_strategy='body_id' requires body_id",
                         {{"new_body", new_body}});
                require_scopable_body(bid);
                target_sel = resolve({{"kind", "body"}, {"id", bid}});
            }
        } catch (ProError pe) {
            fail("resolve_body",
                 "FEAT070_RESOLVE_BODY_FAILED: could not resolve target body (code " +
                     std::to_string(pe) + ")",
                 {{"new_body", new_body}});
        } catch (const std::runtime_error &) {
            throw; // require_scopable_body already carries a clear message
        }
        // NOTE: local is named body_ref (not ref) to avoid shadowing the
        // geometry.cpp helper ref(ProElement, int, ProSelection) used below.
        ProReference body_ref = nullptr;
        ProError rc = ProSelectionToReference(target_sel, &body_ref);
        if (rc != PRO_TK_NO_ERROR || !body_ref) {
            fail("resolve_body",
                 "FEAT070_BODY_REF_FAILED: resolved body selection is not a usable reference "
                 "(code " +
                     std::to_string((int)rc) + ")",
                 {{"new_body", new_body}});
        }
        ProType rtype = PRO_TYPE_UNUSED;
        int rid = -1;
        ProError tc = ProReferenceTypeGet(body_ref, &rtype);
        ProError ic = ProReferenceIdGet(body_ref, &rid);
        if (tc != PRO_TK_NO_ERROR || rtype != PRO_BODY) {
            ProReferenceFree(&body_ref);
            fail("resolve_body",
                 "FEAT070_BODY_NOT_BODY: resolved reference is not a body (type=" +
                     std::to_string(tc == PRO_TK_NO_ERROR ? (int)rtype : -1) + ")",
                 {{"new_body", new_body}});
        }
        new_body["use"] = PRO_BODY_USE_SELECTED;
        new_body["use_name"] = "selected";
        new_body["ref_type_int"] = (int)rtype;
        new_body["ref_id"] = rid;
        new_body["ref_resolved"] = true;

        try {
            ProElement use_elem = nullptr;
            try {
                use_elem = get_path(body_elem, {PRO_E_BODY_USE});
            } catch (ProError) {
                use_elem = nullptr;
            }
            if (use_elem)
                CK(ProElementIntegerSet(use_elem, PRO_BODY_USE_SELECTED));
            else
                integer(body_elem, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
            ProElement select_elem = nullptr;
            try {
                select_elem = get_path(body_elem, {PRO_E_BODY_SELECT});
            } catch (ProError) {
                select_elem = nullptr;
            }
            if (select_elem)
                CK(ProElementReferenceSet(select_elem, body_ref));
            else
                ref(body_elem, PRO_E_BODY_SELECT, target_sel);
        } catch (ProError pe) {
            ProReferenceFree(&body_ref);
            fail("write_body_ref",
                 "FEAT070_WRITE_REF_FAILED: could not rewrite PRO_E_BODY_SELECT (code " +
                     std::to_string(pe) + ")",
                 {{"new_body", new_body}});
        }
        ProReferenceFree(&body_ref);
    }

    // Mirror the repo's redefine() helper: ProFeatureWithoptionsRedefine must
    // receive an allocated options array (PRO_FEAT_CR_NO_OPTS) and a real
    // ProErrorlist; passing nullptr for either dereferences null in the SDK
    // and crashes the worker (observed 2026-11-20 on Creo 10 / release 42).
    ProFeatureCreateOptions *rd_opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&rd_opts));
    rd_opts[0] = PRO_FEAT_CR_NO_OPTS;
    ProErrorlist rd_errors = {};
    log("FEAT070 redefine feature=%d strategy=%s\n", fid, strategy.c_str());
    ProError redefine_code =
        ProFeatureWithoptionsRedefine(nullptr, &f, tree, rd_opts, PRO_REGEN_NO_FLAGS, &rd_errors);
    errors(rd_errors);
    ProArrayFree((ProArray *)&rd_opts);
    free_tree();
    free_sel();
    log("FEAT070 redefine_code=%d\n", (int)redefine_code);
    if (redefine_code != PRO_TK_NO_ERROR) {
        stage_operation_result({{"phase", "redefine"},
                                {"feature_id", fid},
                                {"feature_name", feature_name},
                                {"old_body", old_body},
                                {"new_body", new_body},
                                {"redefine_code", (int)redefine_code},
                                {"feature_incomplete", true},
                                {"body_counts_before", before["body_counts"]},
                                {"volume_before_mm3", before["volume_mm3"]}});
        throw std::runtime_error(
            "FEAT070_REDEFINE_FAILED: ProFeatureWithoptionsRedefine returned code " +
            std::to_string((int)redefine_code) + " for feature " + std::to_string(fid) +
            "; the model has been rolled back");
    }

    log("FEAT070 regenerate feature=%d\n", fid);
    ProError regenerate_code = ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS);
    log("FEAT070 regenerate_code=%d\n", (int)regenerate_code);
    ProBoolean incomplete = PRO_B_TRUE;
    ProFeatureIsIncomplete(&f, &incomplete);
    bool feature_incomplete = (incomplete == PRO_B_TRUE);
    if (regenerate_code != PRO_TK_NO_ERROR || feature_incomplete) {
        J after = feat070_snapshot();
        stage_operation_result({{"phase", "regenerate"},
                                {"feature_id", fid},
                                {"feature_name", feature_name},
                                {"old_body", old_body},
                                {"new_body", new_body},
                                {"redefine_code", (int)redefine_code},
                                {"regenerate_code", (int)regenerate_code},
                                {"feature_incomplete", feature_incomplete},
                                {"body_counts_before", before["body_counts"]},
                                {"body_counts_after", after["body_counts"]},
                                {"volume_before_mm3", before["volume_mm3"]},
                                {"volume_after_mm3", after["volume_mm3"]}});
        throw std::runtime_error("FEAT070_REGENERATE_FAILED: ProSolidRegenerate returned code " +
                                 std::to_string((int)regenerate_code) +
                                 (feature_incomplete ? " and the feature remains incomplete" : "") +
                                 "; the model has been rolled back");
    }

    J after = feat070_snapshot();
    return {
        {"feature_id", fid},
        {"feature_name", feature_name},
        {"old_body", old_body},
        {"new_body", new_body},
        {"redefine_code", (int)redefine_code},
        {"regenerate_code", (int)regenerate_code},
        {"feature_incomplete", feature_incomplete},
        {"body_counts_before", before["body_counts"]},
        {"body_counts_after", after["body_counts"]},
        {"volume_before_mm3", before["volume_mm3"]},
        {"volume_after_mm3", after["volume_mm3"]},
    };
}
// DEV-100 (§8): ensure the target sketch carries a construction centerline
// collinear with axis={kind:"sketch_points",start_mm,end_mm}. Existing solid
// boundary lines stay untouched so closed profiles remain closed.
static void ensure_revolve_sketch_centerline(const J &op, ProFeature &sketch_f) {
    if (!op.contains("axis") || !op["axis"].is_object() ||
        op["axis"].value("kind", "") != "sketch_points")
        return;
    const J *meta =
        op["sketch"].is_string() ? alias_entry(op["sketch"].get<std::string>()) : nullptr;
    if (!meta || !meta->contains("origin") || !meta->contains("u_axis") ||
        !meta->contains("v_axis"))
        throw std::runtime_error(
            "Revolve axis kind 'sketch_points' requires a sketch label with stored frame metadata; "
            "pass a sketch label or use an explicit datum_axis_feature");
    ProElement root = nullptr;
    CK(ProFeatureElemtreeExtract(&sketch_f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
    try {
        J saved_path = meta->value("section_path", J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER}));
        ProElement sk = get_path(root, saved_path);
        ProSection section = nullptr;
        CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&section));
        CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
        ProMatrix loc;
        CK(ProSectionLocationGet(section, loc));
        V origin = vec((*meta)["origin"]);
        V u_axis = vec((*meta)["u_axis"]);
        V v_axis = vec((*meta)["v_axis"]);
        V normal = meta->contains("normal") ? vec((*meta)["normal"]) : V{0.0, 0.0, 1.0};
        bool loc_is_identity = true;
        for (int row = 0; row < 4 && loc_is_identity; row++)
            for (int col = 0; col < 4 && loc_is_identity; col++)
                if (fabs(loc[row][col] - (row == col ? 1.0 : 0.0)) > 1e-12)
                    loc_is_identity = false;
        const bool identity_plausible = fabs(normal[0]) < 1e-9 && fabs(normal[1]) < 1e-9 &&
                                        fabs(normal[2] - 1.0) < 1e-9 && fabs(origin[0]) < 1e-9 &&
                                        fabs(origin[1]) < 1e-9 && fabs(origin[2]) < 1e-9;
        const bool use_frame_basis = loc_is_identity && !identity_plausible;
        double target_pts[2][2];
        const J pt_specs[2] = {op["axis"]["start_mm"], op["axis"]["end_mm"]};
        for (int p_idx = 0; p_idx < 2; p_idx++) {
            double u_val = pt_specs[p_idx][0].get<double>();
            double v_val = pt_specs[p_idx][1].get<double>();
            if (use_frame_basis) {
                target_pts[p_idx][0] = u_val;
                target_pts[p_idx][1] = v_val;
            } else {
                V w = add(origin, add(scale(u_axis, u_val), scale(v_axis, v_val)));
                for (int i = 0; i < 2; i++)
                    target_pts[p_idx][i] = (w[0] - loc[3][0]) * loc[i][0] +
                                           (w[1] - loc[3][1]) * loc[i][1] +
                                           (w[2] - loc[3][2]) * loc[i][2];
            }
        }
        double tdx = target_pts[1][0] - target_pts[0][0];
        double tdy = target_pts[1][1] - target_pts[0][1];
        double tlen = hypot(tdx, tdy);
        if (tlen < 1e-9)
            throw std::runtime_error("Projected sketch_points revolve axis is degenerate");

        std::set<int> known_user_centerlines;
        if (meta->contains("entity_ids") && meta->contains("geometry")) {
            const J &record_ids = meta->at("entity_ids");
            for (const J &e : meta->at("geometry"))
                if (e.is_object() && e.value("type", "") == "centerline" && e.contains("name") &&
                    record_ids.contains(e.at("name").get<std::string>()))
                    known_user_centerlines.insert(
                        record_ids.at(e.at("name").get<std::string>()).get<int>());
        }
        if (meta->contains("revolve_centerline_id") &&
            meta->at("revolve_centerline_id").is_number_integer())
            known_user_centerlines.insert(meta->at("revolve_centerline_id").get<int>());

        int existing_centerlines = 0;
        bool collinear_found = false;
        for (int cl_ent_id : known_user_centerlines) {
            Pro2dEntdef *def = nullptr;
            if (ProSectionEntityGet(section, cl_ent_id, &def) != PRO_TK_NO_ERROR || !def)
                continue;
            if (def->type != PRO_2D_CENTER_LINE)
                continue;
            existing_centerlines++;
            auto *line = (Pro2dLinedef *)def;
            double d1 = fabs((line->end1[0] - target_pts[0][0]) * tdy -
                             (line->end1[1] - target_pts[0][1]) * tdx) /
                        tlen;
            double d2 = fabs((line->end2[0] - target_pts[0][0]) * tdy -
                             (line->end2[1] - target_pts[0][1]) * tdx) /
                        tlen;
            if (d1 <= 1e-6 && d2 <= 1e-6)
                collinear_found = true;
        }

        if (existing_centerlines == 1 && collinear_found) {
            log("REVOLVE_SKETCH_POINTS_CENTERLINE=reused\n");
            CK(ProFeatureElemtreeFree(&sketch_f, root));
            return;
        }
        if (existing_centerlines > 0)
            throw std::runtime_error(
                "Revolve sketch_points axis conflicts with an existing construction centerline "
                "in the sketch; omit axis to use the existing centerline or use an explicit "
                "datum_axis_feature");

        Pro2dLinedef cl = {};
        cl.type = PRO_2D_CENTER_LINE;
        cl.end1[0] = target_pts[0][0];
        cl.end1[1] = target_pts[0][1];
        cl.end2[0] = target_pts[1][0];
        cl.end2[1] = target_pts[1][1];
        int cl_id = -1;
        CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&cl, &cl_id));
        solve_profile(section, J{{"dimensioning", "autodim"}});
        CK(ProElementSpecialvalueSet(sk, (ProAppData)section));
        redefine(&sketch_f, root);
        CK(ProFeatureElemtreeFree(&sketch_f, root));
        aliases[op["sketch"].get<std::string>()]["revolve_centerline_id"] = cl_id;
        log("REVOLVE_SKETCH_POINTS_CENTERLINE=added id=%d end1=%.9f,%.9f end2=%.9f,%.9f\n", cl_id,
            cl.end1[0], cl.end1[1], cl.end2[0], cl.end2[1]);
    } catch (...) {
        ProFeatureElemtreeFree(&sketch_f, root);
        throw;
    }
}

static J extrude_or_revolve(const J &op, bool revolve) {
    if (revolve)
        validate_revolve_axis(op);
    ProFeature sketch_f = feature(op.at("sketch"));
    const bool sketch_points_axis = revolve && op.contains("axis") && op["axis"].is_object() &&
                                    op["axis"].value("kind", "") == "sketch_points";
    if (sketch_points_axis)
        ensure_revolve_sketch_centerline(op, sketch_f);
    bool cut = op.value("mode", "add") == "cut";
    double before_volume = cut ? volume() : 0.0;
    // B4/F08: the non-target comparison needs the state before the feature
    // exists; captured only for a scoped cut so unscoped plans pay nothing.
    J bodies_before = cut && op.contains("scope") ? body_fingerprints() : J(nullptr);
    ProSelection s = selection(sketch_f.id, PRO_FEATURE);
    std::string mode = op.value("mode", "add"), direction = op.value("direction", "positive");
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE,
            mode == "cut"       ? PRO_FEAT_CUT
            : mode == "surface" ? PRO_FEAT_DATUM_SURF
                                : PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, revolve ? PRO_REVOLVE : PRO_EXTRUDE);
    integer(root, PRO_E_EXT_SURF_CUT_SOLID_TYPE,
            mode == "surface" ? PRO_EXT_FEAT_TYPE_SURFACE : PRO_EXT_FEAT_TYPE_SOLID);
    integer(root, PRO_E_REMOVE_MATERIAL,
            mode == "cut" ? PRO_EXT_MATERIAL_REMOVE : PRO_EXT_MATERIAL_ADD);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ref(node(root, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, s);
    ProSelectionFree(&s);
    if (mode != "surface")
        body_options(root, op);
    int sign = 1;
    if (op["sketch"].is_string()) {
        if (const J *entry = alias_entry(op["sketch"].get<std::string>()))
            sign = entry->value("section_normal_sign", 1);
    }
    if (direction == "negative")
        sign = -sign;
    log("DIRECTION_SIGN=%d\n", sign);
    integer(root, PRO_E_STD_DIRECTION, sign > 0 ? 1 : -1);
    if (op.contains("thin")) {
        integer(root, PRO_E_FEAT_FORM_IS_THIN,
                revolve ? PRO_REV_FEAT_FORM_THIN : PRO_EXT_FEAT_FORM_THIN);
        real(root, PRO_E_THICKNESS, op["thin"]);
        integer(root, PRO_E_STD_MATRLSIDE,
                revolve ? PRO_REV_MATERIAL_BOTH_SIDES : PRO_EXT_MATERIAL_BOTH_SIDES);
    }
    // FEAT-008/T09B: keep the resolved axis identity for the result report.
    int revolve_axis_id = -1;
    ProError revolve_axis_code = PRO_TK_NO_ERROR;
    if (revolve) {
        if (op.contains("axis") && !sketch_points_axis) {
            integer(root, PRO_E_REVOLVE_AXIS_OPT, PRO_REV_AXIS_EXT_REF);
            ProSelection a = resolve(op["axis"]);
            ProModelitem axis_item = {};
            revolve_axis_code = ProSelectionModelitemGet(a, &axis_item);
            if (!revolve_axis_code && axis_item.type == PRO_AXIS)
                revolve_axis_id = axis_item.id;
            ref(root, PRO_E_REVOLVE_AXIS, a);
            ProSelectionFree(&a);
            // DEV-093 T4: stage the measured axis/plane relation before the
            // kernel sees the feature, so a regeneration refusal still carries
            // the numbers in its operation record.
            J staged = has_staged_operation_result ? staged_operation_result : J::object();
            staged["revolve_axis_plane_relation"] =
                revolve_axis_plane_relation(op, revolve_axis_id, revolve_axis_code);
            stage_operation_result(staged);
        } else
            integer(root, PRO_E_REVOLVE_AXIS_OPT, PRO_REV_AXIS_INT_REF);
        ProElement angles = node(root, PRO_E_REV_ANGLE), from = node(angles, PRO_E_REV_ANGLE_FROM),
                   to = node(angles, PRO_E_REV_ANGLE_TO);
        integer(from, PRO_E_REV_ANGLE_FROM_TYPE, PRO_REV_ANG_FROM_NONE);
        integer(to, PRO_E_REV_ANGLE_TO_TYPE,
                direction == "symmetric" ? PRO_REV_ANG_SYMMETRIC : PRO_REV_ANG_TO_ANGLE);
        real(to, PRO_E_REV_ANGLE_TO_VAL, op.value("angle", 360.0));
    } else {
        ProElement dep = node(root, PRO_E_STD_EXT_DEPTH), from = node(dep, PRO_E_EXT_DEPTH_FROM),
                   to = node(dep, PRO_E_EXT_DEPTH_TO);
        bool through_all = op.value("depth_type", "blind") == "through_all";
        // A symmetric through-all cut must pierce both directions; TO_ALL with
        // FROM_NONE only removes material on one side (measured as half the
        // expected volume in the T05 acceptance matrix).
        integer(from, PRO_E_EXT_DEPTH_FROM_TYPE,
                through_all && direction == "symmetric" ? PRO_EXT_DEPTH_FROM_ALL
                                                        : PRO_EXT_DEPTH_FROM_NONE);
        integer(to, PRO_E_EXT_DEPTH_TO_TYPE,
                through_all                ? PRO_EXT_DEPTH_TO_ALL
                : direction == "symmetric" ? PRO_EXT_DEPTH_SYMMETRIC
                                           : PRO_EXT_DEPTH_TO_BLIND);
        if (!through_all)
            real(to, PRO_E_EXT_DEPTH_TO_VALUE, op.value("depth", 1.0));
    }
    auto capture_failed_section = [&]() {
        J section = {{"available", false}};
        ProSection saved = nullptr;
        ProError copy_code = ProFeatureSectionCopy(&sketch_f, 0, &saved);
        if (!copy_code) {
            section = section_profile_summary(saved, "feature_create_failure");
            ProSectionFree(&saved);
        } else
            section["query_code"] = copy_code;
        J staged = has_staged_operation_result ? staged_operation_result : J::object();
        staged["native_section"] = section;
        stage_operation_result(staged);
        return section;
    };
    ProFeature f = {};
    try {
        f = create(root);
    } catch (ProError error) {
        ProElementFree(&root);
        if (last_toolkit_error != "ProFeatureWithoptionsCreate")
            throw;
        J section = capture_failed_section();
        throw std::runtime_error(section_create_failure(op, revolve, error, section));
    } catch (const std::runtime_error &err) {
        ProElementFree(&root);
        J section = capture_failed_section();
        if (section.value("available", false) && section.value("open_ends", 0) > 0) {
            throw std::runtime_error(std::string(err.what()) + ". " +
                                     section_create_failure(op, revolve, PRO_TK_NO_ERROR, section));
        }
        throw;
    }
    CK(ProElementFree(&root));
    {
        ProFeatStatus created_status = PRO_FEAT_ACTIVE;
        if (ProFeatureStatusGet(&f, &created_status) == PRO_TK_NO_ERROR &&
            created_status != PRO_FEAT_ACTIVE) {
            J section = capture_failed_section();
            if (section.value("available", false) && section.value("open_ends", 0) > 0)
                throw std::runtime_error(
                    section_create_failure(op, revolve, PRO_TK_GENERAL_ERROR, section));
        }
    }
    remember(op, f);
    J details = {{"feature_id", f.id}};
    if (revolve) {
        details["revolve_axis"] =
            revolve_axis_report(op, f, sketch_f, revolve_axis_id, revolve_axis_code);
        if (op.contains("angle_clamped_from_deg") && op["angle_clamped_from_deg"].is_number())
            details["angle_clamped_from_deg"] = op["angle_clamped_from_deg"];
    } else
        details["extrude_depth"] = extrude_depth_report(f, op);
    if (!revolve && op.contains("scope")) {
        details["scope_applied"] = scope_applied_report(op, f, bodies_before);
        const J &applied = details["scope_applied"];
        // The receipt is evidence, not a formality: a scope the created feature
        // does not carry (unreadable element, "all bodies", or a different id)
        // must fail instead of reporting success for geometry it never scoped.
        bool resolved = applied["query_code"] == PRO_TK_NO_ERROR &&
                        applied["applied_body_ids"].is_array() &&
                        applied["applied_body_ids"] == op.at("scope").at("body_ids");
        if (!resolved) {
            J staged = has_staged_operation_result ? staged_operation_result : J::object();
            staged["scope_applied"] = applied;
            stage_operation_result(staged);
            throw std::runtime_error(
                "F08_SCOPE_RESOLVE_FAILED: the created feature does not carry the requested "
                "scope.body_ids; see scope_applied in the operation result and "
                "creo_capabilities known_limitations.cut_scope");
        }
        const J &unchanged = applied["non_target_bodies_unchanged"];
        if (unchanged.is_boolean() && !unchanged.get<bool>()) {
            J staged = has_staged_operation_result ? staged_operation_result : J::object();
            staged["scope_applied"] = applied;
            stage_operation_result(staged);
            throw std::runtime_error(
                "F08_SCOPE_NON_TARGET_CHANGED: a body outside scope.body_ids changed; the cut "
                "touched geometry it was told to leave alone");
        }
    }
    if (cut) {
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
        double after_volume = volume();
        double removed = before_volume - after_volume;
        log("CUT_MATERIAL_REMOVED_MM3=%.12f\n", removed);
        double threshold = std::max(1e-9, fabs(before_volume) * 1e-12);
        if (removed <= threshold) {
            J depth_report = revolve ? J::object() : details["extrude_depth"];
            J context = cut_geometry_context(op, revolve, sign, before_volume, after_volume,
                                             removed, threshold, depth_report, sketch_f);
            J staged = has_staged_operation_result ? staged_operation_result : J::object();
            staged["cut_geometry_context"] = context;
            stage_operation_result(staged);
            throw std::runtime_error(cut_no_material_failure(revolve, context));
        }
        details["material_removed_mm3"] = removed;
        ProSection cut_sec = nullptr;
        if (ProFeatureSectionCopy(&sketch_f, 0, &cut_sec) == PRO_TK_NO_ERROR) {
            J sec_summary;
            try {
                sec_summary = section_profile_summary(cut_sec, "cut_success");
            } catch (...) {
                ProSectionFree(&cut_sec);
                throw;
            }
            CK(ProSectionFree(&cut_sec));
            details["solved_section_area_mm2"] =
                sec_summary.value("solved_section_area_mm2", J(nullptr));
            J compact_sec = J::object();
            for (const char *key : {"available", "b_spline_entities", "closed_contours",
                                    "open_ends", "solved_section_area_mm2"})
                if (sec_summary.contains(key))
                    compact_sec[key] = sec_summary[key];
            details["native_section"] = std::move(compact_sec);
        }
    }
    int active = active_body_count();
    if (active == 1 && !op.value("skip_empty_body_cleanup", false))
        remove_empty_body();
    return details;
}
static bool hole_plane_normal(ProSelection selection, V &normal, const char *role) {
    ProModelitem item;
    CK(ProSelectionModelitemGet(selection, &item));
    if (item.type != PRO_SURFACE)
        return false; // Edge/axis references retain Toolkit's own validation.
    ProSurface surface;
    CK(ProSurfaceInit((ProSolid)board, item.id, &surface));
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(surface, &data));
    bool planar =
        data && data->data.p_surface_data && data->data.p_surface_data->type == PRO_SRF_PLANE;
    if (planar) {
        const auto &plane = data->data.p_surface_data->srf_shape.plane;
        normal = {plane.e3[0], plane.e3[1], plane.e3[2]};
    }
    if (data)
        CK(ProGeomitemdataFree(&data));
    if (!planar)
        throw std::runtime_error(std::string("Linear hole ") + role +
                                 " must be planar; use a plane/straight edge reference");
    normal = normalized(normal);
    return true;
}
static void validate_hole_planes(ProSelection face, ProSelection first, ProSelection second) {
    V primary, normals[2];
    if (!hole_plane_normal(face, primary, "placement"))
        throw std::runtime_error("Linear hole placement must be a planar surface or datum plane");
    bool planar[2] = {hole_plane_normal(first, normals[0], "reference1"),
                      hole_plane_normal(second, normals[1], "reference2")};
    ProSelection references[] = {first, second};
    for (int i = 0; i < 2; ++i) {
        ProModelitem item;
        CK(ProSelectionModelitemGet(references[i], &item));
        if (item.type == PRO_EDGE) {
            ProEdge edge;
            CK(ProEdgeInit((ProSolid)board, item.id, &edge));
            ProGeomitemdata *data = nullptr;
            CK(ProEdgeDataGet(edge, &data));
            Pro3dPnt start, end;
            ProError line = ProLinedataGet(data->data.p_curve_data, start, end);
            CK(ProGeomitemdataFree(&data));
            if (line)
                throw std::runtime_error("Linear hole requires straight edge references");
            V direction = normalized(add(vec(xyz(end)), scale(vec(xyz(start)), -1)));
            if (fabs(dot(primary, direction)) > 1e-7)
                throw std::runtime_error("Hole edge references must lie in the placement plane");
            normals[i] = normalized(cross(primary, direction));
            planar[i] = true;
        }
        if (!planar[i])
            continue;
        V projected = add(normals[i], scale(primary, -dot(primary, normals[i])));
        if (dot(projected, projected) < 1e-14)
            throw std::runtime_error(
                "Hole reference" + std::to_string(i + 1) +
                " is parallel to placement; choose a plane crossing the placement plane");
        normals[i] = normalized(projected);
    }
    if (planar[0] && planar[1] && fabs(dot(normals[0], normals[1])) > 1 - 1e-7)
        throw std::runtime_error(
            "Hole secondary references do not provide independent location constraints");
}
static void seed_hole_edge_selections(ProSelection &face, ProSelection &first,
                                      ProSelection &second) {
    ProModelitem refs[2];
    CK(ProSelectionModelitemGet(first, &refs[0]));
    CK(ProSelectionModelitemGet(second, &refs[1]));
    if (refs[0].type != PRO_EDGE && refs[1].type != PRO_EDGE)
        return;
    ProModelitem primary;
    CK(ProSelectionModelitemGet(face, &primary));
    ProSurface surface;
    CK(ProSurfaceInit((ProSolid)board, primary.id, &surface));
    ProGeomitemdata *data = nullptr;
    CK(ProSurfaceDataGet(surface, &data));
    V origin = vec(xyz(data->data.p_surface_data->srf_shape.plane.origin));
    V normal = normalized(vec(xyz(data->data.p_surface_data->srf_shape.plane.e3)));
    ProPoint3d pick;
    for (int i = 0; i < 3; ++i)
        pick[i] =
            (data->data.p_surface_data->xyz_min[i] + data->data.p_surface_data->xyz_max[i]) / 2;
    CK(ProGeomitemdataFree(&data));
    CK(ProSelectionPoint3dSet(pick, &face));
    ProUvParam uv;
    CK(ProSurfaceParamEval((ProSolid)board, surface, pick, uv));
    CK(ProSelectionUvParamSet(face, uv));
    // Creo uses the selected points to choose the signed side of edge-derived planes.
    // An ID-only selection can choose an outward side on an identical later request.
    log("HOLE_PLACEMENT_PICK=%.9f,%.9f,%.9f\n", pick[0], pick[1], pick[2]);
    ProSelection *selections[] = {&first, &second};
    for (int i = 0; i < 2; ++i) {
        if (refs[i].type != PRO_EDGE)
            continue;
        ProEdge edge;
        CK(ProEdgeInit((ProSolid)board, refs[i].id, &edge));
        ProVector derivative, second_derivative, direction;
        CK(ProEdgeXyzdataEval(edge, 0.5, pick, derivative, second_derivative, direction));
        if (fabs(dot(add(vec(xyz(pick)), scale(origin, -1)), normal)) > 1e-6)
            throw std::runtime_error("Hole edge references must lie in the placement plane");
        CK(ProSelectionPoint3dSet(pick, selections[i]));
    }
}
// Declared before use: the non-throwing tree walker is defined further down,
// after the round/chamfer/draft readbacks that share it.
static ProElement get_optional(ProElement root, std::initializer_list<int> ids, ProError *code);
// FEAT-035 increment: since 0.10.0 a custom blind hole dimensions its depth to
// the drill tip (PRO_HLE_DEP_TIP_DIM_SCHEME), but that basis only lived in the
// release notes, so a stored plan replayed on an older build silently becomes
// shallower. Read the scheme back from the created feature tree; a plain
// straight hole uses a different element path, so it legitimately reports
// null rather than a guessed basis.
static J hole_depth_basis_json(ProFeature &f) {
    J block = {{"depth_basis", nullptr},
               {"depth_scheme_code", nullptr},
               {"depth_scheme_query", "PRO_E_HLE_DEPTH_DIM_TYPE"},
               {"query_code", nullptr}};
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    block["query_code"] = (int)code;
    if (code != PRO_TK_NO_ERROR)
        return block;
    ProElement scheme = get_optional(tree, {PRO_E_HLE_COM, PRO_E_HLE_DEPTH_DIM_TYPE}, &code);
    if (code == PRO_TK_NO_ERROR && scheme) {
        int value = 0;
        if (!ProElementIntegerGet(scheme, nullptr, &value)) {
            block["depth_scheme_code"] = value;
            block["depth_basis"] = value == PRO_HLE_DEP_TIP_DIM_SCHEME ? "tip" : "not_tip";
        }
    }
    ProFeatureElemtreeFree(&f, tree);
    return block;
}
// FEAT-035 standard hole: the request is not evidence. Read the thread back
// from the hole feature Creo actually built, after regeneration, and report
// null when the element is missing instead of echoing the input. Element ids
// come from ProHole.h: the depth VALUE is PRO_E_HLE_THRDDEPTH (double), while
// PRO_E_HLE_THRD_DEPTH is its type enum; PRO_E_THREAD_DEPTH belongs to the
// cosmetic thread feature and says nothing about a hole.
static std::string narrow(const wchar_t *text) {
    if (!text)
        return std::string();
    int size = WideCharToMultiByte(CP_UTF8, 0, text, -1, nullptr, 0, nullptr, nullptr);
    if (size <= 1)
        return std::string();
    std::string out((size_t)size - 1, '\0');
    WideCharToMultiByte(CP_UTF8, 0, text, -1, out.data(), size, nullptr, nullptr);
    return out;
}
// The installed hole chart names a size by its fastener id ("M6x1" for ISO
// coarse M6), never by the nominal "M6" the frozen table exposes. The resolved
// id travels with the operation, and the chart itself still has the final say:
// an unknown id comes back as PRO_TK_INVALID_NAME from the setter.
static std::string std_hole_fastener_id(const J &op) {
    const J &standard = op["standard"];
    if (standard.contains("fastener_id") && standard["fastener_id"].is_string())
        return standard["fastener_id"].get<std::string>();
    return standard.at("size").get<std::string>();
}
static J hole_thread_json(ProFeature &f, const J &op) {
    J block = {{"add_thread", nullptr},
               {"thread_depth_mm", nullptr},
               {"thread_depth_type", nullptr},
               {"thread_series", nullptr},
               {"screw_size", nullptr},
               {"standard_type", nullptr},
               {"requested_thread_depth_mm", op["standard"].at("thread_depth")},
               {"requested_fastener_id", std_hole_fastener_id(op)},
               {"verified", false},
               {"query_code", nullptr}};
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    block["query_code"] = (int)code;
    if (code != PRO_TK_NO_ERROR)
        return block;
    ProError com_code = PRO_TK_NO_ERROR;
    ProElement com = get_optional(tree, {PRO_E_HLE_COM}, &com_code);
    if (com_code == PRO_TK_NO_ERROR && com) {
        const struct {
            const char *key;
            int id;
        } ints[] = {{"add_thread", PRO_E_HLE_ADD_THREAD},
                    {"thread_depth_type", PRO_E_HLE_THRD_DEPTH},
                    {"thread_series", PRO_E_HLE_THRDSERIS},
                    {"screw_size", PRO_E_HLE_SCREWSIZE},
                    {"standard_type", PRO_E_HLE_STAN_TYPE}};
        for (const auto &item : ints) {
            ProError c = PRO_TK_NO_ERROR;
            ProElement elem = get_optional(com, {item.id}, &c);
            if (c != PRO_TK_NO_ERROR || !elem)
                continue;
            int value = 0;
            if (!ProElementIntegerGet(elem, nullptr, &value))
                block[item.key] = value;
        }
        ProError depth_code = PRO_TK_NO_ERROR;
        ProElement depth = get_optional(com, {PRO_E_HLE_THRDDEPTH}, &depth_code);
        if (depth_code == PRO_TK_NO_ERROR && depth) {
            double value = 0.0;
            if (!ProElementDoubleGet(depth, nullptr, &value))
                block["thread_depth_mm"] = value;
        }
    }
    // Names, not indices: the chart decides what "ISO"/"M6" mean, so the
    // receipt carries the names Creo resolved rather than our raw ints.
    wchar_t *series_name = nullptr;
    ProError series_name_code = ProElementHoleThreadSeriesGet(tree, (ProMdl)board, &series_name);
    block["thread_series_name_query_code"] = (int)series_name_code;
    if (series_name_code == PRO_TK_NO_ERROR && series_name) {
        block["thread_series_name"] = narrow(series_name);
        ProWstringFree(series_name);
    }
    wchar_t *size_name = nullptr;
    ProError size_name_code = ProElementHoleScrewSizeGet(tree, (ProMdl)board, &size_name);
    block["screw_size_name_query_code"] = (int)size_name_code;
    if (size_name_code == PRO_TK_NO_ERROR && size_name) {
        block["screw_size_name"] = narrow(size_name);
        ProWstringFree(size_name);
    }
    // Fallback: Creo may relocate the depth into another subnode, so keep the
    // tree ids in the native log and take a relocated depth when the direct
    // path was empty. A silent miss stays null instead of echoing the request.
    struct ScanState {
        bool relocated = false;
        double depth = 0.0;
        std::vector<int> ids;
    } scan;
    if (!block["thread_depth_mm"].is_number()) {
        ProElemtreeElementVisit(
            tree, nullptr, nullptr,
            [](ProElement, ProElement elem, ProElempath, ProAppData data) -> ProError {
                auto *state = (ScanState *)data;
                ProElemId id = (ProElemId)0;
                if (ProElementIdGet(elem, &id))
                    return PRO_TK_NO_ERROR;
                if (state->ids.size() < 128)
                    state->ids.push_back((int)id);
                if ((int)id == PRO_E_HLE_THRDDEPTH) {
                    double value = 0.0;
                    if (!ProElementDoubleGet(elem, nullptr, &value)) {
                        state->relocated = true;
                        state->depth = value;
                    }
                }
                return PRO_TK_NO_ERROR;
            },
            &scan);
        if (scan.relocated)
            block["thread_depth_mm"] = scan.depth;
    }
    if (!scan.ids.empty()) {
        log("HOLE_THREAD_TREE_IDS");
        for (int id : scan.ids)
            log(" %d", id);
        log("\n");
    }
    double requested = op["standard"].at("thread_depth").get<double>();
    bool depth_ok = block["thread_depth_mm"].is_number() &&
                    fabs(block["thread_depth_mm"].get<double>() - requested) <= 1e-6;
    bool names_ok = block["thread_series_name"].is_string() &&
                    block["screw_size_name"].is_string() &&
                    block["thread_series_name"].get<std::string>() ==
                        op["standard"].at("series").get<std::string>() &&
                    block["screw_size_name"].get<std::string>() == std_hole_fastener_id(op);
    bool verified = block["add_thread"].is_number() &&
                    block["add_thread"].get<int>() == PRO_HLE_ADD_THREAD && depth_ok && names_ok;
    block["verified"] = verified;
    log("HOLE_THREAD add_thread=%s depth=%s requested=%.9f verified=%d\n",
        block["add_thread"].dump().c_str(), block["thread_depth_mm"].dump().c_str(), requested,
        (int)verified);
    ProFeatureElemtreeFree(&f, tree);
    return block;
}
// FEAT-035 standard tapped hole. ProHole.h Table Hole:2 makes the standard
// branch its own element tree: PRO_E_HLE_TYPE_NEW = STANDARD, a tapped stan
// type, chart-bound series/size, and the thread depth pair. The straight-hole
// tree accepts an ADD_THREAD flag but drops the depth, so a standard hole that
// borrowed it would only look threaded.
static void standard_hole_elements(ProElement com, ProElement root, const J &op) {
    const J &standard = op["standard"];
    // The prepared row carries the chart's tap drill; native never derives it
    // from the nominal diameter, which would drill the wrong hole.
    if (!standard.contains("tap_drill_mm") || !standard["tap_drill_mm"].is_number() ||
        !(standard["tap_drill_mm"].get<double>() > 0.0))
        throw std::runtime_error(
            "Standard hole requires the resolved hole-table tap drill diameter");
    double tap_drill = standard["tap_drill_mm"].get<double>();
    double thread_depth = standard.at("thread_depth").get<double>();
    integer(com, PRO_E_HLE_STAN_TYPE, PRO_HLE_TAPPED_TYPE);
    integer(com, PRO_E_HLE_FITTYPE, PRO_HLE_CLOSE_FIT);
    integer(com, PRO_E_HLE_ADD_THREAD, PRO_HLE_ADD_THREAD);
    integer(com, PRO_E_HLE_ADD_CBORE, PRO_HLE_NO_CBORE);
    integer(com, PRO_E_HLE_ADD_CSINK, PRO_HLE_NO_CSINK);
    integer(com, PRO_E_HLE_ADD_EXIT_CSINK, PRO_HLE_NO_EXIT_CSINK);
    real(com, PRO_E_HLE_HOLEDIAM, tap_drill);
    real(com, PRO_E_HLE_DRILLANGLE, 118.0);
    real(com, PRO_E_HLE_THRDDEPTH, thread_depth);
    integer(com, PRO_E_HLE_THRD_DEPTH, PRO_HLE_VARIABLE_THREAD);
    integer(com, PRO_E_HLE_DEPTH,
            op.contains("depth") ? PRO_HLE_STD_VAR_DEPTH : PRO_HLE_STD_THRU_ALL_DEPTH);
    if (op.contains("depth")) {
        real(com, PRO_E_HLE_DRILLDEPTH, op.at("depth"));
        integer(com, PRO_E_HLE_DEPTH_DIM_TYPE, PRO_HLE_DEP_SHOULDER_DIM_SCHEME);
    }
    // Chart-bound lookups: "M6x1" is the chart's fastener id, "M6" is not.
    integer(com, PRO_E_HLE_THRDSERIS, 0);
    integer(com, PRO_E_HLE_SCREWSIZE, 0);
    std::wstring series = wide(standard.at("series").get<std::string>());
    std::wstring fastener = wide(std_hole_fastener_id(op));
    ProError series_code = ProElementHoleThreadSeriesSet(root, (ProMdl)board, series.data());
    log("HOLE_THREAD_SERIES_SET name=%ls code=%d\n", series.c_str(), (int)series_code);
    if (series_code != PRO_TK_NO_ERROR)
        throw std::runtime_error(
            "Standard hole thread series " + standard.at("series").get<std::string>() +
            " is not in the installed hole chart (code " + std::to_string((int)series_code) + ")");
    ProError size_code = ProElementHoleScrewSizeSet(root, (ProMdl)board, fastener.data());
    log("HOLE_THREAD_SIZE_SET name=%ls code=%d\n", fastener.c_str(), (int)size_code);
    if (size_code != PRO_TK_NO_ERROR)
        throw std::runtime_error("Standard hole size " + std_hole_fastener_id(op) +
                                 " is not in the installed " +
                                 standard.at("series").get<std::string>() + " hole chart (code " +
                                 std::to_string((int)size_code) + ")");
}
static J generic_hole(const J &op) {
    double before_volume = volume();
    bool counterbore = op.contains("counterbore");
    bool countersink = op.contains("countersink");
    if (counterbore && countersink)
        throw std::runtime_error("Counterbore and countersink are mutually exclusive");
    bool custom = counterbore || countersink;
    bool standard = op.contains("standard") && !op["standard"].is_null();
    if (custom && standard)
        throw std::runtime_error("Standard threaded holes and custom holes are mutually exclusive");
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_HOLE);
    integer(root, PRO_E_FEATURE_FORM, PRO_HLE_TYPE_STRAIGHT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement com = node(root, PRO_E_HLE_COM);
    integer(com, PRO_E_HLE_TYPE_NEW,
            custom ? PRO_HLE_CUSTOM_TYPE
                   : (standard ? PRO_HLE_NEW_TYPE_STANDARD : PRO_HLE_NEW_TYPE_STRAIGHT));
    if (custom) {
        integer(com, PRO_E_HLE_ADD_CBORE, counterbore ? PRO_HLE_ADD_CBORE : PRO_HLE_NO_CBORE);
        integer(com, PRO_E_HLE_ADD_CSINK, countersink ? PRO_HLE_ADD_CSINK : PRO_HLE_NO_CSINK);
        real(com, PRO_E_HLE_HOLEDIAM, op.at("diameter"));
        integer(com, PRO_E_HLE_DEPTH,
                op.contains("depth") ? PRO_HLE_STD_VAR_DEPTH : PRO_HLE_STD_THRU_ALL_DEPTH);
        if (op.contains("depth")) {
            real(com, PRO_E_HLE_DRILLDEPTH, op.at("depth"));
            // FEAT-035/T12: the blind depth is the overall depth from the
            // placement face down to the drill tip, so the custom hole
            // dimensions till the tip. The plain straight-hole branch keeps
            // its own element tree and its flat-bottomed overall depth.
            integer(com, PRO_E_HLE_DEPTH_DIM_TYPE, PRO_HLE_DEP_TIP_DIM_SCHEME);
        }
        if (counterbore) {
            real(com, PRO_E_HLE_CBOREDIAM, op["counterbore"].at("diameter"));
            real(com, PRO_E_HLE_CBOREDEPTH, op["counterbore"].at("depth"));
        }
        if (countersink) {
            real(com, PRO_E_HLE_CSINKDIAM, op["countersink"].at("diameter"));
            real(com, PRO_E_HLE_CSINKANGLE, op["countersink"].at("angle"));
        }
    } else if (standard) {
        standard_hole_elements(com, root, op);
    } else {
        integer(com, PRO_E_HLE_MAKE_LIGHTWT, PRO_HLE_REGULAR);
        real(com, PRO_E_DIAMETER, op.at("diameter"));
        ProElement dep = node(com, PRO_E_HOLE_STD_DEPTH);
        ProElement to = node(dep, PRO_E_HOLE_DEPTH_TO);
        integer(to, PRO_E_HOLE_DEPTH_TO_TYPE,
                op.contains("depth") ? PRO_HLE_STRGHT_BLIND_DEPTH : PRO_HLE_STRGHT_THRU_ALL_DEPTH);
        if (op.contains("depth"))
            real(to, PRO_E_EXT_DEPTH_TO_VALUE, op.at("depth"));
        integer(node(dep, PRO_E_HOLE_DEPTH_FROM), PRO_E_HOLE_DEPTH_FROM_TYPE,
                PRO_HLE_STRGHT_NONE_DEPTH);
    }
    integer(com, PRO_E_HLE_CRDIR_FLIP,
            op.value("flip", false) ? PRO_HLE_CR_IN_SIDE_TWO : PRO_HLE_CR_IN_SIDE_ONE);
    integer(com, PRO_E_HLE_TOP_CLEARANCE, PRO_HOLE_GEN_CLRNCE);
#if defined(MECHDOG_HAS_PRO_E_HLE_ADD_PARAMETERS) &&                                               \
    defined(MECHDOG_HAS_PRO_HOLE_NO_PARAMETERS_FLAG)
    integer(com, PRO_E_HLE_ADD_PARAMETERS, PRO_HOLE_NO_PARAMETERS_FLAG);
#endif
    integer(com, PRO_E_HLE_ADD_NOTE, PRO_HOLE_NO_NOTE_FLAG);
    ProElement placement = node(root, PRO_E_HLE_PLACEMENT);
    ProSelection face = nullptr, r1 = nullptr, r2 = nullptr;
    try {
        face = resolve(op["placement"]);
        r1 = resolve(op["reference1"]);
        r2 = resolve(op["reference2"]);
        validate_hole_planes(face, r1, r2);
        seed_hole_edge_selections(face, r1, r2);
        ref(placement, PRO_E_HLE_PRIM_REF, face);
        integer(placement, PRO_E_HLE_PL_TYPE, PRO_HLE_PL_TYPE_LIN);
        ref(placement, PRO_E_HLE_DIM_REF1, r1);
        ref(placement, PRO_E_HLE_DIM_REF2, r2);
        double a = op.value("offset1", 0.0), b = op.value("offset2", 0.0);
        integer(placement, PRO_E_HLE_PLC_ALIGN_OPT1,
                a == 0 ? PRO_HLE_PLC_ALIGN : PRO_HLE_PLC_NOT_ALIGN);
        integer(placement, PRO_E_HLE_PLC_ALIGN_OPT2,
                b == 0 ? PRO_HLE_PLC_ALIGN : PRO_HLE_PLC_NOT_ALIGN);
        real(placement, PRO_E_HLE_DIM_DIST1, a);
        real(placement, PRO_E_HLE_DIM_DIST2, b);
        integer(node(root, PRO_E_BODY), PRO_E_BODY_USE, PRO_BODY_USE_ALL);
        ProFeature f = create(root);
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
        double removed = before_volume - volume();
        log("HOLE_MATERIAL_REMOVED_MM3=%.12f\n", removed);
        if (removed <= std::max(1e-9, fabs(before_volume) * 1e-12))
            throw std::runtime_error("Hole removes no material; check reference offsets, "
                                     "placement, flip and overlap with existing holes");
        J axes = J::array();
        J geometry = J::array();
        CK(ProFeatureGeomitemVisit(&f, PRO_AXIS, collect_geom_ids, nullptr, &axes));
        for (const auto &axis : axes) {
            ProGeomitem item;
            CK(ProModelitemInit(board, axis["id"], PRO_AXIS, &item));
            ProGeomitemdata *data = nullptr;
            CK(ProGeomitemdataGet(&item, &data));
            Pro3dPnt start, end;
            CK(ProLinedataGet(data->data.p_curve_data, start, end));
            log("HOLE_AXIS id=%d start=%.9f,%.9f,%.9f end=%.9f,%.9f,%.9f\n", axis["id"].get<int>(),
                start[0], start[1], start[2], end[0], end[1], end[2]);
            geometry.push_back({{"id", axis["id"]}, {"start", xyz(start)}, {"end", xyz(end)}});
            CK(ProGeomitemdataFree(&data));
        }
        CK(ProElementFree(&root));
        ProSelectionFree(&face);
        ProSelectionFree(&r1);
        ProSelectionFree(&r2);
        remember(op, f);
        J basis = hole_depth_basis_json(f);
        J out = {{"feature_id", f.id},
                 {"material_removed_mm3", removed},
                 {"axes", geometry},
                 {"depth_basis", basis["depth_basis"]},
                 {"depth_scheme_code", basis["depth_scheme_code"]},
                 {"depth_scheme_query", basis["depth_scheme_query"]}};
        // Plain holes keep their old receipt; only a standard hole carries the
        // readback of the thread Creo really stored. The frozen receipt keys
        // (thread_metadata/thread_metadata_verified) are composed in Python from
        // this evidence plus the table identity.
        if (op.contains("standard") && !op["standard"].is_null())
            out["thread_readback"] = hole_thread_json(f, op);
        return out;
    } catch (...) {
        if (face)
            ProSelectionFree(&face);
        if (r1)
            ProSelectionFree(&r1);
        if (r2)
            ProSelectionFree(&r2);
        if (root)
            ProElementFree(&root);
        throw;
    }
}
static void curve_collection_with_propagation(ProElement element, const J &refs,
                                              bool propagate_chain) {
    ProCollection coll;
    CK(ProCrvcollectionAlloc(&coll));
    for (auto item : refs) {
        ProSelection s = resolve(item);
        ProReference reference;
        CK(ProSelectionToReference(s, &reference));
        ProCrvcollinstr instr;
        CK(ProCrvcollinstrAlloc(PRO_CURVCOLL_ADD_ONE_INSTR, &instr));
        CK(ProCrvcollinstrReferenceAdd(instr, reference));
        CK(ProCrvcollectionInstructionAdd(coll, instr));
        CK(ProCrvcollinstrFree(instr));
        ProSelectionFree(&s);
    }
    if (propagate_chain) {
        ProCrvcollinstr tan_instr;
        CK(ProCrvcollinstrAlloc(PRO_CURVCOLL_ADD_TANGENT_INSTR, &tan_instr));
        CK(ProCrvcollectionInstructionAdd(coll, tan_instr));
        CK(ProCrvcollinstrFree(tan_instr));
    }
    CK(ProElementCollectionSet(element, coll));
    CK(ProCollectionFree(&coll));
}
static void curve_collection(ProElement element, const J &refs) {
    curve_collection_with_propagation(element, refs, false);
}
// FEAT-051: per-operation material evidence for round/chamfer/draft. The two
// probes reuse the lightweight mass-property query the cut path already takes
// around feature creation; no extra full inspection runs per operation. Values
// are reported in mm^3 only when the model's length-unit scale to mm is known
// (native volume * scale^3); everything unestablished stays null and the raw
// query codes are preserved. Zero deltas are legal reported values.
struct VolumeProbe {
    bool ran = false;
    ProError code = PRO_TK_NO_ERROR;
    double native_volume = 0.0;
    bool finite = false;
};
// Keep the before-side probe for the shared tail and the single failure record.
static VolumeProbe material_probe_before;
static bool material_probe_active = false;
static VolumeProbe probe_volume() {
    VolumeProbe probe;
    ProMassProperty property = {};
    probe.code = ProSolidMassPropertyWithDensityGet((ProSolid)board, nullptr,
                                                    PRO_MP_DENS_USE_ALWAYS, 1.0, &property);
    probe.ran = true;
    probe.native_volume = property.volume;
    probe.finite = std::isfinite(property.volume);
    log("VOLUME_PROBE code=%d native=%.12f\n", probe.code, probe.native_volume);
    return probe;
}
// `no_solid_confirmed` marks a verified material-free model (has_solid=false):
// the volume values then stay null with status not_applicable while the query
// codes keep whatever the probes actually returned. A missing after-side probe
// (failed operation) keeps its code null instead of inventing a result.
static J material_observation_json(const VolumeProbe &before, bool after_ran,
                                   const VolumeProbe &after, bool no_solid_confirmed) {
    auto units = inspect_length_units(board);
    MillimeterScale scale = length_scale_to_mm(board, units);
    const double factor = scale.scale * scale.scale * scale.scale;
    auto established = [&](const VolumeProbe &probe) {
        return probe.ran && probe.code == PRO_TK_NO_ERROR && probe.finite && scale.known;
    };
    J before_mm3 = nullptr, after_mm3 = nullptr, delta = nullptr;
    if (!no_solid_confirmed) {
        if (established(before))
            before_mm3 = before.native_volume * factor;
        if (after_ran && established(after))
            after_mm3 = after.native_volume * factor;
        if (!before_mm3.is_null() && !after_mm3.is_null())
            delta = after_mm3.get<double>() - before_mm3.get<double>();
    }
    const char *status =
        no_solid_confirmed ? "not_applicable" : (!delta.is_null() ? "measured" : "unknown");
    return {{"volume_before_mm3", before_mm3},
            {"volume_after_mm3", after_mm3},
            {"material_delta_mm3", delta},
            {"material_measurement",
             {{"status", status},
              {"before_query_code", before.ran ? J((int)before.code) : J(nullptr)},
              {"after_query_code", after_ran && after.ran ? J((int)after.code) : J(nullptr)}}}};
}

// BUG-191: guard every additive operation between regeneration and save.
// Only an independently confirmed absence of solid bodies establishes zero.
static void verify_add_volume(J &result, bool had_solid, bool has_solid) {
    auto establish = [](J &volume, bool solid) {
        if (!solid)
            volume = 0.0;
        else if (!volume.is_number() || !std::isfinite(volume.get<double>()) ||
                 volume.get<double>() <= 0.0)
            volume = nullptr;
    };
    J &before = result.at("volume_before_mm3");
    J &after = result.at("volume_after_mm3");
    establish(before, had_solid);
    establish(after, has_solid);
    const bool measured = before.is_number() && after.is_number();
    J delta = nullptr, tolerance = nullptr;
    const char *reason = nullptr;
    if (measured) {
        const double difference = after.get<double>() - before.get<double>();
        const double limit = std::max(1e-6, before.get<double>() * 1e-12);
        delta = difference;
        tolerance = limit;
        if (!has_solid || difference < -limit)
            reason = had_solid ? "add_reduced_volume" : "add_produced_no_solid";
    } else {
        reason = "add_volume_unverified";
    }
    result["material_delta_mm3"] = delta;
    result["material_measurement"]["status"] = measured ? "measured" : "unknown";
    result["add_volume_check"] = {{"status", reason ? "failed" : "passed"},
                                  {"reason", reason ? J(reason) : J(nullptr)},
                                  {"tolerance_mm3", tolerance}};
    if (reason) {
        stage_operation_result(result);
        throw std::runtime_error(std::string(reason) + ": additive operation could not be saved " +
                                 "(volume before/after in mm3: " + before.dump() + "/" +
                                 after.dump() + ", tolerance: " + tolerance.dump() + ")");
    }
}
// Non-throwing tree navigation for readback: raw codes instead of exceptions,
// so a missing element degrades one field to unknown instead of failing the
// result of an already-created feature.
static ProElement get_optional(ProElement root, std::initializer_list<int> ids, ProError *code) {
    std::vector<ProElempathItem> items;
    for (int id : ids) {
        ProElempathItem item = {};
        item.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
        item.path_item.elem_id = (ProElemId)id;
        items.push_back(item);
    }
    ProElempath path = nullptr;
    *code = ProElempathAlloc(&path);
    if (!*code)
        *code = ProElempathDataSet(path, items.data(), (int)items.size());
    ProElement result = nullptr;
    if (!*code)
        *code = ProElemtreeElementGet(root, path, &result);
    if (path)
        ProElempathFree(&path);
    return result;
}
// W05: the request side is what the caller actually sent (null when
// validate_operations recorded an omission in defaulted_fields, because the
// operation it hands over already carries the applied default), and the
// effective side is read from the created feature's own tree. A through-all
// feature stores no blind value, so effective_depth_mm stays null there
// instead of repeating the 1 mm default. Unreadable paths keep their raw
// query code and never fabricate.
static J extrude_depth_report(ProFeature &f, const J &op) {
    J defaulted = op.value("defaulted_fields", J::array());
    J block = {{"source", "unknown"},
               {"query_code", nullptr},
               {"requested_depth_type", nullptr},
               {"requested_depth_mm", nullptr},
               {"effective_depth_type", nullptr},
               {"effective_depth_mm", nullptr},
               {"defaulted_fields", defaulted}};
    bool type_omitted = false, depth_omitted = false;
    for (auto field : defaulted) {
        if (field == "depth_type")
            type_omitted = true;
        if (field == "depth")
            depth_omitted = true;
    }
    if (!type_omitted && op.contains("depth_type"))
        block["requested_depth_type"] = op["depth_type"];
    if (!depth_omitted && op.contains("depth"))
        block["requested_depth_mm"] = op["depth"];
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    block["query_code"] = (int)code;
    if (code != PRO_TK_NO_ERROR)
        return block;
    block["source"] = "feature_tree";
    ProError path_code = PRO_TK_NO_ERROR;
    ProElement type_elem = get_optional(
        tree, {PRO_E_STD_EXT_DEPTH, PRO_E_EXT_DEPTH_TO, PRO_E_EXT_DEPTH_TO_TYPE}, &path_code);
    int type = 0;
    if (path_code == PRO_TK_NO_ERROR && type_elem &&
        !ProElementIntegerGet(type_elem, nullptr, &type)) {
        block["effective_depth_type"] = type == PRO_EXT_DEPTH_TO_ALL      ? "through_all"
                                        : type == PRO_EXT_DEPTH_SYMMETRIC ? "symmetric"
                                                                          : "blind";
        if (type != PRO_EXT_DEPTH_TO_ALL) {
            ProElement value_elem = get_optional(
                tree, {PRO_E_STD_EXT_DEPTH, PRO_E_EXT_DEPTH_TO, PRO_E_EXT_DEPTH_TO_VALUE},
                &path_code);
            double value = 0;
            if (path_code == PRO_TK_NO_ERROR && value_elem &&
                !ProElementDoubleGet(value_elem, nullptr, &value))
                block["effective_depth_mm"] = value;
            else
                block["query_code"] = (int)(path_code ? path_code : PRO_TK_GENERAL_ERROR);
        }
    } else
        block["query_code"] = (int)(path_code ? path_code : PRO_TK_GENERAL_ERROR);
    ProFeatureElemtreeFree(&f, tree);
    return block;
}
// FEAT-051: applied_set_count is proven only by the created feature's own
// element tree; the requested input count is reported separately and never
// presented as evidence (no input echo, no full-model edge-count difference).
static ProError count_tree_elements(ProElement tree, int target_id, int *count) {
    struct CountState {
        int id;
        int total;
    } state = {target_id, 0};
    ProError code = ProElemtreeElementVisit(
        tree, nullptr, nullptr,
        [](ProElement, ProElement elem, ProElempath, ProAppData data) -> ProError {
            auto *counter = (CountState *)data;
            ProElemId id = (ProElemId)0;
            if (!ProElementIdGet(elem, &id) && (int)id == counter->id)
                counter->total++;
            return PRO_TK_NO_ERROR;
        },
        &state);
    *count = state.total;
    return code;
}
static J reference_application_block(int requested, const J &applied, const char *source,
                                     ProError code) {
    return {{"requested_set_count", requested},
            {"applied_set_count", applied},
            {"source", source},
            {"query_code", (int)code}};
}
// A zero count against a nonempty request is treated as unproven instead of
// claiming "applied 0": a silently failing visitor must read as unknown.
static J round_reference_application(ProFeature &f, int requested) {
    ProElement tree = nullptr;
    ProError code = ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree);
    if (code)
        return reference_application_block(requested, nullptr, "unknown", code);
    int applied = 0;
    code = count_tree_elements(tree, PRO_E_RNDCH_SET, &applied);
    ProFeatureElemtreeFree(&f, tree);
    if (code || (applied == 0 && requested > 0))
        return reference_application_block(requested, nullptr, "unknown", code);
    return reference_application_block(requested, applied, "feature_tree", code);
}
// BUG-161: one complete circular hole can supply two 180-degree edges with
// different ids. Each id resolves on its own, so neither the selector match nor
// BUG-155's id/type check can see that both name one circle; the feature then
// fails with a bare regeneration status and no ProFeatureErrorlist detail.
// Resolve every edge reference before any element is built and refuse a plan
// that names one circle twice, naming the participants and the id to keep.
static void reject_duplicate_round_circles(const J &op, bool chamfer) {
    struct CircleRef {
        int id;
        V center;
        double radius;
    };
    // Measured centres/radii are native model units; convert the published
    // 1e-6 mm comparison tolerance with the model's own scale and never guess
    // it when the unit query fails.
    const MillimeterScale scale = length_scale_to_mm((ProMdl)board, inspect_length_units(board));
    const double tolerance = scale.known ? 1e-6 / scale.scale : 1e-6;
    std::vector<CircleRef> circles;
    for (const auto &refs : op["references"]) {
        if (!refs.is_object() || !refs.contains("edge"))
            continue;
        ProSelection s = resolve(refs.at("edge"));
        ProModelitem item;
        const ProError item_code = ProSelectionModelitemGet(s, &item);
        ProSelectionFree(&s);
        // A non-edge selection is already refused by the feature builder; this
        // pre-check only speaks for circle duplicates.
        if (item_code != PRO_TK_NO_ERROR || item.type != PRO_EDGE)
            continue;
        ProEdge edge;
        if (ProEdgeInit((ProSolid)board, item.id, &edge) != PRO_TK_NO_ERROR)
            continue;
        ProGeomitemdata *data = nullptr;
        if (ProEdgeDataGet(edge, &data) != PRO_TK_NO_ERROR || !data)
            continue;
        ProCurvedata *curve = data->data.p_curve_data;
        ProEnttype curve_type = PRO_ENT_NONE;
        ProVector v1, v2, origin;
        double start = 0, end = 0, radius = 0;
        // Straight and spline edges carry no centre/radius and cannot be paired.
        const bool circular =
            curve && ProCurvedataTypeGet(curve, &curve_type) == PRO_TK_NO_ERROR &&
            curve_type == PRO_ENT_ARC &&
            ProArcdataGet(curve, v1, v2, origin, &start, &end, &radius) == PRO_TK_NO_ERROR;
        ProGeomitemdataFree(&data);
        if (!circular)
            continue;
        const V center = {origin[0], origin[1], origin[2]};
        for (const auto &seen : circles) {
            if (std::fabs(seen.radius - radius) > tolerance ||
                std::fabs(seen.center[0] - center[0]) > tolerance ||
                std::fabs(seen.center[1] - center[1]) > tolerance ||
                std::fabs(seen.center[2] - center[2]) > tolerance)
                continue;
            const double report_scale = scale.known ? scale.scale : 1.0;
            const char *unit = scale.known ? " mm" : " (model units)";
            throw std::runtime_error(
                std::string(chamfer ? "chamfer" : "round") + " references edges " +
                std::to_string(seen.id) + " and " + std::to_string(item.id) +
                " that lie on one circle (centre " + std::to_string(center[0] * report_scale) +
                ", " + std::to_string(center[1] * report_scale) + ", " +
                std::to_string(center[2] * report_scale) + unit + ", radius " +
                std::to_string(radius * report_scale) + unit + "); keep the smallest id (" +
                std::to_string(std::min(seen.id, item.id)) +
                ") and remove the duplicate reference");
        }
        circles.push_back({item.id, center, radius});
    }
}
static void delete_feature_quiet(int feat_id) {
    if (feat_id <= 0)
        return;
    int *list = nullptr;
    ProFeatureDeleteOptions *options = nullptr;
    if (ProArrayAlloc(1, sizeof(int), 1, (ProArray *)&list) == PRO_TK_NO_ERROR) {
        list[0] = feat_id;
        if (ProArrayAlloc(1, sizeof(ProFeatureDeleteOptions), 1, (ProArray *)&options) ==
            PRO_TK_NO_ERROR) {
            options[0] = PRO_FEAT_DELETE_NO_OPTS;
            ProFeatureWithoptionsDelete((ProSolid)board, list, options, PRO_REGEN_NO_FLAGS);
            ProArrayFree((ProArray *)&options);
        }
        ProArrayFree((ProArray *)&list);
    }
    ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS);
}

static bool feature_is_healthy_active(ProFeature *f) {
    if (!f || f->id <= 0)
        return false;
    ProFeatStatus st = PRO_FEAT_INVALID;
    ProBoolean inc = PRO_B_FALSE;
    if (ProFeatureStatusGet(f, &st) != PRO_TK_NO_ERROR || st != PRO_FEAT_ACTIVE)
        return false;
    if (ProFeatureIsIncomplete(f, &inc) != PRO_TK_NO_ERROR || inc == PRO_B_TRUE)
        return false;
    return true;
}

// FEAT-079: when a multi-reference round/chamfer fails, isolate which individual
// reference(s) cannot regenerate so the caller does not have to manually bisect.
template <typename TreeBuilder>
static J probe_round_references(const J &op, TreeBuilder &&build_tree) {
    const J &refs = op.at("references");
    const size_t total = refs.size();
    const size_t limit = std::min<size_t>(total, 20);
    J failed_indices = J::array();
    int first_failed = -1;
    ProModelitem mi = {};
    if (ProMdlToModelitem(board, &mi) != PRO_TK_NO_ERROR)
        return {{"probed_count", 0},
                {"total_references", (int)total},
                {"failed_indices", failed_indices}};
    for (size_t i = 0; i < limit; ++i) {
        bool ok = false;
        ProElement probe_root = nullptr;
        ProFeature probe_feat = {};
        try {
            probe_root = build_tree("probe_rnd_" + std::to_string(i), J::array({refs[i]}));
            ProSelection sel = nullptr;
            ProFeatureCreateOptions *opts = nullptr;
            if (ProSelectionAlloc(nullptr, &mi, &sel) == PRO_TK_NO_ERROR &&
                ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&opts) ==
                    PRO_TK_NO_ERROR) {
                opts[0] = PRO_FEAT_CR_NO_OPTS;
                ProErrorlist es = {};
                ProError err = ProFeatureWithoptionsCreate(sel, probe_root, opts,
                                                           PRO_REGEN_NO_FLAGS, &probe_feat, &es);
                if (err == PRO_TK_NO_ERROR && probe_feat.id > 0) {
                    ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS);
                    ok = feature_is_healthy_active(&probe_feat);
                }
                ProArrayFree((ProArray *)&opts);
            }
            if (sel)
                ProSelectionFree(&sel);
        } catch (...) {
            ok = false;
        }
        if (probe_root)
            ProElementFree(&probe_root);
        if (probe_feat.id > 0)
            delete_feature_quiet(probe_feat.id);
        if (!ok) {
            failed_indices.push_back((int)i);
            if (first_failed < 0)
                first_failed = (int)i;
        }
    }
    J report = {{"probed_count", (int)limit},
                {"total_references", (int)total},
                {"truncated", total > limit},
                {"failed_indices", failed_indices}};
    if (first_failed >= 0) {
        report["failed_reference_index"] = first_failed;
        report["failed_reference"] = refs[(size_t)first_failed];
    }
    return report;
}

static const char *round_surface_type_name(ProSrftype t) {
    switch (t) {
    case PRO_SRF_PLANE:
        return "plane";
    case PRO_SRF_CYL:
        return "cylinder";
    case PRO_SRF_CONE:
        return "cone";
    case PRO_SRF_TORUS:
        return "torus";
    case PRO_SRF_B_SPL:
        return "b_spline";
    case PRO_SRF_SPL:
        return "spline";
    case PRO_SRF_FIL:
        return "fillet";
    case PRO_SRF_RUL:
        return "ruled";
    case PRO_SRF_REV:
        return "revolved";
    case PRO_SRF_TABCYL:
        return "tabulated_cylinder";
    default:
        return "non_analytic";
    }
}

static const char *round_feat_status_name(ProFeatStatus st) {
    switch (st) {
    case PRO_FEAT_ACTIVE:
        return "active";
    case PRO_FEAT_SUPPRESSED:
        return "suppressed";
    case PRO_FEAT_UNREGENERATED:
        return "unregenerated";
    case PRO_FEAT_INVALID:
        return "invalid";
    default:
        return "other";
    }
}

static bool eval_surface_normal_at_point(ProSurface srf, const double pt[3], double out_n[3]) {
    ProUvParam uv = {0.0, 0.0};
    if (ProSurfaceParamEval((ProSolid)board, srf, const_cast<double *>(pt), uv) != PRO_TK_NO_ERROR)
        return false;
    ProVector xyz = {}, d1[2] = {}, d2[3] = {}, n = {};
    if (ProSurfaceXyzdataEval(srf, uv, xyz, d1, d2, n) != PRO_TK_NO_ERROR)
        return false;
    const double len = std::sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    if (len <= 1e-12)
        return false;
    out_n[0] = n[0] / len;
    out_n[1] = n[1] / len;
    out_n[2] = n[2] / len;
    return true;
}

// BUG-180: collect geometric diagnostics for referenced round/chamfer edges so
// single-edge and multi-edge failures expose adjacent surface types, dihedral
// angle, and vertex sliver/tangent neighbors instead of a bare regen status.
static J diagnose_round_edges(const J &refs, double mm_scale) {
    struct EdgeSample {
        int id = -1;
        double len_mm = 0.0;
        double p0[3] = {};
        double p1[3] = {};
        double t0[3] = {};
        double t1[3] = {};
        bool has_ends = false;
    };
    std::vector<EdgeSample> all_edges;
    std::set<int> seen_edge_ids;
    struct CollectCtx {
        double scale;
        std::vector<EdgeSample> *edges;
        std::set<int> *seen;
        ProSurface current_srf = nullptr;
    } collect_ctx = {mm_scale, &all_edges, &seen_edge_ids, nullptr};
    ProSolidSurfaceVisit((ProSolid)board,
                         [](ProSurface srf, ProError, ProAppData data) -> ProError {
                             auto *ctx = (CollectCtx *)data;
                             ctx->current_srf = srf;
                             ProSurfaceContourVisit(
                                 srf,
                                 [](ProContour cntr, ProError, ProAppData d2) -> ProError {
                                     auto *ctx2 = (CollectCtx *)d2;
                                     ProContourEdgeVisit(
                                         ctx2->current_srf, cntr,
                                         [](ProEdge edge, ProError, ProAppData d3) -> ProError {
                                             auto *ctx = (CollectCtx *)d3;
                                             int eid = -1;
                                             if (ProEdgeIdGet(edge, &eid) != PRO_TK_NO_ERROR ||
                                                 !ctx->seen->insert(eid).second)
                                                 return PRO_TK_NO_ERROR;
                                             EdgeSample s;
                                             s.id = eid;
                                             double len = 0.0;
                                             if (ProEdgeLengthEval(edge, &len) == PRO_TK_NO_ERROR)
                                                 s.len_mm = len * ctx->scale;
                                             ProVector d1 = {}, d2v = {}, dir = {};
                                             if (ProEdgeXyzdataEval(edge, 0.0, s.p0, d1, d2v,
                                                                    s.t0) == PRO_TK_NO_ERROR &&
                                                 ProEdgeXyzdataEval(edge, 1.0, s.p1, d1, d2v,
                                                                    s.t1) == PRO_TK_NO_ERROR)
                                                 s.has_ends = true;
                                             ctx->edges->push_back(s);
                                             return PRO_TK_NO_ERROR;
                                         },
                                         nullptr, d2);
                                     return PRO_TK_NO_ERROR;
                                 },
                                 nullptr, data);
                             return PRO_TK_NO_ERROR;
                         },
                         nullptr, &collect_ctx);

    const double pi = 3.14159265358979323846;
    const double vtx_tol_native = mm_scale > 0.0 ? 0.05 / mm_scale : 0.05;
    auto vertex_info = [&](int self_id, const double pt[3], const double self_tan[3]) -> J {
        int adj_count = 0;
        double min_len = -1.0;
        J tangent_ids = J::array();
        const double st_len = std::sqrt(self_tan[0] * self_tan[0] + self_tan[1] * self_tan[1] +
                                        self_tan[2] * self_tan[2]);
        for (const auto &e : all_edges) {
            if (e.id == self_id || !e.has_ends)
                continue;
            const double d0 = std::sqrt((e.p0[0] - pt[0]) * (e.p0[0] - pt[0]) +
                                        (e.p0[1] - pt[1]) * (e.p0[1] - pt[1]) +
                                        (e.p0[2] - pt[2]) * (e.p0[2] - pt[2]));
            const double d1 = std::sqrt((e.p1[0] - pt[0]) * (e.p1[0] - pt[0]) +
                                        (e.p1[1] - pt[1]) * (e.p1[1] - pt[1]) +
                                        (e.p1[2] - pt[2]) * (e.p1[2] - pt[2]));
            if (d0 > vtx_tol_native && d1 > vtx_tol_native)
                continue;
            adj_count++;
            if (min_len < 0.0 || e.len_mm < min_len)
                min_len = e.len_mm;
            const double *other_tan = (d0 <= d1) ? e.t0 : e.t1;
            const double ot_len =
                std::sqrt(other_tan[0] * other_tan[0] + other_tan[1] * other_tan[1] +
                          other_tan[2] * other_tan[2]);
            if (st_len > 1e-12 && ot_len > 1e-12) {
                double cos_a = std::fabs((self_tan[0] * other_tan[0] + self_tan[1] * other_tan[1] +
                                          self_tan[2] * other_tan[2]) /
                                         (st_len * ot_len));
                cos_a = std::min(1.0, std::max(0.0, cos_a));
                if (std::acos(cos_a) * 180.0 / pi <= 1.0 && tangent_ids.size() < 8)
                    tangent_ids.push_back(e.id);
            }
        }
        return {{"adjacent_edge_count", adj_count},
                {"min_adjacent_edge_mm", min_len >= 0.0 ? J(min_len) : J(nullptr)},
                {"tangent_adjacent_edge_ids", tangent_ids}};
    };

    J diagnostics = J::array();
    const size_t limit = std::min<size_t>(refs.size(), 10);
    for (size_t i = 0; i < limit; ++i) {
        if (!refs[i].is_object() || !refs[i].contains("edge"))
            continue;
        try {
            ProSelection sel = resolve(refs[i].at("edge"));
            ProModelitem mi = {};
            ProError ic = ProSelectionModelitemGet(sel, &mi);
            ProSelectionFree(&sel);
            if (ic != PRO_TK_NO_ERROR || mi.type != PRO_EDGE)
                continue;
            ProEdge edge = nullptr;
            if (ProEdgeInit((ProSolid)board, mi.id, &edge) != PRO_TK_NO_ERROR)
                continue;
            J entry = {{"reference_index", (int)i}, {"edge_id", mi.id}};
            double len = 0.0;
            if (ProEdgeLengthEval(edge, &len) == PRO_TK_NO_ERROR)
                entry["length_mm"] = len * mm_scale;
            ProVector p0 = {}, p1 = {}, pm = {}, d1 = {}, d2 = {}, t0 = {}, t1 = {}, tm = {};
            const bool has_mid = ProEdgeXyzdataEval(edge, 0.5, pm, d1, d2, tm) == PRO_TK_NO_ERROR;
            if (ProEdgeXyzdataEval(edge, 0.0, p0, d1, d2, t0) == PRO_TK_NO_ERROR)
                entry["start_vertex"] = vertex_info(mi.id, p0, t0);
            if (ProEdgeXyzdataEval(edge, 1.0, p1, d1, d2, t1) == PRO_TK_NO_ERROR)
                entry["end_vertex"] = vertex_info(mi.id, p1, t1);
            ProEdge n1 = nullptr, n2 = nullptr;
            ProSurface s1 = nullptr, s2 = nullptr;
            if (ProEdgeNeighborsGet(edge, &n1, &n2, &s1, &s2) == PRO_TK_NO_ERROR) {
                J adj_surfs = J::array();
                double normals[2][3] = {};
                int normal_count = 0;
                ProSurface pair_s[2] = {s1, s2};
                for (int k = 0; k < 2; ++k) {
                    if (!pair_s[k])
                        continue;
                    int sid = -1;
                    ProSurfaceIdGet(pair_s[k], &sid);
                    ProSrftype stype = PRO_SRF_NONE;
                    ProSurfaceTypeGet(pair_s[k], &stype);
                    J srec = {{"id", sid},
                              {"type", (int)stype},
                              {"type_name", round_surface_type_name(stype)}};
                    double area = 0.0;
                    if (ProSurfaceAreaEval(pair_s[k], &area) == PRO_TK_NO_ERROR && area >= 0.0)
                        srec["area_mm2"] = area * mm_scale * mm_scale;
                    if (has_mid &&
                        eval_surface_normal_at_point(pair_s[k], pm, normals[normal_count])) {
                        srec["normal_at_midpoint"] =
                            J::array({normals[normal_count][0], normals[normal_count][1],
                                      normals[normal_count][2]});
                        normal_count++;
                    }
                    adj_surfs.push_back(std::move(srec));
                }
                entry["adjacent_surfaces"] = std::move(adj_surfs);
                if (normal_count == 2) {
                    double dot_n = normals[0][0] * normals[1][0] + normals[0][1] * normals[1][1] +
                                   normals[0][2] * normals[1][2];
                    dot_n = std::max(-1.0, std::min(1.0, dot_n));
                    entry["dihedral_angle_deg"] = std::acos(std::fabs(dot_n)) * 180.0 / pi;
                }
            }
            diagnostics.push_back(std::move(entry));
        } catch (...) {
        }
    }
    return diagnostics;
}

// BUG-179: measure actual created surface count, total area, and chamfered edge
// length directly from the created feature's owned surfaces.
static J collect_created_surface_metrics(ProFeature &f, double mm_scale, bool is_chamfer) {
    J out = J::object();
    if (f.id <= 0 || mm_scale <= 0.0)
        return out;
    J srf_ids = J::array();
    if (ProFeatureGeomitemVisit(&f, PRO_SURFACE, collect_geom_ids, nullptr, &srf_ids) !=
        PRO_TK_NO_ERROR)
        return out;
    int count = 0;
    double total_area_mm2 = 0.0;
    double total_chamfer_len_mm = 0.0;
    for (const auto &id_val : srf_ids) {
        int sid = -1;
        if (id_val.is_number_integer())
            sid = id_val.get<int>();
        else if (id_val.is_object() && id_val.contains("id") && id_val["id"].is_number_integer())
            sid = id_val["id"].get<int>();
        else
            continue;
        ProSurface srf = nullptr;
        if (ProSurfaceInit((ProSolid)board, sid, &srf) != PRO_TK_NO_ERROR)
            continue;
        count++;
        double area = 0.0;
        if (ProSurfaceAreaEval(srf, &area) == PRO_TK_NO_ERROR && area >= 0.0)
            total_area_mm2 += area * mm_scale * mm_scale;
        if (is_chamfer) {
            struct MaxEdgeCtx {
                ProSurface srf = nullptr;
                double max_len = 0.0;
            } mctx = {srf, 0.0};
            ProSurfaceContourVisit(
                srf,
                [](ProContour cntr, ProError, ProAppData d) -> ProError {
                    auto *c0 = (MaxEdgeCtx *)d;
                    ProContourEdgeVisit(
                        c0->srf, cntr,
                        [](ProEdge edge, ProError, ProAppData d2) -> ProError {
                            auto *c = (MaxEdgeCtx *)d2;
                            double len = 0.0;
                            if (ProEdgeLengthEval(edge, &len) == PRO_TK_NO_ERROR &&
                                len > c->max_len)
                                c->max_len = len;
                            return PRO_TK_NO_ERROR;
                        },
                        nullptr, d);
                    return PRO_TK_NO_ERROR;
                },
                nullptr, &mctx);
            total_chamfer_len_mm += mctx.max_len * mm_scale;
        }
    }
    out["created_surface_count"] = count;
    out["created_surface_area_mm2"] = total_area_mm2;
    if (is_chamfer)
        out["chamfered_edge_length_mm"] = total_chamfer_len_mm;
    return out;
}

// FEAT-081: geometry-level G2 curvature verification across shared boundary
// edges between newly created G2 round surfaces and adjacent support surfaces.
static bool eval_normal_curvature_along_dir(ProSurface srf, const double pt[3],
                                            const double tangent_edge[3], double mm_scale,
                                            const double *ref_normal, double *out_normal,
                                            double *out_kappa_inv_mm) {
    ProUvParam uv = {0.0, 0.0};
    if (ProSurfaceParamEval((ProSolid)board, srf, const_cast<double *>(pt), uv) != PRO_TK_NO_ERROR)
        return false;
    ProVector xyz = {}, d1[2] = {}, d2[3] = {}, n = {};
    if (ProSurfaceXyzdataEval(srf, uv, xyz, d1, d2, n) != PRO_TK_NO_ERROR)
        return false;
    const double nlen = std::sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    if (nlen <= 1e-12)
        return false;
    double un[3] = {n[0] / nlen, n[1] / nlen, n[2] / nlen};
    if (ref_normal) {
        double dn = un[0] * ref_normal[0] + un[1] * ref_normal[1] + un[2] * ref_normal[2];
        if (dn < 0.0) {
            un[0] = -un[0];
            un[1] = -un[1];
            un[2] = -un[2];
        }
    }
    out_normal[0] = un[0];
    out_normal[1] = un[1];
    out_normal[2] = un[2];

    // Cross-boundary tangent direction d = normalize(un x tangent_edge).
    double cross[3] = {un[1] * tangent_edge[2] - un[2] * tangent_edge[1],
                       un[2] * tangent_edge[0] - un[0] * tangent_edge[2],
                       un[0] * tangent_edge[1] - un[1] * tangent_edge[0]};
    const double clen = std::sqrt(cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]);
    if (clen <= 1e-12)
        return false;
    cross[0] /= clen;
    cross[1] /= clen;
    cross[2] /= clen;

    const auto dot3 = [](const double a[3], const double b[3]) {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    };
    const double E = dot3(d1[0], d1[0]);
    const double F = dot3(d1[0], d1[1]);
    const double G = dot3(d1[1], d1[1]);
    const double det = E * G - F * F;
    if (std::fabs(det) <= 1e-18)
        return false;
    const double rhs_u = dot3(cross, d1[0]);
    const double rhs_v = dot3(cross, d1[1]);
    const double a = (G * rhs_u - F * rhs_v) / det;
    const double b = (E * rhs_v - F * rhs_u) / det;
    const double first_form = E * a * a + 2.0 * F * a * b + G * b * b;
    if (first_form <= 1e-18)
        return false;
    // ProSurfaceXyzdataEval deriv2[3]: [0]=r_uu, [1]=r_vv, [2]=r_uv
    const double L = dot3(d2[0], un);
    const double N = dot3(d2[1], un);
    const double M = dot3(d2[2], un);
    const double second_form = L * a * a + 2.0 * M * a * b + N * b * b;
    const double kappa_native = second_form / first_form;
    *out_kappa_inv_mm = kappa_native / mm_scale;
    return std::isfinite(*out_kappa_inv_mm);
}

static J measure_g2_round_verification(ProFeature &f, double mm_scale) {
    J out = {{"requested_curvature_continuous", true},
             {"native_conic_type", nullptr},
             {"native_conic_value", nullptr},
             {"sampled_edges", 0},
             {"sampled_points", 0},
             {"max_tangent_angle_deg", nullptr},
             {"max_curvature_gap_inv_mm", nullptr},
             {"tolerance_inv_mm", 0.002},
             {"verdict", "unsupported"},
             {"reason", nullptr}};
    // Read back native conic type & value from feature tree.
    ProElement tree = nullptr;
    if (ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree) ==
        PRO_TK_NO_ERROR) {
        struct ConicRead {
            bool has_type = false;
            int type_val = 0;
            bool has_val = false;
            double conic_val = 0.0;
        } cread;
        ProElemtreeElementVisit(
            tree, nullptr, nullptr,
            [](ProElement, ProElement elem, ProElempath, ProAppData data) -> ProError {
                auto *c = (ConicRead *)data;
                ProElemId id = (ProElemId)0;
                if (ProElementIdGet(elem, &id) != PRO_TK_NO_ERROR)
                    return PRO_TK_NO_ERROR;
                if ((int)id == PRO_E_RNDCH_CONIC_TYPE && !c->has_type) {
                    if (ProElementIntegerGet(elem, nullptr, &c->type_val) == PRO_TK_NO_ERROR)
                        c->has_type = true;
                } else if ((int)id == PRO_E_RNDCH_CONIC_VALUE && !c->has_val) {
                    if (ProElementDoubleGet(elem, nullptr, &c->conic_val) == PRO_TK_NO_ERROR)
                        c->has_val = true;
                }
                return PRO_TK_NO_ERROR;
            },
            &cread);
        ProFeatureElemtreeFree(&f, tree);
        if (cread.has_type)
            out["native_conic_type"] = cread.type_val;
        if (cread.has_val)
            out["native_conic_value"] = cread.conic_val;
    }

    if (mm_scale <= 0.0) {
        out["reason"] = "unknown_length_unit_scale";
        return out;
    }
    J srf_ids_json = J::array();
    if (ProFeatureGeomitemVisit(&f, PRO_SURFACE, collect_geom_ids, nullptr, &srf_ids_json) !=
            PRO_TK_NO_ERROR ||
        srf_ids_json.empty()) {
        out["reason"] = "no_round_surfaces_found";
        return out;
    }
    std::set<int> round_srf_ids;
    for (const auto &v : srf_ids_json) {
        if (v.is_number_integer())
            round_srf_ids.insert(v.get<int>());
        else if (v.is_object() && v.contains("id") && v["id"].is_number_integer())
            round_srf_ids.insert(v["id"].get<int>());
    }

    const double pi = 3.14159265358979323846;
    struct G2Ctx {
        const std::set<int> *round_ids;
        double mm_scale;
        double pi;
        std::set<int> seen_edges;
        int sampled_edges = 0;
        int sampled_points = 0;
        double max_tan_deg = 0.0;
        double max_curv_gap = 0.0;
        ProSurface current_srf = nullptr;
    } g2ctx = {&round_srf_ids, mm_scale, pi, {}, 0, 0, 0.0, 0.0, nullptr};

    for (int sid : round_srf_ids) {
        ProSurface rsrf = nullptr;
        if (ProSurfaceInit((ProSolid)board, sid, &rsrf) != PRO_TK_NO_ERROR)
            continue;
        g2ctx.current_srf = rsrf;
        ProSurfaceContourVisit(
            rsrf,
            [](ProContour cntr, ProError, ProAppData d) -> ProError {
                auto *c0 = (G2Ctx *)d;
                ProContourEdgeVisit(
                    c0->current_srf, cntr,
                    [](ProEdge edge, ProError, ProAppData d2) -> ProError {
                        auto *c = (G2Ctx *)d2;
                        int eid = -1;
                        if (ProEdgeIdGet(edge, &eid) != PRO_TK_NO_ERROR ||
                            !c->seen_edges.insert(eid).second)
                            return PRO_TK_NO_ERROR;
                        ProEdge n1 = nullptr, n2 = nullptr;
                        ProSurface s1 = nullptr, s2 = nullptr;
                        if (ProEdgeNeighborsGet(edge, &n1, &n2, &s1, &s2) != PRO_TK_NO_ERROR ||
                            !s1 || !s2)
                            return PRO_TK_NO_ERROR;
                        int id1 = -1, id2 = -1;
                        ProSurfaceIdGet(s1, &id1);
                        ProSurfaceIdGet(s2, &id2);
                        const bool in1 = c->round_ids->count(id1) > 0;
                        const bool in2 = c->round_ids->count(id2) > 0;
                        if (in1 == in2)
                            return PRO_TK_NO_ERROR;
                        ProSurface rnd_s = in1 ? s1 : s2;
                        ProSurface adj_s = in1 ? s2 : s1;
                        int pts_on_edge = 0;
                        const double ts[3] = {0.25, 0.5, 0.75};
                        for (double t : ts) {
                            ProVector pt = {}, d1 = {}, d2v = {}, dir = {};
                            if (ProEdgeXyzdataEval(edge, t, pt, d1, d2v, dir) != PRO_TK_NO_ERROR)
                                continue;
                            double n_rnd[3] = {}, n_adj[3] = {};
                            double k_rnd = 0.0, k_adj = 0.0;
                            if (!eval_normal_curvature_along_dir(rnd_s, pt, dir, c->mm_scale,
                                                                 nullptr, n_rnd, &k_rnd))
                                continue;
                            if (!eval_normal_curvature_along_dir(adj_s, pt, dir, c->mm_scale, n_rnd,
                                                                 n_adj, &k_adj))
                                continue;
                            double cos_a = std::max(-1.0, std::min(1.0, n_rnd[0] * n_adj[0] +
                                                                            n_rnd[1] * n_adj[1] +
                                                                            n_rnd[2] * n_adj[2]));
                            double angle_deg = std::acos(cos_a) * 180.0 / c->pi;
                            // Skip sharp end-cap boundary edges (> 5 deg); only measure
                            // tangent seam edges where the G2 round blends into support faces.
                            if (angle_deg > 5.0)
                                continue;
                            double gap = std::fabs(k_rnd - k_adj);
                            if (angle_deg > c->max_tan_deg)
                                c->max_tan_deg = angle_deg;
                            if (gap > c->max_curv_gap)
                                c->max_curv_gap = gap;
                            pts_on_edge++;
                            c->sampled_points++;
                        }
                        if (pts_on_edge > 0)
                            c->sampled_edges++;
                        return PRO_TK_NO_ERROR;
                    },
                    nullptr, d);
                return PRO_TK_NO_ERROR;
            },
            nullptr, &g2ctx);
    }

    out["sampled_edges"] = g2ctx.sampled_edges;
    out["sampled_points"] = g2ctx.sampled_points;
    if (g2ctx.sampled_points == 0) {
        out["verdict"] = "unsupported";
        out["reason"] = "no_tangent_seam_samples_evaluated";
        return out;
    }
    out["max_tangent_angle_deg"] = g2ctx.max_tan_deg;
    out["max_curvature_gap_inv_mm"] = g2ctx.max_curv_gap;
    const double tol = 0.002;
    if (g2ctx.max_curv_gap <= tol && g2ctx.max_tan_deg <= 0.5) {
        out["verdict"] = "pass";
        out["reason"] = "seam_curvature_gap_within_tolerance";
    } else {
        out["verdict"] = "fail";
        out["reason"] = "seam_curvature_gap_exceeds_tolerance";
    }
    return out;
}

static J generic_round(const J &op, bool chamfer) {
    reject_duplicate_round_circles(op, chamfer);
    const bool angle_chamfer = chamfer && op.contains("angle_deg");
    const bool two_distance_chamfer = chamfer && op.contains("distance_1");
    const bool curvature_continuous = !chamfer && op.value("curvature_continuous", false);
    const bool propagate_chain = chamfer && op.value("propagate", "single") == "chain";
    const bool multi_ref = op.at("references").size() > 1;
    const MillimeterScale rnd_scale =
        length_scale_to_mm((ProMdl)board, inspect_length_units(board));
    const double mm_scale = rnd_scale.known ? rnd_scale.scale : 1.0;
    auto build_round_tree = [&](const std::string &feat_name, const J &refs_array) -> ProElement {
        ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
        integer(root, PRO_E_FEATURE_TYPE, chamfer ? PRO_FEAT_CHAMFER : PRO_FEAT_ROUND);
        text(root, PRO_E_STD_FEATURE_NAME, wide(feat_name).c_str());
        ProElement sets = node(root, PRO_E_RNDCH_SETS);
        for (const auto &refs : refs_array) {
            ProElement set = node(sets, PRO_E_RNDCH_SET);
            if (chamfer) {
                int dimensional_schema = PRO_CHM_D_X_D;
                if (angle_chamfer)
                    dimensional_schema = PRO_CHM_ANG_X_D;
                else if (two_distance_chamfer)
                    dimensional_schema = PRO_CHM_D1_X_D2;
                integer(set, PRO_E_RNDCH_DIMENSIONAL_SCHEMA, dimensional_schema);
                integer(set, PRO_E_RNDCH_CHAMFER_SHAPE, PRO_CHM_TANGENT_LEGS);
            } else {
                integer(set, PRO_E_RNDCH_SHAPE_OPTIONS, PRO_ROUND_TYPE_CONSTANT);
                integer(node(set, PRO_E_RNDCH_COMPOUND_CONIC), PRO_E_RNDCH_CONIC_TYPE,
                        curvature_continuous ? PRO_ROUND_CURV_CONTINUOUS : PRO_ROUND_CONIC_DISABLE);
                integer(node(set, PRO_E_RNDCH_COMPOUND_SPINE), PRO_E_RNDCH_BALL_SPINE,
                        PRO_ROUND_ROLLING_BALL);
            }
            ProElement r = node(set, PRO_E_RNDCH_REFERENCES);
            if (refs.contains("surfaces")) {
                integer(r, PRO_E_RNDCH_REFERENCE_TYPE, PRO_ROUND_REF_SURF_SURF);
                ProSelection a = resolve(refs["surfaces"][0]), b = resolve(refs["surfaces"][1]);
                ref(r, PRO_E_RNDCH_REFERENCE_SURFACE1, a);
                ref(r, PRO_E_RNDCH_REFERENCE_SURFACE2, b);
                ProSelectionFree(&a);
                ProSelectionFree(&b);
            } else {
                integer(r, PRO_E_RNDCH_REFERENCE_TYPE, PRO_ROUND_REF_EDGE);
                ProSelection e = resolve(refs.at("edge"));
                ProSelectionFree(&e);
                curve_collection_with_propagation(node(r, PRO_E_STD_CURVE_COLLECTION_APPL),
                                                  J::array({refs.at("edge")}), propagate_chain);
            }
            if (angle_chamfer || two_distance_chamfer) {
                ProSelection face =
                    resolve(op.at(angle_chamfer ? "angle_reference" : "reference_surface"));
                ref(r, PRO_E_RNDCH_REFERENCE_SURFACE, face);
                ProSelectionFree(&face);
            }
            ProElement radius = node(node(set, PRO_E_RNDCH_RADII), PRO_E_RNDCH_RADIUS),
                       leg = node(radius, PRO_E_RNDCH_LEG1);
            integer(leg, PRO_E_RNDCH_LEG_TYPE, PRO_ROUND_RADIUS_TYPE_VALUE);
            if (two_distance_chamfer)
                real(leg, PRO_E_RNDCH_LEG_VALUE, op.at("distance_1"));
            else
                real(leg, PRO_E_RNDCH_LEG_VALUE, op.at("size"));
            if (angle_chamfer || two_distance_chamfer) {
                ProElement second_leg = node(radius, PRO_E_RNDCH_LEG2);
                integer(second_leg, PRO_E_RNDCH_LEG_TYPE, PRO_ROUND_RADIUS_TYPE_VALUE);
                real(second_leg, PRO_E_RNDCH_LEG_VALUE,
                     op.at(angle_chamfer ? "angle_deg" : "distance_2"));
            }
        }
        integer(root, PRO_E_RNDCH_ATTACH_TYPE, PRO_ROUND_ATTACHED);
        node(root, PRO_E_RNDCH_TRANSITIONS);
        return root;
    };
    ProElement root = build_round_tree(op.at("label").get<std::string>(), op.at("references"));
    ProFeature f = {};
    bool created_ok = false;
    std::string create_err;
    try {
        f = create(root);
        created_ok = true;
    } catch (const std::exception &ex) {
        create_err = ex.what();
    } catch (ProError code) {
        create_err = "ProFeatureWithoptionsCreate failed with code " + std::to_string((int)code);
    }
    ProElementFree(&root);
    bool healthy = created_ok && feature_is_healthy_active(&f);
    if (!healthy && created_ok) {
        ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS);
        healthy = feature_is_healthy_active(&f);
    }
    if (!healthy) {
        J diag = J::object();
        if (f.id > 0) {
            ProFeatStatus st = PRO_FEAT_INVALID;
            ProBoolean inc = PRO_B_FALSE;
            if (ProFeatureStatusGet(&f, &st) == PRO_TK_NO_ERROR) {
                diag["feature_status"] = (int)st;
                diag["feature_status_name"] = round_feat_status_name(st);
            }
            if (ProFeatureIsIncomplete(&f, &inc) == PRO_TK_NO_ERROR)
                diag["feature_incomplete"] = (inc == PRO_B_TRUE);
            delete_feature_quiet(f.id);
        }
        J edge_diags = diagnose_round_edges(op.at("references"), mm_scale);
        if (!edge_diags.empty())
            diag["edge_diagnostics"] = std::move(edge_diags);
        if (multi_ref) {
            J probe = probe_round_references(op, build_round_tree);
            diag.update(probe);
            J staged = {{"round_failure", diag}};
            std::string suffix;
            if (probe.contains("failed_reference_index")) {
                staged["failed_reference_index"] = probe["failed_reference_index"];
                staged["failed_reference"] = probe["failed_reference"];
                suffix = "; isolated failed_reference_index=" +
                         std::to_string(probe["failed_reference_index"].get<int>()) +
                         ", failed_indices=" + probe["failed_indices"].dump();
            } else {
                suffix = "; all " + std::to_string(probe["probed_count"].get<int>()) +
                         " references succeeded individually (interaction conflict between sets)";
            }
            stage_operation_result(staged);
            std::string base =
                create_err.empty()
                    ? std::string(chamfer ? "chamfer" : "round") +
                          " feature failed regeneration across multiple reference sets"
                    : create_err;
            throw std::runtime_error(base + suffix);
        }
        stage_operation_result({{"round_failure", diag}});
        std::string base = create_err.empty() ? std::string(chamfer ? "chamfer" : "round") +
                                                    " feature failed regeneration"
                                              : create_err;
        if (diag.contains("edge_diagnostics") && !diag["edge_diagnostics"].empty()) {
            const J &e0 = diag["edge_diagnostics"][0];
            base += " (edge " + std::to_string(e0.value("edge_id", -1)) +
                    ", length_mm=" + std::to_string(e0.value("length_mm", 0.0));
            if (e0.contains("dihedral_angle_deg"))
                base += ", dihedral_deg=" + std::to_string(e0["dihedral_angle_deg"].get<double>());
            base += "; see operations[" + std::to_string(operation_position) +
                    "].round_failure.edge_diagnostics in native_result.json)";
        }
        throw std::runtime_error(base);
    }
    remember(op, f);
    J details = J::object();
    if (two_distance_chamfer) {
        details["chamfer_type"] = "d1_d2";
        details["distance_1"] = op.at("distance_1");
        details["distance_2"] = op.at("distance_2");
    } else {
        details["size"] = op.at("size");
        if (angle_chamfer) {
            details["chamfer_type"] = "distance_angle";
            details["angle_deg"] = op.at("angle_deg");
        } else if (chamfer) {
            details["chamfer_type"] = "equal_distance";
        }
    }
    if (chamfer && op.contains("propagate"))
        details["propagate"] = op["propagate"];
    if (!chamfer && curvature_continuous) {
        details["curvature_continuous"] = true;
        details["g2_verification"] = measure_g2_round_verification(f, mm_scale);
    }
    details.update(collect_created_surface_metrics(f, mm_scale, chamfer));
    details["reference_application"] = round_reference_application(f, (int)op["references"].size());
    return details;
}
static J generic_shell(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_SHELL);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement b = node(root, PRO_E_BODY);
    integer(b, PRO_E_BODY_USE, PRO_BODY_USE_SELECTED);
    int resolved_body_id = 0;
    ProSelection body = nullptr;
    if (op.contains("body_id") && !op["body_id"].is_null()) {
        resolved_body_id = op["body_id"].get<int>();
        require_scopable_body(resolved_body_id);
        body = selection(resolved_body_id, PRO_BODY);
    } else {
        ProSolidBody def_body;
        CK(ProSolidDefaultBodyGet((ProSolid)board, &def_body));
        resolved_body_id = def_body.id;
        body = selection(resolved_body_id, PRO_BODY);
    }
    ref(b, PRO_E_BODY_SELECT, body);
    ProSelectionFree(&body);
    real(root, PRO_E_SHELL_THICK, op.at("thickness"));
    integer(root, PRO_E_SHELL_FLIP,
            op.value("outward", false) ? PRO_SHELL_OUTSIDE : PRO_SHELL_INSIDE);
    if (!op["remove_surfaces"].empty())
        set_refs(node(root, PRO_E_SHELL_SRF), op["remove_surfaces"]);
    ProFeature f = create(root);
    CK(ProElementFree(&root));
    remember(op, f);
    return {{"body_id", resolved_body_id}};
}
static ProElement tree_from_json(const J &spec, ProElement parent = nullptr, int depth = 0) {
    if (depth > 40)
        throw std::runtime_error("Element tree is too deep");
    ProElement e = node(parent, constant(spec.at("id")));
    if (spec.contains("integer"))
        CK(ProElementIntegerSet(e, constant(spec["integer"])));
    if (spec.contains("double")) {
        CK(ProElementDecimalsSet(e, 8));
        CK(ProElementDoubleSet(e, spec["double"]));
    }
    if (spec.contains("string"))
        CK(ProElementWstringSet(e, const_cast<wchar_t *>(wide(spec["string"]).c_str())));
    if (spec.contains("reference")) {
        ProSelection s = resolve(spec["reference"]);
        ProReference r;
        CK(ProSelectionToReference(s, &r));
        CK(ProElementReferenceSet(e, r));
        ProSelectionFree(&s);
    }
    if (spec.contains("references"))
        set_refs(e, spec["references"]);
    if (spec.contains("curve_collection"))
        curve_collection(e, spec["curve_collection"]);
    for (auto child : spec.value("children", J::array()))
        tree_from_json(child, e, depth + 1);
    return e;
}
static void parameters(const J &op) {
    ProModelitem owner;
    CK(ProMdlToModelitem(board, &owner));
    for (auto it = op["values"].begin(); it != op["values"].end(); ++it) {
        ProName name;
        wcscpy_s(name, wide(it.key()).c_str());
        ProParamvalue v = {};
        J value = it.value();
        if (value.is_boolean()) {
            v.type = PRO_PARAM_BOOLEAN;
            v.value.l_val = value.get<bool>() ? 1 : 0;
        } else if (value.is_number_integer()) {
            v.type = PRO_PARAM_INTEGER;
            v.value.i_val = value.get<int>();
        } else if (value.is_number()) {
            v.type = PRO_PARAM_DOUBLE;
            v.value.d_val = value.get<double>();
        } else {
            v.type = PRO_PARAM_STRING;
            wcscpy_s(v.value.s_val, wide(value).c_str());
        }
        ProParameter param;
        ProError e = ProParameterInit(&owner, name, &param);
        if (e == PRO_TK_E_NOT_FOUND)
            CK(ProParameterWithUnitsCreate(&owner, name, &v, nullptr, &param));
        else {
            check(e, "FindParameter");
            CK(ProParameterValueWithUnitsSet(&param, &v, nullptr));
        }
    }
}
// BUG-130 Task 1: the old STL path dereferenced the whole-part tessellation
// array without checking the returned pointer/counts and left no stage boundary
// after ProArraySizeGet. Every stage below is flushed by log(); the last line
// before an access violation now identifies the surface/facet/IO/free step.
static ProError free_stl_tessellation(ProSurfaceTessellationData **surfaces) {
    if (!surfaces || !*surfaces) {
        log("STL_TESS_FREE_SKIP ptr=null\n");
        return PRO_TK_NO_ERROR;
    }
    log("STL_TESS_FREE_BEGIN ptr=%p\n", static_cast<void *>(*surfaces));
    ProError code = ProPartTessellationFree(surfaces);
    log("STL_TESS_FREE_END code=%d ptr=%p\n", static_cast<int>(code),
        static_cast<void *>(*surfaces));
    return code;
}
struct StlTessellationGuard {
    ProSurfaceTessellationData **surfaces;
    ~StlTessellationGuard() {
        if (surfaces && *surfaces)
            free_stl_tessellation(surfaces);
    }
};
// BUG-130 diagnostic-only legacy path. It is never used as a fallback: the
// access violation it reproduces must stay observable, so it runs only when
// MECHDOG_STL_LEGACY_TESSELLATE=1 is set explicitly for a controlled probe.
static void write_stl_tessellated(const std::wstring &file) {
    log("STL_LEGACY_TESSELLATE_BEGIN file=%s\n", utf8(file).c_str());
    ProSurfaceTessellationData *surfaces = nullptr;
    log("STL_TESS_BEGIN\n");
    ProError tess_code = ProPartTessellate((ProPart)board, 0.05, 0.1, PRO_B_FALSE, &surfaces);
    log("STL_TESS_END code=%d ptr=%p\n", static_cast<int>(tess_code),
        static_cast<void *>(surfaces));
    if (tess_code != PRO_TK_NO_ERROR)
        throw std::runtime_error("ProPartTessellate failed with code " +
                                 std::to_string(static_cast<int>(tess_code)));
    StlTessellationGuard guard{&surfaces};
    if (!surfaces)
        throw std::runtime_error("ProPartTessellate returned a null surface array");
    int n = 0;
    ProError size_code = ProArraySizeGet((ProArray)surfaces, &n);
    log("STL_OUTER_ARRAY_COUNT code=%d n=%d\n", static_cast<int>(size_code), n);
    if (size_code != PRO_TK_NO_ERROR)
        throw std::runtime_error("ProArraySizeGet failed with code " +
                                 std::to_string(static_cast<int>(size_code)));
    if (n <= 0)
        throw std::runtime_error("ProPartTessellate returned no surfaces");
    std::ofstream out(file);
    log("STL_OUTPUT_OPEN file=%s ok=%d\n", utf8(file).c_str(), out ? 1 : 0);
    if (!out)
        throw std::runtime_error("Cannot open STL output");
    out.precision(12);
    out << "solid creo_native\n";
    log("STL_OUTPUT_HEADER\n");
    int count = 0;
    for (int i = 0; i < n; i++) {
        auto s = surfaces[i];
        log("STL_SURFACE_BEGIN index=%d n_vertices=%d vertices_null=%d n_facets=%d "
            "facets_null=%d\n",
            i, s.n_vertices, s.vertices ? 0 : 1, s.n_facets, s.facets ? 0 : 1);
        int surface_id = -1;
        ProError id_code = ProSurfaceIdGet(s.surface, &surface_id);
        log("STL_SURFACE_ID index=%d surface_id=%d code=%d\n", i, surface_id,
            static_cast<int>(id_code));
        if (s.n_vertices < 0 || s.n_facets < 0 || (s.n_vertices > 0 && !s.vertices) ||
            (s.n_facets > 0 && !s.facets))
            throw std::runtime_error("Invalid tessellation surface array at index " +
                                     std::to_string(i));
        for (int j = 0; j < s.n_facets; j++) {
            auto indices = s.facets[j];
            if (indices[0] < 0 || indices[1] < 0 || indices[2] < 0 || indices[0] >= s.n_vertices ||
                indices[1] >= s.n_vertices || indices[2] >= s.n_vertices) {
                log("STL_BAD_INDEX index=%d surface_id=%d facet=%d indices=%d,%d,%d "
                    "n_vertices=%d\n",
                    i, surface_id, j, indices[0], indices[1], indices[2], s.n_vertices);
                throw std::runtime_error("Tessellation facet index out of range");
            }
            V a = {s.vertices[indices[0]][0], s.vertices[indices[0]][1], s.vertices[indices[0]][2]},
              b = {s.vertices[indices[1]][0], s.vertices[indices[1]][1], s.vertices[indices[1]][2]},
              c = {s.vertices[indices[2]][0], s.vertices[indices[2]][1], s.vertices[indices[2]][2]};
            if (!std::isfinite(a[0]) || !std::isfinite(a[1]) || !std::isfinite(a[2]) ||
                !std::isfinite(b[0]) || !std::isfinite(b[1]) || !std::isfinite(b[2]) ||
                !std::isfinite(c[0]) || !std::isfinite(c[1]) || !std::isfinite(c[2])) {
                log("STL_NONFINITE_VERTEX index=%d surface_id=%d facet=%d\n", i, surface_id, j);
                throw std::runtime_error("Tessellation vertex is not finite");
            }
            V normal = normalized(cross(add(b, scale(a, -1)), add(c, scale(a, -1))));
            if (!std::isfinite(normal[0]) || !std::isfinite(normal[1]) || !std::isfinite(normal[2]))
                log("STL_NONFINITE_NORMAL index=%d surface_id=%d facet=%d\n", i, surface_id, j);
            out << "facet normal " << normal[0] << ' ' << normal[1] << ' ' << normal[2]
                << "\n outer loop\n";
            for (auto v : {a, b, c})
                out << " vertex " << v[0] << ' ' << v[1] << ' ' << v[2] << '\n';
            out << " endloop\nendfacet\n";
            count++;
            if (count % 4096 == 0)
                log("STL_FACET_BATCH facets=%d index=%d surface_id=%d\n", count, i, surface_id);
        }
        log("STL_SURFACE_END index=%d surface_id=%d facets=%d\n", i, surface_id, s.n_facets);
    }
    out << "endsolid creo_native\n";
    out.flush();
    log("STL_FILE_FLUSH ok=%d facets=%d\n", out ? 1 : 0, count);
    if (!out)
        throw std::runtime_error("STL write/flush failed");
    out.close();
    log("STL_FILE_CLOSE ok=%d\n", out ? 1 : 0);
    if (!out)
        throw std::runtime_error("STL close failed");
    if (!count)
        throw std::runtime_error("No solid facets to export");
    log("STL_EXPORT_END facets=%d\n", count);
    // Preserve the historical free-failure behavior while still logging both
    // sides of the call; the guard must not free a second time.
    guard.surfaces = nullptr;
    CK(free_stl_tessellation(&surfaces));
}

static J stl_export_report_json(const StlExportReport &report) {
    J result = J::object();
    result["method"] = report.method;
    result["requested"] = {{"chord_height_mm", report.requested_chord_height_mm},
                           {"angle_control", report.requested_angle_control}};
    result["length_scale_to_mm"] = report.length_scale_to_mm;
    result["passed"] = {{"chord_height_native", report.passed_chord_height_native},
                        {"angle_control", report.passed_angle_control},
                        {"step_size_native", report.passed_step_size_native},
                        {"config_flags", report.config_flags}};
    result["codes"] = {{"parameter_alloc", static_cast<int>(report.parameter_alloc_code)},
                       {"api", static_cast<int>(report.api_code)},
                       {"parameter_free", static_cast<int>(report.parameter_free_code)},
                       {"directory_save", static_cast<int>(report.directory_save_code)},
                       {"directory_change", static_cast<int>(report.directory_change_code)},
                       {"directory_restore", static_cast<int>(report.directory_restore_code)}};
    result["staging_file_written"] = report.staging_file_written;
    result["published"] = report.published;
    result["success"] = report.success;
    if (!report.error.empty())
        result["error"] = report.error;
    if (!report.file_error.empty())
        result["file_error"] = report.file_error;
    result["file"] = {{"facet_count", report.file.facet_count},
                      {"bytes", report.file.bytes},
                      {"min", report.file.min},
                      {"max", report.file.max}};
    return result;
}

static J stl_per_surface_report_json(const StlPerSurfaceReport &report) {
    J result = J::object();
    result["method"] = report.method;
    result["requested"] = {{"chord_height_mm", report.requested_chord_height_mm},
                           {"angle_control", report.requested_angle_control}};
    result["length_scale_to_mm"] = report.length_scale_to_mm;
    result["passed"] = {{"chord_height_native", report.passed_chord_height_native},
                        {"angle_control", report.passed_angle_control}};
    result["surface_count"] = report.surface_count;
    result["facet_count"] = report.facet_count;
    result["zero_area_facets"] = report.zero_area_facets;
    result["normal_surfaces"] = report.normal_surfaces;
    result["normal_flipped_facets"] = report.normal_flipped_facets;
    result["stitched_triangles"] = report.stitched_triangles;
    result["inverted_stitch_facets"] = report.inverted_stitch_facets;
    result["winding_flipped_facets"] = report.winding_flipped_facets;
    result["winding_conflicts"] = report.winding_conflicts;
    result["signed_volume_mm3"] = report.signed_volume_mm3;
    result["global_flipped"] = report.global_flipped;
    result["deviation_requested"] = report.deviation_requested;
    result["deviation_samples"] = report.deviation_samples;
    result["deviation_failed"] = report.deviation_failed;
    result["deviation_max_mm"] = report.deviation_max_mm;
    result["deviation_mean_mm"] = report.deviation_mean_mm;
    result["deviation_p99_mm"] = report.deviation_p99_mm;
    result["deviation_vertex_samples"] = report.deviation_vertex_samples;
    result["deviation_vertex_max_mm"] = report.deviation_vertex_max_mm;
    result["deviation_worst_surface_id"] = report.deviation_worst_surface_id;
    result["deviation_worst_point"] = {report.deviation_worst_point[0],
                                       report.deviation_worst_point[1],
                                       report.deviation_worst_point[2]};
    // Parameter-space refinement of surfaces the SDK tessellated coarser than
    // the requested chord height (see native/stl_export.h).
    result["refine"] = {{"enabled", report.refine_enabled},
                        {"target_native", report.refine_target_native},
                        {"surfaces", report.refined_surfaces},
                        {"input_facets", report.refine_input_facets},
                        {"output_facets", report.refine_output_facets},
                        {"created_vertices", report.refine_created_vertices},
                        {"pinned_triangles", report.refine_pinned_triangles},
                        {"rejected_edges", report.refine_rejected_edges},
                        {"skipped_uv_surfaces", report.refine_skipped_uv},
                        {"skipped_uv_query", report.refine_skipped_uv_query},
                        {"skipped_uv_mismatch", report.refine_skipped_uv_mismatch},
                        {"skipped_normals", report.refine_skipped_normals},
                        {"uv_max_mismatch", report.refine_uv_max_mismatch},
                        {"max_estimated_sag", report.refine_max_estimated_sag},
                        {"limited_surfaces", report.refine_limited_surfaces},
                        {"zero_area_facets", report.refine_zero_area_facets},
                        {"max_level", report.refine_max_level},
                        {"stop_reason", report.refine_stop_reason},
                        {"remaining_candidates", report.refine_remaining_candidates}};
    J surface_facets = J::array();
    for (const auto &entry : report.surface_facets)
        surface_facets.push_back({{"surface_id", entry.first}, {"facets", entry.second}});
    result["surface_facets"] = surface_facets;
    J refine_shares = J::array();
    for (const auto &entry : report.refine_shares)
        refine_shares.push_back({{"surface_id", static_cast<int>(entry[0])},
                                 {"area_weight", entry[1]},
                                 {"vertices_spent", static_cast<std::uint64_t>(entry[2])},
                                 {"vertices_drawn", static_cast<std::uint64_t>(entry[3])}});
    result["refine_shares"] = refine_shares;
    result["failed_surface_id"] = report.failed_surface_id;
    result["failed_facet_index"] = report.failed_facet_index;
    if (!report.failed_indices.empty())
        result["failed_indices"] = report.failed_indices;
    if (!report.failed_stage.empty())
        result["failed_stage"] = report.failed_stage;
    result["failed_code"] = static_cast<int>(report.failed_code);
    result["staging_file_written"] = report.staging_file_written;
    result["published"] = report.published;
    result["success"] = report.success;
    if (!report.error.empty())
        result["error"] = report.error;
    if (!report.file_error.empty())
        result["file_error"] = report.file_error;
    result["file"] = {{"facet_count", report.file.facet_count},
                      {"bytes", report.file.bytes},
                      {"min", report.file.min},
                      {"max", report.file.max}};
    return result;
}

// BUG-130: official file export or the bounded per-surface candidate. Creo
// writes the official file itself; the per-surface path only borrows one
// surface at a time and streams its facets, so the worker never walks the
// nested ProSurfaceTessellationData array that crashed the old path.
static J write_stl(ProMdl model, const std::wstring &destination, const StlExportOptions &options) {
    const char *legacy_probe = std::getenv("MECHDOG_STL_LEGACY_TESSELLATE");
    if (legacy_probe && *legacy_probe == '1') {
        log("STL_LEGACY_PROBE=1\n");
        write_stl_tessellated(destination);
        return {{"method", "ProPartTessellate legacy diagnostic"}, {"success", true}};
    }
    const InspectionLengthUnits units = inspect_length_units(model);
    const MillimeterScale scale = length_scale_to_mm(model, units);
    log("STL_EXPORT_PARAMS requested_chord_mm=%g requested_angle=%g scale_known=%d scale=%g\n",
        options.chord_height_mm, options.angle_control, scale.known ? 1 : 0, scale.scale);
    const std::wstring staging_name =
        L"stl_" + std::to_wstring(generated_identity_index()) + L".stl";
    StlExportOptions effective = options;
    effective.progress = [](const char *name) { generic_substage(name); };
    // Diagnostic quality override for deviation studies; the public export
    // operation still requests the fixed default.
    const char *chord_probe = std::getenv("MECHDOG_STL_CHORD_MM");
    if (chord_probe && *chord_probe) {
        const double value = std::strtod(chord_probe, nullptr);
        if (std::isfinite(value) && value > 0.0) {
            effective.chord_height_mm = value;
            log("STL_EXPORT_CHORD_OVERRIDE=%g\n", value);
        }
    }
    const char *angle_probe = std::getenv("MECHDOG_STL_ANGLE");
    if (angle_probe && *angle_probe) {
        const double value = std::strtod(angle_probe, nullptr);
        if (std::isfinite(value) && value >= 0.0 && value <= 1.0) {
            effective.angle_control = value;
            log("STL_EXPORT_ANGLE_OVERRIDE=%g\n", value);
        }
    }
    // Diagnostic gate for the parameter-space refinement; the public export
    // still uses the built-in defaults.
    const char *refine_min_probe = std::getenv("MECHDOG_STL_REFINE_MIN");
    if (refine_min_probe && *refine_min_probe) {
        const double value = std::strtod(refine_min_probe, nullptr);
        if (std::isfinite(value) && value >= 0.0) {
            effective.refine_min_facets = static_cast<std::uint64_t>(value);
            log("STL_EXPORT_REFINE_MIN_OVERRIDE=%g\n", value);
        }
    }
    const char *refine_max_probe = std::getenv("MECHDOG_STL_REFINE_MAX");
    if (refine_max_probe && *refine_max_probe) {
        const double value = std::strtod(refine_max_probe, nullptr);
        if (std::isfinite(value) && value >= 1.0) {
            effective.refine_max_output_facets = static_cast<std::uint64_t>(value);
            log("STL_EXPORT_REFINE_MAX_OVERRIDE=%g\n", value);
        }
    }
    const char *refine_rounds_probe = std::getenv("MECHDOG_STL_REFINE_ROUNDS");
    if (refine_rounds_probe && *refine_rounds_probe) {
        const double value = std::strtod(refine_rounds_probe, nullptr);
        if (std::isfinite(value) && value >= 0.0 && value <= 16.0) {
            effective.refine_max_rounds = static_cast<int>(value);
            log("STL_EXPORT_REFINE_ROUNDS_OVERRIDE=%g\n", value);
        }
    }
    const char *refine_vertices_probe = std::getenv("MECHDOG_STL_REFINE_VERTICES");
    if (refine_vertices_probe && *refine_vertices_probe) {
        const double value = std::strtod(refine_vertices_probe, nullptr);
        if (std::isfinite(value) && value >= 0.0) {
            effective.refine_max_new_vertices = static_cast<std::uint64_t>(value);
            log("STL_EXPORT_REFINE_VERTICES_OVERRIDE=%g\n", value);
        }
    }
    const char *trace_probe = std::getenv("MECHDOG_STL_TRACE");
    if (trace_probe && *trace_probe == '1')
        stl_surface_detail::trace_hook = [](const char *text) { log("STL_TRACE %s\n", text); };
    const char *official_probe = std::getenv("MECHDOG_STL_OFFICIAL_FILE");
    if (official_probe && *official_probe == '1')
        effective.method = StlExportMethod::official_file;
    J result;
    std::string failure;
    if (effective.method == StlExportMethod::per_surface) {
        log("STL_EXPORT_METHOD=per_surface\n");
        const StlPerSurfaceReport report =
            write_stl_per_surface(model, std::filesystem::path(destination),
                                  std::filesystem::path(generic_job + L"\\staging"), staging_name,
                                  effective, scale.known ? scale.scale : 0.0);
        result = stl_per_surface_report_json(report);
        if (!report.success) {
            failure = "STL export failed";
            if (!report.error.empty())
                failure += ": " + report.error;
            else if (!report.file_error.empty())
                failure += " during file validation: " + report.file_error;
            else
                failure += " at " + report.failed_stage + " (code " +
                           std::to_string(static_cast<int>(report.failed_code)) + ")";
        } else {
            log("STL_EXPORT_END facets=%llu bytes=%llu surfaces=%llu\n",
                static_cast<unsigned long long>(report.file.facet_count),
                static_cast<unsigned long long>(report.file.bytes),
                static_cast<unsigned long long>(report.surface_count));
        }
    } else {
        log("STL_EXPORT_METHOD=official_file\n");
        const StlExportReport report =
            write_stl_file(model, std::filesystem::path(destination),
                           std::filesystem::path(generic_job + L"\\staging"), staging_name,
                           effective, scale.known ? scale.scale : 0.0);
        result = stl_export_report_json(report);
        if (!report.success) {
            failure = "STL export failed";
            if (!report.error.empty())
                failure += ": " + report.error;
            else if (!report.file_error.empty())
                failure += " during file validation: " + report.file_error;
            else
                failure += " with code " + std::to_string(static_cast<int>(report.api_code));
        } else {
            log("STL_EXPORT_END facets=%llu bytes=%llu\n",
                static_cast<unsigned long long>(report.file.facet_count),
                static_cast<unsigned long long>(report.file.bytes));
        }
    }
    result["length_unit"] = length_unit_json(units, scale);
    log("STL_EXPORT_REPORT=%s\n", result.dump().c_str());
    if (!failure.empty()) {
        stage_operation_result({{"stl_export", result}});
        throw std::runtime_error(failure);
    }
    return result;
}
static void generic_pattern(const J &op) {
    ProFeature leader = feature(op["feature"]);
    ProElement root = node(nullptr, PRO_E_PATTERN_ROOT);
    integer(root, PRO_E_GENPAT_TYPE, PRO_GENPAT_DIM_DRIVEN);
    integer(root, PRO_E_GENPAT_REGEN_METHOD, PRO_PAT_GENERAL);
    ProElement dims = node(root, PRO_E_GENPAT_DIM), dir = node(dims, PRO_E_GENPAT_DIM_FIRST_DIR),
               item = node(dir, PRO_E_GENPAT_DIM_DIR_COMPOUND);
    ProSelection d = resolve({{"kind", "dimension"}, {"id", op["dimension_id"]}});
    ref(item, PRO_E_GENPAT_DIR_DIMENSION, d);
    ProSelectionFree(&d);
    integer(item, PRO_E_GENPAT_DIR_VAR_TYPE, PRO_PAT_VALUE_DRIVEN);
    real(item, PRO_E_GENPAT_DIR_VAR_VALUE, op["increment"]);
    integer(dims, PRO_E_GENPAT_DIM_FIRST_DIR_NUM_INST, op["count"]);
    CK(ProPatternCreate(&leader, PRO_FEAT_PATTERN, root));
    CK(ProElementFree(&root));
    ProPattern pat;
    ProFeature head;
    CK(ProFeaturePatternGet(&leader, PRO_FEAT_PATTERN, &pat));
    CK(ProPatternHeaderGet(&pat, &head));
    ProName name;
    wcscpy_s(name, wide(op["label"]).c_str());
    CK(ProModelitemNameSet(&head, name));
    remember(op, head, {{"leader_id", leader.id}});
}
static J populate_profile(ProSection section, const J &op) {
    J entities_spec = op.at("profile");
    Frame frame = {};
    frame.n = {0, 0, 1};
    frame.u = {1, 0, 0};
    ProMatrix loc = {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 1, 0}, {0, 0, 0, 1}};
    const bool mirrored = dot(V{loc[2][0], loc[2][1], loc[2][2]}, frame.n) < 0;
    arc_endpoint_swapped.clear();
    arc_logical_swapped.clear();
    auto project = [](const J &p, double *out) {
        out[0] = p.at(0).get<double>();
        out[1] = p.at(1).get<double>();
    };
    CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    Pro2dCoordSysdef cs = {};
    cs.type = PRO_2D_COORD_SYS;
    int csid;
    CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&cs, &csid));
    std::map<std::string, int> entities;
    auto add_line = [&](const std::string &name, const J &a, const J &b, bool centerline,
                        bool construction) {
        Pro2dLinedef l = {};
        l.type = centerline ? PRO_2D_CENTER_LINE : PRO_2D_LINE;
        project(a, l.end1);
        project(b, l.end2);
        log("LINE_%s=%.9f,%.9f -> %.9f,%.9f\n", name.c_str(), l.end1[0], l.end1[1], l.end2[0],
            l.end2[1]);
        int id;
        CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&l, &id));
        if (!centerline)
            CK(ProSectionEntityConstructionSet(section, id,
                                               construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    };
    for (auto e : entities_spec) {
        std::string type = e.at("type"), name = e.at("name");
        bool construction = e.value("construction", false);
        int id = -1;
        if (type == "line" || type == "centerline") {
            add_line(name, e["start"], e["end"], type == "centerline", construction);
            continue;
        }
        if (type == "rectangle" || type == "polyline") {
            J points;
            if (type == "rectangle") {
                auto a = e["min"], b = e["max"];
                points = J::array({a, J::array({b[0], a[1]}), b, J::array({a[0], b[1]})});
            } else
                points = e["points"];
            int count = (int)points.size(),
                segments = count - 1 + ((type == "rectangle" || e.value("closed", false)) ? 1 : 0);
            for (int i = 0; i < segments; i++)
                add_line(name + "_" + std::to_string(i), points[i], points[(i + 1) % count], false,
                         construction);
            continue;
        }
        if (type == "circle") {
            Pro2dCircledef c = {};
            c.type = PRO_2D_CIRCLE;
            project(e["center"], c.center);
            c.radius = e["radius"];
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&c, &id));
        } else if (type == "arc") {
            Pro2dArcdef a = {};
            a.type = PRO_2D_ARC;
            project(e["center"], a.center);
            a.radius = e["radius"];
            double start = e["start_angle"].get<double>() * acos(-1.0) / 180,
                   end = e["end_angle"].get<double>() * acos(-1.0) / 180;
            double p[2], q[2];
            J center = e["center"];
            project(J::array({center[0].get<double>() + a.radius * cos(start),
                              center[1].get<double>() + a.radius * sin(start)}),
                    p);
            project(J::array({center[0].get<double>() + a.radius * cos(end),
                              center[1].get<double>() + a.radius * sin(end)}),
                    q);
            ArcRepresentation rep = arc_representation(
                atan2(p[1] - a.center[1], p[0] - a.center[0]),
                atan2(q[1] - a.center[1], q[0] - a.center[0]), arc_direction(e), mirrored);
            a.start_angle = rep.start_angle;
            a.end_angle = rep.end_angle;
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&a, &id));
            arc_endpoint_swapped[id] = rep.swapped;
            arc_logical_swapped[name] = rep.swapped;
        } else if (type == "spline") {
            auto points = e["points"];
            std::vector<std::array<double, 2>> xy(points.size());
            for (size_t i = 0; i < xy.size(); i++)
                project(points[i], xy[i].data());
            Pro2dSplinedef s = {};
            s.type = PRO_2D_SPLINE;
            s.tangency_type =
                e.value("closed", false) ? PRO_2D_SPLINE_TAN_PERIODIC : PRO_2D_SPLINE_TAN_NONE;
            s.n_points = (unsigned)xy.size();
            s.point_arr = (Pro2dPnt *)xy.data();
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&s, &id));
        } else if (type == "b_spline") {
            id = add_section_bspline(section, e, project);
        } else if (type == "ellipse") {
            Pro2dEllipsedef ell = {};
            ell.type = PRO_2D_ELLIPSE;
            project(e["center"], ell.origin);
            double align = fabs(dot(frame.u, V{loc[0][0], loc[0][1], loc[0][2]}));
            if (align > 0.99999) {
                ell.x_radius = e["x_radius"];
                ell.y_radius = e["y_radius"];
            } else if (align < 0.00001) {
                ell.x_radius = e["y_radius"];
                ell.y_radius = e["x_radius"];
            } else
                throw std::runtime_error("Ellipse axes must align with the section axes");
            CK(ProSectionEntityAdd(section, (Pro2dEntdef *)&ell, &id));
        } else
            throw std::runtime_error("Unknown sketch entity type");
        CK(ProSectionEntityConstructionSet(section, id, construction ? PRO_B_TRUE : PRO_B_FALSE));
        entities[name] = id;
    }
    if (!op.value("constraints", J::array()).empty()) {
        CK(ProSectionIntentManagerModeSet(section, PRO_B_TRUE));
        std::map<std::string, ProConstraintType> ct = {
            {"coincident", PRO_CONSTRAINT_SAME_POINT},
            {"horizontal", PRO_CONSTRAINT_HORIZONTAL_ENT},
            {"vertical", PRO_CONSTRAINT_VERTICAL_ENT},
            {"point_on", PRO_CONSTRAINT_PNT_ON_ENT},
            {"tangent", PRO_CONSTRAINT_TANGENT_ENTS},
            {"perpendicular", PRO_CONSTRAINT_ORTHOG_ENTS},
            {"equal_radius", PRO_CONSTRAINT_EQUAL_RADII},
            {"parallel", PRO_CONSTRAINT_PARALLEL_ENTS},
            {"equal_length", PRO_CONSTRAINT_EQUAL_SEGMENTS},
            {"collinear", PRO_CONSTRAINT_COLLINEAR_LINES}};
        for (auto c : op["constraints"]) {
            std::vector<ProSelection> refs;
            for (auto r : c["refs"]) {
                ProSelection s = selected(section, entities.at(r["entity"].get<std::string>()),
                                          point_type(r.value("point", "whole")));
                refs.push_back(s);
            }
            int cid;
            ProError err = ProSectionConstraintCreate(section, refs.data(), (int)refs.size(),
                                                      ct.at(c["type"]), &cid);
            for (auto s : refs)
                ProSelectionFree(&s);
            if (err != PRO_TK_E_FOUND)
                check(err, "CreateSketchConstraint");
        }
        CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));
    }
    std::map<std::string, ProSecdimType> dt = {{"length", PRO_TK_DIM_LINE},
                                               {"radius", PRO_TK_DIM_RAD},
                                               {"diameter", PRO_TK_DIM_DIA},
                                               {"distance", PRO_TK_DIM_PNT_PNT},
                                               {"horizontal", PRO_TK_DIM_PNT_PNT_HORIZ},
                                               {"vertical", PRO_TK_DIM_PNT_PNT_VERT},
                                               {"line_distance", PRO_TK_DIM_LINE_LINE},
                                               {"angle", PRO_TK_DIM_LINES_ANGLE},
                                               {"arc_angle", PRO_TK_DIM_ARC_ANGLE},
                                               {"ellipse_x_radius", PRO_TK_DIM_ELLIPSE_X_RADIUS},
                                               {"ellipse_y_radius", PRO_TK_DIM_ELLIPSE_Y_RADIUS}};
    J dims = J::object();
    for (auto d : op.value("dimensions", J::array())) {
        std::vector<int> ids;
        std::vector<ProSectionPointType> senses;
        for (auto r : d["refs"]) {
            ids.push_back(entities.at(r["entity"].get<std::string>()));
            senses.push_back(logical_point(ids.back(), point_type(r.value("point", "whole"))));
        }
        double place[2];
        project(d["position"], place);
        int id;
        CK(ProSecdimCreate(section, ids.data(), senses.data(), (int)ids.size(), dt.at(d["type"]),
                           place, &id));
        CK(ProSecdimValueSet(section, id, d["value"]));
        dims[d["name"].get<std::string>()] = id;
    }

    J solver_info = solve_profile(section, op);
    J ids = J::object();
    for (auto item : entities)
        ids[item.first] = item.second;
    return {{"entity_ids", ids}, {"dimension_ids", dims}, {"solver", solver_info}};
}
#include "component_transform.h"
// R05 (BUG-045/FEAT-012): the assembly receipt serializes the transform it just
// read back, so the row-major matrix helper is forward declared for advanced.cpp.
static J matrix_json(const ProMatrix matrix);
// Result split helpers are defined after the feature modules; forward declared
// here so component sources can resolve controlled detail references (BUG-077).
static J read_inspection_ref(const J &ref);
static J choice_inspection(const J &holder, const char *key);
#include "appearance.h"
#include "advanced.cpp"
#include "sheetmetal_candidates.cpp"
#include "surfaces.cpp"
#include "surface_trim.cpp"
#include "surface_group.cpp"
#include "surface_curvature.cpp"
#include "surface_loft_panel.h"
// BUG-120/D2: the curve-reference rules and their Toolkit adapter. Generic.cpp is
// the only compile unit with the Toolkit headers, so the adapter rides here.
#include "panel_references_sdk.h"
// BUG-120/D3: the selection protocol state machine. Pure C++, so it rides the same
// translation unit and is compiled against the real build configuration.
#include "panel_selection_state.h"
#include "surface_loft.cpp"
#include "surface_round.cpp"
#include "surface_boundary_fill.cpp"
#include "quilt_merge.cpp"
#include "project_curve.cpp"
#include "import_geometry.cpp"
#include "udf.cpp"
#include "loft_mode.cpp"
#include "loft_seed.cpp"
#include "blend_create.cpp"
// BUG-120/D3: the panel route's execution sequence. Included after blend_create.cpp
// because it reuses the resident-callback helpers defined there.
#include "panel_run.h"
#include "sketch_edit.cpp"
#include "planar_wall.h"
#include "planar_wall.cpp"
// DEV-089 T3: composed open-polyline base flange (planar wall + 90 degree
// flange). Included after planar_wall.cpp because it reuses that file's
// measured body, volume and envelope helpers.
#include "base_flange.cpp"
#include "placement.cpp"
#include "linear_pattern.cpp"
#include "feature_state.cpp"
// FEAT-053: three-point datum plane ({kind:'through_points'}). Each label names
// a datum_points feature contributing exactly one PRO_POINT; three non-collinear
// points determine the plane through three PRO_DTMPLN_THRU constraints. The
// points are read back and judged before creation with dimensionless ratios of
// their own spacings, so the verdict never depends on the absolute
// world-coordinate size (docs/work-items/FEAT-053.md), and the created plane is
// verified against the same points afterwards. The reported plane_frame is the
// real read-back frame; downstream work must use it instead of reconstructing
// a frame from the input (Q06).
static constexpr double kThruPointsDuplicateRatio = 1e-9;
static constexpr double kThruPointsCollinearRatio = 1e-6;
static constexpr double kThruPointsAlignTolerance = 1e-9;
static constexpr double kThruPointsDistanceFloorMm = 1e-6;
static constexpr double kThruPointsDistanceRatio = 1e-9;
struct ThruPointRef {
    std::string label;
    int feature_id;
    int point_id;
    V position;
};
static ThruPointRef resolve_through_point(const std::string &label) {
    ThruPointRef result;
    result.label = label;
    result.feature_id = feature_id(label);
    ProFeature f;
    CK(ProModelitemInit(board, result.feature_id, PRO_FEATURE, &f));
    ProFeattype type = {};
    CK(ProFeatureTypeGet(&f, &type));
    if (type != PRO_FEAT_DATUM_POINT)
        throw std::runtime_error("through_points label '" + label +
                                 "' does not identify a datum point feature");
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&f, PRO_POINT, collect_geom_ids, nullptr, &ids));
    if (ids.size() != 1)
        throw std::runtime_error("through_points label '" + label +
                                 "' must contain exactly one point (a single PRO_POINT); found " +
                                 std::to_string(ids.size()));
    result.point_id = ids[0]["id"].get<int>();
    ProPoint point;
    CK(ProPointInit((ProSolid)board, result.point_id, &point));
    ProVector coordinates;
    CK(ProPointCoordGet(point, coordinates));
    result.position = {coordinates[0], coordinates[1], coordinates[2]};
    for (double value : result.position)
        if (!std::isfinite(value))
            throw std::runtime_error("through_points label '" + label +
                                     "' has non-finite coordinates; cannot determine the plane");
    return result;
}
static J classify_through_points(const std::vector<ThruPointRef> &points) {
    V a = points[0].position, b = points[1].position, c = points[2].position;
    V ab = add(b, scale(a, -1)), bc = add(c, scale(b, -1)), ca = add(a, scale(c, -1));
    V ac = add(c, scale(a, -1));
    double sides[3] = {sqrt(dot(ab, ab)), sqrt(dot(bc, bc)), sqrt(dot(ca, ca))};
    double longest = std::max({sides[0], sides[1], sides[2]});
    double shortest = std::min({sides[0], sides[1], sides[2]});
    if (!(longest > 0) || !std::isfinite(longest))
        throw std::runtime_error("through_points cannot determine the plane: the three "
                                 "read-back points do not span a measurable triangle");
    V normal = cross(ab, ac);
    double min_altitude = sqrt(dot(normal, normal)) / longest;
    if (shortest <= kThruPointsDuplicateRatio * longest)
        throw std::runtime_error("through_points refuses repeated points: two of the three "
                                 "read-back points coincide within tolerance");
    if (min_altitude <= kThruPointsCollinearRatio * longest)
        throw std::runtime_error("through_points refuses nearly collinear points: the three "
                                 "read-back points do not determine a unique plane");
    return {{"classification", "ok"},
            {"sides", J::array({sides[0], sides[1], sides[2]})},
            {"longest_side", longest},
            {"min_altitude", min_altitude},
            {"min_altitude_ratio", min_altitude / longest},
            {"duplicate_ratio_tolerance", kThruPointsDuplicateRatio},
            {"collinear_altitude_ratio_tolerance", kThruPointsCollinearRatio}};
}
static J through_points_plane(const J &op) {
    const J &reference = op.at("reference");
    const J &labels = reference.at("points");
    if (!labels.is_array() || labels.size() != 3)
        throw std::runtime_error(
            "through_points requires exactly 3 datum_points feature "
            "labels ({kind:'through_points',points:[label_a,label_b,label_c]})");
    if (op.contains("angle") || op.contains("axis") || fabs(op.value("offset", 0.0)) > 1e-9)
        throw std::runtime_error("datum_plane {kind:'through_points'} is fully determined by "
                                 "its three points and cannot be combined with angle, axis or "
                                 "a nonzero offset");
    auto units = inspect_length_units(board);
    MillimeterScale unit_scale = length_scale_to_mm(board, units);
    if (!unit_scale.known)
        throw std::runtime_error("through_points cannot determine the model length unit; "
                                 "cannot verify the three points, refusing to build the plane");
    std::vector<ThruPointRef> points;
    std::set<std::string> seen_labels;
    for (const auto &entry : labels) {
        std::string label = entry.get<std::string>();
        if (!seen_labels.insert(label).second)
            throw std::runtime_error("through_points refuses repeated point labels: " + label);
        ThruPointRef point = resolve_through_point(label);
        for (double &value : point.position)
            value *= unit_scale.scale;
        points.push_back(point);
    }
    J precheck = classify_through_points(points);
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op.at("label")).c_str());
    ProElement constraints = node(root, PRO_E_DTMPLN_CONSTRAINTS);
    for (const auto &point : points) {
        ProElement c = node(constraints, PRO_E_DTMPLN_CONSTRAINT);
        integer(c, PRO_E_DTMPLN_CONSTR_TYPE, PRO_DTMPLN_THRU);
        ProSelection s = selection(point.point_id, PRO_POINT);
        ref(c, PRO_E_DTMPLN_CONSTR_REF, s);
        ProSelectionFree(&s);
    }
    if (op.value("flip", false))
        integer(root, PRO_E_DTMPLN_FLIP_DIR, PRO_DTMPLN_FLIP_DIR_YES);
    ProFeature f = create(root);
    CK(ProElementFree(&root));
    remember(op, f);
    J points_json = J::array();
    for (const auto &point : points) {
        points_json.push_back({{"label", point.label},
                               {"feature_id", point.feature_id},
                               {"point_id", point.point_id},
                               {"position", xyz(point.position.data())}});
    }
    planes.clear();
    CK(ProFeatureGeomitemVisit(&f, PRO_SURFACE, geom_cb, nullptr, nullptr));
    if (planes.size() != 1) {
        stage_operation_result({{"mode", "through_points"}, {"precheck", precheck}});
        throw std::runtime_error("through_points verification failed: the created feature "
                                 "must own exactly one plane surface; found " +
                                 std::to_string(planes.size()));
    }
    const Plane &surface = planes[0];
    V normal = normalized(V{surface.n[0], surface.n[1], surface.n[2]});
    V origin = {surface.o[0] * unit_scale.scale, surface.o[1] * unit_scale.scale,
                surface.o[2] * unit_scale.scale};
    double longest = precheck["longest_side"].get<double>();
    double distance_tolerance =
        std::max(kThruPointsDistanceFloorMm, kThruPointsDistanceRatio * longest);
    J distances = J::array();
    double max_distance = 0;
    for (const auto &point : points) {
        double distance = fabs(dot(add(point.position, scale(origin, -1)), normal));
        distances.push_back(distance);
        max_distance = std::max(max_distance, distance);
    }
    V ab = add(points[1].position, scale(points[0].position, -1));
    V ac = add(points[2].position, scale(points[0].position, -1));
    double alignment = dot(normal, normalized(cross(ab, ac)));
    ProElement tree = nullptr;
    CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree));
    // BUG-098: reading each constraint's type/reference through
    // ProElemtreeElementGet/ProElementReferenceGet blocked this machine's
    // Toolkit on a freshly created datum plane, so the live path counts the
    // array only and reports the per-reference evidence as unavailable instead
    // of hanging the channel. The creation tree already carries exactly three
    // PRO_DTMPLN_THRU selections; schema and the offline driver verify labels.
    ProElempath constraints_path = nullptr;
    CK(ProElempathAlloc(&constraints_path));
    ProElempathItem constraints_item = {};
    constraints_item.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
    constraints_item.path_item.elem_id = (ProElemId)PRO_E_DTMPLN_CONSTRAINTS;
    CK(ProElempathDataSet(constraints_path, &constraints_item, 1));
    int constraint_total = -1;
    ProError count_code = ProElementArrayCount(tree, constraints_path, &constraint_total);
    ProElempathFree(&constraints_path);
    ProFeatureElemtreeFree(&f, tree);
    bool constraints_ok = count_code == PRO_TK_NO_ERROR && constraint_total == 3;
    bool distances_ok = max_distance <= distance_tolerance;
    bool alignment_ok = fabs(fabs(alignment) - 1) <= kThruPointsAlignTolerance;
    J verification = {
        {"point_distances", distances},
        {"max_point_distance", max_distance},
        {"distance_tolerance", distance_tolerance},
        {"normal_alignment", alignment},
        {"alignment_tolerance", kThruPointsAlignTolerance},
        {"constraint_count", constraint_total},
        {"constraint_count_status",
         {{"available", count_code == PRO_TK_NO_ERROR},
          {"query_code", (int)count_code},
          {"expected", 3}}},
        {"constraints", J::array()},
        {"references_ok", nullptr},
        {"references_status",
         {{"available", false},
          {"reason", "reference_element_query_deferred_after_bug098"},
          {"detail",
           "ProElemtreeElementGet/ProElementReferenceGet blocked the channel on a fresh datum "
           "plane; only the constraint array count is queried"}}},
        {"verified", distances_ok && alignment_ok && constraints_ok}};
    J details = {{"mode", "through_points"},
                 {"plane_frame",
                  {{"surface_id", surface.id},
                   {"normal", xyz(normal.data())},
                   {"origin", xyz(origin.data())},
                   {"length_unit", length_unit_json(units, unit_scale)}}},
                 {"points", points_json},
                 {"precheck", precheck},
                 {"verification", verification}};
    if (!distances_ok || !alignment_ok || !constraints_ok) {
        stage_operation_result(details);
        std::string reason = !distances_ok   ? "a point does not lie on the created plane"
                             : !alignment_ok ? "the normal is not equivalent to the point-leg "
                                               "cross product"
                                             : "the created feature does not own exactly three "
                                               "datum-plane constraints";
        throw std::runtime_error("through_points verification failed: " + reason);
    }
    return details;
}
static void execute_operation_body(const J &op) {
    std::string kind = op.at("op");
    J details = J::object();
    staged_operation_result = J::object();
    has_staged_operation_result = false;
    // FEAT-051: round/chamfer/draft carry per-operation material evidence. The
    // quilt round is included so a surface-only result reports
    // material_measurement=not_applicable instead of omitting the field.
    const bool additive_op =
        (kind == "extrude" || kind == "revolve" || kind == "sweep" || kind == "loft") &&
        op.value("mode", "add") == "add";
    const bool material_op = additive_op || kind == "round" || kind == "chamfer" ||
                             kind == "draft" || kind == "surface_round";
    const bool had_solid = additive_op && model_has_solid();
    material_probe_active = material_op;
    material_probe_before = VolumeProbe{};
    if (material_op)
        material_probe_before = probe_volume();
    log("PHASE=%s%s%s\n", kind.c_str(), op.contains("label") ? ":" : "",
        op.value("label", "").c_str());
    if (kind == "sketch" || kind == "airfoil_sketch")
        details = sketch(op);
    else if (kind == "update_sketch_geometry" || kind == "update_airfoil")
        generic_sketch_edit(op);
    else if (kind == "feature_group")
        generic_group(op);
    else if (kind == "reorder_features")
        generic_reorder(op);
    else if (kind == "feature_state")
        details = generic_feature_state(op);
    else if (kind == "axis_pattern")
        generic_axis_pattern(op);
    else if (kind == "linear_pattern")
        generic_linear_pattern(op);
    else if (kind == "geometry_transform")
        generic_transform(op);
    else if (kind == "set_geometry_transform")
        generic_transform_update(op);
    else if (kind == "extrude" || kind == "revolve")
        details = extrude_or_revolve(op, kind == "revolve");
    else if (kind == "hole")
        details = generic_hole(op);
    else if (kind == "round" || kind == "chamfer")
        details = generic_round(op, kind == "chamfer");
    else if (kind == "shell")
        details = generic_shell(op);
    else if (kind == "dimension_pattern")
        generic_pattern(op);
    else if (kind == "mirror")
        details = generic_mirror(op);
    else if (kind == "draft")
        details = generic_draft(op);
    else if (kind == "sweep")
        generic_sweep(op);
    else if (kind == "loft")
        generic_loft(op);
    else if (kind == "udf_inspect" || kind == "udf_create")
        generic_udf(op);
    else if (kind == "datum_csys")
        generic_csys(op);
    else if (kind == "datum_points")
        generic_points(op);
    else if (kind == "surface_fill")
        generic_fill(op);
    else if (kind == "thicken" || kind == "solidify")
        generic_surface_solid(op);
    else if (kind == "redefine_solidify_body")
        // FEAT-070: rebuild an invalid body reference on an existing
        // solidify/patch feature; returns a repair receipt as details.
        details = generic_redefine_solidify_body(op);
    else if (kind == "surface_offset")
        generic_surface_offset(op);
    else if (kind == "surface_trim")
        generic_surface_trim(op);
    else if (kind == "surface_loft") {
        // BUG-120/D1: creation_route names the backend. An explicit panel request
        // never falls back to the element tree, because only the panel route is
        // expected to complete on a host whose kernel refuses the tree readback.
        std::string route = "element_tree";
        auto route_it = op.find("creation_route");
        if (route_it != op.end() && route_it->is_string())
            route = route_it->get<std::string>();
        // Only an absent field falls back to the element tree. An unrecognised
        // route is refused, because silently building the tree is exactly the
        // fallback BUG-120 rules out.
        if (route == "element_tree")
            generic_surface_loft(op);
        else if (route == "resident_panel")
            generic_surface_loft_panel(op);
        else
            throw std::runtime_error(
                "SURFACE_LOFT_UNKNOWN_ROUTE: creation_route must be element_tree or "
                "resident_panel; no feature was created and the request was not retried on "
                "another route.");
    } else if (kind == "surface_boundary_fill")
        generic_surface_boundary_fill(op);
    else if (kind == "surface_round")
        generic_surface_round(op);
    else if (kind == "surface_group_measure")
        generic_surface_group_measure(op);
    else if (kind == "surface_curvature")
        generic_surface_curvature(op);
    else if (kind == "quilt_merge")
        generic_quilt_merge(op);
    else if (kind == "project_curve")
        generic_project_curve(op);
    else if (kind == "import_geometry")
        generic_import_geometry(op);
    else if (kind == "boolean_bodies")
        generic_boolean(op);
    else if (kind == "rib")
        generic_rib(op);
    else if (kind == "sheetmetal_wall")
        generic_sheetmetal_wall(op);
    else if (kind == "sheetmetal_planar_wall")
        generic_sheetmetal_planar_wall(op);
    else if (kind == "resize_sheetmetal_planar_wall")
        generic_resize_sheetmetal_planar_wall(op);
    else if (kind == "sheetmetal_base_flange")
        generic_sheetmetal_base_flange(op);
    else if (kind == "sheetmetal_flange" || kind == "sheetmetal_flange_profile")
        generic_sheetmetal_flange(op);
    else if (kind == "sheetmetal_corner_relief")
        generic_sheetmetal_corner_relief(op);
    else if (kind == "sheetmetal_quilt_form")
        generic_sheetmetal_quilt_form(op);
    else if (kind == "sheetmetal_unbend" || kind == "sheetmetal_flat_pattern" ||
             kind == "sheetmetal_bend_back")
        generic_sheetmetal_unbend(op);
    else if (kind == "assemble_component")
        assemble_component(op);
    else if (kind == "component_placement" || kind == "component_constraints" ||
             kind == "remove_component")
        modify_component(op);
    else if (kind == "recolor_assembly")
        recolor_assembly(op);
    else if (kind == "datum_plane") {
        const J &plane_reference = op.at("reference");
        std::string plane_ref_kind = plane_reference.is_object() &&
                                             plane_reference.contains("kind") &&
                                             plane_reference["kind"].is_string()
                                         ? plane_reference["kind"].get<std::string>()
                                         : std::string();
        // FEAT-053 backstops; the Python contract rejects these first. The
        // external 0.10.0 spellings must be converted to the explicit form
        // instead of being forwarded to the executor.
        if (plane_reference.is_object() && plane_reference.contains("thru_points"))
            throw std::runtime_error(
                "datum_plane three-point references require the explicit form "
                "{kind:'through_points',points:[label_a,label_b,label_c]}; the external "
                "{thru_points:[...]} spelling is rejected and must be converted first");
        if (plane_ref_kind == "datum_point_feature")
            throw std::runtime_error(
                "{kind:'datum_point_feature',label:...} is the executor-internal point "
                "selection, not a datum_plane reference; convert it to "
                "{kind:'through_points',points:[label_a,label_b,label_c]}");
        if (plane_ref_kind == "through_points") {
            details = through_points_plane(op);
        } else {
            double angle = op.value("angle", 0.0);
            // BUG-094 backstops; the Python PlaneOp contract rejects these first.
            if (op.contains("angle") && fabs(op.value("offset", 0.0)) > 1e-9)
                throw std::runtime_error(
                    "datum_plane cannot combine an explicit angle with a nonzero offset; the "
                    "angled constraint silently drops the offset. Submit two explicit "
                    "datum_plane operations instead");
            if (op.contains("angle")) {
                const J axis_ref = op.value("axis", J());
                std::string axis_kind = axis_ref.is_object() && axis_ref.contains("kind") &&
                                                axis_ref["kind"].is_string()
                                            ? axis_ref["kind"].get<std::string>()
                                            : std::string();
                if (axis_kind != "axis" && axis_kind != "datum_axis_feature")
                    throw std::runtime_error(
                        "An angled datum_plane requires axis {kind:'axis',id:N} or "
                        "{kind:'datum_axis_feature',label:'...'}; rejected: " +
                        (axis_kind.empty() ? std::string("(missing kind)") : axis_kind));
            }
            J axis = op.value("axis", J());
            auto f = offset_plane(op["reference"], op.value("offset", 0.0), wide(op["label"]),
                                  op.contains("angle") ? &angle : nullptr,
                                  op.contains("axis") ? &axis : nullptr, op.value("flip", false));
            remember(op, f);
        }
    } else if (kind == "datum_axis") {
        ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
        integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_AXIS);
        text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
        ProElement cs = node(root, PRO_E_DTMAXIS_CONSTRAINTS);
        for (auto r : op["references"]) {
            ProElement c = node(cs, PRO_E_DTMAXIS_CONSTRAINT);
            integer(c, PRO_E_DTMAXIS_CONSTR_TYPE, PRO_DTMAXIS_CONSTR_TYPE_THRU);
            ProSelection s = resolve(r);
            ref(c, PRO_E_DTMAXIS_CONSTR_REF, s);
            ProSelectionFree(&s);
        }
        ProFeature f = create(root);
        CK(ProElementFree(&root));
        remember(op, f);
        details = feature_axes(&f);
        auto units = inspect_length_units(board);
        details["length_unit"] = length_unit_json(units, length_scale_to_mm(board, units));
    } else if (kind == "set_dimensions") {
        std::vector<DimensionTarget> targets;
        targets.reserve(op["values"].size());
        for (const auto &value : op["values"])
            targets.push_back(read_dimension_target(board, value));
        check_dimension_targets(targets, op["values"]);
        for (auto &target : targets)
            CK(ProDimensionValueSet(&target.dim, target.requested));
        mark_sketch_geometry_stale();
    } else if (kind == "set_sketch_dimensions") {
        ProFeature f = feature(op["sketch"]);
        ProElement root = nullptr;
        CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
        const J *meta =
            op["sketch"].is_string() ? alias_entry(op["sketch"].get<std::string>()) : nullptr;
        J saved_path =
            meta ? meta->value("section_path", J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER}))
                 : J::array({PRO_E_STD_SECTION, PRO_E_SKETCHER});
        ProElement sk = get_path(root, saved_path);
        ProSection s = nullptr;
        CK(ProElementSpecialvalueGet(sk, nullptr, (ProAppData *)&s));
        J ids = meta ? meta->value("dimension_ids", J::object()) : J::object();
        for (auto it = op["values"].begin(); it != op["values"].end(); ++it) {
            int id = ids.contains(it.key()) ? ids[it.key()].get<int>() : std::stoi(it.key());
            CK(ProSecdimValueSet(s, id, it.value()));
        }
        ProWSecerror err = nullptr;
        CK(ProSecerrorAlloc(&err));
        CK(ProSectionRegenerate(s, &err));
        ProSecerrorFree(&err);
        CK(ProElementSpecialvalueSet(sk, (ProAppData)s));
        redefine(&f, root);
        CK(ProFeatureElemtreeFree(&f, root));
        // Numeric references and relations to other sketches need the same
        // invalidation as label-based edits.
        mark_sketch_geometry_stale();
    } else if (kind == "set_parameters") {
        parameters(op);
        mark_sketch_geometry_stale();
    } else if (kind == "set_relations") {
        ProModelitem owner;
        CK(ProMdlToModelitem(board, &owner));
        ProRelset rel;
        ProError e = ProModelitemToRelset(&owner, &rel);
        if (e == PRO_TK_E_NOT_FOUND)
            CK(ProRelsetCreate(&owner, &rel));
        else
            check(e, "GetRelations");
        std::vector<std::wstring> storage;
        for (auto line : op["lines"])
            storage.push_back(wide(line));
        std::vector<ProWstring> ptrs;
        for (auto &line : storage)
            ptrs.push_back(const_cast<wchar_t *>(line.c_str()));
        CK(ProRelsetRelationsSet(&rel, ptrs.data(), (int)ptrs.size()));
        CK(ProRelsetRegenerate(&rel));
        mark_sketch_geometry_stale();
    } else if (kind == "feature_tree") {
        ProElement root = tree_from_json(op["tree"]);
        ProFeature f = create(root);
        CK(ProElementFree(&root));
        remember(op, f);
    } else if (kind == "export") {
        if (op["format"] == "native_bundle") {
            if (!assembly_model())
                throw std::runtime_error("native_bundle requires an assembly");
            // The read-only Python finalizer copies only verified owned snapshots.
            // No Toolkit save, regeneration or source mutation occurs here.
            stage_operation_result({{"op", kind}, {"format", "native_bundle"}});
        } else {
            std::string format = op["format"], extension = format == "step"   ? ".stp"
                                                           : format == "stl"  ? ".stl"
                                                           : format == "iges" ? ".igs"
                                                                              : ".jpg";
            ProPath output;
            path(output, generic_job + L"\\output\\" + model_name + wide(extension));
            J export_result = {{"op", kind}, {"file", utf8(output)}};
            J stl_export;
            if (format == "jpeg") {
                // Same shared capture as the automatic job preview (T07). Unlike
                // that preview, this image is the requested operation result, so a
                // failed capture fails this input (recorded with the raw codes in
                // its single T02 result record) rather than the whole job silently
                // claiming an image it did not write.
                const J options = op.value("jpeg_options", J::object());
                const std::string view = options.value("view", "isometric");
                const int width = options.value("width_px", 800);
                const int height = options.value("height_px", 600);
                ProMatrix front = {{1, 0, 0, 0}, {0, 0, -1, 0}, {0, 1, 0, 0}, {0, 0, 0, 1}};
                ProMatrix back = {{-1, 0, 0, 0}, {0, 0, 1, 0}, {0, 1, 0, 0}, {0, 0, 0, 1}};
                ProMatrix top = {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 1, 0}, {0, 0, 0, 1}};
                ProMatrix bottom = {{1, 0, 0, 0}, {0, -1, 0, 0}, {0, 0, -1, 0}, {0, 0, 0, 1}};
                ProMatrix right = {{0, 0, 1, 0}, {1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 0, 1}};
                ProMatrix left = {{0, 0, -1, 0}, {-1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 0, 1}};
                ProMatrix custom = {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 1, 0}, {0, 0, 0, 1}};
                bool use_custom = false;
                if (options.contains("view_matrix") && options["view_matrix"].is_array() &&
                    options["view_matrix"].size() == 3) {
                    use_custom = true;
                    for (int r = 0; r < 3; r++) {
                        for (int c = 0; c < 3; c++)
                            custom[r][c] = options["view_matrix"][r][c].get<double>();
                        custom[r][3] = 0.0;
                    }
                    custom[3][0] = custom[3][1] = custom[3][2] = 0.0;
                    custom[3][3] = 1.0;
                }
                auto matrix = use_custom         ? custom
                              : view == "front"  ? front
                              : view == "back"   ? back
                              : view == "top"    ? top
                              : view == "bottom" ? bottom
                              : view == "right"  ? right
                              : view == "left"   ? left
                                                 : preview_isometric_view;
                PreviewStepOutcome preview = capture_preview(
                    board, generic_job + L"\\output\\" + model_name + wide(extension), true,
                    width / 100.0, height / 100.0, PRORASTERTYPE_JPEG, matrix);
                J preview_json = preview_outcome_json(preview);
                preview_json["requested_view"] = use_custom ? "custom_matrix" : view;
                if (use_custom)
                    preview_json["requested_view_matrix"] = options["view_matrix"];
                preview_json["requested_size_px"] = {width, height};
                log("PREVIEW=%s\n", preview_json.dump().c_str());
                export_result["preview_code"] = preview.raster_code;
                export_result["preview"] = std::move(preview_json);
                if (!preview_written(preview)) {
                    stage_operation_result(export_result);
                    throw std::runtime_error(
                        "Preview capture failed at " + preview.failed_step + " (code " +
                        std::to_string(preview.failed_code) + ", raster code " +
                        std::to_string(preview.raster_code) + "): " + utf8(preview.path));
                }
            } else if (format == "stl") {
                // BUG-130 Task 6: the validated plan may carry an explicit
                // quality request; otherwise the historical defaults apply.
                StlExportOptions stl_options;
                if (op.contains("stl_options") && op["stl_options"].is_object()) {
                    const J &requested = op["stl_options"];
                    if (requested.contains("chord_height_mm") &&
                        requested["chord_height_mm"].is_number())
                        stl_options.chord_height_mm = requested["chord_height_mm"].get<double>();
                    if (requested.contains("angle_control") &&
                        requested["angle_control"].is_number())
                        stl_options.angle_control = requested["angle_control"].get<double>();
                }
                stl_export = write_stl(board, output, stl_options);
            } else {
                ProIntf3DExportType t =
                    format == "step" ? PRO_INTF_EXPORT_STEP : PRO_INTF_EXPORT_IGES;
                CK(ProIntf3DFileWriteWithDefaultProfile((ProSolid)board, t, output));
            }
            if (!stl_export.is_null())
                export_result["stl_export"] = stl_export;
            stage_operation_result(export_result);
        }
    } else if (kind == "dump_tree") {
        ProFeature f = feature(op["feature"]);
        ProElement root;
        CK(ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &root));
        ProPath output;
        path(output, generic_job + L"\\output\\feature_" + std::to_wstring(f.id) + L".xml");
        CK(ProElemtreeWrite(root, PRO_ELEMTREE_XML, output));
        CK(ProFeatureElemtreeFree(&f, root));
        stage_operation_result({{"op", kind}, {"file", utf8(output)}});
    } else if (kind == "mass_properties") {
        stage_operation_result({{"op", kind}, {"mass_properties", mass_properties_json(op)}});
    } else if (kind != "regenerate" && kind != "save")
        throw std::runtime_error("Operation is not implemented: " + kind);
    if (kind != "export" && kind != "dump_tree" && kind != "udf_inspect" &&
        kind != "mass_properties" && kind != "surface_group_measure" && kind != "surface_curvature")
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    const bool needs_full_post_state =
        has_staged_operation_result &&
        staged_operation_result.value("creation_route", std::string()) == "resident_panel";
    bool post_has_solid = false;
    if (needs_full_post_state) {
        J post_state = inspection();
        // BUG-120 task 3: a panel loft names the feature and quilt it just created by
        // comparing this model before the dialog with the model after the operation.
        panel_attach_post_operation_geometry(staged_operation_result, post_state);
        post_has_solid = post_state["has_solid"].get<bool>();
    } else {
        check_model_health();
        if (material_op)
            post_has_solid = model_has_solid();
    }
    // One terminal record for this input. Branch details and the staged detail
    // are merged here; effect_status stays unknown until the job-level
    // finalizer knows whether the save committed or the rollback restored the
    // verified baseline (T02).
    J result = has_staged_operation_result ? staged_operation_result : J::object();
    result.update(details);
    // BUG-169: every feature-creating operation that registered itself via
    // remember(op, f) publishes its own feature_id directly in its operation
    // record so callers never observe feature_id=null while aliases has the id.
    if (op.contains("label") && op["label"].is_string() && !result.contains("feature_id")) {
        if (const J *entry = alias_entry(op["label"].get<std::string>())) {
            if (entry->value("op", "") == kind && entry->contains("feature_id") &&
                entry->at("feature_id").is_number_integer())
                result["feature_id"] = entry->at("feature_id");
        }
    }
    if (material_op) {
        J mat = material_observation_json(material_probe_before, true, probe_volume(),
                                          !post_has_solid && !additive_op);
        result.update(mat);
        if (additive_op)
            verify_add_volume(result, had_solid, post_has_solid);
        if (kind == "round") {
            const J &delta = mat["material_delta_mm3"];
            result["volume_delta_mm3"] = delta;
            std::string round_kind = "unknown";
            if (delta.is_number()) {
                const double dv = delta.get<double>();
                round_kind = dv < -1e-6 ? "convex" : (dv > 1e-6 ? "concave" : "neutral");
            }
            result["round_kind"] = round_kind;
            const std::string expected_kind =
                op.contains("expected_round_kind") && op["expected_round_kind"].is_string()
                    ? op["expected_round_kind"].get<std::string>()
                    : "";
            const std::string expected_sign =
                op.contains("expected_material_delta_sign") &&
                        op["expected_material_delta_sign"].is_string()
                    ? op["expected_material_delta_sign"].get<std::string>()
                    : "";
            bool mismatch = false;
            if (!expected_kind.empty() && round_kind != expected_kind)
                mismatch = true;
            if (!expected_sign.empty()) {
                if (!delta.is_number())
                    mismatch = true;
                else if (expected_sign == "negative" && !(delta.get<double>() < -1e-6))
                    mismatch = true;
                else if (expected_sign == "positive" && !(delta.get<double>() > 1e-6))
                    mismatch = true;
            }
            if (mismatch) {
                J diag = {{"round_kind", round_kind}, {"material_delta_mm3", delta}};
                J edge_diags = diagnose_round_edges(op.at("references"), inspect_mm_scale);
                if (!edge_diags.empty())
                    diag["edge_diagnostics"] = edge_diags;
                stage_operation_result({{"round_kind", round_kind},
                                        {"material_delta_mm3", delta},
                                        {"volume_delta_mm3", delta},
                                        {"round_failure", diag}});
                std::string msg = "round expectation failed: measured round_kind=" + round_kind +
                                  ", material_delta_mm3=" + delta.dump();
                if (!expected_kind.empty())
                    msg += ", expected_round_kind=" + expected_kind;
                if (!expected_sign.empty())
                    msg += ", expected_material_delta_sign=" + expected_sign;
                if (!edge_diags.empty()) {
                    const J &e0 = edge_diags[0];
                    if (e0.contains("dihedral_angle_deg"))
                        msg += " (edge " + std::to_string(e0.value("edge_id", -1)) +
                               " dihedral_deg=" +
                               std::to_string(e0["dihedral_angle_deg"].get<double>()) + ")";
                }
                throw std::runtime_error(msg);
            }
        }
    }
    result.update({{"op", kind},
                   {"index", operation_position},
                   {"label", op.value("label", "")},
                   {"succeeded", true},
                   {"execution_status", "succeeded"},
                   {"effect_status", "unknown"}});
    append_operation_result(std::move(result));
}
// A failing operation still yields exactly one terminal record: execution is
// failed and the job finalizer decides the effect from real rollback evidence.
static void execute_operation(const J &op) {
    material_probe_active = false;
    material_probe_before = VolumeProbe{};
    // BUG-097 L2: the structured CompleteFeature receipt belongs to the
    // operation that produced it; clear per operation so a later failure can
    // never publish a stale report from an earlier one.
    last_feature_error_report = nullptr;
    try {
        execute_operation_body(op);
    } catch (...) {
        std::exception_ptr error = std::current_exception();
        std::string kind = op.at("op");
        J failure = has_staged_operation_result ? staged_operation_result : J::object();
        // Earlier failures retain the before probe. A guard failure already
        // staged both measurements and must keep the observed after state.
        if (material_probe_active && !failure.contains("material_measurement"))
            failure.update(
                material_observation_json(material_probe_before, false, VolumeProbe{}, false));
        if (!last_feature_error_report.is_null())
            failure["feature_errors"] = last_feature_error_report;
        failure.update({{"op", kind},
                        {"index", operation_position},
                        {"label", op.value("label", "")},
                        {"succeeded", false},
                        {"execution_status", "failed"},
                        {"effect_status", "unknown"}});
        // DEV-093 T4: repeat the measured axis/plane numbers in the message so a
        // revolve refusal is diagnosable without opening the operation record.
        // Nothing is appended when the relation could not be measured.
        const std::string plane_relation =
            has_staged_operation_result
                ? revolve_axis_plane_relation_text(
                      staged_operation_result.value("revolve_axis_plane_relation", J::object()))
                : std::string();
        append_operation_result(std::move(failure));
        if (plane_relation.empty())
            std::rethrow_exception(error);
        throw std::runtime_error(native_exception_text(error) + plane_relation);
    }
}
// Close the per-operation records against the request. Success marks the
// operations that actually ran as committed (a successful save/reload advanced
// the revision; read-only jobs confirm no model write instead). Failure keeps
// the executed/failed records and appends the operations that were never
// started as not_executed/no_effect. rolled_back is only used when the native
// rollback restored and verified the saved baseline. BUG-114: a cleanup-proven
// new-model erasure releases only the managed-model effect of operations that
// do not write external files; external outputs (export/dump_tree) keep
// unknown, because erasing the session model never deletes them. Without
// either proof the effect stays unknown and is never inferred from the job
// status alone.
static bool operation_writes_external_outputs(const std::string &kind) {
    return kind == "export" || kind == "dump_tree";
}

static bool cleanup_clears_managed_effect(const J &report) {
    if (!report.contains("failed_model_cleanup") || !report["failed_model_cleanup"].is_object())
        return false;
    const J &receipt = report["failed_model_cleanup"];
    if (!receipt.value("attempted", false) || receipt.value("status", std::string()) != "erased" ||
        receipt.value("reason", std::string()) != "cleaned" ||
        !receipt.value("absence_verified", false))
        return false;
    // A bare erase code is not enough: only the full cleaned shape qualifies.
    return receipt.contains("erase_code") && receipt["erase_code"].is_number_integer() &&
           receipt["erase_code"].get<int>() == 0;
}

static void finalize_operation_results(const J &request, bool succeeded, bool rolled_back,
                                       bool readonly, bool cleanup_confirmed) {
    if (succeeded) {
        for (auto &item : operation_results)
            if (item.value("execution_status", "unknown") == "succeeded")
                item["effect_status"] = readonly ? "no_effect" : "committed";
        return;
    }
    for (auto &item : operation_results) {
        std::string execution = item.value("execution_status", "unknown");
        if (execution == "not_executed")
            item["effect_status"] = "no_effect";
        else if (execution == "succeeded" || execution == "failed") {
            if (rolled_back)
                item["effect_status"] = "rolled_back";
            else if (cleanup_confirmed &&
                     !operation_writes_external_outputs(item.value("op", std::string())))
                item["effect_status"] = "no_effect";
            else
                item["effect_status"] = "unknown";
        }
    }
    int count = request.contains("operations") && request["operations"].is_array()
                    ? (int)request["operations"].size()
                    : 0;
    for (int index = (int)operation_results.size(); index < count; index++) {
        const J &input = request["operations"][index];
        J entry = {{"op", input.value("op", "")},        {"index", index},
                   {"label", input.value("label", "")},  {"succeeded", false},
                   {"execution_status", "not_executed"}, {"effect_status", "no_effect"}};
        append_operation_result(std::move(entry));
    }
}
// FEAT-067: the millimetre bounding box of the material bodies, taken from the
// per-body outline the inspection already recorded. Native units are scaled,
// never assumed: an unknown conversion leaves the box unmeasured so a plan can
// never pass by comparing millimetres against native units.
static J measured_bbox_mm(const J &state) {
    const MillimeterScale scale = length_scale_to_mm(board, inspect_length_units(board));
    if (!scale.known)
        return {{"available", false},
                {"reason", "the model length unit cannot be converted to millimetres"}};
    double low[3] = {0.0, 0.0, 0.0}, high[3] = {0.0, 0.0, 0.0};
    bool any = false;
    if (state.contains("bodies") && state["bodies"].is_array())
        for (const auto &body : state["bodies"]) {
            if (!body.contains("bbox") || !body["bbox"].is_array() || body["bbox"].size() != 2)
                continue;
            for (int corner = 0; corner < 2; corner++) {
                const J &point = body["bbox"][corner];
                if (!point.is_array() || point.size() != 3)
                    continue;
                for (int axis = 0; axis < 3; axis++) {
                    if (!point[axis].is_number())
                        continue;
                    const double value = point[axis].get<double>() * scale.scale;
                    low[axis] = any ? std::min(low[axis], value) : value;
                    high[axis] = any ? std::max(high[axis], value) : value;
                    any = true;
                }
            }
        }
    if (!any)
        return {{"available", false}, {"reason", "no material body bounding box was measured"}};
    return {{"available", true},
            {"min", J::array({low[0], low[1], low[2]})},
            {"max", J::array({high[0], high[1], high[2]})}};
}

static J verify_seed_solid(const J &binding, const J &state) {
    const J bounds = measured_bbox_mm(state);
    const J volume = state.value("volume_mm3", J(nullptr));
    if (!bounds.value("available", false) || !volume.is_number() || volume.get<double>() <= 0)
        throw std::runtime_error("Rebound seed Blend has no measurable solid");
    double min_z = std::numeric_limits<double>::infinity(), max_z = -min_z;
    for (const auto &label : binding.at("sections")) {
        const J &alias = aliases.at(label.get<std::string>());
        const double z = alias.at("origin").at(2).get<double>();
        min_z = std::min(min_z, z);
        max_z = std::max(max_z, z);
    }
    const double tolerance = std::max(0.01, (max_z - min_z) * 1e-6);
    if (bounds["min"][2].get<double>() > min_z + tolerance ||
        bounds["max"][2].get<double>() < max_z - tolerance)
        throw std::runtime_error(
            "Rebound seed Blend solid does not reach the requested end planes");
    return {{"volume_mm3", volume}, {"bbox_mm", bounds}, {"section_z_mm", {min_z, max_z}}};
}
// FEAT-067: the total area of a part, summed over every face the kernel reports.
// Unlike quilt_area_native this walks the whole solid, so "the area of the model"
// is one number instead of one quilt's worth; a failed face fails the sum.
struct TotalAreaAccumulator {
    bool ok = true;
    int count = 0;
    ProError code = PRO_TK_NO_ERROR;
    double area = 0.0;
};
static ProError total_area_surface_cb(ProSurface surface, ProError status, ProAppData data) {
    auto *acc = (TotalAreaAccumulator *)data;
    if (status) {
        acc->ok = false;
        acc->code = status;
        return PRO_TK_NO_ERROR;
    }
    const MeasurementOutcome per = surface_area_native(surface);
    if (!per.available) {
        acc->ok = false;
        acc->code = per.query_code;
        return PRO_TK_NO_ERROR;
    }
    acc->count++;
    acc->area += per.value;
    return PRO_TK_NO_ERROR;
}
static MeasurementOutcome total_surface_area_native() {
    TotalAreaAccumulator acc;
    const ProError code =
        ProSolidSurfaceVisit((ProSolid)board, total_area_surface_cb, nullptr, &acc);
    MeasurementOutcome out;
    if (code == PRO_TK_E_NOT_FOUND) {
        out.reason = "the model has no surfaces";
        return out;
    }
    if (code) {
        out.query_code = code;
        out.reason = "solid_surface_visit_failed";
        return out;
    }
    if (!acc.ok) {
        out.query_code = acc.code;
        out.reason = "surface_area_eval_failed";
        return out;
    }
    out.available = true;
    out.value = acc.area;
    return out;
}
// Millimetres squared only: the scale is applied twice, and an unknown unit
// leaves the area unmeasured rather than comparing native area against mm2.
static J measured_surface_area_mm2(const J &state) {
    const std::string kind = state.value("model_type", std::string("part"));
    if (kind == "assembly" || kind == "drawing")
        return {{"available", false},
                {"reason", "the surface area assertion measures a part, not a " + kind}};
    const MillimeterScale scale = length_scale_to_mm(board, inspect_length_units(board));
    if (!scale.known)
        return {{"available", false},
                {"reason", "the model length unit cannot be converted to millimetres"}};
    const MeasurementOutcome area = total_surface_area_native();
    if (!area.available)
        return {{"available", false},
                {"reason", area.reason ? std::string(area.reason)
                                       : std::string("no surface area was measured")}};
    return {{"available", true}, {"value", area.value * scale.scale * scale.scale}};
}
static void verify_assertions(const J &state, const J &a) {
    if (a.contains("volume_mm3")) {
        if (state["volume_mm3"].is_null() ||
            fabs(state["volume_mm3"].get<double>() - a["volume_mm3"].get<double>()) >
                a.value("volume_tolerance", 0.01))
            throw std::runtime_error("Volume assertion failed");
    }
    if (a.value("require_solid", false) && !state["has_solid"].get<bool>())
        throw std::runtime_error("Solid assertion failed");
    // FEAT-067: the expected millimetre box of the material bodies. The measured
    // side is the projection above; a box the model cannot express in
    // millimetres fails here instead of passing on native units.
    if (a.contains("bbox_mm") && a["bbox_mm"].is_object()) {
        const J &want = a["bbox_mm"];
        const double tolerance = want.value("tolerance_mm", 1e-3);
        const J measured = measured_bbox_mm(state);
        if (!measured.value("available", false))
            throw std::runtime_error(
                "Bounding box assertion failed: " +
                measured.value("reason", std::string("no measured bounding box")));
        for (int axis = 0; axis < 3; axis++) {
            const double low = measured["min"][axis].get<double>();
            const double high = measured["max"][axis].get<double>();
            const double want_low = want["min"][axis].get<double>();
            const double want_high = want["max"][axis].get<double>();
            if (fabs(low - want_low) > tolerance || fabs(high - want_high) > tolerance)
                throw std::runtime_error(
                    std::string("Bounding box assertion failed on ") + "XYZ"[axis] +
                    ": measured [" + std::to_string(low) + ", " + std::to_string(high) +
                    "] expected [" + std::to_string(want_low) + ", " + std::to_string(want_high) +
                    "] tolerance " + std::to_string(tolerance) + " mm");
        }
    }
    // FEAT-067: the expected total surface area of the part. The measured side
    // walks every face once; an unknown unit or a failed face measurement fails
    // here instead of passing on native area units.
    if (a.contains("surface_area_mm2")) {
        const double want = a["surface_area_mm2"].get<double>();
        const double tolerance = a.value("surface_area_tolerance_mm2", 0.01);
        const J measured = measured_surface_area_mm2(state);
        if (!measured.value("available", false))
            throw std::runtime_error(
                "Surface area assertion failed: " +
                measured.value("reason", std::string("no measured surface area")));
        const double value = measured["value"].get<double>();
        if (fabs(value - want) > tolerance)
            throw std::runtime_error("Surface area assertion failed: measured " +
                                     std::to_string(value) + " mm2 expected " +
                                     std::to_string(want) + " mm2 tolerance " +
                                     std::to_string(tolerance) + " mm2");
    }
    // DEV-077/R01: plan-level fidelity gates. Every sketch result already
    // carries its own geometry_deviation block, so the plan asserts over the
    // measured population instead of inventing a second measurement.
    const bool exact = a.value("require_exact_solve", false);
    const bool preserve = a.value("preserve_input_geometry", false);
    if (a.contains("max_geometry_deviation_mm") || exact || preserve) {
        bool measured = false;
        double worst = 0.0;
        bool shifted = false;
        for (const auto &entry : operation_results) {
            if (!entry.contains("geometry_deviation") || !entry["geometry_deviation"].is_object())
                continue;
            const J &deviation = entry["geometry_deviation"];
            if (!deviation.value("available", false))
                continue;
            measured = true;
            if (deviation.contains("max_deviation_mm") && deviation["max_deviation_mm"].is_number())
                worst = std::max(worst, deviation["max_deviation_mm"].get<double>());
            if (deviation.contains("shift_detected") && deviation["shift_detected"].is_boolean() &&
                deviation["shift_detected"].get<bool>())
                shifted = true;
        }
        if (!measured)
            throw std::runtime_error(
                "Geometry deviation assertion failed: no measured sketch deviation");
        if (a.contains("max_geometry_deviation_mm")) {
            const double limit = a["max_geometry_deviation_mm"].get<double>();
            if (worst > limit)
                throw std::runtime_error("Geometry deviation assertion failed: max_deviation_mm " +
                                         std::to_string(worst) + " exceeds " +
                                         std::to_string(limit));
        }
        if (exact && (worst > 0.0 || shifted))
            throw std::runtime_error(
                "Exact solve assertion failed: the solver changed the input geometry");
        if (preserve && shifted)
            throw std::runtime_error(
                "Input geometry assertion failed: the solver shifted the sketch");
    }
}
static void verify_saved(const J &before, const J &after, bool feature_state_commit) {
    // A committed feature_state plan is the only case where the saved model may
    // legitimately lose features (delete), gain status changes (suppress/resume)
    // and change volume. Every other path keeps the strict comparison.
    std::set<int> deleted_ids;
    J expected_status = J::object();
    if (feature_state_commit) {
        for (auto &id : feature_state_effects.value("deleted_ids", J::array()))
            deleted_ids.insert(id.get<int>());
        expected_status = feature_state_effects.value("status_expectations", J::object());
    }
    if (!feature_state_commit) {
        if (before["features"].size() != after["features"].size() ||
            before["bodies"].size() != after["bodies"].size())
            throw std::runtime_error("Saved feature/body count changed");
    }
    std::map<int, J> after_by_id;
    for (auto &f : after["features"])
        after_by_id[f["id"].get<int>()] = f;
    auto status_of = [](const J &f, const char *key) {
        return f.contains(key) && f[key].is_number_integer() ? f[key].get<int>() : -1;
    };
    if (feature_state_commit)
        for (int id : deleted_ids)
            if (after_by_id.count(id))
                throw std::runtime_error("Saved model still contains a deleted feature");
    for (size_t i = 0; i < before["features"].size(); i++) {
        auto a = before["features"][i];
        int id = a["id"].get<int>();
        auto found = after_by_id.find(id);
        if (found == after_by_id.end()) {
            if (!feature_state_commit)
                throw std::runtime_error("Saved feature/body count changed");
            // A grouped/patterned member follows its header and is removed
            // with it; only such covered removals may be implicit.
            bool member = status_of(a, "group_status") == PRO_GROUP_MEMBER ||
                          status_of(a, "pattern_status") == PRO_PATTERN_MEMBER ||
                          status_of(a, "grppattern_status") == PRO_GRP_PATTERN_MEMBER;
            if (!member)
                throw std::runtime_error(
                    "Saved feature disappeared outside the explicitly deleted set");
            continue;
        }
        auto b = found->second;
        int expected = a["status"].get<int>();
        if (feature_state_commit) {
            std::string key = std::to_string(id);
            if (expected_status.contains(key))
                expected = expected_status[key].get<int>();
        }
        // A suppressed feature's dimensions are not part of the geometry that
        // regenerates; the status comparison below is the real assertion for
        // that transition. Resumed and untouched features keep the full check.
        bool dimensions_compare = expected != PRO_FEAT_SUPPRESSED;
        if (a["id"] != b["id"] || a["type"] != b["type"] || a["name"] != b["name"] ||
            (dimensions_compare && a["dimensions"].size() != b["dimensions"].size()))
            throw std::runtime_error("Saved feature or dimensions changed");
        if (dimensions_compare)
            for (size_t j = 0; j < a["dimensions"].size(); j++)
                if (a["dimensions"][j]["id"] != b["dimensions"][j]["id"] ||
                    fabs(a["dimensions"][j]["value"].get<double>() -
                         b["dimensions"][j]["value"].get<double>()) > 1e-6)
                    throw std::runtime_error("Saved dimension value changed");
        if (b["status"].get<int>() != expected)
            throw std::runtime_error(
                "Saved feature status does not match the requested feature_state");
    }
    if (!feature_state_commit && !before["volume_mm3"].is_null() &&
        (after["volume_mm3"].is_null() ||
         fabs(before["volume_mm3"].get<double>() - after["volume_mm3"].get<double>()) > 0.01))
        throw std::runtime_error("Saved solid volume changed");
    if (before["parameters"].size() != after["parameters"].size())
        throw std::runtime_error("Saved parameter count changed");
    for (auto it = before["parameters"].begin(); it != before["parameters"].end(); ++it) {
        if (!after["parameters"].contains(it.key()))
            throw std::runtime_error("Saved parameter disappeared: " + it.key());
        auto a = it.value(), b = after["parameters"][it.key()];
        bool equal = a["type"] == b["type"];
        if (equal && a["type"].get<int>() == PRO_PARAM_DOUBLE) {
            double x = a["value"], y = b["value"];
            equal = fabs(x - y) <= 1e-10 * std::max(1.0, std::max(fabs(x), fabs(y)));
        } else
            equal = equal && a["value"] == b["value"];
        if (!equal)
            throw std::runtime_error("Saved parameter value changed: " + it.key());
    }
    if (before.contains("components"))
        for (size_t i = 0; i < before["components"].size(); i++) {
            if (i >= after["components"].size())
                throw std::runtime_error("Saved component count changed");
            auto a = before["components"][i], b = after["components"][i];
            if (a.value("packaged", false) != b.value("packaged", false) ||
                a.value("underconstrained", false) != b.value("underconstrained", false))
                throw std::runtime_error("Saved assembly placement state changed");
            // Compare through the shared projection: checkpoints saved before
            // constraints gained the display-only type_name symbol must stay
            // compatible, while numeric type, offsets, references, sides and
            // count/order stay fully verified (constraint_compare.h).
            if (a.contains("constraints") &&
                !mechdog_constraints::match_for_verification(a["constraints"],
                                                             b.value("constraints", J::array())))
                throw std::runtime_error("Saved assembly constraints changed");
        }
    if (before.value("model_type", "part") != after.value("model_type", "part"))
        throw std::runtime_error("Saved model type changed");
    if (before.contains("components")) {
        if (before["components"].size() != after["components"].size())
            throw std::runtime_error("Saved component count changed");
        for (size_t i = 0; i < before["components"].size(); i++) {
            auto a = before["components"][i], b = after["components"][i];
            if (a["feature_id"] != b["feature_id"] || a["model_name"] != b["model_name"])
                throw std::runtime_error("Saved component changed");
            // FEAT-052: the component appearance must survive save/reload and
            // rollback. Baselines recorded before FEAT-052 carry no appearance
            // field and stay compatible; the recolor op refuses components
            // without an appearance baseline instead of guessing one.
            if (a.contains("appearance") && b.contains("appearance") &&
                !appearance_records_equal(a["appearance"], b["appearance"]))
                throw std::runtime_error("Saved component appearance changed");
            const auto &verified_transform = component_transform_for_verification(a, b);
            for (int r = 0; r < 4; r++)
                for (int c = 0; c < 4; c++)
                    if (fabs(a["transform"][r][c].get<double>() -
                             verified_transform[r][c].get<double>()) > 1e-7)
                        throw std::runtime_error("Saved component transform changed");
        }
    }
}
static std::wstring latest_model_file(bool required = true) {
    std::wstring extension = assembly_model() ? L".asm." : L".prt.",
                 mask = folder + L"\\" + model_name + extension + L"*";
    WIN32_FIND_DATAW info;
    HANDLE search = FindFirstFileW(mask.c_str(), &info);
    if (search == INVALID_HANDLE_VALUE) {
        if (!required && GetLastError() == ERROR_FILE_NOT_FOUND)
            return L"";
        throw std::runtime_error("Could not enumerate saved model versions");
    }
    int best = -1;
    std::wstring found;
    do {
        std::wstring name = info.cFileName;
        auto pos = name.rfind(extension);
        if (pos == std::wstring::npos || (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY))
            continue;
        auto suffix = name.substr(pos + extension.size());
        if (suffix.empty() || suffix.find_first_not_of(L"0123456789") != std::wstring::npos)
            continue;
        try {
            int version = std::stoi(suffix);
            if (version > best) {
                best = version;
                found = folder + L"\\" + name;
            }
        } catch (...) {
        }
    } while (FindNextFileW(search, &info));
    auto enumeration_error = GetLastError();
    FindClose(search);
    if (enumeration_error != ERROR_NO_MORE_FILES)
        throw std::runtime_error("Could not enumerate all saved model versions");
    if (required && found.empty())
        throw std::runtime_error("Saved native model version not found");
    return found;
}

// ProMdlErase can return while the active model is still in memory. Never let
// FiletypeLoad satisfy a checkpoint request with that same-name session object.
static void reload_managed_checkpoint(const std::wstring &checkpoint_file, ProMdlType type,
                                      bool report_substages = false) {
    if (board) {
        CK(ProMdlErase(board));
        board = nullptr;
    }
    ProName name;
    wcscpy_s(name, model_name.c_str());
    const auto deadline = GetTickCount64() + 1000;
    for (;;) {
        ProMdl resident = nullptr;
        ProError found = ProMdlInit(name, type, &resident);
        if (found == PRO_TK_E_NOT_FOUND)
            break;
        check(found, "ProMdlInit(checkpoint absence)");
        if (GetTickCount64() >= deadline)
            throw std::runtime_error(
                "Checkpoint reload blocked: the managed model is still in Creo memory after "
                "erase. Close its window and retry recovery during an idle Creo session.");
        Sleep(25);
    }
    ProPath source;
    path(source, checkpoint_file);
    if (report_substages)
        generic_substage("verify_model_reload");
    CK(ProMdlFiletypeLoad(source, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
    ProPath origin;
    CK(ProMdlOriginGet(board, origin));
    std::error_code error;
    if (!std::filesystem::equivalent(origin, checkpoint_file, error)) {
        board = nullptr;
        throw std::runtime_error("Creo did not load the exact managed checkpoint requested");
    }
}

static J save_failure_report(ProError code, const char *stage, const std::wstring &checkpoint,
                             const std::wstring &directory, const std::wstring &model_name,
                             bool assembly, const char *call);
// The only path allowed to replace a diverged owned session model. Python has
// already bound the selected source and explicit action to a durable intent.
static bool recovery_geometry_equal(const J &a, const J &b) {
    if (a.is_number_integer() && b.is_number_integer())
        return a == b;
    if (a.is_number() && b.is_number()) {
        double x = a.get<double>(), y = b.get<double>();
        return std::isfinite(x) && std::isfinite(y) &&
               fabs(x - y) <= 1e-6 * std::max(1.0, std::max(fabs(x), fabs(y)));
    }
    if (a.type() != b.type() || a.size() != b.size())
        return false;
    if (a.is_object()) {
        for (auto it = a.begin(); it != a.end(); ++it)
            if (!b.contains(it.key()) || !recovery_geometry_equal(it.value(), b.at(it.key())))
                return false;
        return true;
    }
    if (a.is_array()) {
        for (size_t i = 0; i < a.size(); ++i)
            if (!recovery_geometry_equal(a[i], b[i]))
                return false;
        return true;
    }
    return a == b;
}

static void verify_recovery(const J &before, const J &after) {
    verify_saved(before, after);
    for (const char *key : {"bodies", "surfaces", "edges", "datum_planes"})
        if (!recovery_geometry_equal(before.at(key), after.at(key)))
            throw std::runtime_error(std::string("Recovery geometry changed: ") + key);
}

static std::string recovery_session_fingerprint() {
    ProConnectionId value;
    CK(ProEngineerConnectIdGet(value));
    // Bind the session without persisting or returning its connection secret.
    return std::to_string(std::hash<std::string>{}(std::string(value)));
}

static bool dependency_free(ProMdl mdl, bool cleanup = true) {
    if (cleanup)
        CK(ProMdlDependenciesCleanup(mdl));
    ProMdlnameShortdata *names = nullptr;
    ProMdlfileType *types = nullptr;
    int count = 0;
    ProError code = ProMdlDependenciesDataList(mdl, &names, &types, &count);
    if (names)
        ProArrayFree((ProArray *)&names);
    if (types)
        ProArrayFree((ProArray *)&types);
    if (code == PRO_TK_E_NOT_FOUND)
        return true;
    check(code, "RecoveryDependencies");
    return count == 0;
}

static bool recovery_dependency_free() {
    return dependency_free(board);
}

static std::wstring save_managed_checkpoint(const std::wstring &checkpoint, const char *stage,
                                            J &report) {
    const std::wstring previous = latest_model_file(false);
    ProName iteration_option = L"save_file_iterations";
    ProPath iterations = {};
    if (!previous.empty() && ProConfigoptionGet(iteration_option, iterations) == PRO_TK_NO_ERROR &&
        !_wcsicmp(iterations, L"no"))
        throw std::runtime_error("Managed saves require Creo save_file_iterations=yes to preserve "
                                 "the previous checkpoint");
    const char *call = "ProMdlnameBackup";
    ProPath target;
    std::error_code error;
    // Save in place only when Toolkit confirms that the write destination is
    // the managed directory and the part cannot propagate saves to dependents.
    if (!checkpoint.empty() && !assembly_model() &&
        ProMdlDirectoryPathGet(board, target) == PRO_TK_NO_ERROR &&
        std::filesystem::equivalent(target, folder, error) && dependency_free(board, false)) {
        call = "ProMdlSave";
        const ProError code = ProMdlSave(board);
        if (code != PRO_TK_NO_ERROR)
            report["save_failure"] =
                save_failure_report(code, stage, checkpoint, folder, model_name, false, call);
        check(code, call);
        std::wstring saved = latest_model_file(false);
        if (!saved.empty() && saved != previous)
            return saved;
        // A successful Save can leave an unmodified file at its current
        // version. Explicit and implicit saves both promise a new version.
        call = "ProMdlnameBackup";
    }
    path(target, folder);
    const ProError code = ProMdlnameBackup(board, target);
    if (code != PRO_TK_NO_ERROR)
        report["save_failure"] = save_failure_report(code, stage, checkpoint, folder, model_name,
                                                     assembly_model(), call);
    check(code, call);
    std::wstring saved = latest_model_file();
    if (saved == previous)
        throw std::runtime_error("Creo did not produce a new managed model version");
    return saved;
}

static J read_inspection_ref(const J &ref) {
    if (!ref.is_object() || !ref.contains("file") || !ref.contains("sha256"))
        throw std::runtime_error("Inspection reference is malformed");
    const std::filesystem::path file(wide(ref.at("file").get<std::string>()));
    if (mechdog_callback::sha256(file) != ref.at("sha256").get<std::string>())
        throw std::runtime_error(
            "Inspection reference hash mismatch: the referenced full inspection "
            "changed since it was recorded");
    std::ifstream input(file, std::ios::binary);
    if (!input)
        throw std::runtime_error("Inspection reference file is missing");
    J value;
    input >> value;
    return value;
}

static J choice_inspection(const J &holder, const char *key) {
    const std::string ref_key = std::string(key) + "_ref";
    if (holder.contains(ref_key))
        return read_inspection_ref(holder.at(ref_key));
    if (holder.contains(key))
        return holder.at(key);
    throw std::runtime_error(std::string("Request is missing ") + key);
}
// Controlled inspection references (BUG-076/DEV-048): full payloads stay next
// to the job as content-addressed sidecar files; control results carry only
// {file, sha256, bytes} and the Python closeout adds a small summary. The
// write/publish policy lives in inspection_sidecar.h so it can be compiled and
// exercised offline. Legacy inline payloads inside requests keep working
// through choice_inspection.
static void split_report_inspections(const J &request, J &report) {
    // Ordinary modeling plans keep their inline inspection: the
    // registry/query snapshot contract for created models is unchanged. A
    // sidecar failure keeps the inline payload and records the fixed stage and
    // reason on the report; the Python closeout tries the same split again.
    try {
        mechdog_sidecar::split_report(request, report, std::filesystem::path(folder));
    } catch (const std::exception &error) {
        log("INSPECTION_SPLIT_FAILED=%s\n", error.what());
    }
}

static bool millimeter_units(ProMdl mdl) {
    ProUnitsystem us;
    ProUnititem unit;
    CK(ProMdlPrincipalunitsystemGet(mdl, &us));
    CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
    return !wcscmp(unit.name, L"mm");
}

// BUG-157: an assembly always references its component models, so the plain
// "dependency free" rule can never accept one. A dependency counts as owned
// only when Toolkit reports it in session and its origin lies inside this
// model's own output directory or the managed models root. Unresolved or
// outside paths are returned with their names so the refusal can list them.
static bool inside_managed_directory(const std::wstring &candidate, const std::wstring &root) {
    if (candidate.empty() || root.empty())
        return false;
    auto normalized = [](std::wstring value) {
        std::replace(value.begin(), value.end(), L'/', L'\\');
        while (value.size() > 3 && value.back() == L'\\')
            value.pop_back();
        return value;
    };
    const std::wstring path_value = normalized(candidate), root_value = normalized(root);
    if (!_wcsicmp(path_value.c_str(), root_value.c_str()))
        return true;
    return path_value.size() > root_value.size() &&
           !_wcsnicmp(path_value.c_str(), root_value.c_str(), root_value.size()) &&
           path_value[root_value.size()] == L'\\';
}

static J unowned_recovery_dependencies(const std::string &managed_root) {
    J refused = J::array();
    CK(ProMdlDependenciesCleanup(board));
    ProMdlnameShortdata *names = nullptr;
    ProMdlfileType *types = nullptr;
    int count = 0;
    const ProError code = ProMdlDependenciesDataList(board, &names, &types, &count);
    const std::wstring root = wide(managed_root);
    if (code != PRO_TK_E_NOT_FOUND)
        for (int i = 0; i < count; ++i) {
            ProMdl dependency = nullptr;
            const ProError found = ProMdlnameInit(names[i].name, types[i], &dependency);
            if (found != PRO_TK_NO_ERROR) {
                refused.push_back(
                    {{"name", utf8(names[i].name)},
                     {"origin", nullptr},
                     {"reason", "not in session; dependency ownership cannot be proven"}});
                continue;
            }
            ProPath origin = {};
            const ProError origin_code = ProMdlOriginGet(dependency, origin);
            if (origin_code != PRO_TK_NO_ERROR) {
                refused.push_back({{"name", utf8(names[i].name)},
                                   {"origin", nullptr},
                                   {"reason", "origin unreadable"},
                                   {"origin_query_code", (int)origin_code}});
                continue;
            }
            const std::wstring value(origin);
            if (!inside_managed_directory(value, folder) && !inside_managed_directory(value, root))
                refused.push_back(
                    {{"name", utf8(names[i].name)},
                     {"origin", utf8(value)},
                     {"reason", "outside this model's output and the managed models root"}});
        }
    if (names)
        ProArrayFree((ProArray *)&names);
    if (types)
        ProArrayFree((ProArray *)&types);
    if (code != PRO_TK_E_NOT_FOUND)
        check(code, "RecoveryDependencies");
    return refused;
}

static void verify_recovery_dependencies(const J &request) {
    if (!assembly_model()) {
        if (!recovery_dependency_free())
            throw std::runtime_error(
                "Recovery refused: external dependencies require separate ownership verification");
        return;
    }
    const J refused = unowned_recovery_dependencies(request.value("managed_root", std::string()));
    if (!refused.empty())
        throw std::runtime_error(
            "Recovery refused: assembly dependencies outside managed directories: " +
            refused.dump());
}

static ProError count_recovery_feature(ProFeature *, ProError status, ProAppData data) {
    if (status == PRO_TK_NO_ERROR)
        (*static_cast<int *>(data))++;
    return PRO_TK_NO_ERROR;
}

// BUG-157: identity verification for restore_baseline. The two full inspections
// and their deep comparison are the expensive part of a recovery on a large
// model; this proves the reloaded checkpoint is this model in the recorded state
// using name, type, units, feature count and volume only. The receipt labels the
// weaker claim (full_inspection_verified=false) and never fabricates geometry.
static void verify_recovery_identity(const J &expected, J &report) {
    ProMdlName actual_name = {};
    CK(ProMdlMdlnameGet(board, actual_name));
    // Creo returns the stored name upper-cased while the registry keeps the
    // generated lower-case name; the reload is the same model either way.
    if (_wcsicmp(actual_name, model_name.c_str()))
        throw std::runtime_error("Recovery identity check: reloaded model name changed");
    ProMdlType type;
    CK(ProMdlTypeGet(board, &type));
    std::string actual_type = "part";
    if (type == PRO_MDL_ASSEMBLY)
        actual_type = "assembly";
    else if (type == PRO_MDL_PART) {
        ProMdlsubtype subtype;
        if (!ProMdlSubtypeGet(board, &subtype) && subtype == PROMDLSTYPE_PART_SHEETMETAL)
            actual_type = "sheetmetal";
    }
    if (expected.value("model_type", "part") != actual_type)
        throw std::runtime_error("Recovery identity check: model type changed");
    int features = 0;
    CK(ProSolidFeatVisit((ProSolid)board, count_recovery_feature, nullptr, &features));
    const int recorded = expected.contains("features") && expected["features"].is_array()
                             ? (int)expected["features"].size()
                             : -1;
    if (recorded >= 0 && features != recorded)
        throw std::runtime_error("Recovery identity check: feature count changed (" +
                                 std::to_string(recorded) + " recorded, " +
                                 std::to_string(features) + " live)");
    J volume = nullptr;
    if (expected.contains("volume_mm3") && expected["volume_mm3"].is_number()) {
        ProMassProperty property;
        const ProError code = ProSolidMassPropertyWithDensityGet(
            (ProSolid)board, nullptr, PRO_MP_DENS_USE_ALWAYS, 1, &property);
        if (code != PRO_TK_NO_ERROR)
            throw std::runtime_error("Recovery identity check: volume query failed with code " +
                                     std::to_string((int)code));
        const auto units = inspect_length_units(board);
        const auto measured = units.volume_mm3(property.volume);
        if (!measured)
            throw std::runtime_error("Recovery identity check: volume unit conversion unavailable");
        if (fabs(*measured - expected["volume_mm3"].get<double>()) > 0.01)
            throw std::runtime_error("Recovery identity check: volume changed");
        volume = *measured;
    }
    report["verification"] = "identity";
    report["full_inspection_verified"] = false;
    report["feature_count"] = features;
    report["volume_mm3"] = volume;
}

static void reconcile_native(const J &request, const std::wstring &checkpoint, J &report) {
    const J &choice = request.at("reconciliation");
    const std::string action = choice.at("action");
    const std::string session = recovery_session_fingerprint();
    if (choice.contains("session_fingerprint") && choice["session_fingerprint"] != session)
        throw std::runtime_error("Recovery refused: Creo session changed since recorded evidence");
    ProName name;
    wcscpy_s(name, model_name.c_str());
    ProMdlType type = request["model"].value("model_type", "part") == "assembly" ? PRO_MDL_ASSEMBLY
                                                                                 : PRO_MDL_PART;
    ProError found = ProMdlInit(name, type, &board);
    if (found != PRO_TK_E_NOT_FOUND)
        check(found, "FindRecoveryModel");
    bool loaded = found == PRO_TK_NO_ERROR, owned = false;
    std::wstring origin;
    if (loaded) {
        ProPath value;
        CK(ProMdlOriginGet(board, value));
        origin = value;
        std::wstring prefix = folder + L"\\";
        owned = !_wcsnicmp(origin.c_str(), prefix.c_str(), prefix.size());
    }
    report["live"] = {{"loaded", loaded},
                      {"owned", owned},
                      {"origin", utf8(origin)},
                      {"session_fingerprint", session}};
    if (action == "inspect") {
        if (loaded && owned) {
            report["live"]["inspection"] = inspection(false);
            ProUnitsystem us;
            ProUnititem unit;
            CK(ProMdlPrincipalunitsystemGet(board, &us));
            CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
            report["live"]["millimeter_units"] = !wcscmp(unit.name, L"mm");
            report["live"]["dependency_free"] = recovery_dependency_free();
            // BUG-157: an assembly's components are dependencies by definition,
            // so admission reads the directory ownership answer instead.
            if (assembly_model())
                report["live"]["dependencies_owned"] =
                    unowned_recovery_dependencies(request.value("managed_root", std::string()))
                        .empty();
            try {
                if (request["model"].contains("inspection") ||
                    request["model"].contains("inspection_ref")) {
                    verify_recovery(choice_inspection(request["model"], "inspection"),
                                    report["live"]["inspection"]);
                    report["live"]["matches_baseline"] = true;
                }
            } catch (const std::exception &error) {
                report["live"]["matches_baseline"] = false;
                report["live"]["baseline_mismatch"] = error.what();
            }
        }
        report["success"] = true;
        return;
    }
    if (loaded && !owned)
        throw std::runtime_error("Recovery refused: session model origin is not owned");
    if (action == "abandon_new") {
        if (loaded) {
            CK(ProMdlErase(board));
            board = nullptr;
        }
        report.update({{"success", true}, {"abandoned", true}, {"files_preserved", true}});
        return;
    }
    if (action == "accept_live") {
        if (!loaded ||
            (!choice.contains("live_inspection") && !choice.contains("live_inspection_ref")))
            throw std::runtime_error(
                "accept_live requires an owned loaded model and live evidence");
        verify_recovery(choice_inspection(choice, "live_inspection"), inspection());
    } else if (action == "restore_baseline" || action == "accept_saved") {
        generic_stage("recovery_reload_source");
        reload_managed_checkpoint(wide(choice.at("source_file")), type);
    } else
        throw std::runtime_error("Unknown reconciliation action");
    ProUnitsystem us;
    ProUnititem unit;
    CK(ProMdlPrincipalunitsystemGet(board, &us));
    CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
    if (wcscmp(unit.name, L"mm"))
        throw std::runtime_error("Recovery requires millimeter model units");
    verify_recovery_dependencies(request);
    generic_stage("recovery_verify_source");
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    const std::string verify_mode = choice.value("verify_mode", "full");
    if (verify_mode != "full" && verify_mode != "identity")
        throw std::runtime_error("Unknown verify_mode; use 'full' or 'identity'");
    // BUG-157: only restore_baseline has a recorded baseline state the reload
    // can be bound to without a second full inspection.
    if (verify_mode == "identity" && action != "restore_baseline")
        throw std::runtime_error("verify_mode=identity is only available for restore_baseline");
    if (verify_mode == "identity") {
        generic_stage("recovery_identity_check");
        verify_recovery_identity(choice_inspection(choice, "source_inspection"), report);
        CK(ProMdlDisplay(board));
        report.update({{"success", true},
                       {"saved_file_reloaded_and_verified", true},
                       {"part_file", choice.at("source_file")}});
        return;
    }
    J before = inspection();
    if (action != "accept_live")
        verify_recovery(choice_inspection(choice, "source_inspection"), before);
    report["loft_checks"]["recovery_source"] = verify_loft_settings(L"recovery_source");
    std::wstring saved = action == "restore_baseline" ? wide(choice.at("source_file")) : L"";
    J after = before;
    if (action != "restore_baseline") {
        generic_stage("recovery_save_and_reload");
        const auto source = action == "accept_saved" ? wide(choice.at("source_file")) : checkpoint;
        saved = save_managed_checkpoint(source, "recovery_save_and_reload", report);
        reload_managed_checkpoint(saved, type);
        CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
        after = inspection();
        verify_recovery(before, after);
    }
    report["loft_checks"]["recovery_reloaded"] = verify_loft_settings(L"recovery_reloaded");
    after["inspection_source"] = "reconciliation_verified";
    after["inspection_available"] = true;
    CK(ProMdlDisplay(board));
    report.update({{"success", true},
                   {"saved_file_reloaded_and_verified", true},
                   {"inspection", after},
                   {"aliases", aliases},
                   {"part_file", utf8(saved)}});
}

// Explicit adoption of the user's current window model as a managed copy. The
// source model is never erased, saved or renamed; adoption copies the in-memory
// state into this job's output directory and verifies the copy like any save.
static void display_adopted_model() {
    CK(ProMdlDisplay(board));
    int window = -1;
    CK(ProMdlWindowGet(board, &window));
    CK(ProWindowCurrentSet(window));
    CK(ProWindowRefit(window));
    CK(ProWindowRepaint(window));
    CK(ProWindowActivate(window));
}

static void confirm_adoption_snapshot(const J &choice, J &report) {
    std::wstring saved = wide(choice.at("source_file"));
    auto candidate = std::filesystem::path(saved).lexically_normal();
    auto output = std::filesystem::path(folder).lexically_normal();
    if (!candidate.is_absolute() || _wcsicmp(candidate.parent_path().c_str(), output.c_str()) ||
        candidate.filename().wstring().find(model_name + L".prt.") != 0)
        throw std::runtime_error("Prepared snapshot is outside its owned output");
    ProMdlName name = {};
    wcscpy_s(name, model_name.c_str());
    ProError found = ProMdlInit(name, PRO_MDL_PART, &board);
    if (found == PRO_TK_NO_ERROR) {
        ProPath origin = {};
        CK(ProMdlOriginGet(board, origin));
        if (_wcsicmp(origin, saved.c_str()))
            throw std::runtime_error("Prepared snapshot name conflicts with another session model");
        // Refuse rather than discard manual changes to the staged copy.
        verify_recovery(choice_inspection(choice, "source_inspection"), inspection(false));
        CK(ProMdlErase(board));
        board = nullptr;
    } else if (found != PRO_TK_E_NOT_FOUND)
        check(found, "FindPreparedSnapshot");
    ProPath file;
    path(file, saved);
    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    if (!millimeter_units(board) || !dependency_free(board))
        throw std::runtime_error("Prepared snapshot units or dependencies changed");
    J after = inspection();
    verify_recovery(choice_inspection(choice, "source_inspection"), after);
    after["inspection_source"] = "adoption_snapshot_verified";
    after["inspection_available"] = true;
    display_adopted_model();
    report.update({{"success", true},
                   {"saved_file_reloaded_and_verified", true},
                   {"inspection", after},
                   {"aliases", J::object()},
                   {"part_file", utf8(saved)},
                   {"adopted", true}});
}

struct SessionInventory {
    J models = J::array();
    J type_errors = J::array();
    bool truncated = false;
    int current_code = 0;
};

// Single-handle session observation shared by the session inventory and the
// open-file result; the field set stays identical so clients can compare
// entries from either source. current_code mirrors ProMdlCurrentGet's own
// outcome: when it failed, is_current is null rather than a guess.
static J observe_session_model(ProMdl mdl, const char *model_type, ProMdl current,
                               int current_code) {
    ProMdlName name = {};
    ProPath origin = {};
    ProBoolean modified = PRO_B_FALSE;
    int id = -1;
    ProError nc = ProMdlMdlnameGet(mdl, name);
    ProError oc = ProMdlOriginGet(mdl, origin);
    ProError mc = ProMdlModificationVerify(mdl, &modified);
    ProError ic = ProMdlIdGet(mdl, &id);
    return {{"name", nc ? J(nullptr) : J(utf8(name))},
            {"model_type", model_type},
            {"is_current", current_code ? J(nullptr) : J(mdl == current)},
            {"origin", oc ? J(nullptr) : J(utf8(origin))},
            {"has_saved_origin", oc ? J(nullptr) : J(origin[0] != 0)},
            {"modified", mc ? J(nullptr) : J(modified == PRO_B_TRUE)},
            {"session_model_id", ic ? J(nullptr) : J(id)},
            {"query_codes", {{"name", nc}, {"origin", oc}, {"modified", mc}, {"id", ic}}}};
}

static void collect_session_models(SessionInventory &inventory) {
    ProMdl current = nullptr;
    inventory.current_code = ProMdlCurrentGet(&current);
    J models = J::array(), errors = J::array();
    const std::pair<ProMdlType, const char *> types[] = {{PRO_MDL_PART, "part"},
                                                         {PRO_MDL_ASSEMBLY, "assembly"},
                                                         {PRO_MDL_DRAWING, "drawing"},
                                                         {PRO_MDL_3DSECTION, "section3d"},
                                                         {PRO_MDL_2DSECTION, "section2d"},
                                                         {PRO_MDL_LAYOUT, "notebook"},
                                                         {PRO_MDL_DWGFORM, "drawing_format"},
                                                         {PRO_MDL_MFG, "manufacturing"},
                                                         {PRO_MDL_REPORT, "report"},
                                                         {PRO_MDL_MARKUP, "markup"},
                                                         {PRO_MDL_DIAGRAM, "diagram"}};
    bool truncated = false;
    for (const auto &entry : types) {
        ProMdl *list = nullptr;
        int count = 0;
        ProError listed = ProSessionMdlList(entry.first, &list, &count);
        if (listed != PRO_TK_NO_ERROR && listed != PRO_TK_E_NOT_FOUND) {
            errors.push_back({{"model_type", entry.second}, {"code", listed}});
        } else if (listed == PRO_TK_NO_ERROR) {
            try {
                for (int i = 0; i < count; ++i) {
                    if (models.size() >= 4096) {
                        truncated = true;
                        break;
                    }
                    J item = observe_session_model(list[i], entry.second, current,
                                                   inventory.current_code);
                    if (entry.first == PRO_MDL_PART) {
                        ProMdlsubtype subtype;
                        ProError sc = ProMdlSubtypeGet(list[i], &subtype);
                        item["query_codes"]["subtype"] = sc;
                        if (!sc && subtype == PROMDLSTYPE_PART_SHEETMETAL)
                            item["model_type"] = "sheetmetal";
                    }
                    models.push_back(item);
                }
            } catch (...) {
                if (list)
                    ProArrayFree((ProArray *)&list);
                throw;
            }
        }
        if (list)
            CK(ProArrayFree((ProArray *)&list));
    }
    inventory.models = models;
    inventory.type_errors = errors;
    inventory.truncated = truncated;
}

static void session_models_native(J &report) {
    SessionInventory inventory;
    collect_session_models(inventory);
    report.update({{"success", true},
                   {"models", inventory.models},
                   {"type_errors", inventory.type_errors},
                   {"complete", inventory.type_errors.empty() && !inventory.truncated},
                   {"truncated", inventory.truncated},
                   {"current_model_code", inventory.current_code}});
}

// FEAT-045: read-only inspection of a resident assembly. The walk selects an
// already-loaded assembly by name, never loads, activates, regenerates, saves
// or adopts anything, and reports every node in tree order with occurrence
// paths, resolved 4x4 transforms and constraint snapshots. Per-node failures
// are marked with their raw query codes instead of failing the whole report.
// The walk's mutable report state (recorded nodes plus the truncated/
// incomplete/depth_limited judgements) is the shared AssemblyWalkState from
// assembly_walk.h, executed by the offline harness too.

// BUG-080: the walk carries both the raw member-to-root chain (member length
// unit -> root length unit) and the millimeter-normalized chain. Either chain
// stops being trustworthy once an ancestor transform or unit query failed, so
// descendants report an unknown root transform instead of inheriting a
// grandparent matrix as if it were their own.
struct WalkContext {
    ProSolid owner = nullptr;
    std::vector<int> path; // component feature ids from the root assembly
    // BUG-080 follow-up: both member-to-root chains with independent
    // validity; WalkChain defaults to the real identity instead of the old
    // zero-initialized raw root.
    WalkChain chain;
    AssemblyWalkState *walk = nullptr;
    ProMdl current = nullptr;
    int current_code = -1;
    int depth = 0;
};

// Creo ProMatrix is row-major with row-vector convention p' = p * M, so the
// translation lives in the last row. BUG-080: entries are raw Creo values in
// the source/target model length units (see assembly_units.h); millimeter
// maps are produced separately and stay null when units are unknown.
static J matrix_json(const ProMatrix matrix) {
    J rows = J::array();
    for (int r = 0; r < 4; ++r) {
        J row = J::array();
        for (int c = 0; c < 4; ++c)
            row.push_back(matrix[r][c]);
        rows.push_back(row);
    }
    return rows;
}

// BUG-080: one model's real length unit with its millimeter scale and every
// raw query code; name and scale stay null on failure instead of pretending
// millimeters.
static J length_unit_json(const InspectionLengthUnits &units, const MillimeterScale &scale) {
    return {{"name", units.code || !units.length.name[0] ? J(nullptr) : J(utf8(units.length.name))},
            {"query_code", units.code},
            {"scale_to_mm", scale.known ? J(scale.scale) : J(nullptr)},
            {"scale_to_mm_known", scale.known},
            {"scale_query_codes",
             {{"unit", scale.unit_query_code},
              {"mm_unit", sdk_query_code_json(scale.mm_unit_queried, scale.mm_unit_query_code)},
              {"conversion",
               sdk_query_code_json(scale.conversion_queried, scale.conversion_query_code)}}}};
}

// Component feature name (the occurrence label the assembly tree shows) for one
// sibling component id. Used by the snapshot so a reference can be described by
// its owning same-level component instead of an id that only means something in
// the source model. A failed query stays null with its raw code.
static J component_label_json(ProSolid assembly, int component_id, J &codes, const char *key) {
    ProModelitem item = {};
    ProError init_code = ProModelitemInit(assembly, component_id, PRO_FEATURE, &item);
    ProName name = {};
    ProError name_code = init_code ? init_code : ProModelitemNameGet(&item, name);
    codes[key] = name_code;
    return {{"occurrence_label", name_code ? J(nullptr) : J(utf8(name))},
            {"occurrence_label_query_code", name_code}};
}

// T09: describe one constraint reference side. The occurrence scope distinguishes
// the assembly's own datum (root reference) from a same-level sibling component;
// a nested path is reported as "nested" and can never be replayed in this phase.
static J assembly_selection_json(ProSelection selection, ProSolid assembly, J &codes) {
    J reference = J::object();
    reference["owner_scope"] = "unknown";
    ProAsmcomppath component_path;
    ProError path_code = ProSelectionAsmcomppathGet(selection, &component_path);
    reference["comppath_query_code"] = path_code;
    if (!path_code) {
        ProMdlName owner_name = {};
        if (!ProMdlMdlnameGet(component_path.owner, owner_name))
            reference["owner_name"] = utf8(owner_name);
        J ids = J::array();
        int levels = component_path.table_num;
        if (levels > PRO_MAX_ASSEM_LEVEL)
            levels = PRO_MAX_ASSEM_LEVEL; // clamp a garbage count defensively
        for (int i = 0; i < levels; ++i)
            ids.push_back(component_path.comp_id_table[i]);
        reference["occurrence_path"] = ids;
        if (levels == 0)
            reference["owner_scope"] = "assembly";
        else {
            reference["owner_scope"] = levels == 1 ? "component" : "nested";
            const int sibling_id = component_path.comp_id_table[0];
            reference["occurrence_component_id"] = sibling_id;
            J label = component_label_json(assembly, sibling_id, codes,
                                           levels == 1 ? "asm_sibling_label" : "nested_label");
            for (auto it = label.begin(); it != label.end(); ++it)
                reference[it.key()] = it.value();
        }
    } else {
        // Some root-level assembly selections carry no component path; the
        // owning model still tells us this is the assembly's own datum instead
        // of leaving an unidentifiable scope.
        ProModelitem selected;
        if (!ProSelectionModelitemGet(selection, &selected) && selected.owner == (ProMdl)assembly)
            reference["owner_scope"] = "assembly";
    }
    ProModelitem item;
    ProError item_code = ProSelectionModelitemGet(selection, &item);
    reference["item_query_code"] = item_code;
    if (!item_code) {
        reference["item_type"] = item.type;
        reference["item_id"] = item.id;
    }
    return reference;
}

static bool reference_identity_known(const J &reference) {
    return reference.is_object() && reference.value("item_query_code", -1) == 0 &&
           reference.contains("item_type") && reference.contains("item_id");
}

static const char *datum_side_name(ProDatumside side) {
    static const std::map<int, const char *> side_names = {{PRO_DATUM_SIDE_YELLOW, "yellow"},
                                                           {PRO_DATUM_SIDE_RED, "red"},
                                                           {PRO_DATUM_SIDE_NONE, "none"}};
    auto found = side_names.find((int)side);
    return found == side_names.end() ? "unknown" : found->second;
}

// T09: one constraint snapshot with both reference identities, both datum
// directions, the offset unit and an explicit replay verdict. The six write
// types this phase can rebuild are mate/align/mate_offset/align_offset/insert/
// csys; fixed and default placements are reported with their real semantics so
// the planner never substitutes one for a constraint it cannot replay.
static J constraint_json(ProAsmcompconstraint constraint, ProAsmcomp *component,
                         const InspectionLengthUnits &owner_units,
                         const MillimeterScale &owner_scale) {
// The shared mapping pins the published ProAsmcompConstrType values; SDK enum
// drift fails the build instead of silently renaming production symbols.
#ifndef CREO_CONSTRAINT_CODES_FALLBACK
    static_assert(PRO_ASM_MATE == 0 && PRO_ASM_MATE_OFF == 1 && PRO_ASM_ALIGN == 2 &&
                      PRO_ASM_ALIGN_OFF == 3 && PRO_ASM_INSERT == 4 && PRO_ASM_ORIENT == 5 &&
                      PRO_ASM_CSYS == 6 && PRO_ASM_TANGENT == 7 && PRO_ASM_PNT_ON_SRF == 8 &&
                      PRO_ASM_EDGE_ON_SRF == 9 && PRO_ASM_DEF_PLACEMENT == 10 &&
                      PRO_ASM_FIX == 13 && PRO_ASM_AUTO == 14,
                  "ProAsmcompConstrType drifted; refresh native/constraint_names.h");
#endif
    J item = J::object();
    J codes = J::object();
    ProAsmcompConstrType type = PRO_ASM_FIX;
    const int type_code = ProAsmcompconstraintTypeGet(constraint, &type);
    codes["type"] = type_code;
    const bool type_known = type_code == PRO_TK_NO_ERROR;
    const char *type_name = type_known ? assembly_constraint_type_name((int)type) : nullptr;
    item["type"] = type_name ? type_name : "unknown";
    if (type_known)
        item["type_code"] = (int)type;
    double offset = 0.0;
    const int offset_code = ProAsmcompconstraintOffsetGet(constraint, &offset);
    codes["offset"] = offset_code;
    const bool offset_known = offset_code == PRO_TK_NO_ERROR && std::isfinite(offset);
    item["offset"] = offset_known ? J(offset) : J(nullptr);
    item["offset_unit"] = length_unit_json(owner_units, owner_scale);
    item["offset_mm"] =
        offset_known && owner_scale.known ? J(offset * owner_scale.scale) : J(nullptr);
    ProSelection selection = nullptr;
    ProDatumside asm_side = PRO_DATUM_SIDE_NONE;
    const int asm_code = ProAsmcompconstraintAsmreferenceGet(constraint, &selection, &asm_side);
    codes["asm_reference"] = asm_code;
    item["asm_reference"] =
        asm_code || !selection
            ? J(nullptr)
            : assembly_selection_json(selection, (ProSolid)component->owner, codes);
    if (!asm_code && selection)
        ProSelectionFree(&selection);
    selection = nullptr;
    ProDatumside comp_side = PRO_DATUM_SIDE_NONE;
    const int comp_code = ProAsmcompconstraintCompreferenceGet(constraint, &selection, &comp_side);
    codes["comp_reference"] = comp_code;
    item["comp_reference"] =
        comp_code || !selection
            ? J(nullptr)
            : assembly_selection_json(selection, (ProSolid)component->owner, codes);
    if (!comp_code && selection)
        ProSelectionFree(&selection);
    // Both directions are kept separately; "orientation" stays the legacy
    // single field and follows the component side unless that query failed.
    item["asm_side"] = asm_code ? J(nullptr) : J(datum_side_name(asm_side));
    item["comp_side"] = comp_code ? J(nullptr) : J(datum_side_name(comp_side));
    item["orientation"] = comp_code ? (asm_code ? J("unknown") : J(datum_side_name(asm_side)))
                                    : J(datum_side_name(comp_side));
    // Placement-only constraints keep their real semantics. Anything else must
    // be one of the six supported write types to be replayable.
    const bool placement = type_known && (type == PRO_ASM_FIX || type == PRO_ASM_DEF_PLACEMENT);
    const bool automatic = type_known && type == PRO_ASM_AUTO;
    if (placement)
        item["placement_kind"] = type == PRO_ASM_FIX ? "fixed" : "default";
    else if (automatic)
        item["placement_kind"] = "auto";
    const bool supported =
        type_known && (type == PRO_ASM_MATE || type == PRO_ASM_MATE_OFF || type == PRO_ASM_ALIGN ||
                       type == PRO_ASM_ALIGN_OFF || type == PRO_ASM_INSERT || type == PRO_ASM_CSYS);
    const J &asm_reference = item["asm_reference"];
    const J &comp_reference = item["comp_reference"];
    const bool asm_known = reference_identity_known(asm_reference);
    const bool comp_known = reference_identity_known(comp_reference);
    const std::string asm_scope =
        asm_reference.is_object() ? asm_reference.value("owner_scope", "unknown") : "unknown";
    const std::string comp_scope =
        comp_reference.is_object() ? comp_reference.value("owner_scope", "unknown") : "unknown";
    const bool comp_own = comp_known && comp_scope == "component" &&
                          comp_reference.value("occurrence_component_id", -1) == component->id;
    const bool offset_type = type_known && (type == PRO_ASM_MATE_OFF || type == PRO_ASM_ALIGN_OFF);
    bool replayable = false;
    const char *reason = nullptr;
    if (!type_known) {
        reason = "type_query_failed";
    } else if (placement) {
        replayable = true; // a real fixed/default placement, not a constraint replay
    } else if (automatic) {
        reason = "automatic_placement";
    } else if (!supported) {
        reason = "unsupported_type";
    } else if (!asm_known) {
        reason = "missing_assembly_reference";
    } else if (!comp_known) {
        reason = "missing_component_reference";
    } else if (asm_scope == "nested" || comp_scope == "nested") {
        reason = "nested_reference";
    } else if (!comp_own) {
        reason = "component_reference_not_own_component";
    } else if (!offset_known) {
        reason = "offset_query_failed";
    } else if (offset_type && !owner_scale.known) {
        reason = "offset_unit_unknown";
    } else {
        replayable = true;
    }
    item["replayable"] = replayable;
    item["reason"] = reason ? J(reason) : J(nullptr);
    item["query_codes"] = codes;
    return item;
}

static J component_constraints_json(ProAsmcomp *component, J &codes,
                                    const InspectionLengthUnits &owner_units,
                                    const MillimeterScale &owner_scale) {
    J constraints = J::array();
    ProAsmcompconstraint *list = nullptr;
    // The comppath form with the owning-assembly path is the supported read;
    // a NULL path crashed native runs on Creo 12, so the path is always built.
    ProIdTable ids = {};
    ids[0] = component->id;
    ProAsmcomppath owner_path;
    ProError path_code = ProAsmcomppathInit((ProSolid)component->owner, ids, 1, &owner_path);
    codes["constraint_comppath"] = path_code;
    ProError code =
        path_code ? path_code : ProAsmcompConstraintsWithComppathGet(component, &owner_path, &list);
    codes["constraints"] = code;
    if (code == PRO_TK_NO_ERROR && list) {
        int count = 0;
        if (!ProArraySizeGet((ProArray)list, &count))
            for (int i = 0; i < count; ++i) {
                constraints.push_back(
                    constraint_json(list[i], component, owner_units, owner_scale));
            }
        ProAsmcompconstraintArrayFree(list);
    } else if (code == PRO_TK_E_NOT_FOUND) {
        codes["constraints"] = 0; // no constraints recorded: packaged placement
    }
    return constraints;
}

static ProError assembly_feature_callback(ProFeature *feature, ProError status, ProAppData data) {
    auto *context = (WalkContext *)data;
    AssemblyWalkState &walk = *context->walk;
    if (status)
        return status;
    if (walk.truncated)
        return PRO_TK_NO_ERROR;
    ProFeattype type;
    ProError type_code = ProFeatureTypeGet(feature, &type);
    if (!walk.apply_query_outcome(type_code)) {
        // An unclassifiable feature may be a component whose whole subtree
        // would silently drop out of the walk; keep visiting siblings but
        // drop the tree completeness claim.
        log("WALK_TYPE_QUERY_FAILED=%d\n", (int)type_code);
        return PRO_TK_NO_ERROR;
    }
    if (type != PRO_FEAT_COMPONENT)
        return PRO_TK_NO_ERROR;
    auto *component = (ProAsmcomp *)feature;
    J item = J::object();
    J codes = J::object();
    std::vector<int> occurrence = context->path;
    occurrence.push_back(feature->id);
    J path_json = J::array();
    for (int id : occurrence)
        path_json.push_back(id);
    J parent_json = J::array();
    for (int id : context->path)
        parent_json.push_back(id);
    item["component_id"] = feature->id;
    item["occurrence_path"] = path_json;
    item["parent_path"] = parent_json;
    item["depth"] = context->depth;
    // T09: the occurrence label is the same-level component identity a replay
    // mapping names; the numeric id stays for traceability.
    J component_label =
        component_label_json((ProSolid)component->owner, feature->id, codes, "occurrence_label");
    for (auto it = component_label.begin(); it != component_label.end(); ++it)
        item[it.key()] = it.value();
    ProFeatStatus feature_status = PRO_FEAT_ACTIVE;
    int status_code = ProFeatureStatusGet(feature, &feature_status);
    codes["feature_status"] = status_code;
    item["feature_status"] = status_code ? J(nullptr) : J((int)feature_status);
    // The component's own feature state (active or suppressed) must stay
    // confirmable; a failed query drops completeness through the shared
    // query outcome judgement instead of a duplicated condition (BUG-080).
    walk.apply_query_outcome((ProError)status_code);
    item["suppressed"] = status_code ? J(nullptr)
                                     : J(feature_status == PRO_FEAT_SUPPRESSED ||
                                         feature_status == PRO_FEAT_FAMTAB_SUPPRESSED ||
                                         feature_status == PRO_FEAT_SIMP_REP_SUPPRESSED ||
                                         feature_status == PRO_FEAT_PROG_SUPPRESSED);
    ProBoolean packaged = PRO_B_FALSE;
    int packaged_code = ProAsmcompIsPackaged(component, &packaged);
    codes["packaged"] = packaged_code;
    item["packaged"] = packaged_code ? J(nullptr) : J(packaged == PRO_B_TRUE);
    ProMdl child = nullptr;
    ProError model_code = ProAsmcompMdlGet(component, &child);
    codes["model"] = model_code;
    if (model_code || !child) {
        // The component feature exists but its model did not resolve (for
        // example a missing file); keep the node observable instead of
        // failing. The shared missing-node operation stamps the resolved /
        // subtree flags itself and drops completeness.
        item.update({{"name", nullptr}, {"model_type", nullptr}, {"constraints", J::array()}});
        item["query_codes"] = codes;
        walk.record_missing_component(item);
        return PRO_TK_NO_ERROR;
    }
    item["resolved"] = true;
    J observed = observe_session_model(child, "", context->current, context->current_code);
    ProMdlType kind = PRO_MDL_PART;
    ProError kind_code = ProMdlTypeGet(child, &kind);
    codes["model_type"] = kind_code;
    // An unclassifiable child model may hide a whole sub-assembly; the node
    // stays observable but the tree completeness claim is dropped through
    // the shared query outcome judgement.
    walk.apply_query_outcome(kind_code);
    const char *kind_name = kind_code ? "" : kind == PRO_MDL_ASSEMBLY ? "assembly" : "part";
    observed["model_type"] = kind_code ? J(nullptr) : J(kind_name);
    ProMdlsubtype subtype = PROMDLSTYPE_PART_SOLID;
    if (!kind_code && kind == PRO_MDL_PART && !ProMdlSubtypeGet(child, &subtype) &&
        subtype == PROMDLSTYPE_PART_SHEETMETAL)
        observed["model_type"] = "sheetmetal";
    for (auto it = observed.begin(); it != observed.end(); ++it)
        item[it.key()] = it.value();
    // observed carries the child's session-identity query codes
    // (name/origin/modified/id); merge them into the node codes so that
    // executed diagnosis survives instead of being overwritten below.
    if (observed.contains("query_codes")) {
        for (auto it = observed["query_codes"].begin(); it != observed["query_codes"].end(); ++it)
            codes[it.key()] = it.value();
    }
    // BUG-080: query the real component/owner units next to the transform and
    // normalize to a full millimeter coordinate map; the raw matrix is always
    // kept, and the normalized map stays null (never pretend-mm) whenever the
    // transform or any required unit scale is unknown.
    InspectionLengthUnits component_units = inspect_length_units(child);
    InspectionLengthUnits parent_units = inspect_length_units((ProMdl)component->owner);
    MillimeterScale component_scale = length_scale_to_mm(child, component_units);
    MillimeterScale parent_scale = length_scale_to_mm((ProMdl)component->owner, parent_units);
    item["units"] = {{"component", length_unit_json(component_units, component_scale)},
                     {"parent", length_unit_json(parent_units, parent_scale)}};
    ProMatrix to_parent = {};
    ProError transform_code = component_to_assembly_transform(component, to_parent);
    codes["transform"] = transform_code;
    // BUG-080 follow-up: a successful query whose returned matrix contains
    // NaN/Infinity is not a known map; serializing it would emit null entries
    // while transform_known stayed true, so the raw map is dropped instead.
    const bool raw_map_known = local_transform_known(transform_code, to_parent);
    ProMatrix to_parent_mm = {};
    bool parent_map_known =
        raw_map_known && component_scale.known && parent_scale.known &&
        normalize_transform_mm(to_parent, component_scale.scale, parent_scale.scale, to_parent_mm);
    item["transform_to_parent"] = parent_map_known ? matrix_json(to_parent_mm) : J(nullptr);
    item["transform_to_parent_raw"] = raw_map_known ? matrix_json(to_parent) : J(nullptr);
    item["transform_known"] = raw_map_known;
    item["transform_mm_known"] = parent_map_known;
    if (!transform_code && !parent_map_known)
        item["transform_unknown_reason"] = !raw_map_known ? "non_finite"
                                           : (!component_scale.known || !parent_scale.known)
                                               ? "unknown_units"
                                               : "invalid_scale";
    // Root maps come from the shared chain composition: a chain exists only
    // while this local map and every ancestor step stayed known, and finite
    // overflow poisons the chain instead of serializing null inside a
    // "known" transform. A failed parent transform or unknown ancestor unit
    // therefore yields null root maps here, never a reused grandparent.
    WalkChainStep step = walk_chain_compose(context->chain, to_parent, raw_map_known, to_parent_mm,
                                            parent_map_known);
    item["transform_to_root_raw"] =
        step.root_raw_known ? matrix_json(step.to_root_raw) : J(nullptr);
    item["transform_to_root"] = step.root_mm_known ? matrix_json(step.to_root_mm) : J(nullptr);
    item["transform_root_known"] = step.root_mm_known;
    // An unknown local or root chain, or an overflowing combination, makes
    // the report incomplete; the node's own known local maps stay observable.
    if (!parent_map_known || !step.root_mm_known || !step.root_raw_known)
        walk.mark_incomplete();
    item["constraints"] = component_constraints_json(component, codes, parent_units, parent_scale);
    item["query_codes"] = codes;
    const size_t node_index = walk.record_node(item);
    if (walk.truncated)
        return PRO_TK_NO_ERROR;
    if (!kind_code && kind == PRO_MDL_ASSEMBLY) {
        WalkContext sub;
        sub.owner = (ProSolid)child;
        sub.path = occurrence;
        // Propagate both chains through the shared step: a failed local
        // transform, unknown unit or overflow poisons the descendant
        // root maps instead of reusing the grandparent matrix.
        sub.chain = walk_chain_descend(context->chain, step);
        sub.walk = context->walk;
        sub.current = context->current;
        sub.current_code = context->current_code;
        sub.depth = context->depth + 1;
        // The shared visit operation enforces the depth limit before the
        // visit and diagnoses a failed sub-assembly walk on the stored node
        // (node_index) instead of failing the whole report �?sibling
        // components stay observable.
        walk.visit_subtree(context->depth, node_index, [&sub]() -> ProError {
            return ProSolidFeatVisit(sub.owner, assembly_feature_callback, nullptr,
                                     (ProAppData)&sub);
        });
    }
    return PRO_TK_NO_ERROR;
}

static void session_assembly_native(const J &request, J &report) {
    const J &choice = request.at("session_assembly");
    std::wstring requested = wide(choice.at("name").get<std::string>());
    if (requested.empty())
        throw std::runtime_error("SESSION_ASSEMBLY_NAME_REQUIRED: pass the resident "
                                 "assembly name from creo_list_session_models");
    ProName name = {};
    wcscpy_s(name, requested.c_str());
    ProMdl mdl = nullptr;
    ProError found = ProMdlInit(name, PRO_MDL_ASSEMBLY, &mdl);
    if (found == PRO_TK_E_NOT_FOUND)
        throw std::runtime_error("SESSION_ASSEMBLY_NOT_FOUND: no resident assembly with that name; "
                                 "select one from creo_list_session_models");
    check(found, "ProMdlInit");
    ProMdlType kind = PRO_MDL_ASSEMBLY;
    check(ProMdlTypeGet(mdl, &kind), "ProMdlTypeGet");
    if (kind != PRO_MDL_ASSEMBLY)
        throw std::runtime_error("SESSION_ASSEMBLY_TYPE_MISMATCH: the resident model "
                                 "with that name is not an assembly");
    ProMdl current = nullptr;
    int current_code = ProMdlCurrentGet(&current);
    AssemblyWalkState walk;
    walk.budget = 4096;
    // Query the root length unit before the walk: it decides whether the
    // normalized root chain is interpretable at all. The shared root
    // initialization ties the root chain validity to the real root unit and
    // marks an unknown root unit incomplete up front, so even an empty tree
    // is globally incomplete then.
    InspectionLengthUnits root_units = inspect_length_units(mdl);
    MillimeterScale root_scale = length_scale_to_mm(mdl, root_units);
    WalkContext context;
    context.owner = (ProSolid)mdl;
    context.walk = &walk;
    context.current = current;
    context.current_code = current_code;
    walk.init_root_chain(context.chain, root_scale);
    // A failed root visit makes the report incomplete (root_visit_code)
    // instead of throwing away the whole inspection.
    int root_visit_code =
        ProSolidFeatVisit(context.owner, assembly_feature_callback, nullptr, (ProAppData)&context);
    if (root_visit_code)
        walk.record_root_visit_failure();
    J root = observe_session_model(mdl, "assembly", current, current_code);
    root["length_unit"] = length_unit_json(root_units, root_scale);
    report.update(
        {{"success", true},
         {"assembly", root},
         {"components", walk.components},
         {"component_count", walk.components.size()},
         {"truncated", walk.truncated},
         {"depth_limited", walk.depth_limited},
         {"root_visit_code", root_visit_code},
         {"incomplete", walk.incomplete},
         {"complete", walk.complete(root_scale.known)},
         {"transform_convention",
          "row-vector 4x4 matrices in Creo ProMatrix order (p' = p * M); translation occupies "
          "the last row; transform_to_parent and transform_to_root are normalized full "
          "coordinate maps with input and output coordinates in millimeters; "
          "transform_to_parent_raw and transform_to_root_raw keep the raw Creo matrices "
          "mapping member-solid coordinates (member length unit) into owner/root-solid "
          "coordinates (owner/root length unit); per-node units.component/units.parent and "
          "assembly.length_unit carry the real unit names, query codes and millimeter scales "
          "and are null when unknown - normalized transforms are then null too instead of "
          "pretending millimeters; constraint offsets stay in the owning assembly length "
          "unit; raw cross-unit matrix semantics follow the local SDK member-transform "
          "documentation and remain pending real mixed-unit machine verification"},
         {"readonly_note", "inspection only: no component loading, activation, "
                           "regeneration, save, adoption or managed revision"}});
}

// FEAT-046: explicit, evidence-bound erasure of selected session models.
// No saves and no disk deletion; assemblies erase before their components;
// every item re-verifies identity, modification state and references, and
// each erasure is confirmed absent through two independent queries before
// success is reported. The whole job runs under one Toolkit channel lock.
struct EraseModel {
    std::wstring name;
    std::string model_type;
    std::string key; // lowercase name + "|" + family (part|assembly)
    ProMdl mdl = nullptr;
    ProPath origin = {};
    bool modified = false;
    bool has_origin = false;
};

static std::string erase_family(const std::string &model_type) {
    return model_type == "assembly" ? "assembly" : "part";
}

static std::string erase_key(const std::wstring &name, const std::string &model_type) {
    std::string lowered;
    for (wchar_t c : name)
        lowered += static_cast<char>(towlower(c));
    return lowered + "|" + erase_family(model_type);
}

// One dependency enumeration over every session part/assembly: each entry maps
// a session key to the set of session keys it depends on.
static std::map<std::string, std::vector<std::string>> session_dependency_graph(
    const std::vector<EraseModel> &models, J &query_errors) {
    std::map<std::string, std::vector<std::string>> graph;
    for (const auto &model : models) {
        ProMdlnameShortdata *names = nullptr;
        ProMdlfileType *types = nullptr;
        int count = 0;
        ProError code = ProMdlDependenciesDataList(model.mdl, &names, &types, &count);
        if (code == PRO_TK_E_NOT_FOUND) {
            graph[model.key] = {};
            continue;
        }
        if (code != PRO_TK_NO_ERROR) {
            query_errors.push_back({{"key", model.key}, {"code", code}});
            graph[model.key] = {};
            continue;
        }
        try {
            std::vector<std::string> dependencies;
            for (int i = 0; i < count; ++i) {
                std::string family = types[i] == PRO_MDLFILE_ASSEMBLY ? "assembly" : "part";
                dependencies.push_back(erase_key(std::wstring(names[i].name), family));
            }
            graph[model.key] = dependencies;
        } catch (...) {
            ProArrayFree((ProArray *)&names);
            ProArrayFree((ProArray *)&types);
            throw;
        }
        ProArrayFree((ProArray *)&names);
        ProArrayFree((ProArray *)&types);
    }
    return graph;
}

static void session_erase_native(const J &request, J &report) {
    const J &choice = request.at("session_erase");
    const std::string action = choice.at("action");
    if (action != "inspect" && action != "apply")
        throw std::runtime_error("Unknown session-erase action");
    generic_stage("session_erase_inventory");
    SessionInventory inventory;
    collect_session_models(inventory);
    if (!inventory.type_errors.empty() || inventory.truncated)
        throw std::runtime_error(
            "SESSION_ENUMERATION_INCOMPLETE: the session inventory could not be "
            "completed, so erase preconditions cannot be proven; nothing was erased");
    // Fresh handles for every session part/assembly (the inventory above only
    // keeps names).
    ProMdl current = nullptr;
    int current_code = ProMdlCurrentGet(&current);
    std::vector<EraseModel> session;
    std::vector<std::wstring> managed_roots;
    if (choice.contains("managed_roots"))
        for (const auto &root : choice.at("managed_roots"))
            managed_roots.push_back(wide(root.get<std::string>()));
    for (const auto &pair : std::initializer_list<std::pair<ProMdlType, const char *>>{
             {PRO_MDL_PART, "part"}, {PRO_MDL_ASSEMBLY, "assembly"}}) {
        ProMdl *list = nullptr;
        int count = 0;
        ProError listed = ProSessionMdlList(pair.first, &list, &count);
        if (listed == PRO_TK_E_NOT_FOUND)
            continue;
        check(listed, "ProSessionMdlList(erase)");
        try {
            for (int i = 0; i < count; ++i) {
                EraseModel model;
                model.model_type = pair.second;
                if (pair.first == PRO_MDL_PART) {
                    ProMdlsubtype subtype;
                    if (!ProMdlSubtypeGet(list[i], &subtype) &&
                        subtype == PROMDLSTYPE_PART_SHEETMETAL)
                        model.model_type = "sheetmetal";
                }
                ProMdlName name = {};
                if (!ProMdlMdlnameGet(list[i], name))
                    model.name = name;
                ProError oc = ProMdlOriginGet(list[i], model.origin);
                model.has_origin = !oc && model.origin[0] != 0;
                ProBoolean modified = PRO_B_FALSE;
                model.modified =
                    !ProMdlModificationVerify(list[i], &modified) && modified == PRO_B_TRUE;
                model.mdl = list[i];
                model.key = erase_key(model.name, model.model_type);
                session.push_back(model);
            }
        } catch (...) {
            if (list)
                ProArrayFree((ProArray *)&list);
            throw;
        }
        if (list)
            CK(ProArrayFree((ProArray *)&list));
    }
    auto find = [&](const std::wstring &name, const std::string &model_type) {
        std::string wanted = erase_key(name, model_type);
        const EraseModel *found = nullptr;
        for (const auto &model : session)
            if (model.key == wanted) {
                if (found)
                    throw std::runtime_error(
                        "SESSION_ERASE_AMBIGUOUS: more than one session model matches a "
                        "target; refuse instead of picking one");
                found = &model;
            }
        return found;
    };
    auto is_managed = [&](const EraseModel &model) {
        for (const auto &root : managed_roots) {
            std::wstring prefix = root;
            if (!prefix.empty() && prefix.back() != L'\\')
                prefix += L"\\";
            if (!_wcsnicmp(model.origin, prefix.c_str(), prefix.size()))
                return true;
        }
        return false;
    };

    J targets = J::array();
    std::vector<const EraseModel *> manifest;
    for (const auto &target : choice.at("targets")) {
        std::wstring name = wide(target.at("name").get<std::string>());
        std::string model_type = target.value("model_type", "part");
        const EraseModel *model = find(name, model_type);
        J entry = {{"name", utf8(name)}, {"model_type", model_type}};
        if (!model) {
            entry["blocked"] = {{"reason", "not_in_session"},
                                {"message", "No session model matches this name and type"}};
        } else {
            int id = -1;
            ProMdlIdGet(model->mdl, &id);
            entry.update({
                {"session_model_id", id},
                {"origin", model->has_origin ? J(utf8(model->origin)) : J(nullptr)},
                {"modified", model->modified},
                {"is_current", current_code ? J(nullptr) : J(model->mdl == current)},
            });
            if (!model->has_origin)
                entry["blocked"] = {{"reason", "never_saved"},
                                    {"message",
                                     "The model has no saved origin; explicit erase covers "
                                     "saved session objects only"}};
            else if (model->modified)
                // BUG-106: the refusal is only half the story. Saving in the
                // GUI clears the dirty flag, but the inspect/apply cycle then
                // has to be repeated, or the same block comes back.
                entry["blocked"] = {
                    {"reason", "modified"},
                    {"message",
                     "The model has unsaved changes; save it in Creo (File > Save) or "
                     "discard the changes there, then call "
                     "creo_erase_session_models(action='inspect') again and apply the same "
                     "targets. Erasing does not save or discard for you"}};
            else if (is_managed(*model))
                entry["blocked"] = {{"reason", "managed"},
                                    {"message",
                                     "The model belongs to this service's managed output; use "
                                     "creo_reconcile_model instead of erasing it here"}};
            else
                manifest.push_back(model);
        }
        targets.push_back(entry);
    }
    // Bind a reference: json value semantics would detach every later update
    // of the summary from the report.
    report["session_erase"] = {{"targets", targets}, {"action", action}};
    J &summary = report["session_erase"];
    if (action == "inspect") {
        // Reference graph over the whole session: an outside model referencing
        // a manifest target, or a cycle inside the manifest, blocks erasure.
        generic_stage("session_erase_reference_check");
        J query_errors = J::array();
        auto graph = session_dependency_graph(session, query_errors);
        if (!query_errors.empty())
            throw std::runtime_error(
                "SESSION_ERASE_DEPENDENCY_QUERY_FAILED: dependency enumeration "
                "failed for at least one session model; preconditions cannot be "
                "proven; nothing was erased");
        std::set<std::string> manifest_keys;
        for (const EraseModel *model : manifest)
            manifest_keys.insert(model->key);
        bool blocked = false;
        for (auto &entry : targets)
            if (!entry.contains("blocked")) {
                std::string key = erase_key(wide(entry["name"].get<std::string>()),
                                            entry["model_type"].get<std::string>());
                for (const auto &[holder, dependencies] : graph) {
                    if (manifest_keys.count(holder))
                        continue;
                    for (const auto &dependency : dependencies)
                        if (dependency == key) {
                            blocked = true;
                            entry["blocked"] = {
                                {"reason", "referenced_outside_manifest"},
                                {"message",
                                 "A session model outside the erase manifest references "
                                 "this target; add it to the manifest or erase it in Creo"}};
                        }
                }
            }
        // Topological erase order: a model no in-manifest model depends on
        // goes first; dependents always erase before their dependencies.
        std::map<std::string, int> dependents;
        for (const auto &key : manifest_keys)
            dependents[key] = 0;
        for (const auto &key : manifest_keys)
            for (const auto &dependency : graph[key])
                if (dependents.count(dependency))
                    dependents[dependency] += 1;
        std::vector<std::string> order;
        std::set<std::string> placed;
        while (order.size() < manifest_keys.size()) {
            bool progressed = false;
            for (const auto &key : manifest_keys) {
                if (placed.count(key) || dependents[key] > 0)
                    continue;
                placed.insert(key);
                order.push_back(key);
                for (const auto &dependency : graph[key])
                    if (dependents.count(dependency))
                        dependents[dependency] -= 1;
                progressed = true;
            }
            if (!progressed) {
                summary.update({
                    {"available", false},
                    {"reason_code", "dependency_cycle"},
                    {"message", "The manifest contains a dependency cycle; no erase order "
                                "exists; nothing was erased"},
                });
                return;
            }
        }
        J erase_order = J::array();
        for (const auto &key : order) {
            for (const auto &entry : targets)
                if (!entry.contains("blocked") &&
                    erase_key(wide(entry["name"].get<std::string>()),
                              entry["model_type"].get<std::string>()) == key)
                    erase_order.push_back({{"name", entry["name"]},
                                           {"model_type", entry["model_type"]},
                                           {"origin", entry["origin"]},
                                           {"modified", entry["modified"]}});
        }
        J remaining = J::array();
        for (const auto &model : session) {
            if (!manifest_keys.count(model.key))
                remaining.push_back({{"name", utf8(model.name)},
                                     {"model_type", model.model_type},
                                     {"modified", model.modified}});
        }
        bool any_blocked = false;
        for (const auto &entry : targets)
            if (entry.contains("blocked"))
                any_blocked = true;
        summary.update({
            {"available", !any_blocked},
            {"reason_code", any_blocked ? J("blocked_targets") : J(nullptr)},
            {"erase_order", erase_order},
            {"remaining_after", remaining},
            {"message", any_blocked ? "One or more targets are blocked; nothing was erased; "
                                      "resolve the blocking reasons and inspect again"
                                    : "Erase plan verified; apply with the evidence token to "
                                      "execute exactly this manifest"},
        });
        report["success"] = true;
        return;
    }

    // apply: execute exactly the manifest from the token, one item at a time.
    generic_stage("session_erase_apply");
    J erased = J::array();
    J unconfirmed = nullptr;
    std::set<std::string> done;
    for (const auto &item : choice.at("erase_order")) {
        std::wstring name = wide(item.at("name").get<std::string>());
        std::string model_type = item.at("model_type");
        std::string key = erase_key(name, model_type);
        const EraseModel *model = find(name, model_type);
        if (!model) {
            if (done.empty())
                throw std::runtime_error(
                    "SESSION_ERASE_IDENTITY_CHANGED: the first manifest item is no "
                    "longer in the session; refuse instead of erasing a changed "
                    "session; nothing was erased");
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "relocate"},
                           {"message", "The item disappeared from the session before its "
                                       "turn; earlier items stay erased"}};
            break;
        }
        if (model->modified) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "modification_recheck"},
                           {"message", "The item reports unsaved changes now; it was not "
                                       "erased; earlier items stay erased"}};
            break;
        }
        std::wstring expected = wide(item.at("origin").get<std::string>());
        if (model->has_origin && _wcsicmp(model->origin, expected.c_str())) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "origin_recheck"},
                           {"message", "The item's origin changed since the token was "
                                       "issued; it was not erased; earlier items stay "
                                       "erased"}};
            break;
        }
        if (is_managed(*model)) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "managed_recheck"},
                           {"message", "The item now looks managed by this service; it "
                                       "was not erased; earlier items stay erased"}};
            break;
        }
        CK(ProMdlErase(model->mdl));
        // Confirm absence through two independent queries; a zero return from
        // ProMdlErase alone never reports success.
        ProMdl probe = nullptr;
        ProName locate = {};
        wcsncpy_s(locate, model->name.c_str(), _TRUNCATE);
        ProError first =
            ProMdlInit(locate, model_type == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART, &probe);
        ProMdl *residue = nullptr;
        int residue_count = 0;
        ProError listed = ProSessionMdlList(
            model_type == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART, &residue, &residue_count);
        bool absent = first == PRO_TK_E_NOT_FOUND;
        if (listed == PRO_TK_NO_ERROR) {
            for (int i = 0; i < residue_count && absent; ++i) {
                ProMdlName other = {};
                if (!ProMdlMdlnameGet(residue[i], other) && !_wcsicmp(other, model->name.c_str()))
                    absent = false;
            }
            ProArrayFree((ProArray *)&residue);
        } else if (listed != PRO_TK_E_NOT_FOUND) {
            check(listed, "ProSessionMdlList(erase-confirm)");
        }
        if (!absent) {
            unconfirmed = {{"name", item.at("name")},
                           {"stage", "absence_confirmation"},
                           {"message", "ProMdlErase returned success but the model is "
                                       "still observable in the session; it stays listed "
                                       "as not confirmed erased"}};
            break;
        }
        done.insert(key);
        erased.push_back({{"name", item.at("name")}, {"model_type", model_type}});
    }
    SessionInventory after;
    collect_session_models(after);
    J remaining_after = J::array();
    for (const auto &item2 : after.models)
        remaining_after.push_back(item2);
    summary.update({
        {"erased", erased},
        {"unconfirmed", unconfirmed},
        {"remaining_after", remaining_after},
        {"stopped_early", !unconfirmed.is_null()},
        {"message", unconfirmed.is_null()
                        ? "Manifest erased and confirmed absent; nothing was saved and "
                          "no disk file was deleted"
                        : "Erasure stopped at an item; erased items stay erased; "
                          "unconfirmed and remaining items are listed explicitly"},
    });
    report["success"] = unconfirmed.is_null();
    if (!unconfirmed.is_null())
        report["message"] = summary["message"];
}

// BUG-096 (Q03/E): failed new-model orphan cleanup. A failed "new" job leaves
// an unsaved session object that blocks the next same-name model ("New model
// name already exists in the Creo session"). Cleanup erases at most the single
// object proven to be the one this job created (ProMdlnameCopy handle + id),
// after re-checking identity and dependencies, inside the same Toolkit lock.
// Vetoes keep the object and the receipt says why; nothing is erased without
// proof. Reasons mirror src/creo_mechdog/failed_model_cleanup.py and
// tests/unit/test_failed_model_cleanup.py. This is NOT the restore-checkpoint
// rollback (rollback_* keeps its old meaning) and never touches
// unknown/recovery protection: no erase_all, no adoption, no retries.
struct NewModelEvidence {
    bool created = false; // this run performed ProMdlnameCopy
    int id = -1;          // ProMdlIdGet captured at creation
    bool id_known = false;
    bool baseline_known = false; // modification probe captured at creation
    bool baseline_modified = false;
    bool ops_mutated = false; // a plan operation mutated the model
};
static NewModelEvidence new_model_evidence;

static J cleanup_receipt(bool attempted, const std::string &status, const std::string &reason,
                         J erase_code, bool absence_verified) {
    return {{"attempted", attempted},
            {"status", status},
            {"reason", reason},
            {"erase_code", erase_code},
            {"absence_verified", absence_verified}};
}

// Two independent absence queries (the session_erase_native apply pattern):
// a name lookup plus a session-list scan. Returns true only when both run and
// agree the name is gone; query_ok reports whether both queries returned.
static bool confirm_name_absent(const std::wstring &name, ProMdlType mdltype, bool &query_ok) {
    query_ok = true;
    ProMdl probe = nullptr;
    ProName locate = {};
    wcsncpy_s(locate, name.c_str(), _TRUNCATE);
    ProError first = ProMdlInit(locate, mdltype, &probe);
    if (first == PRO_TK_NO_ERROR)
        return false;
    if (first != PRO_TK_E_NOT_FOUND) {
        query_ok = false;
        return false;
    }
    ProMdl *residue = nullptr;
    int residue_count = 0;
    ProError listed = ProSessionMdlList(mdltype, &residue, &residue_count);
    if (listed == PRO_TK_E_NOT_FOUND)
        return true;
    if (listed != PRO_TK_NO_ERROR) {
        query_ok = false;
        return false;
    }
    bool absent = true;
    for (int i = 0; i < residue_count; ++i) {
        ProMdlName other = {};
        if (!ProMdlMdlnameGet(residue[i], other) && !_wcsicmp(other, name.c_str()))
            absent = false;
    }
    ProArrayFree((ProArray *)&residue);
    return absent;
}

// Inbound references from other session models. query_ok reports whether every
// dependency enumeration returned; an error means safety cannot be proven.
static bool referenced_by_other_model(const std::wstring &name, ProMdlType mdltype, ProMdl self,
                                      bool &query_ok) {
    query_ok = true;
    std::string family = mdltype == PRO_MDL_ASSEMBLY ? "assembly" : "part";
    std::string key = erase_key(name, family);
    bool referenced = false;
    for (ProMdlType type : {PRO_MDL_PART, PRO_MDL_ASSEMBLY}) {
        ProMdl *list = nullptr;
        int count = 0;
        ProError listed = ProSessionMdlList(type, &list, &count);
        if (listed == PRO_TK_E_NOT_FOUND)
            continue;
        if (listed != PRO_TK_NO_ERROR) {
            query_ok = false;
            return referenced;
        }
        for (int i = 0; i < count; ++i) {
            if (list[i] == self)
                continue;
            ProMdlnameShortdata *names = nullptr;
            ProMdlfileType *types = nullptr;
            int dep_count = 0;
            ProError code = ProMdlDependenciesDataList(list[i], &names, &types, &dep_count);
            if (code == PRO_TK_E_NOT_FOUND)
                continue;
            if (code != PRO_TK_NO_ERROR) {
                query_ok = false;
                ProArrayFree((ProArray *)&list);
                return referenced;
            }
            for (int j = 0; j < dep_count; ++j) {
                std::string dep_family = types[j] == PRO_MDLFILE_ASSEMBLY ? "assembly" : "part";
                if (erase_key(std::wstring(names[j].name), dep_family) == key)
                    referenced = true;
            }
            ProArrayFree((ProArray *)&names);
            ProArrayFree((ProArray *)&types);
        }
        ProArrayFree((ProArray *)&list);
    }
    return referenced;
}

static J failed_model_cleanup_receipt(const J &request, bool connected) {
    if (!request.is_object() || !request.value("new", false))
        return cleanup_receipt(false, "skipped", "not_new_model_job", nullptr, false);
    if (!connected)
        return cleanup_receipt(false, "skipped", "no_session_lookup", nullptr, false);
    std::string model_type = "part";
    if (request.contains("model") && request["model"].is_object())
        model_type = request["model"].value("model_type", "part");
    ProMdlType mdltype = model_type == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART;
    ProName locate = {};
    wcsncpy_s(locate, model_name.c_str(), _TRUNCATE);
    ProMdl found = nullptr;
    ProError code = ProMdlInit(locate, mdltype, &found);
    if (code == PRO_TK_E_NOT_FOUND) {
        // Nothing holds the name; the absence queries must run and agree
        // before the receipt may claim absence_verified.
        bool query_ok = false;
        bool absent = confirm_name_absent(model_name, mdltype, query_ok);
        if (!query_ok || !absent)
            return cleanup_receipt(true, "skipped", "safety_query_failed", nullptr, false);
        return cleanup_receipt(true, "skipped",
                               new_model_evidence.created ? "orphan_already_absent"
                                                          : "no_orphan_created",
                               nullptr, true);
    }
    if (code != PRO_TK_NO_ERROR)
        return cleanup_receipt(true, "skipped", "safety_query_failed", nullptr, false);
    // Collect every probe before the veto chain so a failed query is always
    // reported as safety_query_failed and never as a specific veto it could
    // not prove (mirrors evaluate_candidate's precedence).
    bool safety_query_failed = false;
    bool identity_matches = false;
    int found_id = -1;
    if (ProMdlIdGet(found, &found_id) == PRO_TK_NO_ERROR)
        identity_matches = new_model_evidence.id_known && found_id == new_model_evidence.id;
    else
        safety_query_failed = true;
    bool never_saved = false;
    ProPath origin = {};
    ProError origin_code = ProMdlOriginGet(found, origin);
    if (origin_code == PRO_TK_NO_ERROR) {
        // A model created by ProMdlnameCopy inherits the template's origin
        // path. That is not a save of this model: only an origin whose file
        // stem is this model's own name counts as saved_since_creation.
        std::wstring origin_stem = std::filesystem::path(origin).stem().wstring();
        never_saved = origin[0] == 0 || _wcsicmp(origin_stem.c_str(), model_name.c_str()) != 0;
    } else if (origin_code != PRO_TK_E_NOT_FOUND)
        safety_query_failed = true;
    bool window_open = false;
    int window_id = -1;
    ProError window_code = ProMdlWindowGet(found, &window_id);
    if (window_code == PRO_TK_NO_ERROR)
        window_open = true;
    else if (window_code != PRO_TK_E_NOT_FOUND)
        safety_query_failed = true;
    bool user_modified = false;
    ProBoolean modified = PRO_B_FALSE;
    if (ProMdlModificationVerify(found, &modified) == PRO_TK_NO_ERROR) {
        // The job's own writes (creation copy, plan operations) are not user
        // edits. Without that attribution a flagged model is kept.
        if (modified == PRO_B_TRUE && !new_model_evidence.ops_mutated)
            user_modified =
                !(new_model_evidence.baseline_known && new_model_evidence.baseline_modified);
    } else
        safety_query_failed = true;
    bool refer_ok = true;
    bool referenced = referenced_by_other_model(model_name, mdltype, found, refer_ok);
    if (!refer_ok)
        safety_query_failed = true;
    if (!new_model_evidence.created)
        return cleanup_receipt(true, "skipped", "preexisting_same_name", nullptr, false);
    if (safety_query_failed)
        return cleanup_receipt(true, "skipped", "safety_query_failed", nullptr, false);
    if (!identity_matches)
        return cleanup_receipt(true, "skipped", "identity_changed", nullptr, false);
    if (!never_saved)
        return cleanup_receipt(true, "skipped", "saved_since_creation", nullptr, false);
    if (window_open)
        return cleanup_receipt(true, "skipped", "window_open", nullptr, false);
    if (user_modified)
        return cleanup_receipt(true, "skipped", "user_modified", nullptr, false);
    if (referenced)
        return cleanup_receipt(true, "skipped", "referenced_by_other", nullptr, false);
    ProError erase_code = ProMdlErase(found);
    if (erase_code != PRO_TK_NO_ERROR)
        return cleanup_receipt(true, "failed", "erase_failed", J(erase_code), false);
    // Identity matched the recorded creation handle: the erased object was
    // this run's own model; nothing later in the tail reads board.
    board = nullptr;
    bool query_ok = false;
    bool absent = confirm_name_absent(model_name, mdltype, query_ok);
    if (!query_ok || !absent)
        return cleanup_receipt(true, "unknown", "erase_unconfirmed", J(0), false);
    return cleanup_receipt(true, "erased", "cleaned", J(0), true);
}

static int components_total = 0;
static int components_missing = 0;
static ProError component_probe(ProFeature *feature, ProError status, ProAppData) {
    if (status)
        return status;
    ProFeattype type;
    if (ProFeatureTypeGet(feature, &type))
        return PRO_TK_NO_ERROR;
    if (type != PRO_FEAT_COMPONENT)
        return PRO_TK_NO_ERROR;
    components_total++;
    ProMdl component = nullptr;
    if (ProAsmcompMdlGet((ProAsmcomp *)feature, &component) != PRO_TK_NO_ERROR)
        components_missing++;
    return PRO_TK_NO_ERROR;
}

// Read-only retrieval and display of an existing on-disk native model. The file
// is never saved, erased, renamed or adopted; success creates no managed model.
static void open_file_native(const J &request, J &report) {
    const J &choice = request.at("open_file");
    std::wstring requested = wide(choice.at("requested_path").get<std::string>());
    std::wstring selected = wide(choice.at("selected_file").get<std::string>());
    bool assembly = choice.at("model_kind").get<std::string>() == "assembly";
    std::filesystem::path file_path(selected);
    std::wstring base = file_path.filename().wstring();
    if (size_t dot = base.rfind(L'.'); dot != std::wstring::npos) {
        std::wstring tail = base.substr(dot + 1);
        if (!tail.empty() && tail.find_first_not_of(L"0123456789") == std::wstring::npos)
            base = base.substr(0, dot);
        if (dot = base.rfind(L'.'); dot != std::wstring::npos) {
            std::wstring ext = base.substr(dot + 1);
            if (!_wcsicmp(ext.c_str(), L"prt") || !_wcsicmp(ext.c_str(), L"asm"))
                base = base.substr(0, dot);
        }
    }
    if (base.empty() || base.find_first_of(L".") != std::wstring::npos)
        throw std::runtime_error("Cannot derive a model name from the selected file path");
    J summary = {{"requested_path", utf8(requested)},
                 {"selected_file", utf8(selected)},
                 {"model_kind", assembly ? "assembly" : "part"},
                 {"model_name", utf8(base)}};
    report["open_file"] = summary;
    // Pre-checks and retrieval share one Toolkit channel: the session state the
    // checks observed is the state retrieval starts from.
    generic_stage("open_file_session_check");
    SessionInventory inventory;
    collect_session_models(inventory);
    if (!inventory.type_errors.empty() || inventory.truncated) {
        report["session_inventory"] = {{"type_errors", inventory.type_errors},
                                       {"truncated", inventory.truncated}};
        throw std::runtime_error(
            "SESSION_ENUMERATION_INCOMPLETE: the session inventory could not be "
            "completed, so open-file preconditions cannot be proven; no file was "
            "retrieved");
    }
    for (const auto &item : inventory.models) {
        if (item["name"].is_null())
            continue;
        bool same_name = !_wcsicmp(wide(item["name"].get<std::string>()).c_str(), base.c_str());
        std::string kind = item["model_type"];
        bool same_family = assembly ? kind == "assembly" : (kind == "part" || kind == "sheetmetal");
        if (same_name && same_family) {
            report["open_file"]["conflicting_session_model"] = item;
            throw std::runtime_error(
                "SESSION_NAME_CONFLICT: a " + kind +
                " model with this name is already in the Creo session; the file was "
                "not retrieved. Close or erase it in Creo first, or switch to it "
                "directly. A previously retrieved assembly may have loaded this "
                "name as a dependency (check creo_list_session_models; assembly "
                "components stay in the session even after their window closes)");
        }
    }
    if (assembly) {
        for (const auto &item : inventory.models) {
            std::string kind = item["model_type"];
            if (kind == "part" || kind == "sheetmetal" || kind == "assembly")
                throw std::runtime_error(
                    "ASSEMBLY_REQUIRES_EMPTY_SESSION: the session already holds a "
                    "part or assembly; assembly retrieval needs a session without "
                    "parts/assemblies so partial loading stays observable. No file "
                    "was retrieved");
        }
    }
    generic_stage("open_file_retrieve");
    ProMdl opened = nullptr;
    ProPath file;
    path(file, selected);
    ProError load_code = ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &opened);
    if (load_code != PRO_TK_NO_ERROR) {
        // Retrieval of an incomplete assembly can leave components in the session.
        // Report them explicitly; the missing-component list is unknown to Toolkit.
        SessionInventory after;
        collect_session_models(after);
        J remaining = J::array();
        for (const auto &item : after.models) {
            std::string kind = item["model_type"];
            if (kind == "part" || kind == "sheetmetal" || kind == "assembly")
                remaining.push_back(item);
        }
        report["loaded"] = false;
        report["open_file"]["loaded"] = false;
        report["open_file"]["missing_components"] = "unknown";
        report["open_file"]["remaining_session_models"] = remaining;
        report["open_file"]["remaining_models_note"] =
            "retrieval failed; listed part/assembly objects may be partial residues of "
            "this attempt and are not erased automatically";
        throw std::runtime_error(
            "RETRIEVE_FAILED: ProMdlFiletypeLoad returned " + std::to_string(load_code) +
            " for the selected file; assemblies failing here usually miss components "
            "(list unavailable, marked unknown). Inspect remaining_session_models; "
            "nothing was saved or erased");
    }
    report["loaded"] = true;
    report["open_file"]["loaded"] = true;
    ProMdlType kind = PRO_MDL_PART;
    check(ProMdlTypeGet(opened, &kind), "ProMdlTypeGet");
    if (kind != (assembly ? PRO_MDL_ASSEMBLY : PRO_MDL_PART)) {
        report["open_file"]["actual_model_type_code"] = kind;
        throw std::runtime_error(
            "MODEL_TYPE_MISMATCH: the retrieved file is not the requested model kind; "
            "the loaded object stays in the session, nothing was saved or erased");
    }
    if (assembly) {
        // Toolkit retrieves an incomplete assembly without error; the component
        // features exist but their models stay unresolved. Refuse to report a
        // complete open in that case and leave the residues observable.
        generic_stage("open_file_component_check");
        components_total = 0;
        components_missing = 0;
        check(ProSolidFeatVisit((ProSolid)opened, component_probe, nullptr, nullptr),
              "ProSolidFeatVisit");
        report["open_file"]["component_count"] = components_total;
        if (components_missing > 0) {
            SessionInventory after;
            collect_session_models(after);
            J remaining = J::array();
            for (const auto &item : after.models) {
                std::string item_kind = item["model_type"];
                if (item_kind == "part" || item_kind == "sheetmetal" || item_kind == "assembly")
                    remaining.push_back(item);
            }
            report["open_file"].update(
                {{"displayed", false},
                 {"missing_component_count", components_missing},
                 {"missing_components",
                  {{"count", components_missing},
                   {"total", components_total},
                   {"names", "unknown"}}},
                 {"remaining_session_models", remaining},
                 {"remaining_models_note",
                  "retrieval incomplete; the assembly object stays in the session "
                  "(not displayed, not erased); listed part/assembly objects may be "
                  "partial residues"}});
            throw std::runtime_error(
                "RETRIEVE_INCOMPLETE: the assembly was retrieved but " +
                std::to_string(components_missing) + " of " + std::to_string(components_total) +
                " components did not resolve (names unavailable, marked unknown). The "
                "assembly is not displayed; inspect remaining_session_models; nothing "
                "was saved or erased");
        }
    }
    std::string model_type = assembly ? "assembly" : "part";
    if (kind == PRO_MDL_PART) {
        ProMdlsubtype subtype;
        ProError sc = ProMdlSubtypeGet(opened, &subtype);
        if (!sc && subtype == PROMDLSTYPE_PART_SHEETMETAL)
            model_type = "sheetmetal";
    }
    ProPath origin = {};
    check(ProMdlOriginGet(opened, origin), "ProMdlOriginGet");
    ProMdlName display = {};
    ProError name_code = ProMdlMdlnameGet(opened, display);
    report["open_file"].update(
        {{"model_type", model_type},
         {"origin", utf8(origin)},
         {"origin_matches_selected_file", !_wcsicmp(origin, selected.c_str())},
         {"display_name", name_code ? J(nullptr) : J(utf8(display))}});
    generic_stage("open_file_display");
    bool displayed = false;
    std::string display_message;
    try {
        CK(ProMdlDisplay(opened));
        int window = -1;
        CK(ProMdlWindowGet(opened, &window));
        CK(ProWindowCurrentSet(window));
        CK(ProWindowRefit(window));
        CK(ProWindowRepaint(window));
        CK(ProWindowActivate(window));
        displayed = true;
    } catch (ProError error) {
        display_message = "Toolkit call " + last_toolkit_error + " failed with code " +
                          std::to_string(error) + " during open_file_display";
    } catch (const std::exception &error) {
        display_message = error.what();
    }
    report["open_file"]["displayed"] = displayed;
    if (!displayed) {
        report["open_file"]["display_message"] = display_message;
        report["message"] =
            "Loaded the model into the session but could not display it: " + display_message +
            "; the object remains in the session (query creo_list_session_models); "
            "nothing was saved or erased";
        return;
    }
    // Single-handle observation of the just-opened model: the same fields as a
    // session-inventory entry, read directly from the opened handle without a
    // fresh full enumeration. The Python closeout stamps observed_at.
    ProMdl window_model = nullptr;
    int window_code = ProMdlCurrentGet(&window_model);
    report["open_file"]["opened_session_model"] =
        observe_session_model(opened, model_type.c_str(), window_model, window_code);
    // Bounded post-open session summary (FEAT-044): one full enumeration
    // distinguishes session model objects from the component instances an
    // assembly retrieval brings in. The bounded page is a summary; the
    // complete, refreshable inventory is creo_list_session_models.
    {
        SessionInventory after;
        collect_session_models(after);
        J page = J::array();
        constexpr size_t page_limit = 20;
        for (const auto &item : after.models) {
            if (page.size() >= page_limit)
                break;
            page.push_back(item);
        }
        report["open_file"]["loaded_session_models"] = {
            {"session_model_count", after.models.size()},
            {"component_instance_count", assembly ? J(components_total) : J(nullptr)},
            {"component_instance_scope",
             assembly ? "component features of the assembly opened by this job"
                      : "not an assembly open"},
            {"models", page},
            {"page_limit", page_limit},
            {"complete", after.models.size() <= page_limit},
            {"has_more", after.models.size() > page_limit},
            {"detail", "creo_list_session_models without cursor re-collects the live "
                       "inventory; its cursor pages read a frozen snapshot"}};
    }
    report["success"] = true;
}

// Raw ProFeatureStatusGet codes are the queryable truth; the label is only a
// readability hint and stays "unknown_status_code" outside the SDK enum.
static const char *feat_status_name(int status) {
    switch (status) {
    case PRO_FEAT_INVALID:
        return "invalid";
    case PRO_FEAT_ACTIVE:
        return "active";
    case PRO_FEAT_INACTIVE:
        return "inactive";
    case PRO_FEAT_FAMTAB_SUPPRESSED:
        return "famtab_suppressed";
    case PRO_FEAT_SIMP_REP_SUPPRESSED:
        return "simplified_rep_suppressed";
    case PRO_FEAT_PROG_SUPPRESSED:
        return "program_suppressed";
    case PRO_FEAT_SUPPRESSED:
        return "suppressed";
    case PRO_FEAT_UNREGENERATED:
        return "unregenerated";
    default:
        return "unknown_status_code";
    }
}

// Bounded per-feature diagnosis for the unhealthy_features refusal (FEAT-006):
// every failed, suppressed or incomplete feature keeps its id, name, type and
// raw status code, but only the first item_limit entries travel in control
// metadata; unhealthy_total and truncated keep the omitted remainder countable.
// The health admission rule itself does not change.
static J health_details(const J &features) {
    constexpr size_t item_limit = 20;
    J items = J::array();
    size_t total = 0;
    for (const auto &f : features) {
        bool incomplete = f.value("incomplete", false);
        int status = f.value("status", PRO_FEAT_ACTIVE);
        if (!incomplete && status == PRO_FEAT_ACTIVE)
            continue;
        total++;
        if (items.size() >= item_limit)
            continue;
        items.push_back({{"id", f.value("id", 0)},
                         {"name", f.value("name", "")},
                         {"type_name", f.value("type_name", "")},
                         {"status_code", status},
                         {"status", feat_status_name(status)},
                         {"incomplete", incomplete}});
    }
    return {{"unhealthy_total", total},
            {"returned", items.size()},
            {"item_limit", item_limit},
            {"truncated", total > items.size()},
            {"items", items}};
}

// FEAT-048: this selector never depends on the current window. Resident origin
// plus modification state proves session provenance, not a historical byte
// comparison with disk. That distinction is explicit in source_state.
static J path_source_state(ProMdl source, const J &choice, const std::string &provenance) {
    ProPath origin = {};
    CK(ProMdlOriginGet(source, origin));
    std::wstring selected = wide(choice.at("origin").get<std::string>());
    if (_wcsicmp(origin, selected.c_str()))
        throw std::runtime_error(
            "source_origin_mismatch: resident origin is not the selected file");
    ProBoolean modified = PRO_B_TRUE;
    CK(ProMdlModificationVerify(source, &modified));
    if (modified != PRO_B_FALSE)
        throw std::runtime_error("modified_source: source has unsaved session changes");
    const std::string sha = mechdog_callback::sha256(selected);
    if (sha.empty() || sha != choice.at("origin_sha256").get<std::string>())
        throw std::runtime_error("source_changed: selected file bytes changed");
    int id = -1;
    CK(ProMdlIdGet(source, &id));
    ProWVerstamp stamp = nullptr;
    CK(ProMdlVerstampGet(source, &stamp));
    char *text = nullptr;
    ProError code = ProVerstampStringGet(stamp, &text);
    std::string version = !code && text ? text : "";
    if (text)
        ProVerstampStringFree(&text);
    ProVerstampFree(&stamp);
    check(code, "ProVerstampStringGet");
    if (version.empty())
        throw std::runtime_error("source_identity_unknown: source version stamp is empty");
    return {{"origin", choice.at("origin")},
            {"sha256", sha},
            {"modified", false},
            {"session_model_id", id},
            {"version_stamp", version},
            {"provenance", provenance},
            {"disk_resident_content_equality",
             provenance == "fresh_retrieval" ? "retrieved_from_selected_file" : "unknown"}};
}

static ProMdl select_adoption_path(const J &choice, J &report) {
    report["path_source_checked"] = true;
    report["path_copy_started"] = false;
    report["resident_set_changed"] = false;
    std::filesystem::path file(wide(choice.at("origin").get<std::string>()));
    std::wstring base = file.filename().wstring();
    size_t dot = base.rfind(L'.');
    if (dot != std::wstring::npos) {
        std::wstring tail = base.substr(dot + 1);
        if (!tail.empty() && tail.find_first_not_of(L"0123456789") == std::wstring::npos)
            base = base.substr(0, dot);
    }
    dot = base.rfind(L'.');
    if (dot == std::wstring::npos || _wcsicmp(base.substr(dot + 1).c_str(), L"prt"))
        throw std::runtime_error("unsupported_model_type: path adoption requires a native part");
    base = base.substr(0, dot);
    if (base.empty() || base.size() >= PRO_NAME_SIZE || base.find(L'.') != std::wstring::npos)
        throw std::runtime_error("invalid_source_name: cannot identify selected native part");
    ProName name = {};
    wcscpy_s(name, base.c_str());
    ProMdl source = nullptr;
    ProError found = ProMdlInit(name, PRO_MDL_PART, &source);
    std::string provenance = "existing_resident";
    if (found == PRO_TK_E_NOT_FOUND) {
        if (choice.contains("source_state"))
            throw std::runtime_error("source_changed: inspected resident is no longer present");
        // Check the exact selected bytes before retrieval as well as afterwards.
        if (mechdog_callback::sha256(file.wstring()) !=
            choice.at("origin_sha256").get<std::string>())
            throw std::runtime_error("source_changed: selected file changed before retrieval");
        ProPath selected = {};
        path(selected, file.wstring());
        // Even a failed retrieval may add residents; report this conservatively.
        report["resident_set_changed"] = "possible";
        CK(ProMdlFiletypeLoad(selected, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &source));
        report["resident_set_changed"] = true;
        provenance = "fresh_retrieval";
    } else
        check(found, "ProMdlInit(path source)");
    ProMdlType type = PRO_MDL_UNUSED;
    CK(ProMdlTypeGet(source, &type));
    if (type != PRO_MDL_PART)
        throw std::runtime_error("unsupported_model_type: selected source is not a part");
    J state = path_source_state(source, choice, provenance);
    if (choice.contains("source_state")) {
        mechdog_adoption::require_source_state(state, choice.at("source_state"));
        // A later call sees a resident; preserve original inspect provenance.
        state["inspection_provenance"] = choice["source_state"].at("provenance");
    }
    report["path_source_state"] = state;
    return source;
}

static int adoption_window() {
    int window = -1;
    CK(ProWindowCurrentGet(&window));
    return window;
}

static void verify_path_source(ProMdl source, const J &choice, J &report, int window) {
    J current = path_source_state(source, choice, "existing_resident");
    mechdog_adoption::require_source_state(current, report.at("path_source_state"));
    if (recovery_session_fingerprint() != report.at("live").at("session_fingerprint"))
        throw std::runtime_error("source_changed: Creo session changed before copying");
    if (adoption_window() != window)
        throw std::runtime_error("window_changed: active window changed during path adoption");
    report["source_unchanged"] = true;
    report["window_unchanged"] = true;
}

static void adopt_native(const J &request, J &report) {
    const J &choice = request.at("adoption");
    const std::string action = choice.at("action");
    if (action == "confirm_snapshot") {
        confirm_adoption_snapshot(choice, report);
        return;
    }
    bool preparing = action == "prepare";
    const bool from_path = choice.value("path_source", false);
    if (from_path) {
        report["path_source_checked"] = true;
        report["path_copy_started"] = false;
    }
    const int path_window = from_path ? adoption_window() : -1;
    const std::string session = recovery_session_fingerprint();
    if (choice.contains("session_fingerprint") && choice["session_fingerprint"] != session)
        throw std::runtime_error("Adoption refused: Creo session changed since recorded evidence");
    ProMdl current = nullptr;
    ProError current_code = PRO_TK_NO_ERROR;
    if (from_path)
        current = select_adoption_path(choice, report);
    else
        current_code = ProMdlCurrentGet(&current);
    if (current_code == PRO_TK_BAD_CONTEXT)
        // -8 is "no current model", not a connection failure; keep the call name
        // and raw code so the original evidence stays machine-checkable.
        throw std::runtime_error(
            "NO_CURRENT_MODEL: the Creo window has no current model "
            "(ProMdlCurrentGet(&current) returned -8 PRO_TK_BAD_CONTEXT during " +
            generic_phase +
            "); switch to a model in Creo first; creo_list_session_models shows the "
            "session inventory");
    check(current_code, "ProMdlCurrentGet(&current)");
    ProMdlType kind = PRO_MDL_PART;
    CK(ProMdlTypeGet(current, &kind));
    if (kind != PRO_MDL_PART)
        throw std::runtime_error(
            "unsupported_model_type: only part or sheetmetal models can be adopted; "
            "assemblies and drawings keep their own ownership (adoption refused)");
    ProPath origin = {};
    CK(ProMdlOriginGet(current, origin));
    std::wstring origin_text = origin;
    if (choice.contains("origin") &&
        _wcsicmp(wide(choice.at("origin").get<std::string>()).c_str(), origin_text.c_str()))
        throw std::runtime_error(
            "Adoption refused: the current model is not the inspected model; inspect again");
    board = current; // Borrow the handle read-only, exactly like reconciliation inspect.
    J live = inspection(false);
    bool millimeters = live["units"] == "mm";
    bool dependency_clean = dependency_free(board);
    std::string model_type = live.value("model_type", "part");
    bool supported = model_type == "part" || model_type == "sheetmetal";
    ProMdlName display = {};
    ProError name_code = ProMdlMdlnameGet(current, display);
    J diagnosis = health_details(live["features"]);
    report["live"] = {{"origin", utf8(origin_text)},
                      {"model_type", model_type},
                      {"healthy", live.at("healthy")},
                      {"feature_count", live.at("features").size()},
                      {"volume_mm3", live.contains("volume_mm3") ? live["volume_mm3"] : J(nullptr)},
                      {"millimeter_units", millimeters},
                      {"dependency_free", dependency_clean},
                      {"session_fingerprint", session},
                      {"health_details", diagnosis},
                      {"inspection", live}};
    if (name_code == PRO_TK_NO_ERROR)
        report["live"]["display_name"] = utf8(display);
    if (from_path) {
        report["live"]["source_state"] = report.at("path_source_state");
        report["live"]["resident_set_changed"] = report.at("resident_set_changed");
        verify_path_source(current, choice, report, path_window);
    }
    if (action == "inspect") {
        board = nullptr;
        report["success"] = true;
        return;
    }
    if (action != "apply" && !preparing)
        throw std::runtime_error("Unknown adoption action");
    if (choice.contains("live_inspection") || choice.contains("live_inspection_ref"))
        verify_recovery(choice_inspection(choice, "live_inspection"), live);
    board = nullptr; // The user's model is never the managed target again past this point.
    if (preparing && !origin_text.empty())
        throw std::runtime_error(
            "prepare requires a never-saved model; use inspect/apply for a file source");
    if (!preparing && origin_text.empty())
        throw std::runtime_error(
            "Never-saved model requires explicit prepare, then confirm its frozen snapshot");
    if (!live.value("healthy", false))
        throw std::runtime_error(
            "unhealthy_features: source has failed, suppressed or incomplete features (" +
            std::to_string(diagnosis["unhealthy_total"].get<size_t>()) + " unhealthy; first " +
            std::to_string(diagnosis["returned"].get<size_t>()) +
            " listed in live.health_details) (adoption refused)");
    if (!supported)
        throw std::runtime_error("unsupported_model_type: only independent part or sheetmetal "
                                 "models are supported (adoption refused)");
    if (!millimeters)
        throw std::runtime_error(
            "non_millimeter_units: millimeter model units are required (adoption refused)");
    if (!dependency_clean)
        throw std::runtime_error("external_dependencies: external dependencies require separate "
                                 "ownership verification (adoption refused)");
    struct WindowRestore {
        int window = -1;
        ~WindowRestore() {
            if (window >= 0) {
                ProError selected = ProWindowCurrentSet(window);
                ProError activated = ProWindowActivate(window);
                log("ADOPTION_WINDOW_RESTORE=%d,%d\n", selected, activated);
            }
        }
    } window_restore;
    int original_window = -1;
    if (preparing) {
        CK(ProWindowCurrentGet(&original_window));
        if (original_window < 0)
            throw std::runtime_error("Snapshot preparation requires a current model window");
        window_restore.window = original_window;
    }
    ProName adopted;
    wcscpy_s(adopted, model_name.c_str());
    ProMdl clash = nullptr;
    ProError found = ProMdlInit(adopted, PRO_MDL_PART, &clash);
    if (found == PRO_TK_NO_ERROR)
        throw std::runtime_error("session_name_conflict: the managed model name already exists in "
                                 "this Creo session (adoption refused)");
    if (found != PRO_TK_E_NOT_FOUND)
        check(found, "CheckAdoptedName");
    if (from_path) {
        verify_path_source(current, choice, report, path_window);
        report["path_copy_started"] = true;
    }
    CK(ProMdlnameCopy(current, adopted, &board));
    if (!millimeter_units(board))
        throw std::runtime_error(
            "non_millimeter_units: copied model units are not millimeter (adoption refused)");
    if (!dependency_free(board))
        throw std::runtime_error("external_dependencies: the copied model carries external "
                                 "dependencies (adoption refused)");
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    J before = inspection();
    verify_recovery(live, before); // Prove the copy includes the live source state.
    generic_stage("adoption_save_and_reload");
    ProPath destination;
    path(destination, folder);
    CK(ProMdlnameBackup(board, destination));
    std::wstring saved = latest_model_file(); // Only select the output of this adoption save.
    CK(ProMdlErase(board));
    board = nullptr;
    ProPath file;
    path(file, saved);
    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
    CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
    J after = inspection();
    verify_recovery(before, after);
    after["inspection_source"] = "adoption_verified";
    after["inspection_available"] = true;
    if (preparing) {
        CK(ProWindowCurrentSet(original_window));
        CK(ProWindowActivate(original_window));
        window_restore.window = -1;
    } else if (!from_path)
        display_adopted_model();
    if (from_path)
        verify_path_source(current, choice, report, path_window);
    report.update({{"success", true},
                   {"saved_file_reloaded_and_verified", true},
                   {"inspection", after},
                   {"aliases", J::object()},
                   {"part_file", utf8(saved)},
                   {"adopted", !preparing}});
}

// BUG-111: a transform failure used to arrive as a bare Toolkit code plus the
// phase name. Publish the operation's own shape instead: which backend ran, the
// rotation as requested and as normalized, how many references and whether the
// original geometry was kept. Bounded by construction (no per-face lists); the
// flex_move path also publishes what the copy actually selected (BUG-111 T2:
// requested body ids, selected surface count and the model counts at op start)
// because keep_original copies accumulate inside the single body.
static J transform_failure_report(const J &op) {
    J rotation = op.value("rotation", J::array({0.0, 0.0, 0.0}));
    J normalized = J::array();
    for (auto value : rotation)
        normalized.push_back(normalized_rotation_deg(value.get<double>()));
    J kinds = J::array();
    for (auto reference : op["references"]) {
        std::string kind = reference.value("kind", "");
        if (kind.empty() || std::find(kinds.begin(), kinds.end(), kind) != kinds.end())
            continue;
        if (kinds.size() < 6)
            kinds.push_back(kind);
    }
    const bool body = !op["references"].empty() && op["references"][0]["kind"] == "body";
    J report = {{"label", op.value("label", "")},
                {"backend", body ? "flex_move" : "geometry_move"},
                {"rotation_deg", rotation},
                {"rotation_normalized_deg", normalized},
                {"translation_mm", op.value("translation", J::array({0.0, 0.0, 0.0}))},
                {"keep_original", op.value("keep_original", false)},
                {"reference_count", (int)op["references"].size()},
                {"reference_kinds", kinds},
                {"note", "the kernel is usable inside -180..180 deg; equivalent angles map to the "
                         "same rotation, and a failed copy leaves the plan rolled back"}};
    if (transform_selection.is_object())
        report["selection"] = transform_selection;
    return report;
}

// FEAT-012/FEAT-008 (0.12.0 P-2/P-3, F04 P5): a failed job publishes one
// bounded failure context beside failed_operation_index. Only reported facts
// appear here: an unavailable field stays null instead of being guessed, the
// raw message is cut at a fixed bound, and a placement failure echoes the
// caller's own 4x4 row-vector matrix without orthonormalizing, normalizing or
// transposing it (the batch rollback stays atomic).
static const int FAILED_OPERATION_MESSAGE_LIMIT = 512;

static std::string bounded_failure_message(const std::string &text) {
    if ((int)text.size() <= FAILED_OPERATION_MESSAGE_LIMIT)
        return text;
    int cut = FAILED_OPERATION_MESSAGE_LIMIT;
    // Keep the cut on a UTF-8 code point boundary so the receipt stays valid text.
    while (cut > 0 && (static_cast<unsigned char>(text[cut]) & 0xC0) == 0x80)
        --cut;
    return text.substr(0, cut);
}

// BUG-113: a failed save and a failed rollback verification are separate facts
// and must be readable from the receipt alone. Both blocks below only report
// what this process observed, stay bounded (20 entries plus total/truncated)
// and never publish absolute paths or license data.
static const int RECOVERY_SAMPLE_LIMIT = 20;

static J bounded_directory_names(const std::wstring &directory) {
    J sample = J::array();
    int total = 0;
    bool truncated = false;
    std::error_code error;
    std::filesystem::directory_iterator entry(std::filesystem::path(directory), error);
    const std::filesystem::directory_iterator end;
    while (!error && entry != end) {
        std::error_code type_error;
        if (std::filesystem::is_regular_file(entry->path(), type_error) && !type_error) {
            ++total;
            if ((int)sample.size() < RECOVERY_SAMPLE_LIMIT)
                sample.push_back(utf8(entry->path().filename()));
            else
                truncated = true;
        }
        entry.increment(error);
    }
    if (error)
        return {{"available", false},
                {"total", nullptr},
                {"truncated", nullptr},
                {"sample", J::array()},
                {"reason", "the destination directory could not be listed"}};
    return {{"available", true},
            {"total", total},
            {"truncated", truncated},
            {"sample", sample},
            {"reason", nullptr}};
}

// BUG-113: a Backup failure leaves the managed files behind unchecked. Probe
// readability at the failure instant (bounded to the published sample) so a
// transient exclusive handle is distinguishable from a pure Toolkit error.
static bool readable_file(const std::wstring &path) {
    if (path.empty())
        return false;
    std::ifstream stream(std::filesystem::path(path), std::ios::binary);
    return stream.good();
}

static J candidate_readability(const std::wstring &directory, const J &sample) {
    J items = J::array();
    for (auto &name : sample) {
        std::filesystem::path path =
            std::filesystem::path(directory) / std::filesystem::path(wide(name.get<std::string>()));
        items.push_back({{"name", name}, {"readable", readable_file(path.wstring())}});
    }
    return items;
}

// Only a name inside the managed output directory may be published; anything
// outside it (or any absolute path) stays null instead of leaking a host path.
static J managed_relative_name(const std::wstring &value, const std::wstring &directory) {
    if (value.empty())
        return nullptr;
    std::error_code error;
    const std::filesystem::path relative = std::filesystem::relative(
        std::filesystem::path(value), std::filesystem::path(directory), error);
    if (error || relative.empty() || relative.is_absolute())
        return nullptr;
    if (*relative.begin() == std::filesystem::path(L".."))
        return nullptr;
    return J(utf8(relative.generic_wstring()));
}

static J save_failure_report(ProError code, const char *stage, const std::wstring &checkpoint,
                             const std::wstring &directory, const std::wstring &model_name,
                             bool assembly, const char *call) {
    const std::wstring extension = assembly ? L".asm" : L".prt";
    J candidates = bounded_directory_names(directory);
    J readability = J::array();
    if (candidates.value("available", false) && candidates.contains("sample") &&
        candidates["sample"].is_array())
        readability = candidate_readability(directory, candidates["sample"]);
    return {{"call", call},
            {"code", code},
            {"stage", stage},
            {"destination", utf8(model_name + extension)},
            {"source_checkpoint", managed_relative_name(checkpoint, directory)},
            {"source_checkpoint_readable",
             checkpoint.empty() ? J(nullptr) : J(readable_file(checkpoint))},
            {"candidate_files", candidates},
            {"candidate_readability", readability}};
}

static bool collect_ids(const J &state, const char *key, std::set<int> &ids) {
    if (!state.is_object() || !state.contains(key) || !state[key].is_array())
        return false;
    for (const auto &item : state[key]) {
        if (!item.is_object() || !item.contains("id") || !item["id"].is_number_integer())
            return false;
        ids.insert(item["id"].get<int>());
    }
    return true;
}

static J bounded_ids(const std::set<int> &ids) {
    J sample = J::array();
    for (auto it = ids.begin(); it != ids.end() && (int)sample.size() < RECOVERY_SAMPLE_LIMIT; ++it)
        sample.push_back(*it);
    return {{"total", (int)ids.size()},
            {"truncated", (int)ids.size() > RECOVERY_SAMPLE_LIMIT},
            {"sample", sample}};
}

static J rollback_collection_difference(const J &before, const J &after, const char *key) {
    std::set<int> before_ids, after_ids;
    const bool before_ids_ok = collect_ids(before, key, before_ids);
    const bool after_ids_ok = collect_ids(after, key, after_ids);
    const bool before_listed = before.is_object() && before.contains(key) && before[key].is_array();
    const bool after_listed = after.is_object() && after.contains(key) && after[key].is_array();
    J block = {{"available", false},
               {"before", before_listed ? J((int)before[key].size()) : J(nullptr)},
               {"after", after_listed ? J((int)after[key].size()) : J(nullptr)},
               {"missing_ids", nullptr},
               {"added_ids", nullptr},
               {"reason", nullptr}};
    if (!before_listed || !after_listed) {
        block["reason"] =
            std::string(!before_listed ? "baseline" : "restored") + " inspection carries no " + key;
        return block;
    }
    if (!before_ids_ok || !after_ids_ok) {
        block["reason"] = std::string("one or more ") + key + " records carry no integer id";
        return block;
    }
    std::set<int> missing, added;
    for (int id : before_ids)
        if (!after_ids.count(id))
            missing.insert(id);
    for (int id : after_ids)
        if (!before_ids.count(id))
            added.insert(id);
    block["available"] = true;
    block["missing_ids"] = bounded_ids(missing);
    block["added_ids"] = bounded_ids(added);
    return block;
}

static J rollback_volume_difference(const J &before, const J &after) {
    auto read = [](const J &state) {
        if (!state.is_object() || !state.contains("volume_mm3") || !state["volume_mm3"].is_number())
            return J(nullptr);
        const double value = state["volume_mm3"].get<double>();
        return std::isfinite(value) ? J(value) : J(nullptr);
    };
    const J before_value = read(before), after_value = read(after);
    J block = {{"available", !before_value.is_null() && !after_value.is_null()},
               {"before", before_value},
               {"after", after_value},
               {"reason", nullptr}};
    if (!block["available"].get<bool>())
        block["reason"] = "volume was not measured on both sides, so geometry cannot be compared";
    return block;
}

// The difference is diagnostic only: it never changes rollback_succeeded, the
// operation effect status or the model status. A matched block simply means the
// bounded evidence found no feature/body/volume difference; the comparison that
// rejected the rollback stays the authority and its message stays in reason.
static J rollback_difference_report(const J &baseline, const J &restored,
                                    const std::string &reason) {
    J features = rollback_collection_difference(baseline, restored, "features");
    J bodies = rollback_collection_difference(baseline, restored, "bodies");
    J volume = rollback_volume_difference(baseline, restored);
    const bool available = features["available"].get<bool>() && bodies["available"].get<bool>();
    bool counts_match = true;
    for (const J *block : {&features, &bodies})
        if (!((*block)["before"].is_number_integer() && (*block)["after"].is_number_integer() &&
              (*block)["before"].get<int>() == (*block)["after"].get<int>()))
            counts_match = false;
    auto lists_ids = [](const J &block) {
        return (!block["missing_ids"].is_null() && block["missing_ids"]["total"].get<int>() > 0) ||
               (!block["added_ids"].is_null() && block["added_ids"]["total"].get<int>() > 0);
    };
    const bool volume_changed =
        volume["available"].get<bool>() &&
        fabs(volume["before"].get<double>() - volume["after"].get<double>()) > 0.01;
    const bool mismatch =
        !counts_match || lists_ids(features) || lists_ids(bodies) || volume_changed;
    return {{"available", available},
            {"status", !available ? "unavailable" : (mismatch ? "mismatch" : "matched")},
            {"reason", reason.empty() ? J(nullptr) : J(bounded_failure_message(reason))},
            {"features", features},
            {"bodies", bodies},
            {"volume_mm3", volume}};
}

static void failed_placement_matrix(const J &operation, J &block) {
    // BUG-133/FEAT-012: the admission gate may have rejected this pose before
    // the kernel saw it. Echo the caller's own rotation_matrix (never repaired)
    // and measure it with the same effective tolerance and the same canonical
    // row form the entry would have used, so the reported numbers explain the
    // refusal instead of contradicting it.
    if (!operation.contains("rotation_matrix") || operation.at("rotation_matrix").is_null())
        return; // Euler input only ever reaches the kernel, so no matrix echo exists
    const J &input = operation.at("rotation_matrix");
    if (!input.is_array() || input.size() != 3)
        return;
    double rotation[3][3];
    for (int i = 0; i < 3; ++i) {
        if (!input[i].is_array() || input[i].size() != 3)
            return;
        for (int j = 0; j < 3; ++j) {
            if (!input[i][j].is_number() || !std::isfinite(input[i][j].get<double>()))
                return;
            rotation[i][j] = input[i][j].get<double>();
        }
    }
    const J zero = J::array({0, 0, 0});
    const J &translation = operation.contains("translation") ? operation.at("translation") : zero;
    if (!translation.is_array() || translation.size() != 3)
        return;
    for (int j = 0; j < 3; ++j)
        if (!translation[j].is_number() || !std::isfinite(translation[j].get<double>()))
            return;
    J echo = J::array();
    for (int i = 0; i < 4; ++i) {
        J row = J::array();
        for (int j = 0; j < 4; ++j) {
            const double number = i < 3 ? (j < 3 ? rotation[i][j] : 0.0)
                                        : (j < 3 ? translation[j].get<double>() : 1.0);
            row.push_back(number);
        }
        echo.push_back(std::move(row));
    }
    std::string convention = "row";
    J tolerance = J(nullptr);
    try {
        convention = assembly_input_convention(operation);
        tolerance = J(assembly_effective_tolerance(operation));
    } catch (const std::exception &) {
        // An invalid convention or tolerance is itself the failure; the numbers
        // stay reported without inventing which gate applied.
    }
    if (convention == "column")
        for (int i = 0; i < 3; ++i)
            for (int j = i + 1; j < 3; ++j) {
                const double swap = rotation[i][j];
                rotation[i][j] = rotation[j][i];
                rotation[j][i] = swap;
            }
    const double det =
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1]) -
        rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0]) +
        rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0]);
    double residual = 0;
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j) {
            double dot = 0;
            for (int k = 0; k < 3; ++k)
                dot += rotation[i][k] * rotation[j][k];
            residual = std::max(residual, std::abs(dot - (i == j ? 1.0 : 0.0)));
        }
    if (!std::isfinite(det) || !std::isfinite(residual))
        return;
    block["input_matrix"] = echo;
    block["matrix_source"] = J("rotation_matrix");
    block["matrix_convention"] = convention;
    block["admission_tolerance"] = tolerance;
    block["determinant"] = det;
    block["orthogonality_residual"] = residual;
}

static J failed_operation_context(const J &operation, int index, bool executing,
                                  const std::string &stage, const J &pro_error,
                                  const std::string &pro_error_source,
                                  const std::string &toolkit_call, const std::string &message) {
    const bool in_flight = executing && operation.is_object();
    const std::string kind = in_flight ? operation.value("op", "") : "";
    J block = {{"index", in_flight ? J(index) : J(nullptr)},
               {"operation", kind.empty() ? J(nullptr) : J(kind)},
               {"stage", stage.empty() ? J(nullptr) : J(stage)},
               {"feature_label", nullptr},
               {"sketch_name", nullptr},
               {"toolkit_call", toolkit_call.empty() ? J(nullptr) : J(toolkit_call)},
               {"pro_error", pro_error},
               {"pro_error_source", pro_error_source},
               {"message", nullptr},
               {"message_truncated", false},
               {"input_matrix", nullptr},
               {"matrix_source", nullptr},
               {"matrix_convention", nullptr},
               {"admission_tolerance", nullptr},
               {"determinant", nullptr},
               {"orthogonality_residual", nullptr},
               {"failed_constraint_index", nullptr},
               {"failed_constraint_type", nullptr},
               {"constraint_stage", nullptr},
               {"constraint_reason", nullptr}};
    if (in_flight) {
        if (!last_sketch_solver_info.is_null() &&
            (kind == "sketch" || kind == "update_sketch_geometry" || kind == "update_airfoil"))
            block["solver"] = sketch_solver_receipt(last_sketch_solver_info);
        // Only a string label/reference is a name; an integer sketch id stays
        // unnamed rather than being turned into a label.
        if (operation.contains("label") && operation.at("label").is_string()) {
            std::string label = operation.at("label").get<std::string>();
            if (!label.empty())
                block["feature_label"] = label;
        }
        if (operation.contains("sketch") && operation.at("sketch").is_string()) {
            std::string sketch_name = operation.at("sketch").get<std::string>();
            if (!sketch_name.empty())
                block["sketch_name"] = sketch_name;
        }
        if (kind == "assemble_component" || kind == "component_placement")
            failed_placement_matrix(operation, block);
        // DEV-092/T4: the constraint slot that failed. A pre-parse error names
        // its index/type/stage; a whole-group solve failure reports no index and
        // reason "solver_failed" with the raw Toolkit code kept elsewhere.
        if (last_constraint_failure.active &&
            (kind == "assemble_component" || kind == "component_constraints")) {
            block["failed_constraint_index"] =
                last_constraint_failure.index >= 0 ? J(last_constraint_failure.index) : J(nullptr);
            block["failed_constraint_type"] =
                last_constraint_failure.type.empty() ? J(nullptr) : J(last_constraint_failure.type);
            block["constraint_stage"] = J(last_constraint_failure.stage);
            block["constraint_reason"] = J(last_constraint_failure.reason);
            if (constraint_placement_failure.is_object()) {
                for (const char *field :
                     {"placement_matches_constraints", "max_distance_error_mm",
                      "max_angle_error_deg", "distance_tolerance_mm", "angle_tolerance_deg"})
                    block[field] = constraint_placement_failure.value(field, J(nullptr));
            }
        }
    }
    if (!message.empty()) {
        const std::string bounded = bounded_failure_message(message);
        block["message"] = bounded;
        block["message_truncated"] = bounded.size() < message.size();
    }
    return block;
}

static int run_generic(const std::wstring &job) {
    generic_job = job;
    generic_phase = "loading_request";
    last_toolkit_error.clear();
    last_feature_error_report = nullptr;
    last_constraint_failure = AssemblyConstraintFailure();
    pending_constraint_placements.clear();
    constraint_placement_failure = nullptr;
    J report = {{"success", false},
                {"saved_file_reloaded_and_verified", false},
                {"rollback_succeeded", false}};
    J request;
    ProProcessHandle process = {};
    bool connected = false, mutated = false;
    std::unique_ptr<RecoveryDeadline> recovery_deadline;
    int operation_index = -1;
    J operation_in_flight;
    bool executing_operation = false;
    // FEAT-012/FEAT-008: the raw Toolkit code of the caught failure, with its
    // provenance. A non-Toolkit failure keeps null/"unsupported" instead of the
    // general error code assigned to toolkit_code.
    J failure_pro_error = nullptr;
    std::string failure_pro_error_source = "unsupported";
    std::wstring checkpoint;
    new_model_evidence = NewModelEvidence();
    board_log = _wfsopen((job + L"\\native.log").c_str(), L"w", _SH_DENYNO);
    if (!board_log)
        return 3;
    try {
        std::ifstream input(job + L"\\request.json");
        input >> request;
        FILETIME created, exited, kernel, user;
        if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user) ||
            !publish_native_json(
                job + L"\\native_owner.json",
                {{"pid", GetCurrentProcessId()},
                 {"created", (static_cast<unsigned long long>(created.dwHighDateTime) << 32) |
                                 created.dwLowDateTime}}))
            throw std::runtime_error("Cannot persist native process identity");
        if (request.contains("reconciliation")) {
            // BUG-157/BUG-171: recovery gets its own phase budget (default 300 s,
            // clamped to 30-1800) and never outlives the job's total budget.
            double phase = request.value("recovery_phase_seconds", 300.0);
            if (!std::isfinite(phase))
                phase = 300.0;
            phase = std::min(1800.0, std::max(30.0, phase));
            const double total = request.value("timeout_seconds", phase);
            if (std::isfinite(total) && total > 0)
                phase = std::min(phase, total);
            recovery_deadline = std::make_unique<RecoveryDeadline>(job, (DWORD)(phase * 1000.0));
        }
        auto model = request.at("model");
        model_name = wide(model.at("model_name"));
        folder = wide(model.at("output_directory"));
        // Split registry records pass a controlled reference instead of an
        // inline aliases payload; legacy requests keep the inline dict (BUG-077).
        aliases = model.contains("aliases_ref") ? read_inspection_ref(model.at("aliases_ref"))
                                                : model.at("aliases");
        feature_tombstones =
            model.contains("feature_tombstones") && model["feature_tombstones"].is_object()
                ? model["feature_tombstones"]
                : J::object();
        suppressed_features =
            model.contains("suppressed_features") && model["suppressed_features"].is_object()
                ? model["suppressed_features"]
                : J::object();
        refresh_recorded_suppressed();
        component_sources = request.value("components", J::object());
        for (auto item = component_sources.begin(); item != component_sources.end(); ++item) {
            if (item.value().contains("aliases_ref"))
                item.value()["aliases"] = read_inspection_ref(item.value().at("aliases_ref"));
            if (item.value().contains("inspection_ref"))
                item.value()["inspection"] = read_inspection_ref(item.value().at("inspection_ref"));
        }
        // FEAT-052: recolor evidence is job-scoped; reset before any op can run.
        recolor_reset();
        // BUG-124: the import receipt comes from the model-setup step of this job.
        import_geometry_reset();
        g_recolor_readonly = request.value("readonly", false);
        template_file = wide(request.at("template_file"));
        if (!model["part_file"].is_null())
            checkpoint = wide(model["part_file"]);
        char empty[] = "";
        ProBoolean random = PRO_B_FALSE;
        generic_stage("connect");
        // BUG-109/R12: a stage on each side of the Toolkit connect lets the
        // bounded stall report attribute a slow session attach instead of folding
        // it into the first operation stage. "connected" carries the elapsed
        // milliseconds the attach itself took.
        generic_substage("connect");
        CK(connect_creo(&process));
        generic_substage("connected");
        connected = true;
        report["connected"] = true;
        int release_numeric = 0;
        ProError release_code = ProEngineerReleaseNumericversionGet(&release_numeric);
        report["creo_release_query_code"] = release_code;
        report["creo_release_numeric"] = release_code ? J(nullptr) : J(release_numeric);
        report["session_fingerprint"] = recovery_session_fingerprint();
        if (!publish_native_json(
                job + L"\\native_owner.json",
                {{"pid", GetCurrentProcessId()},
                 {"created", (static_cast<unsigned long long>(created.dwHighDateTime) << 32) |
                                 created.dwLowDateTime},
                 {"session_fingerprint", report["session_fingerprint"]}}))
            throw std::runtime_error("Cannot persist connected session ownership evidence");
        if (request.contains("reconciliation")) {
            generic_stage("recovery_" + request["reconciliation"]["action"].get<std::string>());
            reconcile_native(request, checkpoint, report);
        } else if (request.contains("session_models")) {
            generic_stage("list_session_models");
            session_models_native(report);
        } else if (request.contains("session_assembly")) {
            generic_stage("inspect_session_assembly");
            session_assembly_native(request, report);
        } else if (request.contains("open_file")) {
            generic_stage("open_file_" + request["open_file"]["model_kind"].get<std::string>());
            open_file_native(request, report);
        } else if (request.contains("session_erase")) {
            generic_stage("session_erase_" + request["session_erase"]["action"].get<std::string>());
            session_erase_native(request, report);
        } else if (request.contains("adoption")) {
            generic_stage("adoption_" + request["adoption"]["action"].get<std::string>());
            adopt_native(request, report);
        } else {
            // Recovery has its own evidence-bound path. Check callback readiness
            // only for a normal plan that will create a direct Blend.
            for (const auto &operation : request.at("operations")) {
                if (operation.value("op", "") == "loft") {
                    generic_stage("callback_preflight");
                    wchar_t executable[MAX_PATH];
                    GetModuleFileNameW(nullptr, executable, MAX_PATH);
                    std::string command;
                    resident_blend_callback(std::filesystem::path(executable).parent_path(),
                                            command);
                    break;
                }
            }
            ProName name;
            wcscpy_s(name, model_name.c_str());
            ProMdlType mdltype =
                model.value("model_type", "part") == "assembly" ? PRO_MDL_ASSEMBLY : PRO_MDL_PART;
            ProError found = ProMdlInit(name, mdltype, &board);
            if (request.at("new").get<bool>()) {
                if (found == PRO_TK_NO_ERROR)
                    throw std::runtime_error("New model name already exists in the Creo session");
                if (found != PRO_TK_E_NOT_FOUND)
                    check(found, "CheckNewModelName");
                const J *import_op = import_geometry_choice(request);
                if (import_op) {
                    // BUG-124/C1: the importer creates the part itself, so the
                    // template copy every other new part goes through must not run
                    // first. The operation below only republishes this receipt.
                    generic_stage("import_geometry");
                    board = import_geometry_create(*import_op, model_name, report);
                } else {
                    ProPath original, destination, tfile;
                    CK(ProDirectoryCurrentGet(original));
                    path(destination, folder);
                    path(tfile, template_file);
                    CK(ProDirectoryChange(destination));
                    try {
                        ProMdl templ;
                        if (request.contains("loft_seed"))
                            templ =
                                load_isolated_loft_seed(template_file, report["seed_native_load"]);
                        else
                            CK(ProMdlFiletypeLoad(tfile, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &templ));
                        ProMdlName new_name;
                        wcscpy_s(new_name, model_name.c_str());
                        CK(ProMdlnameCopy(templ, new_name, &board));
                        if (request.contains("loft_seed"))
                            CK(ProMdlErase(templ));
                    } catch (...) {
                        ProDirectoryChange(original);
                        throw;
                    }
                    CK(ProDirectoryChange(original));
                }
                mutated = true;
                new_model_evidence.created = true;
                new_model_evidence.id_known =
                    ProMdlIdGet(board, &new_model_evidence.id) == PRO_TK_NO_ERROR;
                ProBoolean baseline = PRO_B_FALSE;
                new_model_evidence.baseline_known =
                    ProMdlModificationVerify(board, &baseline) == PRO_TK_NO_ERROR;
                new_model_evidence.baseline_modified = baseline == PRO_B_TRUE;
            } else {
                // BUG-124/C1: the documented import creates its own model, so an
                // existing model can never receive it. Python refuses this first.
                if (import_geometry_choice(request))
                    throw std::runtime_error(
                        "import_geometry creates its own new part and cannot be appended to an "
                        "existing model; submit it as the only operation of a new plan");
                if (found == PRO_TK_E_NOT_FOUND) {
                    if (checkpoint.empty())
                        throw std::runtime_error(
                            "model_reconciliation_required: no saved baseline");
                    ProPath file;
                    path(file, checkpoint);
                    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
                } else
                    check(found, "FindOwnedModel");
                if (checkpoint.empty() && !request.value("readonly", false))
                    throw std::runtime_error("model_reconciliation_required: refusing to adopt a "
                                             "checkpointless session model");
                ProPath origin;
                CK(ProMdlOriginGet(board, origin));
                std::wstring actual = origin, prefix = folder + L"\\";
                if (_wcsnicmp(actual.c_str(), prefix.c_str(), prefix.size()))
                    // BUG-106: name the unlock path. A same-name copy saved by
                    // another program, the GUI or a previous session has to be
                    // erased first; the refusal never erases it for the caller.
                    throw std::runtime_error(
                        "Loaded model origin does not match this MCP model's output directory. "
                        "The session holds a same-name model saved elsewhere: read "
                        "creo_erase_session_models(action='inspect'), then call "
                        "creo_erase_session_models(targets=[{name: 'MODEL_NAME', "
                        "model_type: 'part'}]) with that target and retry creo_save_model. "
                        "The session copy is never erased automatically.");
                if ((model.contains("inspection") || model.contains("inspection_ref")) &&
                    !request.value("readonly", false)) {
                    try {
                        // FEAT-052: keep the admission appearance records; the
                        // recolor op refuses components without this baseline.
                        const J admission = choice_inspection(model, "inspection");
                        recolor_set_admission(admission);
                        // BUG-104: refresh_baseline is an explicit per-op request;
                        // only then may the admission appearance come from the
                        // live pre-job read instead of the saved checkpoint.
                        bool refresh_baseline = false;
                        if (request.contains("operations") && request["operations"].is_array())
                            for (const auto &op : request["operations"])
                                if (op.value("op", "") == "recolor_assembly" &&
                                    op.value("refresh_baseline", false))
                                    refresh_baseline = true;
                        if (refresh_baseline)
                            recolor_prime_admission_from_board();
                        verify_saved(admission, inspection());
                    } catch (const std::exception &error) {
                        throw std::runtime_error(std::string("model_reconciliation_required: ") +
                                                 error.what());
                    }
                }
            }
            ProUnitsystem us;
            ProUnititem unit;
            CK(ProMdlPrincipalunitsystemGet(board, &us));
            CK(ProUnitsystemUnitGet(&us, PRO_UNITTYPE_LENGTH, &unit));
            if (wcscmp(unit.name, L"mm"))
                throw std::runtime_error("Expected millimeter model units");
            generic_stage("loaded_blend_validation");
            report["loft_checks"]["loaded"] = verify_loft_settings(L"loaded");
            J seed_profiles;
            if (request.contains("loft_seed")) {
                if (!request.at("new").get<bool>() || request.value("readonly", false))
                    throw std::runtime_error("Loft seed binding requires a new writable part");
                seed_profiles = validate_loft_seed(request["loft_seed"]);
                suppress_seed_for_profiles(request["loft_seed"]["feature_id"], true);
            }
            int operation_total = static_cast<int>(request["operations"].size());
            for (auto op : request["operations"]) {
                last_sketch_solver_info = nullptr;
                last_sketch_reference_info = nullptr;
                ++operation_index;
                operation_position = operation_index;
                operation_in_flight = op;
                executing_operation = true;
                generic_stage("execute_" + op["op"].get<std::string>());
                generic_progress(operation_index + 1, operation_total, op, "start");
                log("OPERATION_INDEX=%d INPUT=%s\n", operation_index, op.dump().c_str());
                if (!request.value("readonly", false)) {
                    mutated = true;
                    new_model_evidence.ops_mutated = true;
                }
                execute_operation(op);
                generic_progress(operation_index + 1, operation_total, op, "done");
                executing_operation = false;
            }
            generic_stage("verify_model");
            generic_substage("verify_model_start");
            auto verify_pending_placements = [&](const char *phase) {
                for (const auto &[id, pending] : pending_constraint_placements) {
                    operation_index = pending.operation_index;
                    operation_in_flight = request["operations"].at(operation_index);
                    executing_operation = true;
                    ProAsmcomp component = {};
                    component.id = id;
                    constraint_placement_failure = nullptr;
                    last_constraint_failure = {true, -1, "", phase, "placement_unverified"};
                    CK(ProModelitemInit(board, id, PRO_FEATURE, &component));
                    verify_constraint_placement(&component, pending, phase,
                                                constraint_placement_failure);
                    operation_results.at(operation_index)["constraint_placement"] =
                        std::move(constraint_placement_failure);
                    constraint_placement_failure = nullptr;
                    executing_operation = false;
                }
            };
            if (request.contains("loft_seed")) {
                suppress_seed_for_profiles(request["loft_seed"]["feature_id"], false);
                // The seed rebinding is a plan-level construction step, not a
                // requested operation: report it beside the operations instead
                // of appending an extra result (T02: N inputs, N results).
                report["loft_seed_feature"] = bind_loft_seed(request["loft_seed"], seed_profiles);
                generic_substage("verify_model_loft_seed");
            }
            if (!request.value("readonly", false)) {
                generic_substage("verify_model_regenerate");
                CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
                verify_pending_placements("after_regenerate");
            }
            generic_substage("verify_model_inspect");
            J state = inspection();
            if (request.contains("loft_seed"))
                report["loft_seed_feature"]["before_save_geometry"] =
                    verify_seed_solid(request.at("loft_seed"), state);
            report["inspection"] = state;
            report["aliases"] = aliases;
            generic_substage("verify_model_assertions");
            verify_assertions(state, request.value("assertions", J::object()));
            std::wstring saved = checkpoint;
            if (!request.value("readonly", false)) {
                generic_stage("before_save_blend_validation");
                generic_substage("verify_model_before_save");
                report["loft_checks"]["before_save"] = verify_loft_settings(L"before_save");
                generic_stage("save_and_reload");
                generic_substage("verify_model_save");
                saved = save_managed_checkpoint(checkpoint, "verify_model_save", report);
                J before = state;
                generic_substage("verify_model_erase");
                reload_managed_checkpoint(saved, mdltype, true);
                generic_substage("verify_model_reload_regenerate");
                CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
                verify_pending_placements("after_reload");
                generic_substage("verify_model_reload_inspect");
                state = inspection();
                if (request.contains("loft_seed"))
                    report["loft_seed_feature"]["reloaded_geometry"] =
                        verify_seed_solid(request.at("loft_seed"), state);
                // FEAT-052: extend the recolor block with the persisted
                // appearance readback before the strict comparison, so the
                // evidence exists even when the comparison throws.
                recolor_after_reload(state, report);
                generic_substage("verify_model_compare");
                verify_saved(before, state, feature_state_touched);
                verify_assertions(state, request.value("assertions", J::object()));
                // The reloaded model must reproduce the recorded intentional
                // suppression set exactly: recorded == actually suppressed.
                if (feature_state_touched) {
                    std::set<int> reloaded_suppressed;
                    for (auto &f : state["features"])
                        if (f["status"].get<int>() == PRO_FEAT_SUPPRESSED)
                            reloaded_suppressed.insert(f["id"].get<int>());
                    if (reloaded_suppressed != recorded_suppressed)
                        throw std::runtime_error(
                            "Saved model suppression set does not match the recorded registry");
                }
                // BUG-120 task 3: measure the panel loft's own quilt on the saved,
                // reloaded model. Best effort: a measurement failure is receipt
                // evidence and never rewrites the save/reload outcome.
                panel_finalize_reloaded_geometry();
                generic_substage("verify_model_after_reload");
                generic_stage("after_reload_blend_validation");
                report["loft_checks"]["after_reload"] = verify_loft_settings(L"after_reload");
                report["saved_file_reloaded_and_verified"] = true;
            }
            state["inspection_source"] =
                request.value("readonly", false) ? "live_query" : "saved_reloaded";
            state["inspection_available"] = true;
            generic_substage("verify_model_preview");
            generic_stage("display_preview");
            // Shared capture (T07): target window selection, current-window and
            // identity checks, fixed view matrix, refit/refresh/repaint order and
            // the raster call live in native/preview.h. A failed capture is
            // recorded with its raw codes beside the successful save; it never
            // turns this job into a failure and never masks the save outcome.
            J preview_json;
            J preview_file;
            int preview_code = 0;
            if (request.value("readonly", false) && operation_results.size() == 1 &&
                operation_results[0].value("op", "") == "export" &&
                operation_results[0].contains("preview")) {
                // The requested JPEG is the preview for this read-only job.
                const J &rendered = operation_results[0];
                preview_json = rendered.at("preview");
                preview_code = rendered.at("preview_code");
                preview_file = rendered.at("file");
            } else {
                PreviewStepOutcome preview = capture_preview(board, job + L"\\output\\preview.jpg",
                                                             true, 8, 6, PRORASTERTYPE_JPEG);
                preview_json = preview_outcome_json(preview);
                preview_code = preview.raster_code;
                preview_file = preview_written(preview) ? J(utf8(preview.path)) : J(nullptr);
                log("PREVIEW=%s\n", preview_json.dump().c_str());
            }
            finalize_operation_results(request, true, false, request.value("readonly", false),
                                       false);
            report.update({{"success", true},
                           {"toolkit_code", 0},
                           {"inspection", state},
                           {"aliases", aliases},
                           {"part_file", utf8(saved)},
                           {"preview_code", preview_code},
                           {"preview", preview_json},
                           {"preview_file", preview_file},
                           {"operations", operation_results}});
            if (feature_state_touched) {
                // Model-level registries ride with the confirmed terminal
                // state; they are never published from a failed job.
                report["feature_tombstones"] = feature_tombstones;
                report["suppressed_features"] = suppressed_features;
            }
            log("BUILD_SUCCESS=1\n");
        }
    } catch (ProError error) {
        report["toolkit_code"] = error;
        // FEAT-012/FEAT-008: this is the failing call's own return code.
        failure_pro_error = J(error);
        failure_pro_error_source = "toolkit";
        report["message"] = "Toolkit call " + last_toolkit_error + " failed with code " +
                            std::to_string(error) + " during " + generic_phase;
        // BUG-097 L2: a failure with a captured ProErrorlist keeps its bounded
        // element/type/error triples and the original section solver messages
        // in the receipt; the text above stays a summary, never the only copy.
        if (!last_feature_error_report.is_null()) {
            report["feature_errors"] = last_feature_error_report;
            const J &element_errors = last_feature_error_report["element_errors"];
            std::string detail;
            for (const auto &entry : element_errors["sample"]) {
                if (!detail.empty())
                    detail += "; ";
                detail += "element=" + std::to_string(entry["element"].get<int>()) +
                          " type=" + std::to_string(entry["type"].get<int>()) +
                          " error=" + std::to_string(entry["error"].get<int>());
            }
            if (element_errors["truncated"].get<bool>())
                detail += "; ...(total " + std::to_string(element_errors["total"].get<int>()) +
                          ", sample capped)";
            if (!detail.empty())
                report["message"] += " Element errors: " + detail + ".";
        }
        log("BUILD_FAILED=%d\n", error);
    } catch (const std::exception &error) {
        report["message"] = error.what();
        if (std::string(error.what()).find("model_reconciliation_required:") == 0)
            report["code"] = "model_reconciliation_required";
        report["toolkit_code"] = PRO_TK_GENERAL_ERROR;
        if (!last_feature_error_report.is_null())
            report["feature_errors"] = last_feature_error_report;
        log("BUILD_FAILED=%s\n", error.what());
    }
    // BUG-109: the completed verify_model sub-stages ride both outcomes, so a
    // stalled save/reload is identifiable from the receipt alone. Old receipts
    // without this key stay valid; nothing is derived from it.
    if (!verify_stages.empty())
        report["verify_stages"] = verify_stages;
    if (!report["success"].get<bool>()) {
        // BUG-105: "mutated" means an operation was dispatched (or a new model
        // was created). A failure with no dispatch left the registered model
        // exactly as it was, whatever the stage, so publish that evidence for
        // the registry to keep the model ready instead of unrecoverable.
        if (!mutated)
            report["model_unchanged"] = true;
        report["failed_stage"] = generic_phase;
        report["failed_toolkit_call"] =
            last_toolkit_error.empty() ? J(nullptr) : J(last_toolkit_error);
        report["failed_operation_index"] = executing_operation ? J(operation_index) : J(nullptr);
        // FEAT-012/FEAT-008: bounded structured context for the failing input
        // (index, operation, stage, names, raw code, bounded text, and the
        // caller's own placement matrix when applicable).
        const std::string failure_message =
            report.contains("message") && report["message"].is_string()
                ? report["message"].get<std::string>()
                : std::string();
        report["failed_operation"] = failed_operation_context(
            operation_in_flight, operation_index, executing_operation, generic_phase,
            failure_pro_error, failure_pro_error_source, last_toolkit_error, failure_message);
        if (constraint_placement_failure.is_object())
            report["constraint_placement_failure"] = constraint_placement_failure;
        // BUG-111: a failed transform names its own backend, angles and reference
        // count instead of leaving only a Toolkit code and the phase name.
        if (executing_operation && operation_in_flight.is_object() &&
            operation_in_flight.value("op", "") == "geometry_transform")
            report["failed_transform"] = transform_failure_report(operation_in_flight);
        // An intermediate inspection is useful diagnostic evidence but is not
        // the restored/current model. Publish it separately, never as a baseline.
        if (report.contains("inspection"))
            report["failure_inspection"] = report["inspection"];
        if (!failed_features.empty())
            report["failed_features"] = failed_features;
        report["inspection"] = nullptr;
        report["inspection_source"] = "unavailable";
    }
    if (!report["success"].get<bool>() && connected && mutated && !checkpoint.empty()) {
        log("PHASE=rollback_to_saved_checkpoint\n");
        // BUG-113: the baseline and the restored state stay readable in the
        // catch blocks, so a rejected comparison reports the actual
        // difference instead of only the comparison's message.
        J rollback_baseline = nullptr;
        J rollback_restored = nullptr;
        try {
            const bool assembly = request["model"].value("model_type", "part") == "assembly";
            reload_managed_checkpoint(checkpoint, assembly ? PRO_MDL_ASSEMBLY : PRO_MDL_PART);
            // Restore the model-level feature registries from the request
            // before verifying the restored state: a partially executed
            // suppress/delete must not leak into the accepted set.
            const J &rollback_model = request["model"];
            feature_tombstones = rollback_model.contains("feature_tombstones") &&
                                         rollback_model["feature_tombstones"].is_object()
                                     ? rollback_model["feature_tombstones"]
                                     : J::object();
            suppressed_features = rollback_model.contains("suppressed_features") &&
                                          rollback_model["suppressed_features"].is_object()
                                      ? rollback_model["suppressed_features"]
                                      : J::object();
            refresh_recorded_suppressed();
            feature_state_effects = J::object();
            feature_state_touched = false;
            rollback_baseline = rollback_model.contains("inspection_ref")
                                    ? read_inspection_ref(rollback_model.at("inspection_ref"))
                                    : rollback_model["inspection"];
            CK(ProSolidRegenerate((ProSolid)board, PRO_REGEN_NO_FLAGS));
            J restored = inspection();
            rollback_restored = restored;
            verify_saved(rollback_baseline, restored);
            // FEAT-052: after the checkpoint reload, compare the restored
            // appearance against the baseline captured before the first
            // appearance write; an unprovable or mismatching restore keeps
            // the existing unknown protection.
            recolor_rollback_check(restored);
            aliases = rollback_model.contains("aliases_ref")
                          ? read_inspection_ref(rollback_model.at("aliases_ref"))
                          : rollback_model["aliases"];
            report["loft_checks"]["rollback"] = verify_loft_settings(L"rollback");
            CK(ProMdlDisplay(board));
            restored["inspection_source"] = "rollback_verified";
            restored["inspection_available"] = true;
            report["inspection"] = restored;
            report["inspection_source"] = "rollback_verified";
            report["aliases"] = aliases;
            report["rollback_succeeded"] = true;
        } catch (const std::exception &e) {
            report["rollback_message"] = e.what();
            report["rollback_difference"] =
                rollback_difference_report(rollback_baseline, rollback_restored, e.what());
        } catch (ProError e) {
            report["rollback_code"] = e;
            report["rollback_message"] = "Checkpoint rollback failed at " + last_toolkit_error;
            report["rollback_difference"] = rollback_difference_report(
                rollback_baseline, rollback_restored, report["rollback_message"]);
        }
    }
    // BUG-096: failed new-model orphan cleanup runs in the same Toolkit lock,
    // after the restore-checkpoint block (the two domains are mutually
    // exclusive: cleanup only ever erases a never-saved job-created orphan,
    // rollback only ever restores a saved checkpoint).
    if (!report["success"].get<bool>()) {
        try {
            report["failed_model_cleanup"] = failed_model_cleanup_receipt(request, connected);
        } catch (...) {
            report["failed_model_cleanup"] =
                cleanup_receipt(false, "unknown", "not_reported", nullptr, false);
        }
    }
    if (!report["success"].get<bool>()) {
        finalize_operation_results(request, false, report.value("rollback_succeeded", false),
                                   request.is_object() && request.value("readonly", false),
                                   cleanup_clears_managed_effect(report));
        // Accepted plans always report their per-operation outcome, including
        // the operations that were never started.
        report["operations"] = operation_results;
    }
    // FEAT-052: publish the final recolor evidence (including the rollback
    // appearance check on the failure path) into the job terminal state.
    recolor_publish(report);
    generic_stage("disconnect");
    if (recovery_deadline)
        recovery_deadline->complete();
    split_report_inspections(request, report);
    int delivered = deliver_native_result(job, report, connected, [&]() {
        int code = ProEngineerDisconnect(&process, 15);
        log("DISCONNECT=%d\n", code);
        return code;
    });
    generic_stage("result_delivery_complete");
    fclose(board_log);
    board_log = nullptr;
    return delivered;
}
