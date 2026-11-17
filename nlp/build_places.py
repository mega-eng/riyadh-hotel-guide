"""
Builds places.json (tourist / entertainment places of Riyadh) from riyadh_places.tsv, an OpenStreetMap
extract (Overpass, © OpenStreetMap contributors, ODbL). Cleans junk, re-classifies, merges duplicates and
marks clusters (Diriyah has ~10 entries) so the trip planner visits an area once.
Usage: python3 build_places.py riyadh_places.tsv places.json
"""
import json, math, re, sys
src, dst = sys.argv[1], sys.argv[2]
def hv(a, b, c, d):
    r = math.pi / 180; x = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))
AR = re.compile('[؀-ۿ]')
rows = []
for line in open(src, encoding='utf8').read().split('\n'):
    f = line.split('\t')
    if len(f) < 8: continue
    oid, cat, lat, lng, nm, ar, en, oh = f[:8]
    rows.append(dict(id=oid, cat=cat, lat=float(lat), lng=float(lng), nm=nm.replace('‎', '').strip(), ar=ar.strip(), en=en.strip(), oh=oh.strip().strip('"')))

JUNK = re.compile(r'^(1|متحف|استراحة|Neighborhood park|Children’s recreation park)$|صورة ملعب|^ملعب|ملعب أطفال|ملعب اطفال|ساحة البلدية$', re.I)
NOT_MALL = re.compile(r'هايبر|أسواق|اسواق|تخفيضات|ساكو|Montblanc|التسوق الذكي|مرجان', re.I)
FUN_NAME = re.compile(r'بوليفارد|(?<!sports )boulevard|blvd|ملاهي|amusement|ونترلاند|winter', re.I)
out = []
for r in rows:
    if JUNK.search(r['nm']): continue
    if r['cat'] == 'mall' and NOT_MALL.search(r['nm']): continue
    if FUN_NAME.search(r['nm'] + ' ' + r['en']): r['cat'] = 'fun'
    if r['cat'] == 'park' and re.search('حديقة الحيوانات|zoo', r['nm'] + r['en'], re.I): r['cat'] = 'fun'
    # display names: Arabic first, English beside it
    nm = r['nm']
    ar = r['ar'] or (nm if AR.search(nm) and not re.search('[A-Za-z]{3}', nm) else '')
    en = r['en'] or ('' if AR.search(nm) else nm)
    m = re.match(r'^(.*?[A-Za-z].*?)\s*[-–/]?\s*([؀-ۿ].*)$', nm)        # "Diriyyah Park حديقة الدرعية"
    if m and not ar: en, ar = en or m.group(1).strip(' -'), m.group(2).strip()
    if not ar and not en: continue
    r['ar'], r['en'] = ar, en
    out.append(r)

# same place twice (same name, < 700 m) → keep one (prefer the one with more info / non-park category)
PRI = {'heritage': 0, 'museum': 1, 'fun': 2, 'show': 3, 'mall': 4, 'park': 5}
keep = []
for r in sorted(out, key=lambda x: (PRI[x['cat']], -len(x['en']) - len(x['ar']))):
    key = re.sub(r'\W', '', (r['ar'] or r['en']).lower())
    if any(re.sub(r'\W', '', (k['ar'] or k['en']).lower()) == key and hv(k['lat'], k['lng'], r['lat'], r['lng']) < 0.7 for k in keep): continue
    if r['en'] and any(k['en'] and k['en'].lower() == r['en'].lower() and hv(k['lat'], k['lng'], r['lat'], r['lng']) < 0.7 for k in keep): continue
    twin = [k for k in keep if k['cat'] == r['cat'] and hv(k['lat'], k['lng'], r['lat'], r['lng']) < 0.25 and bool(k['ar']) != bool(r['ar']) and bool(k['en']) != bool(r['en'])]
    if twin: twin[0]['ar'] = twin[0]['ar'] or r['ar']; twin[0]['en'] = twin[0]['en'] or r['en']; continue   # «Sakr al Jazeera Aviation Museum» + «متحف صقر الجزيرة للطيران»
    keep.append(r)

# importance: is this worth a visitor's trip? (OSM has no ratings, so use honest signals)
MAJOR_PARK = re.compile(r'منتزه|منتزة|sports boulevard|promenade|grove|king|الملك|park.*(salam|futah|malaz)|السلام|الفوطة|الملز|وادي نمار|درة|مركز الملك عبد العزيز|الوطن|الدرعية|البجيري|المعالم|الرمال|السويدي', re.I)
for r in keep:
    c = r['cat']; both = bool(r['ar'] and r['en'])
    if c == 'park': r['tier'] = 1 if (MAJOR_PARK.search(r['ar'] + ' ' + r['en']) and not re.search('حي |الثانية|الثالثة|الرابعة', r['ar'])) else 2
    elif c == 'mall': r['tier'] = 1 if (both or re.search('mall|مول|centre|center|gallery|walk|front|avenue|plaza|square', r['en'] + r['ar'], re.I)) else 2
    else: r['tier'] = 1
    # not for visitors / too minor for a schedule (private palaces, remote wells, temporary shows, halls)
    txt = r['ar'] + ' ' + r['en']
    if c == 'heritage' and (re.search(r'قصر (الملك|الامير|الأمير)|اليمامة|الناصرية|بوابة المطار|بئر|قصر صعب|مهد', txt) and not re.search('الدرعية|Diriyah|Dir', txt)) and hv(r['lat'], r['lng'], 24.736, 46.574) > 2: r['tier'] = 2
    if c == 'show' and re.search(r'blippi|barbie|baker|ليلتي|جمال سنتر|teatro', txt, re.I): r['tier'] = 2
    base = {'heritage': 1.0, 'museum': 0.95, 'fun': 0.9, 'show': 0.55, 'mall': 0.7, 'park': 0.72}[c]
    r['w'] = round(base + (0.15 if both else 0) + (0.08 if r['oh'] else 0), 3)

# one tier-1 entry per name (OSM repeats «واحة الملك سلمان للعلوم» 4 times in different spots)
seen = set()
for r in sorted(keep, key=lambda x: (PRI[x['cat']], -x['w'])):
    k = re.sub(r'\W', '', (r['ar'] or r['en']).lower())
    if r['tier'] == 1 and k in seen: r['tier'] = 2
    if r['tier'] == 1: seen.add(k)

# clusters: places of the same kind within 600 m form one visit (Diriyah, Boulevard City, King Abdulaziz Historical Center)
cid = 0
for r in keep: r['cl'] = None
for r in sorted(keep, key=lambda x: -x['w']):
    if r['cl'] is not None or r['tier'] != 1: continue
    cid += 1; r['cl'] = cid
    for s in keep:
        if s['cl'] is None and s['tier'] == 1 and hv(r['lat'], r['lng'], s['lat'], s['lng']) < 0.6 and (s['cat'] in ('heritage', 'museum')) == (r['cat'] in ('heritage', 'museum')): s['cl'] = cid
for r in keep:
    if r['cl'] is None: cid += 1; r['cl'] = cid
# big areas a visitor sees in one go: everything inside them is one visit
AREAS = [(24.7360, 46.5720, 2.5), (24.7690, 46.6050, 1.2)]       # Diriyah (At-Turaif, Al-Bujairi, Ghusaibah), Boulevard Riyadh City
for lat, lng, rad in AREAS:
    inside = [r for r in keep if r['tier'] == 1 and r['cat'] != 'park' and hv(lat, lng, r['lat'], r['lng']) < rad]
    if inside:
        top = max(inside, key=lambda x: x['w'])
        for r in inside: r['cl'] = top['cl']

res = [[r['id'], r['cat'], round(r['lat'], 6), round(r['lng'], 6), r['ar'], r['en'], r['oh'], r['tier'], r['w'], r['cl']] for r in keep]
json.dump({'source': 'OpenStreetMap contributors (ODbL), extracted 2026-11-17 via Overpass API', 'fields': ['id', 'cat', 'lat', 'lng', 'ar', 'en', 'hours', 'tier', 'w', 'cluster'], 'rows': res},
          open(dst, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
print('kept', len(keep), 'of', len(rows), Counter((r['cat'], r['tier']) for r in keep))
cl = Counter(r['cl'] for r in keep if r['tier'] == 1); print('tier1 clusters', len(cl), 'biggest', [(c, n, [x['ar'] or x['en'] for x in keep if x['cl'] == c][:5]) for c, n in cl.most_common(3)])
for c in ['heritage', 'museum', 'fun', 'show', 'mall']: print(c, [ (r['ar'] or r['en']) for r in keep if r['cat'] == c][:40])
print('parks t1', [(r['ar'] or r['en']) for r in keep if r['cat'] == 'park' and r['tier'] == 1])
