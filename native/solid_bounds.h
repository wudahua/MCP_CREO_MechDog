#pragma once

#include "assembly_units.h"

#include <ProAsmcomp.h>
#include <ProAsmcomppath.h>
#include <ProSolidBody.h>
#include <ProSurface.h>

#include <algorithm>
#include <limits>

// FEAT-078: project tessellated, trimmed material faces into the requested
// frame. The regeneration outline can include cut and revolve envelopes.
namespace solid_bounds {
inline constexpr double target_chord_mm = 0.001;
inline constexpr int max_faces = 20000;
inline constexpr int max_facets = 4000000;
inline constexpr int max_occurrences = 4096;
inline constexpr double infinity = std::numeric_limits<double>::infinity();

struct Bounds {
    double lo[3]{infinity, infinity, infinity};
    double hi[3]{-infinity, -infinity, -infinity};
    int faces = 0;
    int facets = 0;
    int occurrences = 0;
    const char *reason = nullptr;
    ProError code = PRO_TK_NO_ERROR;

    ProError fail(const char *why, ProError raw_code = PRO_TK_NO_ERROR) {
        if (!reason) {
            reason = why;
            code = raw_code;
        }
        return PRO_TK_GENERAL_ERROR;
    }
};

struct Mesh {
    ProTessellation tessellation = nullptr;
    Pro3dPnt *vertices = nullptr;
    ProTriangle *facets = nullptr;

    ~Mesh() {
        if (vertices)
            ProArrayFree((ProArray *)&vertices);
        if (facets)
            ProArrayFree((ProArray *)&facets);
        if (tessellation)
            ProTessellationFree(tessellation);
    }
};

struct PartScan {
    Bounds &bounds;
    const ProMatrix &to_mm;
    ProSurfaceTessellationInput input = nullptr;
};

inline ProError visit_face(ProSurface face, ProError status, ProAppData data) {
    auto &scan = *static_cast<PartScan *>(data);
    auto &bounds = scan.bounds;
    if (status)
        return bounds.fail("surface_visit_failed", status);
    if (++bounds.faces > max_faces)
        return bounds.fail("face_budget_exceeded");
    Mesh mesh;
    ProError code = ProSurfaceTessellationGet(face, scan.input, &mesh.tessellation);
    if (code || !mesh.tessellation)
        return bounds.fail("surface_tessellation_failed", code);
    int vertices = 0, facets = 0;
    if ((code = ProTessellationVerticesGet(mesh.tessellation, &mesh.vertices)) || !mesh.vertices ||
        (code = ProTessellationFacetsGet(mesh.tessellation, &mesh.facets)) || !mesh.facets ||
        (code = ProArraySizeGet((ProArray)mesh.vertices, &vertices)) ||
        (code = ProArraySizeGet((ProArray)mesh.facets, &facets)) || vertices <= 0 || facets <= 0)
        return bounds.fail("surface_mesh_unavailable", code);
    if (facets > max_facets - bounds.facets)
        return bounds.fail("facet_budget_exceeded");
    bounds.facets += facets;
    // Only points referenced by a trimmed face's triangles are eligible.
    for (int i = 0; i < facets; ++i) {
        for (int index : mesh.facets[i]) {
            if (index < 0 || index >= vertices)
                return bounds.fail("invalid_surface_mesh");
            double point[3];
            transform_point(scan.to_mm, mesh.vertices[index], point);
            for (int axis = 0; axis < 3; ++axis) {
                if (!std::isfinite(point[axis]))
                    return bounds.fail("invalid_surface_mesh");
                bounds.lo[axis] = std::min(bounds.lo[axis], point[axis]);
                bounds.hi[axis] = std::max(bounds.hi[axis], point[axis]);
            }
        }
    }
    return PRO_TK_NO_ERROR;
}

inline ProError scan_part(ProSolid part, const ProMatrix &to_mm, Bounds &bounds) {
    double largest_projection_scale = 0.0;
    for (int axis = 0; axis < 3; ++axis)
        largest_projection_scale = std::max(
            largest_projection_scale, std::hypot(to_mm[0][axis], to_mm[1][axis], to_mm[2][axis]));
    if (!std::isfinite(largest_projection_scale) || largest_projection_scale <= 0.0)
        return bounds.fail("invalid_component_transform");

    PartScan scan{bounds, to_mm};
    ProSolidBody *bodies = nullptr;
    int count = 0;
    ProError code = ProSolidBodiesCollect(part, &bodies);
    if (!code && bodies)
        code = ProArraySizeGet((ProArray)bodies, &count);
    if (code)
        bounds.fail("body_query_failed", code);
    for (int i = 0; i < count && !bounds.reason; ++i) {
        ProSolidBodyState state;
        if ((code = ProSolidBodyStateGet(&bodies[i], &state))) {
            bounds.fail("body_state_failed", code);
            break;
        }
        if (state != PRO_BODY_STATE_ACTIVE)
            continue;
        ProBoolean construction = PRO_B_FALSE;
        if ((code = ProSolidBodyIsConstruction(&bodies[i], &construction))) {
            bounds.fail("body_type_failed", code);
            break;
        }
        if (construction == PRO_B_TRUE)
            continue;
        if (!scan.input) {
            code = ProSurfacetessellationinputAlloc(&scan.input);
            if (!code)
                code = ProSurfacetessellationinputChordheightSet(
                    scan.input, target_chord_mm / largest_projection_scale);
            if (code || !scan.input) {
                bounds.fail("surface_tessellation_setup_failed", code);
                break;
            }
        }
        code = ProSolidBodySurfaceVisit(&bodies[i], visit_face, &scan);
        if (code && code != PRO_TK_E_NOT_FOUND)
            bounds.fail("surface_visit_failed", code);
    }
    if (scan.input)
        ProSurfacetessellationinputFree(scan.input);
    if (bodies)
        ProArrayFree((ProArray *)&bodies);
    return bounds.reason ? PRO_TK_GENERAL_ERROR : PRO_TK_NO_ERROR;
}

struct AssemblyScan {
    Bounds &bounds;
    ProSolid root;
    double root_scale;
    ProIdTable path_ids{};
    int depth = 0;
};

inline ProError visit_assembly_feature(ProFeature *feature, ProError status, ProAppData data) {
    auto &scan = *static_cast<AssemblyScan *>(data);
    auto &bounds = scan.bounds;
    if (status)
        return bounds.fail("component_visit_failed", status);
    ProFeattype type;
    ProError code = ProFeatureTypeGet(feature, &type);
    if (code)
        return bounds.fail("component_type_failed", code);
    if (type != PRO_FEAT_COMPONENT && type != PRO_FEAT_ASSEM_CUT)
        return PRO_TK_NO_ERROR;
    ProFeatStatus state;
    if ((code = ProFeatureStatusGet(feature, &state)))
        return bounds.fail("component_status_failed", code);
    if (state == PRO_FEAT_SUPPRESSED || state == PRO_FEAT_FAMTAB_SUPPRESSED ||
        state == PRO_FEAT_SIMP_REP_SUPPRESSED || state == PRO_FEAT_PROG_SUPPRESSED)
        return PRO_TK_NO_ERROR;
    if (type == PRO_FEAT_ASSEM_CUT)
        return bounds.fail("assembly_context_cut");
    if (state != PRO_FEAT_ACTIVE)
        return bounds.fail("component_inactive");
    if (++bounds.occurrences > max_occurrences || scan.depth == PRO_MAX_ASSEM_LEVEL)
        return bounds.fail("assembly_budget_exceeded");

    ProMdl model = nullptr;
    ProMdlType model_type;
    if ((code = ProAsmcompMdlGet((ProAsmcomp *)feature, &model)) || !model ||
        (code = ProMdlTypeGet(model, &model_type)))
        return bounds.fail("component_model_unavailable", code);
    scan.path_ids[scan.depth++] = feature->id;
    if (model_type == PRO_MDL_ASSEMBLY) {
        code = ProSolidFeatVisit((ProSolid)model, visit_assembly_feature, nullptr, &scan);
        if (code)
            bounds.fail("component_visit_failed", code);
    } else if (model_type == PRO_MDL_PART) {
        ProAsmcomppath path;
        ProMatrix to_mm;
        if ((code = ProAsmcomppathInit(scan.root, scan.path_ids, scan.depth, &path)) ||
            (code = ProAsmcomppathTrfGet(&path, PRO_B_TRUE, to_mm))) {
            bounds.fail("component_transform_failed", code);
        } else {
            // The bottom-up matrix maps native part coordinates into native
            // root coordinates. Scaling its output columns converts to mm.
            for (auto &row : to_mm)
                for (int axis = 0; axis < 3; ++axis)
                    row[axis] *= scan.root_scale;
            if (!matrix_entries_finite(to_mm))
                bounds.fail("invalid_component_transform");
            else
                scan_part((ProSolid)model, to_mm, bounds);
        }
    } else {
        bounds.fail("unsupported_component_model");
    }
    --scan.depth;
    return bounds.reason ? PRO_TK_GENERAL_ERROR : PRO_TK_NO_ERROR;
}

inline void inspect(ProSolid model, bool assembly, const MillimeterScale &scale,
                    nlohmann::json &inspection) {
    Bounds bounds;
    if (!scale.known) {
        bounds.fail("unknown_length_unit");
    } else if (assembly) {
        AssemblyScan scan{bounds, model, scale.scale};
        const ProError code = ProSolidFeatVisit(model, visit_assembly_feature, nullptr, &scan);
        if (code)
            bounds.fail("component_visit_failed", code);
    } else {
        const ProMatrix to_mm = {
            {scale.scale, 0, 0, 0}, {0, scale.scale, 0, 0}, {0, 0, scale.scale, 0}, {0, 0, 0, 1}};
        scan_part(model, to_mm, bounds);
    }
    inspection["bounding_box_source"] = "solid_face_tessellation";
    const bool measured = !bounds.reason && bounds.facets > 0;
    inspection["bounding_box_status"] = {
        {"state", bounds.reason   ? "unavailable"
                  : bounds.facets ? "measured"
                                  : "no_solid"},
        {"reason", bounds.reason ? nlohmann::json(bounds.reason) : nlohmann::json(nullptr)},
        {"query_code", bounds.code ? nlohmann::json(bounds.code) : nlohmann::json(nullptr)},
        {"target_chord_height_mm", target_chord_mm},
        {"measurement_method", measured ? nlohmann::json("tessellated") : nlohmann::json(nullptr)},
        {"method_error_bound_mm",
         measured ? nlohmann::json(target_chord_mm) : nlohmann::json(nullptr)},
        {"error_bound_direction", measured ? nlohmann::json("inward") : nlohmann::json(nullptr)},
    };
    if (!bounds.reason && bounds.facets)
        inspection["bounding_box_mm"] = {
            {"min", bounds.lo},
            {"max", bounds.hi},
            {"size",
             {bounds.hi[0] - bounds.lo[0], bounds.hi[1] - bounds.lo[1],
              bounds.hi[2] - bounds.lo[2]}},
        };
}
} // namespace solid_bounds
