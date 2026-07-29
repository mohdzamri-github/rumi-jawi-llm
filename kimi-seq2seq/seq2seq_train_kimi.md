# `seq2seq_train_kimi.py` — Rumi → Jawi Seq2Seq Trainer

Trains a character-level GRU encoder–decoder with Bahdanau attention to
transliterate Malay words from Rumi (Latin) script to Jawi (Arabic) script.
It is a self-contained, single-file training script intended for quick
experiments: by default it runs a tiny **smoke test** on CPU; with `--full`
it trains on the whole dataset with a larger model (GPU if available).

Unlike `seq2seq_train_full.py`, this script **does not save a checkpoint**
(the `torch.save` call is commented out) — it trains, plots the loss curve,
and prints inference results in one run.

## Usage

```bash
# Smoke test (default): 100-sample subset, tiny model, 10 epochs, CPU
python seq2seq_train_kimi.py

# Full training: entire dataset, 128/256-dim 2-layer model, 30 epochs, CUDA if available
python seq2seq_train_kimi.py --full
```

CLI arguments (argparse, parsed in `__main__`):

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--full` | `store_true` | off | Run full training instead of the smoke test (`main(smoke_test=not args.full)`) |

Required files (read from the current working directory):

- `./rumi-jawi-unicode.csv` — the parallel corpus (no header; two columns read as `rumi`, `jawi`).

Dependencies: `torch`, `pandas`, `numpy`, `matplotlib`, `scikit-learn`
(`train_test_split`). Note `numpy` and `sys` are imported but unused.

### Config presets (`get_config`)

| Key | Smoke test | Full |
|---|---|---|
| `sample_n` | 100 | `None` (full dataset) |
| `test_size` | 0.1 | 0.1 |
| `embed_dim` | 16 | 128 |
| `hidden_dim` | 32 | 256 |
| `n_layers` | 1 | 2 |
| `dropout` | 0.0 | 0.3 |
| `lr` | 0.001 | 0.001 |
| `epochs` | 10 | 30 |
| `batch_size` | 32 | 128 |
| `device` | `cpu` | `cuda` if available else `cpu` |
| `plot` / `verbose` | True | True |

## How it works

1. **Data loading** — `pd.read_csv('./rumi-jawi-unicode.csv', header=None,
   names=['rumi', 'jawi'])`, rows with NaN dropped. In smoke-test mode,
   `df.sample(n=100, random_state=42)` takes a reproducible subset. Prints a
   data overview (pair counts, min/max string lengths) when `verbose`.
2. **Vocabulary building** — character-level. All unique characters of each
   side are collected from the (possibly sampled) dataframe, sorted, and
   indexed starting at 4 after the shared special-token dict
   `{'<pad>': 0, '<sos>': 1, '<eos>': 2, '<unk>': 3}`. Inverse maps
   (`rumi_inv`, `jawi_inv`) are built for decoding.
3. **Split & loaders** — `train_test_split(df, test_size, random_state=42)`.
   `RumiJawiDataset` maps each word to a list of character indices; the Jawi
   side is wrapped with `<sos>` … `<eos>`. `collate_fn` zero-pads (`<pad>` = 0)
   both sides per batch with `nn.utils.rnn.pad_sequence`.
4. **Model** — `Seq2Seq(Encoder, Decoder)`:
   - `Encoder`: embedding → **bidirectional** GRU. Returns all outputs
     (batch, src_len, 2·hidden) and the final hidden states.
   - `Decoder._init_hidden` merges the bidirectional final hidden states by
     **summing** forward and backward per layer, producing the unidirectional
     decoder's initial hidden state.
   - Each decoder step (`_forward_step`): embed previous token, compute
     Bahdanau attention context over encoder outputs using the decoder's top
     hidden layer as query, concatenate `[embedding, context]` into the GRU,
     project to vocabulary logits.
   - Training forward (`Decoder.forward`) uses full **teacher forcing**: it
     iterates over `trg[:, 0 : T-1]` and predicts positions `1..T-1`.
5. **Training loop** — per epoch: `train_epoch` (Adam, CrossEntropyLoss with
   `ignore_index=<pad>`, loss on `outputs` vs `jawi[:, 1:]`, gradient clipping
   at `max_norm=1`) then `evaluate` on the held-out test loader under
   `torch.no_grad()`. Prints `Train`/`Val` loss per epoch. Tracks `best_val`
   but the checkpoint save is commented out, so nothing is persisted.
6. **Plot** — if `cfg['plot']`, train/val loss curves are saved to
   `./rumi_jawi_training.png` (matplotlib, 150 dpi).
7. **Inference / evaluation** — greedy decoding only (no beam search):
   `batch_rumi_to_jawi` runs the whole test set's Rumi words through the
   encoder in one padded batch and calls `Decoder.decode`, which feeds each
   step's `argmax` token back as the next input, stopping early when *all*
   sequences in the batch emit `<eos>` (max length 50). Predictions are
   truncated at `<eos>` and compared string-for-string with the gold Jawi to
   compute whole-word accuracy. Finally it transliterates a hardcoded list of
   10 custom words (`abadi`, `adil`, `air`, …, `sayang`).

## Key components

- **`get_config(smoke_test=True)`** — returns the hyperparameter dict for the
  two modes (table above).
- **`Encoder(vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3)`** —
  embedding (padding_idx 0) + bidirectional GRU. Dropout inside the GRU only
  applies when `n_layers > 1`.
- **`BahdanauAttention(hidden_dim)`** — additive attention: `v · tanh(W_q·query
  + W_k·keys)`, optional padding mask (note: the mask parameter is never
  passed by the decoder, so attention is computed over padding too), softmax
  over source positions, weighted sum via `bmm`.
- **`Decoder(...)`** — embedding + attention + unidirectional GRU (input size
  `embed_dim + 2·hidden_dim`) + output linear.
  - `forward(trg, encoder_outputs, encoder_hidden)` — teacher-forced training pass.
  - `_init_hidden(encoder_hidden)` — sum-merge of bi-GRU hidden states.
  - `_forward_step(input_token, hidden, encoder_outputs)` — one greedy step.
  - `decode(encoder_outputs, encoder_hidden, jawi_vocab, max_len=50)` —
    batched greedy decoding from `<sos>` until all-`<eos>` or `max_len`.
- **`Seq2Seq`** — thin wrapper: `forward(src, trg)` → encoder → decoder.
- **`RumiJawiDataset` / `collate_fn`** — index mapping + `<sos>`/`<eos>`
  wrapping; per-batch zero padding.
- **`train_epoch` / `evaluate`** — standard supervised loops; loss averages
  over batches (mean of batch means, not token-weighted).
- **`rumi_to_jawi(...)`** — single-word inference helper. **Broken/unused**:
  it references `jawi_vocab` without taking it as a parameter (only `jawi_inv`
  is passed), so calling it raises `NameError`; `main` never calls it.
- **`batch_rumi_to_jawi(...)`** — the inference path actually used; pads a
  list of words and decodes them in one batch.

## Inputs and outputs

Reads:

- `./rumi-jawi-unicode.csv` — two-column CSV (no header): Rumi word, Jawi word.

Writes:

- `./rumi_jawi_training.png` — train/val loss curve (when `plot` is True, which
  it always is in both presets).
- **No model checkpoint** — `torch.save(model.state_dict(), 'best_model.pt')`
  is present but commented out; the `best_model.pt` in the directory comes
  from another script (e.g. `seq2seq_train_full.py`).

Console output: data overview and vocab sizes; train/test split counts and
parameter count; per-epoch losses; per-word test results with ✓/✗ marks and
final whole-word accuracy; transliterations of 10 hardcoded custom words.

## Notes

- **Device handling**: smoke test is pinned to CPU; full mode auto-selects
  CUDA via `torch.cuda.is_available()`.
- **Special tokens** are `<pad>=0, <sos>=1, <eos>=2, <unk>=3` for both
  vocabularies. `<unk>` is only exercised during inference on custom words
  containing characters unseen in the (sampled) training data — in smoke-test
  mode with only 100 sampled pairs this happens often, so custom-word output
  there is mostly meaningless.
- **Decoding is greedy** (`argmax`); there is no beam search. Early stop is
  batch-wide: decoding continues until *every* sequence has produced `<eos>`.
- **Vocabularies are rebuilt from the sampled subset** in smoke-test mode, so
  they differ from a full-data run — checkpoints between modes would not be
  compatible even if saving were enabled.
- `rumi_inv` is built but never used.
- `Decoder.decode` takes the whole `jawi_vocab` dict only to look up
  `<sos>`/`<eos>` ids.
- Loss averaging is per-batch mean, so batches of different sizes weight
  tokens slightly unevenly — fine for a quick experiment script.
- The script is deterministic-ish (fixed `random_state=42` for sampling and
  splitting) but does not set a torch seed, so model initialisation and
  shuffling vary between runs.
