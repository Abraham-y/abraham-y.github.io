#!/usr/bin/env python3
"""Build edit-codes/index.html and edit-codes/bounds.csv.

    python3 edit-codes/build.py

Inputs, both in this directory:
  base.csv     Houghten's five tables as numbers (family,q,n,d,lower,upper,source),
               generated from text snapshots of her pages.  Never edited by hand.
  records.csv  every bound that differs from base.csv: one row per claim, with its
               reference, and for a code published here its file and sha256.

The build applies each record that beats the current bound, then propagates lower
bounds along E(n+1,d) >= E(n,d) and E(n,d) >= E(n,d+1) (fixed length only).  It
refuses to build if any lower bound ends up above an upper bound, or if a code
file's header or checksum disagrees with its record.  It does not check
distances; check.py does that.
"""
import csv
import datetime
import hashlib
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BROCK = "https://www.cosc.brocku.ca/~shoughten/"

TABLES = [  # family, q, anchor, title, Houghten page
    ("fixed", 2, "binary", "Binary, fixed length", BROCK + "binaryedit.html"),
    ("fixed", 3, "ternary", "Ternary, fixed length", BROCK + "ternaryedit.html"),
    ("fixed", 4, "quaternary", "Quaternary, fixed length", BROCK + "quaternaryedit.html"),
    ("variable", 2, "binary-var", "Binary, variable length", BROCK + "binaryeditvar.html"),
    ("variable", 3, "ternary-var", "Ternary, variable length", BROCK + "ternaryeditvar.html"),
]

REFS = {
    "Y26": ("A. Yeung, <i>Coding Agents for Coding Theory</i>, NeurIPS 2026 MATH-AI Workshop, "
            "arXiv:2609.39081", "https://arxiv.org/abs/2609.39081", True),
    "WH25": ("F. Weindel and R. Heckel, <i>LLM-Guided Search for Deletion-Correcting Codes</i>, "
             "arXiv:2504.00613, Table 3. The codewords are not published.",
             "https://arxiv.org/abs/2504.00613", False),
    "here": ("First published on this page.", None, True),
}
REF_SHORT = {"Y26": "Yeung 2026", "WH25": "Weindel &amp; Heckel 2025", "here": "this page"}


class Cell:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.base_lo, self.base_hi = lo, hi
        self.lo_by = ("H",)      # ("H",) | ("rec", i) | ("der", key)
        self.hi_by = ("H",)
        self.recs = []


def load():
    cells = {}
    with open(os.path.join(HERE, "base.csv")) as fh:
        for r in csv.DictReader(fh):
            key = (r["family"], int(r["q"]), int(r["n"]), int(r["d"]))
            cells[key] = Cell(int(r["lower"]), int(r["upper"]) if r["upper"] else None)
    with open(os.path.join(HERE, "records.csv")) as fh:
        recs = list(csv.DictReader(fh))
    return cells, recs


def check_code(rec):
    """Header fields and checksum of a code file against its record."""
    path = os.path.join(HERE, rec["code"])
    text = open(path).read()
    fields = dict(re.findall(r"^#\s*([nqd]|size)\s*=\s*(\d+)\s*$", text, re.M))
    for k, want in (("q", rec["q"]), ("n", rec["n"]), ("d", rec["d"]), ("size", rec["lower"])):
        if fields.get(k) != want:
            sys.exit(f"{rec['code']}: header {k} = {fields.get(k)}, record says {want}")
    words = sorted(l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#"))
    if len(words) != int(rec["lower"]):
        sys.exit(f"{rec['code']}: {len(words)} words, record says {rec['lower']}")
    digest = hashlib.sha256("".join(w + "\n" for w in words).encode()).hexdigest()
    if digest != rec["sha256"]:
        sys.exit(f"{rec['code']}: sha256 {digest}, record says {rec['sha256']}")
    return os.path.getsize(path)


def apply(cells, recs):
    for i, r in sorted(enumerate(recs), key=lambda t: t[1]["date"]):
        if r["ref"] not in REFS:
            sys.exit(f"record {i}: unknown ref {r['ref']!r}")
        if r["code"]:
            r["bytes"] = check_code(r)
        key = (r["family"], int(r["q"]), int(r["n"]), int(r["d"]))
        c = cells.get(key)
        if c is None:
            sys.exit(f"record {i}: cell {key} is not in base.csv")
        c.recs.append(i)
        if r["lower"] and int(r["lower"]) > c.lo:
            c.lo, c.lo_by = int(r["lower"]), ("rec", i)
        if r["upper"] and (c.hi is None or int(r["upper"]) < c.hi):
            c.hi, c.hi_by = int(r["upper"]), ("rec", i)


def derive(cells):
    """E(n+1,d) >= E(n,d) (append one symbol) and E(n,d) >= E(n,d+1); for upper
    bounds E(n,d) <= E(n,d-1), E(n,d) <= E(n+1,d) and E(n+1,d) <= q E(n,d).  Upper
    bounds are only tightened where the table lists one."""
    changed = True
    while changed:
        changed = False
        for (fam, q, n, d), c in cells.items():
            if fam != "fixed":
                continue
            for src in ((fam, q, n - 1, d), (fam, q, n, d + 1)):
                s = cells.get(src)
                if s and s.lo > c.lo:
                    c.lo, c.lo_by, changed = s.lo, ("der", src), True
            if c.hi is None:
                continue
            for src, mult in (((fam, q, n, d - 1), 1), ((fam, q, n + 1, d), 1), ((fam, q, n - 1, d), q)):
                s = cells.get(src)
                if s and s.hi is not None and s.hi * mult < c.hi:
                    c.hi, c.hi_by, changed = s.hi * mult, ("der", src), True
    for key, c in cells.items():
        if c.hi is not None and c.lo > c.hi:
            sys.exit(f"cell {key}: lower {c.lo} > upper {c.hi}.  A record beats a proven "
                     "upper bound: treat it as a bug.")


def root(cells, key, attr):
    """The record or base entry a derived bound comes from."""
    by = getattr(cells[key], attr)
    while by[0] == "der":
        key = by[1]
        by = getattr(cells[key], attr)
    return key, by


def name(key):
    fam, q, n, d = key
    return f"E<sub>{q}</sub>({n},{d})"


def fmt(v, q, d, fam):
    if fam == "fixed" and d <= 2 and v >= 10 ** 5:
        k = 0
        while q ** k < v:
            k += 1
        if q ** k == v:
            return f"{q}<sup>{k}</sup>"
    return str(v)


def text_of(lo, hi, q, d, fam):
    if hi == lo:
        return fmt(lo, q, d, fam)
    if hi is None:
        return f"&ge;{fmt(lo, q, d, fam)}"
    return f"{fmt(lo, q, d, fam)}&ndash;{fmt(hi, q, d, fam)}"


def anchor(key):
    fam, q, n, d = key
    return f"r{'v' if fam == 'variable' else ''}{q}-{n}-{d}"


def size_str(b):
    return f"{b / 1e6:.1f} MB" if b >= 10 ** 6 else f"{max(1, round(b / 1e3))} kB"


def table_html(cells, recs, fam, q):
    keys = [k for k in cells if k[0] == fam and k[1] == q]
    ns = sorted({k[2] for k in keys})
    ds = sorted({k[3] for k in keys})
    out = ['<div class="scroll"><table class="b"><thead><tr><th scope="col">n\\d</th>']
    out += [f'<th scope="col">{d}</th>' for d in ds]
    out.append("</tr></thead><tbody>")
    for n in ns:
        out.append(f'<tr><th scope="row">{n}</th>')
        for d in ds:
            key = (fam, q, n, d)
            c = cells.get(key)
            if c is None:
                out.append("<td></td>")
                continue
            txt = text_of(c.lo, c.hi, q, d, fam)
            cls, title, link = [], "", None
            if c.lo_by[0] != "H":
                rkey, by = root(cells, key, "lo_by")
                r = recs[by[1]] if by[0] == "rec" else None
                was = text_of(c.base_lo, c.base_hi, q, d, fam)
                if c.lo_by[0] == "der":
                    cls.append("der")
                    title = f"from {re.sub('<[^>]+>', '', name(rkey))}; Houghten: {was}"
                    if by[0] == "H":
                        link = anchor(key)
                elif REFS[r["ref"]][2]:
                    cls.append("new")
                    title = f"{r['method']}, {html.unescape(REF_SHORT[r['ref']])}; Houghten: {was}"
                else:
                    cls.append("rep")
                    title = f"reported by {html.unescape(REF_SHORT[r['ref']])}, no public code; Houghten: {was}"
                if by[0] == "rec":
                    link = anchor(rkey)
            elif d <= 2 or c.lo == 1 == c.hi:
                cls.append("dim")
            attrs = f' class="{" ".join(cls)}"' if cls else ""
            if title:
                attrs += f' title="{html.escape(title, quote=True)}"'
            body = f'<a href="#{link}">{txt}</a>' if link else txt
            out.append(f"<td{attrs}>{body}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def changes_html(cells, recs):
    holders = {}
    for key, c in cells.items():
        if c.lo_by[0] == "rec":
            holders[key] = c
    derived, own = {}, []
    for key, c in cells.items():
        if c.lo_by[0] == "der":
            rkey, by = root(cells, key, "lo_by")
            if by[0] == "rec":
                derived.setdefault(rkey, []).append(key)
            else:
                own.append((key, rkey))
    rows = []
    order = sorted(holders, key=lambda k: (recs[holders[k].lo_by[1]]["date"], k[1], k[3], k[2]), reverse=True)
    for key in order:
        c = holders[key]
        r = recs[c.lo_by[1]]
        fam, q, n, d = key
        was = text_of(c.base_lo, c.base_hi, q, d, fam)
        now = text_of(c.lo, c.hi, q, d, fam)
        ref_txt, ref_url, public = REFS[r["ref"]]
        src = (f'<a href="{ref_url}" target="_blank" rel="noopener">{REF_SHORT[r["ref"]]}</a>'
               if ref_url else REF_SHORT[r["ref"]])
        if r["code"]:
            code = (f'<a href="{r["code"]}">codewords</a> <span class="sz">{size_str(r["bytes"])}</span>'
                    f'<br><code class="sha" title="sha256 of the sorted codewords">{r["sha256"][:16]}&hellip;</code>')
        else:
            code = '<span class="muted">not published</span>'
        extra = []
        older = [recs[i] for i in c.recs if i != c.lo_by[1] and recs[i]["lower"]]
        for o in older:
            when = f", {o['date']}" if o["ref"] == "here" else ""
            extra.append(f"earlier: {o['lower']} ({REF_SHORT[o['ref']]}{when})")
        der = sorted(derived.get(key, []), key=lambda k: (k[3], k[2]))
        if der:
            groups = {}
            for k in der:
                groups.setdefault(k[3], []).append(k[2])
            parts = []
            for dd, nn in sorted(groups.items()):
                span = f"{nn[0]}" if len(nn) == 1 else f"{nn[0]}&ndash;{nn[-1]}"
                parts.append(f"E<sub>{q}</sub>({span},{dd}) &ge; {c.lo}")
            extra.append("and so " + ", ".join(parts))
        note = f'<div class="ex">{"; ".join(extra)}</div>' if extra else ""
        rows.append(
            f'<tr id="{anchor(key)}"><td class="cell">{name(key)}</td>'
            f'<td class="num muted">{was}</td><td class="num"><b>{now}</b></td>'
            f'<td>{html.escape(r["method"])}{note}</td><td class="nw">{r["date"]}</td>'
            f'<td>{src}</td><td class="nw">{code}</td></tr>')
    for key, rkey in sorted(own):
        c = cells[key]
        fam, q, n, d = key
        url = next(u for f, qq, _, _, u in TABLES if (f, qq) == (fam, q))
        rows.append(
            f'<tr id="{anchor(key)}"><td class="cell">{name(key)}</td>'
            f'<td class="num muted">{text_of(c.base_lo, c.base_hi, q, d, fam)}</td>'
            f'<td class="num"><b>{text_of(c.lo, c.hi, q, d, fam)}</b></td>'
            f'<td>append one symbol to a code for {name(rkey)}, which Houghten\'s table gives as '
            f'&ge;{cells[rkey].lo}</td><td class="nw">&ndash;</td>'
            f'<td><a href="{url}" target="_blank" rel="noopener">Houghten</a></td><td class="nw">&ndash;</td></tr>')
    return ('<div class="scroll"><table class="ch"><thead><tr><th>cell</th><th>Houghten</th><th>now</th>'
            '<th>construction</th><th>date</th><th>source</th><th>code</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>"), len(holders), sum(len(v) for v in derived.values()), len(own)


def write_csv(cells, recs):
    def src(key, attr):
        c = cells[key]
        by = getattr(c, attr)
        if by[0] == "H":
            return "houghten"
        if by[0] == "rec":
            return recs[by[1]]["ref"]
        f, q, n, d = by[1]
        return f"derived:E{q}({n},{d})"
    with open(os.path.join(HERE, "bounds.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "q", "n", "d", "lower", "upper", "lower_source", "upper_source"])
        for key in sorted(cells):
            c = cells[key]
            w.writerow(list(key) + [c.lo, "" if c.hi is None else c.hi, src(key, "lo_by"),
                                    "" if c.hi is None else src(key, "hi_by")])


STYLE = """
main.wide { max-width: 1080px; }
.prose { max-width: 720px; }
.prose p { color: var(--fg-2); }
:root { --rep-bg: #e9eef3; --rep-fg: #3d5268; }
@media (prefers-color-scheme: dark) { :root { --rep-bg: #1f262d; --rep-fg: #a9bfd4; } }
.scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--card); margin: 0 0 8px; }
table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
table.b { font-family: var(--mono); font-size: 12px; width: max-content; min-width: 100%; }
table.b th, table.b td { padding: 4px 9px; text-align: right; border-bottom: 1px solid var(--line); white-space: nowrap; }
table.b tr:last-child td, table.b tr:last-child th { border-bottom: 0; }
table.b thead th { color: var(--fg-3); font-weight: 600; background: var(--card); }
table.b tbody th { position: sticky; left: 0; background: var(--card); color: var(--fg-3); font-weight: 600; border-right: 1px solid var(--line); }
table.b td.dim { color: var(--fg-3); }
table.b td.new { background: var(--accent-bg); color: var(--accent); font-weight: 600; }
table.b td.rep { background: var(--rep-bg); color: var(--rep-fg); }
table.b td.der { color: var(--accent); }
table.b td a { color: inherit; border: 0; }
table.b td a:hover { text-decoration: underline; }
table.ch { font-size: 14px; width: 100%; }
table.ch th { text-align: left; font-family: var(--mono); font-size: 11px; font-weight: 600; color: var(--fg-3); padding: 8px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
table.ch td { padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; color: var(--fg-2); }
table.ch tr:last-child td { border-bottom: 0; }
table.ch tr:target td { background: var(--accent-bg); }
table.ch td.cell { color: var(--fg); white-space: nowrap; }
table.ch td.num { font-family: var(--mono); font-size: 13px; white-space: nowrap; text-align: right; }
table.ch td.num b { color: var(--fg); font-weight: 600; }
table.ch .nw { white-space: nowrap; }
table.ch .ex { font-size: 12.5px; color: var(--fg-3); margin-top: 2px; }
table.ch .sz { color: var(--fg-3); font-size: 12px; }
table.ch .sha { font-size: 11px; color: var(--fg-3); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--fg-2); margin: 0 0 14px; }
.legend span::before { content: ""; display: inline-block; width: 11px; height: 11px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; border: 1px solid var(--line); }
.legend .new::before { background: var(--accent-bg); border-color: var(--accent); }
.legend .rep::before { background: var(--rep-bg); }
.legend .der::before { background: var(--card); border-color: var(--accent); border-style: dashed; }
.tnote { font-size: 13px; color: var(--fg-3); margin: 4px 0 0; }
section h2 { margin-bottom: 6px; }
section .sub { font-size: 14px; color: var(--fg-2); margin-bottom: 12px; }
.refs { font-size: 14px; color: var(--fg-2); padding-left: 1.2em; }
.refs li { margin-bottom: 6px; }
pre.cmd { font-family: var(--mono); font-size: 13px; background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; overflow-x: auto; }
"""


def page(cells, recs):
    changes, n_new, n_der, n_own = changes_html(cells, recs)
    own_txt = ("" if not n_own else
               f" {'One more follows' if n_own == 1 else f'{n_own} more follow'} from other entries of "
               "Houghten's own tables.")
    today = datetime.date.today().isoformat()
    upper_changed = any(c.hi_by[0] != "H" for c in cells.values())
    secs = []
    for fam, q, anc, title, url in TABLES:
        if fam == "fixed":
            sub = (f"E<sub>{q}</sub>(n,d) for words of length n over {q} symbols. "
                   f'Houghten\'s table: <a href="{url}" target="_blank" rel="noopener">{url.split("/")[-1]}</a>.')
        else:
            sub = (f"The largest code over {q} symbols with minimum edit distance d whose longest word "
                   f'has length n. Houghten\'s table: <a href="{url}" target="_blank" rel="noopener">'
                   f'{url.split("/")[-1]}</a>.')
        note = ""
        if (fam, q) == ("fixed", 4):
            note = ('<p class="tnote">Houghten\'s quaternary page gives only lower bounds for n &gt; 10; '
                    'they are written with &ge; here.</p>')
        if (fam, q) == ("fixed", 2):
            note = ('<p class="tnote">Houghten\'s binary page has no rows for n = 13&ndash;15 or 17&ndash;19, '
                    '21, 22 and 25&ndash;31.</p>')
        secs.append(f'<section id="{anc}"><h2>{title}</h2><p class="sub">{sub}</p>'
                    f'{table_html(cells, recs, fam, q)}{note}</section>')
    nav = " ".join(f'<a href="#{anc}">{title.lower()}</a>' for _, _, anc, title, _ in TABLES)
    refs = "".join(
        f'<li>{txt} <a href="{url}" target="_blank" rel="noopener">{url.split("//")[1]}</a></li>'
        for key, (txt, url, _) in REFS.items() if url)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Edit-metric code bounds · Abraham Yeung</title>
<meta name="description" content="Tables of the best known bounds on E_q(n,d), the size of the largest code of length n over q symbols with minimum Levenshtein distance d, for binary, ternary and quaternary codes, with codewords for every new bound.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css?v=6">
<style>{STYLE}</style>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🥕</text></svg>">
</head>
<body>
<main class="wide">
  <p class="back"><a href="../">← abrahamyeung.com</a></p>
  <h1 style="margin-top:28px">Bounds on edit-metric codes</h1>
  <div class="prose">
    <p class="lede">E<sub>q</sub>(n,d) is the largest number of words of length n over q symbols such that every two of them are at Levenshtein distance at least d. The distance counts the insertions, deletions and substitutions needed to turn one word into the other. These tables give the best known bounds for binary, ternary and quaternary codes of fixed length, and for binary and ternary codes of variable length.</p>
    <p>The tables start from <a href="{BROCK}edit.html" target="_blank" rel="noopener">Sheridan Houghten's tables</a> at Brock University, copied on 27 October 2026, and record improvements found since then. {n_new} cells have a better lower bound than Houghten's table, and {n_der} more follow from those.{own_txt} Every new lower bound that comes with a code links to the codewords and their SHA-256, and <a href="check.py">check.py</a> checks any of them. This page is maintained separately from Houghten's.</p>
    <p class="small muted">Last updated {today}. Corrections and new codes are welcome at <a href="mailto:ayeung16@stanford.edu">ayeung16@stanford.edu</a>. Data: <a href="bounds.csv">bounds.csv</a> (every cell, with its source), <a href="records.csv">records.csv</a> (every claim beyond Houghten's table).</p>
  </div>
  <nav class="nav"><a href="#changes">improvements</a> {nav} <a href="#notes">notes</a></nav>

  <section id="changes">
    <h2>Improvements</h2>
    <p class="sub">Cells where the best known bound differs from Houghten's table, newest first.</p>
    {changes}
  </section>

  <section id="key" style="margin-top:44px">
    <div class="legend"><span class="new">new code, linked</span><span class="rep">reported in the literature, codewords not public</span><span class="der">follows from an improved cell</span></div>
  </section>
  {"".join(secs)}

  <section id="notes" class="prose">
    <h2>Notes</h2>
    <h3 style="margin:14px 0 6px">Reading the tables</h3>
    <p>A single number is the exact value. a&ndash;b means the value is between a and b. &ge;a means only a lower bound is known. Hover a coloured cell to see where its value comes from and what Houghten's table gives; click it to jump to its entry in the list of improvements. In the variable-length tables a code may contain words of any length up to n, the empty word included.</p>
    <h3 style="margin:14px 0 6px">Bounds that follow from others</h3>
    <p>Appending the same symbol to every word of a code leaves all distances unchanged, so E<sub>q</sub>(n+1,d) &ge; E<sub>q</sub>(n,d). A code with minimum distance d+1 also has minimum distance d, so E<sub>q</sub>(n,d) &ge; E<sub>q</sub>(n,d+1). Cells marked as following from an improved cell take their value this way. {"Some upper bounds have changed; see bounds.csv." if upper_changed else "Every upper bound is Houghten's."}</p>
    <h3 style="margin:14px 0 6px">Checking a code</h3>
    <p>Each code file has a short header declaring q, n, d, the size and the SHA-256 of the sorted codewords, followed by one word per line. check.py needs only Python 3 and checks one file at a time:</p>
    <pre class="cmd">python3 check.py codes/edit4_n13_d3_size500882.txt</pre>
    <p>Before it was listed, each code here was also accepted by three verifiers that share no code: a ball-marking check, a sort-based ball-collision check and a pairwise bit-parallel Levenshtein check.</p>
    <h3 style="margin:14px 0 6px">How the new codes were found</h3>
    <p>The entries from Yeung 2026 came from searching for codes invariant under a chosen group of symbol permutations and reversal, which shrinks the search to orbits of words. Of the entries first published here, the large quaternary ones are lexicodes: take the words in lexicographic order and keep each one that is far enough from every word kept so far. The binary and ternary ones come from iterated local search for a maximum independent set in the conflict graph, whose vertices are all q<sup>n</sup> words, with an edge between two words closer than d. Where that graph is too large, the search runs on the graph of orbits under a small group of symbol permutations and reversal, which the paper uses for the quaternary cells. The same search reproduces every exact value it was run on before any open cell was believed. All of these searches were run by an LLM coding agent under the protocol in the paper, which also describes what went wrong along the way.</p>
    <h3 style="margin:14px 0 6px">Sources</h3>
    <ul class="refs">
      <li>S. Houghten, tables of bounds on edit-metric codes, Brock University: <a href="{BROCK}edit.html" target="_blank" rel="noopener">index</a>, with the five tables linked above. They first appeared in S. K. Houghten, D. Ashlock and J. Lenarz, Construction of optimal edit metric codes, <i>Proc. 2006 IEEE Information Theory Workshop</i>, 259&ndash;263, and S. Baker, R. Flack and S. Houghten, Optimal variable-length insertion-deletion correcting codes and edit metric codes, <i>Congressus Numerantium</i> 186 (2008), 65&ndash;80. Houghten's pages list the later improvements and their sources.</li>
      {refs}
    </ul>
  </section>

  <footer>Abraham Yeung · <a href="mailto:ayeung16@stanford.edu">ayeung16@stanford.edu</a></footer>
</main>
</body>
</html>
"""


def main():
    cells, recs = load()
    apply(cells, recs)
    derive(cells)
    write_csv(cells, recs)
    with open(os.path.join(HERE, "index.html"), "w") as fh:
        fh.write(page(cells, recs))
    print(f"built index.html and bounds.csv: {len(cells)} cells, {len(recs)} records")


if __name__ == "__main__":
    main()
