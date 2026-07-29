# `seq2seq_cv_eval.py` — 10-Fold Cross-Validation Evaluation

## Purpose

Evaluates a trained Rumi→Jawi transliteration checkpoint by running a pseudo cross-validation over a random sample of the dataset. The script samples N pairs from `rumi-jawi-unicode.csv`, splits them into K folds with scikit-learn's `KFold`, runs greedy inference on each fold's test partition, and reports per-fold exact-match accuracy plus mean ± std. Run it after training to get a robustness estimate of the model's accuracy (how much it varies across different random subsets), rather than a single held-out number.

## Usage

```bash
python seq2seq_cv_eval.py
python seq2seq_cv_eval.py --checkpoint best_model.pt --sample 1000 --folds 10 --seed 42
```

CLI arguments (all optional, defaults shown):

- `--checkpoint` (default `best_model.pt`) — path to the trained checkpoint file. Script exits with an error message if missing.
- `--csv` (default `rumi-jawi-unicode.csv`) — the dataset, a headerless two-column CSV (`rumi,jawi`).
- `--sample` (default `1000`) — number of pairs randomly sampled from the dataset before folding. Clamped to the dataset size (`min(args.sample, len(df))`).
- `--folds` (default `10`) — number of KFold splits.
- `--seed` (default `42`) — random seed, used both for `df.sample(random_state=...)` and for `KFold(shuffle=True, random_state=...)`, so runs are reproducible.
- `--device` (default `None`) — explicit device string (e.g. `cuda`, `cpu`). If omitted, auto-selects `cuda` when available, else `cpu`.

Required files: the checkpoint (default `best_model.pt`) and the CSV dataset (default `rumi-jawi-unicode.csv`), both resolved relative to the current working directory.

## How it works

1. **Load checkpoint** — `torch.load(..., map_location=device)`. The checkpoint is expected to be a dict containing `rumi_vocab`, `jawi_vocab`, `model_state_dict`, optional `hyperparams` (with `embed_dim`, `hidden_dim`, `n_layers`, `dropout`; defaults 128 / 256 / 2 / 0.3), plus `epoch` and `val_loss` for display. An inverse Jawi vocab (`jawi_inv`, index → char) is built by reversing `jawi_vocab`.
2. **Rebuild model** — `Encoder`, `Decoder`, and `Seq2Seq` are redefined in this file (they must match the training architecture exactly) and instantiated with the checkpoint's vocab sizes and hyperparameters, then `model.load_state_dict(checkpoint['model_state_dict'])` restores the weights. The model is moved to the selected device.
3. **Load and sample data** — the CSV is read with `header=None`, columns named `rumi`/`jawi`, NaN rows dropped. `random.seed(args.seed)` is set, then `df.sample(n=..., random_state=args.seed)` draws the working sample.
4. **K-fold loop** — `KFold(n_splits=args.folds, shuffle=True, random_state=args.seed)` splits the sampled word list. For each fold only the **test indices** are used (train indices are discarded — nothing is retrained). `batch_predict` transliterates the fold's words, and accuracy is the fraction of predictions exactly equal to the reference Jawi string (`p == t`).
5. **Summary** — prints per-fold accuracies, mean, population standard deviation (`np.std`), and min/max.

### Inference / decoding

`batch_predict` (seq2seq_cv_eval.py:147) performs batched greedy decoding:

- Each Rumi word is mapped to character IDs via `rumi_vocab.get(c, rumi_vocab['<unk>'])`, sequences are padded with `pad_sequence(..., padding_value=0)`, and moved to the device.
- Under `torch.no_grad()`, the encoder produces `encoder_outputs` and `encoder_hidden`, then `Decoder.decode` (seq2seq_cv_eval.py:113) runs greedy decoding: start token `<sos>`, at each step feed the argmax prediction back as the next input, up to `max_len=50` steps, stopping early when **all** batch items emit `<eos>`.
- Predicted ID sequences are converted back to strings, truncating at the first `<eos>`; unknown IDs map to `'?'`.

## Key components

- **`Encoder`** (seq2seq_cv_eval.py:28) — character embedding (`padding_idx=0`) → dropout → bidirectional GRU (`n_layers`, dropout only if `n_layers > 1`). Returns all outputs plus the final hidden state.
- **`BahdanauAttention`** (seq2seq_cv_eval.py:47) — additive attention: `tanh(W_q(query) + W_k(encoder_outputs))` scored by a linear layer to a scalar, optional masking (`scores.masked_fill(mask == 0, -1e10)`), softmax weights, then a `bmm` weighted sum for the context vector. Note: no mask is passed during inference here.
- **`Decoder`** (seq2seq_cv_eval.py:66) — unidirectional GRU whose input is `[embedding; context]` (size `embed_dim + hidden_dim * 2`); output projected to vocab via `self.out`.
  - `_init_hidden` (seq2seq_cv_eval.py:94) converts the bidirectional encoder hidden state to the decoder's initial state by **summing** forward and backward directions per layer (`encoder_hidden[2*l] + encoder_hidden[2*l+1]`).
  - `_forward_step` (seq2seq_cv_eval.py:104) is one decoding step: embed token → attention using the top GRU layer's hidden state as query → GRU → linear projection.
  - `decode` (seq2seq_cv_eval.py:113) is the greedy inference loop described above.
- **`Seq2Seq`** (seq2seq_cv_eval.py:132) — thin wrapper chaining encoder → decoder; its `forward` (teacher forcing over `trg`) is defined but unused in this script, which only calls `model.encoder` and `model.decoder.decode` directly.
- **`batch_predict`** (seq2seq_cv_eval.py:147) — batch inference helper; parameters include `device` (default `'cpu'`) and `max_len` (default `50`).
- **`main`** (seq2seq_cv_eval.py:176) — argument parsing, checkpoint/data loading, KFold loop, and summary printing.

## Inputs and outputs

**Reads:**

- `best_model.pt` (or `--checkpoint`) — checkpoint dict with vocabs, hyperparams, and `model_state_dict`.
- `rumi-jawi-unicode.csv` (or `--csv`) — headerless `rumi,jawi` pair dataset.

**Writes:** no files. Everything goes to stdout:

- Checkpoint info line (epoch and validation loss).
- Dataset size and sampled count.
- One line per fold: `Fold  i/K: nnn/NNN correct = XX.XX%`.
- A summary block: per-fold accuracy list, mean accuracy, std deviation, and min/max.

## Notes

- **Not true cross-validation** — the model is trained once elsewhere; the "folds" here are just K different random test partitions of a fixed sample, measuring accuracy variance across subsets. There is no retraining per fold.
- **Model classes are duplicated** in this file and must match the training scripts (`seq2seq_train_full.py`, `seq2seq_train_kimi.py`) exactly; otherwise `load_state_dict` will fail or silently misbehave. If the training architecture changes, update this file too.
- **Special tokens** — `<sos>`, `<eos>`, `<unk>` are expected in the checkpoint's vocab dicts; `<pad>` is index 0 (used as `padding_idx` and `padding_value`). `eos_id` falls back to `2` if `<eos>` is missing.
- **Device handling** — auto-selects CUDA if available; `--device` overrides. The checkpoint is loaded with `map_location=device`, so CPU-only machines can load GPU-trained checkpoints.
- **Batch `<eos>` early stop quirk** — `decode` stops only when *every* sequence in the fold batch has emitted `<eos>`; per-sequence truncation happens afterwards in `batch_predict`, so this is correct but may run extra steps for long sequences in a batch.
- **Potential print crash** — line 210 formats `val_loss` with `:.4f`; if a checkpoint stores `val_loss` as a non-numeric value (or it's missing and the `'?'` default is used), the script raises a formatting error at startup.
- **Reproducibility** — a single `--seed` controls the sample selection and the fold shuffling, so repeated runs with the same seed give identical numbers.
- **Dependencies** — `torch`, `numpy`, `pandas`, `scikit-learn` (`KFold`).
