"""
Find Prediction Mistakes on Full Dataset (Google Colab Version)
================================================================

Run this in Google Colab:
1. Upload `rumi-jawi-unicode.csv` to the Colab session
   (or place it in /content/drive/MyDrive/rumi-jawi-model/)
2. Make sure `best_model.pt` is in /content/drive/MyDrive/rumi-jawi-model/
   (it is saved there by seq2seq_train_full.py)
3. Run all cells / run the script
4. Results are saved to /content/drive/MyDrive/rumi-jawi-model/mistakes.csv

To skip Google Drive mounting, set `USE_DRIVE = False` below — the script
then reads/writes everything in the current directory.
"""

import os
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

# ============================================================
# CONFIGURATION
# ============================================================

USE_DRIVE = True              # Set to False to skip Google Drive mount
DRIVE_PATH = '/content/drive/MyDrive/rumi-jawi-model'

CHECKPOINT_FILE = 'best_model.pt'
CSV_FILE = 'rumi-jawi-unicode.csv'
OUTPUT_FILE = 'mistakes.csv'

BATCH_SIZE = 256
N_SHOW = 20                   # How many sample mistakes to print

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# ============================================================
# GOOGLE DRIVE SETUP (Colab)
# ============================================================

def setup_drive():
    if USE_DRIVE:
        try:
            from google.colab import drive
            drive.mount('/content/drive')
            os.makedirs(DRIVE_PATH, exist_ok=True)
            print(f"Drive mounted. Using: {DRIVE_PATH}")
            return DRIVE_PATH
        except ImportError:
            print("Not in Colab — skipping Drive mount.")
    return '.'


SAVE_DIR = setup_drive()


def resolve_path(filename):
    """Look in SAVE_DIR first, then the current directory."""
    drive_path = os.path.join(SAVE_DIR, filename)
    if os.path.exists(drive_path):
        return drive_path
    if os.path.exists(filename):
        print(f"Note: '{filename}' not found in {SAVE_DIR} — "
              f"using the copy in the current directory instead.")
        return filename
    return None


# ============================================================
# MODEL DEFINITIONS (must match training)
# ============================================================

class Encoder(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.gru = nn.GRU(
            embed_dim, hidden_dim,
            num_layers=n_layers,
            bidirectional=True,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, src):
        embedded = self.dropout(self.embedding(src))
        outputs, hidden = self.gru(embedded)
        return outputs, hidden


class BahdanauAttention(nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.W_q = nn.Linear(hidden_dim, hidden_dim)
        self.W_k = nn.Linear(hidden_dim * 2, hidden_dim)
        self.v = nn.Linear(hidden_dim, 1)

    def forward(self, query, encoder_outputs, mask=None):
        query_expanded = self.W_q(query).unsqueeze(1)
        keys = self.W_k(encoder_outputs)
        energy = torch.tanh(query_expanded + keys)
        scores = self.v(energy).squeeze(-1)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e10)
        attention_weights = F.softmax(scores, dim=1)
        context = torch.bmm(attention_weights.unsqueeze(1), encoder_outputs).squeeze(1)
        return context, attention_weights


class Decoder(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, n_layers=2, dropout=0.3):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.attention = BahdanauAttention(hidden_dim)
        self.gru = nn.GRU(
            embed_dim + hidden_dim * 2,
            hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0
        )
        self.out = nn.Linear(hidden_dim, vocab_size)
        self.dropout = nn.Dropout(dropout)

    def forward(self, trg, encoder_outputs, encoder_hidden):
        decoder_hidden = self._init_hidden(encoder_hidden)
        outputs, attentions = [], []
        for t in range(trg.shape[1] - 1):
            output, decoder_hidden, attn = self._forward_step(
                trg[:, t:t+1], decoder_hidden, encoder_outputs
            )
            outputs.append(output)
            attentions.append(attn)
        return torch.stack(outputs, dim=1), torch.stack(attentions, dim=1)

    def _init_hidden(self, encoder_hidden):
        n_layers = encoder_hidden.shape[0] // 2
        batch_size = encoder_hidden.shape[1]
        hidden_dim = encoder_hidden.shape[2]
        decoder_hidden = torch.zeros(n_layers, batch_size, hidden_dim,
                                     device=encoder_hidden.device)
        for l in range(n_layers):
            decoder_hidden[l] = encoder_hidden[2*l] + encoder_hidden[2*l + 1]
        return decoder_hidden

    def _forward_step(self, input_token, hidden, encoder_outputs):
        embedded = self.dropout(self.embedding(input_token))
        query = hidden[-1]
        context, attn_weights = self.attention(query, encoder_outputs)
        rnn_input = torch.cat([embedded, context.unsqueeze(1)], dim=-1)
        output, hidden = self.gru(rnn_input, hidden)
        prediction = self.out(output.squeeze(1))
        return prediction, hidden, attn_weights

    def decode(self, encoder_outputs, encoder_hidden, jawi_vocab, max_len=50):
        batch_size = encoder_outputs.shape[0]
        device = encoder_outputs.device
        decoder_hidden = self._init_hidden(encoder_hidden)
        input_token = torch.full((batch_size, 1), jawi_vocab['<sos>'],
                                 dtype=torch.long, device=device)
        predictions = []
        for _ in range(max_len):
            output, decoder_hidden, _ = self._forward_step(
                input_token, decoder_hidden, encoder_outputs
            )
            pred_token = output.argmax(dim=-1)
            predictions.append(pred_token)
            if (pred_token == jawi_vocab['<eos>']).all():
                break
            input_token = pred_token.unsqueeze(1)
        return torch.stack(predictions, dim=1)


class Seq2Seq(nn.Module):
    def __init__(self, encoder, decoder):
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder

    def forward(self, src, trg):
        encoder_outputs, encoder_hidden = self.encoder(src)
        return self.decoder(trg, encoder_outputs, encoder_hidden)


# ============================================================
# INFERENCE
# ============================================================

def batch_predict(model, words, rumi_vocab, jawi_vocab, jawi_inv, device='cpu', max_len=50):
    model.eval()
    indices = [[rumi_vocab.get(c, rumi_vocab['<unk>']) for c in w] for w in words]
    rumi_tensor = nn.utils.rnn.pad_sequence(
        [torch.tensor(idx) for idx in indices],
        batch_first=True, padding_value=0
    ).to(device)

    with torch.no_grad():
        encoder_outputs, encoder_hidden = model.encoder(rumi_tensor)
        predictions = model.decoder.decode(encoder_outputs, encoder_hidden, jawi_vocab, max_len)

    results = []
    eos_id = jawi_vocab.get('<eos>', 2)
    for b in range(predictions.shape[0]):
        pred_ids = predictions[b].cpu().tolist()
        jawi_chars = []
        for idx in pred_ids:
            if idx == eos_id:
                break
            jawi_chars.append(jawi_inv.get(idx, '?'))
        results.append(''.join(jawi_chars))
    return results


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("FIND PREDICTION MISTAKES (COLAB)")
    print("=" * 60)
    print(f"Device: {DEVICE}")

    # ------------------ Load checkpoint ------------------
    checkpoint_path = resolve_path(CHECKPOINT_FILE)
    if checkpoint_path is None:
        print(f"\nERROR: {CHECKPOINT_FILE} not found.")
        print(f"Expected it in: {SAVE_DIR} (or the current directory).")
        print("Train a model first with seq2seq_train_full.py, or upload best_model.pt.")
        return

    print(f"\nLoading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE)

    rumi_vocab = checkpoint['rumi_vocab']
    jawi_vocab = checkpoint['jawi_vocab']
    jawi_inv = {v: k for k, v in jawi_vocab.items()}
    hp = checkpoint.get('hyperparams', {})

    embed_dim = hp.get('embed_dim', 128)
    hidden_dim = hp.get('hidden_dim', 256)
    n_layers = hp.get('n_layers', 2)
    dropout = hp.get('dropout', 0.3)

    encoder = Encoder(len(rumi_vocab), embed_dim, hidden_dim, n_layers, dropout)
    decoder = Decoder(len(jawi_vocab), embed_dim, hidden_dim, n_layers, dropout)
    model = Seq2Seq(encoder, decoder).to(DEVICE)
    model.load_state_dict(checkpoint['model_state_dict'])
    print(f"Model loaded. Epoch {checkpoint.get('epoch', '?')}, val loss: {checkpoint.get('val_loss', '?'):.4f}")

    # ------------------ Load full dataset ------------------
    csv_path = resolve_path(CSV_FILE)
    if csv_path is None:
        print(f"\nERROR: {CSV_FILE} not found.")
        print(f"Upload it to the Colab session or copy it to: {SAVE_DIR}")
        print("Tip: run  from google.colab import files; files.upload()  to upload.")
        return

    df = pd.read_csv(csv_path, header=None, names=['rumi', 'jawi']).dropna()
    print(f"\nDataset: {len(df)} total pairs (from {csv_path})")
    print(f"Running inference on all {len(df)} words (batch_size={BATCH_SIZE})...")

    words = df['rumi'].tolist()
    true_jawis = df['jawi'].tolist()

    all_preds = []
    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i:i + BATCH_SIZE]
        preds = batch_predict(model, batch, rumi_vocab, jawi_vocab, jawi_inv, device=DEVICE)
        all_preds.extend(preds)
        if (i // BATCH_SIZE) % 50 == 0:
            print(f"  {i + len(batch)}/{len(words)} words processed...")

    # ------------------ Find mistakes ------------------
    mistakes = []
    correct_count = 0

    for w, pred, true in zip(words, all_preds, true_jawis):
        if pred != true:
            mistakes.append({'rumi': w, 'predicted': pred, 'true': true})
        else:
            correct_count += 1

    total = len(words)
    accuracy = correct_count / total * 100

    print(f"\n{'='*60}")
    print("RESULTS")
    print("=" * 60)
    print(f"Total words:     {total}")
    print(f"Correct:         {correct_count}")
    print(f"Mistakes:        {len(mistakes)}")
    print(f"Accuracy:        {accuracy:.2f}%")
    print(f"Error rate:      {100 - accuracy:.2f}%")

    # ------------------ Show sample mistakes ------------------
    n_show = min(N_SHOW, len(mistakes))
    if n_show > 0:
        print(f"\nFirst {n_show} mistakes:")
        for m in mistakes[:n_show]:
            print(f"  '{m['rumi']}' → predicted: '{m['predicted']}' | true: '{m['true']}'")

    # ------------------ Save to CSV ------------------
    if mistakes:
        out_df = pd.DataFrame(mistakes)
        out_path = os.path.join(SAVE_DIR, OUTPUT_FILE)
        out_df.to_csv(out_path, index=False)
        print(f"\nSaved {len(mistakes)} mistakes to: {out_path}")
    else:
        print("\nNo mistakes found — perfect accuracy!")


if __name__ == '__main__':
    main()
