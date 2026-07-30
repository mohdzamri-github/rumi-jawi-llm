"""Hybrid Rumi->Jawi: reduplication/hyphen handling + dictionary lookup + rule fallback."""
import translit

def rule_convert(w):
    """rule-only, with reduplication and hyphen handling."""
    if '-' in w:
        parts=w.split('-')
        if len(parts)==2 and parts[0]==parts[1]:      # full reduplication X-X
            return translit.convert(parts[0])+'٢'
        return '-'.join(rule_convert(p) if p else '' for p in parts)
    return translit.convert(w)

def make_hybrid(pairs):
    """build a lookup dict; return a convert() that looks up then falls back to rules."""
    lut={}
    for r,j in pairs:
        lut.setdefault(r,j)   # first spelling wins for ambiguous keys
    def convert(w):
        if w in lut: return lut[w]
        return rule_convert(w)
    return convert, lut
