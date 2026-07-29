# Rumi → Jawi Transliteration (Seq2Seq)

A character-level sequence-to-sequence model that transliterates Malay words
written in Rumi (Latin script) into Jawi (Arabic script), implemented in PyTorch.

**Model architecture** (identical in every script):

- **Encoder**: embedding + 2-layer bidirectional GRU
- **Attention**: Bahdanau (additive) attention over encoder outputs
- **Decoder**: 2-layer GRU; its initial hidden state is the sum of the
  encoder's forward and backward final states; greedy decoding up to 50 chars
- **Vocabulary**: character-level, with special tokens `<pad>` (0), `<sos>` (1),
  `<eos>` (2), `<unk>` (3)
- **Default hyperparameters**: embed 128, hidden 256, 2 layers, dropout 0.3,
  Adam lr 0.001, batch 128, grad clip 1.0

## Files

| File | Role |
|---|---|
| `clean-ZWNJ.py` | One-off data cleaner |
| `seq2seq_train_kimi.py` | Training script with a fast smoke-test mode |
| `seq2seq_train_full.py` | Full training script (Colab-oriented), saves `best_model.pt` |
| `seq2seq_predict.py` | Evaluate a checkpoint on a random sample of the dataset |
| `seq2seq_cli.py` | Interactive / batch transliteration CLI |
| `seq2seq_cv_eval.py` | K-fold cross-validation evaluation |
| `seq2seq_find_mistakes.py` | Export all wrong predictions on the full dataset |

Data and artifacts:

- `rumi-jawi-unicode.csv` — main dataset, two columns, **no header**: `rumi,jawi`
- `rumi-jawi-clean.csv` — output of the cleaner
- `best_model.pt` — trained checkpoint (weights + vocabs + hyperparams)
- `rumi_jawi_training.png` / `training_curve.png` — loss curves
- `mistakes.csv` — output of the mistake finder
- `learn_gru.ipynb` — original notebook experiment
- `seq2seq_*.md` — per-script notes

---

## File details

### `clean-ZWNJ.py`

Removes invisible Unicode joiner characters — ZWNJ (U+200C) and ZWJ (U+200D) —
from every cell of `rumi-jawi-unicode.csv` and writes the result to
`rumi-jawi-clean.csv`. Handles the Excel BOM (`utf-8-sig`) and prints how many
characters were stripped. Has **no CLI arguments**; the input/output filenames
are hard-coded at the top of the file. Run it once before training if your CSV
came from Excel.

### `seq2seq_train_kimi.py`

Training script with two modes, selected by CLI flag:

- **Smoke test** (default): 100-row sample, tiny model (embed 16, hidden 32,
  1 layer, no dropout), CPU, 10 epochs — verifies the whole pipeline in seconds.
- **Full** (`--full`): entire dataset, full-size model (embed 128, hidden 256,
  2 layers, dropout 0.3), up to 30 epochs, GPU if available.

Prints data overview, per-epoch train/val loss, test-set predictions with
accuracy, and transliterations of 10 custom words. Saves the loss curve to
`rumi_jawi_training.png`. **Note:** it tracks the best validation loss but does
not save a checkpoint (the `torch.save` line is commented out) — use
`seq2seq_train_full.py` to produce `best_model.pt`.

### `seq2seq_train_full.py`

The "real" training script, written for Google Colab (mounts Google Drive and
saves to `/content/drive/MyDrive/rumi-jawi-model/`; set `USE_DRIVE = False` at
the top to save locally instead — outside Colab it falls back to the current
directory automatically).

Features: 90/10 train/test split, early stopping (patience 5), gradient
clipping, saves `best_model.pt` whenever validation loss improves (checkpoint
includes both vocabularies and hyperparameters, so all inference scripts can
rebuild the model from this file alone), saves `training_curve.png`, then
reports test-set accuracy and sample transliterations. **No CLI arguments** —
all settings are constants in the CONFIGURATION block at the top of the file.

### `seq2seq_predict.py`

Loads `best_model.pt` and evaluates it two ways:

- default: samples N random pairs from the dataset (default 100, seed 42)
- `--word w1 w2 ...`: predicts your own Rumi words instead, looking up ground
  truth in the CSV where the word exists (words not in the dataset are shown
  without a ✓/✗ mark and excluded from the accuracy)

Prints each prediction with a ✓/✗ against ground truth and reports overall
accuracy. A quick sanity check of a trained checkpoint.

### `seq2seq_cli.py`

End-user transliteration tool. Loads `best_model.pt` and converts your own
Rumi words to Jawi in three modes:

- `--word` — one or more words given on the command line
- `--file` — a text file with one word per line (batched with `--batch-size`)
- `--interactive` — REPL: type a word, get Jawi; `quit` or Ctrl+C to exit

With `--csv <dataset.csv>` it also looks up each input word in the dataset and
marks the prediction ✓/✗ against the ground truth.

### `seq2seq_cv_eval.py`

Loads a checkpoint and evaluates it with K-fold cross-validation (default
10 folds) over a random sample of the dataset (default 1000 pairs, seed 42).
Prints per-fold exact-match accuracy plus mean ± std and min/max. Note: this
evaluates one fixed checkpoint on fold subsets — it does not retrain per fold.

### `seq2seq_find_mistakes.py`

Runs the checkpoint over the **entire** dataset, prints total/correct/accuracy,
shows the first 20 errors, and writes every wrong prediction to `mistakes.csv`
with columns `rumi,predicted,true`. Useful for error analysis and building a
correction list.

---

## User manual

### 1. Setup

Requires Python 3 with:

```bash
pip install torch pandas numpy matplotlib scikit-learn
```

All scripts run on CPU; training and batch inference automatically use CUDA if
available (override with `--device cpu|cuda` where supported).

### 2. Prepare the data

Expected format: a CSV with **no header**, two columns per row —
`rumi_word,jawi_word`. If the file came from Excel and may contain invisible
joiner characters, clean it first:

```bash
python clean-ZWNJ.py
# reads rumi-jawi-unicode.csv → writes rumi-jawi-clean.csv
```

(Then point the training scripts at the cleaned file, or rename it back to
`rumi-jawi-unicode.csv`, which is the default path everywhere.)

### 3. Train

Quick pipeline check (seconds, CPU, 100 samples):

```bash
python seq2seq_train_kimi.py            # smoke test
python seq2seq_train_kimi.py --full     # full data, no checkpoint saved
```

Produce a usable checkpoint (`best_model.pt`):

```bash
python seq2seq_train_full.py
```

Edit the constants at the top of `seq2seq_train_full.py` to change epochs,
batch size, learning rate, early-stopping patience, or the Drive save path.

### 4. Evaluate the checkpoint

```bash
# Random 100-word sample, per-word ✓/✗ and accuracy
python seq2seq_predict.py --checkpoint best_model.pt --sample 100 --seed 42

# Specific words from the command line (ground truth looked up in the CSV)
python seq2seq_predict.py --word keras cinta makan

# 10-fold CV on 1000 sampled pairs: per-fold accuracy, mean ± std
python seq2seq_cv_eval.py --checkpoint best_model.pt --sample 1000 --folds 10

# Full-dataset error analysis → mistakes.csv
python seq2seq_find_mistakes.py --checkpoint best_model.pt --output mistakes.csv
```

### 5. Transliterate your own words

```bash
# Single word
python seq2seq_cli.py --word cinta

# Several words
python seq2seq_cli.py --word cinta makan rumah

# From a file (one Rumi word per line)
python seq2seq_cli.py --file words.txt

# Interactive prompt
python seq2seq_cli.py --interactive

# Compare against ground truth where the word exists in the dataset
python seq2seq_cli.py --word cinta --csv rumi-jawi-unicode.csv
```

Common options: `--checkpoint PATH` (default `best_model.pt`),
`--device cpu|cuda` (auto-detected by default), `--batch-size N` for file mode.

### Typical workflow

```
clean-ZWNJ.py  (once, if needed)
      ↓
seq2seq_train_full.py          → best_model.pt
      ↓
seq2seq_predict.py             quick accuracy check
seq2seq_cv_eval.py             robustness estimate
seq2seq_find_mistakes.py       → mistakes.csv (error analysis)
      ↓
seq2seq_cli.py                 day-to-day transliteration
```

### Troubleshooting

- **`Checkpoint not found: best_model.pt`** — train first with
  `seq2seq_train_full.py`, or pass `--checkpoint` with the right path.
- **Predictions look random** — you may be loading a checkpoint trained by the
  smoke-test config; `seq2seq_train_kimi.py` does not save checkpoints, so this
  usually means `best_model.pt` is stale or missing. Retrain with
  `seq2seq_train_full.py`.
- **Odd/missing Jawi characters in output** — the model can only emit
  characters seen in training; unseen input characters map to `<unk>`. Clean
  ZWNJ/ZWJ from the data (see step 2) and check terminal UTF-8 support.
