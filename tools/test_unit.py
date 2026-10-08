"""Run input validation tests and save a versioned result for release evidence."""
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION

if __name__=='__main__':
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'version':VERSION,'timestamp':time.time(),'tests_run':result.testsRun,
            'success':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors)}
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/unit_test_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
