# `seq2seq_predict.py` — Rumi → Jawi Inference

Loads a trained seq2seq checkpoint and transliterates a random sample of Rumi (Malay Latin) words to Jawi (Arabic script), printing each prediction next to its ground truth and reporting overall accuracy.

## Purpose

Run this after training (e.g. with `seq2seq_train_full.py`) to quickly sanity-check a saved model on a reproducible random subset of the dataset. It is an evaluation/inspection tool, not a training script: nothing is updated or saved, and results go only to the console.

## Usage

```bash
python seq2seq_predict.py
python seq2seq_predict.py --checkpoint best_model.pt --sample 100
```

All arguments are optional:

| Flag | Default | Description |
|---|---|---|
| `--checkpoint` | `best_model.pt` | Path to model checkpoint (`.pt`) |
| `--csv` | `rumi-jawi-unicode.csv` | Path to the Rumi/Jawi CSV dataset |
| `--sample` | `100` | Number of random words to sample |
| `--seed` | `42` | Random seed for sampling |
| `--batch-size` | `64` | Inference batch size |
| `--device` | auto | `cpu` or `cuda`; auto-detected if not set |

Required files:

- A checkpoint containing `rumi_vocab`, `jawi_vocab`, `model_state_dict`, and optionally `hyperparams` / `epoch` / `val_loss`.
- The CSV dataset (no header; two columns: `rumi`, `jawi`).

If either file is missing, the script prints an error and exits.

## How it works

1. **Parse args, pick device** — uses `cuda` if available unless `--device` overrides it.
2. **Load checkpoint** — `torch.load(..., map_location=device)`; extracts `rumi_vocab`, `jawi_vocab`, builds the inverse mapping `jawi_inv` (id → character), and reads `hyperparams` (`embed_dim=128`, `hidden_dim=256`, `n_layers=2`, `dropout=0.3` defaults if absent).
3. **Rebuild the model** — instantiates `Encoder`, `Decoder`, and `Seq2Seq` with the checkpoint hyperparameters and loads `model_state_dict`. The architecture classes are duplicated in this file and must match the training script.
4. **Load and sample data** — reads the CSV with `pandas` (headerless, columns `rumi`/`jawi`, `dropna()`), seeds both `random` and `pandas.sample` with `--seed`, and takes `min(--sample, len(df))` rows.
5. **Batch inference** — for each `--batch-size` chunk of Rumi words, `batch_predict`:
   - Maps each character to its id via `rumi_vocab` (unknown chars → `<unk>`).
   - Pads the batch into a tensor (`padding_value=0`) and moves it to the device.
   - Under `torch.no_grad()`, runs the encoder once, then `Decoder.decode`, which performs **greedy decoding**: start from `<sos>`, take `argmax` each step, stop when every sequence in the batch emits `<eos>` or after `max_len=50` steps.
   - Strips each prediction at the first `<eos>` and joins character ids back into a Jawi string via `jawi_inv`.
6. **Score and print** — exact-string-match accuracy (`prediction == truth`) is computed; every word is printed with a `✓`/`✗` mark, then a summary line like `Accuracy: 87/100 = 87.0%`.

## Key components

- `Encoder(vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3)` — embedding (padding idx 0) → bidirectional GRU. Returns `(outputs, hidden)`; `outputs` has `2 * hidden_dim` features per timestep.
- `BahdanauAttention(hidden_dim)` — additive attention over encoder outputs: `W_q(query) + W_k(encoder_outputs)` → `tanh` → `v` → softmax, optionally masked; returns the context vector and weights.
- `Decoder(...)` — unidirectional GRU taking `[embedding ; context]` as input and producing vocab logits. Notable methods:
  - `_init_hidden` — initializes the decoder hidden state by summing the forward and backward final hidden states of the bidirectional encoder per layer.
  - `_forward_step` — one decoding step: embed token, attend using the top hidden layer as query, concatenate, GRU step, project to vocab.
  - `decode(encoder_outputs, encoder_hidden, jawi_vocab, max_len=50)` — greedy autoregressive decoding for a whole batch; stops early when all sequences reach `<eos>`.
- `Seq2Seq(encoder, decoder)` — thin wrapper; its teacher-forcing `forward` is only used in training, not here.
- `batch_predict(model, words, rumi_vocab, jawi_vocab, jawi_inv, device, max_len)` — the inference entry point described above; switches the model to `eval()` mode.
- `main()` — argument parsing and the load → sample → predict → report orchestration.

## Inputs and outputs

- **Reads:** the checkpoint file (`--checkpoint`, default `best_model.pt`) and the dataset CSV (`--csv`, default `rumi-jawi-unicode.csv`).
- **Writes:** no files. Everything goes to stdout: model config, best-epoch/val-loss info, dataset size, sampled count, one `✓/✗` line per word (`✓ 'makan' → 'مأکن' (true: 'ماکن')`), and a final accuracy summary.

## Notes

- The model classes (`Encoder`, `BahdanauAttention`, `Decoder`, `Seq2Seq`) are **redefined here, not imported** — they must stay in sync with the architecture used by the training script that produced the checkpoint. Mismatched hyperparameters will fail at `load_state_dict`; luckily they are read from the checkpoint's `hyperparams` dict.
- The checkpoint is expected to store vocabularies as plain `dict`s (`char → id`), with special tokens `<sos>`, `<eos>`, `<unk>`, and `<pad>` (id 0 for padding).
- Decoding is **greedy** (argmax); there is no beam search. `max_len` is hardcoded to 50.
- Accuracy is strict **exact string match** on the whole Jawi word — a single character off counts as wrong.
- Evaluation happens on the full dataset (not a held-out split), so the accuracy number includes training data and is optimistic.
- Sampling is reproducible for a given `--seed`, but only if the CSV content/order is unchanged.
- Device defaults to CUDA when available; `--device cpu` forces CPU.
- The batch-level `<eos>` stop condition stops when **all** sequences in a batch have produced `<eos>`; finished sequences simply have their trailing tokens cut off at the first `<eos>` during string conversion.
- Related scripts: this consumes checkpoints produced by `seq2seq_train_full.py` / `seq2seq_train_kimi.py`; for harvesting wrong predictions into `mistakes.csv`, see `seq2seq_find_mistakes.py`.
