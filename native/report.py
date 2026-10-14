"""Validate the native scientific inputs and generate every-case vector evidence."""
import argparse, csv, gzip, hashlib, io, json, statistics, sys, tarfile, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'native')]
import workflow as w
def read(path):return json.loads(gzip.decompress(path.read_bytes()))
def derive(source):
    data=read(source/'measurements.json.gz');cases=read(source/'inputs.json.gz')
    w.require(data['cases']==len(cases)==152 and data['arms']==list(w.ARMS) and data['repeats']==3,'native experiment scope')
    w.require(data['protocol']=='canonical-independent-source-to-endpoint-v1','protocol')
    expected_bindings={path.relative_to(ROOT).as_posix() for path in
        [*sorted((ROOT/'src/driftcert').glob('*.py')),ROOT/'tests/fixtures.py',ROOT/'native/replay.cpp',ROOT/'native/workflow.py']}
    w.require(set(data['source_bindings'])==expected_bindings,'source binding inventory')
    for name,sha in data['source_bindings'].items():w.require(w.digest((ROOT/name).read_bytes())==sha,'measured source changed: '+name)
    w.require(data['trusted_input_sha256']==w.digest((ROOT/'data/generated_traces.json').read_bytes()),'trace input changed')
    groups={};rows=[];totals={arm:{k:0 for k in ['queries','probes','window_misses','fallbacks','failed','moves','edits']} for arm in w.ARMS}
    for sample in data['samples']:
        key=(sample['case'],sample['arm'],sample['repeat'])
        w.require(key not in groups,'duplicate timing');groups[key]=sample
        w.require(all(type(sample[k])is int and sample[k]>0 for k in ['total_ns','preparation_ns','process_io_validation_ns']),'positive timing')
        w.require(sample['total_ns']==sample['preparation_ns']+sample['process_io_validation_ns'],'timing partition')
    w.require(len(groups)==1824,'sample completeness')
    packet_hashes={};output_hashes={}
    for index,case in enumerate(cases):
        inst=w.Instance.from_dict(case['instance']);w.admitted(inst,case['final']);want=w.expected(inst,case['final'])
        med={};first={}
        for arm in w.ARMS:
            packet=w.packet(inst,case['final'],w.prepare(inst,arm),arm);packet_hashes[(index,arm)]=w.digest(packet)
            items=[groups[(index,arm,r)] for r in range(3)]
            scientific={k:items[0][k] for k in ['prefixes','queries','probes','window_misses','fallbacks','failed','moves','edits','checksum']}
            w.validate_output(json.dumps(scientific),want,arm)
            for item in items:
                w.require({k:item[k] for k in scientific}==scientific,'scientific repetition mismatch')
                w.require(item['input_sha256']==w.digest(packet),'actual packet binding')
                w.require(item['output_sha256']==items[0]['output_sha256'],'actual output repeat binding')
            first[arm]=items[0];output_hashes[(index,arm)]=items[0]['output_sha256']
            med[arm]=statistics.median(r['total_ns'] for r in items)
            for k in totals[arm]:totals[arm][k]+=items[0][k]
        rows.append(dict(case=index,name=case['name'],group=case['group'],
            **{arm+'_ns':med[arm] for arm in w.ARMS},
            exact_transport_ratio=med['exact_replay']/med['transport'],
            exact_binary_ratio=med['exact_replay']/med['full_binary'],
            transport_exact_probes=first['transport']['probes']/max(1,first['exact_replay']['probes'])))
    checks=data['checked_conformance'];w.require(len(checks)==608,'checked build completeness')
    w.require({(r['case'],r['arm']) for r in checks}==set(output_hashes),'checked unique coverage')
    for r in checks:w.require(r['output_sha256']==output_hashes[(r['case'],r['arm'])],'checked result mismatch')
    # Raw bytes bind actual producer input and output, not just generated counts.
    with tarfile.open(source/'raw-files.tar.gz','r:gz') as archive:
        members=archive.getmembers();w.require(len(members)==6082 and len({m.name for m in members})==6082,'raw member scope')
        names={'inputs.json.gz','measurements.json.gz'}
        for index in range(152):
            for arm in w.ARMS:
                names|={f'{index:03}-{arm}.input.txt',f'{index:03}-checked-{arm}.json'}
                for repeat in range(4):names|={f'{index:03}-{repeat}-{arm}.stdout.json',f'{index:03}-{repeat}-{arm}.stderr.txt'}
        w.require({m.name for m in members}==names,'raw file membership')
        for member in members:
            w.require(member.isfile() and '/' not in member.name and '\\' not in member.name,'raw basename')
            if member.name.endswith('.input.txt'):
                index,arm=member.name.removesuffix('.input.txt').split('-',1)
                w.require(w.digest(archive.extractfile(member).read())==packet_hashes[(int(index),arm)],'raw input hash')
            elif member.name.endswith('.stdout.json'):
                index,repeat,arm=member.name.removesuffix('.stdout.json').split('-',2)
                w.require(0<=int(repeat)<=3,'raw repeat scope')
                w.require(w.digest(archive.extractfile(member).read())==output_hashes[(int(index),arm)],'raw output hash')
            elif '-checked-' in member.name:
                index,arm=member.name.removesuffix('.json').split('-checked-')
                w.require(w.digest(archive.extractfile(member).read())==output_hashes[(int(index),arm)],'raw checked hash')
            elif member.name.endswith('.stderr.txt'):
                w.require(archive.extractfile(member).read()==b'','native stderr')
            else:w.require(archive.extractfile(member).read()==(source/member.name).read_bytes(),'raw record binding')
    summary=dict(cases=152,timed_samples=1824,warmup_outputs=608,checked_outputs=608,
        raw_files=6082,raw_logical_bytes=sum(m.size for m in members),totals=totals,
        exact_slower_transport=sum(r['exact_transport_ratio']>1 for r in rows),
        exact_slower_binary=sum(r['exact_binary_ratio']>1 for r in rows),
        median_exact_transport_ratio=statistics.median(r['exact_transport_ratio'] for r in rows),
        minmax_exact_transport_ratio=[min(r['exact_transport_ratio'] for r in rows),max(r['exact_transport_ratio'] for r in rows)])
    return rows,summary
def csv_text(rows):
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows);return out.getvalue()
def tex_text(summary):
    lines=[r'\newcommand{\NativeRatio}{'+f"{summary['median_exact_transport_ratio']:.3f}"+'}',
           r'\newcommand{\NativeSlower}{'+str(summary['exact_slower_transport'])+'}',
           r'\begin{table}[t]',r'\caption{Native replay totals.}',r'\label{tab:native}',
           r'\centering',r'\setlength{\tabcolsep}{8pt}',
           r'\begin{tabular}{lrrr}',r'\toprule',r'Policy & Key probes & Window misses & Fallbacks\\',r'\midrule']
    for arm,label in [('exact_replay','Exact replay'),('transport','Ordinary transport'),('stored_fallback','Stored with fallback'),('full_binary','Full binary search')]:
        row=summary['totals'][arm]
        lines.append(f"{label} & {row['probes']:,} & {row['window_misses']:,} & {row['fallbacks']:,} "+r'\\')
    return '\n'.join(lines+[r'\bottomrule',r'\end{tabular}',r'\end{table}',''])
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'results/native-replay')
    p.add_argument('--figures',type=Path,required=True);p.add_argument('--scratch',type=Path,required=True)
    p.add_argument('--font-dir',type=Path);p.add_argument('--check',action='store_true')
    p.add_argument('--table-only',action='store_true',help='Validate retained records and write/check only native-summary.tex; never rewrite results or plots.')
    a=p.parse_args()
    rows,summary=derive(a.source);text=csv_text(rows)
    if a.table_only:
        w.require(json.loads((a.source/'summary.json').read_text())==summary,'summary stale')
        if a.check:
            w.require((a.figures/'native-summary.tex').read_text()==tex_text(summary),'native table stale')
        else:
            a.figures.mkdir(parents=True,exist_ok=True)
            (a.figures/'native-summary.tex').write_text(tex_text(summary))
        print(json.dumps(summary,indent=2));return
    if a.check:
        w.require((a.figures/'native-replay.csv').read_text()==text,'figure data stale')
        w.require(json.loads((a.source/'summary.json').read_text())==summary,'summary stale')
        w.require((a.figures/'native-summary.tex').read_text()==tex_text(summary),'native table stale')
        print(json.dumps(summary,indent=2));return
    a.figures.mkdir(parents=True,exist_ok=True);a.scratch.mkdir(parents=True,exist_ok=True)
    (a.figures/'native-replay.csv').write_text(text)
    (a.figures/'native-summary.tex').write_text(tex_text(summary))
    (a.source/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    sys.path.insert(0,str(ROOT/'scripts'));import plot_figures as plot
    with tempfile.TemporaryDirectory(dir=a.scratch,ignore_cleanup_errors=True) as tmp:
        plot.configure_fonts(a.font_dir,tmp);fig,ax=plot.canvas(406,198,(48,35,345,140),8)
        for group,marker,color in [('trace','o','0.2'),('scale','x','0.55')]:
            part=[r for r in rows if r['group']==group]
            ax.scatter([r['exact_transport_ratio'] for r in part],[r['transport_exact_probes'] for r in part],s=15,marker=marker,color=color,label=group.capitalize())
        ax.axvline(1,color='0.4',linewidth=.6,linestyle='--');ax.axhline(1,color='0.4',linewidth=.6,linestyle='--')
        ax.set_xscale('log',base=2);ax.set(xlabel='Exact / transport complete-call time',ylabel='Transport / exact key probes')
        ax.legend(frameon=False,loc='upper right');ax.grid(alpha=.2,linewidth=.4)
        plot.save(fig,'native-replay',a.figures,None)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
