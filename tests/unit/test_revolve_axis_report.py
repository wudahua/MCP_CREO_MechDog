"""FEAT-008/BUG-083 T09B: actual revolve-axis reporting contract (offline).

Covered: explicit datum axis, surface-resolved axis, internal centerline
fallback, multiple centerlines, no centerline and invalid axis. The report
must state the actually resolved axis (source/kind/id, origin/direction,
length_unit, geometry_known and query codes); measured values only ever come
from an actual axis or section centerline query and unknown is never
backfilled from the request.
"""

import copy
import unittest

from creo_mechdog.operation_results import (
    annotate_native_result,
    normalize_revolve_axis,
)
from creo_mechdog.references import normalize_revolve_axis as admit_revolve_axis
from creo_mechdog.schema import SketchOp


def model_frame_block(**overrides):
    block = {
        "source": "explicit",
        "kind": "datum_axis",
        "id": 83,
        "frame": "model",
        "origin": [0.0, 0.0, 0.0],
        "direction": [0.0, 0.0, 1.0],
        "length_unit": {"name": "mm", "query_code": 0},
        "geometry_known": True,
        "query_code": 0,
        "resolution": {
            "feature_axis_query_code": 0,
            "axis_item_query_code": 0,
            "axis_surface_query_code": -1,
            "section_centerline_count": None,
            "section_query_code": None,
        },
    }
    block.update(overrides)
    return block


def revolve_record(block=None):
    record = {
        "op": "revolve",
        "index": 0,
        "label": "ring",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "unknown",
    }
    if block is not None:
        record["revolve_axis"] = block
    return record


class ResolvedAxisProjection(unittest.TestCase):
    def test_explicit_datum_axis_passes_measured_values(self):
        entry = normalize_revolve_axis(model_frame_block())
        self.assertEqual(entry["source"], "explicit")
        self.assertEqual(entry["kind"], "datum_axis")
        self.assertEqual(entry["id"], 83)
        self.assertEqual(entry["frame"], "model")
        self.assertEqual(entry["origin"], [0.0, 0.0, 0.0])
        self.assertEqual(entry["direction"], [0.0, 0.0, 1.0])
        self.assertTrue(entry["geometry_known"])
        self.assertEqual(entry["length_unit"], {"name": "mm", "query_code": 0})
        self.assertEqual(entry["resolution"]["axis_surface_query_code"], -1)

    def test_surface_resolved_axis_kind_is_kept(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                kind="surface",
                id=52,
                resolution={
                    "feature_axis_query_code": 0,
                    "axis_item_query_code": 0,
                    "axis_surface_query_code": 0,
                    "section_centerline_count": None,
                    "section_query_code": None,
                },
            )
        )
        self.assertEqual(entry["kind"], "surface")
        self.assertEqual(entry["id"], 52)
        self.assertTrue(entry["geometry_known"])

    def test_internal_centerline_fallback_reports_source_and_kind(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=7,
                resolution={
                    "feature_axis_query_code": 0,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 1,
                    "section_query_code": 0,
                },
            )
        )
        self.assertEqual(entry["source"], "internal_centerline")
        self.assertEqual(entry["kind"], "section_centerline")
        self.assertEqual(entry["id"], 7)
        self.assertEqual(entry["resolution"]["section_centerline_count"], 1)

    def test_internal_section_frame_geometry_is_2d_and_explicit(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=7,
                frame="sketch_local",
                origin=[10.0, 0.0],
                direction=[0.0, 1.0],
                resolution={
                    "feature_axis_query_code": -1,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 1,
                    "section_query_code": 0,
                },
            )
        )
        self.assertEqual(entry["frame"], "sketch_local")
        self.assertEqual(entry["origin"], [10.0, 0.0])
        self.assertEqual(entry["direction"], [0.0, 1.0])
        self.assertTrue(entry["geometry_known"])

    def test_multiple_centerlines_keep_count_and_never_guess_an_id(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=None,
                frame=None,
                origin=None,
                direction=None,
                geometry_known=False,
                query_code=None,
                resolution={
                    "feature_axis_query_code": -1,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 2,
                    "section_query_code": 0,
                },
            )
        )
        self.assertIsNone(entry["id"])
        self.assertFalse(entry["geometry_known"])
        self.assertIsNone(entry["origin"])
        self.assertEqual(entry["resolution"]["section_centerline_count"], 2)

    def test_no_centerline_reports_zero_count_without_values(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=None,
                frame=None,
                origin=None,
                direction=None,
                geometry_known=False,
                query_code=None,
                resolution={
                    "feature_axis_query_code": -1,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 0,
                    "section_query_code": 0,
                },
            )
        )
        self.assertEqual(entry["resolution"]["section_centerline_count"], 0)
        self.assertFalse(entry["geometry_known"])
        self.assertIsNone(entry["id"])

    def test_inconsistent_measured_fields_degrade_to_unknown(self):
        broken = [
            model_frame_block(geometry_known=False),
            model_frame_block(origin=None),
            model_frame_block(direction=[0.0, float("nan"), 1.0]),
            model_frame_block(frame="part_local"),
            model_frame_block(frame="sketch_local", origin=[1.0, 2.0, 3.0]),
        ]
        for block in broken:
            with self.subTest(block=block):
                entry = normalize_revolve_axis(block)
                self.assertFalse(entry["geometry_known"])
                self.assertIsNone(entry["origin"])
                self.assertIsNone(entry["direction"])
                self.assertIsNone(entry["frame"])

    def test_invalid_enums_and_ids_stay_unknown(self):
        entry = normalize_revolve_axis(
            model_frame_block(source="guess", kind="revolve_axis", id="83", query_code="0")
        )
        self.assertEqual(entry["source"], "unknown")
        self.assertEqual(entry["kind"], "unknown")
        self.assertIsNone(entry["id"])
        self.assertIsNone(entry["query_code"])

    def test_non_dict_block_becomes_explicit_unknown(self):
        entry = normalize_revolve_axis("revolve about x")
        self.assertEqual(entry["source"], "unknown")
        self.assertFalse(entry["geometry_known"])
        self.assertEqual(
            entry["resolution"],
            {
                "feature_axis_query_code": None,
                "axis_item_query_code": None,
                "axis_surface_query_code": None,
                "section_centerline_count": None,
                "section_query_code": None,
            },
        )

    def test_length_unit_only_passes_a_query_block(self):
        self.assertIsNone(
            normalize_revolve_axis(model_frame_block(length_unit="mm"))["length_unit"]
        )
        entry = normalize_revolve_axis(
            model_frame_block(length_unit={"name": None, "query_code": -3})
        )
        self.assertEqual(entry["length_unit"], {"name": None, "query_code": -3})


class CenterlineAccountingContract(unittest.TestCase):
    """Count accounting fixed for DEV-051 T09B (one drawn line counted as 3).

    The native executor now filters the sketch's system reference projections
    out of ``section_centerline_count`` (``ProSectionEntityIsProjection``), so
    one drawn centerline counts as 1 and its sketch section entity id becomes
    ``id``. Truly multiple user centerlines keep the count and never receive a
    guessed id. The projection layer must carry both verbatim: it never
    reinterprets an inflated or ambiguous count into a single-line pick.
    """

    def test_single_user_centerline_count_one_with_entity_id(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=17,
                frame=None,
                origin=[0.0, -5.0],
                direction=[0.0, 1.0],
                geometry_known=True,
                query_code=0,
                resolution={
                    "feature_axis_query_code": 0,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 1,
                    "section_query_code": 0,
                },
            )
        )
        self.assertEqual(entry["resolution"]["section_centerline_count"], 1)
        self.assertEqual(entry["id"], 17)
        self.assertEqual(entry["kind"], "section_centerline")

    def test_inflated_reference_count_is_reported_verbatim_never_reinterpreted(self):
        # Shape the broken build produced on 10-29 (two system reference
        # projections counted with one user line): the projection keeps the
        # count and the null id exactly as measured - it must not shrink the
        # count to 1 or invent id=<first line>.
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=None,
                frame="model",
                origin=[0.0, -5.0, 0.0],
                direction=[0.0, 1.0, 0.0],
                geometry_known=True,
                query_code=0,
                resolution={
                    "feature_axis_query_code": 0,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 3,
                    "section_query_code": 0,
                },
            )
        )
        self.assertEqual(entry["resolution"]["section_centerline_count"], 3)
        self.assertIsNone(entry["id"])

    def test_two_true_user_centerlines_stay_ambiguous_without_a_guessed_id(self):
        entry = normalize_revolve_axis(
            model_frame_block(
                source="internal_centerline",
                kind="section_centerline",
                id=None,
                frame=None,
                origin=None,
                direction=None,
                geometry_known=False,
                query_code=None,
                resolution={
                    "feature_axis_query_code": -1,
                    "axis_item_query_code": None,
                    "axis_surface_query_code": None,
                    "section_centerline_count": 2,
                    "section_query_code": 0,
                },
            )
        )
        self.assertEqual(entry["resolution"]["section_centerline_count"], 2)
        self.assertIsNone(entry["id"])
        self.assertFalse(entry["geometry_known"])


class SketchEntityIdSourcePublication(unittest.TestCase):
    """The sketch operation record carries ``entity_ids`` (10-31 live gap).

    The T09B id-source contract compares ``revolve_axis.id`` with the sketch
    section entity id of the drawn centerline; the 10-31 live run could not
    verify that source because the sketch operation record published no
    ``entity_ids`` at all. The native executor now records them on the result,
    and normalization must carry the mapping through untouched so the driver's
    documented source stays client-visible.
    """

    def test_sketch_entity_ids_survive_result_annotation(self):
        result = {
            "operations": [
                {
                    "op": "sketch",
                    "index": 0,
                    "label": "ring_sketch",
                    "entity_ids": {"ring_0": 5, "ring_1": 6, "spin_centerline": 9},
                }
            ]
        }
        annotate_native_result(result, readonly=False)
        record = result["operations"][0]
        self.assertEqual(record["entity_ids"], {"ring_0": 5, "ring_1": 6, "spin_centerline": 9})

    def test_fixed_centerline_accounting_shape_passes_through(self):
        # The fixed native accounting (one drawn line -> count 1 and its sketch
        # section entity id) must reach the client verbatim; the projection
        # never re-derives or re-guesses the id.
        result = {
            "operations": [
                revolve_record(
                    model_frame_block(
                        source="internal_centerline",
                        kind="section_centerline",
                        id=9,
                        frame="sketch_local",
                        origin=[0.0, -10.0],
                        direction=[0.0, 1.0],
                        geometry_known=True,
                        query_code=0,
                        resolution={
                            "feature_axis_query_code": 0,
                            "axis_item_query_code": None,
                            "axis_surface_query_code": None,
                            "section_centerline_count": 1,
                            "section_query_code": 0,
                        },
                    )
                )
            ]
        }
        annotate_native_result(result, readonly=False)
        entry = result["operations"][0]["revolve_axis"]
        self.assertEqual(entry["id"], 9)
        self.assertEqual(entry["resolution"]["section_centerline_count"], 1)
        self.assertEqual(entry["frame"], "sketch_local")


class NoRequestEcho(unittest.TestCase):
    def test_missing_block_stays_missing_and_is_not_fabricated(self):
        request_axis = {"kind": "datum_axis_feature", "label": "axis_label"}
        result = {"operations": [revolve_record(None)]}
        result["operations"][0]["request_axis"] = copy.deepcopy(request_axis)
        annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "revolve", "label": "ring", "axis": request_axis}],
        )
        self.assertNotIn("revolve_axis", result["operations"][0])

    def test_unknown_block_never_carries_request_values(self):
        request_axis = {"kind": "axis", "id": 83}
        block = {"source": "explicit", "kind": "datum_axis", "id": 83}
        result = {"operations": [revolve_record(block)]}
        annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "revolve", "label": "ring", "axis": request_axis}],
        )
        entry = result["operations"][0]["revolve_axis"]
        self.assertFalse(entry["geometry_known"])
        self.assertIsNone(entry["origin"])
        self.assertIsNone(entry["direction"])

    def test_other_operations_get_no_axis_block(self):
        result = {"operations": [{"op": "extrude", "index": 0, "label": "pad", "depth": 4.0}]}
        annotate_native_result(result, readonly=False)
        (record,) = result["operations"]
        self.assertNotIn("revolve_axis", record)
        self.assertEqual(record["op"], "extrude")
        self.assertEqual(record["depth"], 4.0)


class AdmissionCompatibility(unittest.TestCase):
    def test_omitted_and_null_axis_keep_the_internal_fallback(self):
        self.assertNotIn("axis", admit_revolve_axis({"kind": "axis", "id": 1}))
        sketch = SketchOp.model_validate(
            {
                "op": "sketch",
                "label": "sec",
                "entities": [{"type": "centerline", "name": "cl", "start": [0, -5], "end": [0, 5]}],
            }
        )
        self.assertEqual(len(sketch.entities), 1)

    def test_current_admission_still_rejects_non_axis_kinds(self):
        # A surface reference is not admitted as a revolve axis today; the
        # surface-resolved case is an axis geomitem owned by surface geometry,
        # reached through {kind:"axis",id:N} or a non-datum axis feature label.
        for bad in ({"kind": "surface", "id": 5}, {"entity": "ax"}, {}, {"kind": "axis"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    admit_revolve_axis(bad)

    def test_multi_centerline_sketch_rule_is_unchanged(self):
        # Existing admission: a sketch created through this service carries at
        # most one construction centerline. No tightening was added here; a
        # future tightening of the multi-centerline fallback must record its
        # version impact explicitly.
        with self.assertRaisesRegex(ValueError, "One revolve centerline"):
            SketchOp.model_validate(
                {
                    "op": "sketch",
                    "label": "sec",
                    "entities": [
                        {"type": "centerline", "name": "cl0", "start": [0, -5], "end": [0, 5]},
                        {"type": "centerline", "name": "cl1", "start": [5, -5], "end": [5, 5]},
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
