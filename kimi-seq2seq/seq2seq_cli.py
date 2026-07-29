#!/usr/bin/env python3
"""
Rumi → Jawi CLI Prediction Tool
================================

Load best_model.pt and transliterate Malay (Rumi) words to Jawi.

Usage:
    python seq2seq_cli.py --word "cinta"
    python seq2seq_cli.py --word "cinta" "makan" "rumah"
    python seq2seq_cli.py --file words.txt
    python seq2seq_cli.py --interactive
    python seq2seq_cli.py --word "cinta" --csv rumi-jawi-unicode.csv  # show ground truth if available
"""

import argparse
import os
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================
# MODEL DEFINITIONS (must match training architecture)
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
    """Transliterate a batch of Rumi words to Jawi."""
    if not words:
        return []
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
# MODEL LOADING
# ============================================================

def load_model(checkpoint_path, device):
    if not os.path.exists(checkpoint_path):
        print(f"ERROR: Checkpoint not found: {checkpoint_path}")
        sys.exit(1)

    checkpoint = torch.load(checkpoint_path, map_location=device)

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
    model = Seq2Seq(encoder, decoder).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])

    return model, rumi_vocab, jawi_vocab, jawi_inv, checkpoint


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Rumi → Jawi transliteration CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --word cinta
  %(prog)s --word cinta makan rumah
  %(prog)s --file words.txt
  %(prog)s --interactive
  %(prog)s --word cinta --csv rumi-jawi-unicode.csv
""")
    parser.add_argument('--checkpoint', type=str, default='best_model.pt',
                        help='Path to model checkpoint (default: best_model.pt)')
    parser.add_argument('--word', nargs='+', metavar='WORD',
                        help='One or more Rumi words to transliterate')
    parser.add_argument('--file', type=str,
                        help='Path to a text file with one Rumi word per line')
    parser.add_argument('--interactive', action='store_true',
                        help='Interactive mode: type words and get predictions')
    parser.add_argument('--csv', type=str, default=None,
                        help='Optional CSV dataset to show ground-truth Jawi for comparison')
    parser.add_argument('--device', type=str, default=None,
                        help='Device: cpu or cuda (auto-detected if not set)')
    parser.add_argument('--batch-size', type=int, default=64,
                        help='Batch size for inference (default: 64)')
    args = parser.parse_args()

    device = torch.device(args.device if args.device else ('cuda' if torch.cuda.is_available() else 'cpu'))

    # Load model
    model, rumi_vocab, jawi_vocab, jawi_inv, checkpoint = load_model(args.checkpoint, device)
    model.eval()

    print(f"Loaded model: {args.checkpoint}")
    print(f"  Best epoch: {checkpoint.get('epoch', '?')}, val loss: {checkpoint.get('val_loss', '?'):.4f}")
    print(f"  Device: {device}")
    print()

    # Optional ground-truth lookup
    truth_map = {}
    if args.csv and os.path.exists(args.csv):
        import pandas as pd
        df = pd.read_csv(args.csv, header=None, names=['rumi', 'jawi']).dropna()
        truth_map = dict(zip(df['rumi'], df['jawi']))

    # Determine input words
    if args.interactive:
        print("Interactive Rumi → Jawi transliterator")
        print("Type a word and press Enter. Press Ctrl+C or type 'quit' to exit.\n")
        try:
            while True:
                try:
                    word = input("Rumi: ").strip()
                except EOFError:
                    break
                if not word or word.lower() in ('quit', 'exit', 'q'):
                    break
                preds = batch_predict(model, [word], rumi_vocab, jawi_vocab, jawi_inv, device=device)
                pred = preds[0]
                if word in truth_map:
                    true_jawi = truth_map[word]
                    mark = "✓" if pred == true_jawi else "✗"
                    print(f"Jawi: {pred}  {mark} (true: {true_jawi})")
                else:
                    print(f"Jawi: {pred}")
                print()
        except KeyboardInterrupt:
            print("\nGoodbye.")
            return

    elif args.file:
        if not os.path.exists(args.file):
            print(f"ERROR: File not found: {args.file}")
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8') as f:
            words = [line.strip() for line in f if line.strip()]
        if not words:
            print("ERROR: Input file is empty.")
            sys.exit(1)

        all_preds = []
        for i in range(0, len(words), args.batch_size):
            batch = words[i:i + args.batch_size]
            preds = batch_predict(model, batch, rumi_vocab, jawi_vocab, jawi_inv, device=device)
            all_preds.extend(preds)

        for w, p in zip(words, all_preds):
            if w in truth_map:
                true_jawi = truth_map[w]
                mark = "✓" if p == true_jawi else "✗"
                print(f"{mark} {w} -> {p}  (true: {true_jawi})")
            else:
                print(f"  {w} -> {p}")

    elif args.word:
        words = args.word
        all_preds = []
        for i in range(0, len(words), args.batch_size):
            batch = words[i:i + args.batch_size]
            preds = batch_predict(model, batch, rumi_vocab, jawi_vocab, jawi_inv, device=device)
            all_preds.extend(preds)

        for w, p in zip(words, all_preds):
            if w in truth_map:
                true_jawi = truth_map[w]
                mark = "✓" if p == true_jawi else "✗"
                print(f"{mark} {w} -> {p}  (true: {true_jawi})")
            else:
                print(f"  {w} -> {p}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
