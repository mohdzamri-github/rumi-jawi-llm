#!/usr/bin/env python3
"""Randomly sample N words and measure conversion accuracy (exact match).

Usage:
  python3 test_sample.py                 # 100 random words, random seed
  python3 test_sample.py 200             # sample 200 words
  python3 test_sample.py 100 --seed 42   # reproducible sample
  python3 test_sample.py --all           # print every row, not just mismatches

Reports two honest numbers:
  * RULE-ONLY  — the rule engine alone (measures true generalization)
  * HYBRID(holdout) — dictionary lookup + rule fallback, with the sampled words
    REMOVED from the dictionary so it can't just memorize the answer.
"""
import sys, random
import translit, hybrid
from evaluate import load_rows

def main(argv):
    n = 100
    seed = None
    show_all = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--all':
            show_all = True
        elif a.startswith('--seed='):
            seed = int(a.split('=')[1])
        elif a == '--seed':
            i += 1
            seed = int(argv[i])            # consume the next token as the seed
        elif a.isdigit():
            n = int(a)
        i += 1

    if seed is None:
        seed = random.randrange(1_000_000)
    rng = random.Random(seed)

    rows = load_rows()
    sample = rng.sample(rows, min(n, len(rows)))

    # HYBRID(holdout): dictionary built from everything EXCEPT the sampled words
    sample_keys = {r for r, _ in sample}
    train = [(r, j) for r, j in rows if r not in sample_keys]
    hold_convert, _ = hybrid.make_hybrid(train)
    # HYBRID(app): full dictionary — exactly what the deployed jawi.py returns
    app_convert, _ = hybrid.make_hybrid(rows)

    rule_ok = hold_ok = app_ok = 0
    print("seed=%d   sample=%d words\n" % (seed, len(sample)))
    print("%-18s %-14s %-14s %-14s %-14s" %
          ("RUMI", "GOLD", "RULE", "HYB-holdout", "HYB-app"))
    print("-" * 78)
    for r, gold in sample:
        rp = hybrid.rule_convert(r)
        hp = hold_convert(r)
        ap = app_convert(r)
        r_ok, h_ok, a_ok = rp == gold, hp == gold, ap == gold
        rule_ok += r_ok; hold_ok += h_ok; app_ok += a_ok
        if show_all or not (r_ok and h_ok and a_ok):
            flag = ("R" if not r_ok else " ") + ("H" if not h_ok else " ") + ("A" if not a_ok else " ")
            print("%-18s %-14s %-14s %-14s %-14s  %s" % (r, gold, rp, hp, ap, flag))

    tot = len(sample)
    print("-" * 78)
    print("RULE-ONLY        : %3d/%d = %.1f%%   (rules alone; true generalization)"
          % (rule_ok, tot, rule_ok/tot*100))
    print("HYBRID (holdout) : %3d/%d = %.1f%%   (dict minus sample + rule fallback)"
          % (hold_ok, tot, hold_ok/tot*100))
    print("HYBRID (app)     : %3d/%d = %.1f%%   (full dict — what jawi.py returns)"
          % (app_ok, tot, app_ok/tot*100))
    print("(flags: R/H/A = rule/holdout/app wrong)")

if __name__ == '__main__':
    main(sys.argv[1:])
