#!/usr/bin/env python3
"""rumi-jawi-cli.py — transliterate Malay (Rumi) text into Jawi.

It reuses the same engine as the rest of the project:
  * translit.py  — the Rumi->Jawi RULE engine (see plan.md for the derivation)
  * hybrid.py    — reduplication/hyphen handling + dictionary lookup with rule fallback
  * rumi-jawi-unicode.csv — the rumi,jawi word list used as the dictionary

Two conversion modes:
  hybrid (default)  look each word up in the dictionary; fall back to the rules
                    for any word not in the list  (best accuracy on real words)
  rules  (--rules)  ignore the dictionary and apply the rules to every word
                    (shows what the rule engine alone produces — good for testing
                    the rules on new/unseen words)

USAGE
  # words / sentences straight from the command line
  python3 rumi-jawi-cli.py saya makan nasi
  python3 rumi-jawi-cli.py "Dia belajar di sekolah."

  # rule-only (no dictionary) — useful when testing new words against the rules
  python3 rumi-jawi-cli.py --rules mengabadikan

  # pipe text in, or convert a whole file, one line at a time
  echo "selamat pagi" | python3 rumi-jawi-cli.py
  python3 rumi-jawi-cli.py --file cerita.txt

  # show, per word, whether it came from the dictionary [dict] or the rules [rule]
  python3 rumi-jawi-cli.py --verbose keadaan xylophone

  # interactive prompt (no arguments, and input is a terminal)
  python3 rumi-jawi-cli.py

INTERACTIVE COMMANDS
  :rules     switch to rule-only mode
  :hybrid    switch back to dictionary+rules mode
  :verbose   toggle the [dict]/[rule] source tags
  :help      show this help
  :q         quit
"""
import sys
import os
import re
import argparse

import translit
import hybrid
from evaluate import load_rows

# dictionary lives next to this script regardless of the current directory
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'rumi-jawi-unicode.csv')

# A "word" is a run of latin letters plus the hyphens/apostrophes that occur
# inside Malay words (reduplication "anak-anak", clitics "'ain"). Everything
# else — spaces, punctuation, digits, Jawi already present — passes through as-is.
TOKEN = re.compile(r"[A-Za-z][A-Za-z'‘’-]*")


class Converter:
    """Wraps the chosen conversion function and reports per-word provenance."""

    def __init__(self, use_dict=True):
        self.use_dict = use_dict
        self.lut = {}
        self.convert_word = hybrid.rule_convert
        if use_dict:
            try:
                _, self.lut = hybrid.make_hybrid(load_rows(DATA))
            except FileNotFoundError:
                print("(dictionary %r not found — using rule-only mode)" % DATA,
                      file=sys.stderr)
                self.use_dict = False

    @property
    def mode(self):
        return "hybrid (dict+rules)" if self.use_dict else "rule-only"

    def word(self, w):
        """convert a single lowered word; return (jawi, source) where
        source is 'dict' or 'rule'."""
        if self.use_dict and w in self.lut:
            return self.lut[w], 'dict'
        return hybrid.rule_convert(w), 'rule'

    def text(self, line, verbose=False):
        """convert every Malay word in a line, preserving spacing & punctuation."""
        if verbose:
            def repl(m):
                jawi, src = self.word(m.group(0).lower())
                return "%s[%s]" % (jawi, src)
            return TOKEN.sub(repl, line)
        return TOKEN.sub(lambda m: self.word(m.group(0).lower())[0], line)


def run_interactive(conv, verbose):
    print("Rumi → Jawi converter  [mode: %s%s]" % (
        conv.mode, (", %d words" % len(conv.lut)) if conv.lut else ""))
    print("Type Malay text to convert. Commands: :rules :hybrid :verbose :help :q")
    while True:
        try:
            line = input("rumi> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        s = line.strip()
        if s in (':q', ':quit', ':exit'):
            break
        if s == ':help':
            print(__doc__)
            continue
        if s == ':rules':
            conv = Converter(use_dict=False)
            print("[mode: rule-only]")
            continue
        if s == ':hybrid':
            conv = Converter(use_dict=True)
            print("[mode: hybrid, %d words]" % len(conv.lut))
            continue
        if s == ':verbose':
            verbose = not verbose
            print("[verbose: %s]" % ("on" if verbose else "off"))
            continue
        if not s:
            continue
        print("jawi> " + conv.text(line, verbose))


def build_parser():
    p = argparse.ArgumentParser(
        prog='rumi-jawi-cli.py',
        description='Transliterate Malay (Rumi) text into Jawi.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="With no words, no --file and no piped input, an interactive "
               "prompt is started.\nSee the module docstring for full examples.")
    p.add_argument('words', nargs='*',
                   help='Malay word(s) or sentence to convert')
    p.add_argument('-r', '--rules', action='store_true',
                   help='rule-only mode: ignore the dictionary, apply rules to every word')
    p.add_argument('-f', '--file', metavar='PATH',
                   help='read Rumi text from a file (converted line by line)')
    p.add_argument('-v', '--verbose', action='store_true',
                   help='tag each word with its source: [dict] or [rule]')
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    conv = Converter(use_dict=not args.rules)

    # 1) explicit file
    if args.file:
        try:
            with open(args.file, encoding='utf-8') as f:
                for line in f:
                    print(conv.text(line.rstrip('\n'), args.verbose))
        except OSError as e:
            print("error: cannot read %r: %s" % (args.file, e), file=sys.stderr)
            return 1
        return 0

    # 2) words given on the command line
    if args.words:
        print(conv.text(' '.join(args.words), args.verbose))
        return 0

    # 3) piped stdin
    if not sys.stdin.isatty():
        for line in sys.stdin:
            print(conv.text(line.rstrip('\n'), args.verbose))
        return 0

    # 4) interactive REPL
    run_interactive(conv, args.verbose)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
