"""Deterministic numerical summaries of retained raw results; no timing fabrication."""
from __future__ import annotations
from pathlib import Path
import argparse,json,csv,statistics,collections,sys
ROOT=Path(__file__).resolve().parents[1]

def write_csv(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def summarize(source:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    exact=[]
    fields={'overlap':['rank_queries','admissible_set_occurrences'],
            'budgets':['contracts','rank_queries','admissible_set_occurrences'],
            'integration':['instances','actual_present_key_queries','certificates_checked','shortest_results_checked','endpoint_mutants_rejected']}
    for group,keys in fields.items():
        paths=sorted((source/'exact').glob(group+'*.json'))
        expected={'overlap':9,'budgets':9,'integration':8}[group]
        if len(paths)!=expected:raise ValueError(f'incomplete {group}: {len(paths)} files, expected {expected}')
        ds=[json.loads(f.read_text()) for f in paths]
        assert all(d['mismatches']==0 for d in ds)
        row={'group':group,'chunks':len(ds),**{k:sum(d[k] for d in ds) for k in keys},
             'mismatches':0,'cpu_seconds':sum(d['cpu_seconds'] for d in ds),
             'peak_rss_kib':max(d['peak_rss_kib'] for d in ds)}
        exact.append(row)
    (output/'exact.json').write_text(json.dumps(exact,indent=2)+'\n')
    prefix=[]
    for mode,field in [('envelope','contracts'),('minimum','minimum_queries')]:
        paths=sorted((source/'prefix').glob(mode+'_u*.json'))
        if len(paths)!=4:raise ValueError(f'incomplete prefix {mode}: {len(paths)} files, expected 4')
        ds=[json.loads(f.read_text()) for f in paths]
        assert all(d['mismatches']==0 for d in ds)
        row={'group':'prefix_'+mode,'chunks':len(ds),field:sum(d[field] for d in ds),
             'mismatches':0,'cpu_seconds':sum(d['cpu_seconds'] for d in ds),
             'peak_rss_kib':max(d['peak_rss_kib'] for d in ds)}
        for key in ('admissible_final_sets_counted_with_multiplicity','replay_prefixes',
                    'active_prefix_queries','safe_results','violating_results',
                    'contracts_with_strict_prefix_enlargement','strict_segment_enlargements',
                    'expanded_witnesses','expanded_endpoint_wrappers',
                    'expanded_prefix_wrappers','expanded_initial_phase',
                    'expanded_deletion_min_phase','expanded_final_phase',
                    'expanded_old_query_retained','expanded_old_query_deleted',
                    'expanded_new_query','expanded_empty_final',
                    'expanded_zero_budget','edit_steps_replayed',
                    'active_query_assertions','rank_assertions','budget_assertions'):
            if key in ds[0]:row[key]=sum(d[key] for d in ds)
        prefix.append(row)
    prefix_scaling=json.loads((source/'prefix/scaling.json').read_text())
    assert prefix_scaling['mismatches']==0 and prefix_scaling['case_count']==24
    prefix.append({'group':'prefix_scaling','chunks':1,
                   'case_count':prefix_scaling['case_count'],
                   'segments_compared':prefix_scaling['segments_compared'],
                   'enlarged_segments':prefix_scaling['enlarged_segments'],
                   'cases_with_enlargement':prefix_scaling['cases_with_enlargement'],
                   'producer_witness_constructions':prefix_scaling['producer_witness_constructions'],
                   'mismatches':0,'cpu_seconds':prefix_scaling['cpu_seconds'],
                   'peak_rss_kib':prefix_scaling['peak_rss_kib']})
    regression=json.loads((source/'prefix/regression.json').read_text())
    assert regression['mismatches']==0
    prefix.append({'group':'prefix_regression','chunks':1,
                   'certificate_mutants_rejected':len(regression['certificate_mutants_rejected']),
                   'minimum_mutants_rejected':len(regression['minimum_mutants_rejected']),
                   'prefix_minimum_edits':regression['prefix_minimum_edits'],
                   'hot_path':regression['hot_path'],
                   'targeted_witness_expansion':regression['targeted_witness_expansion'],
                   'mismatches':0,'cpu_seconds':regression['cpu_seconds'],
                   'peak_rss_kib':regression['peak_rss_kib']})
    (output/'prefix.json').write_text(json.dumps(prefix,indent=2)+'\n')
    scaling=[]
    for n in [32,128,512,2048,8192,32768]:
      for family in ['uniform','alternating','increasing','clustered']:
        d=json.loads((source/'scaling'/f'{n}_{family}.json').read_text());assert d['mismatches']==0
        row={'n':n,'family':family,'segments':d['segments'],'domain_width':d['domain_width'],
             'minimum_edits':d['minimum_edits'],'certificate_bytes':d['certificate_json_bytes'],
             'exact_width':d['mean_segment_width']['exact'],
             'no_cardinality_width':d['mean_segment_width']['without_cardinality'],
             'no_total_width':d['mean_segment_width']['without_total_cap'],
             'uniform_width':d['mean_segment_width']['uniform_transport']}
        for method in ['direct','bisection','envelope','checker']:
            vals=[r[method]['cpu_seconds'] for r in d['repeats']]
            row[method+'_cpu_median']=statistics.median(vals)
            row[method+'_cpu_min']=min(vals);row[method+'_cpu_max']=max(vals)
        row['direct_candidates']=d['repeats'][0]['direct']['candidate_evaluations']
        row['binary_envelope_calls']=d['repeats'][0]['bisection']['envelope_calls']
        row['peak_rss_kib']=d['peak_rss_kib']
        scaling.append(row)
    write_csv(output/'scaling.csv',scaling)
    trace=json.loads((source/'trace.json').read_text());g=collections.defaultdict(collections.Counter)
    keys=['queries','failed_queries','key_probes','fallbacks','refreshes','certificates_checked','window_misses','cpu_seconds','maintenance_cpu_seconds']
    for r in trace['results']:
        for k in keys:g[r['policy']][k]+=r.get(k,0)
    trace_rows=[{'policy':name,**dict(count),'mean_key_probes':count['key_probes']/count['queries']} for name,count in g.items()]
    write_csv(output/'trace.csv',trace_rows)
    sensitivity=json.loads((source/'sensitivity.json').read_text())
    write_csv(output/'sensitivity.csv',[{k:v for k,v in row.items() if k!='endpoints'} for row in sensitivity['rows']])
    # Exact compact example coordinates; compare pointwise against literal sets.
    sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
    from driftcert import Instance
    from driftcert.model import rank_band
    from validate import final_states
    inst=Instance.from_dict(json.loads((ROOT/'data/example.json').read_text()))
    example=[];states=list(final_states(inst))
    for x in range(inst.lo,inst.hi+1):
        band=rank_band(inst,x);ranks=[t.index(x) for t,_ in states if x in t]
        assert band is not None and (min(ranks),max(ranks))==band[:2]
        pred=inst.segments[0].predict(x)
        example.append(dict(x=x,rank_lower=band[0],rank_upper=band[1],prediction=pred,
                            residual_lower=band[0]-pred,residual_upper=band[1]-pred))
    write_csv(output/'example.csv',example)
    metrics={'exact':exact,'prefix':prefix,'scaling_cases':len(scaling),'scaling_repetitions_per_method':3,
             'scaling_maximum_peak_rss_kib':max(r['peak_rss_kib'] for r in scaling),
             'direct_binary_cpu_ratio_min':min(r['direct_cpu_median']/r['bisection_cpu_median'] for r in scaling),
             'direct_binary_cpu_ratio_max':max(r['direct_cpu_median']/r['bisection_cpu_median'] for r in scaling),
             'trace':trace_rows,'sensitivity_cases':sensitivity['cases'],
             'fixed_size_parity_pairs_checked':sensitivity['fixed_size_parity_pairs_checked']}
    (output/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='results/campaign');p.add_argument('--output',default='results/summary');args=p.parse_args()
    result=summarize(ROOT/args.source,ROOT/args.output)
    print(json.dumps(result,indent=2))
