#!/usr/bin/env python3
"""Check an edit-metric code file from abrahamyeung.com/edit-codes/.

    python3 check.py codes/edit4_n13_d3_size500882.txt

The file declares '# n = ...', '# d = ...' and '# q = ...' in its header and
lists one codeword per line over the symbols 0 .. q-1.  The check passes when
every word has length n, uses only those symbols, appears once, and every two
words are at Levenshtein (insert / delete / substitute) distance at least d.

Method.  Edit distance is a path metric over strings of all lengths, so with
r = (d-1)//2 and s = d-1-r, two words are within distance d-1 exactly when the
radius-r ball of one meets the radius-s ball of the other.  The script marks
every radius-r ball in one bitset per string length and fails on any string
marked twice; for even d it then checks each word's radius-s ball against the
marks of the other words.  Optimal edit paths between q-ary words only pass
through q-ary words, so the balls are taken over the q symbols.  A code of
500,000 words at n = 13 takes about a minute and under 200 MB.

Codes of at most 5,000 words are checked pair by pair instead (Wagner-Fischer
on every pair).  These are the large-d codes, whose balls are too big to list:
at q = 4, n = 16, d = 7 the bitsets alone would need 46 GB.

Variable-length codes (the binary and ternary variable-length tables) say
'# family = variable' in the header.  Their words may have any length from 0 to
n, the empty word written as '-', and they are always checked pair by pair.

Python 3 standard library only.  No floating point.
"""
import hashlib
import re
import sys


def header(text):
    """The integer fields n, d, q, each filling a whole comma-separated field
    of a '#' line, and the claimed sha256 if there is one."""
    vals = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#"):
            continue
        for field in re.split(r"[,;]", line[1:]):
            m = re.fullmatch(r"\s*([ndq])\s*=\s*(\d+)\s*", field)
            if m:
                k, v = m.group(1), int(m.group(2))
                if vals.get(k, v) != v:
                    sys.exit(f"FAIL: header gives {k} twice ({vals[k]} and {v})")
                vals[k] = v
    for k in "ndq":
        if k not in vals:
            sys.exit(f"FAIL: header has no '# {k} = ...' line")
    m = re.search(r"sha256\(codewords\)\s*=\s*([0-9a-f]{64})", text)
    variable = re.search(r"^#\s*family\s*=\s*variable\s*$", text, re.M) is not None
    return vals["n"], vals["d"], vals["q"], m.group(1) if m else None, variable


def ball1(w, sym):
    out = {w}
    for i in range(len(w)):
        out.add(w[:i] + w[i + 1:])
        for c in sym:
            if c != w[i]:
                out.add(w[:i] + c + w[i + 1:])
    for i in range(len(w) + 1):
        for c in sym:
            out.add(w[:i] + c + w[i:])
    return out


def ball(w, r, sym):
    cur = {w}
    for _ in range(r):
        nxt = set()
        for x in cur:
            nxt |= ball1(x, sym)
        cur = nxt
    return cur


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i]
        for j in range(1, len(b) + 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1])))
        prev = cur
    return prev[-1]


PAIRWISE_MAX = 5000


def main(path):
    text = open(path).read()
    n, d, q, claimed, variable = header(text)
    words = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    sym = "0123456789"[:q]
    if not 2 <= q <= 10 or d < 1:
        sys.exit(f"FAIL: unsupported q = {q} or d = {d}")
    seen = set()
    for w in words:
        if variable and w == "-":
            pass
        elif variable and (not 1 <= len(w) <= n or set(w) - set(sym)):
            sys.exit(f"FAIL: {w!r} is not a word of length 0..{n} over 0..{q - 1}")
        elif not variable and (len(w) != n or set(w) - set(sym)):
            sys.exit(f"FAIL: {w!r} is not a word of length {n} over 0..{q - 1}")
        if w in seen:
            sys.exit(f"FAIL: {w!r} appears twice")
        seen.add(w)
    digest = hashlib.sha256("".join(w + "\n" for w in sorted(words)).encode()).hexdigest()
    if claimed and claimed != digest:
        sys.exit(f"FAIL: header sha256 {claimed[:16]}... but the words hash to {digest[:16]}...")

    if variable or len(words) <= PAIRWISE_MAX:
        plain = ["" if w == "-" else w for w in words]
        for i, a in enumerate(plain):
            for b in plain[i + 1:]:
                if lev(a, b) < d:
                    a, b = a or "-", b or "-"
                    sys.exit(f"FAIL: {a!r} and {b!r} are within distance {d - 1}")
        print(f"OK  q={q} n={n} d={d} size={len(words)}{' (variable length)' if variable else ''} sha256={digest}")
        return

    r, s = (d - 1) // 2, d - 1 - (d - 1) // 2
    marks = {L: bytearray(q ** L // 8 + 1) for L in range(max(0, n - r), n + r + 1)}

    def key(x):
        return int(x, q) if x else 0

    def culprit(x, me):
        for j, w in enumerate(words):
            if j != me and x in ball(w, r, sym):
                return words[j]

    for i, w in enumerate(words):
        for x in ball(w, r, sym):
            k, row = key(x), marks[len(x)]
            if row[k >> 3] >> (k & 7) & 1:
                sys.exit(f"FAIL: {culprit(x, i)!r} and {w!r} are within distance {d - 1}")
            row[k >> 3] |= 1 << (k & 7)
    if s > r:
        for i, w in enumerate(words):
            for x in ball(w, s, sym) - ball(w, r, sym):
                row = marks.get(len(x))
                if row is None:
                    continue
                k = key(x)
                if row[k >> 3] >> (k & 7) & 1:
                    sys.exit(f"FAIL: {culprit(x, i)!r} and {w!r} are within distance {d - 1}")
    print(f"OK  q={q} n={n} d={d} size={len(words)} sha256={digest}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
