#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_accuracy.py - held-out accuracy test for the Jawi transliterator.

Takes 1000 random unique rumi words out of the dictionary, rebuilds the
transliterator without them, then measures how often the prediction matches
one of the attested Jawi spellings. Error breakdown is written to errors.tsv.
"""

import argparse
import collections
import random
import sys
import time

import jawi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=1000, help="held-out sample size")
    ap.add_argument("--seed", type=int, default=None,
                    help="pin the sample; default: seeded from current time")
    ap.add_argument("--errors", default="errors.tsv")
    ap.add_argument("--rules-only", action="store_true",
                    help="bypass dictionary+morphology, score the raw rules")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else int(time.time() * 1000)
    print(f"seed           : {seed}")

    full = jawi.load_dictionary()
    words = sorted(full)
    rng = random.Random(seed)
    held_out = set(rng.sample(words, min(args.n, len(words))))

    train = {k: v for k, v in full.items() if k not in held_out}
    tr = jawi.Jawi(train)

    correct = 0
    errors = []
    by_src = collections.Counter()
    by_src_ok = collections.Counter()

    for w in sorted(held_out):
        if args.rules_only:
            pred, src = jawi.rules_word(w), "rules"
        else:
            pred, src = tr.transliterate(w)
        ok = pred in full[w]
        by_src[src] += 1
        if ok:
            correct += 1
            by_src_ok[src] += 1
        else:
            errors.append((w, " | ".join(full[w]), pred, src))

    total = len(held_out)
    print(f"held-out words : {total}")
    print(f"correct        : {correct}")
    print(f"accuracy       : {correct / total:.2%}")
    print("\nby source:")
    for src, n in by_src.most_common():
        print(f"  {src:7s} n={n:4d}  correct={by_src_ok[src]:4d}  "
              f"acc={by_src_ok[src] / n:.2%}")

    with open(args.errors, "w", encoding="utf-8") as f:
        f.write("rumi\texpected\tpredicted\tsource\n")
        for row in errors:
            f.write("\t".join(row) + "\n")
    print(f"\n{len(errors)} errors written to {args.errors}")


if __name__ == "__main__":
    main()
