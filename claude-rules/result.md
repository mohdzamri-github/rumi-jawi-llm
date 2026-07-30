# Rumi → Jawi — Rule Accuracy Evaluation

Evaluation of the rule engine (`translit.py`) and the hybrid converter (`hybrid.py`)
against `rumi-jawi-unicode.csv`.

- **Metric:** exact string match (predicted Jawi === gold Jawi).
- **Split:** deterministic 80/20 train/test by a hash of the Rumi word
  (`evaluate.split`, seed 12345), so the test words were never used while deriving rules.
- **Data:** 71,449 raw pairs → **65,099** clean pairs after filtering
  (Rumi must be `[a-z]+`; Jawi must be all Arabic-block characters).
  Train = 52,193 · Test = 12,906.
- Reproduce with: `python3 evaluate.py translit`

## Headline numbers

| System | Scenario | Accuracy |
|---|---|---|
| **Rules only** | held-out **test** (unseen words) | **65.45%** |
| Rules only | train split | 65.20% |
| Rules only | all clean rows | 65.25% |
| **Hybrid** (dict = train) + rule fallback | held-out **test** | 65.45% |
| **Hybrid** (full 59,847-word dict) | all rows (what the CLI returns) | **99.09%** |

Notes:
- On the held-out test set the hybrid equals rule-only, because test words are by
  construction absent from the dictionary and fall through to the rules — this is the
  honest measure of generalisation to new words.
- The 99.09% figure is what an end user sees for words that exist in the dictionary
  (the remaining ~0.9% are duplicate Rumi keys that map to more than one Jawi spelling,
  where only the first spelling can win).

## Effect of the rule improvements

Measured on the same split, before vs. after the three fixes
(prefix plain-alef junction, `x` keheh/initial-`ز`, `-sme` → `ى`):

| | Train | Test |
|---|---|---|
| Before | 64.35% | 64.57% |
| After  | **65.20%** | **65.45%** |
| Δ | +0.85 | **+0.88** |

Small in aggregate because the fixes target specific patterns, but each was verified
to *raise* accuracy with no regression (candidate rules that the data showed would
regress — e.g. `k`-before-suffix → `ق`, `-ik` → `ک`, `-at` → `ة` — were rejected).

## Rule accuracy by word length (syllables)

Rule engine, all clean rows:

| Syllables | Words | Correct | Accuracy |
|---:|---:|---:|---:|
| 1 | 734 | 507 | 69.1% |
| 2 | 13,906 | 10,279 | 73.9% |
| 3 | 26,510 | 18,608 | 70.2% |
| 4 | 17,466 | 9,875 | 56.5% |
| 5 | 5,159 | 2,646 | 51.3% |
| 6 | 1,057 | 458 | 43.3% |
| 7+ | 267 | 104 | 39.0% |

Accuracy falls with length: every additional syllable adds another chance for an
ambiguous vowel (unwritten schwa `a`, pepet-vs-taling `e`) to be guessed wrong, and the
errors compound multiplicatively across a word.

## Where the rules fail (test set)

Of 12,906 test words, **8,447 correct / 4,459 wrong**. Breaking the failures down by the
single-character edit that would fix them (root causes overlap; grouped by cause):

| Root cause | Approx. share of failures | Example (pred → gold) |
|---|---:|---|
| Medial/final `a` written-or-dropped (lexical schwa) | ~32% | `abangan` اباڠن → ابڠن ; `berabjad` بربجد → برابجد |
| Unwritten vs written `e`/`i` (pepet vs taling) | ~21% | `abese` ابسي → ابيسي |
| Native `ق` vs loan `ک` for `k` | ~8% | `pengadukan` …کن → …قن ; `abstrak` …ترق → …ترک |
| Etymological Arabic letters (ع ص ض ط ظ ث ذ ح) | ~10% | `aklam` اکلم → اعلم ; `hajah` هاجه → حاجه |
| Hamza (ء) placement in vowel junctions | ~6% | `mengacarai` …چاراي → …چاراءي |
| Multiple / other | ~23% | — |

## Interpretation

The mapping Rumi → Jawi is **inherently ambiguous**: the Latin spelling does not encode
whether an `a`/`e` is written, nor whether a consonant follows Arabic etymological
spelling. Those two facts (the top ~63% of failures above) are *lexical* — they depend
on the individual word's origin, not on any pattern in its Rumi form — so no
deterministic rule can recover them. This is why pure rules plateau around **65%** and
why a dictionary layer (→ **99%**) is the practical converter.

The genuinely rule-addressable residue is the `k` (`ق`/`ک`) and hamza-junction cases
(~14% of failures); these are already at their majority-class optimum in the current
ruleset (chasing them further trades correct majority cases for incorrect minority ones).

---
*Generated from `rumi-jawi-unicode.csv` (71,449 pairs). Regenerate the headline numbers
with `python3 evaluate.py translit`.*
