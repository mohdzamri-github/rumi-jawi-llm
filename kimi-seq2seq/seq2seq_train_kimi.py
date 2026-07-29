import argparse
import sys
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

def get_config(smoke_test=True):
    """Return hyperparameters. Smoke test uses tiny model for fast execution."""
    if smoke_test:
        return {
            'sample_n': 100,
            'test_size': 0.1,
            'embed_dim': 16,
            'hidden_dim': 32,
            'n_layers': 1,
            'dropout': 0.0,
            'lr': 0.001,
            'epochs': 10,
            'batch_size': 32,
            'device': 'cpu',
            'plot': True,
            'verbose': True,
        }
    else:
        return {
            'sample_n': None,          # None = use full dataset
            'test_size': 0.1,
            'embed_dim': 128,
            'hidden_dim': 256,
            'n_layers': 2,
            'dropout': 0.3,
            'lr': 0.001,
            'epochs': 30,
            'batch_size': 128,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'plot': True,
            'verbose': True,
        }

# ============================================================
# MODEL DEFINITIONS
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
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1)
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
# INFERENCE (batched for speed)
# ============================================================

def rumi_to_jawi(model, word, rumi_vocab, jawi_inv, device='cpu', max_len=50):
    """Transliterate a single Rumi word to Jawi."""
    model.eval()
    rumi_idx = [rumi_vocab.get(c, rumi_vocab['<unk>']) for c in word]
    rumi_tensor = torch.tensor([rumi_idx], device=device)

    with torch.no_grad():
        encoder_outputs, encoder_hidden = model.encoder(rumi_tensor)
        predictions = model.decoder.decode(encoder_outputs, encoder_hidden, jawi_vocab, max_len)

    pred_ids = predictions[0].cpu().tolist()
    jawi_chars = []
    for idx in pred_ids:
        if idx == jawi_vocab['<eos>']:
            break
        jawi_chars.append(jawi_inv.get(idx, '?'))
    return ''.join(jawi_chars)


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

def main(smoke_test=True):
    cfg = get_config(smoke_test=smoke_test)
    device = torch.device(cfg['device'])
    verbose = cfg['verbose']

    # ------------------ Load Data ------------------
    df = pd.read_csv('./rumi-jawi-unicode.csv', header=None, names=['rumi', 'jawi'])
    df = df.dropna()
    if cfg['sample_n']:
        df = df.sample(n=cfg['sample_n'], random_state=42).reset_index(drop=True)

    if verbose:
        print("=" * 60)
        print("DATA OVERVIEW")
        print("=" * 60)
        print(f"Total pairs: {len(df)}")
        print(df.head(5).to_string())
        print(f"\nRumi lengths: min={df['rumi'].str.len().min()}, max={df['rumi'].str.len().max()}")
        print(f"Jawi lengths: min={df['jawi'].str.len().min()}, max={df['jawi'].str.len().max()}")
    else:
        print(f"Loaded {len(df)} pairs")

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

    print(f"Rumi vocab: {len(rumi_vocab)}, Jawi vocab: {len(jawi_vocab)}")

    # ------------------ DataLoaders ------------------
    train_df, test_df = train_test_split(df, test_size=cfg['test_size'], random_state=42)
    train_loader = DataLoader(
        RumiJawiDataset(train_df, rumi_vocab, jawi_vocab),
        batch_size=cfg['batch_size'], shuffle=True, collate_fn=collate_fn
    )
    test_loader = DataLoader(
        RumiJawiDataset(test_df, rumi_vocab, jawi_vocab),
        batch_size=cfg['batch_size'], shuffle=False, collate_fn=collate_fn
    )
    print(f"Train: {len(train_df)} | Test: {len(test_df)} | Batches: {len(train_loader)}")

    # ------------------ Model ------------------
    encoder = Encoder(len(rumi_vocab), cfg['embed_dim'], cfg['hidden_dim'],
                      cfg['n_layers'], cfg['dropout'])
    decoder = Decoder(len(jawi_vocab), cfg['embed_dim'], cfg['hidden_dim'],
                      cfg['n_layers'], cfg['dropout'])
    model = Seq2Seq(encoder, decoder).to(device)

    pad_idx = jawi_vocab['<pad>']
    criterion = nn.CrossEntropyLoss(ignore_index=pad_idx)
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg['lr'])

    n_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n_params:,} | Device: {device} | Epochs: {cfg['epochs']}")

    # ------------------ Training ------------------
    print("\n" + "=" * 60)
    print("TRAINING")
    print("=" * 60)

    train_losses, val_losses = [], []
    best_val = float('inf')

    for epoch in range(cfg['epochs']):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss = evaluate(model, test_loader, criterion, device)
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        print(f"Epoch {epoch+1:2d}/{cfg['epochs']} | Train: {train_loss:.4f} | Val: {val_loss:.4f}")

        if val_loss < best_val:
            best_val = val_loss
            # Optional: save best model
            # torch.save(model.state_dict(), 'best_model.pt')

    # ------------------ Plot ------------------
    if cfg['plot']:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(range(1, cfg['epochs'] + 1), train_losses, 'b-o', label='Train')
        ax.plot(range(1, cfg['epochs'] + 1), val_losses, 'r-s', label='Val')
        ax.set_xlabel('Epoch')
        ax.set_ylabel('Loss')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('./rumi_jawi_training.png', dpi=150)
        plt.close()
        print("\nTraining curve saved!")

    # ------------------ Inference ------------------
    print("\n" + "=" * 60)
    print("RUMI → JAWI TRANSLITERATION RESULTS")
    print("=" * 60)

    # Batch inference on test set
    test_words = test_df['rumi'].tolist()
    true_jawis = test_df['jawi'].tolist()
    preds = batch_rumi_to_jawi(model, test_words, rumi_vocab, jawi_vocab, jawi_inv, device=device)

    correct = sum(p == t for p, t in zip(preds, true_jawis))
    print(f"\n--- Test set ({len(test_words)} words) ---")
    for w, p, t in zip(test_words, preds, true_jawis):
        mark = "✓" if p == t else "✗"
        print(f"{mark} '{w}' → '{p}' (true: '{t}')")
    print(f"\nAccuracy: {correct}/{len(test_words)} = {correct/len(test_words)*100:.1f}%")

    # Custom words
    custom = ['abadi', 'adil', 'air', 'api', 'besar', 'cinta', 'hati', 'makan', 'rumah', 'sayang']
    custom_preds = batch_rumi_to_jawi(model, custom, rumi_vocab, jawi_vocab, jawi_inv, device=device)
    print("\n--- Custom words ---")
    for w, p in zip(custom, custom_preds):
        print(f"  '{w}' → '{p}'")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='Run full training instead of smoke test')
    args = parser.parse_args()
    main(smoke_test=not args.full)
