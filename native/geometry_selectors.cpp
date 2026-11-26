// DEV-089 T1: geometric anchor selectors resolved against the current model.
//
// Included by generic.cpp after inspection() and the vector helpers, so this
// translation unit owns the whole matching rule for {kind:'geometry_selector'}.
// The request shape is frozen by creo_mechdog.geometry_selectors; this file is
// the second line of defence and never guesses a candidate.
//
// Coordinates in the inspection record are model length units, so every
// comparison converts model -> millimetres with the executor's own measured
// scale. An unknown scale refuses the selector instead of assuming millimetres
// (BUG-080).

struct GeometrySelectorOutcome {
    bool matched = false;
    int id = -1;
    std::string target;
    J diagnostic = J::object();
    std::string error;
};

static double selector_component_error(const V &actual, const V &expected) {
    return std::max(std::max(fabs(actual[0] - expected[0]), fabs(actual[1] - expected[1])),
                    fabs(actual[2] - expected[2]));
}

static double selector_axis_distance(const V &point, const V &origin, const V &axis) {
    V offset = {point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]};
    double along = dot(offset, axis);
    V perpendicular = {offset[0] - axis[0] * along, offset[1] - axis[1] * along,
                       offset[2] - axis[2] * along};
    return sqrt(dot(perpendicular, perpendicular));
}

static double selector_segment_distance(const V &point, const V &first, const V &second) {
    V direction = {second[0] - first[0], second[1] - first[1], second[2] - first[2]};
    double length_squared = dot(direction, direction);
    if (length_squared < 1e-18)
        return selector_component_error(point, first);
    V offset = {point[0] - first[0], point[1] - first[1], point[2] - first[2]};
    double t = dot(offset, direction) / length_squared;
    t = std::max(0.0, std::min(1.0, t));
    V nearest = {first[0] + direction[0] * t, first[1] + direction[1] * t,
                 first[2] + direction[2] * t};
    return sqrt(dot(V{point[0] - nearest[0], point[1] - nearest[1], point[2] - nearest[2]},
                    V{point[0] - nearest[0], point[1] - nearest[1], point[2] - nearest[2]}));
}

static std::string selector_id_list(const std::vector<int> &ids) {
    std::string text;
    for (int id : ids)
        text += (text.empty() ? "" : ", ") + std::to_string(id);
    return text;
}

static std::string selector_surface_type_name(int type) {
    if (type == PRO_SRF_PLANE)
        return "plane";
    if (type == PRO_SRF_CYL)
        return "cylinder";
    return "type " + std::to_string(type);
}

static std::string selector_surface_list(const std::vector<int> &ids,
                                         const std::vector<int> &types) {
    std::string text;
    for (size_t index = 0; index < ids.size(); index++)
        text += (text.empty() ? "" : ", ") + std::to_string(ids[index]) + " (" +
                selector_surface_type_name(types[index]) + ")";
    return text;
}

static double selector_vector_norm(const V &value) {
    return sqrt(dot(value, value));
}

static V selector_cross(const V &first, const V &second) {
    return {first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0]};
}

static std::string selector_edge_error(const std::string &form, const std::vector<int> &matches,
                                       int candidates, double tolerance, bool same_circle = false) {
    if (matches.empty()) {
        std::string text = "geometry_selector edge " + form + " matched none of the " +
                           std::to_string(candidates) +
                           " eligible model edges (tolerance_mm=" + std::to_string(tolerance) + ")";
        if (form == "point_mm") {
            text += "; a single point matches a finite straight edge or a circular arc edge "
                    "(not the circle's centre point) - name a circular edge with "
                    "center_mm+radius_mm (+full_circle:true) instead of its centre point";
        } else if (form == "circular") {
            text += "; re-read creo_inspect_model edges[].arc origin/radius and pass current "
                    "model coordinates";
        } else {
            text += "; re-read creo_inspect_model edges[].start/end and pass current "
                    "coordinates, or use {kind:'edge',id:N}";
        }
        return text;
    }
    if (same_circle) {
        // FEAT-068 A0 / 0.27.0 feedback / BUG-176: one physical rim is reported as several
        // arcs of the same circle. Every one of them passes the centre + radius
        // filter by construction, so "use a smaller tolerance_mm" can never pick
        // one; the caller can pass full_circle:true (for round/chamfer propagation),
        // narrow by point_mm on the span, or select by edge id.
        return "geometry_selector edge " + form + " matched " + std::to_string(matches.size()) +
               " arcs of one circle (ids " + selector_id_list(matches) +
               "); the rim is reported as several arcs with the same centre and radius, so a "
               "smaller tolerance_mm cannot separate them - set full_circle:true to pick one "
               "deterministic arc of the circle, add point_mm on the span you want, "
               "or select one arc with {kind:'edge',id:N}";
    }
    return "geometry_selector edge " + form + " matched " + std::to_string(matches.size()) +
           " edges (ids " + selector_id_list(matches) +
           "); use a smaller tolerance_mm or an anchor that belongs to exactly one edge";
}

// DEV-098: zero-match edge selectors report the closest eligible edges so the
// caller can re-read the measurements instead of retrying the same anchor. This
// is diagnostic only - the matcher never selects one of these edges.
static bool selector_edge_on_face(const J &selector, const J &edge) {
    if (!selector.contains("on_face"))
        return true;
    if (!edge.contains("adjacent_surfaces") || !edge.at("adjacent_surfaces").is_array())
        return false;
    const auto &faces = edge.at("adjacent_surfaces");
    return std::find(faces.begin(), faces.end(), selector.at("on_face").at("id")) != faces.end();
}

static J selector_nearest_edges(const J &selector, const J &state, double mm_scale,
                                const std::string &form) {
    const double pi = 3.14159265358979323846;
    struct Row {
        double error;
        int id;
        J record;
    };
    std::vector<Row> rows;
    if (form == "circular") {
        const V center = vec(selector["center_mm"]);
        const double radius = selector["radius_mm"].get<double>();
        const bool filter_axis = selector.contains("axis");
        const V requested = filter_axis ? normalized(vec(selector["axis"])) : V{0, 0, 0};
        for (const auto &edge : state.value("edges", J::array())) {
            if (!selector_edge_on_face(selector, edge))
                continue;
            if (!edge.contains("arc"))
                continue;
            const J &arc = edge["arc"];
            const V arc_center = scale(vec(arc["origin"]), mm_scale);
            const double arc_radius = arc["radius"].get<double>() * mm_scale;
            const double radius_error = fabs(arc_radius - radius);
            const double center_error = selector_component_error(arc_center, center);
            J record = {{"id", edge["id"]},
                        {"center_mm", J::array({arc_center[0], arc_center[1], arc_center[2]})},
                        {"radius_mm", arc_radius},
                        {"radius_error_mm", radius_error},
                        {"center_error_mm", center_error}};
            double error = std::max(radius_error, center_error);
            if (filter_axis) {
                V arc_axis = selector_cross(vec(arc["v1"]), vec(arc["v2"]));
                const double axis_length = selector_vector_norm(arc_axis);
                if (axis_length > 1e-9) {
                    arc_axis = scale(arc_axis, 1.0 / axis_length);
                    const double cosine =
                        std::max(-1.0, std::min(1.0, fabs(dot(arc_axis, requested))));
                    const double axis_error = std::acos(cosine) * 180.0 / pi;
                    record["axis_error_deg"] = axis_error;
                }
            }
            record["error_mm"] = error;
            rows.push_back({error, edge["id"].get<int>(), record});
        }
    } else {
        const bool endpoints_form = form == "endpoints";
        const V wanted[2] = {vec(selector.contains("endpoints_mm")
                                     ? selector.at("endpoints_mm").at(0)
                                     : selector.at("point_mm")),
                             endpoints_form ? vec(selector.at("endpoints_mm").at(1)) : V{0, 0, 0}};
        const bool filter_point = selector.contains("point_mm");
        const V point = filter_point ? vec(selector["point_mm"]) : V{0, 0, 0};
        for (const auto &edge : state.value("edges", J::array())) {
            if (!selector_edge_on_face(selector, edge))
                continue;
            if (!edge.contains("start") || !edge.contains("end"))
                continue;
            const V first = scale(vec(edge["start"]), mm_scale);
            const V second = scale(vec(edge["end"]), mm_scale);
            double endpoint_error = 0;
            J record = {{"id", edge["id"]},
                        {"endpoints_mm", J::array({J::array({first[0], first[1], first[2]}),
                                                   J::array({second[0], second[1], second[2]})})}};
            if (endpoints_form) {
                const double direct[2] = {selector_component_error(first, wanted[0]),
                                          selector_component_error(second, wanted[1])};
                const double reverse[2] = {selector_component_error(second, wanted[0]),
                                           selector_component_error(first, wanted[1])};
                const bool use_reverse =
                    std::max(reverse[0], reverse[1]) < std::max(direct[0], direct[1]);
                record["endpoint_errors_mm"] = J::array(
                    {use_reverse ? reverse[0] : direct[0], use_reverse ? reverse[1] : direct[1]});
                endpoint_error =
                    use_reverse ? std::max(reverse[0], reverse[1]) : std::max(direct[0], direct[1]);
            }
            double error = endpoint_error;
            if (filter_point) {
                const double point_error = selector_segment_distance(point, first, second);
                record["point_error_mm"] = point_error;
                error = std::max(error, point_error);
            }
            record["error_mm"] = error;
            rows.push_back({error, edge["id"].get<int>(), record});
        }
    }
    std::sort(rows.begin(), rows.end(), [](const Row &a, const Row &b) {
        if (a.error != b.error)
            return a.error < b.error;
        return a.id < b.id;
    });
    if (rows.size() > 5)
        rows.resize(5);
    J nearest = J::array();
    for (auto &row : rows) {
        row.record["suggested_reference"] = {{"kind", "edge"}, {"id", row.id}};
        nearest.push_back(std::move(row.record));
    }
    return nearest;
}

// DEV-098: zero-match surface selectors report the closest nameable faces the
// same way edges do. Only planar and cylindrical faces are listed: they are the
// only types a surface selector can name, and a wrong-type candidate is already
// reported in type_rejected_ids. Diagnostic only - never selected.
static J selector_nearest_surfaces(const J &selector, const J &state, double mm_scale) {
    const double pi = 3.14159265358979323846;
    struct Row {
        double error;
        int id;
        J record;
    };
    std::vector<Row> rows;
    const bool filter_axis = selector.contains("axis");
    const V requested = filter_axis ? normalized(vec(selector["axis"])) : V{0, 0, 0};
    const bool filter_radius = selector.contains("radius_mm");
    const double radius = filter_radius ? selector["radius_mm"].get<double>() : 0.0;
    const bool filter_center = selector.contains("center_mm");
    const V center = filter_center ? vec(selector["center_mm"]) : V{0, 0, 0};
    // radius_mm/center_mm only describe cylinders; a plane that carries the
    // requested direction is a wrong-type candidate reported elsewhere.
    const bool cylinder_only = filter_radius || filter_center;
    for (const auto &surface : state.value("surfaces", J::array())) {
        const int type = surface.value("type", -1);
        const bool plane = type == PRO_SRF_PLANE;
        const bool cylinder = type == PRO_SRF_CYL;
        if (!plane && !cylinder)
            continue;
        if (cylinder_only && !cylinder)
            continue;
        V axis = {0, 0, 0};
        bool has_axis = false;
        if (plane && surface.contains("normal")) {
            axis = normalized(vec(surface["normal"]));
            has_axis = true;
        }
        if (cylinder && surface.contains("axis")) {
            axis = normalized(vec(surface["axis"]));
            has_axis = true;
        }
        if (filter_axis && !has_axis)
            continue;
        const V origin =
            surface.contains("origin") ? scale(vec(surface["origin"]), mm_scale) : V{0, 0, 0};
        J record = {{"id", surface["id"]},
                    {"type", plane ? "plane" : "cylinder"},
                    {"coordinate_space", "model"},
                    {"suggested_reference", {{"kind", "surface"}, {"id", surface["id"]}}}};
        if (surface.contains("origin"))
            record["origin_mm"] = J::array({origin[0], origin[1], origin[2]});
        double error = 0;
        if (filter_axis) {
            const double cosine = std::max(-1.0, std::min(1.0, fabs(dot(axis, requested))));
            record["axis_error_deg"] = std::acos(cosine) * 180.0 / pi;
        }
        record[plane ? "normal" : "axis"] = J::array({axis[0], axis[1], axis[2]});
        if (cylinder && surface.contains("radius")) {
            const double measured = surface["radius"].get<double>() * mm_scale;
            record["radius_mm"] = measured;
            if (filter_radius) {
                const double radius_error = fabs(measured - radius);
                record["radius_error_mm"] = radius_error;
                error = std::max(error, radius_error);
            }
        }
        if (filter_center) {
            const double distance = selector_axis_distance(center, origin, axis);
            record["center_axis_distance_mm"] = distance;
            error = std::max(error, distance);
        }
        if (selector.contains("points_mm")) {
            double worst = 0;
            bool measurable = true;
            for (const auto &item : selector["points_mm"]) {
                const V point = vec(item);
                double offset = 0;
                if (plane && has_axis)
                    offset = fabs(dot(
                        V{point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]}, axis));
                else if (cylinder && has_axis && surface.contains("radius"))
                    offset = fabs(selector_axis_distance(point, origin, axis) -
                                  surface["radius"].get<double>() * mm_scale);
                else {
                    measurable = false;
                    break;
                }
                worst = std::max(worst, offset);
            }
            if (!measurable)
                continue;
            record["points_offset_mm"] = worst;
            error = std::max(error, worst);
        }
        record["error_mm"] = error;
        rows.push_back({error, surface["id"].get<int>(), record});
    }
    std::sort(rows.begin(), rows.end(), [](const Row &a, const Row &b) {
        if (a.error != b.error)
            return a.error < b.error;
        return a.id < b.id;
    });
    if (rows.size() > 5)
        rows.resize(5);
    J nearest = J::array();
    for (auto &row : rows)
        nearest.push_back(std::move(row.record));
    return nearest;
}

// Distance to the finite measured arc, including a possible closest endpoint.
static double selector_arc_distance(const J &arc, const V &point, double mm_scale) {
    const V center = scale(vec(arc.at("origin")), mm_scale);
    const V x = normalized(vec(arc.at("v1"))), y = normalized(vec(arc.at("v2")));
    if (selector_vector_norm(selector_cross(x, y)) <= 1e-9)
        return std::numeric_limits<double>::infinity();
    const V delta = {point[0] - center[0], point[1] - center[1], point[2] - center[2]};
    const double radius = arc.at("radius").get<double>() * mm_scale;
    const double start = arc.at("start_angle").get<double>();
    const double finish = arc.at("end_angle").get<double>();
    constexpr double full = 6.28318530717958647692;
    const double angle = std::atan2(dot(delta, y), dot(delta, x));
    double span = finish - start;
    if (span < 0)
        span += full;
    double offset = std::fmod(angle - start, full);
    if (offset < 0)
        offset += full;
    auto distance = [&](double at) {
        V difference{};
        for (int axis = 0; axis < 3; ++axis)
            difference[axis] =
                delta[axis] - radius * (x[axis] * std::cos(at) + y[axis] * std::sin(at));
        return selector_vector_norm(difference);
    };
    return offset <= span ? distance(angle) : std::min(distance(start), distance(finish));
}

// BUG-176: test whether a 3D point lies on a measured circular arc within tolerance.
static bool selector_point_on_arc(const J &arc, const V &point, double mm_scale, double tolerance,
                                  V *out_center = nullptr, double *out_radius = nullptr,
                                  V *out_normal = nullptr, double *out_error = nullptr) {
    V arc_center = scale(vec(arc["origin"]), mm_scale);
    const double arc_radius = arc["radius"].get<double>() * mm_scale;
    V arc_v1 = normalized(vec(arc["v1"]));
    V arc_v2 = normalized(vec(arc["v2"]));
    V normal = selector_cross(arc_v1, arc_v2);
    const double normal_length = selector_vector_norm(normal);
    if (normal_length <= 1e-9)
        return false;
    normal = scale(normal, 1.0 / normal_length);
    V radial = {point[0] - arc_center[0], point[1] - arc_center[1], point[2] - arc_center[2]};
    const double plane_err = fabs(dot(radial, normal));
    if (plane_err > tolerance)
        return false;
    const double rad_err = fabs(selector_vector_norm(radial) - arc_radius);
    if (rad_err > tolerance)
        return false;
    const double two_pi = 2.0 * 3.14159265358979323846;
    const double start_angle = arc["start_angle"].get<double>();
    const double raw_span = arc["end_angle"].get<double>() - start_angle;
    if (raw_span < two_pi - 1e-6) {
        double span = raw_span;
        if (span < 0)
            span += two_pi;
        double offset = std::atan2(dot(radial, arc_v2), dot(radial, arc_v1)) - start_angle;
        offset = std::fmod(offset, two_pi);
        if (offset < 0)
            offset += two_pi;
        const double angular_tolerance = tolerance / std::max(arc_radius, 1e-9) + 1e-6;
        if (offset > span + angular_tolerance && (two_pi - offset) > angular_tolerance)
            return false;
    }
    if (out_center)
        *out_center = arc_center;
    if (out_radius)
        *out_radius = arc_radius;
    if (out_normal)
        *out_normal = normal;
    if (out_error)
        *out_error = std::max(plane_err, rad_err);
    return true;
}

static GeometrySelectorOutcome match_geometry_edge_selector(const J &selector, const J &state,
                                                            double mm_scale, double tolerance) {
    GeometrySelectorOutcome outcome;
    // BUG-155: resolve() picks PRO_EDGE/PRO_SURFACE from this field. The surface
    // matcher always set it; the edge matcher did not, so a matched edge id was
    // initialised as a surface and failed with PRO_TK_NOT_EXIST (-23).
    outcome.target = "edge";
    const bool circular = selector.contains("center_mm") || selector.contains("radius_mm");
    const bool nearest = selector.value("ambiguity", "") == "nearest";
    std::string form = circular                            ? "circular"
                       : selector.contains("endpoints_mm") ? "endpoints"
                                                           : "point_mm";
    std::vector<int> matches;
    J matched = J::array();
    int candidates = 0;
    // Every matched arc keeps its measured circle: the refusal text has to tell
    // "one rim split into arcs" apart from "the tolerance let two circles in".
    std::vector<V> matched_centers;
    std::vector<double> matched_radii;
    std::vector<V> matched_normals;
    bool all_matches_are_arcs = true;
    if (circular) {
        V center = vec(selector["center_mm"]);
        const double radius = selector["radius_mm"].get<double>();
        const bool filter_axis = selector.contains("axis");
        const double axis_tolerance = selector.value("axis_tolerance_deg", 0.5);
        const double cosine_limit = std::cos(axis_tolerance * 3.14159265358979323846 / 180.0);
        const V requested = filter_axis ? normalized(vec(selector["axis"])) : V{0, 0, 0};
        for (const auto &edge : state.value("edges", J::array())) {
            if (!selector_edge_on_face(selector, edge))
                continue;
            if (!edge.contains("arc"))
                continue; // only measured circular edges are eligible
            candidates++;
            const J &arc = edge["arc"];
            V arc_center = scale(vec(arc["origin"]), mm_scale);
            const double arc_radius = arc["radius"].get<double>() * mm_scale;
            if (fabs(arc_radius - radius) > tolerance)
                continue;
            if (selector_component_error(arc_center, center) > tolerance)
                continue;
            V arc_axis = selector_cross(vec(arc["v1"]), vec(arc["v2"]));
            const double axis_length = selector_vector_norm(arc_axis);
            if (axis_length > 1e-9)
                arc_axis = scale(arc_axis, 1.0 / axis_length);
            if (filter_axis) {
                if (axis_length <= 1e-9)
                    continue; // no measured plane normal, so no axis filter can pass
                if (fabs(dot(arc_axis, requested)) < cosine_limit)
                    continue;
            }
            if (selector.contains("point_mm")) {
                // FEAT-068 A0 / BUG-176: a full rim is often split into two arcs with the
                // same centre and radius. The point selects the piece whose measured
                // angular span contains it; it must lie on the circle.
                V point = vec(selector["point_mm"]);
                if (!selector_point_on_arc(arc, point, mm_scale, tolerance))
                    continue;
            }
            matches.push_back(edge["id"].get<int>());
            matched_centers.push_back(arc_center);
            matched_radii.push_back(arc_radius);
            matched_normals.push_back(arc_axis);
            matched.push_back({{"id", edge["id"]},
                               {"radius_mm", arc_radius},
                               {"center_error_mm", selector_component_error(arc_center, center)}});
        }
    } else {
        V expected[2] = {vec(selector.contains("endpoints_mm") ? selector.at("endpoints_mm").at(0)
                                                               : selector.at("point_mm")),
                         V{0, 0, 0}};
        if (selector.contains("endpoints_mm"))
            expected[1] = vec(selector.at("endpoints_mm").at(1));
        for (const auto &edge : state.value("edges", J::array())) {
            if (!selector_edge_on_face(selector, edge))
                continue;
            if (edge.contains("start") && edge.contains("end")) {
                candidates++;
                V first = scale(vec(edge["start"]), mm_scale);
                V second = scale(vec(edge["end"]), mm_scale);
                double error = 0;
                if (selector.contains("endpoints_mm")) {
                    // Undirected: a straight edge has no meaningful start.
                    double forward = std::max(selector_component_error(first, expected[0]),
                                              selector_component_error(second, expected[1]));
                    double reverse = std::max(selector_component_error(second, expected[0]),
                                              selector_component_error(first, expected[1]));
                    error = std::min(forward, reverse);
                    if (error > tolerance)
                        continue;
                    if (selector.contains("point_mm")) {
                        V point = vec(selector["point_mm"]);
                        if (selector_segment_distance(point, first, second) > tolerance)
                            continue;
                    }
                } else {
                    // FEAT-068 A0: one point on one finite straight edge. The
                    // distance is measured to the segment, never to its infinite
                    // line, so a point beyond an endpoint cannot match.
                    error = selector_segment_distance(expected[0], first, second);
                    if (error > tolerance)
                        continue;
                }
                matches.push_back(edge["id"].get<int>());
                all_matches_are_arcs = false;
                matched.push_back({{"id", edge["id"]}, {"anchor_error_mm", error}});
            } else if (!selector.contains("endpoints_mm") && edge.contains("arc")) {
                // BUG-176: single point_mm also matches circular arc edges when the
                // point lies on the arc curve itself (not at the circle centre).
                candidates++;
                V arc_center = {0, 0, 0};
                double arc_radius = 0.0;
                V arc_normal = {0, 0, 0};
                double error = 0.0;
                if (nearest) {
                    error = selector_arc_distance(edge["arc"], expected[0], mm_scale);
                    if (!std::isfinite(error) || error > tolerance)
                        continue;
                } else if (!selector_point_on_arc(edge["arc"], expected[0], mm_scale, tolerance,
                                                  &arc_center, &arc_radius, &arc_normal, &error)) {
                    continue;
                }
                matches.push_back(edge["id"].get<int>());
                matched_centers.push_back(arc_center);
                matched_radii.push_back(arc_radius);
                matched_normals.push_back(arc_normal);
                matched.push_back(
                    {{"id", edge["id"]}, {"anchor_error_mm", error}, {"radius_mm", arc_radius}});
            }
        }
    }
    // Only arcs sitting on one and the same circle prove that a tighter
    // tolerance cannot separate them: they pass the centre + radius filter by
    // construction. Two distinct circles that both fit inside the tolerance are
    // still separable, so they keep the generic advice.
    const double same_circle_epsilon = 1e-6;
    bool same_circle = !nearest && all_matches_are_arcs && matched_centers.size() > 1 &&
                       matched_centers.size() == matches.size();
    for (size_t i = 1; same_circle && i < matched_centers.size(); ++i) {
        same_circle =
            fabs(matched_radii[i] - matched_radii[0]) <= same_circle_epsilon &&
            selector_component_error(matched_centers[i], matched_centers[0]) <= same_circle_epsilon;
        if (same_circle && i < matched_normals.size() &&
            selector_vector_norm(matched_normals[i]) > 1e-9 &&
            selector_vector_norm(matched_normals[0]) > 1e-9) {
            same_circle = fabs(dot(matched_normals[i], matched_normals[0])) >= 1.0 - 1e-6;
        }
    }
    // BUG-176: deterministically pick the smallest arc id of one physical circle
    // when either (a) full_circle:true is requested on a circular edge selector, or
    // (b) point_mm lands on the shared seam/extremum between complementary arcs of
    // the same circle.
    const bool full_circle_opt_in = circular && selector.value("full_circle", false);
    const bool seam_point_hit = selector.contains("point_mm");
    const bool resolved_same_circle =
        matches.size() > 1 && same_circle && (full_circle_opt_in || seam_point_hit);
    int nearest_id = -1;
    double nearest_error = std::numeric_limits<double>::infinity();
    double second_error = nearest_error;
    if (nearest && matches.size() > 1) {
        for (const auto &candidate : matched) {
            const double error = candidate.at("anchor_error_mm").get<double>();
            if (error < nearest_error) {
                second_error = nearest_error;
                nearest_error = error;
                nearest_id = candidate.at("id").get<int>();
            } else {
                second_error = std::min(second_error, error);
            }
        }
    }
    const bool resolved_nearest = nearest_id >= 0 && second_error - nearest_error > 1e-6;
    if (matches.size() == 1 || resolved_same_circle || resolved_nearest) {
        const int chosen =
            resolved_nearest ? nearest_id : *std::min_element(matches.begin(), matches.end());
        outcome.matched = true;
        outcome.id = chosen;
        outcome.diagnostic = {{"target", "edge"},
                              {"form", form},
                              {"matched_geometry_id", chosen},
                              {"candidate_count", candidates},
                              {"tolerance_mm", tolerance}};
        if (selector.contains("on_face"))
            outcome.diagnostic["on_face"] = selector.at("on_face");
        if (resolved_nearest) {
            outcome.diagnostic["matched_ids"] = J(matches);
            outcome.diagnostic["ambiguity_resolution"] = "nearest";
            outcome.diagnostic["distance_mm"] = nearest_error;
            outcome.diagnostic["next_distance_mm"] = second_error;
        }
        if (resolved_same_circle) {
            outcome.diagnostic["matched_ids"] = J(matches);
            outcome.diagnostic["same_circle"] = true;
            if (full_circle_opt_in)
                outcome.diagnostic["full_circle"] = true;
            if (seam_point_hit)
                outcome.diagnostic["seam_point_resolved"] = true;
        }
        return outcome;
    }
    outcome.diagnostic = {{"target", "edge"},
                          {"form", form},
                          {"coordinate_space", "model"},
                          {"tolerance_mm", tolerance},
                          {"candidate_count", candidates},
                          {"matched_ids", J(matches)}};
    outcome.error = selector_edge_error(form, matches, candidates, tolerance, same_circle);
    if (matches.size() > 1 && !same_circle) {
        std::string adj_hint;
        int first_surface_id = -1;
        for (int match_id : matches) {
            for (const auto &edge : state.value("edges", J::array())) {
                if (edge.value("id", -1) != match_id)
                    continue;
                if (edge.contains("adjacent_surfaces") && edge["adjacent_surfaces"].is_array()) {
                    if (!adj_hint.empty())
                        adj_hint += "; ";
                    adj_hint += "edge " + std::to_string(match_id) +
                                " adjacent_surfaces=" + edge["adjacent_surfaces"].dump();
                    if (first_surface_id < 0 && !edge["adjacent_surfaces"].empty() &&
                        edge["adjacent_surfaces"][0].is_number_integer())
                        first_surface_id = edge["adjacent_surfaces"][0].get<int>();
                }
                break;
            }
        }
        if (!adj_hint.empty()) {
            outcome.error += "; " + adj_hint;
            if (first_surface_id >= 0)
                outcome.error += "; disambiguate with on_face:{kind:'surface',id:" +
                                 std::to_string(first_surface_id) + "} or ambiguity:'nearest'";
        }
    }
    if (selector.contains("on_face")) {
        outcome.diagnostic["on_face"] = selector.at("on_face");
        outcome.error += "; restricted to edges adjacent to current surface " +
                         std::to_string(selector.at("on_face").at("id").get<int>());
    }
    if (nearest && matches.size() > 1) {
        outcome.diagnostic["ambiguity_resolution"] = "tied";
        outcome.diagnostic["distance_mm"] = nearest_error;
        outcome.diagnostic["next_distance_mm"] = second_error;
        outcome.error +=
            "; closest edges tie within 1e-6 mm - constrain on_face or use a current edge id";
    }
    if (matches.empty()) {
        outcome.diagnostic["nearest_edges"] =
            selector_nearest_edges(selector, state, mm_scale, form);
        outcome.error +=
            "; nearest eligible edges are listed in geometry_selector_diagnostic.nearest_edges "
            "(diagnostic only, never selected automatically)";
    }
    return outcome;
}

static GeometrySelectorOutcome match_geometry_surface_selector(const J &selector, const J &state,
                                                               double mm_scale, double tolerance) {
    GeometrySelectorOutcome outcome;
    outcome.target = "surface";
    const double axis_tolerance = selector.value("axis_tolerance_deg", 0.5);
    const double cosine_limit = std::cos(axis_tolerance * 3.14159265358979323846 / 180.0);
    std::vector<int> matches;
    std::vector<int> match_types;
    // BUG-132: candidates that matched the measured direction (or a points_mm
    // anchor) but cannot be the requested type. They are reported separately so
    // "wrong type" is not confused with "nothing matched".
    std::vector<int> rejected;
    std::vector<int> rejected_types;
    int eligible = 0;
    for (const auto &surface : state.value("surfaces", J::array())) {
        int type = surface.value("type", -1);
        const bool plane = type == PRO_SRF_PLANE;
        const bool cylinder = type == PRO_SRF_CYL;
        if (plane || cylinder)
            eligible++;
        V axis = {0, 0, 0};
        bool has_axis = false;
        if (plane && surface.contains("normal")) {
            axis = normalized(vec(surface["normal"]));
            has_axis = true;
        }
        if (cylinder && surface.contains("axis")) {
            axis = normalized(vec(surface["axis"]));
            has_axis = true;
        }
        // Normal/axis direction is compared sign-insensitively: the same planar
        // face reports opposite normals depending on which body is queried.
        if (selector.contains("axis")) {
            if (!has_axis)
                continue;
            V requested = normalized(vec(selector["axis"]));
            if (fabs(dot(axis, requested)) < cosine_limit)
                continue;
        }
        if (!plane && !cylinder) {
            // Only planar and cylindrical faces can be named. A points_mm anchor
            // inside this face's box is still evidence that the selector aimed at
            // it, so report the real type instead of "nothing matched".
            if (!selector.contains("points_mm"))
                continue;
            bool near_anchor = false;
            if (surface.contains("bbox") && surface["bbox"].is_array() &&
                surface["bbox"].size() == 2) {
                V low = scale(vec(surface["bbox"][0]), mm_scale);
                V high = scale(vec(surface["bbox"][1]), mm_scale);
                for (const auto &item : selector["points_mm"]) {
                    V point = vec(item);
                    bool inside_box = true;
                    for (int axis_index = 0; axis_index < 3; axis_index++)
                        if (point[axis_index] < low[axis_index] - tolerance ||
                            point[axis_index] > high[axis_index] + tolerance) {
                            inside_box = false;
                            break;
                        }
                    if (inside_box) {
                        near_anchor = true;
                        break;
                    }
                }
            }
            if (near_anchor) {
                rejected.push_back(surface["id"].get<int>());
                rejected_types.push_back(type);
            }
            continue;
        }
        if ((selector.contains("radius_mm") || selector.contains("center_mm")) && !cylinder) {
            // radius_mm/center_mm are cylinder filters. A plane that already
            // passed the direction filter is the classic wrong-type candidate.
            rejected.push_back(surface["id"].get<int>());
            rejected_types.push_back(type);
            continue;
        }
        if (selector.contains("radius_mm")) {
            if (!surface.contains("radius"))
                continue;
            if (fabs(surface["radius"].get<double>() * mm_scale -
                     selector["radius_mm"].get<double>()) > tolerance)
                continue;
        }
        V origin =
            surface.contains("origin") ? scale(vec(surface["origin"]), mm_scale) : V{0, 0, 0};
        if (selector.contains("center_mm")) {
            // The cylinder's parameter origin is not unique along its axis, so
            // only the perpendicular distance to the axis line is meaningful.
            if (!has_axis)
                continue;
            if (selector_axis_distance(vec(selector["center_mm"]), origin, axis) > tolerance)
                continue;
        }
        if (selector.contains("points_mm")) {
            bool all_on_surface = true;
            for (const auto &item : selector["points_mm"]) {
                V point = vec(item);
                double offset = 0;
                if (plane) {
                    offset = fabs(dot(
                        V{point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]}, axis));
                } else if (has_axis && surface.contains("radius")) {
                    offset = fabs(selector_axis_distance(point, origin, axis) -
                                  surface["radius"].get<double>() * mm_scale);
                } else {
                    all_on_surface = false;
                    break;
                }
                if (offset > tolerance) {
                    all_on_surface = false;
                    break;
                }
                // A coaxial cylinder is often reported as several pieces (and a
                // large plane can also be split); the infinite-surface offset is
                // identical for all of them. Require the point to be inside the
                // reported piece's own bounding box so one anchor names one piece.
                if (surface.contains("bbox") && surface["bbox"].is_array() &&
                    surface["bbox"].size() == 2) {
                    V low = scale(vec(surface["bbox"][0]), mm_scale);
                    V high = scale(vec(surface["bbox"][1]), mm_scale);
                    for (int axis = 0; axis < 3; axis++)
                        if (point[axis] < low[axis] - tolerance ||
                            point[axis] > high[axis] + tolerance) {
                            all_on_surface = false;
                            break;
                        }
                }
                if (!all_on_surface)
                    break;
            }
            if (!all_on_surface)
                continue;
        }
        matches.push_back(surface["id"].get<int>());
        match_types.push_back(type);
    }
    const bool coaxial_any = selector.value("coaxial", std::string()) == "any";
    if (matches.size() > 1 && coaxial_any) {
        // BUG-132: a full cylinder is often reported as two coaxial half faces.
        // insert/concentric only needs the axis, so every matched cylinder piece
        // is geometrically equivalent. This stays opt-in (the default still needs
        // one exact face) and the smallest id keeps the choice deterministic and
        // visible in the diagnostic.
        bool all_cylinders = true;
        for (int type : match_types)
            all_cylinders = all_cylinders && type == PRO_SRF_CYL;
        if (all_cylinders) {
            int chosen = matches[0];
            for (int id : matches)
                chosen = std::min(chosen, id);
            outcome.matched = true;
            outcome.id = chosen;
            outcome.diagnostic = {{"target", "surface"},
                                  {"matched_geometry_id", chosen},
                                  {"candidate_count", eligible},
                                  {"tolerance_mm", tolerance},
                                  {"coaxial_any", true},
                                  {"matched_ids", J(matches)},
                                  {"matched_types", J(match_types)}};
            return outcome;
        }
    }
    if (matches.size() == 1) {
        outcome.matched = true;
        outcome.id = matches[0];
        outcome.diagnostic = {{"target", "surface"},
                              {"matched_geometry_id", matches[0]},
                              {"candidate_count", eligible},
                              {"tolerance_mm", tolerance}};
        return outcome;
    }
    outcome.diagnostic = {{"target", "surface"},
                          {"coordinate_space", "model"},
                          {"tolerance_mm", tolerance},
                          {"candidate_count", eligible},
                          {"matched_ids", J(matches)},
                          {"matched_types", J(match_types)},
                          {"type_rejected_ids", J(rejected)},
                          {"type_rejected_types", J(rejected_types)}};
    if (matches.empty())
        outcome.diagnostic["nearest_surfaces"] =
            selector_nearest_surfaces(selector, state, mm_scale);
    if (!matches.empty()) {
        outcome.error =
            "geometry_selector surface filters matched " + std::to_string(matches.size()) +
            " faces (ids " + selector_surface_list(matches, match_types) +
            "); a full cylinder is often reported as several coaxial pieces, so "
            "center_mm/radius_mm/axis alone cannot name one. Add points_mm that lies inside "
            "exactly one piece's bbox, use {kind:'surface',id:N}, or (insert/concentric only) "
            "set coaxial:'any'. radius_mm filters a cylinder's radius; it is not a surface-type "
            "filter.";
        return outcome;
    }
    if (!rejected.empty()) {
        outcome.error =
            "geometry_selector surface filters matched no usable face, but " +
            std::to_string(rejected.size()) +
            " candidate(s) had the requested direction or anchor and the wrong type (ids " +
            selector_surface_list(rejected, rejected_types) +
            "); radius_mm/center_mm require a cylinder and radius_mm is not a type filter. A "
            "points_mm anchor that lies on a cylinder's planar end face resolves to that plane; "
            "move it onto the cylindrical wall, pass {kind:'surface',id:N}, or (insert/concentric "
            "only) set coaxial:'any'. The closest nameable faces are listed in "
            "geometry_selector_diagnostic.nearest_surfaces (diagnostic only, never selected "
            "automatically).";
        return outcome;
    }
    outcome.error =
        "geometry_selector surface filters matched none of the " + std::to_string(eligible) +
        " planar/cylindrical model faces (tolerance_mm=" + std::to_string(tolerance) +
        ", axis_tolerance_deg=" + std::to_string(axis_tolerance) +
        "); re-read creo_inspect_model surfaces[] and pass current normal/origin/radius, or use "
        "{kind:'surface',id:N}. radius_mm filters a cylinder's radius; it is not a surface-type "
        "filter. The closest nameable faces are listed in "
        "geometry_selector_diagnostic.nearest_surfaces (diagnostic only, never selected "
        "automatically).";
    if (outcome.diagnostic.contains("nearest_surfaces") &&
        outcome.diagnostic["nearest_surfaces"].is_array() &&
        !outcome.diagnostic["nearest_surfaces"].empty()) {
        const J &top = outcome.diagnostic["nearest_surfaces"][0];
        outcome.error +=
            " Closest candidate: {kind:'surface',id:" + std::to_string(top["id"].get<int>()) +
            "} (" + top.value("type", "surface") +
            ", error_mm=" + std::to_string(top.value("error_mm", 0.0)) + ").";
    }
    return outcome;
}

// DEV-089 T1 assembly occurrences: a selector written in root-assembly
// coordinates is mapped into the component's own model frame with the inverse of
// the occurrence placement. ProMatrix rows are the local axes expressed in the
// parent frame and row 3 is the origin, so:
//   p_local = (p_assembly - origin) . row[axis]     for each axis row
// A direction only rotates. Nothing here assumes an identity placement.
static J occurrence_point_to_model(const J &item, const ProMatrix &position) {
    const double offset[3] = {item.at(0).get<double>() - position[3][0],
                              item.at(1).get<double>() - position[3][1],
                              item.at(2).get<double>() - position[3][2]};
    J result = J::array();
    for (int row = 0; row < 3; row++)
        result.push_back(offset[0] * position[row][0] + offset[1] * position[row][1] +
                         offset[2] * position[row][2]);
    return result;
}

static J occurrence_vector_to_model(const J &item, const ProMatrix &position) {
    const double vector[3] = {item.at(0).get<double>(), item.at(1).get<double>(),
                              item.at(2).get<double>()};
    double local[3] = {0, 0, 0};
    for (int row = 0; row < 3; row++)
        local[row] = vector[0] * position[row][0] + vector[1] * position[row][1] +
                     vector[2] * position[row][2];
    const double length =
        std::sqrt(local[0] * local[0] + local[1] * local[1] + local[2] * local[2]);
    if (length <= 1e-12)
        throw std::runtime_error(
            "geometry_selector axis became degenerate while mapping assembly coordinates into "
            "the component frame; check the occurrence placement");
    J result = J::array();
    for (double value : local)
        result.push_back(value / length);
    return result;
}

static J selector_to_component_model(const J &selector, const ProMatrix &position) {
    J mapped = selector;
    for (const char *key : {"endpoints_mm", "points_mm"}) {
        if (!selector.contains(key))
            continue;
        J points = J::array();
        for (const auto &item : selector[key])
            points.push_back(occurrence_point_to_model(item, position));
        mapped[key] = points;
    }
    for (const char *key : {"point_mm", "center_mm"})
        if (selector.contains(key))
            mapped[key] = occurrence_point_to_model(selector[key], position);
    if (selector.contains("axis"))
        mapped["axis"] = occurrence_vector_to_model(selector["axis"], position);
    mapped["coordinate_space"] = "model";
    return mapped;
}

static J model_point_to_assembly(const J &item, const ProMatrix &position) {
    const double local[3] = {item.at(0).get<double>(), item.at(1).get<double>(),
                             item.at(2).get<double>()};
    J result = J::array();
    for (int col = 0; col < 3; col++)
        result.push_back(position[3][col] + local[0] * position[0][col] +
                         local[1] * position[1][col] + local[2] * position[2][col]);
    return result;
}

static J model_vector_to_assembly(const J &item, const ProMatrix &position) {
    const double local[3] = {item.at(0).get<double>(), item.at(1).get<double>(),
                             item.at(2).get<double>()};
    double world[3] = {0, 0, 0};
    for (int col = 0; col < 3; col++)
        world[col] =
            local[0] * position[0][col] + local[1] * position[1][col] + local[2] * position[2][col];
    const double length =
        std::sqrt(world[0] * world[0] + world[1] * world[1] + world[2] * world[2]);
    if (length <= 1e-12)
        return J::array({world[0], world[1], world[2]});
    return J::array({world[0] / length, world[1] / length, world[2] / length});
}

static GeometrySelectorOutcome match_geometry_selector(const J &selector, const J &state,
                                                       double mm_scale) {
    const std::string target = selector.at("target").get<std::string>();
    const double tolerance = selector.at("tolerance_mm").get<double>();
    if (target == "edge")
        return match_geometry_edge_selector(selector, state, mm_scale, tolerance);
    if (target == "surface")
        return match_geometry_surface_selector(selector, state, mm_scale, tolerance);
    GeometrySelectorOutcome outcome;
    outcome.error = "geometry_selector target must be 'edge' or 'surface', not '" + target + "'";
    return outcome;
}
