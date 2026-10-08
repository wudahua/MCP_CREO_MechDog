import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema import validate_operations
from generic_bridge import component_graph
from capabilities import require_available
from generic_bridge import submit

class AdvancedValidation(unittest.TestCase):
    def valid(self,op): return validate_operations([op])[0]
    def invalid(self,op):
        with self.assertRaises(ValueError): self.valid(op)

    def test_mirror_geometry_and_feature_rejection(self):
        base={'op':'mirror','label':'copy','plane':{'kind':'datum_plane','axis':'x'}}
        self.assertEqual(self.valid(base)['references'],[])
        self.invalid({**base,'references':[{'kind':'feature','label':'solid'}]})
        self.invalid({**base,'references':[{'kind':'part'},{'kind':'curve','id':1}]})

    def test_invalid_new_reference_ids(self):
        for kind in ('quilt','csys','point'):
            self.invalid({'op':'mirror','label':'copy','plane':{'kind':'datum_plane','axis':'x'},'references':[{'kind':kind,'id':-1}]})

    def test_sweep_profile_and_trajectory(self):
        base={'op':'sweep','label':'pipe','trajectory':'path','profile':[{'type':'circle','name':'c','center':[0,0],'radius':2}]}
        self.assertEqual(self.valid(base)['mode'],'add')
        self.invalid({**base,'trajectory':[]})
        self.invalid({**base,'dimensions':[{'name':'size','type':'diameter','value':4,'refs':[{'entity':'missing'}]}]})

    def test_loft_sections_and_draft_angle(self):
        self.invalid({'op':'loft','label':'loft','sections':['a','a']})
        self.invalid({'op':'loft','label':'loft','sections':['a']})
        base={'op':'draft','label':'draft','surfaces':[{'kind':'surface','id':1}],'neutral_plane':{'kind':'datum_plane','axis':'z'},'angle':0}
        self.invalid(base)
        self.assertEqual(self.valid({**base,'angle':-3})['angle'],-3)

    def test_sheetmetal_numeric_limits(self):
        base={'op':'sheetmetal_wall','label':'wall','sketch':'profile','depth':20,'thickness':1}
        self.assertEqual(self.valid(base)['thickness'],1)
        self.invalid({**base,'thickness':0})
        self.invalid({**base,'y_factor':1.5})
        self.invalid({'op':'sheetmetal_flange','label':'flange','edge':{'kind':'edge','id':1},'height':10,'angle':180})

    def test_assembly_placement_constraints_must_agree(self):
        base={'op':'assemble_component','label':'component','source_model_id':'a'*32}
        self.assertEqual(self.valid(base)['placement'],'fixed')
        self.invalid({**base,'placement':'constraints'})
        self.invalid({**base,'rotation':[0,0]})
        self.invalid({**base,'source_model_id':'../file.prt'})

    def test_recursive_assembly_cycle_and_busy_source(self):
        with patch('pathlib.Path.is_file',return_value=True):
            f=Path('test_source.asm.1')
            def model(sid,children=()):
                return {'model_id':sid,'status':'ready','part_file':str(f),'aliases':{str(i):{'source_model_id':c} for i,c in enumerate(children)}}
            a=model('a'*32,['b'*32]); b=model('b'*32,['c'*32]); c=model('c'*32)
            db={v['model_id']:v for v in (a,b,c)}
            with patch('generic_bridge.model_info',side_effect=db.__getitem__):
                with self.assertRaises(ValueError): component_graph(a,'c'*32)
                self.assertEqual(len(component_graph(a,'d'*32)),3)
                b['pending_job']='e'*32
                with self.assertRaises(ValueError): component_graph(a,'d'*32)

    def test_unavailable_operations_rejected_before_native_job(self):
        op={'op':'loft','label':'transition','sections':['first','second']}
        with patch('generic_bridge.bridge.toolkit_lock') as lock, patch('pathlib.Path.mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError,'no native job was queued'):
                submit([op])
            lock.assert_not_called();mkdir.assert_not_called()
        require_available([{'op':'sheetmetal_flange'}])

    def test_sheetmetal_unused_options_are_rejected(self):
        base={'op':'sheetmetal_wall','label':'wall','sketch':'profile','depth':20,'thickness':1}
        self.invalid({**base,'bend_radius':2})
        self.invalid({**base,'bend_sharps':True})

if __name__=='__main__': unittest.main()
