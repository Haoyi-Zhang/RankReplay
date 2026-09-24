"""Dense coordinate/rank/size reference for the sparse minimum algorithm.

Not an actual-subset oracle: the old-first overlap formula is used here, after
being validated separately against actual subsets. This test isolates the
comparison-arrangement optimization, projections, and floor/negative arithmetic.
"""
from pathlib import Path
import sys, random, time, resource, os, json, argparse
from bisect import bisect_left
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from driftcert import Instance, Segment, Contract, direct_minimum, shortest, check_shortest
from driftcert.certificate import _comparison_candidates


def run(cases=512):
    rng=random.Random(131071)
    queries=pairs=transitions=0
    for case in range(cases):
        width=rng.randint(8,129); a=rng.randint(-1000,1000); b=a+width-1
        n=rng.randint(0,min(16,width)); s=tuple(sorted(rng.sample(range(a,b+1),n)))
        split=rng.randint(a,b)
        segs=[]
        for lo,hi in ((a,split),(split+1,b)):
            if lo<=hi: segs.append(Segment(lo,hi,rng.randint(-15,15),rng.randint(-100,100),rng.randint(1,11)))
        I,D=rng.randint(0,5),rng.randint(0,5)
        ml,mh=sorted((rng.randint(0,n+I+1),rng.randint(0,n+I+1)))
        inst=Instance(a,b,s,tuple(segs),Contract(I,D,I+D,ml,mh))
        windows=[sorted((rng.randint(-20,20),rng.randint(-20,20))) for _ in segs]
        best=None
        for x in range(a,b+1):
            L=bisect_left(s,x); old=int(L<n and s[L]==x); R=n-old-L
            seg=segs[int(x>split)] if len(segs)>1 else segs[0]
            w=windows[int(x>split)] if len(segs)>1 else windows[0]
            p=seg.predict(x)
            for m in range(max(ml,1),min(mh,width)+1):
                for r in range(max(0,m-1-(b-x)),min(m-1,x-a)+1):
                    h=old+min(L,r)+min(R,m-1-r)
                    i,d=m-h,n-h
                    if i<=I and d<=D and not w[0]<=r-p<=w[1]:
                        best=i+d if best is None else min(best,i+d)
                    pairs+=1
            queries+=1
        ans,_=direct_minimum(inst,windows)
        assert (ans is None)==(best is None),(inst,windows,best,ans)
        if best is not None: assert ans['edits']==best,(inst,windows,best,ans)
        check_shortest(inst,windows,shortest(inst,windows))
    # Directed weak comparisons must stay constant within every returned cell.
    for _ in range(1024):
        a,b=-64,64
        lines=[(rng.randint(-3,3),rng.randint(-40,40)) for _ in range(7)]
        A,B,Q=rng.randint(-20,20),rng.randint(-100,100),rng.randint(1,11)
        shift=rng.randint(-10,10)
        candidates=set(_comparison_candidates(a,b,lines,(A,B,Q),shift))
        previous=None
        for x in range(a,b+1):
            vals=[s*x+t for s,t in lines]+[(A*x+B)//Q+shift]
            signature=tuple((v<=w,w<=v) for i,v in enumerate(vals) for w in vals[i+1:])
            if previous is not None and signature!=previous:
                assert x-1 in candidates and x in candidates,(x,lines,A,B,Q,shift)
                transitions+=1
            previous=signature
    return dict(instances=cases,coordinate_queries=queries,rank_size_pairs=pairs,
                weak_order_instances=1024,weak_order_transitions=transitions,
                mismatches=0,seed=131071)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',type=int,default=512)
    ap.add_argument('--output',default='results/arrangement.json');args=ap.parse_args()
    if not 1<=args.cases<=512:ap.error('cases must be 1..512')
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(3758096384,3758096384))
    w,c=time.monotonic(),time.process_time();result=run(args.cases)
    result.update(cpu_seconds=time.process_time()-c,wall_seconds=time.monotonic()-w,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
