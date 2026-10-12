# Vector figure reproduction

Figure generation is optional post-processing of retained results, not an experiment or part of certificate checking. It needs Python 3.10+, Matplotlib, and FontTools (a Matplotlib dependency).

```sh
python -m pip install matplotlib fonttools
python scripts/plot_figures.py
# To regenerate plotting data, wrappers, PDFs and the existing tables:
python tools/paper_assets.py --source results/summary --output results/paper-assets
```

The native outputs are in `artifact/figures/`. To copy identical PDFs into a full project's sibling paper, add `--paper-figures ../paper/figures`. A paper-only package can compile its shipped figure PDFs without Python.

The producer reads `results/paper-assets/data` (or `--data`) and draws the discrete example, measured timing ratios, and budget steps. `tools/paper_assets.py` still derives the plotting CSVs and measured tables from the retained summaries, but writes PDF wrappers and invokes this one producer. It cannot reintroduce PGFPlots. Ineligible growth budgets 0–2 remain NaN/omitted, not zero; parity plateaus use post steps. `paper/figures/draw_evaluation.py` forwards to this producer.

The text family is Linux Libertine (the acmart body family). Fonts are discovered from installed Linux Libertine O faces or `kpsewhich`. If neither is available, pass `--font-dir` pointing to the Linux Libertine distribution's `LinLibertine_R.otf` and `LinLibertine_RI.otf`; no machine path is stored in the producer. FontTools adapts these CFF outlines to temporary TrueType outlines (one font-unit curve tolerance), retaining Unicode mappings and every advance width. Only subsets embedded in PDFs are shipped, not modified font files. The original font's GPL/OFL metadata stays intact. On Windows the FreeType render cache can hold temporary font files until process exit.

PDF text is embedded with `pdf.fonttype=42`; `text.usetex` and unembedded PDF core fonts are disabled. Curves, markers, axes, and text remain vector objects. The canvas and axis rectangles are explicit PDF-point dimensions measured from the current manuscript plots; saving does not crop or rasterize them. Captions and float placement remain in the TeX source.
