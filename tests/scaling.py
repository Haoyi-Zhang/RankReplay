"""Same-instance, same-cap comparison; timings are descriptive, not superiority evidence."""
from __future__ import annotations
from pathlib import Path
import sys,json,time,resource,os,argparse,statistics
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from driftcert import produce,check,shortest,shortest_bisection,check_shortest
from fixtures import scale_instance,stored_windows,uniform_transport,exact_fixture,ROOT,FAMILIES


def widths(cert):return [row['upper']-row['lower']+1 for row in cert['segments'] if row is not None]


def run(n,family):
    inst=scale_instance(n,family);inst.validate()
    # JSON conversion makes tuple/list normalization explicit for exact fixture comparison.
    exact_fixture(ROOT/'data/scaling'/f'{n}_{family}.json',json.loads(json.dumps(inst.to_dict())))
    initial=stored_windows(inst);c=inst.contract
    windows=[[lo-max(1,c.delete//2),hi+max(1,c.insert//2)] for lo,hi in initial]
    repeats=[];answers=[]
    for repeat in range(3):
        row={'repeat':repeat}
        for name,fn in [('direct',shortest),('bisection',shortest_bisection)]:
            stats={};t,cpu=time.monotonic(),time.process_time()
            result=fn(inst,windows,stats)
            row[name]={'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-t,**stats}
            check_shortest(inst,windows,result)
            answers.append((result['kind'],result.get('edits')))
        t,cpu=time.monotonic(),time.process_time();cert,stats=produce(inst)
        row['envelope']={'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-t,**stats}
        t,cpu=time.monotonic(),time.process_time();checked=check(inst,cert)
        row['checker']={'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-t,**checked}
        repeats.append(row)
    assert len(set(answers))==1
    loose_size=replace(inst,contract=replace(c,size_lo=0,size_hi=inst.hi-inst.lo+1))
    loose_total=replace(inst,contract=replace(c,edits=c.insert+c.delete))
    no_size,_=produce(loose_size);no_total,_=produce(loose_total)
    check(loose_size,no_size);check(loose_total,no_total)
    simple=uniform_transport(inst)
    for full,sized,total,baseline in zip(cert['segments'],no_size['segments'],no_total['segments'],simple):
        if full is not None:
            assert sized['lower']<=full['lower']<=full['upper']<=sized['upper']
            assert total['lower']<=full['lower']<=full['upper']<=total['upper']
            assert baseline[0]<=full['lower']<=full['upper']<=baseline[1]
    groups={'exact':widths(cert),'without_cardinality':widths(no_size),'without_total_cap':widths(no_total),
            'uniform_transport':[hi-lo+1 for lo,hi in simple]}
    return dict(n=n,family=family,segments=len(inst.segments),domain_width=inst.hi-inst.lo+1,
                maximum_input_coordinate_bits=max(abs(inst.lo).bit_length(),abs(inst.hi).bit_length()),
                contract=inst.to_dict()['contract'],repeats=repeats,result_kind=answers[0][0],
                minimum_edits=answers[0][1],widths=groups,
                mean_segment_width={name:statistics.mean(vals) for name,vals in groups.items()},
                maximum_segment_width={name:max(vals) for name,vals in groups.items()},
                certificate_json_bytes=len(json.dumps(cert,separators=(',',':')).encode()),
                requested_windows=windows,mismatches=0,
                per_method_resource_cap={'workers':1,'address_space_bytes':3758096384,'chunk_wall_seconds':35})


def main():
    p=argparse.ArgumentParser();p.add_argument('--size',type=int,choices=[32,128,512,2048,8192,32768],required=True)
    p.add_argument('--family',choices=FAMILIES,required=True);p.add_argument('--output',required=True);args=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(3758096384,3758096384))
    t,c=time.monotonic(),time.process_time();result=run(args.size,args.family)
    result.update(cpu_seconds=time.process_time()-c,wall_seconds=time.monotonic()-t,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k in ['n','family','minimum_edits','cpu_seconds','mean_segment_width','peak_rss_kib']},indent=2))
if __name__=='__main__':main()
