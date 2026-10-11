"""Geometry invariants and failures that must be rejected before native mutation."""
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import airfoil
import bridge
import seeds
from schema import AirfoilProfile, validate_operations

ROOT=Path(__file__).resolve().parents[1]


class PortableModeling(unittest.TestCase):
    def test_naca_chord_thickness_and_closed_boundary(self):
        profile=airfoil.entities({'chord':40,'thickness_ratio':.12})
        upper,lower=profile[0]['points'],profile[2]['points']
        self.assertAlmostEqual(max(p[0] for p in upper)-min(p[0] for p in upper),40)
        self.assertAlmostEqual(2*max(p[1] for p in upper),4.8,delta=.015)
        self.assertEqual(upper[0],lower[-1])
        self.assertEqual(profile[1]['start'],upper[-1])
        self.assertEqual(profile[1]['end'],lower[0])
        self.assertGreater(math.dist(upper[-1],lower[0]),0)

    def test_twist_is_about_requested_pivot_and_origin(self):
        base=airfoil.entities({'chord':20,'pivot_fraction':.4})[0]['points']
        turned=airfoil.entities({'chord':20,'pivot_fraction':.4,'twist_deg':90,'origin':[3,7]})[0]['points']
        for a,b in zip(base,turned):
            self.assertAlmostEqual(b[0],3-a[1])
            self.assertAlmostEqual(b[1],7+a[0])

    def test_invalid_airfoil_parameters_rejected(self):
        for profile in [{'chord':0},{'chord':10,'thickness_ratio':0},{'chord':10,'twist_deg':181},
                        {'chord':10,'origin':[float('nan'),0]},{'chord':10,'points_per_side':201}]:
            with self.assertRaises(ValueError):AirfoilProfile.model_validate(profile)

    def test_parameter_updates_compose_in_the_same_plan(self):
        operations=validate_operations([
            {'op':'airfoil_sketch','label':'foil','profile':{'chord':20}},
            {'op':'update_airfoil','sketch':'foil','values':{'chord':30}},
            {'op':'update_airfoil','sketch':'foil','values':{'twist_deg':25}},
        ])
        result=airfoil.prepare(operations,{})
        self.assertEqual(result[-1]['profile']['chord'],30)
        self.assertEqual(result[-1]['profile']['twist_deg'],25)
        with self.assertRaises(ValueError):airfoil.prepare([operations[1]],{})

    def test_packaged_seed_choice_needs_no_native_id(self):
        self.assertEqual(seeds.list_seeds()['available_count'],3)
        selected=seeds.select_seed(5,'smooth')
        self.assertEqual(selected['name'],'five_smooth')
        self.assertTrue(Path(selected['seed_file']).is_file())
        with self.assertRaises(ValueError):seeds.select_seed(5,'straight')

    def test_relocated_library_and_corrupt_seed_detection(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as directory:
            root=Path(directory).resolve()
            self.assertTrue(root.is_relative_to(ROOT.resolve()))
            shutil.copytree(ROOT/'seed_library',root/'seed_library')
            (root/'docs').mkdir()
            shutil.copy2(ROOT/'docs/seed_manifest.json',root/'docs/seed_manifest.json')
            shutil.copy2(ROOT/'LICENSE',root/'LICENSE')
            with patch.object(bridge,'ROOT',root),patch.object(bridge,'config',return_value={}):
                result=seeds.install_seed_library()
                self.assertEqual(result['available_count'],3)
                selected=seeds.select_seed(5,'smooth')
                self.assertTrue(Path(selected['seed_file']).is_relative_to(root))
                Path(selected['seed_file']).write_bytes(b'corrupt seed')
                self.assertFalse(seeds.validate_seed('five_smooth')['available'])
                with self.assertRaises(ValueError):seeds.select_seed(5,'smooth')

    def test_seed_path_traversal_rejected(self):
        entry={**seeds.manifest()['seeds'][0],'relative_path':'../outside.prt.1'}
        with self.assertRaises(ValueError):seeds._checked_seed(ROOT,entry)

    def test_invalid_transform_and_reorder_fail_before_submission(self):
        for op in [
            {'op':'geometry_transform','label':'pose','references':[{'kind':'body'}]},
            {'op':'geometry_transform','label':'pose','references':[{'kind':'body'},{'kind':'quilt','id':3}],'translation':[1,0,0]},
            {'op':'geometry_transform','label':'pose','references':[{'kind':'body'}],'translation':[1,0]},
            {'op':'reorder_features','features':['a'],'before':'b','after':'c'},
            {'op':'axis_pattern','label':'copies','leader':'blade','axis':{'kind':'datum_axis_feature','label':'axis'},'increment_deg':0},
            {'op':'update_airfoil','sketch':'foil','values':{}},
        ]:
            with self.assertRaises(ValueError):validate_operations([op])


if __name__=='__main__':unittest.main()
