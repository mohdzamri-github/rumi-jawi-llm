#!/usr/bin/env python3
"""Rumi -> Jawi converter CLI.

Usage:
  python3 jawi.py                 # interactive prompt
  python3 jawi.py makan minum     # convert words given as arguments
  echo "saya makan nasi" | python3 jawi.py     # convert piped text
  python3 jawi.py --rules ...     # rule-only (no dictionary lookup)

Type a word or a whole sentence; each Malay word is converted to Jawi.
Commands in interactive mode:  :rules  :hybrid  :q (quit)
"""
import sys, re
import translit, hybrid
from evaluate import load_rows

DATA = 'rumi-jawi-unicode.csv'

def build(use_dict=True):
    if not use_dict:
        return hybrid.rule_convert, 0
    try:
        rows = load_rows(DATA)
    except FileNotFoundError:
        print("(dictionary %r not found — falling back to rule-only)" % DATA, file=sys.stderr)
        return hybrid.rule_convert, 0
    convert, lut = hybrid.make_hybrid(rows)
    return convert, len(lut)

# a "word" is a run of latin letters / hyphens / apostrophes; everything else
# (spaces, punctuation, digits) is passed through unchanged.
TOKEN = re.compile(r"[A-Za-z][A-Za-z'‘’-]*")

def convert_text(text, convert):
    """convert every Malay word in a line, preserving spacing & punctuation."""
    def repl(m):
        return convert(m.group(0).lower())
    return TOKEN.sub(repl, text)

def main(argv):
    use_dict = True
    args = []
    for a in argv:
        if a in ('--rules', '-r'): use_dict = False
        elif a in ('--help', '-h'): print(__doc__); return
        else: args.append(a)

    convert, n = build(use_dict)
    mode = 'hybrid (dict+rules)' if (use_dict and n) else 'rule-only'

    # one-shot: words as arguments
    if args:
        print(convert_text(' '.join(args), convert))
        return

    # one-shot: piped stdin
    if not sys.stdin.isatty():
        for line in sys.stdin:
            print(convert_text(line.rstrip('\n'), convert))
        return

    # interactive REPL
    print("Rumi → Jawi converter  [mode: %s%s]" % (
        mode, (", %d words" % n) if n else ""))
    print("Type text to convert.  Commands: :rules  :hybrid  :q to quit")
    while True:
        try:
            line = input("rumi> ")
        except (EOFError, KeyboardInterrupt):
            print(); break
        s = line.strip()
        if s in (':q', ':quit', ':exit'): break
        if s == ':rules':
            convert, n = build(False); print("[mode: rule-only]"); continue
        if s == ':hybrid':
            convert, n = build(True); print("[mode: hybrid, %d words]" % n); continue
        if not s: continue
        print("jawi> " + convert_text(line, convert))

if __name__ == '__main__':
    main(sys.argv[1:])
