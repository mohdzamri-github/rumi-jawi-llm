# Rumi → Jawi Converter

Convert Malay words from **Rumi** (Latin script) to **Jawi** (Arabic script).

The rules were derived empirically from `rumi-jawi-unicode.csv` (71,450 Rumi–Jawi pairs).
The full derivation — 11 documented experiments — lives in [`plan.md`](plan.md).

## Accuracy

Measured as exact-match on a held-out 20% test split (words unseen during rule derivation):

| System | Accuracy | Scenario |
|---|---|---|
| **Hybrid** (dictionary + rule fallback) | **98.8%** | random Malay dictionary words |
| Pure rules only | ~65% | genuinely novel / out-of-vocabulary words |

Rumi → Jawi is an inherently **ambiguous** mapping (the same Latin spelling can be pepet vs
taling `e`, medial `a` is written only ~72% of the time and is lexically determined, and
loanwords use etymological Arabic/Sanskrit spelling). Pure deterministic rules therefore
plateau around 65%; the ≥80% target is met by combining the rules with a dictionary lookup,
which is how production converters (e.g. DBP's) work.

## Quick start

```bash
# Interactive prompt
python3 jawi.py
#   rumi> saya makan nasi
#   jawi> ساي ماکن ناسي

# Convert words / a sentence given as arguments
python3 jawi.py "Saya makan nasi, dia minum air!"
#   → ساي ماکن ناسي, دي مينوم اءير!

# Convert piped text, line by line
echo "kemerdekaan negara kita" | python3 jawi.py
#   → کمرديکاءن نݢارا کيت

# Rule-only mode (no dictionary) — useful for novel words
python3 jawi.py --rules "glombak zibrakisme"
#   → ݢلومبق زيبراکيسمي
```

No dependencies — pure Python 3, UTF-8. Run from the directory containing
`rumi-jawi-unicode.csv` (the CLI falls back to rule-only if the CSV is absent).

### CLI details

Two front-ends share the same engine:

- `jawi.py` — the original minimal CLI.
- `rumi-jawi-cli.py` — a fuller CLI (argparse help, `--file`, `--verbose` source tags, extra
  interactive commands). Recommended for trying the rules on new words:

  ```bash
  # convert words / sentences, from args, a pipe, or a file
  python3 rumi-jawi-cli.py "Dia belajar di sekolah."
  python3 rumi-jawi-cli.py --file cerita.txt

  # rule-only, for testing the rules on novel / out-of-vocabulary words
  python3 rumi-jawi-cli.py --rules mengabadikan xantina

  # tag each word with where it came from: [dict] (looked up) or [rule] (generated)
  python3 rumi-jawi-cli.py --verbose keadaan xylophone
  #   → کاداءن[dict] زيلوڤهوني[rule]
  ```

- **Default mode is hybrid**: known words are looked up in the ~48k-word dictionary; unknown
  words fall back to the rules.
- **Sentence-aware**: spaces, punctuation, and digits pass through unchanged; each Malay word
  is lowercased and converted. Full reduplication like `anak-anak` → `انق٢` is handled.
- **Interactive commands** (`rumi-jawi-cli.py`): `:rules` / `:hybrid` switch modes,
  `:verbose` toggles source tags, `:help`, `:q` to quit.
- `--rules` / `-r` forces rule-only mode; `--help` / `-h` shows usage.

## Using it as a library

```python
import translit, hybrid
from evaluate import load_rows

# pure rules
translit.convert("makan")            # -> 'ماکن'

# hybrid (dictionary + rule fallback)
convert, lut = hybrid.make_hybrid(load_rows())
convert("kita")                       # -> 'کيت'  (authoritative spelling)
hybrid.rule_convert("anak-anak")      # -> 'انق٢' (rules + reduplication)
```

## The ruleset (summary)

Applied left-to-right after digraph tokenization, with a syllable model (`V.CV` / `VC.CV`).

**Consonants**
`b`→ب `t`→ت `d`→د `r`→ر `l`→ل `n`→ن `m`→م `h`→ه `g`→ݢ `p`→ڤ `c`→چ `j`→ج
`s`→س `f`→ف `z`→ز `w`→و `y`→ي `v`→ۏ `q`→ق ;
`x` word-initial → ز (`xantina`→زنتينا), elsewhere → کس ;
digraphs `ng`→ڠ `ny`→ڽ `kh`→خ `gh`→غ `sy`→ش .
Word-final `k` → **ق** (qaf); elsewhere `k` → **ک** (keheh).

**Vowels `i` / `o` / `u`** — always written: `i`→ي, `o`/`u`→و (word-initial: `i`→اي, `o/u`→او).

**Vowel `a`**
- word-initial → ا
- hiatus (after another vowel): `a`-after-`a` → **ء**, otherwise → ا
- medial **open** syllable → ا ; medial **closed** syllable → dropped
- word-**final** `-a` → ا only if the word is **bisyllabic** (2 vowels), else dropped

**Vowel `e`** — default **dropped** (pepet); word-initial `e`→ا; word-final/hiatus `e`→ي,
except the loanword ending `-sme`/`-isme` where final `e`→**ى** (alef maqsura).
(Medial taling `e`=ي is unpredictable from Rumi — the main source of rule error.)

**Prefix / junction rules**
- `di-` + consonant → **د** (the `i` is dropped); `di-`/`ke-`/`se-` + vowel-root →
  د / ک / س + plain-alef onset (the vowel root keeps its leading ا — measured against
  the data, which never uses a hamza-alef أ here)
- `i` after `u`/`o` (e.g. suffix `-i` junction) → **ءي**
- Other prefixes (`ber/ter/per/meng/…`) fall out of the plain letter rules.

**Reduplication / compounds** — `X-X` → convert(X) + **٢** ; `X-Y` → convert(X)-convert(Y).

**Not rule-derivable (accepted losses)** — etymological Arabic/Sanskrit loan letters
(ع ص ض ط ظ ث ذ ح خ غ …), pepet-vs-taling `e`, and the ~25% lexical exceptions in medial-`a`.

See [`plan.md`](plan.md) for the full derivation and the per-experiment measurements.

## Files

| File | Purpose |
|---|---|
| `jawi.py` | Command-line interface (original, minimal) |
| `rumi-jawi-cli.py` | Command-line interface (argparse, `--file`, `--verbose` source tags) |
| `translit.py` | Pure rule engine (~65% on unseen words) |
| `hybrid.py` | Dictionary lookup + rule fallback + reduplication (98.8%) |
| `evaluate.py` | Train/test split + exact-match accuracy harness |
| `plan.md` | Full rule-derivation log (11 experiments) + final ruleset |
| `rumi-jawi-unicode.csv` | Source data (71,450 Rumi,Jawi pairs) |

## Evaluate

```bash
python3 evaluate.py translit      # prints train/test accuracy + sample failures
```
