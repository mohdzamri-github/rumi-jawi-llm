# `seq2seq_cli.py` — Rumi → Jawi CLI Prediction Tool

## 1. Purpose

A command-line inference tool for the Rumi→Jawi transliteration model. It loads a trained
checkpoint (`best_model.pt` by default) and transliterates Malay words written in Latin
script (Rumi) into Arabic script (Jawi). Run it after training is complete, whenever you
want ad-hoc predictions — single words, a list of words, a file of words, or an
interactive REPL. It can also compare predictions against ground truth when given the
training CSV.

It does **not** train anything; there is no training loop here.

## 2. Usage

```bash
python seq2seq_cli.py --word "cinta"
python seq2seq_cli.py --word "cinta" "makan" "rumah"
python seq2seq_cli.py --file words.txt
python seq2seq_cli.py --interactive
python seq2seq_cli.py --word "cinta" --csv rumi-jawi-unicode.csv
```

Exactly one input mode must be given (`--word`, `--file`, or `--interactive`). If none
is provided, the script prints the help text and exits with code 1. If several are
provided, the effective priority is `--interactive` > `--file` > `--word`
(the branches are `if/elif`).

| Flag | Default | Meaning |
|---|---|---|
| `--checkpoint` | `best_model.pt` | Path to the model checkpoint. Script exits if missing. |
| `--word WORD [WORD ...]` | — | One or more Rumi words to transliterate (`nargs='+'`). |
| `--file` | — | UTF-8 text file, one Rumi word per line (blank lines skipped). |
| `--interactive` | off | Interactive prompt; type a word per line. `quit`/`exit`/`q`, EOF, or Ctrl+C exits. |
| `--csv` | `None` | Optional dataset CSV used only to show ground-truth Jawi next to predictions. |
| `--device` | auto | `cpu` or `cuda`; auto-detects CUDA if unset. |
| `--batch-size` | `64` | Batch size used when chunking `--word`/`--file` input lists. |

**Required files:** the checkpoint (must contain `rumi_vocab`, `jawi_vocab`,
`model_state_dict`, and optionally `hyperparams`). The CSV is optional.

## 3. How It Works

1. **Parse args, pick device** — `main()` builds the argparse parser, then resolves the
   device: explicit `--device`, else `cuda` if `torch.cuda.is_available()`, else `cpu`
   (`seq2seq_cli.py:236`).
2. **Load model** — `load_model()` loads the checkpoint with
   `torch.load(..., map_location=device)`, pulls out the two vocabularies, builds the
   inverse Jawi vocab (`jawi_inv = {id: char}`), reads `hyperparams` (falling back to
   `embed_dim=128, hidden_dim=256, n_layers=2, dropout=0.3`), constructs
   `Encoder`/`Decoder`/`Seq2Seq`, moves it to the device, and loads
   `model_state_dict` (`seq2seq_cli.py:180-202`).
3. **Print model info** — reports checkpoint path, best epoch, validation loss, and
   device.
4. **Optional ground truth** — if `--csv` is given and the file exists, it is read with
   pandas as a header-less two-column CSV (`rumi`, `jawi`) and turned into a lookup dict
   (`seq2seq_cli.py:248-252`).
5. **Inference** — the three input modes all funnel into `batch_predict()`:
   - Characters of each Rumi word are mapped to IDs via `rumi_vocab` (unknown characters
     become `<unk>`), then padded to a batch tensor with `padding_value=0`
     (`seq2seq_cli.py:153-157`).
   - Under `torch.no_grad()`, the batch runs through `model.encoder`, then
     `model.decoder.decode(...)`.
   - **Decoding is greedy**: at each step the decoder takes `argmax` over the output
     logits, feeds that token back in, and stops when every sequence in the batch emits
     `<eos>` or after `max_len=50` steps (`seq2seq_cli.py:114-130`). There is no beam
     search.
   - Token IDs are converted back to characters with `jawi_inv`, truncating at the first
     `<eos>`; unknown IDs render as `?` (`seq2seq_cli.py:163-173`).
6. **Output** — each word is printed as `word -> jawi`; if ground truth is known, a
   `✓`/`✗` marker and the true Jawi are appended.

### Model architecture (redefined here to match training)

- **Encoder** (`seq2seq_cli.py:29-45`): character embedding (`padding_idx=0`) + dropout +
  **bidirectional** GRU (`batch_first=True`, dropout between layers when `n_layers > 1`).
  Returns all outputs (each hidden state is `2 * hidden_dim`) and the final hidden state.
- **BahdanauAttention** (`seq2seq_cli.py:48-64`): additive attention. Query (decoder top
  hidden) and keys (encoder outputs) are projected to `hidden_dim`, combined with
  `tanh`, scored by a linear layer to 1 dim, optionally masked (scores for masked
  positions set to `-1e10`), softmaxed, and used to weight-sum the encoder outputs into a
  context vector.
- **Decoder** (`seq2seq_cli.py:67-130`): unidirectional GRU whose input is the embedding
  concatenated with the attention context (`embed_dim + 2*hidden_dim`), plus a linear
  output layer to vocab size. `_init_hidden()` derives the initial decoder state by
  **summing** the forward and backward encoder hidden states per layer.
  `forward()` is the teacher-forced training loop (kept for state-dict compatibility),
  `decode()` is the greedy inference loop seeded with `<sos>`.
- **Seq2Seq** (`seq2seq_cli.py:133-141`): thin wrapper joining encoder and decoder.

## 4. Key Components

- `Encoder(vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3)` — bidirectional
  GRU encoder over Rumi character sequences.
- `BahdanauAttention(hidden_dim)` — additive attention producing a context vector per
  decoder step; accepts an optional padding `mask` (unused in the CLI path).
- `Decoder(vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3)` — attention
  decoder; notable methods:
  - `_init_hidden(encoder_hidden)` — collapses the bidirectional encoder state
    (shape `2*n_layers × B × H`) into the decoder's initial state by adding direction
    pairs.
  - `_forward_step(...)` — one decoding step: embed → attend → concat → GRU → logits.
  - `decode(encoder_outputs, encoder_hidden, jawi_vocab, max_len=50)` — batched greedy
    decoding starting from `<sos>`.
- `Seq2Seq(encoder, decoder)` — container whose `forward` runs the teacher-forced path.
- `batch_predict(model, words, rumi_vocab, jawi_vocab, jawi_inv, device='cpu', max_len=50)`
  — end-to-end batch transliteration: tokenize → pad → encode → greedy decode →
  detokenize. Returns a list of Jawi strings aligned with the input words; returns `[]`
  for empty input.
- `load_model(checkpoint_path, device)` — checkpoint validation, vocab extraction, model
  reconstruction from saved (or default) hyperparameters, and state-dict loading. Exits
  the process if the checkpoint file does not exist.
- `main()` — argument parsing, device selection, input-mode dispatch, and result
  printing (with optional ground-truth comparison).

## 5. Inputs and Outputs

**Reads:**

- `--checkpoint` (default `best_model.pt`) — required; a dict with keys
  `model_state_dict`, `rumi_vocab`, `jawi_vocab`, and optionally `hyperparams`, `epoch`,
  `val_loss`.
- `--file` — UTF-8 text file, one Rumi word per line.
- `--csv` (optional) — header-less two-column CSV, e.g. `rumi-jawi-unicode.csv`, used
  solely for ground-truth display.
- Interactive mode reads words from stdin.

**Writes:** nothing. The script is read-only — no files are created or modified; all
results go to stdout. (Checkpoints such as `best_model.pt` are produced by the separate
training scripts, not here.)

**Console output:** a header (`Loaded model: ...`, best epoch, val loss, device), then
one line per word, e.g. `✓ cinta -> چينتا  (true: چينتا)` when ground truth is
available, or `  cinta -> چينتا` otherwise.

## 6. Notes

- **Architecture must match training.** The model classes are redefined in this file and
  must stay in sync with the training scripts (`seq2seq_train_full.py`,
  `seq2seq_train_kimi.py`); the checkpoint only stores weights, not class definitions.
- **Checkpoint contract.** Requires `rumi_vocab` and `jawi_vocab` saved inside the
  checkpoint; there is no separate vocab file. `hyperparams` is optional — missing keys
  fall back to `embed_dim=128, hidden_dim=256, n_layers=2, dropout=0.3`.
- **Greedy decoding only.** `Decoder.decode()` takes `argmax` per step; no beam search,
  no sampling. `max_len` is fixed at 50 in both `decode()` and `batch_predict()` — not a
  CLI flag.
- **Unknown characters** map to `<unk>` on input; unknown output IDs print as `?`.
- **Special tokens:** `<sos>` and `<eos>` are looked up in `jawi_vocab`; `<pad>` is ID 0
  (used as `padding_idx` and `padding_value`). The batch decode loop exits early only
  when **all** sequences have emitted `<eos>`.
- **Device handling:** defaults to CUDA when available; `--device cpu` forces CPU. The
  checkpoint is loaded with `map_location=device`, so GPU-trained models load fine on
  CPU with `--device cpu`.
- **Batching:** in `--word`/`--file` modes words are processed in chunks of
  `--batch-size` (default 64); interactive mode always predicts one word at a time.
- **Minor quirks:** the startup line `checkpoint.get('val_loss', '?')` is formatted with
  `:.4f`, so a checkpoint missing `val_loss` would raise a `TypeError`; `import pandas`
  happens lazily inside `main()` only when `--csv` is used; `--interactive` wins over
  `--file`, which wins over `--word` if several flags are combined.
- **Dependencies:** `torch` (always), `pandas` (only with `--csv`).
