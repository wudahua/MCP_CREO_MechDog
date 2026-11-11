// surface_loft.cpp — FEAT-009 (H02): the minimal two-section boundary blend.
//
// Contract: docs/development/G5-NATIVE-CONTRACT.md §2.1 (candidate tree), §3.1
// (first-release boundary), §4.4.2 (surface_area_mm2/status, surface_type,
// sections) and §6.2 (this entry point). The tree comes from Probbl.h, the only
// documented boundary-blend tree on this SDK. The 2026-11-01 probe added
// PRO_E_EXT_SURF_CUT_SOLID_TYPE/PRO_E_BNBLN_TAN_COND* to the §2.1 skeleton and
// the feature stayed PRO_FEAT_UNREGENERATED; §2.1 explicitly forbids both, so
// this implementation builds the bare skeleton first and completes it from the
// extracted tree instead of guessing element values.
//
// This file is included by generic.cpp after the shared element-tree,
// selection, quilt and measurement helpers are visible; it defines no entry
// point of its own beyond generic_surface_loft.
// BUG-107 / DEV-076: the generator gates constants.inc, but this handwritten
// include must also tolerate SDK generations that omit the boundary-blend tree.
// SDK-free compilation also exercises the automatic missing-header detection.
#ifndef MECHDOG_HAS_PROBBL_HEADER
#if defined(__has_include)
#if __has_include(<Probbl.h>)
#define MECHDOG_HAS_PROBBL_HEADER 1
#endif
#endif
#ifndef MECHDOG_HAS_PROBBL_HEADER
#define MECHDOG_HAS_PROBBL_HEADER 0
#endif
#endif

// H13 / BUG-107: the running executor, not the Python build environment, owns
// the answer to "did this binary compile the boundary-blend route". The worker
// reports this state in its build-info probe so admission can reject the
// operation before a job exists instead of inferring the loaded worker's SDK
// from this machine's headers or from release_numeric.
const char *mechdog_surface_loft_sdk_state() {
    return MECHDOG_HAS_PROBBL_HEADER ? "compiled" : "sdk_header_missing";
}

#if MECHDOG_HAS_PROBBL_HEADER
#include <Probbl.h>

// Bounded element-tree readback. The extracted tree is the only honest source
// of the kernel's own defaults, so it is published as evidence instead of being
// discarded when regeneration fails.
static constexpr int SURFACE_LOFT_TREE_SAMPLE_LIMIT = 160;

// FEAT-065/M1: an upper bound that keeps one element tree (and one receipt)
// bounded; the kernel has no documented maximum of its own.
static constexpr int SURFACE_LOFT_SECTION_LIMIT = 32;
// FEAT-065/M2 experiment: the second direction (guides) is bounded the same way.
static constexpr int SURFACE_LOFT_GUIDE_LIMIT = 8;

// `truncated`, when given, is set once the budget runs out before an element
// or a sibling list is read, so a cut sample never claims to be the whole tree.
static J loft_element_json(ProElement element, int depth, int &budget, bool *truncated = nullptr) {
    J record = J::object();
    if (!element)
        return record;
    if (budget <= 0) {
        if (truncated)
            *truncated = true;
        return record;
    }
    budget--;
    ProElemId id = 0;
    if (!ProElementIdGet(element, &id))
        record["id"] = (int)id;
    ProBoolean compound = PRO_B_FALSE, array = PRO_B_FALSE;
    if (!ProElementIsCompound(element, nullptr, &compound))
        record["compound"] = compound == PRO_B_TRUE;
    if (!ProElementIsArray(element, nullptr, &array))
        record["array"] = array == PRO_B_TRUE;
    if (compound != PRO_B_TRUE && array != PRO_B_TRUE) {
        ProValueDataType type = PRO_VALUE_TYPE_INT;
        ProError type_code = ProElementValuetypeGet(element, &type);
        record["value_type"] = (int)type;
        record["value_code"] = (int)type_code;
        if (!type_code) {
            if (type == PRO_VALUE_TYPE_INT) {
                int value = 0;
                if (!ProElementIntegerGet(element, nullptr, &value))
                    record["integer"] = value;
            } else if (type == PRO_VALUE_TYPE_DOUBLE) {
                double value = 0.0;
                if (!ProElementDoubleGet(element, nullptr, &value))
                    record["double"] = value;
            } else if (type == PRO_VALUE_TYPE_BOOLEAN) {
                ProBoolean value = PRO_B_FALSE;
                if (!ProElementBooleanGet(element, nullptr, &value))
                    record["boolean"] = value == PRO_B_TRUE;
            } else if (type == PRO_VALUE_TYPE_WSTRING) {
                wchar_t *value = nullptr;
                if (!ProElementWstringGet(element, nullptr, &value) && value) {
                    record["string"] = utf8(std::wstring(value));
                    ProWstringFree(value);
                }
            } else if (type == PRO_VALUE_TYPE_SELECTION) {
                ProReference *refs = nullptr;
                if (!ProElementReferencesGet(element, nullptr, &refs)) {
                    int count = 0;
                    if (!ProArraySizeGet((ProArray)refs, &count))
                        record["reference_count"] = count;
                }
                if (refs)
                    ProArrayFree((ProArray *)&refs);
            }
        }
    }
    if (depth < 12) {
        ProElement *children = nullptr;
        ProArrayAlloc(0, sizeof(ProElement), 1, (ProArray *)&children);
        ProError code = array == PRO_B_TRUE ? ProElementArrayGet(element, nullptr, &children)
                                            : ProElementChildrenGet(element, nullptr, &children);
        int count = 0;
        if (!code)
            ProArraySizeGet((ProArray)children, &count);
        J items = J::array();
        for (int index = 0; index < count; index++) {
            if (budget <= 0) {
                if (truncated)
                    *truncated = true;
                break;
            }
            items.push_back(loft_element_json(children[index], depth + 1, budget, truncated));
        }
        if (!items.empty())
            record["children"] = items;
        if (children)
            ProArrayFree((ProArray *)&children);
    }
    return record;
}

static J loft_tree_json(ProElement root, int limit = SURFACE_LOFT_TREE_SAMPLE_LIMIT) {
    int budget = limit;
    bool truncated = false;
    J sample = loft_element_json(root, 0, budget, &truncated);
    return {{"limit", limit},
            {"truncated", truncated},
            {"root", sample},
            {"elements_read", limit - budget}};
}

// One section = one sketch feature. A section may be a single non-composite
// curve, or the two curves that make one closed profile: Creo stores a closed
// ellipse/circle as two arcs, and requiring one curve would make every closed
// hull section unusable. Composite curves and three or more curves are still
// refused instead of being stitched by guesswork.
static std::vector<int> surface_loft_curves(const J &reference, const char *role) {
    int id = feature_id(reference);
    ProFeature sketch;
    CK(ProFeatureInit((ProSolid)board, id, &sketch));
    ProFeattype type;
    CK(ProFeatureTypeGet(&sketch, &type));
    if (type != PRO_FEAT_CURVE)
        throw std::runtime_error(std::string("surface_loft ") + role +
                                 " section is not an independent sketch (feature " +
                                 std::to_string(id) + ")");
    J items = J::array();
    CK(ProFeatureGeomitemVisit(&sketch, PRO_CURVE, collect_geom_ids, nullptr, &items));
    std::vector<int> simple;
    for (auto item : items) {
        ProCurve curve = nullptr;
        if (ProCurveInit((ProSolid)board, item["id"].get<int>(), &curve))
            continue;
        ProEnttype kind;
        if (ProCurveTypeGet(curve, &kind) == PRO_TK_NO_ERROR && kind != PRO_ENT_CMP_CRV)
            simple.push_back(item["id"].get<int>());
    }
    if (simple.size() != 1 && simple.size() != 2)
        throw std::runtime_error(
            std::string("surface_loft ") + role +
            " section must own one curve, or two curves forming one closed profile; feature " +
            std::to_string(id) + " owns " + std::to_string((int)simple.size()) +
            " non-composite curves");
    return simple;
}

// FEAT-065/M3 (2026-11-11, offline): one loft input is one chain holder. A
// sketch label/id keeps the M1/M2 resolution above unchanged; an explicit
// {kind:'curve'|'edge',id} goes straight into the curve collection; a point
// ({kind:'point',id} or {kind:'datum_point_feature',label}) is a convergence
// end at the first or last section only. Only the sketch form has Creo 12.4
// live evidence; every other form is reported in unverified_input_forms.
struct SurfaceLoftInput {
    std::string source; // sketch | curve | edge | point
    ProType type = PRO_CURVE;
    std::vector<int> ids;
    J record;
};

static const char *SURFACE_LOFT_INPUT_FORMS =
    "use a sketch label or feature id, {kind:'curve',id:N} (a PRO_CURVE geometry id such as a "
    "project_curve curve_id) or {kind:'edge',id:N} (an edge id from creo_inspect_model)";

// A rejected input names its slot, its request, the reason and the form to use
// instead, both in the message and as a staged failed_loft_input block, so a
// client never has to parse prose to learn which reference was wrong.
[[noreturn]] static void surface_loft_reject(J details, const char *role, size_t index,
                                             const J &request, const char *reason, ProError code,
                                             const std::string &why, const std::string &instead) {
    const std::string slot = std::string(role) + "s[" + std::to_string(index) + "]";
    details["failed_loft_input"] = {
        {"role", role},
        {"index", (int)index},
        {"slot", slot},
        {"request", request},
        {"reason", reason},
        {"query_code", code == PRO_TK_NO_ERROR ? J(nullptr) : J((int)code)},
        {"use_instead", instead}};
    stage_operation_result(details);
    throw std::runtime_error("SURFACE_LOFT_INPUT_REJECTED: surface_loft " + slot + " " +
                             request.dump() + ": " + why + "; " + instead);
}

// Typed existence check: ProModelitemInit documents "item not found" for a
// wrong id or type, and the type-specific query proves the handle is real.
static ProError surface_loft_probe(int id, ProType type) {
    ProModelitem item;
    ProError code = ProModelitemInit(board, id, type, &item);
    if (code != PRO_TK_NO_ERROR)
        return code;
    if (type == PRO_CURVE) {
        ProCurve curve = nullptr;
        ProEnttype kind = PRO_ENT_NONE;
        code = ProCurveInit((ProSolid)board, id, &curve);
        if (code == PRO_TK_NO_ERROR)
            code = ProCurveTypeGet(curve, &kind);
    } else if (type == PRO_EDGE) {
        ProEdge edge = nullptr;
        ProEnttype kind = PRO_ENT_NONE;
        code = ProEdgeInit((ProSolid)board, id, &edge);
        if (code == PRO_TK_NO_ERROR)
            code = ProEdgeTypeGet(edge, &kind);
    } else if (type == PRO_POINT) {
        ProPoint point = nullptr;
        ProVector xyz = {0.0, 0.0, 0.0};
        code = ProPointInit((ProSolid)board, id, &point);
        if (code == PRO_TK_NO_ERROR)
            code = ProPointCoordGet(point, xyz);
    }
    return code;
}

// A curve id passed as an edge (or the reverse) is answered with the kind the
// id really resolves to, not only with "not found".
static std::string surface_loft_kind_hint(int id, ProType requested) {
    // Function-local and non-static: the aggregate-compile contract collects
    // every `static` line in this gated region as a guarded file symbol.
    const std::pair<ProType, const char *> candidates[] = {
        {PRO_CURVE, "curve"}, {PRO_EDGE, "edge"}, {PRO_POINT, "point"}};
    for (const auto &kind : candidates)
        if (kind.first != requested && surface_loft_probe(id, kind.first) == PRO_TK_NO_ERROR)
            return std::string(" (id ") + std::to_string(id) + " does resolve as a " + kind.second +
                   "; pass {kind:'" + kind.second + "',id:" + std::to_string(id) + "})";
    return "";
}

static SurfaceLoftInput surface_loft_input(const J &reference, const char *role, size_t index,
                                           size_t count, const J &details) {
    SurfaceLoftInput input;
    if (!reference.is_object()) {
        // Sketch label or feature id: the published M1/M2 path, message and all.
        const std::string legacy = std::string(role) + " " + std::to_string((int)index + 1);
        input.source = "sketch";
        input.ids = surface_loft_curves(reference, legacy.c_str());
        input.record = {{"source", "sketch"},
                        {"feature_id", feature_id(reference)},
                        {"geometry_type", "curve"},
                        {"ids", input.ids},
                        {"live_verified", true}};
        return input;
    }
    const std::string kind = reference.contains("kind") && reference["kind"].is_string()
                                 ? reference["kind"].get<std::string>()
                                 : std::string();
    const bool section = std::string(role) == "section";
    const bool end_slot = index == 0 || index + 1 == count;
    if (kind == "point" || kind == "datum_point_feature") {
        if (!section)
            surface_loft_reject(details, role, index, reference, "point_in_guides", PRO_TK_NO_ERROR,
                                "a guide is a curve that crosses every section and cannot be a "
                                "point",
                                SURFACE_LOFT_INPUT_FORMS);
        if (!end_slot)
            surface_loft_reject(details, role, index, reference, "point_not_at_end",
                                PRO_TK_NO_ERROR,
                                "a point is only accepted as the first or last section (a "
                                "convergence end)",
                                "move the point to sections[0] or the last section, or " +
                                    std::string(SURFACE_LOFT_INPUT_FORMS));
    } else if (kind != "curve" && kind != "edge") {
        surface_loft_reject(details, role, index, reference, "unsupported_kind", PRO_TK_NO_ERROR,
                            kind.empty() ? std::string("the reference carries no string kind")
                                         : "kind '" + kind + "' is not a loft section or guide",
                            std::string(SURFACE_LOFT_INPUT_FORMS) +
                                (section ? ", or at the first/last section {kind:'point',id:N} / "
                                           "{kind:'datum_point_feature',label:...}"
                                         : ""));
    }

    int id = -1;
    if (kind != "datum_point_feature") {
        const J raw = reference.contains("id") ? reference["id"] : J(nullptr);
        if (!raw.is_number_integer() || raw.get<long long>() < 0 ||
            raw.get<long long>() > 2147483647LL)
            surface_loft_reject(details, role, index, reference, "invalid_id", PRO_TK_NO_ERROR,
                                "the id must be a nonnegative 32-bit geometry id",
                                "read a current id from creo_inspect_model");
        id = raw.get<int>();
    }

    if (kind == "curve" || kind == "edge") {
        const ProType type = kind == "curve" ? PRO_CURVE : PRO_EDGE;
        ProError code = surface_loft_probe(id, type);
        if (code != PRO_TK_NO_ERROR)
            surface_loft_reject(
                details, role, index, reference,
                kind == "curve" ? "curve_not_found" : "edge_not_found", code,
                "no " + kind + " geometry with id " + std::to_string(id) + " in this model" +
                    surface_loft_kind_hint(id, type),
                kind == "curve"
                    ? "pass a current PRO_CURVE id (creo_inspect_model section=feature_geometry, "
                      "type 62, or a project_curve curve_id), or name the sketch by its label"
                    : "pass a current edge id from creo_inspect_model; ids change when the "
                      "model rebuilds");
        input.source = kind;
        input.type = type;
        input.ids = {id};
        input.record = {{"source", kind},
                        {"geometry_type", kind},
                        {"ids", input.ids},
                        {"live_verified", false}};
        if (type == PRO_CURVE) {
            ProCurve curve = nullptr;
            ProEnttype curve_type = PRO_ENT_NONE;
            CK(ProCurveInit((ProSolid)board, id, &curve));
            CK(ProCurveTypeGet(curve, &curve_type));
            input.record["curve_type"] = (int)curve_type;
            // Probbl.h allows a composite curve in the collection; it is
            // reported, not refused, because the caller named this exact id.
            input.record["composite"] = curve_type == PRO_ENT_CMP_CRV;
        } else {
            ProEdge edge = nullptr;
            ProEnttype edge_type = PRO_ENT_NONE;
            CK(ProEdgeInit((ProSolid)board, id, &edge));
            CK(ProEdgeTypeGet(edge, &edge_type));
            input.record["edge_type"] = (int)edge_type;
            // The faces on either side of the edge: a quilt boundary edge has
            // one, an interior or solid edge two. FEAT-065/M4 needs this to name
            // the surface a boundary condition would refer to.
            ProEdge next1 = nullptr, next2 = nullptr;
            ProSurface face1 = nullptr, face2 = nullptr;
            ProError neighbors = ProEdgeNeighborsGet(edge, &next1, &next2, &face1, &face2);
            J adjacent = J::array();
            if (neighbors == PRO_TK_NO_ERROR)
                for (ProSurface face : {face1, face2}) {
                    int surface_id = -1;
                    if (face && ProSurfaceIdGet(face, &surface_id) == PRO_TK_NO_ERROR)
                        adjacent.push_back(surface_id);
                }
            input.record["neighbors_query_code"] = (int)neighbors;
            input.record["adjacent_surface_ids"] =
                neighbors == PRO_TK_NO_ERROR ? adjacent : J(nullptr);
        }
        return input;
    }

    // Convergence point. The curve-collection instruction for points is
    // documented in ProCrvcollection.h (PRO_CURVCOLL_ADD_POINT_INSTR); its use
    // inside a boundary-blend chain holder is not documented in Probbl.h, so
    // this route is an experiment until a Creo 12.4 live run proves it.
    int point_feature = -1;
    if (kind == "datum_point_feature") {
        if (!reference.contains("label") || !reference["label"].is_string() ||
            reference["label"].get<std::string>().empty())
            surface_loft_reject(details, role, index, reference, "invalid_label", PRO_TK_NO_ERROR,
                                "datum_point_feature needs a non-empty feature label",
                                "pass {kind:'datum_point_feature',label:'<datum_points label>'}");
        try {
            point_feature = feature_id(reference["label"]);
        } catch (const std::runtime_error &error) {
            surface_loft_reject(details, role, index, reference, "label_not_found", PRO_TK_NO_ERROR,
                                error.what(),
                                "create the point with a single-point datum_points operation "
                                "first, or pass {kind:'point',id:N}");
        }
        ProFeature point_owner = {};
        ProFeattype owner_type = 0;
        ProError code = ProModelitemInit(board, point_feature, PRO_FEATURE, &point_owner);
        if (code == PRO_TK_NO_ERROR)
            code = ProFeatureTypeGet(&point_owner, &owner_type);
        if (code != PRO_TK_NO_ERROR || owner_type != PRO_FEAT_DATUM_POINT)
            surface_loft_reject(details, role, index, reference, "not_a_datum_point_feature", code,
                                "feature " + std::to_string(point_feature) +
                                    " is not a datum point feature",
                                "pass a single-point datum_points label or {kind:'point',id:N}");
        J points = J::array();
        code = ProFeatureGeomitemVisit(&point_owner, PRO_POINT, collect_geom_ids, nullptr, &points);
        if (code != PRO_TK_NO_ERROR || points.size() != 1)
            surface_loft_reject(details, role, index, reference, "point_count", code,
                                "datum point feature " + std::to_string(point_feature) +
                                    " defines " + std::to_string((int)points.size()) +
                                    " points; a convergence end needs exactly one",
                                "use a single-point datum_points feature or {kind:'point',id:N}");
        id = points[0]["id"].get<int>();
    }
    ProError code = surface_loft_probe(id, PRO_POINT);
    if (code != PRO_TK_NO_ERROR)
        surface_loft_reject(details, role, index, reference, "point_not_found", code,
                            "no datum point geometry with id " + std::to_string(id) +
                                " in this model" + surface_loft_kind_hint(id, PRO_POINT),
                            "pass {kind:'datum_point_feature',label:...} for a datum_points "
                            "feature, or a current point id");
    ProPoint point = nullptr;
    ProVector xyz = {0.0, 0.0, 0.0};
    CK(ProPointInit((ProSolid)board, id, &point));
    CK(ProPointCoordGet(point, xyz));
    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    input.source = "point";
    input.type = PRO_POINT;
    input.ids = {id};
    input.record = {{"source", "point"},
                    {"geometry_type", "point"},
                    {"ids", input.ids},
                    {"point_mm", xyz_json(xyz, scale)},
                    {"chain_instruction", "PRO_CURVCOLL_ADD_POINT_INSTR"},
                    {"live_verified", false}};
    if (point_feature >= 0)
        input.record["feature_id"] = point_feature;
    return input;
}

// The documented point instruction of ProCrvcollection.h, mirrored on the
// curve_collection() shape the curve/edge holders use. Every code is kept so a
// refusal of the undocumented point holder is evidence, not a bare -1.
static void surface_loft_point_chain(ProElement element, int point_id, J &details) {
    J codes = J::object();
    ProCollection collection = nullptr;
    ProCrvcollinstr instruction = nullptr;
    ProSelection selected = nullptr;
    ProReference reference = nullptr;
    ProError code = ProCrvcollectionAlloc(&collection);
    codes["collection_alloc"] = (int)code;
    if (code == PRO_TK_NO_ERROR) {
        code = ProCrvcollinstrAlloc(PRO_CURVCOLL_ADD_POINT_INSTR, &instruction);
        codes["instruction_alloc"] = (int)code;
    }
    if (code == PRO_TK_NO_ERROR) {
        ProModelitem item;
        code = ProModelitemInit(board, point_id, PRO_POINT, &item);
        if (code == PRO_TK_NO_ERROR)
            code = ProSelectionAlloc(nullptr, &item, &selected);
        if (code == PRO_TK_NO_ERROR)
            code = ProSelectionToReference(selected, &reference);
        codes["point_reference"] = (int)code;
    }
    if (code == PRO_TK_NO_ERROR) {
        code = ProCrvcollinstrReferenceAdd(instruction, reference);
        codes["reference_add"] = (int)code;
    }
    if (code == PRO_TK_NO_ERROR) {
        code = ProCrvcollectionInstructionAdd(collection, instruction);
        codes["instruction_add"] = (int)code;
    }
    if (code == PRO_TK_NO_ERROR) {
        code = ProElementCollectionSet(element, collection);
        codes["collection_set"] = (int)code;
    }
    if (instruction)
        ProCrvcollinstrFree(instruction);
    if (selected)
        ProSelectionFree(&selected);
    if (collection)
        ProCollectionFree(&collection);
    details["convergence_point"]["chain_codes"] = codes;
    if (code != PRO_TK_NO_ERROR) {
        stage_operation_result(details);
        throw std::runtime_error(
            "SURFACE_LOFT_POINT_CHAIN_REFUSED: surface_loft could not place point " +
            std::to_string(point_id) + " in a chain holder (code " + std::to_string((int)code) +
            "); the PRO_CURVCOLL_ADD_POINT_INSTR holder is an unproven FEAT-065 M3 route. No "
            "feature was created");
    }
}

static void surface_loft_chain(ProElement holders, const SurfaceLoftInput &input, J &details) {
    ProElement holder = node(holders, PRO_E_STD_CHAIN_HOLDER);
    ProElement collection = node(holder, PRO_E_STD_CURVE_COLLECTION_APPL);
    if (input.type == PRO_POINT) {
        surface_loft_point_chain(collection, input.ids.front(), details);
        return;
    }
    J refs = J::array();
    for (int id : input.ids)
        refs.push_back({{"kind", input.type == PRO_EDGE ? "edge" : "curve"}, {"id", id}});
    curve_collection(collection, refs);
}

// FEAT-065/M4 (2026-11-11, offline candidate): continuity between one loft
// boundary and the face next to it. Probbl.h documents only TAN_COND_FREE for
// PRO_E_BNBLN_TAN_COND_TYPE and gives it no parsable value, and the
// kernel-completed PRO_E_BNBLN_TAN_COND array (four PRO_E_BNBLN_TNC_BNDRY,
// TAN_COND_TYPE=1,1,0,0 on 2026-11-07) does not say which entry is which
// boundary. Both tables stay empty until FEAT-065 T2b reads a Creo-built
// reference part: an empty entry refuses the request after extraction and
// before redefine, so nothing is guessed into the kernel. The public field is
// also refused before a job by capabilities.UNAVAILABLE_FIELDS.
static const std::map<std::string, int> SURFACE_LOFT_TAN_COND_TYPE_VALUES = {};
static const std::map<std::string, int> SURFACE_LOFT_TNC_BOUNDARY_INDEX = {};
// PRO_E_SURF_CHAIN_METHOD of the connect chain. ProSweep.h's ProSurfChainMethod
// is not documented for Probbl.h, so -1 leaves the element unwritten until the
// reference tree shows the value Creo stores.
static const int SURFACE_LOFT_CONNECT_CHAIN_METHOD = -1;
// The TAN_COND subtree has its own budget: in a large loft the shared
// 160-element sample runs out before the walk reaches it.
static constexpr int SURFACE_LOFT_TAN_COND_SAMPLE_LIMIT = 64;

struct SurfaceLoftCondition {
    size_t index = 0;
    std::string boundary;
    std::string condition;
    int edge_id = -1;
    int surface_id = -1;
};

[[noreturn]] static void surface_loft_condition_reject(J &details, const char *prefix,
                                                       const SurfaceLoftCondition &item,
                                                       const char *reason, ProError code,
                                                       const std::string &why) {
    const std::string slot = "boundary_conditions[" + std::to_string(item.index) + "]";
    details["failed_boundary_condition"] = {
        {"index", (int)item.index},
        {"slot", slot},
        {"boundary", item.boundary},
        {"condition", item.condition},
        {"reason", reason},
        {"query_code", code == PRO_TK_NO_ERROR ? J(nullptr) : J((int)code)},
        {"tracking", "FEAT-065 T2b"}};
    stage_operation_result(details);
    throw std::runtime_error(std::string(prefix) + ": surface_loft " + slot + " " + item.boundary +
                             "=" + item.condition + ": " + why);
}

// Re-checks the request shape (a hand-written plan can bypass the Python
// model) and resolves each non-free boundary to its edge and the edge's single
// adjacent face. Runs before the feature tree is built, so a refusal here
// creates nothing.
static std::vector<SurfaceLoftCondition> surface_loft_conditions(
    const J &op, const std::vector<SurfaceLoftInput> &sections,
    const std::vector<SurfaceLoftInput> &guides, J &details) {
    std::vector<SurfaceLoftCondition> result;
    if (!op.contains("boundary_conditions") || op["boundary_conditions"].is_null())
        return result;
    const J &items = op["boundary_conditions"];
    if (!items.is_array() || items.size() > 4)
        throw std::runtime_error("SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED: surface_loft "
                                 "boundary_conditions must be a list of at most four "
                                 "{boundary, condition} objects");
    std::set<std::string> seen;
    J echo = J::array();
    for (size_t index = 0; index < items.size(); index++) {
        const J &raw = items[index];
        SurfaceLoftCondition item;
        item.index = index;
        if (raw.is_object() && raw.contains("boundary") && raw["boundary"].is_string())
            item.boundary = raw["boundary"].get<std::string>();
        if (raw.is_object() && raw.contains("condition") && raw["condition"].is_string())
            item.condition = raw["condition"].get<std::string>();
        auto refuse = [&details, &item](const char *reason, ProError code, const std::string &why) {
            surface_loft_condition_reject(details, "SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED", item,
                                          reason, code, why);
        };
        const bool section = item.boundary == "first_section" || item.boundary == "last_section";
        if (!section && item.boundary != "first_guide" && item.boundary != "last_guide")
            refuse("unknown_boundary", PRO_TK_NO_ERROR,
                   "boundary must be first_section, last_section, first_guide or last_guide");
        if (item.condition != "free" && item.condition != "tangent" &&
            item.condition != "curvature" && item.condition != "normal")
            refuse("unknown_condition", PRO_TK_NO_ERROR,
                   "condition must be free, tangent, curvature or normal");
        if (!seen.insert(item.boundary).second)
            refuse("repeated_boundary", PRO_TK_NO_ERROR, "each boundary may be named once");
        const std::vector<SurfaceLoftInput> &slots = section ? sections : guides;
        if (slots.empty())
            refuse("no_guides", PRO_TK_NO_ERROR, "the loft has no guides");
        const bool first = item.boundary == "first_section" || item.boundary == "first_guide";
        const SurfaceLoftInput &input = first ? slots.front() : slots.back();
        if (item.condition != "free") {
            if (input.source != "edge")
                refuse("boundary_not_an_edge", PRO_TK_NO_ERROR,
                       "a non-free condition needs that boundary to be an edge {kind:'edge',id:N}, "
                       "not a " +
                           input.source);
            const J faces = input.record.value("adjacent_surface_ids", J(nullptr));
            if (!faces.is_array() || faces.size() != 1)
                refuse("adjacent_face_count",
                       (ProError)input.record.value("neighbors_query_code", 0),
                       "edge " + std::to_string(input.ids.front()) + " has " +
                           std::to_string(faces.is_array() ? (int)faces.size() : -1) +
                           " readable adjacent faces; a continuity neighbour must be the single "
                           "face of a quilt boundary edge");
            item.edge_id = input.ids.front();
            item.surface_id = faces[0].get<int>();
        }
        echo.push_back({{"index", (int)index},
                        {"boundary", item.boundary},
                        {"condition", item.condition},
                        {"edge_id", item.edge_id < 0 ? J(nullptr) : J(item.edge_id)},
                        {"surface_id", item.surface_id < 0 ? J(nullptr) : J(item.surface_id)},
                        {"status", item.condition == "free" ? "kernel_default" : "requested"}});
        result.push_back(item);
    }
    details["boundary_conditions"] = echo;
    return result;
}

static J surface_loft_tan_cond_json(ProElement tree) {
    ProError code = PRO_TK_NO_ERROR;
    ProElement array = get_optional(tree, {PRO_E_BNBLN_TAN_COND}, &code);
    if (code != PRO_TK_NO_ERROR || !array)
        return {{"available", false}, {"query_code", (int)code}};
    J sample = loft_tree_json(array, SURFACE_LOFT_TAN_COND_SAMPLE_LIMIT);
    sample["available"] = true;
    return sample;
}

// Mapping unknown: refuse before any element of the extracted tree is touched.
// Mapping known: rewrite that TNC_BNDRY entry's TAN_COND_TYPE and rebuild its
// connect chain around the edge's single adjacent face.
static void surface_loft_apply_conditions(ProElement tree,
                                          const std::vector<SurfaceLoftCondition> &conditions,
                                          J &details) {
    const char *unmapped = "SURFACE_LOFT_BOUNDARY_CONDITION_UNMAPPED";
    bool any = false;
    for (const auto &item : conditions) {
        if (item.condition == "free")
            continue;
        any = true;
        if (!SURFACE_LOFT_TAN_COND_TYPE_VALUES.count(item.condition) ||
            !SURFACE_LOFT_TNC_BOUNDARY_INDEX.count(item.boundary))
            surface_loft_condition_reject(
                details, unmapped, item, "unmapped", PRO_TK_NO_ERROR,
                "the PRO_E_BNBLN_TAN_COND_TYPE value of '" + item.condition +
                    "' and the PRO_E_BNBLN_TNC_BNDRY entry of '" + item.boundary +
                    "' are unknown (Probbl.h documents only TAN_COND_FREE); FEAT-065 T2b must "
                    "read them from a reference part. The feature is rolled back");
    }
    if (!any)
        return;

    ProError code = PRO_TK_NO_ERROR;
    ProElement array = get_optional(tree, {PRO_E_BNBLN_TAN_COND}, &code);
    std::vector<ProElement> entries;
    if (code == PRO_TK_NO_ERROR && array) {
        ProElement *items = nullptr;
        int count = 0;
        code = ProArrayAlloc(0, sizeof(ProElement), 1, (ProArray *)&items);
        if (code == PRO_TK_NO_ERROR)
            code = ProElementArrayGet(array, nullptr, &items);
        if (code == PRO_TK_NO_ERROR)
            code = ProArraySizeGet((ProArray)items, &count);
        for (int index = 0; code == PRO_TK_NO_ERROR && index < count; index++)
            entries.push_back(items[index]);
        if (items)
            ProArrayFree((ProArray *)&items);
    }
    for (const auto &item : conditions) {
        if (item.condition == "free")
            continue;
        J &record = details["boundary_conditions"][item.index];
        const int position = SURFACE_LOFT_TNC_BOUNDARY_INDEX.at(item.boundary);
        if (code != PRO_TK_NO_ERROR || position < 0 || position >= (int)entries.size())
            surface_loft_condition_reject(
                details, unmapped, item, "tan_cond_entry_missing", code,
                "the extracted tree holds " + std::to_string((int)entries.size()) +
                    " PRO_E_BNBLN_TNC_BNDRY entries and the mapped entry " +
                    std::to_string(position) + " is not among them. The feature is rolled back");
        ProElement entry = entries[position];
        const int value = SURFACE_LOFT_TAN_COND_TYPE_VALUES.at(item.condition);

        ProError type_code = PRO_TK_NO_ERROR;
        ProElement type = get_optional(entry, {PRO_E_BNBLN_TAN_COND_TYPE}, &type_code);
        if (type_code != PRO_TK_NO_ERROR || !type)
            type = node(entry, PRO_E_BNBLN_TAN_COND_TYPE);
        CK(ProElementIntegerSet(type, value));

        // Rebuilt from scratch, so no kernel default face survives beside the
        // requested one.
        ProError chain_code = PRO_TK_NO_ERROR;
        if (get_optional(entry, {PRO_E_BNBLN_CONNECT_SURF_CHAIN}, &chain_code) &&
            chain_code == PRO_TK_NO_ERROR) {
            ProElempathItem step = {};
            step.type = PRO_ELEM_PATH_ITEM_TYPE_ID;
            step.path_item.elem_id = (ProElemId)PRO_E_BNBLN_CONNECT_SURF_CHAIN;
            ProElempath path = nullptr;
            ProElement removed = nullptr;
            ProError remove_code = ProElempathAlloc(&path);
            if (remove_code == PRO_TK_NO_ERROR)
                remove_code = ProElempathDataSet(path, &step, 1);
            if (remove_code == PRO_TK_NO_ERROR)
                remove_code = ProElemtreeElementRemove(entry, path, &removed);
            if (path)
                ProElempathFree(&path);
            check(remove_code, "ProElemtreeElementRemove(PRO_E_BNBLN_CONNECT_SURF_CHAIN)");
            if (removed)
                CK(ProElementFree(&removed));
        }
        ProElement chain = node(entry, PRO_E_BNBLN_CONNECT_SURF_CHAIN);
        ProElement compound = node(chain, PRO_E_SURF_CHAIN_CMPND);
        if (SURFACE_LOFT_CONNECT_CHAIN_METHOD >= 0)
            integer(compound, PRO_E_SURF_CHAIN_METHOD, SURFACE_LOFT_CONNECT_CHAIN_METHOD);
        ProElement surfaces = node(compound, PRO_E_SURF_CHAIN_REF_SURFS);
        ProElement surface = node(surfaces, PRO_E_SURF_CHAIN_SURF);
        ProSelection face = selection(item.surface_id, PRO_SURFACE);
        try {
            ref(surface, PRO_E_SURF_CHAIN_REF, face);
        } catch (...) {
            ProSelectionFree(&face);
            throw;
        }
        ProSelectionFree(&face);
        record["status"] = "written";
        record["tnc_index"] = position;
        record["tan_cond_type"] = value;
        record["surf_chain_method"] = SURFACE_LOFT_CONNECT_CHAIN_METHOD >= 0
                                          ? J(SURFACE_LOFT_CONNECT_CHAIN_METHOD)
                                          : J(nullptr);
    }
}

static void generic_surface_loft(const J &op) {
    const J &sections = op.at("sections");
    // FEAT-065/M1 (2026-11-10): the same PRO_E_BNBLN_1DIR tree that carries two
    // sections carries N — each section is one more chain holder — so the
    // published single-direction straight blend now accepts 2..32 sections.
    // FEAT-065/M2 adds the second direction (guides) beside it, never instead
    // of it: a guided blend still needs at least two sections.
    if (sections.size() < 2)
        throw std::runtime_error("surface_loft requires at least two sections");
    if (sections.size() > SURFACE_LOFT_SECTION_LIMIT)
        throw std::runtime_error("surface_loft accepts at most " +
                                 std::to_string(SURFACE_LOFT_SECTION_LIMIT) +
                                 " sections; split the plan instead");
    const std::string interpolation = op.value("interpolation", "straight");
    if (interpolation != "straight" && interpolation != "smooth")
        throw std::runtime_error(
            "surface_loft interpolation must be 'straight' (exactly two sections) or 'smooth' "
            "(three or more sections)");
    // Measured 2026-11-11 on Creo 12.4.0.0: >2 holders produce one blend through
    // every section, not piecewise ruled patches, so "straight" would be a lie.
    if (sections.size() > 2 && interpolation != "smooth")
        throw std::runtime_error(
            "surface_loft with more than two sections is a smooth blend through every section; "
            "pass interpolation=\"smooth\"");

    // An empty list is the schema default, i.e. "no second direction"; it must
    // stay a plain single-direction blend rather than a one-guide request.
    const bool has_guides = op.contains("guides") && !op["guides"].is_null() &&
                            (!op["guides"].is_array() || !op["guides"].empty());
    // FEAT-065/M3: the request echo is staged with any rejected input, so the
    // failure record names the slot without the caller re-reading its plan.
    J details = {{"op", "surface_loft"},
                 {"sections", sections},
                 {"interpolation", interpolation},
                 {"guides", has_guides ? op["guides"] : J::array()},
                 {"route", "probbl_boundary_blend"}};

    // Sketch sections resolve exactly as in M1/M2 (same curves, same messages).
    // One (type, id) set spans sections and guides: no geometry item may sit in
    // two chain holders, whichever spelling named it.
    std::vector<SurfaceLoftInput> section_inputs;
    std::vector<int> curve_ids;
    std::set<std::pair<int, int>> used_items;
    int point_sections = 0;
    for (size_t index = 0; index < sections.size(); index++) {
        std::string role = "section " + std::to_string((int)index + 1);
        SurfaceLoftInput input =
            surface_loft_input(sections[index], "section", index, sections.size(), details);
        for (int id : input.ids) {
            if (!used_items.insert({(int)input.type, id}).second) {
                if (input.source == "sketch")
                    throw std::runtime_error("surface_loft " + role + " repeats curve " +
                                             std::to_string(id) +
                                             "; every section must name a different sketch");
                surface_loft_reject(details, "section", index, sections[index], "repeated_geometry",
                                    PRO_TK_NO_ERROR,
                                    input.source + " " + std::to_string(id) +
                                        " already sits in an earlier section",
                                    "every section must name different geometry");
            }
            if (input.type == PRO_CURVE)
                curve_ids.push_back(id);
        }
        if (input.source == "point" && ++point_sections > 1)
            surface_loft_reject(details, "section", index, sections[index], "second_point",
                                PRO_TK_NO_ERROR, "a loft accepts one convergence point",
                                "keep a point at one end only; the other end needs a curve or "
                                "edge section");
        section_inputs.push_back(std::move(input));
    }

    // FEAT-065/M2: guides are the second direction. Probbl.h lists
    // PRO_E_BNBLN_2DIR as an array of chain holders exactly like 1DIR, so each
    // guide is one sketch and one holder; whether the curves actually cross
    // every section is the kernel's decision, not a guess made here. Measured
    // 2026-11-11 on Creo 12.4.0.0: one holder creates but never regenerates,
    // two holders build a quilt whose geometry follows the guide curves.
    // FEAT-065/M3: a guide may also be one curve or edge id, never a point.
    std::vector<SurfaceLoftInput> guide_inputs;
    std::vector<int> guide_curve_ids;
    std::set<int> seen_guides;
    if (has_guides) {
        const J &guides = op["guides"];
        if (!guides.is_array())
            throw std::runtime_error("surface_loft guides must be a list of sketch labels or ids");
        if (guides.size() < 2)
            throw std::runtime_error(
                "surface_loft guides are a second direction and need at least two guide "
                "sketches; a single 2DIR curve creates a feature that does not regenerate");
        if (guides.size() > SURFACE_LOFT_GUIDE_LIMIT)
            throw std::runtime_error("surface_loft accepts at most " +
                                     std::to_string(SURFACE_LOFT_GUIDE_LIMIT) +
                                     " guides; a second direction is meant to be a few curves");
        for (size_t index = 0; index < guides.size(); index++) {
            std::string role = "guide " + std::to_string((int)index + 1);
            if (!guides[index].is_object() && !seen_guides.insert(feature_id(guides[index])).second)
                throw std::runtime_error("surface_loft " + role +
                                         " repeats a guide sketch; every guide must be a "
                                         "different sketch");
            SurfaceLoftInput input =
                surface_loft_input(guides[index], "guide", index, guides.size(), details);
            // One guide is one direction curve: a two-curve closed profile is a
            // section shape, not a longitudinal guide, and is refused rather
            // than handed to the kernel as an unproved chain.
            if (input.source == "sketch" && input.ids.size() != 1)
                throw std::runtime_error(
                    "surface_loft " + role +
                    " must own exactly one non-composite curve; a guide is one curve "
                    "crossing the sections, not a closed profile");
            for (int id : input.ids) {
                if (!used_items.insert({(int)input.type, id}).second) {
                    if (input.source == "sketch" &&
                        curve_ids.end() != std::find(curve_ids.begin(), curve_ids.end(), id))
                        throw std::runtime_error("surface_loft " + role + " reuses curve " +
                                                 std::to_string(id) +
                                                 " as a section; a guide must be its own curve");
                    surface_loft_reject(details, "guide", index, guides[index], "repeated_geometry",
                                        PRO_TK_NO_ERROR,
                                        input.source + " " + std::to_string(id) +
                                            " already sits in a section or an earlier guide",
                                        "a guide must be its own curve or edge");
                }
                if (input.type == PRO_CURVE)
                    guide_curve_ids.push_back(id);
            }
            guide_inputs.push_back(std::move(input));
        }
    }

    // Receipt: per-slot source kinds and the geometry ids actually placed in
    // each holder. section_curve_ids/guide_curve_ids keep their M1/M2 meaning
    // (PRO_CURVE ids only), so an edge or point never masquerades as a curve.
    J curve_json = J::array();
    for (int curve_id : curve_ids)
        curve_json.push_back(curve_id);
    J guide_json = J::array();
    for (int curve_id : guide_curve_ids)
        guide_json.push_back(curve_id);
    std::set<std::string> unverified;
    J convergence = nullptr;
    auto describe = [&unverified, &convergence](const std::vector<SurfaceLoftInput> &inputs,
                                                bool section, J &kinds, J &ids, J &records) {
        kinds = J::array();
        ids = J::array();
        records = J::array();
        for (size_t index = 0; index < inputs.size(); index++) {
            const SurfaceLoftInput &input = inputs[index];
            kinds.push_back(input.source);
            ids.push_back(input.ids);
            J record = input.record;
            record["index"] = (int)index;
            records.push_back(record);
            if (input.source != "sketch")
                unverified.insert(input.source);
            if (section && input.source == "point")
                convergence = {{"section_index", (int)index},
                               {"position", index == 0 ? "start" : "end"},
                               {"point_id", input.ids.front()},
                               {"point_mm", input.record["point_mm"]},
                               {"chain_instruction", "PRO_CURVCOLL_ADD_POINT_INSTR"},
                               {"live_verified", false},
                               {"note", "a point in a boundary-blend chain holder is not "
                                        "documented in Probbl.h; unproven on Creo 12.4"}};
        }
    };
    J section_kinds, section_ids, section_records, guide_kinds, guide_ids, guide_records;
    describe(section_inputs, true, section_kinds, section_ids, section_records);
    describe(guide_inputs, false, guide_kinds, guide_ids, guide_records);
    std::string unverified_text;
    J unverified_json = J::array();
    for (const auto &form : unverified) {
        unverified_text += (unverified_text.empty() ? "" : ",") + form;
        unverified_json.push_back(form);
    }
    const std::string unverified_note = unverified_text.empty()
                                            ? std::string()
                                            : "; unverified input forms: " + unverified_text +
                                                  " (FEAT-065 M3, no Creo 12.4 live evidence yet)";
    details.update({{"section_count", (int)section_inputs.size()},
                    {"section_curve_ids", curve_json},
                    {"section_source_kinds", section_kinds},
                    {"section_geometry_ids", section_ids},
                    {"section_sources", section_records},
                    {"piecewise_ruled", section_inputs.size() == 2},
                    {"guide_count", (int)guide_inputs.size()},
                    {"guide_curve_ids", guide_json},
                    {"guide_source_kinds", guide_kinds},
                    {"guide_geometry_ids", guide_ids},
                    {"guide_sources", guide_records},
                    {"convergence_point", convergence},
                    {"unverified_input_forms", unverified_json}});

    // FEAT-065/M4: refused shapes and non-edge boundaries stop here, before
    // any feature exists. The TAN_COND sample is published whenever a
    // condition was asked for or an edge feeds the loft (the edge-bridging
    // case T2b compares against a reference part); sketch lofts keep their
    // receipt unchanged.
    const std::vector<SurfaceLoftCondition> conditions =
        surface_loft_conditions(op, section_inputs, guide_inputs, details);
    bool publish_tan_cond = !conditions.empty();
    for (const auto *inputs : {&section_inputs, &guide_inputs})
        for (const auto &input : *inputs)
            publish_tan_cond = publish_tan_cond || input.source == "edge";

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    integer(root, PRO_E_DTM_SRF_TYPE, PRO_E_DTM_SRF_TYPE_BND_BLEND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProElement curves = node(root, PRO_E_BNBLN_CURVES);
    ProElement direction = node(curves, PRO_E_BNBLN_1DIR);
    ProElement holders = node(direction, PRO_E_BNBLN_DIR_CURVES);
    for (const auto &input : section_inputs)
        surface_loft_chain(holders, input, details);
    if (!guide_inputs.empty()) {
        ProElement direction2 = node(curves, PRO_E_BNBLN_2DIR);
        ProElement gholders = node(direction2, PRO_E_BNBLN_DIR_CURVES);
        for (const auto &input : guide_inputs)
            surface_loft_chain(gholders, input, details);
    }

    // INCOMPLETE lets the kernel fill the defaults it owns; the extracted tree
    // is then the completed tree for ProFeatureWithoptionsRedefine. A failed
    // create keeps its element-error list in the receipt instead of only in
    // native.log.
    ProModelitem item;
    CK(ProMdlToModelitem(board, &item));
    ProSelection solid_selection = nullptr;
    CK(ProSelectionAlloc(nullptr, &item, &solid_selection));
    ProFeatureCreateOptions *options = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&options));
    options[0] = PRO_FEAT_CR_INCOMPLETE_FEAT;
    ProFeature feature = {};
    ProErrorlist element_errors = {};
    ProError created = ProFeatureWithoptionsCreate(solid_selection, root, options,
                                                   PRO_REGEN_NO_FLAGS, &feature, &element_errors);
    errors(element_errors);
    ProArrayFree((ProArray *)&options);
    ProSelectionFree(&solid_selection);
    details["create_code"] = (int)created;
    details["create_element_errors"] = {{"total", element_errors.error_number},
                                        {"sample", J::array({})}};
    J create_sample = J::array();
    for (int index = 0; index < element_errors.error_number && index < FEATURE_ERROR_SAMPLE_LIMIT;
         index++)
        create_sample.push_back({{"element", element_errors.error_list[index].err_item_id},
                                 {"type", element_errors.error_list[index].err_item_type},
                                 {"error", element_errors.error_list[index].error}});
    details["create_element_errors"]["sample"] = create_sample;
    if (created != PRO_TK_NO_ERROR) {
        last_feature_error_report =
            feature_error_report("ProFeatureWithoptionsCreate", created, "surface_loft_create");
        stage_operation_result(details);
        std::string listed;
        for (size_t index = 0; index < curve_ids.size(); index++)
            listed += (index ? ", " : "") + std::to_string(curve_ids[index]);
        throw std::runtime_error("surface_loft boundary blend create failed (code " +
                                 std::to_string((int)created) +
                                 ", sections=" + std::to_string((int)curve_ids.size()) +
                                 ", section_curve_ids=[" + listed + "])" + unverified_note);
    }
    ProElementFree(&root);

    ProElement extracted = nullptr;
    ProError extract_code =
        ProFeatureElemtreeExtract(&feature, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &extracted);
    details["extract_code"] = (int)extract_code;
    if (extract_code || !extracted) {
        stage_operation_result(details);
        throw std::runtime_error("surface_loft cannot extract the created feature tree (code " +
                                 std::to_string((int)extract_code) + ")");
    }
    // The tree is logged in full and kept in the receipt only when the
    // regeneration fails; a successful job must not carry a 30 KB element tree
    // that inflates every poll of its result.
    J tree_json = loft_tree_json(extracted);
    log("SURFACE_LOFT_TREE=%s\n", tree_json.dump().c_str());
    details["tree_elements_read"] = tree_json["elements_read"];
    J tan_cond_tree = surface_loft_tan_cond_json(extracted);
    if (publish_tan_cond)
        details["tan_cond_tree"] = tan_cond_tree;

    // FEAT-065/M4: written into the extracted tree only, never into the
    // creation tree (the 2026-11-01 probe stayed UNREGENERATED that way). An
    // unmapped condition is refused here, before redefine; the job rollback
    // then discards the incomplete feature like every other failure below.
    try {
        surface_loft_apply_conditions(extracted, conditions, details);
    } catch (...) {
        details["tan_cond_tree"] = tan_cond_tree;
        stage_operation_result(details);
        CK(ProFeatureElemtreeFree(&feature, extracted));
        throw;
    }

    // The extracted tree is completed by the kernel's own defaults; redefining
    // with it is the regeneration the incomplete create skipped. A failure here
    // keeps the tree sample so the missing element is visible.
    try {
        redefine(&feature, extracted);
    } catch (...) {
        details["extracted_tree"] = tree_json;
        details["tan_cond_tree"] = tan_cond_tree;
        stage_operation_result(details);
        CK(ProFeatureElemtreeFree(&feature, extracted));
        throw;
    }
    CK(ProFeatureElemtreeFree(&feature, extracted));

    ProFeatStatus status = PRO_FEAT_ACTIVE;
    CK(ProFeatureStatusGet(&feature, &status));
    details["feature_id"] = (int)feature.id;
    details["feature_status"] = (int)status;
    ProFeattype feature_type = 0;
    CK(ProFeatureTypeGet(&feature, &feature_type));
    details["feature_type"] = (int)feature_type;

    J quilts = J::array();
    ProError quilt_visit =
        ProFeatureGeomitemVisit(&feature, PRO_QUILT, collect_geom_ids, nullptr, &quilts);
    details["quilt_visit_code"] = (int)quilt_visit;
    details["quilt_count"] = (int)quilts.size();
    details["quilt_ids"] = quilts;
    int quilt_id = quilts.size() == 1 ? quilts[0]["id"].get<int>() : -1;
    details["quilt_id"] = quilt_id < 0 ? J(nullptr) : J(quilt_id);

    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    MeasurementOutcome area, closed;
    if (quilt_id >= 0) {
        ProQuilt quilt = nullptr;
        ProError init_code = ProQuiltInit((ProSolid)board, quilt_id, &quilt);
        details["quilt_init_code"] = (int)init_code;
        if (!init_code) {
            area = quilt_area_native(quilt);
            closed = quilt_closed_native(quilt);
        } else {
            area.reason = "quilt_init_failed";
            area.query_code = init_code;
            closed.reason = "quilt_init_failed";
            closed.query_code = init_code;
        }
    } else {
        area.reason = "quilt_geometry_missing";
        closed.reason = "quilt_geometry_missing";
    }
    details.update(area_fields_json(area, units, scale, "surface_area_mm2", "surface_area_status"));
    const char *closure = quilt_closed_is_open(closed) ? "open"
                          : closed.available           ? "closed"
                                                       : "unknown";
    details["quilt_closed_native"] = closure;
    details["closure"] = {{"available", closed.available},
                          {"query_code", (int)closed.query_code},
                          {"reason", closed.reason ? J(closed.reason) : J(nullptr)}};
    // FEAT-039/H04: the quilt's own faces are a group too, so the boundary
    // measurement is published beside the boolean closure probe. A single
    // boundary-blend quilt reports its exposed edges; the seam fields stay
    // null with a reason instead of a fabricated zero.
    details["surface_group"] =
        quilt_id >= 0 ? surface_group_receipt({quilt_id}, 0.01, 1.0) : J(nullptr);
    details["has_solid"] = inspection(false)["has_solid"];
    details["surface_type"] =
        feature_type == PRO_FEAT_DATUM_SURF ? J("datum_surface") : J("unknown");
    stage_operation_result(details);

    if (status != PRO_FEAT_ACTIVE) {
        details["extracted_tree"] = tree_json;
        details["tan_cond_tree"] = tan_cond_tree;
        stage_operation_result(details);
        last_feature_error_report = feature_error_report("ProFeatureStatusGet", (ProError)status,
                                                         "surface_loft_regeneration");
        throw std::runtime_error(
            "surface_loft boundary blend regeneration failed (feature_status=" +
            std::to_string((int)status) + ", feature_id=" + std::to_string((int)feature.id) +
            ", quilt_count=" + std::to_string((int)quilts.size()) +
            "); the created tree did not produce a regenerated surface" + unverified_note);
    }
    if (feature_type != PRO_FEAT_DATUM_SURF)
        throw std::runtime_error("surface_loft produced feature type " +
                                 std::to_string((int)feature_type) + " instead of a datum surface");
    if (quilts.size() != 1)
        throw std::runtime_error("surface_loft produced " + std::to_string((int)quilts.size()) +
                                 " quilt geometry items (visit code " +
                                 std::to_string((int)quilt_visit) +
                                 "); exactly one boundary-blend surface is required");
    if (!area.available)
        throw std::runtime_error(std::string("surface_loft surface is not measurable") +
                                 (area.reason ? ": " : "") + (area.reason ? area.reason : ""));
    if (details["has_solid"].get<bool>())
        throw std::runtime_error("surface_loft created solid material; a surface loft must not");
    if (!quilt_closed_is_open(closed))
        throw std::runtime_error(
            "surface_loft result must be an open quilt; ProQuiltVolumeEval reported " +
            std::string(closure) + " (code " + std::to_string((int)closed.query_code) + ")");

    remember(op, feature, {{"quilt_id", quilt_id}, {"section_curve_ids", curve_json}});
}
#else
static void generic_surface_loft(const J &op) {
    (void)op;
    throw std::runtime_error(
        "SURFACE_LOFT_SDK_UNAVAILABLE: surface_loft requires Probbl.h; this Creo Toolkit "
        "SDK does not provide the boundary-blend element tree. No feature was created");
}
#endif
