"""Structural audit of the manuscript bibliography and citation graph.

This deliberately distinguishes local consistency from external metadata review.
It parses the BibTeX file without third-party packages, verifies that every entry
is cited and every citation resolves, checks DOI syntax/uniqueness, and emits a
row-level audit table that records the stable identifier used for external review.
"""
from __future__ import annotations

import argparse, csv, json, re
from pathlib import Path

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)


def braced(text: str, pos: int) -> tuple[str, int]:
    assert text[pos] == "{"
    depth = 0; out: list[str] = []
    for i in range(pos, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
            if depth > 1: out.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0: return "".join(out), i + 1
            out.append(ch)
        else:
            out.append(ch)
    raise ValueError("unclosed brace")


def quoted(text: str, pos: int) -> tuple[str, int]:
    out: list[str] = []; escaped = False
    for i in range(pos + 1, len(text)):
        ch = text[i]
        if ch == '"' and not escaped: return "".join(out), i + 1
        out.append(ch); escaped = (ch == "\\" and not escaped)
    raise ValueError("unclosed quote")


def parse_bib(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    entries: list[dict[str, str]] = []; pos = 0
    while True:
        at = text.find("@", pos)
        if at < 0: break
        match = re.match(r"@(\w+)\s*\{\s*([^,]+),", text[at:])
        if not match:
            pos = at + 1; continue
        typ, key = match.group(1).lower(), match.group(2).strip()
        i = at + match.end(); fields: dict[str, str] = {"type": typ, "key": key}
        while True:
            while i < len(text) and (text[i].isspace() or text[i] == ","): i += 1
            if i >= len(text): raise ValueError(f"unterminated entry {key}")
            if text[i] == "}": i += 1; break
            field = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", text[i:])
            if not field: raise ValueError(f"cannot parse {key} near {text[i:i+40]!r}")
            name = field.group(1).lower(); i += field.end()
            if text[i] == "{": value, i = braced(text, i)
            elif text[i] == '"': value, i = quoted(text, i)
            else:
                j = i
                while j < len(text) and text[j] not in ",}": j += 1
                value, i = text[i:j].strip(), j
            fields[name] = re.sub(r"\s+", " ", value).strip()
        entries.append(fields); pos = i
    return entries


def citations(tex_root: Path) -> list[str]:
    keys: list[str] = []
    for path in sorted(tex_root.rglob("*.tex")):
        text = re.sub(r"(?m)(?<!\\)%.*$", "", path.read_text(encoding="utf-8"))
        for body in re.findall(r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}", text):
            keys.extend(k.strip() for k in body.split(",") if k.strip())
    return keys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--paper",
        required=True,
        help=("path to a manuscript directory containing references.bib and "
              "the cited .tex sources; this optional integration audit is not "
              "part of standalone scientific reproduction"),
    )
    ap.add_argument("--identifiers", default="sources/bibliography-identifiers.csv")
    ap.add_argument("--output", default="sources/bibliography-audit.csv")
    ap.add_argument("--summary", default="sources/bibliography-audit.json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    paper = (root / args.paper).resolve()
    entries = parse_bib(paper / "references.bib")
    identifier_path = root / args.identifiers
    with identifier_path.open(newline="", encoding="utf-8") as handle:
        identifier_rows = list(csv.DictReader(handle))
    identifier_map = {row["key"]: row for row in identifier_rows}
    if len(identifier_map) != len(identifier_rows):
        raise SystemExit("duplicate key in bibliography identifier provenance")
    cited = citations(paper)
    cited_set = set(cited); keys = [e["key"] for e in entries]; key_set = set(keys)
    if len(keys) != len(key_set): raise SystemExit("duplicate BibTeX key")
    missing = sorted(cited_set - key_set); unused = sorted(key_set - cited_set)
    if missing or unused: raise SystemExit(f"citation graph mismatch: missing={missing}, unused={unused}")
    if set(identifier_map) != key_set:
        raise SystemExit(f"identifier provenance key mismatch: missing={sorted(key_set-set(identifier_map))}, extra={sorted(set(identifier_map)-key_set)}")
    identifiers: dict[str, str] = {}
    rows = []
    for entry in entries:
        doi = entry.get("doi", "")
        if doi and not DOI_RE.match(doi): raise SystemExit(f"invalid DOI syntax: {entry['key']} {doi}")
        provenance = identifier_map[entry["key"]]
        identifier_type = provenance["identifier_type"]
        identifier = provenance["identifier"]
        if identifier_type == "DOI":
            if not DOI_RE.match(identifier): raise SystemExit(f"invalid provenance DOI: {entry['key']} {identifier}")
            if doi.casefold() != identifier.casefold(): raise SystemExit(f"BibTeX/provenance DOI mismatch: {entry['key']}")
        elif identifier_type != "stable URL" or not re.match(r"^https://", identifier):
            raise SystemExit(f"invalid stable identifier provenance: {entry['key']}")
        elif doi:
            raise SystemExit(f"stable-URL provenance used despite BibTeX DOI: {entry['key']}")
        folded = identifier.casefold()
        if folded in identifiers: raise SystemExit(f"duplicate stable identifier: {entry['key']} and {identifiers[folded]}")
        identifiers[folded] = entry["key"]
        rows.append({
            "key": entry["key"], "type": entry["type"],
            "title": entry.get("title", ""), "authors": entry.get("author", ""),
            "year": entry.get("year", ""),
            "venue": entry.get("journal", entry.get("booktitle", entry.get("howpublished", ""))),
            "volume": entry.get("volume", ""), "number": entry.get("number", ""),
            "pages_or_article": entry.get("pages", entry.get("articleno", "")),
            "identifier_type": identifier_type, "identifier": identifier,
            "citation_occurrences": str(cited.count(entry["key"])),
            "local_validation": "parsed; cited; unique identifier; no local conflict",
            "external_review_boundary": "identifier is the publisher/proceedings/archive record used for metadata review",
        })
    out = root / args.output; out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "entries": len(entries), "unique_entries": len(key_set),
        "citation_occurrences": len(cited), "all_entries_cited": not unused,
        "all_citations_resolved": not missing,
        "doi_entries": sum(identifier_map[k]["identifier_type"] == "DOI" for k in key_set),
        "stable_url_without_doi_entries": sum(identifier_map[k]["identifier_type"] == "stable URL" for k in key_set),
        "entries_without_stable_identifier": 0,
        "duplicate_identifiers": 0, "invalid_doi_syntax": 0,
        "scope": "local citation/structure audit plus exact matching to the retained publisher/proceedings/archive identifier provenance table; complete-paper content review is limited to the separately documented 22-paper calibration set",
    }
    (root / args.summary).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__": main()
