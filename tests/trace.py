"""Generated atomic replacements; compare policies under a common 2-CPU-second cap.

The public values are not a public workload. Probe counts omit arithmetic/cache
costs. This is not an implementation or benchmark of an existing dynamic index.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import replace
from bisect import bisect_left
import sys,json,time,resource,os,argparse,random,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from driftcert import Instance,Contract,produce,check
from fixtures import model,stored_windows,wine_keys,exact_fixture,ROOT

HORIZON=4;STEPS=64;CPU_CAP=2.0
FAMILIES=('uniform','lower_shift','upper_shift','alternating')
POLICIES=('static_negative_control','periodic_with_fallback','certified_horizon','rebuild_every_batch')


def trace(keys,lo,hi,family,seed):
    rng=random.Random(seed);states=[list(keys)];edits=[];current=set(keys)
    for step in range(STEPS):
        ordered=sorted(current)
        direction=family
        if family=='alternating':direction='lower_shift' if step%2==0 else 'upper_shift'
        if direction=='uniform':
            deletion=ordered[rng.randrange(len(ordered))]
            insertion=rng.randint(lo,hi)
            while insertion in current:insertion=rng.randint(lo,hi)
        elif direction=='lower_shift':
            deletion=ordered[-1]
            insertion=next(x for x in range(ordered[0]-1,lo-1,-1) if x not in current) if ordered[0]>lo else next(x for x in range(lo,hi+1) if x not in current)
        else:
            deletion=ordered[0]
            insertion=next(x for x in range(ordered[-1]+1,hi+1) if x not in current) if ordered[-1]<hi else next(x for x in range(hi,lo-1,-1) if x not in current)
        current.remove(deletion);current.add(insertion)
        assert len(current)==len(keys)
        edits.append({'delete':deletion,'insert':insertion});states.append(sorted(current))
    return dict(states=states,edits=edits,lo=lo,hi=hi,seed=seed,family=family)


def find_key(keys,x,lo,hi):
    probes=0
    while lo<=hi:
        mid=(lo+hi)//2;value=keys[mid];probes+=1
        if value==x:return mid,probes
        if value<x:lo=mid+1
        else:hi=mid-1
    return None,probes


def policy(raw,name):
    n=len(raw['states'][0]);lo,hi=raw['lo'],raw['hi']
    counts=collections.Counter();hist=collections.Counter();refreshes=0;certs=0
    start,cpu=time.monotonic(),time.process_time();maint=0.0;model_used=None;windows=None
    for step in range(STEPS):
        target=tuple(raw['states'][step+1])
        refresh=(model_used is None or name=='rebuild_every_batch' or
                 (name!='static_negative_control' and step%HORIZON==0))
        if refresh:
            t=time.process_time()
            source=target if name=='rebuild_every_batch' else tuple(raw['states'][step])
            model_used=model(source,lo,hi)
            inst=Instance(lo,hi,source,model_used,Contract(HORIZON,HORIZON,2*HORIZON,n,n))
            if name=='certified_horizon':
                cert,_=produce(inst);check(inst,cert);certs+=1
                windows=[[row['lower'],row['upper']] for row in cert['segments']]
            else:windows=stored_windows(inst)
            refreshes+=1;maint+=time.process_time()-t
        j=0
        for actual,x in enumerate(target):
            while x>model_used[j].hi:j+=1
            p=model_used[j].predict(x);left=max(0,p+windows[j][0]);right=min(n-1,p+windows[j][1])
            found,probes=find_key(target,x,left,right)
            miss=not left<=actual<=right
            assert (found is None)==miss
            counts['queries']+=1;counts['window_misses']+=int(miss)
            if found is None and name!='static_negative_control':
                found,extra=find_key(target,x,0,n-1);probes+=extra;counts['fallbacks']+=1
            counts['failed_queries']+=int(found!=actual)
            counts['key_probes']+=probes;hist[probes]+=1
        if time.process_time()-cpu>CPU_CAP:raise AssertionError('common per-policy CPU ceiling exceeded')
    if name!='static_negative_control':assert counts['failed_queries']==0
    if name=='certified_horizon':assert counts['fallbacks']==0 and counts['window_misses']==0
    return dict(policy=name,**dict(counts),refreshes=refreshes,certificates_checked=certs,
                cpu_seconds=time.process_time()-cpu,maintenance_cpu_seconds=maint,
                wall_seconds=time.monotonic()-start,probe_histogram=dict(sorted(hist.items())),
                mean_key_probes=counts['key_probes']/counts['queries'],
                cpu_cap_seconds=CPU_CAP,workers=1)


def run():
    inputs={'public_proline':wine_keys(),'generated_uniform':tuple(8*k+128 for k in range(128))}
    rows=[];fixture=[]
    for dataset,keys in inputs.items():
        lo,hi=min(keys)-64,max(keys)+64
        for number,family in enumerate(FAMILIES):
            raw=trace(keys,lo,hi,family,32452843+number)
            raw['dataset']=dataset;fixture.append(raw)
            for name in POLICIES:rows.append(dict(dataset=dataset,family=family,n=len(keys),**policy(raw,name)))
    exact_fixture(ROOT/'data/generated_traces.json',fixture)
    return dict(horizon_atomic_replacements=HORIZON,steps_per_trace=STEPS,trace_count=len(fixture),
                policy_runs=len(rows),results=rows,
                public_csv_rows=178,public_unique_proline_keys=len(inputs['public_proline']),
                input_path='data/generated_traces.json',mismatches=0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(3758096384,3758096384))
    t,c=time.monotonic(),time.process_time();result=run()
    result.update(cpu_seconds=time.process_time()-c,wall_seconds=time.monotonic()-t,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))
if __name__=='__main__':main()
