"""Exploratory budget sensitivity, added after the fixed-size cap-ablation null.

No input/window was selected for a favorable effect. All integer total budgets,
all four declared gap families, and all three declared size bands are retained.
"""
from __future__ import annotations
from pathlib import Path
import sys,json,time,resource,os,argparse,statistics
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from driftcert import produce,check
from fixtures import scale_instance,FAMILIES


def run():
    rows=[];parity_checks=0
    for n in (128,512):
      for family in FAMILIES:
        base=scale_instance(n,family);c=base.contract
        bands={'fixed':(n,n),'flexible':(n-c.delete,n+c.insert),'growth':(n+3,n+3)}
        for name,(ml,mh) in bands.items():
          previous=None
          for b in range(c.insert+c.delete+1):
            inst=replace(base,contract=replace(c,edits=b,size_lo=ml,size_hi=mh))
            cert,stats=produce(inst);check(inst,cert)
            endpoints=[None if r is None else [r['lower'],r['upper']] for r in cert['segments']]
            widths=[hi-lo+1 for item in endpoints if item is not None for lo,hi in [item]]
            if name=='fixed' and b%2:
                assert endpoints==previous;parity_checks+=1
            if previous is not None:
              for old,new in zip(previous,endpoints):
                if old is not None:assert new is not None and new[0]<=old[0]<=old[1]<=new[1]
            rows.append(dict(n=n,family=family,band=name,insert=c.insert,delete=c.delete,
                             edits=b,size_lo=ml,size_hi=mh,mean_segment_width=statistics.mean(widths) if widths else None,
                             endpoints=endpoints,**stats))
            previous=endpoints
    return dict(status='exploratory_post_campaign',reason='fixed-size scaling total-cap ablation was nonbinding',
                cases=len(rows),fixed_size_parity_pairs_checked=parity_checks,mismatches=0,rows=rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(3758096384,3758096384))
    wall,cpu=time.monotonic(),time.process_time();result=run()
    result.update(cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
