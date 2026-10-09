import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema import validate_operations
from generic_bridge import submit


class DevelopmentValidation(unittest.TestCase):
    def test_invalid_table_shapes_and_updates(self):
        for op in [
            {'op':'drawing_table','label':'t','position':[0,0],'columns':[20,30],'cells':[['only one']]},
            {'op':'drawing_table_cell','table':'t','row':0,'column':1,'text':'bad'},
            {'op':'drawing_view_update','view':'front'},
            {'op':'drawing_note_update','note':'n'},
        ]:
            with self.subTest(op=op),self.assertRaises(ValueError):validate_operations([op])

    def test_wrong_model_type_rejected_before_files_or_jobs(self):
        for op,model_type in [
            ({'op':'drawing_note','label':'n','lines':['abc'],'position':[10,20]},'part'),
            ({'op':'export','format':'pdf'},'part'),
            ({'op':'export','format':'step'},'drawing'),
            ({'op':'extrude','label':'e','sketch':'s','depth':10},'drawing'),
        ]:
            with self.subTest(op=op),patch('generic_bridge.bridge.toolkit_lock'),patch('pathlib.Path.mkdir') as mkdir,patch('generic_bridge.subprocess.Popen') as start:
                with self.assertRaises(ValueError):submit([op],model_type=model_type)
                mkdir.assert_not_called();start.assert_not_called()

    def test_boolean_distinct_bodies_and_counts(self):
        op={'op':'boolean_bodies','label':'b','method':'union','targets':[{'kind':'body','id':1}],'tools':[{'kind':'body','id':2}]}
        validate_operations([op])
        for changes in [{'tools':[{'kind':'body','id':1}]},{'keep_tools':True},{'targets':[{'kind':'body','id':1},{'kind':'body','id':3}]}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_operations([{**op,**changes}])

    def test_udf_nonfinite_and_invalid_references(self):
        op={'op':'udf_create','label':'u','file_path':'library.gph','references':{'REF_CSYS':{'kind':'default_csys'}}}
        validate_operations([op])
        for change in [{'dimensions':{'d1':math.inf}},{'references':{'REF_CSYS':{'kind':'csys','id':-1}}}]:
            with self.subTest(change=change),self.assertRaises(ValueError):validate_operations([{**op,**change}])
        with patch('generic_bridge.bridge.toolkit_lock'),patch('pathlib.Path.is_file',return_value=True),patch('generic_bridge.bridge.config',return_value={'creo_root':'C:/Creo'}),patch('pathlib.Path.mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError,'absolute path'):submit([op])
            mkdir.assert_not_called()

    def test_datum_and_surface_parameters(self):
        for op in [
            {'op':'datum_csys','label':'c','translation':[1,2]},
            {'op':'datum_points','label':'p','points':[{'name':'a','position':[0,0,0]},{'name':'a','position':[1,2,3]}]},
            {'op':'thicken','label':'t','reference':{'kind':'quilt','id':1},'thickness':0},
        ]:
            with self.subTest(op=op),self.assertRaises(ValueError):validate_operations([op])


if __name__=='__main__':unittest.main()
