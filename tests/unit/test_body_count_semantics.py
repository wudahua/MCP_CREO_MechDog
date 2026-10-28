"""DEV-051 T08B: body counts keep the object count and the material count apart.

Offline only. The native assertions read native/generic.cpp, the projection
assertions feed synthetic inspection payloads; nothing connects to Creo and no
body is created, deleted or renamed here.
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from creo_mechdog.model_queries import RESPONSE_BUDGET, inspection_summary, serialized_size

NATIVE = Path(__file__).resolve().parents[2] / "native"

# ProSolidBody.h (Creo 12.4 Toolkit):
#   PRO_BODY_STATE_NONE=-1, MISSING=0, CONSUMED=1, NO_CONTR_FEAT=2,
#   NO_GEOMETRY=3, ACTIVE=4
ACTIVE = 4
NO_GEOMETRY = 3


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def region(source: str, start: str, stop: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(stop, begin)]


def body_record(body_id: int, state: int, **overrides) -> dict:
    record = {"id": body_id, "state": state, "state_name": "unknown"}
    record.update(overrides)
    return record


def active_body(**overrides) -> dict:
    fields = {
        "state_name": "active",
        "surface_count": 7,
        "has_geometry": True,
        "material": True,
        "bbox": [[0.0, 0.0, 0.0], [185.0, 232.0, 1.0]],
        "bbox_query_code": 0,
    }
    fields.update(overrides)
    return body_record(118, ACTIVE, **fields)


def empty_body(**overrides) -> dict:
    fields = {"state_name": "no_geometry", "has_geometry": None, "material": False}
    fields.update(overrides)
    return body_record(-5778, NO_GEOMETRY, **fields)


def inspection(bodies: list[dict] | None = None, body_counts=None) -> dict:
    if bodies is None:
        bodies = [active_body(), empty_body()]
    if body_counts is None:
        body_counts = {
            "objects": len(bodies),
            "records": len(bodies),
            "active": 1,
            "with_material": 1,
            "without_material": len(bodies) - 1,
            "counts_meaning": {
                "bodies": "body_objects",
                "with_material": "active_bodies_with_surfaces",
            },
        }
    return {
        "healthy": True,
        "has_solid": True,
        "features": [],
        "surfaces": [],
        "edges": [],
        "bodies": bodies,
        "body_counts": body_counts,
    }


class CountSemantics(unittest.TestCase):
    """counts.bodies is the record count; body_counts is the separated view."""

    def test_counts_bodies_keeps_the_record_meaning(self):
        summary = inspection_summary(inspection())
        self.assertEqual(summary["counts"]["bodies"], 2)
        self.assertEqual(summary["body_counts"]["with_material"], 1)

    def test_body_counts_separates_objects_from_material(self):
        counts = inspection_summary(inspection())["body_counts"]
        self.assertEqual(counts["objects"], 2)
        self.assertEqual(counts["records"], 2)
        self.assertEqual(counts["active"], 1)
        self.assertEqual(counts["with_material"], 1)
        self.assertEqual(counts["without_material"], 1)
        self.assertEqual(counts["counts_meaning"]["bodies"], "body_objects")

    def test_empty_and_negative_id_records_are_not_dropped(self):
        source = inspection()
        summary = inspection_summary(source)
        self.assertEqual(summary["counts"]["bodies"], len(source["bodies"]))
        kept = {body["id"]: body for body in source["bodies"]}
        self.assertIn(-5778, kept)
        self.assertIsNone(kept[-5778]["has_geometry"])
        self.assertFalse(kept[-5778]["material"])
        self.assertNotIn("bbox", kept[-5778])

    def test_a_missing_block_is_reported_as_unknown_not_as_zero(self):
        source = inspection()
        source.pop("body_counts")
        summary = inspection_summary(source)
        self.assertIsNone(summary["body_counts"])
        self.assertEqual(summary["counts"]["bodies"], 2)

    def test_partial_counts_do_not_invent_numbers(self):
        counts = inspection_summary(
            inspection(body_counts={"objects": 2, "records": "2", "with_material": -1})
        )["body_counts"]
        self.assertEqual(counts["objects"], 2)
        self.assertIsNone(counts["records"])
        self.assertIsNone(counts["with_material"])
        self.assertIsNone(counts["active"])
        self.assertNotIn("counts_meaning", counts)

    def test_projection_does_not_mutate_the_inspection(self):
        source = inspection()
        before = copy.deepcopy(source)
        inspection_summary(source)
        self.assertEqual(source, before)

    def test_the_separated_block_fits_the_response_budget(self):
        bodies = [active_body() if index == 0 else empty_body(id=index) for index in range(40)]
        summary = inspection_summary(inspection(bodies=bodies))
        self.assertLess(serialized_size(summary), RESPONSE_BUDGET)


class NativeBodyInventory(unittest.TestCase):
    """The native record carries the state, the surfaces and the membership."""

    def setUp(self):
        self.source = native_source("generic.cpp")
        self.block = region(self.source, "int active_bodies = 0, material_bodies = 0;", "if (list)")

    def test_every_record_keeps_its_state_name_and_surface_count(self):
        for token in (
            "state_name",
            "body_state_name(state)",
            "surface_count",
            "material",
            "bbox_query_code",
            "if (surfaces > 0)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.block)

    def test_the_state_names_cover_the_declared_enum(self):
        helper = region(self.source, "static const char *body_state_name", "static J inspection(")
        for token in (
            "PRO_BODY_STATE_ACTIVE",
            "PRO_BODY_STATE_NO_GEOMETRY",
            "PRO_BODY_STATE_NO_CONTR_FEAT",
            "PRO_BODY_STATE_CONSUMED",
            "PRO_BODY_STATE_MISSING",
            "PRO_BODY_STATE_NONE",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)
        self.assertIn("unknown", helper)

    def test_non_active_records_are_kept_without_a_geometry_claim(self):
        non_active = region(self.block, "} else {", "bodies.push_back(b);")
        self.assertIn('b["material"] = false;', non_active)
        self.assertIn('b["has_geometry"] = nullptr;', non_active)
        self.assertNotIn("ProSolidBodyDelete", self.block)

    def test_every_enumerated_record_is_pushed_without_filtering(self):
        self.assertEqual(self.block.count("bodies.push_back(b);"), 1)
        for token in ("if (list[i].id >", "continue;"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.block)

    def test_the_material_count_only_grows_for_a_body_with_surfaces(self):
        guarded = region(self.block, "if (surfaces > 0) {", "} else {")
        self.assertIn("material_bodies++;", guarded)
        self.assertIn("active_bodies++;", self.block)
        self.assertNotIn("material_bodies--", self.block)
        self.assertNotIn("active_bodies - 1", self.block)

    def test_the_separated_block_is_published_and_null_for_assemblies(self):
        published = region(self.source, "J body_counts = nullptr;", "J result = ")
        self.assertIn("if (!isasm)", published)
        for token in (
            "objects",
            "records",
            "with_material",
            "without_material",
            "counts_meaning",
        ):
            with self.subTest(token=token):
                self.assertIn('"' + token + '"', published)
        self.assertIn('{"body_counts", body_counts}', self.source)


if __name__ == "__main__":
    unittest.main()
