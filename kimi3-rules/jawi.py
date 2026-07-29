#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jawi.py - Rumi (Malay in Latin script) -> Jawi (Malay in Arabic script) transliterator.

Strategy (in order):
  1. Dictionary lookup (built from rumi-jawi-unicode.csv).
  2. Morphological decomposition: strip Malay affixes, look up the stem in the
     dictionary, recompose with the Jawi form of the affixes.
  3. Rule-based transliteration (DBP-style Jawi orthography) for unknown stems.

The module can be used as a library (class `Jawi`) or as a CLI:

    python3 jawi.py saya makan nasi
    echo "selamat pagi" | python3 jawi.py
    python3 jawi.py --text "Saya suka makan."
"""

import os
import re
import sys

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "rumi-jawi-unicode.csv")

# ---------------------------------------------------------------------------
# Letter tables (corpus conventions: g -> U+0762, k -> U+06A9, p -> U+06A4)
# ---------------------------------------------------------------------------
DIGRAPH = {
    "ng": "ڠ",   # U+06A0
    "ny": "ڽ",   # U+06BD
    "sy": "ش",   # U+0634
    "kh": "خ",   # U+062E
    "gh": "غ",   # U+063A
}
CONS = {
    "b": "ب", "c": "چ", "d": "د", "f": "ف", "g": "ݢ",
    "h": "ه", "j": "ج", "k": "ک", "l": "ل", "m": "م",
    "n": "ن", "p": "ڤ", "q": "ق", "r": "ر", "s": "س",
    "t": "ت", "v": "ۏ", "w": "و", "x": "کس", "y": "ي",
    "z": "ز",
}
VOWELS = set("aiueo")
MATRES = ("ا", "و", "ي", "ى")
FINAL_KAF = "ق"          # word-final -k (tidak -> تيدق)
REDUP = "٢"              # reduplication marker (anak-anak -> انق٢)


def load_dictionary(path=CSV_PATH):
    """Return dict: rumi -> [jawi variants] (first occurrence is canonical)."""
    d = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip("\r\n")
            if not line or "," not in line:
                continue
            r, j = line.split(",", 1)
            r, j = r.strip(), j.strip()
            if not r or not j:
                continue
            d.setdefault(r, [])
            if j not in d[r]:
                d[r].append(j)
    return d


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------
def tokenize(w):
    """Split into units, keeping digraphs (ng, ny, sy, kh, gh) as one unit."""
    out, i = [], 0
    while i < len(w):
        if w[i:i + 2] in DIGRAPH:
            out.append(w[i:i + 2])
            i += 2
        else:
            out.append(w[i])
            i += 1
    return out


class RuleConfig:
    """Tunable switches for the rule engine (chosen by held-out testing)."""
    drop_final_a_after_kg = True    # suka -> سوک, aneka -> انيک
    drop_final_a_after_y = True     # saya -> ساي, bahaya -> بهاي
    final_e = "ى"                   # -isme -> سمى (majority convention)
    medial_e = "drop"               # pepet handling: "drop" | "ya" | "open"
    initial_e = "اي"                # eja -> ايجا (majority convention)


def _is_cons(tok):
    return tok not in VOWELS


def _has_cluster(toks, skip_i):
    """True if tokens contain a consonant cluster other than the pair at skip_i."""
    for a in range(len(toks) - 1):
        if a == skip_i:
            continue
        if _is_cons(toks[a]) and _is_cons(toks[a + 1]):
            return True
    return False


def _closed_syllable(nxt, nxt2):
    """True when a vowel sits in a closed syllable (Coda follows)."""
    return nxt is not None and _is_cons(nxt) and \
        (nxt2 is None or _is_cons(nxt2))


def render_single(v, initial, final, prev, nxt, nxt2, cfg):
    """Render one vowel. prev/nxt/nxt2 are neighbouring tokens (None at edges)."""
    if v == "a":
        if initial:
            return "ا"
        if final:
            if prev == "ny":                       # -nya -> ڽ
                return ""
            if cfg.drop_final_a_after_kg and prev in ("k", "g"):
                return ""                          # suka -> سوک
            if cfg.drop_final_a_after_y and prev == "y":
                return ""                          # saya -> ساي
            return "ا"
        # medial 'a': written (alif) in open syllables, dropped in closed ones
        if _closed_syllable(nxt, nxt2):
            return ""                              # bapak -> باڤق
        return "ا"                                 # abadi -> ابادي
    if v == "i":
        return "اي" if initial else "ي"
    if v == "u":
        return "او" if initial else "و"
    if v == "e":
        if initial:
            return cfg.initial_e
        if final:
            return cfg.final_e
        if cfg.medial_e == "ya":
            return "ي"
        if cfg.medial_e == "open":
            return "" if _closed_syllable(nxt, nxt2) else "ي"
        return ""                                  # pepet: tengah -> تڠه
    if v == "o":
        return "او" if initial else "و"
    return ""


def render_seq(seq, initial, final, nxt, nxt2, cfg):
    """Render a run of 2+ vowels (diphthongs and hiatus)."""
    if len(seq) > 2:
        # split off the first vowel, then re-render the remaining run
        first = render_single(seq[0], initial, False, None, seq[1], None, cfg)
        return first + render_seq(seq[1:], False, final, nxt, nxt2, cfg)

    ini_i = "اي" if initial else "ي"
    ini_u = "او" if initial else "و"

    if seq == "ai":
        return "اي" if (final and not initial) else "اءي"
    if seq == "au":
        return "او" if (final and not initial) else "اءو"
    if seq == "ae":
        return "اي" if initial else "اءي"          # aero -> ايرو, daerah -> داءيره
    if seq == "aa":
        # second 'a' follows normal syllable rules: keadaan -> کاداءن
        return "اء" + render_single("a", False, final, "a", nxt, nxt2, cfg)
    if seq == "ui":
        return ini_u + "ءي"                        # kuih -> کوءيه
    if seq == "oi":
        # -oid loans take hamzah, word-final -oi does not (amboi -> امبوي)
        return ("اوي" if initial else "وي") if final else ini_u + "ءي"
    if seq == "ei":
        return ini_i + "ئي"                        # ateis -> اتيئيس
    if seq == "ie":
        return ini_i + "ئ"                         # ampere -> امڤيئر
    if seq in ("ii", "ee"):
        return ini_i + "ئي"
    if seq in ("uu", "oo"):
        return ini_u + "ءو"                        # koordinasi -> کوءورديناسي
    # smooth hiatus without hamzah
    if seq == "ia":
        if nxt == "h" and nxt2 is None:
            return "يئ"                            # tahniah -> تهنيئه
        return ini_i + "ا"                         # niaga -> نياݢ
    if seq == "ea":
        if final:
            return ini_i + "ا"                     # alinea -> الينيا
        return ("اي" if initial else "") + "ا"     # keadaan -> کاداءن
    if seq in ("io", "iu", "eu", "eo"):
        return ini_i + "و"                         # radio, tiub, deodoran
    if seq in ("ua", "oa"):
        return ini_u + "ا"                         # bual, proaktif
    if seq in ("ue",):
        return ini_u + "ي"
    if seq in ("uo",):
        return ini_u + "و"
    # fallback: render each vowel on its own
    return render_single(seq[0], initial, False, None, seq[1], None, cfg) + \
        render_single(seq[1], False, final, seq[0], nxt, nxt2, cfg)


def rules_word(w, cfg=RuleConfig()):
    """Pure rule-based transliteration of a single lowercase word (no dict)."""
    w = w.lower()
    if not w:
        return ""
    if "-" in w:
        parts = w.split("-")
        if len(parts) == 2 and parts[0] == parts[1]:
            return rules_word(parts[0], cfg) + REDUP
        if parts[0] == "al":                       # al-ijarah -> الاجارة
            return rules_word(parts[0], cfg) + \
                "".join(rules_word(p, cfg) for p in parts[1:] if p)
        return "-".join(rules_word(p, cfg) for p in parts if p)

    toks = tokenize(w)
    out, i, n = [], 0, len(toks)
    while i < n:
        t = toks[i]
        if t in VOWELS:
            j = i
            while j < n and toks[j] in VOWELS:
                j += 1
            seq = "".join(toks[i:j])
            prev = toks[i - 1] if i > 0 else None
            nxt = toks[j] if j < n else None
            nxt2 = toks[j + 1] if j + 1 < n else None
            if len(seq) == 1:
                out.append(render_single(seq, i == 0, j == n, prev, nxt, nxt2, cfg))
            else:
                out.append(render_seq(seq, i == 0, j == n, nxt, nxt2, cfg))
            i = j
        elif t in DIGRAPH:
            out.append(DIGRAPH[t])
            i += 1
        elif t == "k":
            if i == n - 1:
                out.append(FINAL_KAF)              # tidak -> تيدق
            elif toks[i + 1] == "s":
                # coda k before s -> qaf (saksi -> سقسي), but in foreign
                # onset clusters the kaf stays (konstruksi -> کونستروکسي)
                out.append(CONS["k"] if _has_cluster(toks, i) else FINAL_KAF)
            else:
                out.append(CONS["k"])
            i += 1
        elif t in CONS:
            out.append(CONS[t])
            i += 1
        elif t == "x":
            out.append("ز" if i == 0 else CONS["x"])   # xenon -> زينون
            i += 1
        else:
            out.append(t)                          # pass through digits etc.
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Morphology
# ---------------------------------------------------------------------------
# (rumi prefix, jawi prefix, restorable initials, drop stem alif before vowel)
PREFIXES = [
    ("memper", "ممڤر", ("",), False),
    ("diper", "دڤر", ("",), False),
    ("menge", "مڠ", ("",), False),
    ("meng", "مڠ", ("", "k"), True),
    ("mem", "مم", ("", "p"), True),
    ("men", "من", ("", "t"), True),
    ("meny", "مڽ", ("", "s", "ny"), True),
    ("peng", "ڤڠ", ("", "k"), True),
    ("pem", "ڤم", ("", "p"), True),
    ("pen", "ڤن", ("", "t"), True),
    ("peny", "ڤڽ", ("", "s", "ny"), True),
    ("ber", "بر", ("", "r"), False),
    ("ter", "تر", ("",), False),
    ("per", "ڤر", ("",), False),
    ("pel", "ڤل", ("",), False),
    ("di", "د", ("",), False),
    ("ke", "ک", ("",), False),
    ("se", "س", ("",), False),
    ("me", "م", ("",), False),
    ("pe", "ڤ", ("",), False),
    ("be", "ب", ("",), False),
]
# restore letter -> jawi letter to strip from the start of the stem
RESTORE_JAWI = {"k": "ک", "p": "ڤ", "t": "ت", "s": "س", "ny": "ڽ", "r": "ر"}

OUTER_SUFFIXES = ("nya", "lah", "kah", "tah", "pun", "ku", "mu")
INNER_SUFFIXES = ("kan", "an", "i")

PARTICLE_JAWI = {
    "nya": "ڽ", "lah": "له", "kah": "که", "tah": "ته",
    "pun": "ڤون", "ku": "کو", "mu": "مو",
}


def _suffix_jawi(sfx, stem_rumi, stem_jawi):
    """Jawi form of a suffix, given the rumi/jawi shape of what it attaches to."""
    if sfx == "kan":
        if stem_jawi.endswith(MATRES):
            return "کن"                            # bagaikan -> باݢايکن
        if stem_jawi.endswith("ڽ"):
            return "اکن"                           # bertanyakan -> برتاڽاکن
        if stem_rumi[-1:] in VOWELS:
            return "اکن"                           # adakan -> اداکن
        return "کن"
    if sfx == "an":
        if stem_rumi.endswith("a"):
            # hiatus with hamzah; alif-final stems already carry the mater
            return "ءن" if stem_jawi.endswith("ا") else "اءن"
        if stem_rumi.endswith("u"):
            return "ان"                            # perabuan -> ڤرابوان
        return "ن"                                 # buaian -> بواين
    if sfx == "i":
        if stem_jawi.endswith("و"):
            return "ءي"                            # diabui -> دابوءي
        if stem_jawi.endswith("ڽ") and stem_rumi[-1:] in VOWELS:
            return "اءي"                           # mempunyai -> ممڤوڽاءي
        return "ي"                                 # diajari -> داجري
    return PARTICLE_JAWI[sfx]


class Jawi:
    """Dictionary + morphology + rules transliterator."""

    def __init__(self, dictionary, cfg=RuleConfig()):
        # dictionary: rumi -> [variants]; canonical = first variant
        self.variants = dictionary
        self.d = {k: v[0] for k, v in dictionary.items()}
        self.cfg = cfg
        self.cache = {}

    # -- public -----------------------------------------------------------
    def transliterate(self, word):
        """Return (jawi, source); source in dict/morph/rules/mixed."""
        key = word
        if key in self.cache:
            return self.cache[key]
        w = word.lower()
        if w in self.d:
            res = (self.d[w], "dict")
        elif "-" in w:
            res = (self._hyphenated(w), "mixed")
        else:
            m = self._morph(w)
            if m is not None:
                res = (m, "morph")
            else:
                res = (rules_word(w, self.cfg), "rules")
        self.cache[key] = res
        return res

    def to_jawi(self, word):
        return self.transliterate(word)[0]

    # -- internals --------------------------------------------------------
    def _hyphenated(self, w):
        parts = w.split("-")
        if len(parts) == 2 and parts[0] == parts[1]:
            return self.to_jawi(parts[0]) + REDUP
        if len(parts) == 2 and parts[1].startswith(parts[0]) and \
                parts[1][len(parts[0]):] in ("nya", "ku", "mu"):
            # anak-anaknya -> انق٢ڽ (majority convention for particles only)
            base_j = self.to_jawi(parts[0])
            sfx = parts[1][len(parts[0]):]
            return base_j + REDUP + PARTICLE_JAWI[sfx]
        if parts[0] == "al":
            return self.to_jawi(parts[0]) + \
                "".join(self.to_jawi(p) for p in parts[1:] if p)
        # affixed reduplication: both sides spelled out (berlari-lari)
        return "-".join(self.to_jawi(p) for p in parts if p)

    def _morph(self, w):
        """Try affix stripping; return composed jawi or None."""
        if len(w) < 4:
            return None
        # candidate (base, suffixes) pairs, longest base first
        cands = []
        for s1 in ("",) + OUTER_SUFFIXES:
            if s1 and not w.endswith(s1):
                continue
            b1 = w[:len(w) - len(s1)] if s1 else w
            for s2 in ("",) + INNER_SUFFIXES:
                if s2:
                    if not b1.endswith(s2):
                        continue
                    b2 = b1[:len(b1) - len(s2)]
                    if len(b2) < 4:                # avoid spurious -i/-kan cuts
                        continue
                else:
                    b2 = b1
                if len(b2) < 3:
                    continue
                sufs = tuple(x for x in (s2, s1) if x)
                cands.append((b2, sufs))
        # longest base first; de-duplicate
        seen, ordered = set(), []
        for b, s in sorted(cands, key=lambda x: -len(x[0])):
            if (b, s) not in seen:
                seen.add((b, s))
                ordered.append((b, s))

        for base, sufs in ordered:
            stem_j = self.d.get(base)
            if stem_j is not None:
                return self._compose("", base, stem_j, sufs)
            # prefix matches: prefer the longest restored stem
            best = None
            for pr_rumi, pr_jawi, restores, drop_alif in PREFIXES:
                if not base.startswith(pr_rumi) or len(base) <= len(pr_rumi) + 1:
                        continue
                rest = base[len(pr_rumi):]
                for r in restores:
                    stem = r + rest
                    if len(stem) < 3:
                        continue
                    stem_j = self.d.get(stem)
                    if stem_j is None:
                        continue
                    score = (len(stem), r == "")
                    if best is None or score > best[0]:
                        best = (score, pr_jawi, r, drop_alif, stem, stem_j)
            if best is not None:
                _, pr_jawi, r, drop_alif, stem, stem_j = best
                adj = stem_j
                if r:
                    # assimilated initial: memukul = مم + (ڤوکول - ڤ)
                    strip = RESTORE_JAWI[r]
                    if adj.startswith(strip):
                        adj = adj[len(strip):]
                elif drop_alif and len(stem) >= 4 and stem[0] in VOWELS \
                        and adj.startswith("ا") and not adj.startswith("اء") \
                        and adj[1:2] not in "ثحخذصضطظعغة":
                    # meN-/peN- before a longer vowel stem: mengambil -> مڠمبيل
                    # (short stems and Arabic-loan stems keep the alif)
                    adj = adj[1:]
                return self._compose(pr_jawi, stem, adj, sufs)
        return None

    def _compose(self, pre_jawi, stem_rumi, stem_jawi, sufs):
        out = (pre_jawi or "") + stem_jawi
        cur_r, cur_j = stem_rumi, out
        for s in sufs:
            out += _suffix_jawi(s, cur_r, cur_j)
            cur_r += s
            cur_j = out
        return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def transliterate_text(text, tr, show_source=False):
    """Transliterate every word in a text, preserving the rest."""
    def repl(m):
        jawi, src = tr.transliterate(m.group(0))
        return f"{jawi}[{src}]" if show_source else jawi
    return re.sub(r"[A-Za-z]+(?:-[A-Za-z]+)*", repl, text)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(
        description="Transliterate Malay words from Rumi (Latin) to Jawi.")
    ap.add_argument("words", nargs="*", help="word(s) to transliterate")
    ap.add_argument("-t", "--text", action="store_true",
                    help="treat input as free text (transliterate every word)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="show rumi and lookup source alongside the jawi")
    ap.add_argument("-d", "--dict", default=CSV_PATH,
                    help="path to the rumi-jawi CSV dictionary")
    args = ap.parse_args(argv)

    tr = Jawi(load_dictionary(args.dict))

    def emit(word):
        jawi, src = tr.transliterate(word)
        if args.verbose:
            print(f"{word}\t{jawi}\t({src})")
        else:
            print(jawi)

    if args.words:
        if args.text:
            print(transliterate_text(" ".join(args.words), tr, args.verbose))
        else:
            for w in args.words:
                emit(w)
    else:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if args.text:
                print(transliterate_text(line, tr, args.verbose))
            else:
                for w in line.split():
                    emit(w)


if __name__ == "__main__":
    main(sys.argv[1:])
