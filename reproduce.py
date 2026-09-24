"""Run bounded, one-worker scientific chunks using only the standard library.

Recorded reference results are not overwritten by the default reproduction.
Each child has a 35-second wall timeout and an address-space limit of 3.5 GiB.
The controller records cumulative child CPU including interpreter startup.
"""
from __future__ import annotations
import argparse, json, os, resource, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--group',choices=['exact','prefix','arrangement','scaling','trace','sensitivity','all'],default='exact')
    p.add_argument('--match', help='run only case labels containing this literal text')
    p.add_argument('--size',type=int,choices=[32,128,512,2048,8192,32768])
    p.add_argument('--output',default='results/reproduced')
    args=p.parse_args()
    os.chdir(ROOT);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    commands=[]
    if args.group in ('exact','all'):
        for mode,end in [('overlap',9),('budgets',6),('integration',8)]:
            for u in range(1,end+1):
                shards = [(k,k+16) for k in range(0,64,16)] if mode == 'budgets' and u == 6 else [(None,None)]
                for start,stop in shards:
                    suffix = f'_sets{start}-{stop}' if start is not None else ''
                    label=f'{mode}_u{u}{suffix}'
                    target=output/'exact'/f'{label}.json'
                    command=['tests/validate.py','--mode',mode,'--universe',str(u),'--output',str(target)]
                    if start is not None: command += ['--start-set',str(start),'--stop-set',str(stop)]
                    commands.append((label,command))
        commands.append(('regression',['tests/validate.py','--mode','regression','--output',str(output/'exact/regression.json')]))
    if args.group in ('prefix','all'):
        for mode in ('envelope','minimum'):
            for u in range(1,5):
                label=f'prefix_{mode}_u{u}'
                commands.append((label,['tests/prefix.py','--mode',mode,'--universe',str(u),
                                        '--output',str(output/'prefix'/f'{mode}_u{u}.json')]))
        commands.append(('prefix_regression',['tests/prefix.py','--mode','regression',
                                               '--output',str(output/'prefix/regression.json')]))
        commands.append(('prefix_scaling',['tests/prefix_scaling.py',
                                            '--output',str(output/'prefix/scaling.json')]))
    if args.group in ('arrangement','all'):
        commands.append(('arrangement',['tests/arrangement.py','--output',str(output/'arrangement.json')]))
    if args.group in ('scaling','all'):
        for n in ([args.size] if args.size else [32,128,512,2048,8192,32768]):
            for family in ['uniform','alternating','increasing','clustered']:
                commands.append((f'scale_{n}_{family}', ['tests/scaling.py','--size',str(n),'--family',family,'--output',str(output/'scaling'/f'{n}_{family}.json')]))
    if args.group in ('trace','all'):
        commands.append(('trace',['tests/trace.py','--output',str(output/'trace.json')]))
    if args.group in ('sensitivity','all'):
        commands.append(('sensitivity',['tests/sensitivity.py','--output',str(output/'sensitivity.json')]))
    if args.match:
        commands=[item for item in commands if args.match in item[0]]
        if not commands: p.error('no matching case')
    records=[];wall=time.monotonic();parent_cpu=time.process_time()
    def usage():
        r=resource.getrusage(resource.RUSAGE_CHILDREN)
        return r.ru_utime+r.ru_stime
    before_all=usage()
    for label,command in commands:
        before=usage();t=time.monotonic()
        try:
            def child_limits():
                resource.setrlimit(resource.RLIMIT_AS, (3758096384, 3758096384))
            done=subprocess.run([sys.executable,*command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                text=True,timeout=35,preexec_fn=child_limits,
                                env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
            code=done.returncode;stderr=done.stderr[-4000:]
        except subprocess.TimeoutExpired:
            code=124;stderr='35-second chunk timeout'
        records.append(dict(case=label,command=['python',*command],exit_code=code,
                            cpu_seconds=usage()-before,wall_seconds=time.monotonic()-t,
                            cumulative_child_cpu_seconds=usage()-before_all,stderr=stderr))
        accounting=dict(group=args.group,workers=1,chunk_timeout_seconds=35,
                        child_cpu_seconds=usage()-before_all,parent_cpu_seconds=time.process_time()-parent_cpu,
                        wall_seconds=time.monotonic()-wall,records=records)
        suffix=f'_{args.size}' if args.size else ''
        if args.match: suffix += '_' + ''.join(c for c in args.match if c.isalnum() or c in '-_')
        (output/f'accounting_{args.group}{suffix}.json').write_text(json.dumps(accounting,indent=2)+'\n')
        print(label, 'exit',code,'CPU',round(records[-1]['cpu_seconds'],4),flush=True)
        if code:
            print(stderr,file=sys.stderr);raise SystemExit(code)
        if usage()-before_all>21600:
            raise SystemExit('development allocation exhausted; repair reserve protected')
    print('completed',len(records),'chunks; child CPU seconds',round(usage()-before_all,4))
if __name__=='__main__':main()
