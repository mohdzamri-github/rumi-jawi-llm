# Rumi → Jawi Transliteration Rules

Rules for transliterating Malay words from Latin (Rumi) spelling to Jawi
(Arabic-based) spelling, derived from `rumi-jawi-unicode.csv` and implemented
in `jawi.py`. Arabic-script code points follow the corpus conventions
(`g`=ݢ U+0762, `k`=ک U+06A9, `p`=ڤ U+06A4, `ng`=ڠ U+06A0, `ny`=ڽ U+06BD,
`v`=ۏ U+06CF).

Resolution order in the engine:

1. **Dictionary lookup** (all entries from the CSV; first-listed spelling is
   canonical). This covers Arabic/Sanskrit loanwords with etymological
   spelling (`selamat`→`سلامت`, `akidah`→`عقيدة`) and defective spellings of
   common words (`kata`→`کات`, `ada`→`اد`, `suka`→`سوک`).
2. **Morphological decomposition** (affix stripping + dictionary stem).
3. **Phonemic rules** below (fallback for unknown stems).

---

## 1. Consonant mapping

| Rumi | Jawi | Rumi | Jawi | Rumi | Jawi |
|------|------|------|------|------|------|
| b | ب | n | ن | w | و |
| c | چ | p | ڤ | x | کس |
| d | د | q | ق | y | ي |
| f | ف | r | ر | z | ز |
| g | ݢ | s | س | ng | ڠ |
| h | ه | t | ت | ny | ڽ |
| j | ج | v | ۏ | sy | ش |
| k | ک | l | ل | kh | خ |
| m | م | | | gh | غ |

Notes:

- Digraphs (`ng ny sy kh gh`) are tokenized as single units first.
- Word-initial `x` reads /z/: `xenon`→`زينون`; elsewhere `x`→`کس`
  (`taksi`→`تکسي`).
- Letters ح ص ض ط ظ ع غ ة ث ذ appear **only in Arabic loanwords** and are not
  predictable — they require the dictionary.

### Final and coda -k

- Word-final `-k` → `ق`: `tidak`→`تيدق`, `anak`→`انق`, `baik`→`باءيق`.
- `k` before `s` (coda) → `ق`: `saksi`→`سقسي`, `beksa`→`بيقسا`.
- `k` in foreign onset clusters stays `ک`: `konstruksi`→`کونستروکسي`,
  `eksploitasi`→`ايکسڤلوءيتاسي` (detected by the presence of another
  consonant cluster in the word).

---

## 2. Vowels

| Vowel | Word-initial | Medial | Final |
|-------|-------------|--------|-------|
| a | ا | ا in open syllables, dropped in closed ones | ا (see exceptions) |
| i | اي | ي | ي |
| u | او | و | و |
| e | اي | dropped (pepet) | ى |
| o | او | و | و |

### The vowel `a`

- **Initial**: always `ا` (`abah`→`ابه`, `anak`→`انق`).
- **Open syllable** (followed by one consonant + vowel): written `ا`
  (`abadi`→`ابادي`, `sawah`→`ساوه`).
- **Closed syllable** (followed by two consonants, or one consonant + word
  end): **dropped** (`bapak`→`باڤق`, `tengah`→`تڠه`, `sekolah`→`سکوله`).
- **Final `-a`**: `ا` by default (`gula`→`ڬولا`), but dropped after:
  - `ny` → the digraph letter alone: `baginya`→`باݢيڽ`
  - `k`/`g` (majority convention): `suka`→`سوک`, `aneka`→`انيک`
  - `y` (majority convention): `saya`→`ساي`, `bahaya`→`بهاي`

### The vowel `e` (pepet vs taling)

- Default is **pepet**: medial `e` is unwritten (`tengah`→`تڠه`,
  `sejarah`→`سجاره`, `kerja`→`کرجا`).
- Taling `e` (/e/) is written `ي` (`bebas`→`بيبس`, `mesin`→`ميسين`) but is
  lexically determined — the dictionary resolves it.
- Initial `e` → `اي` (majority): `eja`→`ايجا`, `ekor`→`ايکور`
  (exceptions like `emas`→`امس` come from the dictionary).
- Final `-e` → `ى`: `absurdisme`→`ابسورديسمى` (exceptions like
  `kafe`→`کافي` come from the dictionary).

---

## 3. Vowel sequences (diphthongs and hiatus)

Diphthongs `ai`/`au`:

- Word-final: `اي` / `او` — `sungai`→`سوڠاي`, `pulau`→`ڤولاو`.
- Before a consonant (or word-initial): `اءي` / `اءو` — `baik`→`باءيق`,
  `laut`→`لاءوت`, `air`→`اءير`, `aura`→`اءورا`.

Hiatus (other vowel pairs) — hamzah insertion:

| Pair | Jawi | Example |
|------|------|---------|
| aa | اء + (a by syllable rule) | `keadaan`→`کاداءن`, `cubaan`→`چوباءن` |
| ui | وءي | `kuih`→`کوءيه`, `diabui`→`دابوءي` |
| uu, oo | وءو | `koordinasi`→`کوءورديناسي` |
| ei | يئي | `ateis`→`اتيئيس` |
| ie | يئ | `ampere`→`امڤيئر` |
| ii, ee | يئي | |
| oi (before consonant) | وءي | `antropoid`→`انتروڤوءيد` |
| ae (medial) | اءي | `daerah`→`داءيره` |

Hamzah form: `ئ` (on ya-chair) when the preceding mater is `ي`, standalone
`ء` otherwise.

Smooth hiatus — **no** hamzah:

| Pair | Jawi | Example |
|------|------|---------|
| ia | يا | `niaga`→`نياݢ` (before final `-h`: يئ — `tahniah`→`تهنيئه`) |
| io, iu, eo, eu | يو | `radio`→`راديو`, `tiub`→`تيوب` |
| ua, oa | وا | `bual`→`بوال`, `proaktif`→`ڤرواکتيف` |
| oi (word-final) | وي | `amboi`→`امبوي` |
| ae (initial) | اي | `aerob`→`ايروب` |
| ea | e dropped + ا | `seakan`→`ساکن`; final `-ea` → يا (`alinea`→`الينيا`) |

---

## 4. Reduplication (hyphenated words)

- Identical parts: base + `٢` — `anak-anak`→`انق٢`, `kupu-kupu`→`کوڤو٢`.
- Bare stem + particle suffix: base + `٢` + suffix —
  `anak-anaknya`→`انق٢ڽ`, `kata-kataku`→`کات٢کو`.
- Affixed reduplication (parts differ): both sides spelled out, joined by
  hyphen — `berlari-lari`→`برلاري-لاري`, `berabad-abad`→`برابد-ابد`,
  `kekanak-kanakan`→`ککنق-کانقن`.
- Arabic article words: joined without hyphen — `al-ijarah`→`الاجارة`.

---

## 5. Morphology (affixes)

When a word is not in the dictionary, productive affixes are stripped, the
stem is looked up, and the Jawi affixes are re-attached.

### Prefixes

| Rumi | Jawi | Assimilation handled |
|------|------|---------------------|
| memper- | ممڤر | |
| diper- | دڤر | |
| meng-, menge- | مڠ | stem-initial `k` drops: `mengira`→`مڠيرا` |
| mem- | مم | stem-initial `p` drops: `memukul`→`مموکول` |
| men- | من | stem-initial `t` drops: `menari`→`مناري` |
| meny- | مڽ | stem-initial `s`/`ny` drops: `menyapu`→`مڽاڤو`, `menyanyi`→`مڽاڽي` |
| peng-, pem-, pen-, peny- | ڤڠ ڤم ڤن ڤڽ | same as meN- |
| ber- | بر | stem-initial `r` drops: `berenang`→`برنڠ` |
| ter-, per-, pel-, di-, ke-, se-, me-, pe-, be- | تر ڤر ڤل د ک س م ڤ ب | plain concatenation |

- **Vowel-initial stems after meN-/peN-**: the stem's initial alif drops for
  stems of 4+ letters (`mengambil`→`مڠمبيل`), but is kept for short stems
  (`mengair`→`مڠاءير`) and for Arabic-loan stems (`pengakhiran`→`ڤڠاخيرن`).
- Assimilated initials: when Rumi drops the stem's first consonant, the
  corresponding Jawi letter is dropped from the stem instead of doubling it
  (`mem`+`pukul` → `مم`+`وکول`, not `ممڤوکول`).
- Candidate parses are scored by longest restored stem
  (`memakan` = me+`makan`→`مماکن`, not mem+`akan`).

### Suffixes

| Suffix | Jawi | Condition / example |
|--------|------|---------------------|
| -kan | کن | default; after any mater-final stem: `bagaikan`→`باݢايکن`, `mengacarakan`→`مڠاچاراکن` |
| -kan | اکن | stem Rumi ends in a vowel but its Jawi ends in a consonant (defective): `adakan`→`اداکن`, `katakan`→`کاتاکن`; also after `ڽ`: `bertanyakan`→`برتاڽاکن` |
| -an | ن | default: `pukulan`→`ڤوقولن`, `buaian`→`بواين` |
| -an | اءن / ءن | stem ends in `-a` (hamzah hiatus): `keadaan`→`کاداءن`, `jembaan`→`جمباءن` |
| -an | ان | stem ends in `-u`: `perabuan`→`ڤرابوان` |
| -i | ي | default: `diajari`→`داجري` |
| -i | ءي | stem Jawi ends in `و`: `diabui`→`دابوءي` |
| -i | اءي | stem ends in `-nya` (Jawi `ڽ`): `mempunyai`→`ممڤوڽاءي` |
| -nya | ڽ | `baginya`→`باݢيڽ` |
| -ku / -mu | کو / مو | |
| -lah / -kah / -tah | له / که / ته | `sudahlah`→`سودهله` |
| -pun | ڤون | |

---

## 6. Known limitations (dictionary territory)

These are not rule-predictable and are resolved by the dictionary:

- Arabic/Sanskrit etymological letters: ح ص ض ط ظ ع غ ة ث ذ
  (`hasil`→`حاصل`, `adil`→`عادل`).
- Taling `e` vs pepet `e` mid-word (`bebas`→`بيبس` vs `belas`→`بلس`).
- Defective common words (`kata`→`کات`, `ini`→`اين`, `pada`→`ڤد`).
- Lexical alif keep/drop exceptions (`bandar`→`باندر` vs `bandit`→`بنديت`).
- Loanword final `-k` keeping `ک` (`saintifik`→`ساءينتيفيک`).
