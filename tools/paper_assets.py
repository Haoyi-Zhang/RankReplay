"""Generate LaTeX-native figures and tables from retained measured results.

Standalone use writes results/paper-assets. Pass --output ../paper/figures only
when integrating the sibling paper. No publisher files or result files change.
"""
from pathlib import Path
import argparse,csv,json
ROOT=Path(__file__).resolve().parents[1]

def dump_csv(path,fields,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',default='results/summary');ap.add_argument('--output',default='results/paper-assets');args=ap.parse_args()
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
    (out/'example.tex').write_text(r'''\begin{tikzpicture}
\begin{axis}[width=.94\linewidth,height=5.6cm,xlabel={Query coordinate $x$},ylabel={Rank residual},xmin=0,xmax=10,ymin=-3.6,ymax=2.6,xtick={0,1,...,10},ytick={-3,-2,...,2},legend style={at={(.5,1.03)},anchor=south,draw=none},legend columns=2,grid=major,grid style={densely dotted},tick label style={font=\small},label style={font=\small}]
\addplot[black,thick,mark=*,mark size=1.7pt] table[x=x,y=residual_lower,col sep=comma]{figures/data/example.csv};
\addlegendentry{Lower residual}
\addplot[black,dashed,thick,mark=square*,mark size=1.7pt] table[x=x,y=residual_upper,col sep=comma]{figures/data/example.csv};
\addlegendentry{Upper residual}
\addplot[black,densely dotted,forget plot] coordinates {(3,-3.6)(3,2.6)};
\addplot[black,densely dotted,forget plot] coordinates {(7,-3.6)(7,2.6)};
\end{axis}
\end{tikzpicture}
''')
    styles=('solid,mark=*','dashed,mark=square*','dotted,mark=triangle*','dashdotted,mark=diamond*')
    body=r'''\begin{tikzpicture}
\begin{axis}[width=.94\linewidth,height=6.3cm,xmode=log,log basis x=2,ymode=log,xlabel={Source keys $n$},ylabel={Direct / bisection CPU time},xmin=25,xmax=42000,ymin=.7,ymax=24,xtick={32,128,512,2048,8192,32768},xticklabels={32,128,512,2048,8192,32768},ytick={1,2,4,8,16},yticklabels={1,2,4,8,16},legend style={at={(.5,1.03)},anchor=south,draw=none},legend columns=2,grid=major,grid style={densely dotted},tick label style={font=\small},label style={font=\small}]
'''
    for fam,style in zip(families,styles):
        body+=r'\addplot[black,thick,'+style+r'] table[x=n,y=ratio,col sep=comma]{figures/data/ratio-'+fam+'.csv};\n'+r'\addlegendentry{'+fam.capitalize()+'}\n'
    body+=r'\addplot[black,thin,forget plot] coordinates {(25,1)(42000,1)};'+'\n'+r'\end{axis}'+'\n'+r'\end{tikzpicture}'+'\n'
    (out/'timing-ratio.tex').write_text(body)
    body=r'''\begin{tikzpicture}
\begin{axis}[width=.94\linewidth,height=5.8cm,xlabel={Total net-edit cap $B$},ylabel={Mean residual-window width},xmin=0,xmax=48,ymin=0,legend style={at={(.5,1.03)},anchor=south,draw=none},legend columns=3,grid=major,grid style={densely dotted},tick label style={font=\small},label style={font=\small},unbounded coords=jump]
'''
    for band,style,label in zip(('fixed','flexible','growth'),('solid','dashed','dotted'),('Size 512','Sizes 496--544','Size 515')):
        body+=r'\addplot[black,thick,const plot,'+style+r'] table[x=budget,y=width,col sep=comma]{figures/data/sensitivity-'+band+'.csv};\n'+r'\addlegendentry{'+label+'}\n'
    body+=r'\end{axis}'+'\n'+r'\end{tikzpicture}'+'\n';(out/'budget-sensitivity.tex').write_text(body)
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
    print('Generated three native figures, their exact plotting data, and two measured tables in',out)
if __name__=='__main__':main()
