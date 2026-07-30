#!/usr/bin/env python3
"""Measure rule-conversion accuracy bucketed by Rumi word length.

Usage:
  python3 test_by_length.py                 # lengths 4..9 (default)
  python3 test_by_length.py 4 5 6 7 8 9 10  # custom set of lengths
  python3 test_by_length.py --all           # every length present in the data
  python3 test_by_length.py --sample 500    # random 500 words per length (faster/uniform)

Accuracy is exact-match of the PURE RULE engine (`translit.convert` via
`hybrid.rule_convert`). Rules are word-independent, so this is a fair measure of how
conversion difficulty scales with length — it does not depend on any dictionary lookup.
"""
import sys, random
import hybrid
from evaluate import load_rows

def main(argv):
    lengths = None
    sample_per = None
    seed = 0
    i = 0
    rest = []
    while i < len(argv):
        a = argv[i]
        if a == '--all': lengths = 'all'
        elif a == '--sample': i += 1; sample_per = int(argv[i])
        elif a == '--seed': i += 1; seed = int(argv[i])
        elif a.isdigit(): rest.append(int(a))
        i += 1
    if lengths != 'all':
        lengths = rest if rest else [4, 5, 6, 7, 8, 9]

    rows = load_rows()
    # bucket rows by length of the Rumi word
    buckets = {}
    for r, j in rows:
        buckets.setdefault(len(r), []).append((r, j))

    if lengths == 'all':
        lengths = sorted(buckets)

    rng = random.Random(seed)
    print("Rule-only accuracy by Rumi word length"
          + (" (sample %d/length)" % sample_per if sample_per else "") + "\n")
    print("%-6s %-8s %-8s %-9s  %s" % ("len", "count", "correct", "accuracy", "bar"))
    print("-" * 60)
    grand_ok = grand_n = 0
    for L in lengths:
        items = buckets.get(L, [])
        if not items:
            print("%-6d %-8d (no words of this length)" % (L, 0)); continue
        if sample_per and len(items) > sample_per:
            items = rng.sample(items, sample_per)
        ok = sum(1 for r, j in items if hybrid.rule_convert(r) == j)
        n = len(items)
        acc = ok / n
        grand_ok += ok; grand_n += n
        bar = '#' * round(acc * 30)
        print("%-6d %-8d %-8d %6.1f%%    %s" % (L, n, ok, acc*100, bar))
    print("-" * 60)
    if grand_n:
        print("TOTAL  %-8d %-8d %6.1f%%" % (grand_n, grand_ok, grand_ok/grand_n*100))

if __name__ == '__main__':
    main(sys.argv[1:])
