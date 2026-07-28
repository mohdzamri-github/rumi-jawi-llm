#!/usr/bin/env python3
"""
Rumi-to-Jawi Transliterator (Updated)

This version loads the full CSV dictionary as its primary lookup mechanism,
then falls back to improved rule-based transliteration for unknown words.

Key improvements:
1. Full CSV dictionary loaded at import time for exact matches
2. Smarter prefix stripping with false-prefix detection
3. Better vowel handling (writes medial vowels by default)
4. Expanded loanword coverage
"""

import csv
import os
import random
from typing import Dict, List, Optional, Tuple

# =============================================================================
# DICTIONARY LOADER
# =============================================================================

CSV_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        "rumi-jawi-unicode.csv")

class JawiDictionary:
    """In-memory lookup table loaded from CSV.

    Keeps ALL Jawi variants for each Rumi word: the CSV contains hundreds
    of homographs (same Rumi, multiple valid Jawi spellings).
    """

    def __init__(self, path: str = CSV_PATH):
        self._exact: Dict[str, List[str]] = {}
        self._lower: Dict[str, List[str]] = {}
        self._load(path)

    def _load(self, path: str) -> None:
        if not os.path.isfile(path):
            path = "rumi-jawi-unicode.csv"
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    rumi = row[0].strip()
                    jawi = row[1].strip()
                    variants = self._exact.setdefault(rumi, [])
                    if jawi not in variants:
                        variants.append(jawi)
        for rumi, jawis in self._exact.items():
            existing = self._lower.setdefault(rumi.lower(), [])
            for j in jawis:
                if j not in existing:
                    existing.append(j)

    def lookup_variants(self, word: str) -> List[str]:
        """All known Jawi spellings for a word (exact, then case-folded)."""
        return self._exact.get(word) or self._lower.get(word.lower(), [])

    def lookup(self, word: str) -> Optional[str]:
        variants = self.lookup_variants(word)
        return variants[0] if variants else None

    def stats(self) -> str:
        total = sum(len(v) for v in self._exact.values())
        return f"{len(self._exact)} entries, {total} variants"


# Global dictionary instance (loaded once at import)
_DICTIONARY = JawiDictionary()


# =============================================================================
# RULE-BASED FALLBACK ENGINE
# =============================================================================

# Digraphs must be processed before single letters
DIGRAPHS = {
    'ng': 'ڠ', 'ny': 'ڽ', 'sy': 'ش', 'kh': 'خ', 'gh': 'غ',
    'ch': 'چ', 'sh': 'ش', 'th': 'ث', 'dh': 'ذ', 'bh': 'بھ',
    'ph': 'ف', 'au': 'او', 'ai': 'اي', 'oi': 'وي',
    'ee': 'ي', 'oo': 'و', 'ia': 'يا', 'io': 'يو', 'ua': 'وا', 'ui': 'وي',
}

CONSONANTS = {
    'b': 'ب', 'c': 'چ', 'd': 'د', 'f': 'ف', 'g': 'ݢ', 'h': 'ه',
    'j': 'ج', 'k': 'ک', 'l': 'ل', 'm': 'م', 'n': 'ن', 'p': 'ڤ',
    'q': 'ق', 'r': 'ر', 's': 'س', 't': 'ت', 'v': 'ۏ', 'w': 'و',
    'x': 'ز', 'y': 'ي', 'z': 'ز', "'": 'ء',
}

VOWELS = set('aiueo')

PREFIXES = [
    ('memper', 'ممڤر'), ('mempel', 'ممڤل'), ('diper', 'دڤر'),
    ('berke', 'برک'), ('keter', 'کتر'), ('sepe', 'سڤ'),
    ('meng', 'مڠ'), ('meny', 'مڽ'), ('mem', 'مم'), ('men', 'من'),
    ('mel', 'مل'), ('me', 'م'), ('peng', 'ڤڠ'), ('peny', 'ڤڽ'),
    ('pem', 'ڤم'), ('pen', 'ڤن'), ('pel', 'ڤل'), ('per', 'ڤر'),
    ('pe', 'ڤ'), ('ber', 'بر'), ('ter', 'تر'), ('di', 'د'),
    ('ke', 'ک'), ('se', 'س'),
]

SUFFIXES = [
    ('kannya', 'کنڽ'), ('inya', 'يڽ'), ('kan', 'کن'),
    ('lah', 'له'), ('kah', 'که'), ('nya', 'ڽ'),
    ('wan', 'ون'), ('wati', 'واتي'), ('an', 'ن'), ('i', 'ي'),
]

# Roots that start with strings that look like prefixes but aren't
# These are actual root words, not prefixed forms
FALSE_PREFIX_ROOTS = frozenset([
    # ber- roots
    'ber', 'bera', 'berabe', 'berabu', 'berada', 'beradu', 'beraga', 'beragi',
    'berahi', 'berai', 'berair', 'berais', 'berak', 'berakah', 'berang', 'berani',
    'beras', 'berat', 'berau', 'berayi',
    # ter- roots
    'ter', 'tera', 'teraan', 'terada', 'terai', 'teraju', 'terak', 'teraku',
    'teral', 'terala', 'terali', 'teran', 'terang', 'terap', 'terapi', 'teras',
    'terasa', 'teratai', 'teratak', 'terau', 'terawang', 'terbang', 'teri', 'terik',
    'terima', 'terin', 'teritip', 'terjerat', 'terjun', 'terka', 'terkam', 'terkop',
    'teror', 'terpa', 'tertib', 'teru', 'terubuk', 'terucuk', 'teruna', 'terup',
    'terus',
    # di- roots (common ones)
    'di', 'dia', 'diah', 'diak', 'diam', 'dian', 'diana', 'diang', 'diar',
    'dias', 'diau', 'diabetes', 'diploma', 'diet',
    # ke- roots
    'ke', 'kea', 'keb', 'keba', 'kebab', 'kebah', 'kebak', 'kebal', 'kebam',
    'keban', 'kebas', 'kebat', 'kebel', 'kebil', 'kebuk', 'kebun', 'kebur',
    'kebut', 'kecah', 'kecai', 'kecak', 'kecal', 'kecam', 'kecan', 'kecap',
    'kecar', 'kecas', 'kecat', 'kecek', 'kecil', 'kecip', 'kecit', 'kecoh',
    'kecundang', 'kedah', 'kedai', 'kedak', 'kedal', 'kedam', 'kedan', 'kedap',
    'kedau', 'keding', 'kedut', 'kehel', 'kehil', 'kek', 'keka', 'kekah',
    'kekal', 'kekam', 'kekan', 'kekar', 'kekau', 'kekel', 'kekencing', 'kekik',
    'kekol', 'keku', 'kelah', 'kelai', 'kelak', 'kelam', 'kelan', 'kelap',
    'kelar', 'kelas', 'kelat', 'kelebih', 'kelebir', 'kelebu', 'kelebut', 'kelempong',
    'kelengkeng', 'kelepai', 'kelepak', 'kelepat', 'kelepik', 'kelepir', 'kelepit',
    'kelesa', 'keletah', 'keletak', 'keletuk', 'keletup', 'keli', 'kelian',
    'keliar', 'kelik', 'kelim', 'kelimpang', 'keling', 'kelip', 'kelir', 'kelis',
    'kelit', 'keliu', 'kelok', 'kelompong', 'kelompuk', 'kelong', 'kelonong',
    'kelopak', 'kelor', 'kelosok', 'kelotok', 'kelu', 'kelua', 'keluak', 'keluang',
    'keluar', 'keluarga', 'kelubung', 'kelui', 'keluk', 'keluli', 'kelumit',
    'kelumun', 'kelun', 'kelupas', 'kelupur', 'keluri', 'keluru', 'kelusuh',
    'kem', 'kema', 'kemah', 'kemai', 'kemal', 'keman', 'kemap', 'kemas',
    'kemat', 'kembu', 'kembur', 'kembut', 'kemeja', 'kemek', 'kemel', 'kemesan',
    'kemih', 'kemik', 'kemis', 'kemit', 'kempa', 'kempis', 'kempit', 'kemu',
    'kemudi', 'kemut', 'kena', 'kenal', 'kenan', 'kenap', 'kencang', 'kencing',
    'kencit', 'kendana', 'kendang', 'kendati', 'kendong', 'kendur', 'kene',
    'kening', 'kenit', 'kenyal', 'kenyut', 'kepai', 'kepak', 'kepal', 'kepam',
    'kepan', 'kepar', 'kepas', 'kepat', 'kepau', 'kepek', 'kepel', 'kepen',
    'keper', 'kepet', 'kepi', 'kepial', 'kepik', 'kepil', 'keping', 'kepit',
    'kepong', 'kepot', 'kepu', 'kepuk', 'kepul', 'kerah', 'kerai', 'kerak',
    'keral', 'keram', 'keran', 'kerap', 'keras', 'kerat', 'kerau', 'kere',
    'kerek', 'keren', 'kereng', 'keret', 'kereta', 'keri', 'keriang', 'keriap',
    'keriat', 'kerih', 'kerik', 'keril', 'kering', 'kerip', 'keris', 'kerit',
    'keron', 'kerong', 'kerongkong', 'keronjong', 'keropak', 'keropok', 'kerosi',
    'kerosong', 'kerpang', 'kerpas', 'kerpuk', 'kertak', 'kertang', 'kertap',
    'kertas', 'kertuk', 'kertup', 'keruh', 'keruk', 'kerul', 'kerumit', 'kerumun',
    'kerun', 'kerup', 'kerut', 'kesah', 'kesak', 'kesal', 'kesan', 'kesat',
    'kese', 'kesek', 'kesel', 'keset', 'kesi', 'kesik', 'kesip', 'kesit',
    'kesot', 'keta', 'ketah', 'ketak', 'ketal', 'ketam', 'ketan', 'ketap',
    'ketar', 'ketat', 'ketau', 'kete', 'ketek', 'ketel', 'ketem', 'keten',
    'keter', 'keti', 'ketik', 'ketil', 'ketip', 'ketiak', 'ketipung', 'ketis',
    'keto', 'ketong', 'ketor', 'ketua', 'ketuat', 'ketuh', 'ketuk', 'ketul',
    'ketum', 'ketun', 'ketup', 'kepong',
    # se- roots
    'se', 'seba', 'sebab', 'sebai', 'sebak', 'sebal', 'sebam', 'seban',
    'sebar', 'sebat', 'sebau', 'sebih', 'sebik', 'sebit', 'sebu', 'sebuk',
    'sebum', 'sebun', 'sedak', 'sedang', 'sedap', 'sedat', 'sedi', 'sedih',
    'sedot', 'sedu', 'segak', 'segan', 'segar', 'sehat', 'sejuk', 'sekat',
    'sekoi', 'sela', 'selai', 'selak', 'selam', 'selan', 'selap', 'selar',
    'selas', 'selat', 'seleh', 'selek', 'selep', 'seler', 'seles', 'seli',
    'selip', 'selir', 'selit', 'selok', 'selom', 'selon', 'selop', 'selor',
    'selot', 'selu', 'sema', 'semah', 'semai', 'semak', 'semal', 'seman',
    'semap', 'semar', 'semat', 'sembai', 'sembak', 'sembal', 'sembam', 'semban',
    'sembang', 'sembap', 'sembar', 'sembat', 'sembe', 'sembil', 'sembu',
    'sembul', 'sembun', 'sembur', 'semeh', 'semek', 'semel', 'semen', 'semer',
    'semet', 'semi', 'semir', 'sempal', 'sempang', 'sempat', 'sempel',
    'sempil', 'sempit', 'sempon', 'sempuh', 'sempuk', 'sempul', 'sempur',
    'senak', 'senam', 'senang', 'senap', 'senar', 'senat', 'senda', 'sendai',
    'sendal', 'sendam', 'sendat', 'sendi', 'sendu', 'sengap', 'sengar', 'sengat',
    'senget', 'sengih', 'sengit', 'senguk', 'sengut', 'seni', 'senja', 'senjak',
    'senta', 'sentak', 'sental', 'sentap', 'sentil', 'sentuh', 'senum', 'sepa',
    'sepah', 'sepai', 'sepak', 'sepal', 'sepam', 'sepan', 'separ', 'sepas',
    'sepat', 'sepe', 'sepek', 'sepel', 'sepen', 'sepet', 'sepi', 'sepih',
    'sepit', 'sepo', 'sepoh', 'sepok', 'sepon', 'sepos', 'sepu', 'sepuk',
    'sepul', 'sepur', 'sera', 'serah', 'serai', 'serak', 'seram', 'seran',
    'serap', 'serat', 'serau', 'sere', 'sereh', 'serek', 'serel', 'serem',
    'seret', 'seri', 'seriap', 'sering', 'serit', 'sero', 'serobok', 'serong',
    'serot', 'seru', 'seruh', 'seruk', 'serun', 'serup', 'serut', 'sesah',
    'sesak', 'sesal', 'sesam', 'sesan', 'sesap', 'sesat', 'seta', 'setah',
    'setai', 'setak', 'setal', 'setan', 'setap', 'setar', 'setas', 'setat',
    'sete', 'setek', 'setel', 'setem', 'seten', 'seter', 'seti', 'setia',
    'setik', 'setil', 'setin', 'setip', 'setir', 'seto', 'seton', 'setor',
    'setu', 'setubuh', 'setuh', 'setuk', 'setum', 'setun', 'setup', 'sewa',
    'sewal', 'sewat', 'sewat', 'sewot',
    # me- roots
    'me', 'mecak', 'mecia', 'mecis', 'medak', 'medal', 'medan', 'media',
    'medil', 'medit', 'mega', 'megah', 'megak', 'megan', 'megap', 'megar',
    'meh', 'meja', 'mejam', 'mejan', 'mek', 'mekah', 'mekan', 'mel', 'mela',
    'melabur', 'melah', 'melai', 'melak', 'melam', 'melan', 'melar', 'melas',
    'mele', 'melebih', 'melebu', 'meleis', 'melek', 'melekat', 'meleleh',
    'melelu', 'melempai', 'melempap', 'melempit', 'melengkung', 'melengkup',
    'melengset', 'melentik', 'melenting', 'melentur', 'melepai', 'melepap',
    'melepas', 'melepat', 'melepuk', 'meleset', 'meletak', 'meletup', 'melewa',
    'meli', 'meliang', 'meliar', 'melibat', 'melicik', 'melidi', 'meligat',
    'meligu', 'melik', 'melilit', 'melimpah', 'melimpit', 'meling', 'melingkup',
    'melintang', 'melintas', 'melinting', 'melintir', 'melipat', 'melipur',
    'melis', 'melit', 'meliuk', 'melod', 'melok', 'melon', 'melondong',
    'melonjak', 'melonjong', 'melontar', 'melopong', 'melor', 'melorot',
    'meluk', 'melun', 'melup', 'melut', 'mem', 'memah', 'memak', 'memal',
    'meman', 'memas', 'memat', 'memb', 'membez', 'memo', 'memu', 'men',
    'mena', 'menai', 'menak', 'menal', 'menam', 'menan', 'menang', 'menap',
    'menar', 'menat', 'mencak', 'mencang', 'mencar', 'mencek', 'mencel',
    'mencer', 'mencit', 'mencong', 'mencu', 'mendak', 'mendang', 'mendap',
    'mendar', 'mendel', 'mendem', 'menden', 'mender', 'mendi', 'mendoa',
    'mendok', 'mendon', 'mendu', 'mendung', 'mendus', 'meng', 'menga',
    'mengai', 'mengal', 'mengam', 'mengan', 'mengap', 'mengar', 'mengas',
    'mengat', 'menge', 'mengel', 'mengen', 'menges', 'mengi', 'mengil',
    'mengin', 'mengir', 'mengis', 'mengit', 'mengo', 'mengok', 'mengon',
    'mengot', 'mengsan', 'mengu', 'menguk', 'mengun', 'mengut', 'meni',
    'menil', 'menin', 'menir', 'menit', 'menj', 'menja', 'menjah', 'menjaj',
    'menjal', 'menjam', 'menjan', 'menjap', 'menjar', 'menjat', 'menjeng',
    'menjir', 'menju', 'menka', 'menoh', 'menok', 'menon', 'menop', 'menta',
    'mente', 'mentel', 'menter', 'menti', 'mento', 'mentok', 'mentol',
    'mentul', 'menu', 'meny', 'menya', 'menyal', 'menyam', 'menyan', 'menyap',
    'menyar', 'menyat', 'menye', 'menyel', 'menyer', 'menyes', 'menyet',
    'menyi', 'menyil', 'menyir', 'menyo', 'menyor', 'menuk', 'menyus',
    'menyu', 'meo', 'mer', 'mera', 'merah', 'merai', 'merak', 'meral',
    'meram', 'meran', 'merang', 'merap', 'meras', 'merat', 'merau', 'mere',
    'merek', 'merel', 'merem', 'meren', 'mereng', 'meres', 'meret', 'meri',
    'meriang', 'meriap', 'merih', 'merik', 'meril', 'mering', 'meris',
    'merit', 'meriu', 'merna', 'merok', 'meron', 'meros', 'meru', 'meruh',
    'meruk', 'merum', 'merun', 'merup', 'merut', 'mes', 'mesa', 'mesah',
    'mesai', 'mesak', 'mesal', 'mesan', 'mesap', 'mesar', 'mesat', 'mese',
    'mesek', 'mesel', 'mesen', 'meser', 'meset', 'mesh', 'mesi', 'mesin',
    'mesir', 'mesit', 'meso', 'meson', 'mesra', 'mesu', 'mesui', 'mesut',
    'meta', 'metah', 'metai', 'metal', 'metan', 'metap', 'metas', 'mete',
    'metek', 'metel', 'meter', 'meti', 'metil', 'metis', 'meto', 'metong',
    'metu', 'metua', 'metui', 'metuk', 'metul', 'metum', 'metun', 'metup',
    'mew', 'mewah', 'mewek',
    # pe- roots
    'pe', 'pecah', 'pecai', 'pecak', 'pecal', 'pecat', 'peci', 'pecok',
    'pecuk', 'pecun', 'pecus', 'pecut', 'peda', 'pedak', 'pedal', 'pedang',
    'pedap', 'pedar', 'pedas', 'pedat', 'pedih', 'pedis', 'pedo', 'pedu',
    'pegal', 'pegang', 'pegun', 'pejah', 'pejal', 'pejam', 'pejan', 'pejat',
    'peju', 'pek', 'peka', 'pekak', 'pekal', 'pekam', 'pekan', 'pekap',
    'pekar', 'pekas', 'pekat', 'pekau', 'pekik', 'pekir', 'pekit', 'pekok',
    'pekuk', 'pel', 'pela', 'pelah', 'pelai', 'pelak', 'pelam', 'pelan',
    'pelap', 'pelar', 'pelas', 'pelat', 'pele', 'peleh', 'pelek', 'pelekat',
    'pelep', 'peles', 'pelet', 'peli', 'pelik', 'pelin', 'pelip', 'pelir',
    'pelit', 'peloh', 'pelok', 'pelong', 'pelopong', 'pelor', 'pelosok',
    'peluh', 'peluk', 'pelun', 'pelup', 'pelut', 'pen', 'pena', 'penah',
    'penak', 'penal', 'penam', 'penan', 'penap', 'penar', 'penas', 'penat',
    'pencak', 'pencang', 'pencar', 'pencek', 'pencel', 'pencer', 'pencit',
    'pencong', 'pencu', 'penda', 'pendah', 'pendak', 'pendam', 'pendang',
    'pendap', 'pendar', 'pende', 'pendek', 'pendel', 'pendem', 'pender',
    'pendi', 'pendoa', 'pendok', 'pendong', 'pendu', 'pendul', 'pendur',
    'peng', 'pengan', 'pengap', 'pengar', 'penge', 'pengel', 'pengen',
    'penges', 'pengi', 'pengin', 'pengir', 'pengis', 'pengit', 'pengo',
    'pengok', 'pengon', 'pengot', 'pengu', 'penguk', 'pengun', 'pengus',
    'pengut', 'peni', 'penil', 'penin', 'penir', 'penit', 'penj', 'penja',
    'penjah', 'penjaj', 'penjal', 'penjam', 'penjan', 'penjap', 'penjar',
    'penjat', 'penjeng', 'penjer', 'penjil', 'penjin', 'penjir', 'penjo',
    'penjol', 'penju', 'penk', 'penoh', 'penok', 'penon', 'penop', 'penu',
    'peny', 'penya', 'penyak', 'penyal', 'penyam', 'penyan', 'penyap',
    'penyar', 'penyat', 'penye', 'penyel', 'penyer', 'penyes', 'penyet',
    'penyi', 'penyil', 'penyir', 'penyo', 'penyor', 'penyu', 'penyus',
    'penyul', 'pep', 'pepa', 'pepak', 'pepal', 'pepam', 'pepas', 'pepat',
    'pepau', 'pepek', 'pepel', 'pepen', 'peper', 'pepes', 'pepet', 'pepi',
    'pepih', 'pepit', 'pepo', 'pepoh', 'pepok', 'pepos', 'pepu', 'per',
    'pera', 'perah', 'perai', 'perak', 'peral', 'peram', 'peran', 'perang',
    'perap', 'peras', 'perat', 'perau', 'pere', 'pereh', 'perek', 'perel',
    'perem', 'peren', 'pereng', 'peres', 'peret', 'peri', 'periang', 'periap',
    'perih', 'perik', 'peril', 'pering', 'peris', 'perit', 'periu', 'perna',
    'pero', 'perok', 'peron', 'peros', 'peru', 'peruh', 'peruk', 'perum',
    'perun', 'perup', 'perus', 'perut', 'pes', 'pesa', 'pesah', 'pesai',
    'pesak', 'pesal', 'pesan', 'pesap', 'pesar', 'pesat', 'pese', 'pesek',
    'pesel', 'pesen', 'peser', 'peset', 'pesh', 'pesi', 'pesin', 'pesir',
    'pesit', 'peso', 'peson', 'pesot', 'pesu', 'pesui', 'pesut', 'pet',
    'peta', 'petah', 'petai', 'petak', 'petal', 'petam', 'petan', 'petang',
    'petap', 'petar', 'petas', 'pete', 'petek', 'petel', 'peten', 'peter',
    'peti', 'petik', 'petil', 'petin', 'petip', 'petir', 'petis', 'peto',
    'petong', 'petu', 'petua', 'petuh', 'petuk', 'petul', 'petum', 'petun',
    'petup', 'pew', 'pewah', 'pewak', 'peyot',
])


def strip_prefix(word: str) -> Tuple[str, str]:
    """Strip prefix only if the remainder looks like a valid root."""
    for pre_rumi, pre_jawi in PREFIXES:
        if word.startswith(pre_rumi) and len(word) > len(pre_rumi):
            remainder = word[len(pre_rumi):]
            # Don't strip if remainder is too short or word is a known root
            if len(remainder) >= 3 and word not in FALSE_PREFIX_ROOTS:
                return pre_rumi, remainder
            # Also don't strip if remainder starts with a vowel and is very short
            if len(remainder) >= 2 and remainder[0] not in VOWELS and word not in FALSE_PREFIX_ROOTS:
                return pre_rumi, remainder
    return '', word


def strip_suffix(word: str) -> Tuple[str, str]:
    for suf_rumi, suf_jawi in SUFFIXES:
        if word.endswith(suf_rumi) and len(word) > len(suf_rumi):
            return word[:-len(suf_rumi)], suf_rumi
    return word, ''


def transliterate_root(word: str) -> str:
    """
    Transliterate a root word.
    Improved vowel handling: writes medial vowels by default.
    """
    if not word:
        return ''

    result = []
    i = 0
    n = len(word)

    while i < n:
        ch_lower = word[i].lower()

        # Try digraphs first
        if i + 1 < n:
            digraph = word[i:i+2].lower()
            if digraph in DIGRAPHS:
                result.append(DIGRAPHS[digraph])
                i += 2
                continue

        # Single consonants
        if ch_lower in CONSONANTS:
            if ch_lower == 'k' and i == n - 1 and len(word) > 1:
                result.append('ق')
            else:
                result.append(CONSONANTS[ch_lower])
            i += 1
            continue

        # Vowels
        if ch_lower in VOWELS:
            if i == 0:
                # Word-initial vowels: i/e -> اي, u/o -> او, a -> ا
                if ch_lower in ('i', 'e'):
                    result.append('اي')
                elif ch_lower in ('u', 'o'):
                    result.append('او')
                else:
                    result.append('ا')
            elif i == n - 1:
                # Final vowel
                if ch_lower in ('i', 'e'):
                    result.append('ي')
                elif ch_lower in ('u', 'o'):
                    result.append('و')
                elif ch_lower == 'a':
                    pass  # Final -a usually omitted
            else:
                # Medial vowel - WRITE IT by default
                if ch_lower == 'a':
                    result.append('ا')
                elif ch_lower == 'i':
                    result.append('ي')
                elif ch_lower == 'u':
                    result.append('و')
                elif ch_lower == 'e':
                    result.append('ي')
                elif ch_lower == 'o':
                    result.append('و')
            i += 1
            continue

        if word[i] == '-':
            result.append('-')
            i += 1
            continue

        result.append(word[i])
        i += 1

    return ''.join(result)


def apply_prefix(prefix_rumi: str, root_jawi: str) -> str:
    for pr, pj in PREFIXES:
        if pr == prefix_rumi:
            return pj + root_jawi
    return root_jawi


def apply_suffix(suffix_rumi: str) -> str:
    for sr, sj in SUFFIXES:
        if sr == suffix_rumi:
            return sj
    return ''


def transliterate_rules(word: str) -> str:
    """
    Pure rule-based transliteration (no dictionary lookup).
    Used as the fallback for unknown words; also measured on its own
    to gauge the quality of the rules themselves.
    """
    if not word:
        return ''

    # Handle reduplication with hyphen: equal parts use ٢ (kata ganda)
    if '-' in word:
        parts = word.split('-')
        if len(parts) == 2 and parts[0] == parts[1]:
            return transliterate_rules(parts[0]) + '٢'
        return '-'.join(transliterate_rules(p) for p in parts)

    prefix_rumi, after_prefix = strip_prefix(word)
    root_rumi, suffix_rumi = strip_suffix(after_prefix)

    if not root_rumi and prefix_rumi:
        for pr, pj in PREFIXES:
            if pr == prefix_rumi:
                return pj
        return word

    # di-/ke- before a vowel-initial root is spelled with hamza: دأ / کأ
    # (diarahkan -> دأرهکن, keabsahan -> کأبسهن)
    if prefix_rumi in ('di', 'ke') and root_rumi and root_rumi[0] in VOWELS:
        root_jawi = 'أ' + transliterate_root(root_rumi)[1:]
    else:
        root_jawi = transliterate_root(root_rumi)
    result = apply_prefix(prefix_rumi, root_jawi)

    # Hamza at morpheme boundary: root-final 'a' + -an is written اءن
    # (pekerjaan -> ڤکرجاءن); near-exceptionless in the dictionary.
    # The root-final 'a' becomes the hamza seat (kept if already written,
    # e.g. via the ia/ua digraphs).
    if suffix_rumi == 'an' and root_rumi.endswith('a'):
        sep = '' if result.endswith('ا') else 'ا'
        return result + sep + 'ء' + apply_suffix(suffix_rumi)
    result += apply_suffix(suffix_rumi)

    return result


def transliterate(word: str) -> str:
    """
    Main transliteration function.
    Uses dictionary lookup first, then falls back to rules.
    """
    if not word:
        return ''

    # 1. Dictionary lookup (primary)
    jawi = _DICTIONARY.lookup(word)
    if jawi:
        return jawi

    # 2. Rule-based fallback
    return transliterate_rules(word)


# =============================================================================
# EVALUATION
# =============================================================================

def load_variants(test_file: str = 'rumi-jawi-unicode.csv') -> Dict[str, set]:
    """Load the CSV as {rumi: {all valid Jawi spellings}}."""
    variants: Dict[str, set] = {}
    with open(test_file, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                variants.setdefault(row[0].strip(), set()).add(row[1].strip())
    return variants


def evaluate(test_file: str = 'rumi-jawi-unicode.csv', limit: int = 5000,
             use_dictionary: bool = True):
    """
    Evaluate the transliterator against the CSV dictionary.
    A prediction counts as correct if it matches ANY known variant.
    """
    variants = load_variants(test_file)
    words = sorted(variants)
    if limit:
        words = words[:limit]

    correct = 0
    errors = []
    for rumi in words:
        predicted = (transliterate(rumi) if use_dictionary
                     else transliterate_rules(rumi))
        if predicted in variants[rumi]:
            correct += 1
        else:
            errors.append((rumi, sorted(variants[rumi])[0], predicted))

    total = len(words)
    accuracy = correct / total * 100 if total else 0
    mode = "dictionary + rules" if use_dictionary else "rules only"
    print(f"Evaluated on {total} unique words ({mode})")
    print(f"Correct: {correct} ({accuracy:.1f}%)")
    print(f"Errors: {total - correct}")
    print()
    print("Sample errors:")
    for rumi, expected, predicted in errors[:30]:
        print(f"  {rumi:20s} | Expected: {expected:20s} | Got: {predicted}")

    return correct, total, errors


# =============================================================================
# DEMO
# =============================================================================

def demo(sample_size: int = 1000, seed: Optional[int] = None,
         use_dictionary: bool = True):
    """
    Randomly sample unique words from the CSV dictionary and evaluate
    the transliterator against them (any known variant counts as correct).
    """
    if seed is not None:
        random.seed(seed)

    variants = load_variants()
    words = list(variants)

    if sample_size > len(words):
        sample_size = len(words)

    sampled = random.sample(words, sample_size)

    def predict(rumi: str) -> str:
        return transliterate(rumi) if use_dictionary else transliterate_rules(rumi)

    correct = 0
    incorrect = []
    for rumi in sampled:
        predicted = predict(rumi)
        if predicted in variants[rumi]:
            correct += 1
        else:
            incorrect.append((rumi, sorted(variants[rumi])[0], predicted))

    accuracy = correct / sample_size * 100 if sample_size else 0
    mode = "dictionary + rules" if use_dictionary else "RULES ONLY"

    print("=" * 70)
    print(f"RUMI → JAWI RANDOM SAMPLE EVALUATION ({mode})")
    print("=" * 70)
    print(f"Unique words in dictionary: {len(words)}")
    print(f"Sample size               : {sample_size}")
    if seed is not None:
        print(f"Random seed               : {seed}")
    print(f"Correct                   : {correct} / {sample_size}")
    print(f"Accuracy                  : {accuracy:.2f}%")
    print("=" * 70)
    print()

    # Show some correct examples
    correct_examples = [r for r in sampled if predict(r) in variants[r]]
    print("Sample CORRECT transliterations:")
    print("-" * 70)
    for rumi in correct_examples[:10]:
        print(f"  {rumi:<25} → {predict(rumi)}")
    print()

    # Show incorrect examples
    print("Sample INCORRECT transliterations:")
    print("-" * 70)
    for rumi, expected, predicted in incorrect[:20]:
        print(f"  {rumi:<25} | Expected: {expected:<25} | Got: {predicted}")
    print()

    if len(incorrect) > 20:
        print(f"  ... and {len(incorrect) - 20} more errors")
        print()

    return correct, sample_size, incorrect


if __name__ == '__main__':
    import sys
    argv = sys.argv[1:]
    use_dictionary = '--rules' not in argv
    if '--eval' in argv:
        evaluate(use_dictionary=use_dictionary)
    else:
        demo(use_dictionary=use_dictionary)
        print()
        print("Options: --eval (evaluate first 5000 words)  --rules (rules only, no dictionary)")
