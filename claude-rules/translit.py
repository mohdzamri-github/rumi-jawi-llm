"""Rumi -> Jawi rule engine (final ruleset). See plan.md "FINAL RULESET" for the derivation.

Pure-rule exact-match generalization: ~65.4% on unseen words (test split of
rumi-jawi-unicode.csv). Use hybrid.py (dict + this engine) for the ~98.8% practical
converter.

The residual ~35% is dominated by ambiguities a Rumi-only rule cannot resolve:
  * pepet vs taling 'e' and elided schwa 'a' (written or dropped — not marked in Rumi)
  * Arabic-etymology consonants ح ع ص ض ط ظ ث ذ and vowel signs, which depend on the
    word's origin, not its Rumi spelling.
These are exactly what the dictionary layer in hybrid.py covers."""

DIG={'ng':'ڠ','ny':'ڽ','kh':'خ','gh':'غ','sy':'ش'}
CONS={'b':'ب','t':'ت','d':'د','r':'ر','l':'ل','n':'ن','m':'م','h':'ه',
      'g':'ݢ','p':'ڤ','c':'چ','j':'ج','s':'س','f':'ف','z':'ز','w':'و',
      'y':'ي','v':'ۏ','q':'ق'}
VOW='aeiou'

def tokenize(w):
    i=0;n=len(w);out=[]
    while i<n:
        p=w[i:i+2]
        if p in DIG: out.append(('C',p));i+=2;continue
        ch=w[i]
        if ch in VOW: out.append(('V',ch));i+=1;continue
        out.append(('C',ch));i+=1
    return out

def syll(toks,idx):
    """classify vowel syllable: final / open / closed / hiatus"""
    if idx==len(toks)-1: return 'final'
    if toks[idx+1][0]=='V': return 'hiatus'
    # next is C
    if idx+2<len(toks) and toks[idx+2][0]=='V': return 'open'
    return 'closed'

def convert(w):
    # di- passive prefix: 'i' is dropped -> just د + converted root.
    # Derivation note: di/ke/se + vowel-root is written with a PLAIN alef, not a
    # hamza-alef أ (in the data di+V -> ا 515x vs أ 0x). An earlier version added a
    # hamza onset here; measuring against rumi-jawi-unicode.csv showed that was wrong.
    if w.startswith('di') and len(w)>3:
        out = 'د'+_convert_root(w[2:])
    # ke- / se- proclitics + vowel-root: same plain-alef junction
    elif w.startswith('ke') and len(w)>3 and w[2] in VOW:
        out = 'ک'+_convert_root(w[2:])
    elif w.startswith('se') and len(w)>3 and w[2] in VOW:
        out = 'س'+_convert_root(w[2:])
    else:
        out = _convert_root(w)
    # -isme / -sme loanword ending: final schwa is written as alef maqsura ى,
    # not ye ي (data: -sme -> ى 217x vs ي 1x).
    if w.endswith('sme') and out.endswith('ي'):
        out = out[:-1]+'ى'
    return out

def _convert_root(w):
    toks=tokenize(w); out=[]
    nvow=sum(1 for t,ch in toks if t=='V')
    for idx,(t,ch) in enumerate(toks):
        initial=(idx==0)
        if t=='C':
            if ch in DIG: out.append(DIG[ch])
            elif ch=='k':
                out.append('ق' if idx==len(toks)-1 else 'ک')
            elif ch in CONS: out.append(CONS[ch])
            # x: word-initial -> ز (xantina->زنتينا); elsewhere -> کس. Note the ک is
            # U+06A9 keheh (as used throughout the data), NOT U+0643 arabic kaf.
            elif ch=='x': out.append('ز' if initial else 'کس')
            # else skip
            continue
        # vowel
        s=syll(toks,idx)
        prev_vowel = idx>0 and toks[idx-1][0]=='V'  # hiatus (preceded by a vowel)
        prev_ch = toks[idx-1][1] if idx>0 else ''
        if ch=='a':
            if initial: out.append('ا')
            elif prev_ch=='a': out.append('ء')    # a-after-a -> hamza
            elif prev_vowel: out.append('ا')      # other hiatus -> alef
            elif s=='final':
                if nvow==2: out.append('ا')        # bisyllabic final -a -> written
                # else dropped
            elif s in ('open','hiatus'): out.append('ا')
            # medial closed -> drop
        elif ch=='i':
            if prev_ch in 'uo': out.append('ءي')   # u/o + i junction -> hamza-yeh
            else: out.append('اي' if initial else 'ي')
        elif ch in 'uo':
            out.append('او' if initial else 'و')
        elif ch=='e':
            if initial: out.append('ا')
            elif prev_vowel: out.append('ي')       # hiatus e -> ye
            elif s=='final': out.append('ي')
            # else pepet -> drop
    return ''.join(out)
