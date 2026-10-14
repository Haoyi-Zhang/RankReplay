"""Literal minimal-order transport oracle and owned native conformance."""
import argparse, copy, importlib.util, itertools, json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'native')]
from driftcert import Instance,Segment,Contract
from driftcert.transport import transport_windows
import workflow as w
BINARIES=[];COUNTS={}
def require(v,m):
    if not v:raise AssertionError(m)
def count(k,n=1):COUNTS[k]=COUNTS.get(k,0)+n
class Transport(unittest.TestCase):
    def test_literal_all_minimal_orders(self):
        for u in range(1,6):
            universe=set(range(-2,u-2))
            subsets=[{x for k,x in enumerate(sorted(universe)) if mask>>k&1} for mask in range(1<<u)]
            for source in subsets:
                for target in subsets:
                    edits=[('d',x) for x in source-target]+[('i',x) for x in target-source]
                    i,d=len(target-source),len(source-target)
                    for A,B,Q in [(-2,-1,3),(3,-2,2)]:
                        inst=Instance(-2,u-3,tuple(sorted(source)),(Segment(-2,u-3,A,B,Q),),Contract(i,d,i+d,len(target),len(target)))
                        windows=transport_windows(inst);count('contracts')
                        # Independent dense source-rank construction, not sparse helpers.
                        residuals=[sum(y<x for y in source)-(A*x+B)//Q for x in sorted(universe)]
                        require(windows==[[min(residuals)-d,max(residuals)+i]],'dense transport construction')
                        for order in itertools.permutations(edits):
                            active=set(source);count('minimal_orders')
                            for operation in [None,*order]:
                                if operation:
                                    kind,x=operation
                                    if kind=='d':active.remove(x)
                                    else:active.add(x)
                                count('prefixes')
                                for rank,x in enumerate(sorted(active)):
                                    require(windows[0][0]<=rank-(A*x+B)//Q<=windows[0][1],'transport containment')
                                    count('active_queries')
    def test_owned_native_negative_floor_and_prefixes(self):
        for source,final,lo,hi,A,B,Q in [([0,2],[1,2],0,2,0,0,1),([-3,-1],[0,2],-4,4,-3,-2,2),([0,1],[],0,2,3,-5,2),([],[-2,2],-2,2,1,-3,3),([-7,0,8],[-6,0,9],-8,10,7,-13,5)]:
            i,d=len(set(final)-set(source)),len(set(source)-set(final))
            inst=Instance(lo,hi,tuple(source),(Segment(lo,hi,A,B,Q),),Contract(i,d,i+d,len(final),len(final)))
            want=w.expected(inst,final)
            for arm in w.ARMS:
                data=w.packet(inst,final,w.prepare(inst,arm),arm);previous=None
                for binary in BINARIES:
                    r=subprocess.run([str(binary)],input=data,capture_output=True,timeout=15)
                    require(r.returncode==0,r.stderr.decode(errors='replace'));obj=w.validate_output(r.stdout,want,arm)
                    if previous is not None:require(obj==previous,'native build disagreement')
                    previous=obj;count('native_processes')
    def test_output_typed_and_semantic_mutations(self):
        inst=Instance(0,2,(0,2),(Segment(0,2,0,0),),Contract(1,1,2,2,2));final=[1,2]
        r=subprocess.run([str(BINARIES[0])],input=w.packet(inst,final,w.prepare(inst,'transport'),'transport'),capture_output=True,timeout=15)
        require(r.returncode==0,'native fixture');obj=json.loads(r.stdout);want=w.expected(inst,final)
        for key,value in [('failed',True),('failed',1),('queries',0),('checksum',0),('edits',0),('fallbacks',1),('prefixes',[])]:
            mutated=copy.deepcopy(obj);mutated[key]=value
            with self.assertRaises(ValueError):w.validate_output(json.dumps(mutated),want,'transport')
            count('output_mutants_rejected')
    def test_native_rejects_ordinary_out_of_domain_input(self):
        inst=Instance(0,2,(0,2),(Segment(0,2,0,0),),Contract(1,1,2,2,2))
        for binary in BINARIES:
            r=subprocess.run([str(binary)],input=w.packet(inst,[-1,2],[[0,0]],'full_binary'),capture_output=True,timeout=15)
            self.assertNotEqual(r.returncode,0);count('native_admission_rejections')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    BINARIES=a.binary
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Transport))
    a.output.write_text(json.dumps(dict(tests=r.testsRun,successful=r.wasSuccessful(),counts=COUNTS),indent=2)+'\n')
    sys.exit(0 if r.wasSuccessful() else 1)
