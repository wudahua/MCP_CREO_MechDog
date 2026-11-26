// DEV-089 T3: composed open-polyline base flange.
//
// Creo's own polyline base flange cannot be built from the documented element
// trees on Creo 12.4.0.0 (six measured attempts, DEV-089 "实机尝试：T3"), so the
// open 90-degree chain is composed from two already verified primitives:
//
//   1. `sheetmetal_planar_wall` builds the first leg as the rectangular
//      unattached wall (length = first leg, width = sheet width, one-sided
//      gauge along +normal);
//   2. `sheetmetal_flange` attaches to that wall's free end edge and bends 90
//      degrees, giving the second leg.
//
// Two live probes (2026-11-15) fixed the geometry this file relies on:
//   * the flange height carries the plate gauge, so a free second leg of L2
//     needs height = L2 + thickness (h=12 -> 10 mm free, h=14 -> 12 mm free);
//   * the flange grows on the opposite side of the plate and its own thickness
//     stays inside the plate's end face, so the composed envelope is
//     first_leg x width x (second_leg + thickness);
//   * the bend removes the quarter annulus between the inside radius and
//     radius + thickness; both probes matched that bound to 0.002 mm3
//     (see creo_mechdog.sheetmetal.base_flange_expected_volume).
//
// The result is deliberately published as two features (`composed_features`),
// never as one base flange: the wall stays addressable as <label>, the flange
// as <label>_leg2 and the driving sketch as <label>_sk.

static double base_flange_v_distance(const V &first, const V &second) {
    double total = 0;
    for (int axis = 0; axis < 3; axis++) {
        double delta = first[axis] - second[axis];
        total += delta * delta;
    }
    return std::sqrt(total);
}

static bool base_flange_entity_point(const J &entity, const char *key, V &point) {
    if (!entity.is_object() || !entity.contains(key))
        return false;
    const J &value = entity[key];
    if (!value.is_array() || value.size() != 3)
        return false;
    for (auto coordinate : value)
        if (!coordinate.is_number() || !std::isfinite(coordinate.get<double>()))
            return false;
    point = {value[0].get<double>(), value[1].get<double>(), value[2].get<double>()};
    return true;
}

static J base_flange_placed_point(const V &origin, const V &u_axis, const V &v_axis, const V &n,
                                  double u, double v, double n_value) {
    return J::array({origin[0] + u_axis[0] * u + v_axis[0] * v + n[0] * n_value,
                     origin[1] + u_axis[1] * u + v_axis[1] * v + n[1] * n_value,
                     origin[2] + u_axis[2] * u + v_axis[2] * v + n[2] * n_value});
}

static void generic_sheetmetal_base_flange(const J &op) {
    std::string label = op.at("label").get<std::string>();
    // The composed operation also creates <label>_sk and <label>_leg2; all three
    // are real Creo feature names under the 28 character limit.
    if (label.size() > 22)
        throw std::runtime_error(
            "sheetmetal_base_flange label must be at most 22 characters: the operation also "
            "creates <label>_sk and <label>_leg2");
    J section = op.at("section");
    if (!section.is_array())
        throw std::runtime_error("sheetmetal_base_flange section must be an array of entities");
    std::vector<V> starts, ends;
    for (auto entity : section) {
        std::string type =
            entity.is_object() && entity.contains("type") && entity["type"].is_string()
                ? entity["type"].get<std::string>()
                : std::string();
        if (entity.is_object() &&
            (type == "centerline" || entity.value("construction", false) == true))
            continue;
        if (type != "line")
            throw std::runtime_error(
                "sheetmetal_base_flange admits straight lines only in this batch; got " +
                (type.empty() ? std::string("<no type>") : type));
        V start = {0, 0, 0}, end = {0, 0, 0};
        if (!base_flange_entity_point(entity, "start", start) ||
            !base_flange_entity_point(entity, "end", end))
            throw std::runtime_error(
                "sheetmetal_base_flange lines need finite [x,y,z] start and end points");
        if (base_flange_v_distance(start, end) <= 1e-9)
            throw std::runtime_error("sheetmetal_base_flange lines must not be zero length");
        starts.push_back(start);
        ends.push_back(end);
    }
    if (starts.size() != 2)
        throw std::runtime_error(
            "sheetmetal_base_flange composes exactly two straight lines in this batch; got " +
            std::to_string(starts.size()));

    V corner = ends[0];
    if (base_flange_v_distance(corner, starts[1]) > 1e-9)
        throw std::runtime_error(
            "sheetmetal_base_flange segments 0 and 1 are not connected end-to-start; the chain "
            "must be continuous in the given order and must not branch");
    V far_first = starts[0];
    V far_second = ends[1];
    V first_direction = {far_first[0] - corner[0], far_first[1] - corner[1],
                         far_first[2] - corner[2]};
    V second_direction = {far_second[0] - corner[0], far_second[1] - corner[1],
                          far_second[2] - corner[2]};
    double first_leg = base_flange_v_distance(far_first, corner);
    double second_leg = base_flange_v_distance(far_second, corner);
    double corner_dot = dot(first_direction, second_direction);
    if (first_leg <= 0 || second_leg <= 0 || fabs(corner_dot) > 1e-6 * first_leg * second_leg)
        throw std::runtime_error(
            "sheetmetal_base_flange composes a 90 degree bend only: the two legs must be "
            "perpendicular, so a collinear chain or another bend angle has no composed "
            "counterpart in this batch");

    const std::string direction = op.value("direction", "positive");
    const bool flip_thickness = op.value("flip_thickness", false);
    double width = op["width"].get<double>();
    double thickness = op["thickness"].get<double>();
    double radius = op.value("radius", 1.0);
    double k_factor = op.value("k_factor", 0.5);
    if (!(k_factor > 0.0 && k_factor <= 1.0))
        throw std::runtime_error(
            "sheetmetal_base_flange k_factor must be greater than 0 and at most 1");
    double y_factor = k_factor * acos(-1.0) / 2.0;
    std::string sketch_label = label + "_sk";
    std::string flange_label = label + "_leg2";
    if (alias_entry(label) || alias_entry(sketch_label) || alias_entry(flange_label))
        throw std::runtime_error(
            "sheetmetal_base_flange would create " + label + ", " + sketch_label + " and " +
            flange_label +
            ", but one of those names already exists in this model; managed labels are never "
            "overwritten");

    // 1) First leg: the rectangular unattached wall.
    J wall_op = {{"op", "sheetmetal_planar_wall"},
                 {"label", label},
                 {"plane", op.value("plane", J("XY"))},
                 {"length", first_leg},
                 {"width", width},
                 {"thickness", thickness},
                 {"direction", direction},
                 {"origin", op.value("origin", J::array({0.0, 0.0}))}};
    try {
        generic_sheetmetal_planar_wall(wall_op);
    } catch (const std::exception &error) {
        throw std::runtime_error(std::string("sheetmetal_base_flange first leg failed: ") +
                                 error.what());
    }

    // 2) Second leg: the flange on the wall's free end edge. The wall recorded
    //    its own measured frame, so the edge is named by geometry instead of a
    //    guessed element id, and the recorded origin places the rectangle.
    const J *wall_meta = alias_entry(label);
    if (!wall_meta || !wall_meta->contains("planar_wall"))
        throw std::runtime_error(
            "sheetmetal_base_flange created the wall but its recorded planar_wall frame is "
            "missing; the flange placement cannot be derived");
    J record = (*wall_meta)["planar_wall"];
    J frame = record.at("frame");
    J recorded_origin = record.value("origin", J::array({0.0, 0.0}));
    double u0 = recorded_origin[0].get<double>();
    double v0 = recorded_origin[1].get<double>();
    V origin = vec(frame["origin"]), u_axis = vec(frame["u_axis"]), v_axis = vec(frame["v_axis"]),
      normal = vec(frame["normal"]);
    J endpoints =
        J::array({base_flange_placed_point(origin, u_axis, v_axis, normal, u0 + first_leg, v0, 0.0),
                  base_flange_placed_point(origin, u_axis, v_axis, normal, u0 + first_leg,
                                           v0 + width, 0.0)});
    log("BASE_FLANGE_EDGE u=%.9f v0=%.9f v1=%.9f first=%.9f second=%.9f\n", u0 + first_leg, v0,
        v0 + width, first_leg, second_leg);
    J flange_op = {
        {"op", "sheetmetal_flange"},
        {"label", flange_label},
        {"edge", J{{"kind", "edge_geometry"}, {"endpoints_mm", endpoints}, {"tolerance_mm", 1e-4}}},
        {"height", second_leg + thickness},
        {"angle", 90.0},
        {"radius", radius},
        {"y_factor", y_factor},
        {"flip", false},
        {"flip_thickness", flip_thickness}};
    try {
        generic_sheetmetal_flange(flange_op);
    } catch (const std::exception &error) {
        throw std::runtime_error(std::string("sheetmetal_base_flange second leg failed: ") +
                                 error.what());
    }

    // 3) Accept only on measured evidence: the composed volume bound, the
    //    sheetmetal body and the signed frame envelope.
    J state = inspection();
    double measured = planar_wall_measured_volume(state);
    const double first_extent = first_leg + (flip_thickness ? thickness : 0.0);
    double straight = (first_extent + second_leg) * width * thickness;
    double removed = (1.0 - acos(-1.0) / 4.0) *
                     ((radius + thickness) * (radius + thickness) - radius * radius) * width;
    double expected = straight - removed;
    double tolerance = std::max(1.0, fabs(expected) * 0.005);
    log("BASE_FLANGE_VOLUME measured=%.9f expected=%.9f delta=%.9f tolerance=%.9f\n", measured,
        expected, measured - expected, tolerance);
    if (fabs(measured - expected) > tolerance)
        throw std::runtime_error(
            "sheetmetal_base_flange measured " + std::to_string(measured) +
            " mm3 instead of the composed bound " + std::to_string(expected) + " mm3 (two legs " +
            std::to_string(first_leg) + " / " + std::to_string(second_leg) + " mm, thickness " +
            std::to_string(thickness) + " mm, bend radius " + std::to_string(radius) +
            " mm); the wall and the flange do not form the requested L");
    PlanarWallBodies bodies = planar_wall_bodies();
    if (!bodies.sheetmetal)
        throw std::runtime_error(
            "sheetmetal_base_flange built geometry but no body reports the sheetmetal state");
    if (!bodies.material)
        throw std::runtime_error(
            "sheetmetal_base_flange built features but no sheetmetal body carries material");
    J bounds = planar_wall_material_bounds(state);
    J envelope = planar_wall_envelope(bounds, origin, u_axis, v_axis, normal);
    struct BaseFlangeExtent {
        const char *axis;
        double low;
        double high;
    } extents[3] = {{"u", u0, u0 + first_extent},
                    {"v", v0, v0 + width},
                    {"n", direction == "negative" ? -thickness : -second_leg,
                     direction == "negative" ? second_leg : thickness}};
    for (const auto &want : extents) {
        const J &entry = envelope[want.axis];
        double low = entry["min"].get<double>(), high = entry["max"].get<double>();
        if (fabs(low - want.low) > 1e-3 || fabs(high - want.high) > 1e-3)
            throw std::runtime_error(
                "sheetmetal_base_flange envelope " + std::string(want.axis) + " is [" +
                std::to_string(low) + ", " + std::to_string(high) +
                "] mm instead of the composed [" + std::to_string(want.low) + ", " +
                std::to_string(want.high) +
                "] mm; the flange did not attach to the wall's free end on the expected side");
    }

    // 4) BUG-129: report the measured width direction instead of leaving the
    //    caller to guess from `plane`. The direction is the sketch frame's own
    //    v axis; `expected_width_direction_world` only asserts against it and is
    //    never used to rotate or project the rectangle.
    V width_axis = normalized(v_axis);
    const double width_tolerance = op.value("width_direction_tolerance_deg", 0.5);
    if (op.contains("expected_width_direction_world") &&
        !op["expected_width_direction_world"].is_null()) {
        V expected = normalized(vec(op["expected_width_direction_world"]));
        const double limit = std::cos(width_tolerance * acos(-1.0) / 180.0);
        if (fabs(dot(width_axis, expected)) < limit)
            throw std::runtime_error(
                "sheetmetal_base_flange width runs along model v = world (" +
                std::to_string(width_axis[0]) + ", " + std::to_string(width_axis[1]) + ", " +
                std::to_string(width_axis[2]) + ") but expected_width_direction_world is (" +
                std::to_string(expected[0]) + ", " + std::to_string(expected[1]) + ", " +
                std::to_string(expected[2]) + ") within " + std::to_string(width_tolerance) +
                " deg; choose the plane that gives the expected frame instead of treating this "
                "assertion as a rotation");
    }
    log("BASE_FLANGE_WIDTH_AXIS x=%.9f y=%.9f z=%.9f\n", width_axis[0], width_axis[1],
        width_axis[2]);
    J mass = mass_properties_json(J::object());

    // 5) One terminal record for the requested operation, listing the two
    //    features it really created instead of pretending to be one feature.
    const J *flange_meta = alias_entry(flange_label);
    J composed = J::array();
    composed.push_back({{"op", "sheetmetal_planar_wall"},
                        {"label", label},
                        {"feature_id", wall_meta->value("feature_id", J(nullptr))},
                        {"length_mm", first_leg},
                        {"width_mm", width},
                        {"thickness_mm", thickness}});
    composed.push_back(
        {{"op", "sheetmetal_flange"},
         {"label", flange_label},
         {"feature_id", flange_meta ? flange_meta->value("feature_id", J(nullptr)) : J(nullptr)},
         {"height_mm", second_leg + thickness},
         {"angle_deg", 90.0},
         {"radius_mm", radius}});
    J envelope_mm = {
        {"u", J::array({envelope["u"]["min"], envelope["u"]["max"]})},
        {"v", J::array({envelope["v"]["min"], envelope["v"]["max"]})},
        {"n", J::array({envelope["n"]["min"], envelope["n"]["max"]})},
    };
    stage_operation_result(
        {{"op", "sheetmetal_base_flange"},
         {"feature", label},
         {"feature_id", wall_meta->value("feature_id", J(nullptr))},
         {"composed", true},
         {"single_feature", false},
         {"composed_features", composed},
         {"sketch", sketch_label},
         {"flange_label", flange_label},
         {"first_leg_mm", first_leg},
         {"second_leg_mm", second_leg},
         {"width_mm", width},
         {"thickness_mm", thickness},
         {"radius_mm", radius},
         {"k_factor", k_factor},
         {"y_factor", y_factor},
         {"bend_angle_deg", 90.0},
         {"flange_height_mm", second_leg + thickness},
         {"direction", direction},
         {"flip_thickness", flip_thickness},
         {"u_extension_from_flip_thickness_mm", flip_thickness ? thickness : 0.0},
         {"volume_mm3", measured},
         {"expected_volume_mm3", expected},
         {"volume_delta_mm3", measured - expected},
         {"straight_volume_mm3", straight},
         {"bend_removed_mm3", removed},
         {"frame", frame},
         {"envelope", envelope},
         {"envelope_mm", envelope_mm},
         {"bounds_mm", bounds},
         {"width_direction_frame", "model"},
         {"width_direction_world", xyz(width_axis.data())},
         {"width_direction_tolerance_deg", width_tolerance},
         {"width_expected", op.value("expected_width_direction_world", J(nullptr))},
         {"center_of_mass_mm", mass.value("center_of_mass_mm", J(nullptr))},
         {"sheetmetal_body", bodies.sheetmetal > 0},
         {"material_bodies", bodies.material}});
}
