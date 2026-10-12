"""Generate vector-PDF figure wrappers and tables from retained measured results.

Standalone use writes results/paper-assets. Pass --output ../paper/figures only
when integrating the sibling paper. No publisher files or result files change.
"""
from pathlib import Path
import argparse,csv,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def dump_csv(path,fields,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',default='results/summary');ap.add_argument('--output',default='results/paper-assets');ap.add_argument('--font-dir',type=Path);args=ap.parse_args()
    src=ROOT/args.source;out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True);(out/'data').mkdir(exist_ok=True)
    def rows(name):
        with (src/name).open(newline='') as f:return list(csv.DictReader(f))
    scale=rows('scaling.csv');sens=rows('sensitivity.csv')
    (out/'data/example.csv').write_bytes((src/'example.csv').read_bytes())
    families=('uniform','alternating','increasing','clustered')
    for fam in families:
        data=[dict(n=r['n'],ratio=float(r['direct_cpu_median'])/float(r['bisection_cpu_median'])) for r in scale if r['family']==fam]
        dump_csv(out/f'data/ratio-{fam}.csv',['n','ratio'],data)
    for band in ('fixed','flexible','growth'):
        data=[dict(budget=r['edits'],width=r['mean_segment_width'] or 'nan') for r in sens if r['n']=='512' and r['family']=='uniform' and r['band']==band]
        dump_csv(out/f'data/sensitivity-{band}.csv',['budget','width'],data)
    # One producer owns every PDF; regeneration cannot restore stale PGFPlots.
    command=[sys.executable,str(ROOT/'scripts/plot_figures.py'),
             '--data',str(out/'data'),'--output',str(ROOT/'figures')]
    if args.font_dir is not None:
        command+=['--font-dir',str(args.font_dir)]
    subprocess.run(command,check=True)
    for name in ('example','timing-ratio','budget-sensitivity'):
        (out/(name+'.tex')).write_text(
            r'\includegraphics{figures/'+name+'.pdf}'+'\n',encoding='utf-8')
        if (ROOT/'figures'/ (name+'.pdf')).resolve() != (out/(name+'.pdf')).resolve():
            shutil.copyfile(ROOT/'figures'/(name+'.pdf'),out/(name+'.pdf'))
    t=[]
    for r in scale:
        edit=r['minimum_edits'] or 'Safe'
        t.append(f"{int(r['n']):,} & {r['family'].capitalize()} & {edit} & {float(r['direct_cpu_median']):.5f} & {float(r['bisection_cpu_median']):.5f} & {float(r['envelope_cpu_median']):.5f} & {float(r['checker_cpu_median']):.5f} \\\\")
    (out/'scaling-table.tex').write_text(r'''\begin{table}[t]
\caption{All coordinate-scale cases. Minimum is the minimum failing net-edit cost within the contract; Safe means that no such failure exists. Producer columns include the required minimum packet. The envelope and checker columns measure their individual operations. Times are medians of three CPU measurements in seconds.}
\label{tab:scaling}
\begin{tabular}{rlrrrrr}
\toprule
$n$ & Family & Minimum & Direct & Bisection & Envelope & Checker\\
\midrule
'''+'\n'.join(t)+r'''
\bottomrule
\end{tabular}
\end{table}
''')
    t=[]
    for r in scale:
        if r['n']!='32768':continue
        fmt=lambda key:f"{float(r[key]):,.2f}" if float(r[key])<1e7 else f"${float(r[key])/1e10:.3f}\\times10^{{10}}$"
        t.append(f"{r['family'].capitalize()} & {fmt('exact_width')} & {fmt('no_cardinality_width')} & {fmt('uniform_width')} & {int(r['certificate_bytes']):,} \\\\")
    (out/'width-table.tex').write_text(r'''\begin{table}[t]
\caption{Mean unclipped residual width at $n=32768$. No-size removes the final-cardinality restriction; Uniform uses the coarse uniform rank-shift bound. Bytes is the compact JSON certificate size. Clustered widths round to the same displayed value despite small absolute differences; exact values remain in the artifact.}
\label{tab:width}
\begin{tabular}{lrrrr}
\toprule
Family & Exact & No-size & Uniform & Bytes\\
\midrule
'''+'\n'.join(t)+r'''
\bottomrule
\end{tabular}
\end{table}
''')
    print('Generated three vector-PDF figures, their exact plotting data, and two measured tables in',out)
if __name__=='__main__':main()
