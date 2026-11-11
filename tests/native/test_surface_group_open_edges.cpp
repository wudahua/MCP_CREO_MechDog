// FEAT-065 T1b: execute the production open-edge record builder of
// native/surface_group.cpp without any Toolkit call. The unit test extracts
// the block between "struct GroupOpenEdgeRecords" and "// Group-state
// decision." into open_edges_under_test.inc; the stand-ins below mirror only
// the fields that block reads.
#include <cmath>
#include <limits>
#include <vector>
#include "../../native/third_party/json.hpp"
using J = nlohmann::json;

typedef int ProError;

struct GroupPoint {
    double v[3] = {0.0, 0.0, 0.0};
};

struct GroupBoundaryEdge {
    int edge_id = -1;
    int surface_id = -1;
    int quilt_index = -1;
    double length = 0.0;
    std::vector<GroupPoint> points;
    bool joined = false;
    ProError id_code = 0;
    ProError sample_code = 0;
    ProError endpoints_code = 0;
    bool endpoints_ok = false;
    GroupPoint endpoints[2];
};

#include "open_edges_under_test.inc"

static GroupBoundaryEdge edge(int id, int surface, int quilt, double x0, double x1, bool joined) {
    GroupBoundaryEdge out;
    out.edge_id = id;
    out.surface_id = surface;
    out.quilt_index = quilt;
    out.length = x1 - x0;
    out.points = {{{x0, 0.0, 0.0}}, {{x1, 0.0, 0.0}}};
    out.joined = joined;
    out.endpoints_ok = true;
    out.endpoints[0] = {{x0, 0.0, 10.0}};
    out.endpoints[1] = {{x1, 0.0, 10.0}};
    return out;
}

int main() {
    const std::vector<int> quilts = {21, 22};
    // A joined edge is never listed; open edges keep visit order and map the
    // quilt index to the quilt id.
    std::vector<GroupBoundaryEdge> edges = {edge(101, 31, 0, 0.0, 40.0, false),
                                            edge(102, 31, 0, 0.0, 40.0, true),
                                            edge(201, 41, 1, 0.0, 20.0, false)};
    GroupOpenEdgeRecords out = group_open_edge_records(edges, quilts, true, 1.0, 32);
    if (out.total != 2 || out.truncated || out.records.size() != 2)
        return 1;
    const J &first = out.records[0];
    if (first["edge_id"] != 101 || first["surface_id"] != 31 || first["quilt_id"] != 21)
        return 2;
    if (first["length_mm"] != 40.0 || first["endpoints_mm"][1][0] != 40.0 ||
        first["endpoints_mm"][0][2] != 10.0 || first.contains("reason"))
        return 3;
    if (out.records[1]["edge_id"] != 201 || out.records[1]["quilt_id"] != 22)
        return 4;

    // The scale converts both the length and the endpoints (inches -> mm).
    out = group_open_edge_records(edges, quilts, true, 25.4, 32);
    if (std::fabs(out.records[0]["length_mm"].get<double>() - 1016.0) > 1e-9 ||
        std::fabs(out.records[0]["endpoints_mm"][0][2].get<double>() - 254.0) > 1e-9)
        return 5;

    // Unknown unit scale: ids stay, every mm value is null, no per-record
    // reason (the shared status carries unit_scale_unknown).
    out = group_open_edge_records(edges, quilts, false, 1.0, 32);
    if (out.records.size() != 2 || out.records[0]["edge_id"] != 101 ||
        !out.records[0]["length_mm"].is_null() || !out.records[0]["endpoints_mm"].is_null() ||
        out.records[0].contains("reason"))
        return 6;

    // The bound: only `limit` records, the rest still counted.
    std::vector<GroupBoundaryEdge> many;
    for (int index = 0; index < 5; index++)
        many.push_back(edge(300 + index, 50, 0, 0.0, 1.0 + index, false));
    out = group_open_edge_records(many, quilts, true, 1.0, 3);
    if (out.total != 5 || !out.truncated || out.records.size() != 3 ||
        out.records[2]["edge_id"] != 302)
        return 7;
    out = group_open_edge_records(many, quilts, true, 1.0, 5);
    if (out.total != 5 || out.truncated || out.records.size() != 5)
        return 8;

    // Per-value failures null only that value and name it with the raw code;
    // the failure counters cover every open edge, listed or not.
    GroupBoundaryEdge unnamed = edge(-1, 31, 0, 0.0, 40.0, false);
    unnamed.id_code = -2;
    GroupBoundaryEdge no_ends = edge(401, 31, 0, 0.0, 40.0, false);
    no_ends.endpoints_ok = false;
    no_ends.endpoints_code = -3;
    GroupBoundaryEdge no_samples = edge(402, 31, 5, 0.0, 40.0, false);
    no_samples.points.clear();
    no_samples.length = 0.0;
    no_samples.sample_code = -4;
    out = group_open_edge_records({unnamed, no_ends, no_samples}, quilts, true, 1.0, 32);
    if (out.edge_id_failures != 1 || out.endpoint_failures != 1 || out.length_failures != 1)
        return 9;
    if (!out.records[0]["edge_id"].is_null() || out.records[0]["reason"] != "edge_id_unavailable" ||
        out.records[0]["query_code"] != -2)
        return 10;
    if (!out.records[1]["endpoints_mm"].is_null() || out.records[1]["length_mm"] != 40.0 ||
        out.records[1]["reason"] != "endpoint_eval_failed" || out.records[1]["query_code"] != -3)
        return 11;
    if (!out.records[2]["length_mm"].is_null() || out.records[2]["endpoints_mm"].is_null() ||
        out.records[2]["reason"] != "edge_sampling_failed" || out.records[2]["query_code"] != -4 ||
        !out.records[2]["quilt_id"].is_null())
        return 12;

    // A non-finite length is not published.
    GroupBoundaryEdge infinite = edge(501, 31, 0, 0.0, 40.0, false);
    infinite.length = std::numeric_limits<double>::infinity();
    out = group_open_edge_records({infinite}, quilts, true, 1.0, 32);
    if (!out.records[0]["length_mm"].is_null() || out.length_failures != 1)
        return 13;

    // Everything joined: an empty list, not null.
    out = group_open_edge_records({edge(601, 31, 0, 0.0, 1.0, true)}, quilts, true, 1.0, 32);
    if (out.total != 0 || out.truncated || !out.records.is_array() || !out.records.empty())
        return 14;
    return 0;
}
