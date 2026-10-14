"""Owned fixture/oracle red controls. All conditions execute under Python -O."""
import argparse, importlib.util, json, sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import fixtures
spec=importlib.util.spec_from_file_location('owned_validate',ROOT/'tests/validate.py')
validate=importlib.util.module_from_spec(spec)
if sys.platform=='win32':
    # Import only: no resource main or accounting is emulated.
    with patch.dict(sys.modules,{'resource':types.ModuleType('resource')}):spec.loader.exec_module(validate)
else:spec.loader.exec_module(validate)
SCRATCH=None
class Gates(unittest.TestCase):
    def fixture_rejects(self,text,expected):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/'fixture.json';path.write_text(text)
            with self.assertRaises((AssertionError,ValueError)):fixtures.exact_fixture(path,expected)
            self.assertEqual(path.read_text(),text)
    def test_fixture_content(self):self.fixture_rejects('[1]',[2])
    def test_fixture_boolean_integer(self):self.fixture_rejects('[false]',[0])
    def test_fixture_float_integer(self):self.fixture_rejects('[1.0]',[1])
    def test_fixture_nested_alias(self):self.fixture_rejects('{"r":[true]}',{'r':[1]})
    def test_finite_oracle_executes(self):
        with patch.object(validate,'rank_band',return_value=None):
            with self.assertRaises(AssertionError):validate.overlap(1)
    def test_existing_fixture_unchanged(self):
        path=ROOT/'data/example.json';before=path.read_bytes()
        fixtures.exact_fixture(path,json.loads(before));self.assertEqual(path.read_bytes(),before)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scratch',type=Path,required=True);a=p.parse_args()
    a.scratch.mkdir(parents=True,exist_ok=True);SCRATCH=a.scratch
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gates))
    sys.exit(0 if r.wasSuccessful() else 1)
