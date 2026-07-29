# Transliteration Accuracy Results

Evaluation of the Rumi → Jawi transliterator (`jawi.py`: dictionary +
morphology + rules) against `rumi-jawi-unicode.csv` (65,998 unique words).

## Method

- **Held-out test** (`test_accuracy.py`): 1000 random words are removed from
  the dictionary, then predicted by the engine. A prediction is correct if it
  matches any attested Jawi spelling of that word.
- **10-fold cross-validation** (`cross_validate.py`): 5000 random words split
  into 10 folds of 500; each fold is held out and predicted once. Seeds are
  time-based (different sample every run) unless pinned with `--seed`.

## 10-fold cross-validation (n = 5000, k = 10)

### Run 1 (seed 1785286213667)

| Fold | n | Correct | Accuracy |
|------|---|---------|----------|
| 1 | 500 | 414 | 82.80% |
| 2 | 500 | 424 | 84.80% |
| 3 | 500 | 417 | 83.40% |
| 4 | 500 | 420 | 84.00% |
| 5 | 500 | 424 | 84.80% |
| 6 | 500 | 420 | 84.00% |
| 7 | 500 | 434 | 86.80% |
| 8 | 500 | 419 | 83.80% |
| 9 | 500 | 416 | 83.20% |
| 10 | 500 | 425 | 85.00% |

**Mean accuracy: 84.26% (±1.15%)**, min 82.80%, max 86.80%.

### Run 2 (different time-based seed)

**Mean accuracy: 84.02% (±1.53%)**, min 82.00%, max 86.40%.

## Accuracy by resolution source (all folds, run 1)

| Source | n | Correct | Accuracy |
|--------|---|---------|----------|
| morph (affix stripping + dictionary stem) | 2730 | 2535 | 92.86% |
| rules (phonemic fallback) | 1814 | 1268 | 69.90% |
| mixed (hyphenated / reduplication) | 456 | 410 | 89.91% |

Run 2: morph 92.75%, rules 71.03%, mixed 86.56%.

## Single held-out tests (n = 1000)

Repeated time-seeded runs: 83.2%, 84.4%, 85.1% — consistent with the
cross-validation mean.

## Notes

- These numbers measure performance on **fully out-of-vocabulary words**:
  every test word was removed from the dictionary before prediction, so the
  score reflects the rule/morphology engine only.
- The shipped CLI loads the **complete** dictionary (65,995/65,998 entries
  resolve to an attested spelling), so real-world accuracy on natural text —
  where most tokens are known words — is substantially higher than 84%.
- Residual errors are concentrated in categories that are not rule-
  predictable: Arabic-loan etymological letters (ح ص ض ط ظ ع غ ة),
  taling-vs-pepet `e` (`bebas`→`بيبس` vs `belas`→`بلس`), and inconsistent
  spellings inside the corpus itself (e.g. `marah`→`ماراه` but
  `kemarahannya`→`کمارهنڽ`).
