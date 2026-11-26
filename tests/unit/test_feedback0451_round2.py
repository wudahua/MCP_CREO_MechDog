"""Unit tests for 0.45.1 feedback items: BUG-194, BUG-195, FEAT-091, FEAT-092."""

from __future__ import annotations

import asyncio
import pathlib
import unittest

from pydantic import ValidationError

from creo_mechdog import schema, server, sketch_regions

ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestFeedback0451Round2(unittest.TestCase):
    def test_round_op_expected_assertions(self) -> None:
        ok = schema.RoundOp(
            op="round",
            label="r1",
            size=5.0,
            references=[{"edge": {"kind": "edge", "id": 1}}],
            expected_round_kind="convex",
            expected_material_delta_sign="negative",
        )
        self.assertEqual(ok.expected_round_kind, "convex")
        self.assertEqual(ok.expected_material_delta_sign, "negative")
        dumped = ok.model_dump(exclude_none=True)
        self.assertEqual(dumped["expected_round_kind"], "convex")
        self.assertEqual(dumped["expected_material_delta_sign"], "negative")

        with self.assertRaises(ValidationError):
            schema.RoundOp(
                op="round",
                label="r2",
                size=5.0,
                references=[{"edge": {"kind": "edge", "id": 1}}],
                expected_round_kind="convex",
                expected_material_delta_sign="positive",
            )

    def test_region_closed_chain_adaptation(self) -> None:
        sketch = {
            "op": "sketch",
            "label": "sk_src",
            "plane": "XY",
            "entities": [
                {"type": "line", "name": "e0", "start": [0.0, 0.0], "end": [10.0, 0.0]},
                {"type": "line", "name": "e1", "start": [10.0, 0.0], "end": [10.0, 5.0]},
                {
                    "type": "b_spline",
                    "name": "sp0",
                    "degree": 2,
                    "control_points": [[0.0, 0.0], [5.0, 5.0], [10.0, 5.0]],
                },
            ],
        }
        extrude = schema.ExtrudeOp(
            op="extrude",
            label="cut1",
            sketch="sk_src",
            mode="cut",
            depth=2.0,
            region=schema.SketchRegionSelector(
                closed_chain=[
                    {"geo": 0, "reversed": False},
                    {"geo": 1, "reversed": False},
                    {"spline": 0, "reversed": True},
                ]
            ),
        )
        adapted, records = sketch_regions.adapt_region_extrudes([sketch, extrude])
        self.assertEqual(len(adapted), 3)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["entity_names"], ["e0", "e1", "sp0"])

        broken = schema.ExtrudeOp(
            op="extrude",
            label="cut_bad",
            sketch="sk_src",
            mode="cut",
            depth=2.0,
            region=schema.SketchRegionSelector(
                closed_chain=[
                    {"geo": 0, "reversed": False},
                    {"geo": 1, "reversed": True},
                    {"spline": 0, "reversed": True},
                ]
            ),
        )
        with self.assertRaisesRegex(ValueError, "not closed"):
            sketch_regions.adapt_region_extrudes([sketch, broken])

        with self.assertRaises(ValidationError):
            schema.SketchRegionSelector(
                signature_yz_mm="0,0->10,0",
                closed_chain=[{"geo": 0}, {"geo": 1}],
            )

    def test_creo_server_info(self) -> None:
        info = asyncio.run(server.creo_server_info())
        self.assertEqual(info["server_name"], "MCP_CREO_MechDog")
        self.assertEqual(info["toolkit_channel_mode"], "single_channel_nonblocking")
        self.assertGreater(info["tool_count"], 100)
        self.assertEqual(info["units"], {"length": "mm", "angle": "deg"})

    def test_native_and_capabilities_markers(self) -> None:
        sketch_cpp = (ROOT / "native" / "sketch_coordinates.cpp").read_text(encoding="utf-8")
        self.assertIn('type != "circle")', sketch_cpp)
        self.assertIn("dimensioning='autodim'", sketch_cpp)
        self.assertIn("geometry_tolerance_mm=<cap>", sketch_cpp)

        bounds_h = (ROOT / "native" / "solid_bounds.h").read_text(encoding="utf-8")
        self.assertIn('"method_error_bound_mm"', bounds_h)
        self.assertIn('"inward"', bounds_h)

        generic_cpp = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
        self.assertIn("0 solid surfaces yet", generic_cpp)
        self.assertIn("round expectation failed", generic_cpp)

        sel_cpp = (ROOT / "native" / "geometry_selectors.cpp").read_text(encoding="utf-8")
        self.assertIn("adjacent_surfaces=", sel_cpp)
        self.assertIn("on_face:{kind:'surface',id:", sel_cpp)

        flange_cpp = (ROOT / "native" / "base_flange.cpp").read_text(encoding="utf-8")
        self.assertIn('"envelope_mm"', flange_cpp)
        self.assertIn('"u_extension_from_flip_thickness_mm"', flange_cpp)

        caps = server._capabilities_payload([])
        limits = caps["families"]["sketch_dimensioning"]["limits"]
        self.assertIn("b_spline/arc also route to autodim under dimensioning='auto'", limits)


if __name__ == "__main__":
    unittest.main()
