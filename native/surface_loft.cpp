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

static J loft_element_json(ProElement element, int depth, int &budget) {
    J record = J::object();
    if (!element || budget <= 0)
        return record;
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
    if (depth < 12 && budget > 0) {
        ProElement *children = nullptr;
        ProArrayAlloc(0, sizeof(ProElement), 1, (ProArray *)&children);
        ProError code = array == PRO_B_TRUE ? ProElementArrayGet(element, nullptr, &children)
                                            : ProElementChildrenGet(element, nullptr, &children);
        int count = 0;
        if (!code)
            ProArraySizeGet((ProArray)children, &count);
        if (count > 0) {
            J items = J::array();
            for (int index = 0; index < count && budget > 0; index++)
                items.push_back(loft_element_json(children[index], depth + 1, budget));
            record["children"] = items;
        }
        if (children)
            ProArrayFree((ProArray *)&children);
    }
    return record;
}

static J loft_tree_json(ProElement root) {
    int budget = SURFACE_LOFT_TREE_SAMPLE_LIMIT;
    return {{"limit", SURFACE_LOFT_TREE_SAMPLE_LIMIT},
            {"truncated", false},
            {"root", loft_element_json(root, 0, budget)},
            {"elements_read", SURFACE_LOFT_TREE_SAMPLE_LIMIT - budget}};
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

    std::vector<std::vector<int>> section_curves;
    std::vector<int> curve_ids;
    std::set<int> seen_curves;
    for (size_t index = 0; index < sections.size(); index++) {
        std::string role = "section " + std::to_string((int)index + 1);
        std::vector<int> curves = surface_loft_curves(sections[index], role.c_str());
        for (int curve : curves) {
            if (!seen_curves.insert(curve).second)
                throw std::runtime_error("surface_loft " + role + " repeats curve " +
                                         std::to_string(curve) +
                                         "; every section must name a different sketch");
            curve_ids.push_back(curve);
        }
        section_curves.push_back(curves);
    }

    // FEAT-065/M2: guides are the second direction. Probbl.h lists
    // PRO_E_BNBLN_2DIR as an array of chain holders exactly like 1DIR, so each
    // guide is one sketch and one holder; whether the curves actually cross
    // every section is the kernel's decision, not a guess made here. Measured
    // 2026-11-11 on Creo 12.4.0.0: one holder creates but never regenerates,
    // two holders build a quilt whose geometry follows the guide curves.
    std::vector<std::vector<int>> guide_curves;
    std::vector<int> guide_curve_ids;
    std::set<int> seen_guides;
    // An empty list is the schema default, i.e. "no second direction"; it must
    // stay a plain single-direction blend rather than a one-guide request.
    const bool has_guides = op.contains("guides") && !op["guides"].is_null() &&
                            (!op["guides"].is_array() || !op["guides"].empty());
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
            if (!seen_guides.insert(feature_id(guides[index])).second)
                throw std::runtime_error("surface_loft " + role +
                                         " repeats a guide sketch; every guide must be a "
                                         "different sketch");
            std::vector<int> curves = surface_loft_curves(guides[index], role.c_str());
            // One guide is one direction curve: a two-curve closed profile is a
            // section shape, not a longitudinal guide, and is refused rather
            // than handed to the kernel as an unproved chain.
            if (curves.size() != 1)
                throw std::runtime_error(
                    "surface_loft " + role +
                    " must own exactly one non-composite curve; a guide is one curve "
                    "crossing the sections, not a closed profile");
            for (int curve : curves) {
                if (curve_ids.end() != std::find(curve_ids.begin(), curve_ids.end(), curve))
                    throw std::runtime_error("surface_loft " + role + " reuses curve " +
                                             std::to_string(curve) +
                                             " as a section; a guide must be its own curve");
                guide_curve_ids.push_back(curve);
            }
            guide_curves.push_back(curves);
        }
    }

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    integer(root, PRO_E_DTM_SRF_TYPE, PRO_E_DTM_SRF_TYPE_BND_BLEND);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProElement curves = node(root, PRO_E_BNBLN_CURVES);
    ProElement direction = node(curves, PRO_E_BNBLN_1DIR);
    ProElement holders = node(direction, PRO_E_BNBLN_DIR_CURVES);
    for (auto &curves : section_curves) {
        ProElement holder = node(holders, PRO_E_STD_CHAIN_HOLDER);
        J refs = J::array();
        for (int curve_id : curves)
            refs.push_back({{"kind", "curve"}, {"id", curve_id}});
        curve_collection(node(holder, PRO_E_STD_CURVE_COLLECTION_APPL), refs);
    }
    if (!guide_curves.empty()) {
        ProElement direction2 = node(curves, PRO_E_BNBLN_2DIR);
        ProElement gholders = node(direction2, PRO_E_BNBLN_DIR_CURVES);
        for (auto &guide : guide_curves) {
            ProElement holder = node(gholders, PRO_E_STD_CHAIN_HOLDER);
            J refs = J::array();
            for (int curve_id : guide)
                refs.push_back({{"kind", "curve"}, {"id", curve_id}});
            curve_collection(node(holder, PRO_E_STD_CURVE_COLLECTION_APPL), refs);
        }
    }

    J curve_json = J::array();
    for (int curve_id : curve_ids)
        curve_json.push_back(curve_id);
    J guide_json = J::array();
    for (int curve_id : guide_curve_ids)
        guide_json.push_back(curve_id);
    J details = {{"op", "surface_loft"},
                 {"sections", sections},
                 {"section_count", (int)section_curves.size()},
                 {"section_curve_ids", curve_json},
                 {"piecewise_ruled", section_curves.size() == 2},
                 {"interpolation", interpolation},
                 {"guides", has_guides ? op["guides"] : J::array()},
                 {"guide_count", (int)guide_curves.size()},
                 {"guide_curve_ids", guide_json},
                 {"route", "probbl_boundary_blend"}};

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
                                 ", section_curve_ids=[" + listed + "])");
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

    // The extracted tree is completed by the kernel's own defaults; redefining
    // with it is the regeneration the incomplete create skipped. A failure here
    // keeps the tree sample so the missing element is visible.
    try {
        redefine(&feature, extracted);
    } catch (...) {
        details["extracted_tree"] = tree_json;
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
        stage_operation_result(details);
        last_feature_error_report = feature_error_report("ProFeatureStatusGet", (ProError)status,
                                                         "surface_loft_regeneration");
        throw std::runtime_error(
            "surface_loft boundary blend regeneration failed (feature_status=" +
            std::to_string((int)status) + ", feature_id=" + std::to_string((int)feature.id) +
            ", quilt_count=" + std::to_string((int)quilts.size()) +
            "); the created tree did not produce a regenerated surface");
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
