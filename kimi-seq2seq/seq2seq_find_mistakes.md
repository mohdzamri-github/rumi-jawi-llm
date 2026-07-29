# `seq2seq_find_mistakes.py` — Explanation

## 1. Purpose

This script is a **whole-dataset error analysis tool** for the trained Rumi→Jawi
transliteration model. It loads a trained checkpoint (`best_model.pt`), runs greedy
inference over **every pair** in the dataset CSV, compares each prediction to the
ground-truth Jawi string, and saves all mismatches to a CSV file (`mistakes.csv`).

You would run it **after training** to:

- measure exact-match word accuracy on the full dataset,
- inspect what the model gets wrong (a sample of mistakes is printed),
- produce `mistakes.csv` for downstream analysis or targeted re-training.

There is no training in this script — the model is only used in `eval()` mode.

## 2. Usage

```bash
# All defaults (equivalent to the second line):
python seq2seq_find_mistakes.py
python seq2seq_find_mistakes.py --checkpoint best_model.pt --csv rumi-jawi-unicode.csv --output mistakes.csv
```

### CLI arguments

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `--checkpoint` | str | `best_model.pt` | Path to the trained model checkpoint (`.pt` file). |
| `--csv` | str | `rumi-jawi-unicode.csv` | Dataset CSV: headerless, two columns `rumi,jawi`. |
| `--output` | str | `mistakes.csv` | Where to write the mistakes CSV. |
| `--batch-size` | int | `256` | Number of words encoded/decoded per batch. |
| `--device` | str | `None` (auto) | Force `cuda`/`cpu`; auto-selects CUDA if available. |

### Required files

- A checkpoint produced by the training script (`best_model.pt`) containing
  `model_state_dict`, `rumi_vocab`, `jawi_vocab`, and optionally `hyperparams`,
  `epoch`, `val_loss`.
- The dataset CSV (`rumi-jawi-unicode.csv`), no header, columns: Rumi word, Jawi word.

## 3. How It Works

### Checkpoint load and model rebuild

1. `torch.load(args.checkpoint, map_location=device)` loads the checkpoint.
2. Vocabularies are pulled from the checkpoint (`rumi_vocab`, `jawi_vocab`);
   `jawi_inv` is the inverted Jawi vocab (id → char).
3. Hyperparameters come from `checkpoint['hyperparams']`, falling back to
   `embed_dim=128, hidden_dim=256, n_layers=2, dropout=0.3`.
4. `Encoder` + `Decoder` are reconstructed with vocab sizes from the checkpoint
   vocabularies, wrapped in `Seq2Seq`, and `load_state_dict` restores weights.
5. The script prints the epoch and validation loss stored in the checkpoint
   (note: this print assumes `val_loss` is a float — it formats it with `:.4f`).

### Dataset load

- `pd.read_csv(args.csv, header=None, names=['rumi','jawi']).dropna()` — headerless
  two-column CSV; rows with missing values are dropped.
- The full dataset is evaluated (no train/val split — this is inference over everything).

### Inference loop

Words are processed in batches of `--batch-size`:

```
for i in range(0, len(words), args.batch_size):
    preds = batch_predict(model, batch, rumi_vocab, jawi_vocab, jawi_inv, device=device)
```

Inside `batch_predict` (greedy decoding, no teacher forcing):

1. Each Rumi word is mapped char-by-char to ids via `rumi_vocab` (unknown chars → `<unk>`).
2. Sequences are zero-padded (`pad_sequence`, `padding_value=0`) into a batch tensor.
3. The encoder runs once per batch: `encoder_outputs, encoder_hidden = model.encoder(src)`.
4. `Decoder.decode` generates tokens autoregressively up to `max_len=50`:
   - starts from `<sos>` for every sequence,
   - takes `argmax` of the output logits each step (greedy — no beam search),
   - stops early when **all** sequences in the batch have emitted `<eos>`.
5. Each prediction id sequence is converted back to a Jawi string, truncating at
   the first `<eos>` (ids not in `jawi_inv` become `'?'`).

### Mistake collection and reporting

- Predictions are compared to ground truth with exact string equality
  (`pred != true`). There is no normalisation — any character difference counts.
- Console output: total / correct / mistakes counts, accuracy %, error rate %,
  and the first up to 20 mistakes in the form
  `'rumi' → predicted: '...' | true: '...'`.
- If there are any mistakes, they are written to `--output` as a CSV with columns
  `rumi,predicted,true` (with header). If accuracy is 100%, no file is written.

## 4. Key Components

### `Encoder(vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3)`

- Embedding (`padding_idx=0`) → dropout → **bidirectional** GRU (`batch_first=True`).
- Returns `outputs` (all timesteps, `hidden_dim*2` features) and the stacked
  `hidden` state (`2*n_layers` layers because of bidirectionality).

### `BahdanauAttention(hidden_dim)`

- Additive attention: `score = v · tanh(W_q·query + W_k·keys)`.
- `W_q` maps the decoder top-layer hidden state (`hidden_dim`) and `W_k` maps the
  encoder outputs (`hidden_dim*2`, since the encoder is bidirectional).
- Supports a padding `mask` (scores set to `-1e10`), though the inference path
  here calls it without a mask.
- Returns the context vector (weighted sum of encoder outputs) and the weights.

### `Decoder(vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3)`

- Embedding → per-step: attention over encoder outputs using the top hidden layer
  as query → GRU whose input is `[embedded ; context]` (`embed_dim + hidden_dim*2`)
  → linear projection to vocab logits.
- `_init_hidden` collapses the bidirectional encoder hidden state into the
  decoder's initial state by **summing the forward and backward states** per layer.
- `forward` (teacher-forced, used in training) exists but is unused here.
- `decode` is the inference path: greedy loop over `_forward_step` with `<sos>`
  start, early stop on all-`<eos>`, `max_len=50`.

### `Seq2Seq(encoder, decoder)`

- Thin wrapper; `forward(src, trg)` runs encoder then teacher-forced decoder.
  In this script only `.encoder` and `.decoder.decode` are used.

### `batch_predict(model, words, rumi_vocab, jawi_vocab, jawi_inv, device='cpu', max_len=50)`

- End-to-end helper: string batch → id tensor → encode → greedy decode →
  list of predicted Jawi strings. Runs under `torch.no_grad()` with `model.eval()`.

### `main()`

- Parses args, picks device, loads checkpoint + dataset, batches through
  `batch_predict`, computes exact-match accuracy, prints samples, writes the
  mistakes CSV.

## 5. Inputs and Outputs

### Reads

- `--checkpoint` (default `best_model.pt`): `torch.load` — must contain
  `model_state_dict`, `rumi_vocab`, `jawi_vocab`; optional `hyperparams`, `epoch`,
  `val_loss`.
- `--csv` (default `rumi-jawi-unicode.csv`): headerless `rumi,jawi` pairs.

### Writes

- `--output` (default `mistakes.csv`): one row per wrong prediction, columns
  `rumi,predicted,true`. **Not written** if there are zero mistakes.

### Console

- Checkpoint/model load confirmation (epoch, val loss).
- Dataset size, inference batch size.
- Results block: totals, accuracy, error rate.
- Up to 20 sample mistakes.
- Save confirmation (or "perfect accuracy" message).
- No checkpoints or models are saved — inference only.

## 6. Notes

- **Architecture must match the trainer.** The model classes are re-defined inline
  and must structurally match whatever script saved `best_model.pt` (e.g.
  `seq2seq_train_kimi.py` / `seq2seq_train_full.py`). Hyperparameters come from the
  checkpoint's `hyperparams` dict, but the architecture code itself (bidirectional
  encoder, hidden-sum init, etc.) is hardcoded here.
- **Special tokens:** `<sos>`, `<eos>`, `<unk>` are required to exist in the
  checkpoint vocabularies; `0` is the padding index. `<eos>` falls back to id `2`
  if missing, and unmapped prediction ids render as `'?'`.
- **Greedy decoding only** — no beam search; predictions are per-step argmax.
- **Evaluation is on the full dataset, including any data the model trained on**
  (no split is applied), so the reported accuracy is *not* a held-out metric —
  use `seq2seq_cv_eval.py` for cross-validated evaluation.
- **No normalisation** before comparison: exact string match means Unicode
  variants or extra whitespace count as mistakes.
- **Device:** CUDA if available unless `--device` overrides; the checkpoint is
  loaded with `map_location=device`, so a GPU-trained model runs fine on CPU.
- **Early-stop quirk:** the batch decode loop stops when *all* sequences have
  emitted `<eos>`; sequences that finished earlier keep being fed their last
  predicted token, but the post-processing truncates at each sequence's first
  `<eos>`, so results are unaffected.
- **Dropout at inference is harmless** because `model.eval()` is set in
  `batch_predict`.
- **Missing checkpoint** just prints an error and returns (exit code 0).
- `max_len=50` caps generated sequences at 50 characters.
