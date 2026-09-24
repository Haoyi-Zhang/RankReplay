"""Compare complete reproduction with reference science, excluding measurements.

All explicit deterministic fields, case counts, integer endpoints, seeds, fixtures
and operation counters must agree. For the five unsharded reference budget runs,
missing source-set scope metadata is completed from the frozen complete-enumeration
protocol; their original result files are not altered. CPU/wall time and peak RSS are not reproducible
bit-for-bit measurements and are reported separately, not used as equality tests.
"""
from pathlib import Path
import argparse,json
ROOT=Path(__file__).resolve().parents[1]
MEASUREMENTS={'cpu_seconds','wall_seconds','peak_rss_kib','maintenance_cpu_seconds'}

def stable(obj):
    if isinstance(obj,dict):return {k:stable(v) for k,v in obj.items() if k not in MEASUREMENTS}
    if isinstance(obj,list):return [stable(v) for v in obj]
    return obj

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference',default='results/campaign');ap.add_argument('--candidate',default='results/reproduced');ap.add_argument('--output',default='results/reproduction-check.json');a=ap.parse_args()
    ref=ROOT/a.reference;can=ROOT/a.candidate
    names=sorted([str(p.relative_to(ref)) for p in ref.glob('exact/*.json')]+[str(p.relative_to(ref)) for p in ref.glob('scaling/*.json')]+[str(p.relative_to(ref)) for p in ref.glob('prefix/*.json')]+['arrangement.json','trace.json','sensitivity.json'])
    if len(names)!=64:raise SystemExit(f'incomplete reference result set: {len(names)} (expected 64)')
    checked=[];completed_scopes=[]
    for name in names:
        if not (can/name).is_file():raise SystemExit('missing candidate '+name)
        r=json.loads((ref/name).read_text());c=json.loads((can/name).read_text())
        if r.get('mode') == 'budgets' and r.get('universe') in range(1,6):
            u=r['universe']
            expected=(1 << u)*(u+1)**2*(2*u+1)*((u+1)*(u+2)//2)
            if r.get('contracts') != expected:
                raise SystemExit('unsharded reference has wrong complete-contract count: '+name)
            if 'initial_set_start' not in r and 'initial_set_stop' not in r:
                r={**r,'initial_set_start':0,'initial_set_stop':1 << u}
                completed_scopes.append(name)
        if stable(r)!=stable(c):raise SystemExit('deterministic result disagreement: '+name)
        if c.get('mismatches')!=0:raise SystemExit('nonzero or missing mismatch field: '+name)
        checked.append(name)
    result={'accepted':True,'scientific_result_files_checked':len(checked),'deterministic_fields_equal_after_declared_scope_completion':True,'unsharded_reference_scope_completion':completed_scopes,'excluded_measurement_fields':sorted(MEASUREMENTS),'cases':checked}
    out=ROOT/a.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
