"""Owned native canonical batches; total preparation/process/update/query cost.

Every batch replays from its own source to one endpoint. Consecutive four-edit
horizons are NOT relabelled as one canonical replay of repeated operations.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, os, platform, statistics, subprocess, sys, time
from bisect import bisect_left
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from driftcert import Instance, Contract, produce_prefix, check_prefix
from driftcert.transport import transport_windows
from fixtures import model, scale_instance
ARMS=('exact_replay','transport','stored_fallback','full_binary')
def require(value,message):
    if not value: raise ValueError(message)
def digest(data):return hashlib.sha256(data).hexdigest()
def fixture_cases():
    traces=json.loads((ROOT/'data/generated_traces.json').read_text());cases=[]
    for raw in traces:
        for start in range(0,64,4):
            keys=tuple(raw['states'][start]);n=len(keys)
            inst=Instance(raw['lo'],raw['hi'],keys,model(keys,raw['lo'],raw['hi']),Contract(4,4,8,n,n))
            cases.append(dict(name=f"trace-{raw['dataset']}-{raw['family']}-{start}",group='trace',
                              instance=inst.to_dict(),final=raw['states'][start+4]))
    for n in [32,128,512,2048,8192,32768]:
        for family in ['uniform','alternating','increasing','clustered']:
            inst=scale_instance(n,family);target=list(inst.keys[1:])+[inst.hi];target.sort()
            cases.append(dict(name=f'scale-{n}-{family}',group='scale',instance=inst.to_dict(),final=target))
    require(len(cases)==152,'case inventory');return cases
def admitted(inst,final):
    require(type(final)is list and all(type(x)is int for x in final),'typed final')
    require(sorted(set(final))==final and all(inst.lo<=x<=inst.hi for x in final),'final set domain')
    s,t=set(inst.keys),set(final);i,d=len(t-s),len(s-t);c=inst.contract
    require(i<=c.insert and d<=c.delete and i+d<=c.edits and c.size_lo<=len(final)<=c.size_hi,'endpoint contract')
def states(inst,final):
    active=set(inst.keys);target=set(final);yield sorted(active)
    for x in sorted(active-target):active.remove(x);yield sorted(active)
    for x in sorted(target-active):active.add(x);yield sorted(active)
def expected(inst,final):
    checksum=queries=edits=0;sizes=[]
    for active in states(inst,final):
        sizes.append(len(active));queries+=len(active)
        for rank,x in enumerate(active):checksum=(checksum*6364136223846793005+(x%(1<<64))+rank)%(1<<64)
    return dict(queries=queries,checksum=checksum,sizes=sizes,edits=len(sizes)-1)
def prepare(inst,arm):
    if arm=='exact_replay':
        cert,_=produce_prefix(inst);check_prefix(inst,cert)
        return [[r['lower'],r['upper']] if r is not None else [0,0] for r in cert['segments']]
    if arm=='transport':return transport_windows(inst)
    if arm=='full_binary':return [[0,0] for _ in inst.segments]
    # Match the original stored-window fallback policy; empty pieces get [0,0].
    rows=[None]*len(inst.segments);j=0
    for rank,x in enumerate(inst.keys):
        while x>inst.segments[j].hi:j+=1
        value=rank-inst.segments[j].predict(x)
        rows[j]=[value,value] if rows[j] is None else [min(rows[j][0],value),max(rows[j][1],value)]
    return [r if r is not None else [0,0] for r in rows]
def packet(inst,final,windows,arm):
    mode=0 if arm=='full_binary' else 2 if arm=='stored_fallback' else 1
    # Plain binary search must not pay to transfer or route through unused models.
    pieces=inst.segments if mode else (type(inst.segments[0])(inst.lo,inst.hi,0,0,1),)
    if not mode:windows=[[0,0]]
    fields=[str(mode),str(len(inst.keys)),str(len(final)),str(len(pieces))]
    fields += [str(x) for x in inst.keys]+[str(x) for x in final]
    for s,w in zip(pieces,windows):fields += [str(x) for x in (s.lo,s.hi,s.a,s.b,s.q,*w)]
    return (' '.join(fields)+'\n').encode()
def validate_output(raw,want,arm):
    obj=json.loads(raw)
    fields={'prefixes','queries','probes','window_misses','fallbacks','failed','moves','edits','checksum'}
    require(type(obj)is dict and set(obj)==fields,'native output schema')
    require(all(type(obj[k])is int and obj[k]>=0 for k in fields-{'prefixes'}),'native exact counts')
    require(type(obj['prefixes'])is list and all(type(r)is list and len(r)==4 and all(type(v)is int and v>=0 for v in r) for r in obj['prefixes']),'prefix schema')
    require(obj['queries']==want['queries'] and obj['checksum']==want['checksum'] and obj['edits']==want['edits'],'literal input binding')
    require([r[0] for r in obj['prefixes']]==want['sizes'] and all(r[0]==r[1] for r in obj['prefixes']),'literal prefix binding')
    require(sum(r[2] for r in obj['prefixes'])==obj['probes'] and sum(r[3] for r in obj['prefixes'])==obj['window_misses'],'prefix totals')
    require(obj['failed']==0,'native failed lookup')
    if arm in ('exact_replay','transport','full_binary'):require(obj['window_misses']==obj['fallbacks']==0,'universal window miss')
    else:require(obj['fallbacks']==obj['window_misses'],'fallback accounting')
    return obj
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--repeats',type=int,default=3);ap.add_argument('--check-binary',type=Path)
    a=ap.parse_args();require(1<=a.repeats<=7,'repeat admission');a.output.mkdir(parents=True,exist_ok=True)
    cases=fixture_cases();(a.output/'inputs.json.gz').write_bytes(gzip.compress(json.dumps(cases,separators=(',',':')).encode(),mtime=0))
    samples=[];conformance=[]
    for index,case in enumerate(cases):
        inst=Instance.from_dict(case['instance']);admitted(inst,case['final']);want=expected(inst,case['final'])
        packets={};observed={}
        for repeat in range(-1,a.repeats):
            order=ARMS if (index+repeat)%2 else tuple(reversed(ARMS))
            for arm in order:
                start=time.perf_counter_ns();inst.validate();admitted(inst,case['final'])
                windows=prepare(inst,arm);data=packet(inst,case['final'],windows,arm)
                mid=time.perf_counter_ns();path=a.output/f'{index:03}-{arm}.input.txt'
                # The same input is written and closed on every invocation; file I/O is charged.
                path.write_bytes(data)
                with path.open('rb') as source:
                    done=subprocess.run([str(a.binary)],stdin=source,capture_output=True,timeout=15)
                require(done.returncode==0,'native process: '+done.stderr.decode(errors='replace'))
                obj=validate_output(done.stdout,want,arm);end=time.perf_counter_ns()
                if arm in packets:require(data==packets[arm] and obj==observed[arm],'nondeterministic packet/result')
                packets[arm]=data;observed[arm]=obj
                log=f'{index:03}-{repeat+1}-{arm}';(a.output/(log+'.stdout.json')).write_bytes(done.stdout)
                (a.output/(log+'.stderr.txt')).write_bytes(done.stderr)
                if repeat>=0:samples.append(dict(case=index,arm=arm,repeat=repeat,total_ns=end-start,
                    preparation_ns=mid-start,process_io_validation_ns=end-mid,input_sha256=digest(data),output_sha256=digest(done.stdout),**obj))
        if a.check_binary:
            for arm in ARMS:
                done=subprocess.run([str(a.check_binary)],input=packets[arm],capture_output=True,timeout=15)
                require(done.returncode==0,'checked native process');obj=validate_output(done.stdout,want,arm)
                require(obj==observed[arm],'release/check conformance')
                (a.output/f'{index:03}-checked-{arm}.json').write_bytes(done.stdout)
                conformance.append(dict(case=index,arm=arm,output_sha256=digest(done.stdout)))
        print(index,case['name'],flush=True)
    result=dict(protocol='canonical-independent-source-to-endpoint-v1',cases=len(cases),arms=list(ARMS),repeats=a.repeats,
        samples=samples,checked_conformance=conformance,python=sys.version,platform=platform.platform(),
        clocks={k:vars(time.get_clock_info(k)) for k in ['perf_counter','process_time']},
        binary_sha256=digest(a.binary.read_bytes()),source_sha256=digest(Path(__file__).read_bytes()),
        native_source_sha256=digest((ROOT/'native/replay.cpp').read_bytes()),
        source_bindings={path.relative_to(ROOT).as_posix():digest(path.read_bytes()) for path in
            [*sorted((ROOT/'src/driftcert').glob('*.py')),ROOT/'tests/fixtures.py',ROOT/'native/replay.cpp',Path(__file__)]},
        trusted_input_sha256=digest((ROOT/'data/generated_traces.json').read_bytes()),
        scope='Owned compact vectors and exact Python preparation; not a third-party index or deployment. Full interval includes validation, prepare/check, encoding, file write/close, process startup/read, updates, queries, output parse/binding. Excludes fixture generation/literal reference, builds, warmup, logging and summary equally. No fsync, RSS, physical allocation or energy measurement.')
    (a.output/'measurements.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0))
if __name__=='__main__':main()
