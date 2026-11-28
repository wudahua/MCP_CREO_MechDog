#include <ProDtmCsys.h>
#include <ProDtmPnt.h>
#include <ProFlatsrf.h>
#include <ProThicken.h>
#include <ProSolidify.h>
#include <ProBooleanBodies.h>
#include <ProRib.h>
#include <ProCsys.h>
#include <ProPoint.h>

#include <cmath>

#include "quilt_gauge_guard.h"

static void generic_csys(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_CSYS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProSelection s = resolve(op.value("reference", J{{"kind", "default_csys"}}));
    ref(node(node(root, PRO_E_CSYS_ORIGIN_CONSTRS), PRO_E_CSYS_ORIGIN_CONSTR),
        PRO_E_CSYS_ORIGIN_CONSTR_REF, s);
    ProSelectionFree(&s);
    integer(root, PRO_E_CSYS_OFFSET_TYPE, PRO_CSYS_OFFSET_CARTESIAN);
    integer(root, PRO_E_CSYS_ORIENT_BY_METHOD, PRO_CSYS_ORIENT_BY_SEL_CSYS_AXES);
    ProElement moves = node(root, PRO_E_CSYS_ORIENTMOVES);
    for (int step = 0; step < 6; step++) {
        int i = (step + 3) % 6;
        ProElement move = node(moves, PRO_E_CSYS_ORIENTMOVE);
        integer(move, PRO_E_CSYS_ORIENTMOVE_MOVE_TYPE, i);
        real(move, PRO_E_CSYS_ORIENTMOVE_MOVE_VAL, op[i < 3 ? "translation" : "rotation"][i % 3]);
    }
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
    J ids = J::array();
    CK(ProFeatureGeomitemVisit(&f, PRO_CSYS, collect_geom_ids, nullptr, &ids));
    if (ids.size() != 1)
        throw std::runtime_error("Coordinate system geometry missing");
    ProCsys cs;
    CK(ProCsysInit((ProSolid)board, ids[0]["id"], &cs));
    ProGeomitemdata *data = nullptr;
    CK(ProCsysDataGet(cs, &data));
    auto c = data->data.p_csys_data;
    stage_operation_result({{"op", "datum_csys"},
                            {"origin", xyz(c->origin)},
                            {"x_axis", xyz(c->x_vector)},
                            {"y_axis", xyz(c->y_vector)},
                            {"z_axis", xyz(c->z_vector)}});
    ProGeomitemdataFree(&data);
}
static void generic_points(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_POINT);
    integer(root, PRO_E_DPOINT_TYPE, PRO_DPOINT_TYPE_OFFSET_CSYS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_DPOINT_OFST_CSYS_TYPE, PRO_DTMPNT_OFFCSYS_CARTESIAN);
    integer(root, PRO_E_DPOINT_OFST_CSYS_WITH_DIMS, PRO_B_TRUE);
    ProSelection s = resolve(op.value("reference", J{{"kind", "default_csys"}}));
    ref(root, PRO_E_DPOINT_OFST_CSYS_REF, s);
    ProSelectionFree(&s);
    ProElement points = node(root, PRO_E_DPOINT_OFST_CSYS_PNTS_ARRAY);
    for (auto point : op["points"]) {
        ProElement p = node(points, PRO_E_DPOINT_OFST_CSYS_PNT);
        text(p, PRO_E_DPOINT_OFST_CSYS_PNT_NAME, wide(point["name"]).c_str());
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR1_VAL, point["position"][0]);
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR2_VAL, point["position"][1]);
        real(p, PRO_E_DPOINT_OFST_CSYS_DIR3_VAL, point["position"][2]);
    }
    ProFeature f = create(root);
    ProElementFree(&root);
    remember(op, f);
}
static int verified_feature_quilt(ProFeature &f) {
    J ids = J::array();
    if (ProFeatureGeomitemVisit(&f, PRO_QUILT, collect_geom_ids, nullptr, &ids) !=
            PRO_TK_NO_ERROR ||
        ids.size() != 1 || !ids[0]["id"].is_number_integer())
        return -1;
    int id = ids[0]["id"].get<int>();
    ProQuilt quilt = nullptr;
    if (id < 0 || ProQuiltInit((ProSolid)board, id, &quilt) != PRO_TK_NO_ERROR || !quilt)
        return -1;
    return id;
}
static ProSelection solidify_quilt_selection(const J &reference) {
    if (reference.at("kind") != "quilt_feature")
        return resolve(reference);
    std::string label = reference.at("label").get<std::string>();
    const J *entry = alias_entry(label);
    if (!entry)
        return resolve(reference);
    std::string result_op = entry->value("op", std::string());
    if (result_op != "quilt_merge" && result_op != "mirror" && result_op != "surface_trim")
        return resolve(reference);

    auto units = inspect_length_units(board);
    auto scale = length_scale_to_mm(board, units);
    auto verified_selection = [&](int id) {
        ProQuilt quilt = nullptr;
        if (id < 0 || ProQuiltInit((ProSolid)board, id, &quilt) != PRO_TK_NO_ERROR || !quilt)
            throw std::runtime_error("Solidify result label '" + label + "' recorded quilt id " +
                                     std::to_string(id) +
                                     ", but that quilt is not usable in the current model" +
                                     quilt_candidates_hint((ProSolid)board, units, scale));
        return selection(id, PRO_QUILT);
    };

    // Merge and trim remember the quilt actually measured by their native
    // implementation. Never replace that relation with a feature reverse visit:
    // a merge result can still belong to the original target feature.
    const char *id_key = result_op == "surface_trim" ? "result_quilt_id" : "quilt_id";
    auto recorded = entry->find(id_key);
    if (recorded != entry->end() && recorded->is_number_integer())
        return verified_selection(recorded->get<int>());

    // A mirror created earlier in this same atomic plan has not passed through
    // Python closeout yet. Use the kernel's exact feature/quilt membership and
    // accept it only when it names one quilt; bbox and recency play no part.
    if (result_op == "mirror" && entry->at("feature_id").is_number_integer()) {
        int feature_id = entry->at("feature_id").get<int>();
        J collected = collect_model_quilts((ProSolid)board, units, scale);
        std::set<int> matches;
        for (const auto &record : collected["records"]) {
            if (!record["quilt_id"].is_number_integer() || !record["feature_ids"].is_array())
                continue;
            for (const auto &owner : record["feature_ids"])
                if (owner.is_number_integer() && owner.get<int>() == feature_id) {
                    matches.insert(record["quilt_id"].get<int>());
                    break;
                }
        }
        if (matches.size() == 1)
            return verified_selection(*matches.begin());
    }
    throw std::runtime_error("Solidify result label '" + label + "' (" + result_op +
                             ") does not identify exactly one usable result quilt; use the "
                             "operation receipt's quilt_id as {kind:\"quilt\",id:N}" +
                             quilt_candidates_hint((ProSolid)board, units, scale));
}
static void generic_fill(const J &op) {
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_DATUM_SURF);
    integer(root, PRO_E_FEATURE_FORM, PRO_FLAT);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    ProSelection s = selection(feature_id(op["sketch"]), PRO_FEATURE);
    ref(node(root, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, s);
    ProSelectionFree(&s);
    ProFeature f = create(root);
    ProElementFree(&root);
    J details = {{"feature_id", (int)f.id}};
    int quilt_id = verified_feature_quilt(f);
    if (quilt_id >= 0) {
        details["quilt_id"] = quilt_id;
        remember(op, f, {{"quilt_id", quilt_id}});
    } else {
        // Zero/ambiguous/unreadable geometry stays unidentified; never borrow a
        // nearby quilt merely to fill the receipt.
        remember(op, f);
    }
    stage_operation_result(details);
}
static void generic_surface_solid(const J &op) {
    bool thin = op["op"] == "thicken", cut = op.value("mode", "add") == "cut";
    // S06: a quilt becomes a solid only when it is closed. ProQuiltVolumeEval
    // answers for a closed quilt and returns PRO_TK_INVALID_TYPE for an open
    // one, so the closure is measured, not assumed, and an open quilt is
    // refused with that code instead of a bare feature failure.
    ProSelection s = thin ? resolve(op["reference"]) : solidify_quilt_selection(op["reference"]);
    int target_quilt_id = -1;
    J closure = J(nullptr);
    if (!thin && !cut) {
        ProModelitem item;
        CK(ProSelectionModelitemGet(s, &item));
        target_quilt_id = item.id;
        ProQuilt target_quilt = nullptr;
        if (ProQuiltInit((ProSolid)board, target_quilt_id, &target_quilt))
            throw std::runtime_error("solidify could not open the referenced quilt (id " +
                                     std::to_string(target_quilt_id) + ")");
        MeasurementOutcome closed = quilt_closed_native(target_quilt);
        closure = {{"available", closed.available},
                   {"query_code", (int)closed.query_code},
                   {"reason", closed.reason ? J(closed.reason) : J(nullptr)}};
        if (quilt_closed_is_open(closed))
            throw std::runtime_error(
                "solidify requires a closed quilt; the referenced quilt is open "
                "(ProQuiltVolumeEval=" +
                std::to_string((int)closed.query_code) +
                (closed.reason ? std::string(", ") + closed.reason : std::string()) + ")");
    }
    // The volume is the solid's own measure, so it is read after the feature
    // exists. A model without a solid yet has no mass property, and that is
    // reported as unknown instead of zero.
    bool volume_before_known = true;
    double volume_before = 0.0;
    try {
        volume_before = volume();
    } catch (...) {
        volume_before_known = false;
    }
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, cut ? PRO_FEAT_CUT : PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    if (thin)
        integer(root, PRO_E_FEAT_FORM_ALWAYS_THIN, PRO_THIN);
    ref(root, thin ? PRO_E_STD_USEQLT_QLT : PRO_E_PATCH_QUILT, s);
    ProSelectionFree(&s);
    if (thin) {
        real(root, PRO_E_THICKNESS, op["thickness"]);
        std::string side = op["side"];
        integer(root, PRO_E_STD_USEQLT_SIDE,
                side == "symmetric"  ? PRO_THICKEN_BOTH_SIDES
                : side == "positive" ? PRO_THICKEN_SIDE_ONE
                                     : PRO_THICKEN_SIDE_TWO);
        integer(root, PRO_E_SRF_OFFS_METHOD, PRO_OFFS_METH_NORMTOSURF);
    } else
        integer(root, PRO_E_PATCH_MATERIAL_SIDE,
                op["side"] == "positive" ? PRO_SOLIDIFY_SIDE_ONE : PRO_SOLIDIFY_SIDE_TWO);
    body_options(root, op);
    ProFeature f = create(root);
    ProElementFree(&root);
    J extra = {{"target_quilt_id", target_quilt_id >= 0 ? J(target_quilt_id) : J(nullptr)},
               {"closure", closure},
               {"volume_before_mm3", volume_before_known ? J(volume_before) : J(nullptr)}};
    if (!cut) {
        double volume_after = volume();
        extra["volume_after_mm3"] = volume_after;
    }
    // The operation result is what a client reads, so the measured numbers are
    // staged there as well; remember() only feeds the alias table.
    stage_operation_result(extra);
    remember(op, f, extra);
}
// FEAT-039/S07: a controlled offset of a quilt along its surface normal.
// The documented route (ProThicken.h) is a protrusion with the surface form,
// the thin form, the quilt reference, the distance, the normal offset method
// and one explicit side. The offset distance is measured back from the
// result instead of being echoed from the request.
static void generic_surface_offset(const J &op) {
    ProSelection s = resolve(op["reference"]);
    int quilt_id = -1;
    ProModelitem item;
    CK(ProSelectionModelitemGet(s, &item));
    quilt_id = item.id;
    // BUG-112: ProQuiltInit reports its outcome through a code and a handle, so
    // both must agree before the quilt may be measured. A leftover handle after
    // a failed Init would otherwise become a bogus source area and a fabricated
    // finite offset distance.
    ProQuilt quilt = nullptr;
    ProError init_code = ProQuiltInit((ProSolid)board, quilt_id, &quilt);
    bool gauge_ready = quilt_gauge_ready((int)init_code, quilt);
    MeasurementOutcome area;
    QuiltPlanarity planarity;
    if (gauge_ready) {
        area = quilt_area_native(quilt);
        planarity = quilt_planarity_native(quilt);
    }
    double source_area = area.available ? area.value : 0.0;
    bool area_known = area.available;
    // An unavailable area always names why: a failed Init, a successful Init
    // that handed back no handle, or the measurement's own reason.
    const char *area_reason = nullptr;
    if (!area_known) {
        if (!gauge_ready)
            area_reason = init_code ? "quilt_init_failed" : "quilt_handle_missing";
        else
            area_reason = area.reason ? area.reason : "source_area_unavailable";
    }
    J source_area_status = {{"available", area_known},
                            {"init_code", (int)init_code},
                            {"query_code", gauge_ready ? J((int)area.query_code) : J(nullptr)},
                            {"reason", area_reason ? J(area_reason) : J(nullptr)}};
    double volume_before = 0.0;
    bool volume_before_known = true;
    try {
        volume_before = volume();
    } catch (...) {
        volume_before_known = false;
    }
    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_PROTRUSION);
    integer(root, PRO_E_FEATURE_FORM, PRO_USE_SURFS);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_FEAT_FORM_ALWAYS_THIN, PRO_THIN);
    ref(root, PRO_E_STD_USEQLT_QLT, s);
    ProSelectionFree(&s);
    real(root, PRO_E_THICKNESS, op["distance"]);
    integer(root, PRO_E_STD_USEQLT_SIDE,
            op["side"] == "negative" ? PRO_THICKEN_SIDE_TWO : PRO_THICKEN_SIDE_ONE);
    integer(root, PRO_E_SRF_OFFS_METHOD, PRO_OFFS_METH_NORMTOSURF);
    body_options(root, op);
    ProFeature f = create(root);
    ProElementFree(&root);
    double volume_after = volume();
    // FEAT-039/R01: the volume over area ratio is the offset distance only when
    // the part had no solid before the offset and the source is exactly one
    // planar face. An existing solid folds its old volume into the numerator;
    // a curved or multi-face source is not a constant-normal sweep. Both keep
    // the distance null with a named reason instead of publishing a plausible
    // but ungrounded number.
    const bool single_planar_source =
        planarity.visit_ok && planarity.face_count == 1 && planarity.planar_count == 1;
    const bool empty_before = volume_before_known && std::fabs(volume_before) <= 1e-9;
    const bool result_volume_known = std::isfinite(volume_after) && volume_after > 0.0;
    const bool distance_available =
        area_known && single_planar_source && empty_before && result_volume_known;
    const char *distance_reason = nullptr;
    if (!area_known)
        distance_reason = "source_area_unavailable";
    else if (!planarity.visit_ok)
        distance_reason = "source_surface_visit_failed";
    else if (!single_planar_source)
        distance_reason = "source_quilt_not_a_single_plane";
    else if (!volume_before_known)
        distance_reason = "pre_offset_volume_unavailable";
    else if (!empty_before)
        distance_reason = "pre_existing_volume";
    else if (!result_volume_known)
        distance_reason = "result_volume_unavailable";
    const double measured =
        distance_available ? (volume_after - volume_before) / source_area : -1.0;
    J offset_distance_status = {
        {"available", distance_available},
        {"source", distance_available ? J("volume_over_source_area") : J(nullptr)},
        {"query_code", planarity.visit_ok ? J(nullptr) : J((int)planarity.query_code)},
        {"reason", distance_reason ? J(distance_reason) : J(nullptr)}};
    J extra = {{"target_quilt_id", quilt_id},
               {"source_area_mm2", area_known ? J(source_area) : J(nullptr)},
               {"source_area_status", source_area_status},
               {"offset_distance_mm", op["distance"]},
               {"measured_offset_distance_mm", measured >= 0.0 ? J(measured) : J(nullptr)},
               {"offset_distance_status", offset_distance_status},
               {"direction", op["side"]},
               {"offset_method", "normal_to_surface"},
               {"volume_before_mm3", volume_before_known ? J(volume_before) : J(nullptr)},
               {"volume_after_mm3", volume_after}};
    stage_operation_result(extra);
    remember(op, f, extra);
}
static void require_boolean_body(int id) {
    ProSolidBody *list = nullptr;
    int n = 0;
    CK(ProSolidBodiesCollect((ProSolid)board, &list));
    CK(ProArraySizeGet((ProArray)list, &n));
    bool found = false;
    ProSolidBodyState found_state = PRO_BODY_STATE_NONE;
    for (int i = 0; i < n; i++) {
        if (list[i].id == id && list[i].owner == board && list[i].type == PRO_BODY) {
            found = true;
            CK(ProSolidBodyStateGet(&list[i], &found_state));
            break;
        }
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    if (!found)
        throw std::runtime_error("BOOLEAN_BODY_NOT_FOUND: boolean_bodies references a body id (" +
                                 std::to_string(id) +
                                 ") that this part does not contain; inspect bodies[].id");
    if (found_state != PRO_BODY_STATE_ACTIVE)
        throw std::runtime_error(
            "BOOLEAN_BODY_INACTIVE: boolean_bodies references a body id (" + std::to_string(id) +
            ") without active material (state=" + std::to_string((int)found_state) + ")");
}

static int active_solid_body_count() {
    ProSolidBody *list = nullptr;
    int n = 0;
    CK(ProSolidBodiesCollect((ProSolid)board, &list));
    CK(ProArraySizeGet((ProArray)list, &n));
    int active = 0;
    for (int i = 0; i < n; i++) {
        ProSolidBodyState state = PRO_BODY_STATE_NONE;
        if (list[i].owner == board && list[i].type == PRO_BODY &&
            ProSolidBodyStateGet(&list[i], &state) == PRO_TK_NO_ERROR &&
            state == PRO_BODY_STATE_ACTIVE)
            active++;
    }
    if (list)
        ProArrayFree((ProArray *)&list);
    return active;
}

static void generic_boolean(const J &op) {
    std::string method = op["method"];
    const int bodies_before = active_solid_body_count();
    double volume_before = 0.0;
    bool volume_before_known = true;
    try {
        volume_before = volume();
    } catch (...) {
        volume_before_known = false;
    }
    auto validate_bodies = [&](const J &bodies) {
        for (const auto &body_ref : bodies) {
            if (!body_ref.is_object() || body_ref.value("kind", "") != "body" ||
                !body_ref.contains("id") || !body_ref["id"].is_number_integer())
                throw std::runtime_error("Explicit body IDs are required for boolean_bodies");
            require_boolean_body(body_ref["id"].get<int>());
        }
    };
    validate_bodies(op["targets"]);
    validate_bodies(op["tools"]);

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_BOOLEANBODIES);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    integer(root, PRO_E_BOOLEAN_TYPE,
            method == "union"       ? PRO_MERGE_BOOL_TYPE
            : method == "intersect" ? PRO_INTERSECT_BOOL_TYPE
                                    : PRO_SUBTRACT_BOOL_TYPE);
    auto set_bodies = [&](int elem_id, const J &bodies) {
        if (bodies.size() == 1) {
            ProSelection s = selection(bodies[0]["id"].get<int>(), PRO_BODY);
            ref(root, elem_id, s);
            ProSelectionFree(&s);
        } else {
            ProElement elem = node(root, elem_id);
            ProReference *values = nullptr;
            CK(ProArrayAlloc((int)bodies.size(), sizeof(ProReference), 1, (ProArray *)&values));
            for (size_t i = 0; i < bodies.size(); i++) {
                ProSelection s = selection(bodies[i]["id"].get<int>(), PRO_BODY);
                CK(ProSelectionToReference(s, &values[i]));
                ProSelectionFree(&s);
            }
            CK(ProElementReferencesSet(elem, values));
            ProArrayFree((ProArray *)&values);
        }
    };
    set_bodies(PRO_E_TARGET_BODY, op["targets"]);
    set_bodies(PRO_E_TOOL_BODIES, op["tools"]);
    if (method == "subtract")
        integer(root, PRO_E_KEEP_TOOLS,
                op.value("keep_tools", false) ? PRO_KEEP_TOOL_YES : PRO_KEEP_TOOL_NO);
    ProFeature f = create(root);
    ProElementFree(&root);
    const int bodies_after = active_solid_body_count();
    double volume_after = 0.0;
    bool volume_after_known = true;
    try {
        volume_after = volume();
    } catch (...) {
        volume_after_known = false;
    }
    J extra = {{"method", method},
               {"bodies_before", bodies_before},
               {"bodies_after", bodies_after},
               {"volume_before_mm3", volume_before_known ? J(volume_before) : J(nullptr)},
               {"volume_after_mm3", volume_after_known ? J(volume_after) : J(nullptr)}};
    stage_operation_result(extra);
    remember(op, f, extra);
}
static J rib_element_errors_snapshot() {
    J sample = J::array();
    for (const auto &entry : feature_error_entries)
        sample.push_back(
            {{"element", entry.element}, {"type", entry.type}, {"error", entry.error}});
    return {{"total", feature_error_total},
            {"truncated", feature_error_total > (int)feature_error_entries.size()},
            {"sample", sample}};
}
static void generic_rib(const J &op) {
    const std::string side = op["side"];
    const bool flip = op.value("flip", false);
    const int side_opt = side == "symmetric"  ? PRO_RIB_SYMMETRIC
                         : side == "positive" ? PRO_RIB_SIDE_ONE
                                              : PRO_RIB_SIDE_TWO;
    const int matrlside = flip ? PRO_RIB_SEC_SIDE_TWO : PRO_RIB_SEC_SIDE_ONE;
    J rib_diag = {{"failed_stage", nullptr},
                  {"sketch_id", nullptr},
                  {"target_body_id", nullptr},
                  {"thickness_mm", op["thickness"]},
                  {"side", side},
                  {"side_opts_value", side_opt},
                  {"flip", flip},
                  {"matrlside_value", matrlside},
                  {"create_code", nullptr},
                  {"create_element_errors", nullptr},
                  {"feature_id", nullptr},
                  {"extract_code", nullptr},
                  {"matrlside_set_code", nullptr},
                  {"redefine_code", nullptr},
                  {"redefine_element_errors", nullptr},
                  {"status_code", nullptr},
                  {"feature_status", nullptr},
                  {"geometry_visit_code", nullptr},
                  {"geometry_item_count", nullptr},
                  {"geometry_items_sample", J::array()}};

    J state = inspection();
    if (!state["has_solid"].get<bool>()) {
        rib_diag["failed_stage"] = "precheck_no_solid";
        stage_operation_result({{"rib_diagnostics", rib_diag}});
        throw std::runtime_error(
            "Rib requires an existing solid body and an intersecting open profile");
    }
    int sketch_id = feature_id(op["sketch"]);
    rib_diag["sketch_id"] = sketch_id;
    for (const auto &meta : aliases) {
        if (meta.value("feature_id", -1) != sketch_id || !meta.contains("geometry"))
            continue;
        for (const auto &entity : meta["geometry"]) {
            if (entity.value("construction", false) || entity.value("type", "") == "centerline")
                continue;
            std::string kind = entity.value("type", "");
            if (kind == "circle" || kind == "ellipse" || kind == "rectangle" ||
                ((kind == "polyline" || kind == "spline") && entity.value("closed", false))) {
                rib_diag["failed_stage"] = "precheck_closed_profile";
                stage_operation_result({{"rib_diagnostics", rib_diag}});
                throw std::runtime_error(
                    "Rib requires an open profile; closed sketch contours are not accepted");
            }
        }
    }
    ProSolidBody default_body = {};
    if (ProSolidDefaultBodyGet((ProSolid)board, &default_body) == PRO_TK_NO_ERROR)
        rib_diag["target_body_id"] = default_body.id;

    ProElement root = node(nullptr, PRO_E_FEATURE_TREE);
    integer(root, PRO_E_FEATURE_TYPE, PRO_FEAT_RIB);
    integer(root, PRO_E_FEATURE_FORM, PRO_EXTRUDE);
    text(root, PRO_E_STD_FEATURE_NAME, wide(op["label"]).c_str());
    body_options(root, op);
    ProElement section = node(root, PRO_E_RIB_SECTION_COMP);
    ProSelection s = selection(sketch_id, PRO_FEATURE);
    ref(node(section, PRO_E_STD_SECTION), PRO_E_SEC_USE_SKETCH, s);
    ProSelectionFree(&s);
    // ProRib.h: material side is ignored until the standard section is fully
    // defined. Apply the requested side to the extracted native section below.
    real(root, PRO_E_RIB_THICKNESS, op["thickness"]);
    integer(root, PRO_E_RIB_SIDE_OPTS, side_opt);

    ProModelitem mi = {};
    CK(ProMdlToModelitem(board, &mi));
    ProSelection model_sel = nullptr;
    CK(ProSelectionAlloc(nullptr, &mi, &model_sel));
    ProFeatureCreateOptions *cr_opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&cr_opts));
    cr_opts[0] = PRO_FEAT_CR_INCOMPLETE_FEAT;
    ProFeature f = {};
    ProErrorlist create_es = {};
    ProError create_err =
        ProFeatureWithoptionsCreate(model_sel, root, cr_opts, PRO_REGEN_NO_FLAGS, &f, &create_es);
    errors(create_es);
    ProArrayFree((ProArray *)&cr_opts);
    ProSelectionFree(&model_sel);
    ProElementFree(&root);

    const int create_err_total = feature_error_total;
    rib_diag["create_code"] = (int)create_err;
    rib_diag["create_element_errors"] = rib_element_errors_snapshot();
    rib_diag["feature_id"] = f.id > 0 ? J(f.id) : J(nullptr);
    log("ProFeatureWithoptionsCreate=%d\n", (int)create_err);
    if (create_err != PRO_TK_NO_ERROR) {
        rib_diag["failed_stage"] = "rib_create";
        stage_operation_result(
            {{"feature_id", f.id > 0 ? J(f.id) : J(nullptr)}, {"rib_diagnostics", rib_diag}});
        last_feature_error_report =
            feature_error_report("ProFeatureWithoptionsCreate", create_err, "rib_create");
        log("RIB_DIAG stage=rib_create feature_id=%d create_code=%d create_errs=%d\n", f.id,
            (int)create_err, create_err_total);
        check(create_err, "ProFeatureWithoptionsCreate");
    }
    log("created_feature_id=%d\n", f.id);

    ProElement extracted = nullptr;
    ProError extract_err =
        ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &extracted);
    rib_diag["extract_code"] = (int)extract_err;
    log("ProFeatureElemtreeExtract(&f, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &extracted)=%d\n",
        (int)extract_err);
    if (extract_err != PRO_TK_NO_ERROR) {
        rib_diag["failed_stage"] = "rib_extract_tree";
        stage_operation_result({{"feature_id", f.id}, {"rib_diagnostics", rib_diag}});
        last_feature_error_report =
            feature_error_report("ProFeatureElemtreeExtract", extract_err, "rib_extract_tree");
        log("RIB_DIAG stage=rib_extract_tree feature_id=%d create_code=%d extract_code=%d\n", f.id,
            (int)create_err, (int)extract_err);
        check(extract_err, "ProFeatureElemtreeExtract");
    }

    ProElement matrl_elem = get(extracted, {PRO_E_RIB_SECTION_COMP, PRO_E_STD_MATRLSIDE});
    ProError matrl_err = ProElementIntegerSet(matrl_elem, matrlside);
    rib_diag["matrlside_set_code"] = (int)matrl_err;
    log("ProElementIntegerSet(PRO_E_STD_MATRLSIDE, %d)=%d\n", matrlside, (int)matrl_err);
    if (matrl_err != PRO_TK_NO_ERROR) {
        ProFeatureElemtreeFree(&f, extracted);
        rib_diag["failed_stage"] = "rib_set_matrlside";
        stage_operation_result({{"feature_id", f.id}, {"rib_diagnostics", rib_diag}});
        last_feature_error_report =
            feature_error_report("ProElementIntegerSet", matrl_err, "rib_set_matrlside");
        log("RIB_DIAG stage=rib_set_matrlside feature_id=%d create_code=%d extract_code=%d "
            "matrlside_set_code=%d\n",
            f.id, (int)create_err, (int)extract_err, (int)matrl_err);
        check(matrl_err, "ProElementIntegerSet");
    }

    ProFeatureCreateOptions *rd_opts = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), 1, (ProArray *)&rd_opts));
    rd_opts[0] = PRO_FEAT_CR_NO_OPTS;
    ProErrorlist redefine_es = {};
    ProError redefine_err = ProFeatureWithoptionsRedefine(nullptr, &f, extracted, rd_opts,
                                                          PRO_REGEN_NO_FLAGS, &redefine_es);
    errors(redefine_es);
    ProArrayFree((ProArray *)&rd_opts);
    CK(ProFeatureElemtreeFree(&f, extracted));

    const int redefine_err_total = feature_error_total;
    rib_diag["redefine_code"] = (int)redefine_err;
    rib_diag["redefine_element_errors"] = rib_element_errors_snapshot();
    log("CompleteFeature=%d\n", (int)redefine_err);
    if (redefine_err != PRO_TK_NO_ERROR) {
        rib_diag["failed_stage"] = "rib_redefine";
        stage_operation_result({{"feature_id", f.id}, {"rib_diagnostics", rib_diag}});
        last_feature_error_report =
            feature_error_report("ProFeatureWithoptionsRedefine", redefine_err, "rib_redefine");
        log("RIB_DIAG stage=rib_redefine feature_id=%d create_code=%d extract_code=%d "
            "matrlside_set_code=%d redefine_code=%d redefine_errs=%d\n",
            f.id, (int)create_err, (int)extract_err, (int)matrl_err, (int)redefine_err,
            redefine_err_total);
        check(redefine_err, "CompleteFeature");
    }

    ProFeatStatus status = PRO_FEAT_INVALID;
    ProError status_err = ProFeatureStatusGet(&f, &status);
    rib_diag["status_code"] = (int)status_err;
    if (status_err == PRO_TK_NO_ERROR)
        rib_diag["feature_status"] = (int)status;

    J geometry = J::array();
    ProError geom_visit_err =
        ProFeatureGeomitemVisit(&f, PRO_TYPE_UNUSED, collect_geom_ids, nullptr, &geometry);
    rib_diag["geometry_visit_code"] = (int)geom_visit_err;
    rib_diag["geometry_item_count"] = (int)geometry.size();
    J geom_sample = J::array();
    for (size_t i = 0; i < geometry.size() && i < 20; ++i)
        geom_sample.push_back(geometry[i]);
    rib_diag["geometry_items_sample"] = geom_sample;

    log("RIB_DIAG feature_id=%d create_code=%d extract_code=%d matrlside_set_code=%d "
        "redefine_code=%d status_code=%d feature_status=%d geom_items=%d geom_visit_code=%d "
        "create_errs=%d redefine_errs=%d\n",
        f.id, (int)create_err, (int)extract_err, (int)matrl_err, (int)redefine_err, (int)status_err,
        (int)status, (int)geometry.size(), (int)geom_visit_err, create_err_total,
        redefine_err_total);

    if (status_err != PRO_TK_NO_ERROR) {
        rib_diag["failed_stage"] = "rib_status_query";
        stage_operation_result({{"feature_id", f.id}, {"rib_diagnostics", rib_diag}});
        last_feature_error_report =
            feature_error_report("ProFeatureStatusGet", status_err, "rib_status_query");
        check(status_err, "ProFeatureStatusGet");
    }
    if (status != PRO_FEAT_ACTIVE) {
        rib_diag["failed_stage"] = "rib_regeneration";
        stage_operation_result({{"feature_id", f.id}, {"rib_diagnostics", rib_diag}});
        last_feature_error_report =
            feature_error_report("ProFeatureStatusGet", (ProError)status, "rib_regeneration");
        throw std::runtime_error(
            "Rib regeneration failed on the requested material side (feature_id=" +
            std::to_string(f.id) + ", feature_status=" + std::to_string((int)status) +
            ", geometry_items=" + std::to_string((int)geometry.size()) +
            ", create_code=" + std::to_string((int)create_err) +
            ", redefine_code=" + std::to_string((int)redefine_err) +
            "); check profile/body intersection, both-end solid bounding, flip and thickness side");
    }
    stage_operation_result({{"feature_id", f.id}, {"rib_diagnostics", rib_diag}});
    remember(op, f);
}
