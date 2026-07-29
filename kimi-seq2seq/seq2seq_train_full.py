"""
Rumi → Jawi Seq2Seq Training Script (Google Colab Optimized)
============================================================

Run this in Google Colab:
1. Upload `rumi-jawi-unicode.csv` to the Colab session
2. Run all cells
3. Model checkpoints and plots are saved to `/content/drive/MyDrive/rumi-jawi-model/`

To skip Google Drive mounting, set `USE_DRIVE = False` below.
"""

import os
import time
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split

# ============================================================
# CONFIGURATION
# ============================================================

USE_DRIVE = True              # Set to False to skip Google Drive mount
DRIVE_PATH = '/content/drive/MyDrive/rumi-jawi-model'
CSV_FILE = 'rumi-jawi-unicode.csv'

# Hyperparameters for full training
EMBED_DIM = 128
HIDDEN_DIM = 256
N_LAYERS = 2
DROPOUT = 0.3
LEARNING_RATE = 0.001
N_EPOCHS = 50
BATCH_SIZE = 128
TEST_SIZE = 0.1
RANDOM_STATE = 42

EARLY_STOPPING_PATIENCE = 5   # Stop if val loss doesn't improve for N epochs
GRAD_CLIP = 1.0

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
            print(f"Drive mounted. Saving to: {DRIVE_PATH}")
            return DRIVE_PATH
        except ImportError:
            print("Not in Colab — skipping Drive mount.")
    return '.'

SAVE_DIR = setup_drive()

# ============================================================
# MODEL DEFINITIONS
# ============================================================

class Encoder(nn.Module):
    """Bidirectional GRU Encoder."""
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
    """Additive (Bahdanau) Attention."""
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
    """GRU Decoder with Bahdanau Attention."""
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
# DATASET & DATALOADER
# ============================================================

class RumiJawiDataset(Dataset):
    def __init__(self, df, rumi_vocab, jawi_vocab):
        self.df = df.reset_index(drop=True)
        self.rumi_vocab = rumi_vocab
        self.jawi_vocab = jawi_vocab

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        rumi = self.df['rumi'].iloc[idx]
        jawi = self.df['jawi'].iloc[idx]
        rumi_idx = [self.rumi_vocab[c] for c in rumi]
        jawi_idx = ([self.jawi_vocab['<sos>']] +
                    [self.jawi_vocab[c] for c in jawi] +
                    [self.jawi_vocab['<eos>']])
        return torch.tensor(rumi_idx), torch.tensor(jawi_idx)


def collate_fn(batch):
    rumi_seqs, jawi_seqs = zip(*batch)
    rumi_padded = nn.utils.rnn.pad_sequence(rumi_seqs, batch_first=True, padding_value=0)
    jawi_padded = nn.utils.rnn.pad_sequence(jawi_seqs, batch_first=True, padding_value=0)
    return rumi_padded, jawi_padded


# ============================================================
# TRAINING & EVALUATION
# ============================================================

def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss = 0
    for rumi, jawi in loader:
        rumi, jawi = rumi.to(device), jawi.to(device)
        optimizer.zero_grad()
        outputs, _ = model(rumi, jawi)
        loss = criterion(outputs.reshape(-1, outputs.shape[-1]), jawi[:, 1:].reshape(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=GRAD_CLIP)
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0
    with torch.no_grad():
        for rumi, jawi in loader:
            rumi, jawi = rumi.to(device), jawi.to(device)
            outputs, _ = model(rumi, jawi)
            loss = criterion(outputs.reshape(-1, outputs.shape[-1]), jawi[:, 1:].reshape(-1))
            total_loss += loss.item()
    return total_loss / len(loader)


# ============================================================
# INFERENCE (batched)
# ============================================================

def batch_rumi_to_jawi(model, words, rumi_vocab, jawi_vocab, jawi_inv, device='cpu', max_len=50):
    """Transliterate multiple Rumi words in one batch."""
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
    print("RUMI → JAWI SEQ2SEQ TRAINING (FULL)")
    print("=" * 60)
    print(f"Device: {DEVICE}")
    print(f"PyTorch version: {torch.__version__}")

    # ------------------ Load Data ------------------
    if not os.path.exists(CSV_FILE):
        print(f"\nERROR: {CSV_FILE} not found.")
        print("Please upload the CSV file to the Colab session.")
        return

    df = pd.read_csv(CSV_FILE, header=None, names=['rumi', 'jawi'])
    df = df.dropna()
    print(f"\nTotal pairs loaded: {len(df)}")
    print(f"Rumi length: min={df['rumi'].str.len().min()}, max={df['rumi'].str.len().max()}, mean={df['rumi'].str.len().mean():.1f}")
    print(f"Jawi length: min={df['jawi'].str.len().min()}, max={df['jawi'].str.len().max()}, mean={df['jawi'].str.len().mean():.1f}")

    # ------------------ Vocabularies ------------------
    rumi_chars = set()
    jawi_chars = set()
    for r, j in zip(df['rumi'], df['jawi']):
        rumi_chars.update(r)
        jawi_chars.update(j)

    special = {'<pad>': 0, '<sos>': 1, '<eos>': 2, '<unk>': 3}
    rumi_vocab = {**special, **{ch: i + 4 for i, ch in enumerate(sorted(rumi_chars))}}
    jawi_vocab = {**special, **{ch: i + 4 for i, ch in enumerate(sorted(jawi_chars))}}
    rumi_inv = {v: k for k, v in rumi_vocab.items()}
    jawi_inv = {v: k for k, v in jawi_vocab.items()}

    print(f"\nRumi vocab size: {len(rumi_vocab)}")
    print(f"Jawi vocab size: {len(jawi_vocab)}")

    # ------------------ DataLoaders ------------------
    train_df, test_df = train_test_split(df, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    train_loader = DataLoader(
        RumiJawiDataset(train_df, rumi_vocab, jawi_vocab),
        batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn
    )
    test_loader = DataLoader(
        RumiJawiDataset(test_df, rumi_vocab, jawi_vocab),
        batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_fn
    )
    print(f"\nTrain: {len(train_df)} | Test: {len(test_df)}")
    print(f"Train batches: {len(train_loader)} | Test batches: {len(test_loader)}")

    # ------------------ Model ------------------
    encoder = Encoder(len(rumi_vocab), EMBED_DIM, HIDDEN_DIM, N_LAYERS, DROPOUT)
    decoder = Decoder(len(jawi_vocab), EMBED_DIM, HIDDEN_DIM, N_LAYERS, DROPOUT)
    model = Seq2Seq(encoder, decoder).to(DEVICE)

    pad_idx = jawi_vocab['<pad>']
    criterion = nn.CrossEntropyLoss(ignore_index=pad_idx)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nTotal parameters: {n_params:,}")

    # ------------------ Training ------------------
    print("\n" + "=" * 60)
    print("TRAINING")
    print("=" * 60)

    train_losses, val_losses = [], []
    best_val = float('inf')
    patience_counter = 0
    start_time = time.time()

    for epoch in range(N_EPOCHS):
        epoch_start = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, criterion, DEVICE)
        val_loss = evaluate(model, test_loader, criterion, DEVICE)
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        elapsed = time.time() - epoch_start

        print(f"Epoch {epoch+1:2d}/{N_EPOCHS} | "
              f"Train: {train_loss:.4f} | Val: {val_loss:.4f} | "
              f"Time: {elapsed:.1f}s")

        # Save best model
        if val_loss < best_val:
            best_val = val_loss
            patience_counter = 0
            checkpoint = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss': train_loss,
                'val_loss': val_loss,
                'rumi_vocab': rumi_vocab,
                'jawi_vocab': jawi_vocab,
                'hyperparams': {
                    'embed_dim': EMBED_DIM,
                    'hidden_dim': HIDDEN_DIM,
                    'n_layers': N_LAYERS,
                    'dropout': DROPOUT,
                }
            }
            save_path = os.path.join(SAVE_DIR, 'best_model.pt')
            torch.save(checkpoint, save_path)
            print(f"  → Saved best model (val loss: {best_val:.4f})")
        else:
            patience_counter += 1

        # Early stopping
        if patience_counter >= EARLY_STOPPING_PATIENCE:
            print(f"\nEarly stopping triggered after {epoch+1} epochs (no improvement for {EARLY_STOPPING_PATIENCE} epochs).")
            break

    total_time = time.time() - start_time
    print(f"\nTotal training time: {total_time:.1f}s ({total_time/60:.1f} min)")

    # ------------------ Plot ------------------
    epochs_ran = len(train_losses)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(range(1, epochs_ran + 1), train_losses, 'b-o', label='Train Loss', linewidth=2)
    ax.plot(range(1, epochs_ran + 1), val_losses, 'r-s', label='Val Loss', linewidth=2)
    ax.set_xlabel('Epoch')
    ax.set_ylabel('Loss')
    ax.set_title('Training and Validation Loss')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plot_path = os.path.join(SAVE_DIR, 'training_curve.png')
    plt.savefig(plot_path, dpi=150)
    plt.show()
    print(f"\nTraining curve saved to: {plot_path}")

    # ------------------ Load Best Model ------------------
    best_path = os.path.join(SAVE_DIR, 'best_model.pt')
    if os.path.exists(best_path):
        checkpoint = torch.load(best_path, map_location=DEVICE)
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"Loaded best model from epoch {checkpoint['epoch']} (val loss: {checkpoint['val_loss']:.4f})")

    # ------------------ Inference on Test Set ------------------
    print("\n" + "=" * 60)
    print("RUMI → JAWI TRANSLITERATION RESULTS")
    print("=" * 60)

    test_words = test_df['rumi'].tolist()
    true_jawis = test_df['jawi'].tolist()
    preds = batch_rumi_to_jawi(model, test_words, rumi_vocab, jawi_vocab, jawi_inv, device=DEVICE)

    correct = sum(p == t for p, t in zip(preds, true_jawis))
    n_show = min(20, len(test_words))
    print(f"\n--- Test set sample ({n_show}/{len(test_words)} words) ---")
    for w, p, t in zip(test_words[:n_show], preds[:n_show], true_jawis[:n_show]):
        mark = "✓" if p == t else "✗"
        print(f"{mark} '{w}' → '{p}' (true: '{t}')")
    print(f"\nTest accuracy: {correct}/{len(test_words)} = {correct/len(test_words)*100:.1f}%")

    # ------------------ Custom Words ------------------
    custom = ['abadi', 'adil', 'air', 'api', 'besar', 'cinta', 'hati', 'makan', 'rumah', 'sayang']
    custom_preds = batch_rumi_to_jawi(model, custom, rumi_vocab, jawi_vocab, jawi_inv, device=DEVICE)
    print("\n--- Custom words ---")
    for w, p in zip(custom, custom_preds):
        print(f"  '{w}' → '{p}'")

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Best model saved to: {os.path.join(SAVE_DIR, 'best_model.pt')}")


if __name__ == '__main__':
    main()
