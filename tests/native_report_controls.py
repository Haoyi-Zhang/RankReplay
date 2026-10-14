"""Benign in-memory mutations of the actual native scientific consumer."""
import argparse,copy,gzip,importlib.util,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'native'))
import report
SOURCE=ROOT/'results/native-replay'
class Consumer(unittest.TestCase):
    def test_complete_current_records(self):
        rows,summary=report.derive(SOURCE);self.assertEqual(len(rows),152);self.assertEqual(summary['timed_samples'],1824)
    def test_controlled_scientific_mutations(self):
        real=report.read;data=real(SOURCE/'measurements.json.gz')
        controls=[]
        x=copy.deepcopy(data);x['samples'].pop();controls.append(x)
        x=copy.deepcopy(data);x['samples'].append(x['samples'][0]);controls.append(x)
        x=copy.deepcopy(data);x['samples'][0]['failed']=False;controls.append(x)
        x=copy.deepcopy(data);x['samples'][0]['input_sha256']='0'*64;controls.append(x)
        x=copy.deepcopy(data);x['checked_conformance'].pop();controls.append(x)
        x=copy.deepcopy(data);x['source_bindings'].pop(next(iter(x['source_bindings'])));controls.append(x)
        x=copy.deepcopy(data);x['samples'][0]['total_ns']=0;controls.append(x)
        x=copy.deepcopy(data);x['protocol']='endpoint-only';controls.append(x)
        for number,mutant in enumerate(controls):
            def read(path):return mutant if path.name=='measurements.json.gz' else real(path)
            with self.subTest(control=number),patch.object(report,'read',side_effect=read),self.assertRaises((ValueError,KeyError)):
                report.derive(SOURCE)
if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Consumer))
    sys.exit(0 if r.wasSuccessful() else 1)
