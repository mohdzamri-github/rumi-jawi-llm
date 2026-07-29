# `seq2seq_train_full.py` — Full Rumi→Jawi Seq2Seq Training Script

## Purpose

End-to-end training script for the Rumi (Malay Latin script) → Jawi (Arabic script)
character-level neural transliteration model. It loads the word-pair CSV, builds
character vocabularies, trains a bidirectional-GRU encoder / GRU decoder with
Bahdanau attention from scratch, saves the best checkpoint, plots the training
curve, and runs a final evaluation on the held-out test set.

Run this when you want to (re)train the full model — typically in **Google Colab**
(the script is written for that environment: it optionally mounts Google Drive and
saves outputs there). Other scripts in the project (`seq2seq_predict.py`,
`seq2seq_cv_eval.py`, `seq2seq_find_mistakes.py`) consume the `best_model.pt`
checkpoint this script produces.

## Usage

No CLI arguments — everything is configured via constants at the top of the file.

```bash
python seq2seq_train_full.py
```

Required input file (must exist in the current working directory):

- `rumi-jawi-unicode.csv` — word pairs, no header, two columns: `rumi,jawi`

Configuration constants (edit in place, `seq2seq_train_full.py:28-46`):

| Constant | Default | Meaning |
|---|---|---|
| `USE_DRIVE` | `True` | Mount Google Drive and save to `DRIVE_PATH` (Colab only) |
| `DRIVE_PATH` | `/content/drive/MyDrive/rumi-jawi-model` | Where outputs are saved in Colab |
| `CSV_FILE` | `rumi-jawi-unicode.csv` | Input dataset path |
| `EMBED_DIM` / `HIDDEN_DIM` / `N_LAYERS` / `DROPOUT` | 128 / 256 / 2 / 0.3 | Model hyperparameters |
| `LEARNING_RATE` / `N_EPOCHS` / `BATCH_SIZE` | 0.001 / 50 / 128 | Training hyperparameters |
| `TEST_SIZE` / `RANDOM_STATE` | 0.1 / 42 | Train/test split |
| `EARLY_STOPPING_PATIENCE` | 5 | Epochs without val-loss improvement before stopping |
| `GRAD_CLIP` | 1.0 | Gradient norm clipping |

Device is chosen automatically: CUDA if available, otherwise CPU (`seq2seq_train_full.py:46`).

## How it works

1. **Drive setup** — `setup_drive()` runs at import time. In Colab with
   `USE_DRIVE=True` it mounts `/content/drive` and returns `DRIVE_PATH` as
   `SAVE_DIR`; otherwise (or outside Colab) `SAVE_DIR` is the current directory `.`.
2. **Data loading** — `main()` reads the CSV with `pandas` (no header, columns
   renamed to `rumi`/`jawi`), drops NaN rows, and prints length statistics.
3. **Vocabulary building** — character-level vocabularies are built from the full
   dataframe. Special tokens occupy IDs 0–3:
   `<pad>=0, <sos>=1, <eos>=2, <unk>=3`; remaining characters are sorted and
   assigned IDs starting at 4. Inverse maps (`rumi_inv`, `jawi_inv`) are built too.
4. **Split & DataLoaders** — `train_test_split` (10% test, seed 42), then
   `DataLoader`s with batch size 128; the train loader shuffles, the test loader
   doesn't. `collate_fn` pads both sequences in a batch to equal length with 0.
5. **Model construction** — `Encoder` (bi-GRU) + `Decoder` (GRU + attention)
   wrapped in `Seq2Seq`, moved to `DEVICE`. Loss is `CrossEntropyLoss` with
   `ignore_index=<pad>`; optimizer is Adam.
6. **Training loop** — up to 50 epochs. Each epoch: `train_epoch()` (teacher
   forcing, loss on `jawi[:, 1:]` vs. decoder outputs, gradient clipping at 1.0,
   Adam step) then `evaluate()` on the test loader under `torch.no_grad()`.
   Per-epoch train/val loss and time are printed.
7. **Checkpointing & early stopping** — whenever val loss improves, a checkpoint
   dict (epoch, model + optimizer state, losses, **both vocabularies**, and the
   model hyperparams) is written to `SAVE_DIR/best_model.pt`. After 5 consecutive
   non-improving epochs, training stops early.
8. **Plot** — train/val loss curves are saved to `SAVE_DIR/training_curve.png`
   (and displayed via `plt.show()`).
9. **Final evaluation** — the best checkpoint is reloaded, then the entire test
   set is transliterated with `batch_rumi_to_jawi()` (greedy decoding). Up to 20
   sample predictions are printed with ✓/✗ marks, followed by exact-match test
   accuracy. Finally, 10 hardcoded custom words are transliterated as a sanity
   check.

## Key components

- **`Encoder`** — embedding (`padding_idx=0`) + dropout + bidirectional GRU
  (`batch_first=True`). Returns all hidden outputs and the final hidden state;
  output width is `2 * hidden_dim` because of bidirectionality.
- **`BahdanauAttention`** — additive attention: projects the decoder query
  (`W_q`) and encoder outputs (`W_k`), scores with `tanh` + a linear layer to a
  scalar, softmax over the source length (with optional padding mask), and
  returns the weighted-sum context plus the attention weights.
- **`Decoder`** — GRU decoder attending at every step.
  - `_init_hidden()` collapses the bidirectional encoder hidden state into the
    decoder's initial hidden state by **summing** the forward and backward
    states per layer.
  - `_forward_step()` embeds one token, computes attention against the top-layer
    hidden state, concatenates `[embedding, context]` as GRU input, and projects
    the output to vocabulary logits.
  - `forward()` runs teacher forcing over `trg` (loops `trg.shape[1] - 1` steps).
  - `decode()` does batched **greedy** inference: starts from `<sos>`, feeds each
    argmax prediction back as the next input, stops when **every** sequence in
    the batch has emitted `<eos>` or after `max_len=50` steps. No beam search.
- **`Seq2Seq`** — thin wrapper: `forward(src, trg)` → encoder → decoder.
- **`RumiJawiDataset` / `collate_fn`** — yields character-ID tensors; Jawi targets
  are wrapped in `<sos>`/`<eos>`; collate pads with 0. Note: dataset lookup uses
  direct dict indexing (`rumi_vocab[c]`), so characters outside the training
  vocab would raise `KeyError` here — only inference (`batch_rumi_to_jawi`)
  falls back to `<unk>`.
- **`train_epoch()` / `evaluate()`** — standard train/eval loops returning mean
  batch loss; loss flattens decoder outputs against `jawi[:, 1:]` (shift-right
  target).
- **`batch_rumi_to_jawi()`** — batch inference helper: encodes words, runs greedy
  `decode()`, strips everything from `<eos>` onward, and joins characters into
  Jawi strings (unknown IDs render as `?`).

## Inputs and outputs

Reads:

- `rumi-jawi-unicode.csv` (from the current working directory)

Writes (to `SAVE_DIR` — Drive path in Colab, `.` locally):

- `best_model.pt` — checkpoint with model/optimizer state, losses, vocabularies,
  and hyperparameters; overwritten each time val loss improves
- `training_curve.png` — train/val loss plot (150 dpi)

Console output: dataset stats, vocab sizes, parameter count, per-epoch losses,
early-stopping notices, sample test predictions with exact-match accuracy, and
custom-word transliterations.

## Notes

- **Colab-oriented**: the top docstring assumes Colab; with `USE_DRIVE=True`
  outside Colab the `google.colab` import fails gracefully and it falls back to
  saving in the current directory.
- **Hardcoded paths/values**: CSV filename, Drive path, the 10 custom test words,
  and all hyperparameters are constants — there is no `argparse`.
- **Vocab stored in checkpoint**: the saved vocabularies are what downstream
  scripts use to stay consistent with training; model architecture hyperparams
  are saved too, but the class definitions themselves must be re-declared (or
  imported) to load the state dict.
- **Character-level model**: vocabularies are over characters, not words; Jawi
  targets get `<sos>`/`<eos>` but Rumi sources do not.
- **Greedy-only decoding**: no beam search anywhere; batched decode stops only
  when all sequences in the batch hit `<eos>`.
- **Padding mask unused in practice**: `BahdanauAttention` supports a mask, but
  neither `Decoder.forward` nor `decode` passes one — padding positions still
  receive attention weight (mitigated somewhat by `ignore_index=<pad>` in the
  loss).
- **Bidirectional → unidirectional bridge**: encoder hidden directions are
  combined by summation in `Decoder._init_hidden`; keep this in mind if you
  change `N_LAYERS` or `HIDDEN_DIM` asymmetrically between encoder and decoder.
- **Dependencies**: `torch`, `pandas`, `numpy`, `matplotlib`, `scikit-learn`;
  `google.colab` only when `USE_DRIVE=True` inside Colab.
