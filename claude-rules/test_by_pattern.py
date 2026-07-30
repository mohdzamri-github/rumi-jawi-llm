#!/usr/bin/env python3
"""Measure rule-conversion accuracy bucketed by CV (consonant/vowel) pattern.

The pattern is the syllable skeleton of the Rumi word, digraph-aware: `ng ny kh gh sy`
count as one C, each vowel letter is a V.  e.g. buku->CVCV, makan->CVCVC, mengung->CVCVC.

Usage:
  python3 test_by_pattern.py                 # top 25 most-common patterns
  python3 test_by_pattern.py CVCV CVCVC CVC  # only these patterns
  python3 test_by_pattern.py --top 40        # top N patterns by frequency
  python3 test_by_pattern.py --min 200       # every pattern with >= 200 words

Accuracy is exact-match of the PURE RULE engine (dictionary-independent).
"""
import sys
import translit, hybrid
from evaluate import load_rows

def pattern(w):
    """CV skeleton via the digraph-aware tokenizer; None if word has non-letter tokens."""
    toks = translit.tokenize(w)
    return ''.join('V' if t == 'V' else 'C' for t, _ in toks)

def main(argv):
    want = []          # explicit patterns to show
    top = 25
    minc = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--top': i += 1; top = int(argv[i])
        elif a == '--min': i += 1; minc = int(argv[i])
        elif a.upper().strip('CV') == '' and a: want.append(a.upper())
        i += 1

    rows = load_rows()
    # only clean latin words map to a meaningful CV pattern
    stat = {}          # pattern -> [count, correct]
    for r, j in rows:
        if not r.isalpha():          # skip hyphens/reduplication/noise
            continue
        p = pattern(r)
        ok = translit.convert(r) == j
        s = stat.setdefault(p, [0, 0])
        s[0] += 1
        s[1] += ok

    # choose which patterns to display
    if want:
        show = [(p, stat.get(p, [0, 0])) for p in want]
    else:
        items = sorted(stat.items(), key=lambda kv: -kv[1][0])
        if minc is not None:
            items = [x for x in items if x[1][0] >= minc]
        else:
            items = items[:top]
        show = items

    print("Rule-only accuracy by CV pattern\n")
    print("%-14s %-8s %-8s %-9s  %s" % ("pattern", "count", "correct", "accuracy", "bar"))
    print("-" * 62)
    tot_n = tot_ok = 0
    for p, (n, ok) in show:
        if n == 0:
            print("%-14s %-8s (none)" % (p, 0)); continue
        acc = ok / n
        tot_n += n; tot_ok += ok
        print("%-14s %-8d %-8d %6.1f%%    %s" % (p, n, ok, acc*100, '#' * round(acc*30)))
    print("-" * 62)
    if tot_n:
        print("shown TOTAL   %-8d %-8d %6.1f%%" % (tot_n, tot_ok, tot_ok/tot_n*100))

if __name__ == '__main__':
    main(sys.argv[1:])
