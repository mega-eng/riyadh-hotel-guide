"""
Builds brands.json (chains / named places) from the POI data inside the page.
A "brand" = a name that appears on >= MIN_BRANCHES POIs. Arabic and English spellings that sit in the same
POI name ("Dunkin' Donuts (دانكن دونتس)") are merged into one brand with union-find; SEED adds the spellings
people actually type (دنكن, ماك, كي اف سي ...). Usage: python3 build_brands.py page.html
"""
import json, re, sys
from collections import Counter, defaultdict
HTML = sys.argv[1] if len(sys.argv) > 1 else 'page.html'
MIN_BRANCHES = 4

def normalize(s):  # same rules as nlp_core.js normalize (Arabic part only matters here)
    s = s.lower().replace('\u200e', '')
    s = re.sub('[\u064b-\u0652\u0640]', '', s)
    for a, b in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي')): s = s.replace(a, b)
    return s
def clean(p): return re.sub(r"[^a-z\u0621-\u064a0-9 ]", ' ', re.sub(r"['’`´]", '', p)).strip()
def parts(name):
    n = normalize(name)
    return [re.sub(r'\s+', ' ', clean(p)) for p in re.findall(r'[^()|\-–/،,]+', n)]

GENERIC = set(normalize(x) for x in """مغاسل مغسله مغسله ملابس laundry laundries تموينات بقاله سوبرماركت supermarket market markets restaurant مطعم
 cafe coffee قهوه كافيه نادي gym fitness مخبز bakery حلويات sweets pastry juice عصائر pizza بيتزا burger برجر shawarma شاورما
 dry clean dry cleaning dry cleaners مغاسل ملابس ahmad mohammed""".split())
GENERIC |= {normalize(x) for x in ['riyadh', 'الرياض', 'riyad', 'ar', 'saudi', 'السعودية', 'قهوة مختصة', 'specialty coffee', 'للسكان فقط', 'residents only', 'بوفيه', 'buffet', 'برجر مشوي', 'البرجر المشوي', 'grilled burger', 'مطعم بخاري', 'مطعم البخاري', 'taxi', 'تاكسي', 'تكسي', 'robbins', 'spice', 'signature', 'خفيف', 'تسالي', 'مغسلة ملابس', 'dry cleaning', 'مغسلة', 'مغاسل ملابس', 'سوبر ماركت', 'كوفي شوب', 'coffee shop']}

# spellings people type -> match keys that exist in POI names (normalized, apostrophes removed)
SEED = {
 'dunkin': (['دانكن', 'دنكن', 'دانكن دونتس', 'دنكن دونتس', 'دانكن دونات', 'دنكن دونات', 'dunkin', 'dunkin donuts'], ['dunkin', 'دانكن']),
 'starbucks': (['ستاربكس', 'ستارباكس', 'ستاربكس كوفي', 'starbucks', 'ستار بكس'], ['starbucks', 'ستاربكس']),
 'barns': (['بارنز', 'بارنس', 'barns', 'barn s'], ['barns', 'barn s', 'بارنز']),
 'mcdonalds': (['ماكدونالدز', 'ماكدونالد', 'ماك', 'ماكدونلدز', 'ماكدونالدس', 'mcdonalds', 'mcdonald s', 'macdonalds'], ['mcdonalds', 'macdonalds', 'mcdonald s', 'ماكدونالدز']),
 'kfc': (['كنتاكي', 'كي اف سي', 'كيه اف سي', 'kfc'], ['kfc', 'كنتاكي']),
 'albaik': (['البيك', 'بيك', 'البيك السعودي', 'albaik', 'al baik'], ['albaik', 'al baik', 'البيك']),
 'herfy': (['هرفي', 'herfy', 'هيرفي'], ['herfy', 'هرفي']),
 'kudu': (['كودو', 'kudu', 'كدو'], ['kudu', 'كودو']),
 'burgerking': (['برجر كنج', 'برجر كينج', 'burger king', 'برقر كنق', 'برغر كنج'], ['burger king', 'برجر كنج', 'برجر كينج']),
 'pizzahut': (['بيتزا هت', 'pizza hut', 'بيتزا هات'], ['pizza hut', 'بيتزا هت']),
 'dominos': (['دومينوز', 'دومينو', 'دومينوس', 'dominos', 'domino s', 'dominos pizza', 'دومينوز بيتزا'], ['dominos', 'domino s', 'دومينوز']),
 'baskin': (['باسكن روبنز', 'باسكن', 'باسكن روبينز', 'baskin robbins', 'baskin'], ['baskin', 'باسكن']),
 'subway': (['صب واي', 'سب واي', 'subway'], ['subway', 'صب واي']),
 'shawarmer': (['شاورمر', 'shawarmer'], ['shawarmer', 'شاورمر']),
 'maestro': (['مايسترو بيتزا', 'مايسترو', 'maestro pizza', 'maestro'], ['maestro', 'مايسترو']),
 'hardees': (['هارديز', 'hardees', 'hardee s'], ['hardees', 'hardee s', 'هارديز']),
 'costa': (['كوستا', 'كوستا كوفي', 'costa', 'costa coffee'], ['costa', 'كوستا']),
 'timhortons': (['تيم هورتنز', 'تيم هورتن', 'tim hortons', 'tim horton s'], ['tim horton', 'تيم هورتنز']),
 'tamimi': (['التميمي', 'تميمي', 'اسواق التميمي', 'tamimi', 'tamimi markets'], ['tamimi', 'التميمي']),
 'panda': (['بنده', 'panda', 'panda supermarket', 'هايبر بنده', 'اسواق بنده'], ['panda', 'بنده']),
 'othaim': (['العثيم', 'اسواق العثيم', 'عبدالله العثيم', 'othaim', 'alothaim', 'abdullah alothaim markets'], ['othaim', 'العثيم']),
 'danube': (['الدانوب', 'دانوب', 'danube'], ['danube', 'الدانوب']),
 'lulu': (['لولو', 'لولو هايبرماركت', 'lulu', 'lulu hypermarket'], ['lulu hyper', 'لولو هايبر']),
 'fitnesstime': (['فتنس تايم', 'فيتنس تايم', 'فتنس تايم', 'fitness time', 'fitness time xpress'], ['fitness time', 'فتنس تايم', 'فيتنس تايم']),
 'aljabr': (['الجبر', 'مغسلة الجبر', 'aljabr', 'al jabr'], ['aljabr', 'al jabr', 'مغسله الجبر', 'مغاسل الجبر']),
 'drcafe': (['دكتور كافيه', 'دي ار كافيه', 'dr cafe', 'dr cafe coffee', 'دكتور كوفي'], ['dr cafe', 'دكتور كافيه']),
 'mccafe': (['ماك كافيه', 'ماكافيه', 'mccafe', 'mc cafe'], ['mccafe']),
 'tomtom': (['توم توم', 'tom tom'], ['tom tom']),
 'oneword': (['عنوان القهوه', 'عنوان القهوة'], ['عنوان القهوه']),
}
LABEL = {'dunkin': 'دانكن دونتس', 'starbucks': 'ستاربكس', 'barns': 'بارنز', 'mcdonalds': 'ماكدونالدز', 'kfc': 'كنتاكي', 'albaik': 'البيك', 'herfy': 'هرفي',
 'kudu': 'كودو', 'burgerking': 'برجر كنج', 'pizzahut': 'بيتزا هت', 'dominos': 'دومينوز', 'baskin': 'باسكن روبنز', 'subway': 'صب واي', 'shawarmer': 'شاورمر',
 'maestro': 'مايسترو بيتزا', 'hardees': 'هارديز', 'costa': 'كوستا', 'timhortons': 'تيم هورتنز', 'tamimi': 'أسواق التميمي', 'panda': 'بنده', 'othaim': 'أسواق العثيم',
 'danube': 'الدانوب', 'lulu': 'لولو هايبرماركت', 'fitnesstime': 'فتنس تايم', 'aljabr': 'مغاسل الجبر', 'drcafe': 'دكتور كافيه', 'mccafe': 'ماك كافيه', 'tomtom': 'توم توم', 'oneword': 'عنوان القهوة'}
SEED = {k: ([normalize(a) for a in al], [normalize(m) for m in mt]) for k, (al, mt) in SEED.items()}

html = open(HTML, encoding='utf8').read()
P = json.loads(re.search(r'id="poi-data">(.*?)</script>', html, re.S).group(1))

# --- 1) keys + union-find over names that co-occur inside one POI name
cnt = Counter(); par = {}
def find(x):
    while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
    return x
rows = []
for cat, v in P.items():
    for idx, x in enumerate(v):
        ks = [k for k in parts(x[0] or '') if len(k) >= 3 and k not in GENERIC]
        ks = list(dict.fromkeys(ks)); rows.append((cat, idx, ks))
        for k in ks: cnt[k] += 1
good = {k for k, n in cnt.items() if n >= MIN_BRANCHES}
for cat, idx, ks in rows:
    ks = [k for k in ks if k in good]
    for a, b in zip(ks, ks[1:]):
        # only merge an Arabic key with a Latin key (the bilingual "X (Y)" pattern) — avoids chaining unrelated names
        if bool(re.match('[a-z]', a)) != bool(re.match('[a-z]', b)) and min(cnt[a], cnt[b]) >= 0.5 * max(cnt[a], cnt[b]): par[find(a)] = find(b)
groups = defaultdict(list)
for k in good: groups[find(k)].append(k)

brands = []
used = set()
# seeds first
for sid, (aliases, match) in SEED.items():
    cats = Counter(); n = 0
    for cat, idx, ks in rows:
        nm = normalize(P[cat][idx][0] or '')
        if any(m in clean(nm) for m in match): cats[cat] += 1; n += 1
    if n:
        disp = LABEL.get(sid) or max(aliases, key=len)
        brands.append({'id': sid, 'disp': disp, 'aliases': aliases, 'match': match, 'cats': dict(cats), 'n': n, 'seed': True})
        used.update(k for k in good if any(m in k for m in match))
# auto brands
for g, ks in groups.items():
    ks = [k for k in ks if k not in used]
    if not ks: continue
    n = max(cnt[k] for k in ks)
    if n < MIN_BRANCHES * 2 and len(ks) == 1: continue          # keep singletons only if clearly frequent
    cats = Counter()
    for cat, idx, kk in rows:
        if any(k in kk for k in ks): cats[cat] += 1
    disp = max(ks, key=lambda a: (bool(re.match('[a-z]', a)), cnt[a]))
    brands.append({'id': 'auto_' + re.sub(r'\W+', '_', disp), 'disp': disp, 'aliases': ks, 'match': ks, 'cats': dict(cats), 'n': sum(cats.values()), 'seed': False})
brands.sort(key=lambda b: -b['n'])
json.dump(brands, open('brands.json', 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
print(len(brands), 'brands;', sum(b['seed'] for b in brands), 'seed')
for b in brands[:25]: print(b['id'], b['n'], b['cats'], b['aliases'][:4])
