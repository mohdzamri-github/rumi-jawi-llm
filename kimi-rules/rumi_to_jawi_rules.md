# Rumi-to-Jawi Transliteration Rules

Rules implemented in `rumi_to_jawi.py` and verified against
`rumi-jawi-unicode.csv` (66,000 unique words). Accuracy figures below are
measured on the full dictionary; a prediction counts as correct if it
matches **any** known Jawi variant of a word (the CSV contains ~830
homographs with multiple valid spellings).

## 1. Overview

Malay Jawi is written in a modified Arabic abjad script. Classic Jawi leaves
most short vowels implicit, but **this dictionary writes vowels far more
often than classic abjad style** — measured on the data, writing every
medial vowel is the single best simple strategy (see §3.3). Transliteration
is still consonant-centric: consonant mapping is nearly deterministic, while
vowel placement is lexically variable and is the main source of rule errors.

## 2. Consonant Mappings

### 2.1 Basic Consonants

| Rumi | Jawi | Unicode | Notes |
|------|------|---------|-------|
| b | ب | U+0628 | |
| c | چ | U+0686 | Malay "ca" sound /tʃ/ |
| d | د | U+062F | |
| f | ف | U+0641 | |
| g | ݢ | U+0762 | Jawi gaf (distinct from Arabic) |
| h | ه | U+0647 | |
| j | ج | U+062C | |
| k | ک / ق | U+06A9 / U+0642 | See §2.3 |
| l | ل | U+0644 | |
| m | م | U+0645 | |
| n | ن | U+0646 | |
| p | ڤ | U+06A4 | |
| q | ق | U+0642 | |
| r | ر | U+0631 | |
| s | س | U+0633 | |
| t | ت | U+062A | |
| v | ۏ | U+06CF | Used in loanwords |
| w | و | U+0648 | |
| x | ز | U+0632 | |
| y | ي | U+064A | |
| z | ز | U+0632 | |
| ' | ء | U+0621 | Apostrophe → hamza |

### 2.2 Digraphs (processed before single letters)

| Rumi | Jawi | Notes |
|------|------|-------|
| ng | ڠ | Most frequent digraph (~16,600 occurrences) |
| ny | ڽ | |
| sy | ش | |
| kh | خ | Arabic loans |
| gh | غ | Arabic loans |
| ch | چ | |
| sh | ش | |
| th | ث | Arabic loans |
| dh | ذ | Arabic loans |
| ph | ف | |
| au | او | Diphthong |
| ai | اي | Diphthong |
| oi | وي | |
| ee | ي | |
| oo | و | |
| ia | يا | |
| io | يو | |
| ua | وا | |
| ui | وي | |

### 2.3 The Letter K (ک vs ق)

- Word-final **k** → **ق** (qaf): matches 89% of `<vowel>k` words in the
  dictionary (ق 4,067 vs ک 481). The ک cases are mostly modern loans
  (*statistik* → ستاتيستيک).
- **k** anywhere else → **ک** (kaf).
- *anak* → انق, *akan* → اکن

## 3. Vowel Rules (measured)

### 3.1 Word-Initial Vowels

| Initial | Jawi | Dictionary evidence |
|---------|------|---------------------|
| a- | ا | 89% of 1,794 a-initial words |
| e- | اي | 77% of 599 e-initial words |
| i- | اي | 76% of 637 i-initial words |
| o- | او | 99% of 327 o-initial words |
| u- | او | 92% of 496 u-initial words |

- *ikan* → ايکن, *emas* → ايماس, *udang* → اودڠ, *olah* → اوله, *aba* → اب

### 3.2 Final Vowels

| Final Vowel | Jawi | Examples |
|-------------|------|----------|
| -i, -e | ـي | *baki* → باقي, *sate* → ساتي |
| -u, -o | ـو | *guru* → ݢورو, *bolo* → بولو |
| -a | omitted | *rumah* → رومه, *makan* → ماکن |

Final -a is lexically variable (61% omitted, 39% written in the data); the
rule omits it, except when it arrives via the *ia/ua* digraphs, where the
alif is part of the digraph (*dunia* → دونيا).

### 3.3 Medial Vowels — written, not omitted

**This dictionary writes most medial vowels.** Measured rules-only accuracy
of candidate strategies on 15,000 random words:

| Strategy | Accuracy |
|----------|----------|
| Write all medial vowels (a→ا, i/e→ي, u/o→و) | **30.3%** |
| Write only open-syllable vowels | 22.5% |
| Write only first-syllable vowel | 22.4% |
| Omit all medial vowels (classic abjad) | 15.1% |

The engine therefore writes every medial vowel. Residual vowel errors are
lexically arbitrary (e.g. *perambut* → ڤرمبوت drops the first vowel,
*makan* → ماکن keeps it) and cannot be captured by position rules — this is
the single largest error class (~80% of remaining rule errors) and the main
reason a dictionary layer is essential.

## 4. Prefixes (Imbuhan Awalan)

### 4.1 Assimilation table (as implemented)

| Prefix | Jawi | | Prefix | Jawi |
|--------|------|-|--------|------|
| memper- | ممڤر | | pel- | ڤل |
| mempel- | ممڤل | | per- | ڤر |
| diper- | دڤر | | pe- | ڤ |
| berke- | برک | | ber- | بر |
| keter- | کتر | | ter- | تر |
| sepe- | سڤ | | di- | د |
| meng- | مڠ | | ke- | ک |
| meny- | مڽ | | se- | س |
| mem- | مم | | men- | من |
| mel- | مل | | me- | م |
| peng- | ڤڠ | | pem- | ڤم |
| peny- | ڤڽ | | pen- | ڤن |

Longest match wins; a prefix is only stripped when the remainder looks like
a real root (≥ 3 letters, or ≥ 2 starting with a consonant) and the word is
not in a list of ~500 false-prefix roots (*kedai*, *perang*, *seminar*,
*terima*, …).

### 4.2 Hamza after di- / ke- before vowel-initial roots

- *di- + arah* → *diarahkan* → دأرهکن
- *ke- + absah* → *keabsahan* → کأبسهن

The initial alif of the root is replaced by أ. Other prefixes do **not**
take hamza (*mengabadikan* → مڠاباديکن).

## 5. Suffixes (Imbuhan Akhiran)

| Suffix | Jawi | Notes |
|--------|------|-------|
| -kan | کن | Causative/benefactive |
| -an | ن | See §5.1 for the hamza rule |
| -i | ي | Locative/benefactive |
| -lah | له | Emphatic particle |
| -kah | که | Question particle |
| -nya | ڽ | **Not** ڽا: 3,506 vs 12 in the data |
| -wan | ون | Agentive (masculine) |
| -wati | واتي | Agentive (feminine) |
| -kannya | کنڽ | |
| -inya | يڽ | |

### 5.1 Hamza at the -an boundary (root-final a + -an)

A root ending in **-a** followed by **-an** is written **اءن** — this holds
for 702/702 such words in the dictionary:

- *pekerjaan* → ڤکرجاءن
- *persediaan* → ڤرسدياءن

The root-final 'a' becomes the hamza's seat (written ا, or kept when it
already exists from an ia/ua digraph). Note the same does **not** apply to
*-i* (*-ai* words carry hamza only 16% of the time, e.g. *nilai* → نيلاي).

## 6. Reduplication (Kata Ganda)

- **Equal parts** (`X-X`) → base + **٢** in ~99.7% of dictionary entries,
  regardless of affixes on the base:
  - *aba-aba* → اب٢, *makan-makan* → ماکن٢, *sebelah-sebelah* → سبله٢
- **Unequal / partial reduplication** → hyphen, parts transliterated
  separately:
  - *berabad-abad* → برابد-ابد, *berlebih-lebih* → برلبيه-لبيه

## 7. Arabic Loanwords

A large share of Malay vocabulary retains Arabic spelling and breaks the
phonetic rules (ع، غ، خ، ح، ق، ث، ذ، ص، ض، ط، ظ، ة):

| Rumi | Regular rule would give | Actual Jawi |
|------|-------------------------|-------------|
| adil | اديل | عاديل |
| akal | اکل | عقل |
| ilmu | ايلمو | علم |
| taat | تاات | طاعة |

These are not recoverable by rules and are the second-largest error class.

## 8. Summary Algorithm

```
1. Dictionary lookup first (primary; handles loans and vowel idiosyncrasy)
2. Rule fallback for unknown words:
   a. Equal-part reduplication  → base + ٢;  unequal → hyphenate parts
   b. Strip known prefix (longest match, false-prefix root guard)
   c. Strip known suffix
   d. di-/ke- + vowel-initial root        → prefix + أ + root
   e. Transliterate root: digraphs first, then consonants;
      initial vowel  → ا / اي / او (a, ie, uo)
      medial vowels  → all written (ا / ي / و)
      final vowel    → ي (i/e), و (u/o), -a omitted
      word-final k   → ق
   f. Root-final a + -an → root + اء + ن
```

## 9. Measured Accuracy

| Mode | Accuracy | Method |
|------|----------|--------|
| Dictionary + rules | **100.00%** | 1,000 random unique words |
| Rules only | **32.16%** | All 66,000 unique words |

Evaluation is duplicate-aware: matching any listed variant of a word counts
as correct. Rules-only errors break down roughly as: ~80% lexically
arbitrary vowel presence, ~6% consonant-level mismatches, ~6% hamza
contexts, ~4% Arabic-loan letters, ~2% reduplication form, ~1% final k.
