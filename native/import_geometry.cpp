// import_geometry.cpp — BUG-124/C1: import one STEP or IGES file into its own
// new part.
//
// The documented entry point (ProIntfimport.h) creates a model, so this route
// is the model-creation step of a new plan, not a feature appended to an
// existing model: generic.cpp calls import_geometry_create() where the plain
// new-part path would copy the part template, and the operation dispatch only
// republishes the receipt the import measured. Nothing here fabricates a
// value: an unmeasured area or closure is published with its status and code.
//
// Included by generic.cpp after the shared geometry, measurement and unit
// helpers are visible.

#include <ProIntfimport.h>

#include <filesystem>
#include <set>
#include <string>

namespace {

struct ImportGeometryState {
    bool attempted = false;
    J receipt = J::object();
};

} // namespace

// One job at a time, exactly like the other job-scoped evidence blocks.
static ImportGeometryState import_geometry_state;
static constexpr size_t IMPORT_MODEL_NAME_LIMIT = 31;

static void import_geometry_reset() {
    import_geometry_state = ImportGeometryState();
}

static ProIntfImportType import_geometry_type(const std::string &format) {
    if (format == "step")
        return PRO_INTF_IMPORT_STEP;
    if (format == "iges")
        return PRO_INTF_IMPORT_IGES;
    throw std::runtime_error("import_geometry format must be 'step' or 'iges'");
}

// The importer's own return codes stay in the receipt by number; the label only
// helps a reader. PRO_TK_NO_LICENSE (-40) is the one a pure-surface import is
// expected to hit first and must never be folded into a generic failure.
static const char *import_geometry_error_label(ProError code) {
    switch (code) {
    case PRO_TK_NO_ERROR:
        return "ok";
    case PRO_TK_NO_LICENSE:
        return "PRO_TK_NO_LICENSE";
    case PRO_TK_UNSUPPORTED:
        return "PRO_TK_UNSUPPORTED";
    case PRO_TK_CANT_OPEN:
        return "PRO_TK_CANT_OPEN";
    case PRO_TK_INVALID_FILE:
        return "PRO_TK_INVALID_FILE";
    case PRO_TK_INVALID_TYPE:
        return "PRO_TK_INVALID_TYPE";
    case PRO_TK_NOT_EXIST:
        return "PRO_TK_NOT_EXIST";
    case PRO_TK_BAD_INPUTS:
        return "PRO_TK_BAD_INPUTS";
    case PRO_TK_E_FOUND:
        return "PRO_TK_E_FOUND";
    case PRO_TK_LINE_TOO_LONG:
        return "PRO_TK_LINE_TOO_LONG";
    default:
        return "other";
    }
}

// The single import operation of a plan, or null when the plan has none. Python
// refuses a mixed or existing-model submission first; the native side re-checks
// because it is the authority on what it will create.
static const J *import_geometry_choice(const J &request) {
    if (!request.contains("operations") || !request["operations"].is_array())
        return nullptr;
    const J *chosen = nullptr;
    for (const auto &op : request["operations"]) {
        if (op.value("op", "") != "import_geometry")
            continue;
        if (chosen)
            throw std::runtime_error(
                "import_geometry may appear only once in a plan; no job was created");
        chosen = &op;
    }
    if (!chosen)
        return nullptr;
    if (request["operations"].size() != 1)
        throw std::runtime_error(
            "import_geometry must be the only operation of its plan: the import call creates "
            "the model, so nothing can run before it and no label exists for anything after it");
    return chosen;
}

struct ImportGeometryScan {
    int feature_count = 0;
    std::set<int> quilt_ids;
};

// Feature visit: count the imported features and union their quilt ids. A quilt
// is an id in one namespace with surfaces (quilt_query.h), so the set also
// removes duplicates a nested feature could report twice.
static ProError import_geometry_feature_cb(ProFeature *feature, ProError status, ProAppData data) {
    auto *scan = static_cast<ImportGeometryScan *>(data);
    if (status)
        return PRO_TK_NO_ERROR;
    scan->feature_count++;
    J quilts = J::array();
    if (!ProFeatureGeomitemVisit(feature, PRO_QUILT, collect_geom_ids, nullptr, &quilts))
        for (const auto &item : quilts)
            if (item.contains("id") && item["id"].is_number_integer())
                scan->quilt_ids.insert(item["id"].get<int>());
    return PRO_TK_NO_ERROR;
}

// Hashes the inputs it was given, imports, and measures what the import
// produced. Throws with the importer's own code in the message on any failure,
// so a licence refusal reaches the caller as PRO_TK_NO_LICENSE and not as a
// generic error.
static ProMdl import_geometry_create(const J &op, const std::wstring &model_name, J &report) {
    import_geometry_state = ImportGeometryState();
    import_geometry_state.attempted = true;
    const std::string file = op.at("file").get<std::string>();
    const bool has_profile = op.contains("profile") && !op["profile"].is_null();
    const std::string profile = has_profile ? op["profile"].get<std::string>() : std::string();
    const std::string format = op.value("format", "step");
    J details = {{"op", "import_geometry"},
                 {"file", file},
                 {"format", format},
                 {"declared_file_sha256", op.value("file_sha256", "")},
                 // A profile stays valid for the whole Creo session once set, so the
                 // receipt says whether this job set one or rode the session default.
                 {"profile_source", has_profile ? "explicit" : "creo_default"},
                 {"profile", has_profile ? J{{"path", profile},
                                             {"declared_sha256", op.value("profile_sha256", "")}}
                                         : J(nullptr)},
                 {"rep_type", "PRO_IMPORTREP_MASTER"},
                 {"create_type", "PRO_MDL_UNUSED"}};
    if (model_name.size() > IMPORT_MODEL_NAME_LIMIT)
        throw std::runtime_error(
            "import_geometry model name is longer than 31 characters, which the documented "
            "importer reports as PRO_TK_LINE_TOO_LONG; shorten the model name before import");
    const std::filesystem::path file_path(wide(file));
    const std::filesystem::path profile_path(wide(profile));
    if (!std::filesystem::is_regular_file(file_path))
        throw std::runtime_error("import_geometry input is missing at execution time: " + file +
                                 "; nothing was imported");
    if (has_profile && !std::filesystem::is_regular_file(profile_path))
        throw std::runtime_error("import_geometry profile is missing at execution time: " +
                                 profile + "; nothing was imported");
    // The digests are re-read here, not trusted from the request: a file swapped
    // between submission and execution fails instead of being imported silently.
    const std::string file_digest = mechdog_callback::sha256(file_path);
    const std::string profile_digest = has_profile ? mechdog_callback::sha256(profile_path) : "";
    const std::string declared_file = op.value("file_sha256", "");
    const std::string declared_profile = op.value("profile_sha256", "");
    if ((!declared_file.empty() && declared_file != file_digest) ||
        (has_profile && !declared_profile.empty() && declared_profile != profile_digest))
        throw std::runtime_error(
            "IMPORT_GEOMETRY_INPUT_CHANGED: the import file or profile changed after the plan "
            "was validated (file " +
            file_digest + ", profile " + (has_profile ? profile_digest : std::string("none")) +
            "); nothing was imported, resubmit with the current files");
    ProPath import_file = {}, profile_file = {};
    path(import_file, wide(file));
    if (has_profile)
        path(profile_file, wide(profile));
    ProMdlName name = {};
    wcscpy_s(name, model_name.c_str());
    ProMdl created = nullptr;
    const ProError code = ProIntfimportModelWithOptionsMdlnameCreate(
        import_file, has_profile ? profile_file : nullptr, import_geometry_type(format),
        PRO_MDL_UNUSED, PRO_IMPORTREP_MASTER, name, nullptr, nullptr, &created);
    details["create_code"] = (int)code;
    details["create_code_name"] = import_geometry_error_label(code);
    if (code != PRO_TK_NO_ERROR || created == nullptr)
        throw std::runtime_error(
            "import_geometry failed: ProIntfimportModelWithOptionsMdlnameCreate returned " +
            std::to_string((int)code) + " (" + import_geometry_error_label(code) +
            ") for the requested " + format + " import; the job rolls back");
    ProMdlType model_type = PRO_MDL_UNUSED;
    const ProError type_code = ProMdlTypeGet(created, &model_type);
    details["model_type_code"] = (int)type_code;
    details["model_type"] = (int)model_type;
    const InspectionLengthUnits units = inspect_length_units(created);
    const MillimeterScale scale = length_scale_to_mm(created, units);
    details["units"] = {{"name", units.length.name[0] ? J(utf8(units.length.name)) : J(nullptr)},
                        {"scale_to_mm_known", scale.known}};
    ImportGeometryScan scan;
    ProError visit_code = PRO_TK_NO_ERROR;
    if (model_type == PRO_MDL_PART)
        visit_code =
            ProSolidFeatVisit((ProSolid)created, import_geometry_feature_cb, nullptr, &scan);
    details["feature_visit_code"] = (int)visit_code;
    details["feature_count"] = scan.feature_count;
    details["quilt_count"] = (int)scan.quilt_ids.size();
    J quilt_ids = J::array();
    for (int id : scan.quilt_ids)
        quilt_ids.push_back(id);
    details["quilt_ids"] = quilt_ids;
    // Area is the sum of the imported quilts' trimmed face areas; one failed quilt
    // makes the whole sum unavailable instead of a partial total presented as the
    // model's area. Closure is only meaningful for a single quilt.
    MeasurementOutcome area;
    area.reason = "no_quilt_in_imported_model";
    const char *closure = "unknown";
    if (!scan.quilt_ids.empty()) {
        double total = 0.0;
        bool measured = true;
        ProError failed = PRO_TK_NO_ERROR;
        for (int id : scan.quilt_ids) {
            ProQuilt quilt = nullptr;
            const ProError init_code = ProQuiltInit((ProSolid)created, id, &quilt);
            if (init_code) {
                measured = false;
                failed = init_code;
                break;
            }
            const MeasurementOutcome per_quilt = quilt_area_native(quilt);
            if (!per_quilt.available) {
                measured = false;
                failed = per_quilt.query_code;
                break;
            }
            total += per_quilt.value;
        }
        if (measured) {
            area.available = true;
            area.value = total;
            area.reason = nullptr;
        } else {
            area.query_code = failed;
            area.reason = "quilt_area_unavailable";
        }
        if (scan.quilt_ids.size() == 1) {
            ProQuilt quilt = nullptr;
            if (!ProQuiltInit((ProSolid)created, *scan.quilt_ids.begin(), &quilt)) {
                const MeasurementOutcome closed = quilt_closed_native(quilt);
                closure = quilt_closed_is_open(closed) ? "open"
                          : closed.available           ? "closed"
                                                       : "unknown";
            }
        }
    }
    details["quilt_closure"] = closure;
    details.update(area_fields_json(area, units, scale, "area_mm2", "area_status"));
    details["created_model_name"] = utf8(model_name);
    import_geometry_state.receipt = details;
    report["import_geometry"] = details;
    return created;
}

// Dispatch: the model and its receipt already exist, so the operation only
// republishes them. Reaching here without an import means the plan tried to
// append an import to an existing model, which the importer cannot do.
static void generic_import_geometry(const J &op) {
    (void)op;
    if (!import_geometry_state.attempted)
        throw std::runtime_error(
            "import_geometry creates its own new part: submit it as the only operation of a new "
            "plan (no model_id) instead of appending it to an existing model");
    stage_operation_result(import_geometry_state.receipt);
}
