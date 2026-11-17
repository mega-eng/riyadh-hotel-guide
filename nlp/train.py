"""
Trains the two sentence classifiers (service, sort) and the token tagger (slots) used by the
hotel-services page, from SYNTHETIC Saudi-dialect / MSA / English query templates.
Outputs: model.json (weights, consumed by nlp_core.js) and tests.json (held-out data for eval.js).
Usage: python3 train.py <path-to-html>
"""
import json, random, re, sys, unicodedata
from collections import Counter
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

random.seed(11); np.random.seed(11)
HTML = sys.argv[1] if len(sys.argv) > 1 else '../أقرب_خدمة_للفندق.html'

# ---------- text processing (mirror of nlp_core.js) ----------
def normalize(s):
    s = s.lower()
    s = ''.join(unicodedata.normalize('NFD', c)[0] if '\u00c0' <= c <= '\u017f' else c for c in s)
    s = s.translate({0x660 + i: ord('0') + i for i in range(10)}).translate({0x6f0 + i: ord('0') + i for i in range(10)})
    s = re.sub('[\u064b-\u0652\u0640]', '', s)
    for a, b in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي')): s = s.replace(a, b)
    return s
TOK = re.compile(r'[a-z]+|[\u0621-\u064a]+|\d+(?:\.\d+)?')
def tokenize(s): return TOK.findall(normalize(s))
def isnum(t): return '0' <= t[0] <= '9'
def sh(t): return '#' if isnum(t) else t

def sent_feats(toks):
    f = []
    n = len(toks)
    for i, t in enumerate(toks):
        w = sh(t); f.append('w=' + w)
        if w != '#':
            p = '<' + w + '>'
            for k in (3, 4):
                for j in range(len(p) - k + 1): f.append('c%d=%s' % (k, p[j:j + k]))
        if i + 1 < n: f.append('b=%s_%s' % (w, sh(toks[i + 1])))
    return f

def tag_feats(toks, i, lex=frozenset()):
    n = len(toks); t = toks[i]; w = sh(t)
    def at(j): return '<s>' if j < 0 else ('</s>' if j >= n else sh(toks[j]))
    f = ['b', 'w=' + w, 'w-1=' + at(i - 1), 'w-2=' + at(i - 2), 'w+1=' + at(i + 1), 'w+2=' + at(i + 2),
         'w-1|w=%s|%s' % (at(i - 1), w), 'w|w+1=%s|%s' % (w, at(i + 1)), 'w-2|w-1=%s|%s' % (at(i - 2), at(i - 1))]
    if isnum(t):
        f.append('dig')
        if '.' in t: f.append('dot')
    else:
        f.append('lat' if 'a' <= t[0] <= 'z' else 'ar')
        for k in (1, 2, 3):
            if len(t) >= k: f += ['p%d=%s' % (k, t[:k]), 's%d=%s' % (k, t[-k:])]
    f.append('len=%d' % min(len(t), 7))
    if t in lex: f.append('blex')
    if i > 0 and toks[i - 1] in lex: f.append('blex-1')
    if i + 1 < n and toks[i + 1] in lex: f.append('blex+1')
    return f

# ---------- brands (built by build_brands.py) ----------
BR = json.load(open('brands.json', encoding='utf8'))
random.shuffle(BR)
BCUT = int(len(BR) * 0.8)
BR_TR, BR_TE = BR[:BCUT], BR[BCUT:]
for b in BR:                       # hand-written (seed) brands always go to train; they are tested via eval.js hand set
    if b.get('seed') and b not in BR_TR: BR_TR.append(b); BR_TE = [x for x in BR_TE if x is not b]
def brand_pool(bs):
    out = []
    for b in bs:
        for a in b['aliases']:
            if 3 <= len(a) <= 30: out.append(a)
    return out
BPOOL_TR, BPOOL_TE = brand_pool(BR_TR), brand_pool(BR_TE)
LEX = set(tok for a in BPOOL_TR for tok in tokenize(a))

# ---------- hotels ----------
html = open(HTML, encoding='utf8').read()
H = json.loads(re.search(r'id="hotels-data">(.*?)</script>', html, re.S).group(1))
disp = sorted({(h.get('n') or h.get('a')) for h in H if (h.get('n') or h.get('a'))})

LAT2AR = [('sh', 'ش'), ('ch', 'ش'), ('th', 'ث'), ('kh', 'خ'), ('ph', 'ف'), ('ck', 'ك'), ('oo', 'و'), ('ee', 'ي'),
          ('a', 'ا'), ('b', 'ب'), ('c', 'ك'), ('d', 'د'), ('e', 'ي'), ('f', 'ف'), ('g', 'ج'), ('h', 'ه'), ('i', 'ي'), ('j', 'ج'),
          ('k', 'ك'), ('l', 'ل'), ('m', 'م'), ('n', 'ن'), ('o', 'و'), ('p', 'ب'), ('q', 'ق'), ('r', 'ر'), ('s', 'س'), ('t', 'ت'),
          ('u', 'و'), ('v', 'ف'), ('w', 'و'), ('x', 'كس'), ('y', 'ي'), ('z', 'ز')]
def translit(word):
    w = word.lower(); out = ''; i = 0
    while i < len(w):
        for a, b in LAT2AR:
            if w.startswith(a, i): out += b; i += len(a); break
        else: i += 1
    return re.sub(r'(.)\1+', r'\1', out)

BRANDS = {  # hand-written Arabic spellings people actually type (also used as matcher test set)
 'marriott': ['ماريوت', 'ماريوتس', 'ماريوت الرياض'], 'hilton': ['هيلتون', 'هيلتن', 'هلتون'],
 'four seasons': ['فورسيزونز', 'فورسيزنز', 'فور سيزنز', 'فورسيزون'], 'sheraton': ['شيراتون', 'شيرتون', 'شيراتن'],
 'radisson': ['راديسون', 'رادسون', 'راديسن بلو'], 'crowne plaza': ['كراون بلازا', 'كراونة بلازا', 'كراون بلازه'],
 'intercontinental': ['انتركونتننتال', 'انتركونتيننتال', 'انتركونتنتال'], 'holiday inn': ['هوليداي ان', 'هوليدي ان', 'هوليداي'],
 'movenpick': ['موفنبيك', 'موفنبك', 'موفنبيك الرياض'], 'fairmont': ['فيرمونت', 'فيرمنت'], 'ritz': ['ريتز كارلتون', 'ريتز', 'ريتز كارلتن'],
 'sofitel': ['سوفيتيل', 'سوفتيل'], 'kempinski': ['كمبينسكي', 'كيمبنسكي'], 'hyatt': ['حياة ريجنسي', 'هايات', 'هيات ريجنسي'],
 'mercure': ['ميركيور', 'ميركور'], 'novotel': ['نوفوتيل', 'نوفتيل'], 'doubletree': ['دبل تري', 'دابل تري'],
 'best western': ['بيست وسترن', 'بست ويسترن'], 'courtyard': ['كورتيارد', 'كورت يارد'], 'meridien': ['ميريديان', 'لو ميريديان', 'ميريدين'],
 'ascott': ['اسكوت', 'اسكوت رافال'], 'tulip': ['توليب ان', 'تيوليب ان'], 'swiss': ['سويس بل', 'سويس بيل'], 'hard rock': ['هارد روك'],
 'st.regis': ['سانت ريجس', 'سان ريجيس'], 'gloria': ['جلوريا', 'غلوريا'], 'vivienda': ['فيفيندا'], 'comfort': ['كومفورت', 'كمفورت'],
 'diamond': ['دايموند', 'دايمند'], 'boudl': ['بودل'], 'rafal': ['رافال'], 'wyndham': ['ويندهام', 'وندهام'],
}
POOL = set()
for n in disp:
    toks = TOK.findall(n.lower())
    toks = [t for t in toks if t not in ('hotel', 'hotels', 'فندق')]
    if not toks or len(' '.join(toks)) < 4: continue
    POOL.add(' '.join(toks[:2])); POOL.add(' '.join(toks[:3]))
    if all('a' <= t[0] <= 'z' for t in toks[:2]):
        POOL.add(' '.join(translit(t) for t in toks[:2]))
for v in BRANDS.values(): POOL.update(v)
POOL.update(['three palms', 'five stars inn', 'seven seas', 'two towers', 'ten hotel', 'one tower', 'ثلاث نخيل', 'خمس نجوم', 'اربع مواسم'])
POOL = sorted(p for p in POOL if p.strip())
random.shuffle(POOL)
cut = int(len(POOL) * 0.8)
POOL_TR, POOL_TE = POOL[:cut], POOL[cut:]

# ---------- lexicons ----------
SVC_AR = {
 'restaurant': ['مطعم', 'مطاعم', 'مطعم شاورما', 'مطعم كبسه', 'مطعم برجر', 'مطعم بيتزا', 'مطعم مندي', 'مشويات', 'اكل', 'مكان ياكل', 'عشا', 'غدا', 'فطور', 'وجبه', 'مكان اتعشى فيه', 'مكان اتغدى فيه', 'شاورما', 'برجر', 'بيتزا', 'كبسه', 'مندي', 'اكل شعبي', 'جوعان'],
 'cafe': ['كافيه', 'كافيهات', 'كافي', 'كوفي', 'كوفي شوب', 'قهوه', 'مقهى', 'قهوه مختصه', 'مكان اشرب فيه قهوه', 'كافيه للدراسه', 'مقاهي', 'محل قهوه', 'قهوه ودراسه'],
 'gym': ['نادي', 'نادي رياضي', 'جيم', 'صاله رياضيه', 'نادي لياقه', 'اتمرن', 'تمرين', 'مكان اتمرن فيه', 'لياقه', 'نوادي', 'حديد', 'صاله حديد', 'نادي رياضه'],
 'supermarket': ['سوبرماركت', 'سوبر ماركت', 'بقاله', 'ماركت', 'تموينات', 'هايبر', 'اشتري اغراض', 'اغراض البيت', 'خضار وفواكه', 'ماركت قريب', 'بقالات', 'هايبرماركت', 'اغراض'],
 'laundry': ['مغسله', 'مغاسل', 'غسيل ملابس', 'دراي كلين', 'كوي', 'اغسل ملابسي', 'تنظيف ملابس', 'مغسله ملابس', 'مكان اغسل فيه', 'مغسله سريعه', 'مكوى'],
 'all': ['خدمات', 'كل الخدمات', 'اي شي', 'شي قريب', 'وش حول', 'وش قريب', 'ايش في المنطقه', 'الاماكن القريبه', 'كل شي', 'خدمات قريبه', 'وش الخدمات', 'اي خدمه', 'مرافق'],
}
SVC_EN = {
 'restaurant': ['restaurant', 'restaurants', 'food', 'dinner', 'lunch', 'burger place', 'pizza'], 'cafe': ['cafe', 'coffee', 'coffee shop', 'cafes'],
 'gym': ['gym', 'fitness', 'gyms', 'workout place'], 'supermarket': ['supermarket', 'grocery', 'groceries', 'market'],
 'laundry': ['laundry', 'dry cleaning', 'laundromat'], 'all': ['services', 'anything', 'places', 'things'],
}
OPEN_AR = ['', '', '', 'ابغى', 'ابي', 'ابا', 'عطني', 'وريني', 'ورني', 'اعرض لي', 'دلني على', 'وين', 'وين فيه', 'فين', 'ايش', 'وش', 'ممكن', 'لو سمحت', 'اريد', 'ابحث عن', 'ودي اشوف', 'تكفى', 'ابغى اعرف', 'ودي في', 'اقترح علي']
NEAR_AR = ['اقرب', 'اقرب', 'قريب', 'الاقرب', 'قريبه', '', '']
SMART_AR = ['افضل', 'احسن', 'الاحسن', 'اجود', 'ممتاز', 'الافضل', 'الاحلى', 'زين', 'نظيف', 'طيب', 'اعلى تقييم', 'احلى', 'مميز']
HOTEL_CUE = ['من', 'عند', 'قرب', 'جنب', 'حول', 'بجانب', 'في', 'قريب من', 'من جنب', 'ل', 'لـ', 'جوار', 'بالقرب من', 'حوالين', 'على', 'من عند']
DIST_CUE = ['خلال', 'في حدود', 'ضمن', 'على بعد', 'لا يزيد عن', 'اقل من', 'مسافه', 'بحدود', 'بمسافه', 'ما يزيد عن', 'ما يبعد اكثر من', 'مسافتها']
EN_NEAR = ['nearest', 'closest', 'near', 'nearby']; EN_SMART = ['best', 'top', 'best rated', 'top rated', 'good', 'great']
NEARME_AR = ['مني', 'قريب مني', 'حولي', 'جنبي', 'من موقعي', 'قريب من موقعي', 'من مكاني', 'قريب من البيت', 'بجنبي']
NEARME_EN = ['near me', 'around me', 'close to me', 'nearby']
def typo(w):
    if len(w) < 4 or random.random() > 0.2: return w
    i = random.randrange(1, len(w) - 1); r = random.random()
    return w[:i] + w[i + 1:] if r < .4 else (w[:i] + w[i] + w[i:] if r < .7 else w[:i] + w[i + 1] + w[i] + w[i + 2:])
def noisy(txt, p=0.08):
    return ' '.join(typo(w) if random.random() < p else w for w in txt.split())

AR_WORDS = {1: 'واحد', 2: 'اثنين', 3: 'ثلاثه', 4: 'اربعه', 5: 'خمسه', 6: 'سته', 7: 'سبعه', 8: 'ثمانيه', 9: 'تسعه', 10: 'عشره'}
EN_WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten'}
def fmt_num(v, lang='ar'):
    r = random.random()
    if lang == 'en': r = r * 1.6 if r > .35 else r
    if float(v).is_integer(): v = int(v)
    if r < 0.2 and isinstance(v, int):
        return ''.join('٠١٢٣٤٥٦٧٨٩'[int(d)] for d in str(v))
    if r < 0.4 and isinstance(v, int) and 1 <= v <= 10:
        w = (AR_WORDS if lang == 'ar' else EN_WORDS)[v]
        if lang == 'ar' and w.endswith('ه') and v >= 3 and random.random() < .5: w = w[:-1]
        return w
    return str(v)

def gen_count(lang):
    v = random.choice([3, 3, 5, 5, 5, 10, 10, 15, 2, 4, 6, 7, 8, 20])
    return v, fmt_num(v, lang)

def gen_dist(lang):
    mode = random.random()
    if mode < .45:
        m = random.choice([200, 300, 400, 500, 500, 600, 700, 800, 1000, 1500]); u = random.choice(['متر', 'م', 'امتار', 'متر']) if lang == 'ar' else random.choice(['m', 'meters', 'metres'])
        return m / 1000, '%s %s' % (fmt_num(m, lang), u)
    if mode < .85:
        k = random.choice([1, 1, 2, 2, 3, 5, 1.5, 2.5, 4, 10]); u = random.choice(['كم', 'كيلو', 'كيلومتر']) if lang == 'ar' else random.choice(['km', 'kilometers', 'kilometres'])
        return k, '%s %s' % (fmt_num(k, lang), u)
    if lang == 'en': return 1, '1 km'
    return random.choice([(0.5, 'نص كيلو'), (0.25, 'ربع كيلو'), (1, 'كيلو'), (2, 'كيلوين'), (1.5, 'كيلو ونص'), (0.5, 'نص كم')])

def gen_rate_ar():
    v = random.choice([3, 3.5, 4, 4, 4.5, 4.5, 3.8, 4.2, 4.7, 4.3])
    n = fmt_num(v)
    if v == 4.5 and random.random() < .2: n = random.choice(['اربعه ونص', '4 ونص'])
    tmpl = random.choice([
        [('O', 'تقييم'), ('O', random.choice(['فوق', 'اكثر من', 'اعلى من', 'لا يقل عن', 'على الاقل'])), ('RATE', n)],
        [('O', 'تقييمه'), ('O', random.choice(['فوق', 'اكثر من', 'اعلى من'])), ('RATE', n)],
        [('RATE', n), ('O', random.choice(['نجوم', 'نجمه'])), ('O', random.choice(['او اكثر', 'وفوق', 'فاعلى']))],
        [('O', random.choice(['اكثر من', 'فوق', 'اعلى من'])), ('RATE', n), ('O', 'نجوم')],
        [('O', 'تقييم'), ('RATE', n), ('O', 'وفوق')],
        [('O', 'بتقييم'), ('RATE', n), ('O', 'او اكثر')],
        [('O', 'نجوم'), ('RATE', n)],
        [('O', 'تقييمها'), ('O', 'اعلى من'), ('RATE', n)]])
    return v, tmpl

def hotel_seg(name):
    r = random.random()
    pre = 'فندق ' if r < .2 else (random.choice(['لفندق ', 'للفندق ', 'بفندق ', 'الفندق ']) if r < .35 else '')
    nm = noisy(name, 0.12)
    if not pre and random.random() < .3 and not nm[0].isascii(): nm = 'ل' + nm.replace(' ', ' ', 1)
    return ('HOTEL', pre + nm)

def gen_ar(pool):
    svc = random.choice(list(SVC_AR)); phrase = random.choice(SVC_AR[svc])
    smart = random.random() < .4
    cue = random.choice(SMART_AR) if smart else random.choice(NEAR_AR)
    segs = []; gold = {'service': svc, 'sort': 'smart' if smart else 'near', 'k': None, 'maxkm': None, 'minr': None, 'hotel': None}
    op = random.choice(OPEN_AR)
    if op: segs.append(('O', op))
    count = random.random() < .3
    if cue: segs.append(('O', cue))
    if count:
        k, ktxt = gen_count('ar'); gold['k'] = k; segs.append(('COUNT', ktxt)); segs.append(('O', noisy(phrase)))
    else: segs.append(('O', noisy(phrase)))
    clauses = []
    if random.random() < .82:
        name = random.choice(pool); gold['hotel'] = name
        clauses.append([('O', random.choice(HOTEL_CUE)), hotel_seg(name)])
    elif random.random() < .6: clauses.append([('O', random.choice(NEARME_AR))])
    if random.random() < .3:
        v, txt = gen_dist('ar'); gold['maxkm'] = v; clauses.append([('O', random.choice(DIST_CUE)), ('DIST', txt)])
    if random.random() < .3:
        v, t = gen_rate_ar(); gold['minr'] = v; clauses.append(t)
    random.shuffle(clauses)
    if clauses and gold['hotel'] and random.random() < .5:
        clauses.sort(key=lambda c: 0 if any(t == 'HOTEL' for t, _ in c) else 1)
    for c in clauses: segs += c
    if random.random() < .1: segs.append(('O', random.choice(['لو سمحت', 'تكفى', 'بسرعه', 'الله يعافيك'])))
    return segs, gold

def gen_en(pool):
    svc = random.choice(list(SVC_EN)); phrase = random.choice(SVC_EN[svc])
    smart = random.random() < .4
    gold = {'service': svc, 'sort': 'smart' if smart else 'near', 'k': None, 'maxkm': None, 'minr': None, 'hotel': None}
    segs = []
    op = random.choice(['', '', 'show me', 'find', 'where is the', 'i need', 'give me', 'looking for'])
    if op: segs.append(('O', op))
    segs.append(('O', random.choice(EN_SMART if smart else EN_NEAR)))
    if random.random() < .3:
        k, t = gen_count('en'); gold['k'] = k; segs.append(('COUNT', t))
    segs.append(('O', phrase))
    cl = []
    if random.random() < .82:
        name = random.choice(pool); gold['hotel'] = name; cl.append([('O', random.choice(['to', 'near', 'close to', 'around', 'by', 'from'])), hotel_seg(name)])
    elif random.random() < .6: cl.append([('O', random.choice(NEARME_EN))])
    if random.random() < .3:
        v, t = gen_dist('en'); gold['maxkm'] = v; cl.append([('O', random.choice(['within', 'less than', 'under', 'up to'])), ('DIST', t)])
    if random.random() < .3:
        v = random.choice([3, 3.5, 4, 4.5]); gold['minr'] = v
        cl.append(random.choice([[('O', 'rating above'), ('RATE', str(v))], [('O', 'rated'), ('RATE', str(v)), ('O', 'stars or more')], [('RATE', str(v)), ('O', 'stars and up')]]))
    random.shuffle(cl)
    for c in cl: segs += c
    return segs, gold

def gen_brand_ar(pool, bpool):
    smart = random.random() < .3
    cue = random.choice(SMART_AR) if smart else random.choice(NEAR_AR)
    gold = {'service': 'brand', 'sort': 'smart' if smart else 'near', 'k': None, 'maxkm': None, 'minr': None, 'hotel': None, 'brand': None}
    segs = []
    op = random.choice(OPEN_AR)
    if op: segs.append(('O', op))
    if cue: segs.append(('O', cue))
    b = random.choice(bpool); gold['brand'] = b
    if random.random() < .15: segs.append(('O', random.choice(['فرع', 'محل', 'مطعم', 'كافيه', 'مقهى'])))
    if random.random() < .25:
        k, ktxt = gen_count('ar'); gold['k'] = k; segs.append(('COUNT', ktxt)); segs.append(('O', random.choice(['فرع', 'فروع'])))
    segs.append(('BRAND', noisy(b, .1)))
    clauses = []
    if random.random() < .75:
        name = random.choice(pool); gold['hotel'] = name
        clauses.append([('O', random.choice(HOTEL_CUE)), hotel_seg(name)])
    elif random.random() < .6: clauses.append([('O', random.choice(NEARME_AR))])
    if random.random() < .25:
        v, txt = gen_dist('ar'); gold['maxkm'] = v; clauses.append([('O', random.choice(DIST_CUE)), ('DIST', txt)])
    random.shuffle(clauses)
    for c in clauses: segs += c
    return segs, gold

def gen_brand_en(pool, bpool):
    smart = random.random() < .3
    gold = {'service': 'brand', 'sort': 'smart' if smart else 'near', 'k': None, 'maxkm': None, 'minr': None, 'hotel': None, 'brand': None}
    segs = []
    op = random.choice(['', '', 'show me', 'find', 'where is the', 'i need', 'where is'])
    if op: segs.append(('O', op))
    segs.append(('O', random.choice(EN_SMART if smart else EN_NEAR)))
    b = random.choice([x for x in bpool if x[0].isascii()] or bpool); gold['brand'] = b
    segs.append(('BRAND', b))
    if random.random() < .75:
        name = random.choice(pool); gold['hotel'] = name
        segs += [('O', random.choice(['to', 'near', 'close to', 'around', 'from'])), hotel_seg(name)]
    elif random.random() < .6: segs.append(('O', random.choice(NEARME_EN)))
    return segs, gold

def to_tokens(segs):
    toks, tags = [], []
    for kind, txt in segs:
        tt = tokenize(txt)
        for j, t in enumerate(tt):
            toks.append(t); tags.append('O' if kind == 'O' else ('B-' if j == 0 else 'I-') + kind)
    return toks, tags

def make(n, pool, bpool):
    out = []
    for _ in range(n):
        r = random.random()
        if r < .3: segs, gold = gen_brand_en(pool, bpool) if random.random() < .15 else gen_brand_ar(pool, bpool)
        else: segs, gold = gen_en(pool) if random.random() < .15 else gen_ar(pool)
        toks, tags = to_tokens(segs)
        if toks: out.append({'toks': toks, 'tags': tags, 'gold': gold, 'text': ' '.join(t for _, t in segs)})
    return out

train = make(18000, POOL_TR, BPOOL_TR); test = make(3000, POOL_TE, BPOOL_TE)
# test set also checks seen-pool generalisation less: it uses unseen hotel mentions only

# ---------- fit ----------
def fit(rows, labels, C, min_count, prune):
    cnt = Counter(f for r in rows for f in set(r))
    keep = {f for f, c in cnt.items() if c >= min_count}
    dv = DictVectorizer()
    X = dv.fit_transform([{f: 1 for f in r if f in keep} for r in rows])
    clf = LogisticRegression(C=C, max_iter=400, solver='lbfgs')
    clf.fit(X, labels)
    names = dv.get_feature_names_out(); W = {}
    for j, nme in enumerate(names):
        w = clf.coef_[:, j] if len(clf.classes_) > 2 else np.array([-clf.coef_[0, j], clf.coef_[0, j]])
        if np.abs(w).max() >= prune: W[str(nme)] = [round(float(x), 2) for x in w]
    b = clf.intercept_ if len(clf.classes_) > 2 else np.array([-clf.intercept_[0], clf.intercept_[0]])
    return {'classes': [str(c) for c in clf.classes_], 'bias': [round(float(x), 3) for x in b], 'w': W}

def run(model, feats):
    C = len(model['classes']); s = list(model['bias'])
    for f in feats:
        v = model['w'].get(f)
        if v:
            for j in range(C): s[j] += v[j]
    return model['classes'][int(np.argmax(s))]

nb_train = [r for r in train if r['gold']['service'] != 'brand']; nb_test = [r for r in test if r['gold']['service'] != 'brand']
svc_model = fit([sent_feats(r['toks']) for r in nb_train], [r['gold']['service'] for r in nb_train], 4.0, 2, 0.12)
sort_model = fit([sent_feats(r['toks']) for r in train], [r['gold']['sort'] for r in train], 4.0, 2, 0.12)
tag_rows, tag_y = [], []
for r in train:
    for i in range(len(r['toks'])): tag_rows.append(tag_feats(r['toks'], i, LEX)); tag_y.append(r['tags'][i])
tag_model = fit(tag_rows, tag_y, 3.0, 2, 0.15)

svc_acc = np.mean([run(svc_model, sent_feats(r['toks'])) == r['gold']['service'] for r in nb_test])
sort_acc = np.mean([run(sort_model, sent_feats(r['toks'])) == r['gold']['sort'] for r in test])
tok_acc = np.mean([run(tag_model, tag_feats(r['toks'], i, LEX)) == r['tags'][i] for r in test for i in range(len(r['toks']))])
print('python check  service %.3f  sort %.3f  tag-token %.3f' % (svc_acc, sort_acc, tok_acc))

model = {'hotelAliases': BRANDS, 'service': svc_model, 'sort': sort_model, 'tagger': tag_model, 'lex': sorted(set(tok for b in BR for a in b['aliases'] for tok in tokenize(a))),
         'meta': {'train_sentences': len(train), 'test_sentences': len(test), 'data': 'synthetic (templates), held-out hotel names in test',
                  'brands': len(BR), 'features': {'service': len(svc_model['w']), 'sort': len(sort_model['w']), 'tagger': len(tag_model['w'])}}}
json.dump(model, open('model.json', 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump({'test': [{'text': r['text'], 'gold': r['gold'], 'toks': r['toks'], 'tags': r['tags']} for r in test],
           'brands': BRANDS, 'hotels': disp, 'brand_pool_test': BPOOL_TE}, open('tests.json', 'w'), ensure_ascii=False)
import os; print('model.json KB', os.path.getsize('model.json') // 1024)
