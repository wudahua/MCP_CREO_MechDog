import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge


class Parameters(unittest.TestCase):
    def spec(self, **changes):
        args = dict(length=80, width=60, thickness=20, radius=5, holes=[])
        args.update(changes)
        return bridge.validate_spec(**args)

    def test_requested_plate(self):
        holes = [{"x": x, "y": y, "diameter": 8} for x, y in [(-30,-20),(30,-20),(30,20),(-30,20)]] + [{"x":0,"y":0,"diameter":10}]
        self.assertEqual(len(self.spec(holes=holes)["holes"]), 5)

    def test_nonfinite_and_invalid_dimensions(self):
        for changes in ({"length": math.nan}, {"width": math.inf}, {"thickness":0}, {"radius":30}, {"radius":-1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.spec(**changes)

    def test_hole_overlap_and_boundary(self):
        examples = [
            [{"x":0,"y":0,"diameter":10},{"x":9,"y":0,"diameter":10}],
            [{"x":36,"y":0,"diameter":8}],
            [{"x":38,"y":28,"diameter":4}],
            [{"x":0,"y":0,"diameter":math.inf}],
        ]
        for holes in examples:
            with self.subTest(holes=holes), self.assertRaises(ValueError):
                self.spec(holes=holes)

    def test_zero_round_and_no_holes(self):
        self.assertEqual(self.spec(radius=0)["holes"], [])

    def test_traversal_and_name(self):
        for value in ("../", "a"*31, "0"*32+"/.."): # valid IDs are exactly 32 hex characters
            with self.assertRaises(ValueError):
                bridge.job_path(value)
        for name in ("../part", "A_PART", 'p";cmd', "a"*32):
            with self.assertRaises(ValueError):
                self.spec(model_name=name)


if __name__ == "__main__":
    unittest.main()
