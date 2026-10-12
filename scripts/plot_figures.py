#!/usr/bin/env python3
"""Draw exact rank coordinates and retained evaluation CSVs, not experiments."""
import argparse
import csv
import json
import shutil
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path, delimiter=","):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def canvas(width, height, box, fontsize=8):
    """Canvas and axis geometry in PDF points, measured in the original PDF."""
    fig = plt.figure(figsize=(width / 72, height / 72))
    left, bottom, axis_width, axis_height = box
    ax = fig.add_axes([left / width, bottom / height,
                       axis_width / width, axis_height / height])
    ax.tick_params(direction="in", length=2.5, width=.4, pad=3,
                   labelsize=fontsize)
    for spine in ax.spines.values():
        spine.set_linewidth(.4)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, name, output, paper_figures):
    output.mkdir(parents=True, exist_ok=True)
    target = output / (name + ".pdf")
    fig.savefig(target, format="pdf", metadata={"Creator": None,
                                               "Producer": None,
                                               "CreationDate": None,
                                               "ModDate": None})
    plt.close(fig)
    if paper_figures is not None:
        paper_figures.mkdir(parents=True, exist_ok=True)
        if target.resolve() != (paper_figures / target.name).resolve():
            shutil.copyfile(target, paper_figures / target.name)
    print(json.dumps({"asset": target.name,
                      "size_bp": [round(v * 72, 5) for v in fig.get_size_inches()]}))


def configure_fonts(font_dir, temporary):
    """Resolve the manuscript family; convert CFF outlines for valid Type-42 PDFs.

    TeX's Type-1 body and these OpenType outlines are the same Linux Libertine
    family. Conversion is only a temporary font-format adaptation, not a
    distributed replacement font; advance widths and Unicode maps are retained.
    """
    import subprocess
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont
    sources = []
    for name in ("LinLibertine_R.otf", "LinLibertine_RI.otf"):
        if font_dir is not None:
            source = font_dir / name
        else:
            installed = [Path(f.fname) for f in font_manager.fontManager.ttflist
                         if Path(f.fname).name == name]
            if installed:
                source = installed[0]
            elif shutil.which("kpsewhich"):
                result = subprocess.run(["kpsewhich", name], check=True,
                                        capture_output=True, text=True)
                source = Path(result.stdout.strip())
            else:
                raise RuntimeError("Install Linux Libertine, put kpsewhich on PATH, "
                                   "or pass --font-dir with its OTF files.")
        if not source.is_file():
            raise FileNotFoundError(source)
        original = TTFont(source)
        glyph_set = original.getGlyphSet()
        order = original.getGlyphOrder()
        glyphs = {}
        for glyph_name in order:
            pen = TTGlyphPen(glyph_set)
            glyph_set[glyph_name].draw(
                Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
            glyphs[glyph_name] = pen.glyph()
        builder = FontBuilder(original["head"].unitsPerEm, isTTF=True)
        builder.setupGlyphOrder(order)
        builder.setupCharacterMap(original.getBestCmap())
        builder.setupGlyf(glyphs)
        builder.setupHorizontalMetrics(original["hmtx"].metrics)
        builder.setupHorizontalHeader(ascent=original["hhea"].ascent,
                                      descent=original["hhea"].descent)
        builder.setupOS2()
        builder.font["OS/2"] = original["OS/2"]
        builder.font["name"] = original["name"]
        builder.setupPost(italicAngle=original["post"].italicAngle)
        builder.setupMaxp()
        builder.setupHead(macStyle=original["head"].macStyle,
                          created=original["head"].created,
                          modified=original["head"].modified)
        converted = Path(temporary) / (source.stem + ".ttf")
        builder.save(converted)
        if TTFont(converted)["hmtx"].metrics != original["hmtx"].metrics:
            raise ValueError("Font conversion changed glyph advance widths.")
        font_manager.fontManager.addfont(converted)
        sources.append(str(source))
    family = font_manager.FontProperties(fname=converted).get_name()
    plt.rcParams.update({
        "font.family": family, "font.size": 8.97,
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "pdf.use14corefonts": False, "text.usetex": False,
        "mathtext.fontset": "custom", "mathtext.rm": family,
        "mathtext.it": family + ":italic", "mathtext.bf": family,
        "mathtext.fallback": None, "axes.unicode_minus": True,
        "axes.labelpad": 5, "legend.fontsize": 8.97,
    })
    print(json.dumps({"font_family": family, "font_files": sources,
                      "temporary_format": "TrueType; original hmtx retained"}))

def render(data, output, paper_figures=None):
    import math
    example = read_rows(data / "example.csv")
    if [int(row["x"]) for row in example] != list(range(11)):
        raise ValueError("Unexpected discrete example domain.")
    for row in example:
        x = int(row["x"])
        lower = 0 if x == 0 else 3 if x == 10 else max(0, x-7)
        upper = 0 if x == 0 else 3 if x == 10 else min(3, x)
        if (int(row["rank_lower"]) != lower or int(row["rank_upper"]) != upper
                or int(row["prediction"]) != x//2
                or int(row["residual_lower"]) != lower-x//2
                or int(row["residual_upper"]) != upper-x//2):
            raise ValueError("Example data differ from the inclusive integer-rank formulas.")
    fig, ax = canvas(406, 158, (43, 27, 357.86674, 113.90385), 7.97)
    xs = [int(row["x"]) for row in example]
    ax.plot(xs, [int(row["residual_lower"]) for row in example],
            color="black", linewidth=1.2, marker="o", markersize=3.4,
            label="Lower residual")
    ax.plot(xs, [int(row["residual_upper"]) for row in example],
            color="black", linewidth=1.2, linestyle="--", marker="s",
            markersize=3.4, label="Upper residual")
    for hinge in (3, 7):
        ax.axvline(hinge, color="black", linewidth=.6, linestyle=":")
    ax.set(xlim=(0, 10), ylim=(-3.6, 2.6), xticks=list(range(11)),
           yticks=[-3, -2, -1, 0, 1, 2], xlabel=r"Query coordinate $x$",
           ylabel="Rank residual")
    ax.xaxis.label.set_size(7.97)
    ax.yaxis.label.set_size(7.97)
    ax.grid(True, color=".75", linewidth=.35, linestyle=":")
    ax.legend(loc="lower center", bbox_to_anchor=(.5, 1.03), ncol=2,
              frameon=False, borderaxespad=0, borderpad=0, handlelength=2,
              columnspacing=1.2)
    save(fig, "example", output, paper_figures)

    fig, ax = canvas(402.7, 181, (43, 29, 357.85, 125.75), 7.97)
    families = ("uniform", "alternating", "increasing", "clustered")
    counts = {}
    for family, marker, style in zip(families, ("o", "s", "^", "D"),
                                     ("-", "--", ":", "-.")):
        rows = read_rows(data / ("ratio-" + family + ".csv"))
        counts[family] = len(rows)
        ax.plot([int(row["n"]) for row in rows],
                [float(row["ratio"]) for row in rows], color="black",
                linewidth=.8, marker=marker, markersize=3.8,
                linestyle=style, label=family.capitalize())
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=10)
    ax.set(xlim=(25, 42000), ylim=(.7, 24),
           xticks=[32, 128, 512, 2048, 8192, 32768], yticks=[1, 2, 4, 8, 16],
           xlabel=r"Source keys $n$", ylabel="Direct / bisection CPU time")
    ax.set_xticklabels(["32", "128", "512", "2048", "8192", "32768"])
    ax.set_yticklabels(["1", "2", "4", "8", "16"])
    ax.minorticks_off()
    ax.tick_params(labelsize=7.97)
    ax.xaxis.label.set_size(7.97)
    ax.yaxis.label.set_size(7.97)
    ax.axhline(1, color=".35", linewidth=.6, linestyle=(0, (3, 2)))
    ax.grid(True, color=".75", linewidth=.35, linestyle=":")
    ax.legend(loc="lower center", bbox_to_anchor=(.5, 1.03), ncol=2,
              frameon=False, borderaxespad=0, borderpad=0, handlelength=2,
              columnspacing=1.2, labelspacing=.2, fontsize=7.97)
    save(fig, "timing-ratio", output, paper_figures)

    fig, ax = canvas(402.7, 161, (43, 28, 357.85, 119.58), 7.97)
    missing = {}
    for band, style, label in zip(("fixed", "flexible", "growth"),
                                  ("-", "--", ":"),
                                  ("Size 512", "Sizes 496-544", "Size 515")):
        rows = read_rows(data / ("sensitivity-" + band + ".csv"))
        ys = [float(row["width"]) if row["width"].strip() else math.nan
              for row in rows]
        missing[band] = sum(math.isnan(y) for y in ys)
        # NaN marks ineligible budgets, not zero width; post steps match const plot.
        ax.step([int(row["budget"]) for row in rows], ys, where="post",
                color="black", linewidth=.8, linestyle=style, label=label)
    ax.set(xlim=(0, 48), ylim=(0, 52.3), xticks=[0, 10, 20, 30, 40],
           yticks=[0, 10, 20, 30, 40, 50], xlabel=r"Total net-edit cap $B$",
           ylabel="Mean residual-window width")
    ax.xaxis.label.set_size(7.97)
    ax.yaxis.label.set_size(7.97)
    ax.grid(True, color=".75", linewidth=.35, linestyle=":")
    ax.legend(loc="lower center", bbox_to_anchor=(.5, 1.035), ncol=3,
              frameon=False, borderaxespad=0, borderpad=0, handlelength=2,
              columnspacing=1.4, fontsize=7.97)
    save(fig, "budget-sensitivity", output, paper_figures)
    print(json.dumps({"example_rows": len(example), "ratio_rows": counts,
                      "ineligible_budget_rows": missing}))


def main():
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "results/paper-assets/data")
    parser.add_argument("--output", type=Path, default=ROOT / "figures")
    parser.add_argument("--paper-figures", type=Path)
    parser.add_argument("--font-dir", type=Path)
    args = parser.parse_args()
    # FreeType can retain open font handles in its render cache on Windows.
    with tempfile.TemporaryDirectory(prefix="libertine-plot-",
                                     ignore_cleanup_errors=True) as temporary:
        configure_fonts(args.font_dir, temporary)
        render(args.data, args.output, args.paper_figures)


if __name__ == "__main__":
    main()
