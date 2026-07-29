#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cross_validate.py - 10-fold cross-validation of the Jawi transliterator.

Samples N unique rumi words, splits them into 10 folds, and in turn holds
each fold out of the dictionary while the transliterator (dictionary +
morphology + rules) predicts the held-out words. Reports per-fold and
average accuracy against the attested Jawi spellings.
"""

import argparse
import collections
import random
import statistics
import time

import jawi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=5000,
                    help="total words to sample across all folds")
    ap.add_argument("-k", type=int, default=10, help="number of folds")
    ap.add_argument("--seed", type=int, default=None,
                    help="pin the sampling; default: seeded from current time")
    ap.add_argument("--errors", default="cv_errors.tsv",
                    help="write all mis-transliterations here ('' to disable)")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else int(time.time() * 1000)
    print(f"seed           : {seed}")

    full = jawi.load_dictionary()
    words = sorted(full)
    rng = random.Random(seed)
    sample = rng.sample(words, min(args.n, len(words)))
    rng.shuffle(sample)

    k = max(2, min(args.k, len(sample)))
    folds = [sample[i::k] for i in range(k)]

    all_errors = []
    fold_accs = []
    by_src = collections.Counter()
    by_src_ok = collections.Counter()

    for i, fold in enumerate(folds, 1):
        held_out = set(fold)
        train = {w: v for w, v in full.items() if w not in held_out}
        tr = jawi.Jawi(train)

        correct = 0
        for w in fold:
            pred, src = tr.transliterate(w)
            by_src[src] += 1
            if pred in full[w]:
                correct += 1
                by_src_ok[src] += 1
            else:
                all_errors.append((i, w, " | ".join(full[w]), pred, src))

        acc = correct / len(fold)
        fold_accs.append(acc)
        print(f"fold {i:2d}         : n={len(fold):4d}  correct={correct:4d}  "
              f"acc={acc:.2%}")

    mean = statistics.mean(fold_accs)
    stdev = statistics.stdev(fold_accs) if len(fold_accs) > 1 else 0.0
    print(f"\nmean accuracy  : {mean:.2%} (+/- {stdev:.2%})")
    print(f"min / max      : {min(fold_accs):.2%} / {max(fold_accs):.2%}")

    print("\nby source (all folds):")
    for src, n in by_src.most_common():
        print(f"  {src:7s} n={n:4d}  correct={by_src_ok[src]:4d}  "
              f"acc={by_src_ok[src] / n:.2%}")

    if args.errors:
        with open(args.errors, "w", encoding="utf-8") as f:
            f.write("fold\trumi\texpected\tpredicted\tsource\n")
            for row in all_errors:
                f.write("\t".join(map(str, row)) + "\n")
        print(f"\n{len(all_errors)} errors written to {args.errors}")


if __name__ == "__main__":
    main()
