// Evaluates the *deployed* JS inference (nlp_core.js) on held-out data. Usage: node eval.js
const fs = require('fs'), N = require('./nlp_core.js');
const model = JSON.parse(fs.readFileSync('model.json', 'utf8')), T = JSON.parse(fs.readFileSync('tests.json', 'utf8'));
const hotels = T.hotels.map(d => ({ n: d, a: '', disp: d }));
const brands = JSON.parse(fs.readFileSync('brands.json', 'utf8'));
const eng = new N.Engine(model, hotels, brands, { hotelAliases: model.hotelAliases });
const norm = N.normalize;
const same = (a, b) => (a == null && b == null) || (a != null && b != null && Math.abs(a - b) < 1e-6);

// 1) held-out synthetic sentences (unseen hotel mentions)
let svcN = 0, svc = 0, srt = 0, k = 0, d = 0, r = 0, tp = 0, fp = 0, fn = 0, tokOK = 0, tokN = 0;
T.test.forEach(t => {
  const o = eng.parse(t.text);
  if (t.gold.service !== 'brand') { svcN++; svc += o.service === t.gold.service; } srt += o.sort === t.gold.sort;
  k += same(o.k, t.gold.k); d += same(o.maxkm, t.gold.maxkm); r += same(o.minr, t.gold.minr);
  o.tags.forEach((g, i) => { tokN++; tokOK += g === t.tags[i]; const gh = /HOTEL/.test(t.tags[i]), ph = /HOTEL/.test(g); if (gh && ph) tp++; else if (ph) fp++; else if (gh) fn++; });
});
let bTP = 0, bFP = 0, bFN = 0; T.test.forEach(t => { const o = eng.parse(t.text), g = /BRAND/.test(t.tags.join()), p = !!o.brand; if (g && p) bTP++; else if (p) bFP++; else if (g) bFN++; });
const n = T.test.length, f1 = 2 * tp / (2 * tp + fp + fn);
const synthetic = { n, service_acc_non_brand: svc / svcN, sort_acc: srt / n, count_acc: k / n, distance_acc: d / n, rating_acc: r / n, hotel_span_f1: f1, tag_token_acc: tokOK / tokN, brand_detect_f1_unseen_brands: 2 * bTP / (2 * bTP + bFP + bFN) };

// 2) hand-written realistic queries (not produced by the generator)
const H = (q, svc, sort, extra, brand) => Object.assign({ q, svc, sort, brand }, extra || {});
const HAND = [
 H('ابغى مطعم قريب من فندق الفورسيزونز', 'restaurant', 'near', {}, 'four seasons'), H('وين اقرب مغسلة لهيلتون', 'laundry', 'near', {}, 'hilton'),
 H('ابي كافيه تقييمه فوق ٤ جنب ماريوت', 'cafe', 'near', { minr: 4 }, 'marriott'), H('اعرض لي افضل ٣ نوادي حول شيراتون', 'gym', 'smart', { k: 3 }, 'sheraton'),
 H('نادي رياضي خلال ٥٠٠ متر من راديسون بلو', 'gym', 'near', { maxkm: 0.5 }, 'radisson'), H('سوبرماركت ضمن كيلو من هوليداي ان', 'supermarket', 'near', { maxkm: 1 }, 'holiday inn'),
 H('اقرب مطعم مندي لفندق كراون بلازا بتقييم 4.5 او اكثر', 'restaurant', 'near', { minr: 4.5 }, 'crowne plaza'), H('عطني احسن خمس مطاعم قريبة من موفنبيك', 'restaurant', 'smart', { k: 5 }, 'movenpick'),
 H('nearest coffee shop to hilton', 'cafe', 'near', {}, 'hilton'), H('best gym within 2 km of marriott rating above 4', 'gym', 'smart', { maxkm: 2, minr: 4 }, 'marriott'),
 H('وش الخدمات اللي حول فندق ريتز كارلتون', 'all', 'near', {}, 'ritz'), H('ودي اتمرن جنب فيرمونت', 'gym', 'near', {}, 'fairmont'),
 H('فين اقرب بقالة من هيلتون', 'supermarket', 'near', {}, 'hilton'), H('مغسلة ملابس على بعد ٣ كم من سوفيتيل', 'laundry', 'near', { maxkm: 3 }, 'sofitel'),
 H('كافيه للدراسة قريب من انتركونتننتال', 'cafe', 'near', {}, 'intercontinental'), H('اجود مطعم برجر عند هوليداي ان بتقييم اكثر من ٣ ونص', 'restaurant', 'smart', { minr: 3.5 }, 'holiday inn'),
 H('ابغى 10 مطاعم من كراون بلازا', 'restaurant', 'near', { k: 10 }, 'crowne plaza'), H('دراي كلين قريب من راديسون', 'laundry', 'near', {}, 'radisson'),
 H('restaurants near four seasons', 'restaurant', 'near', {}, 'four seasons'), H('اقرب نادي لفندق حياة ريجنسي مسافة نص كيلو', 'gym', 'near', { maxkm: 0.5 }, 'hyatt'),
 H('تموينات جنب نوفوتيل', 'supermarket', 'near', {}, 'novotel'), H('كوفي شوب بتقييم 4 وفوق حول دبل تري', 'cafe', 'near', { minr: 4 }, 'doubletree'),
 H('اشوف الخدمات القريبة من شيراتون خلال كيلوين', 'all', 'near', { maxkm: 2 }, 'sheraton'), H('افضل ٥ مغاسل قرب ميركيور', 'laundry', 'smart', { k: 5 }, 'mercure'),
 H('مطعم شاورما جنب ماريوت خلال ٣٠٠ متر', 'restaurant', 'near', { maxkm: 0.3 }, 'marriott'), H('ابي اكل زين قريب من كمبينسكي', 'restaurant', 'smart', {}, 'kempinski'),
 H('gym near hilton within 1 km', 'gym', 'near', { maxkm: 1 }, 'hilton'), H('وين اشرب قهوة قريب من ريتز', 'cafe', 'near', {}, 'ritz'),
 H('سوبر ماركت تقييمه فوق ٤ ونص عند بيست وسترن', 'supermarket', 'near', { minr: 4.5 }, 'best western'), H('ابغى اغسل ملابسي قرب فيرمونت', 'laundry', 'near', {}, 'fairmont'),
 H('اعرض اقرب ٢ نوادي من سويس بل', 'gym', 'near', { k: 2 }, 'swiss'), H('كافيهات ممتازة جنب هارد روك', 'cafe', 'smart', {}, 'hard rock'),
 H('جيم قريب من ماريوت', 'gym', 'near', {}, 'marriott'), H('مطاعم حول كورتيارد ضمن ١ كم', 'restaurant', 'near', { maxkm: 1 }, 'courtyard'),
 H('مقهى قريب من توليب ان', 'cafe', 'near', {}, 'tulip'), H('افضل جيم قرب ميريديان', 'gym', 'smart', {}, 'meridien'),
];
const BR = T.brands;
// 2b) brand queries (the new part): does «اقرب دانكن» resolve to the right chain + hotel + slots?
const BQ = [
 ['وين اقرب دانكن دونتس من فندق فورسيزونز', 'dunkin', 'four seasons'], ['ابغى اقرب دنكن جنب ماريوت', 'dunkin', 'marriott'], ['اقرب دانكن لفندق هيلتون خلال كيلو', 'dunkin', 'hilton', { maxkm: 1 }],
 ['nearest dunkin donuts to marriott', 'dunkin', 'marriott'], ['اقرب ستاربكس من راديسون', 'starbucks', 'radisson'], ['افضل ٣ ستاربكس حول شيراتون', 'starbucks', 'sheraton', { k: 3 }],
 ['starbucks near hilton within 2 km', 'starbucks', 'hilton', { maxkm: 2 }], ['وين بارنز قريب من هوليداي ان', 'barns', 'holiday inn'], ['اقرب كودو لفندق كراون بلازا', 'kudu', 'crowne plaza'],
 ['عطني اقرب ماكدونالدز من موفنبيك', 'mcdonalds', 'movenpick'], ['ابي اقرب كنتاكي جنب فيرمونت', 'kfc', 'fairmont'], ['اقرب البيك من فندق ريتز كارلتون', 'albaik', 'ritz'],
 ['اقرب هرفي لسوفيتيل', 'herfy', 'sofitel'], ['بيتزا هت قريب من نوفوتيل', 'pizzahut', 'novotel'], ['افضل 5 دومينوز حول ميركيور', 'dominos', 'mercure', { k: 5 }],
 ['burger king closest to four seasons', 'burgerking', 'four seasons'], ['اقرب برجر كنج لدبل تري ضمن ٥٠٠ متر', 'burgerking', 'doubletree', { maxkm: 0.5 }], ['اقرب صب واي من انتركونتننتال', 'subway', 'intercontinental'],
 ['وين اقرب باسكن روبنز من هيلتون', 'baskin', 'hilton'], ['اقرب فتنس تايم من ماريوت', 'fitnesstime', 'marriott'], ['اقرب بنده من راديسون', 'panda', 'radisson'], ['اقرب العثيم لفندق شيراتون', 'othaim', 'sheraton'],
 ['اقرب تميمي جنب هيلتون', 'tamimi', 'hilton'], ['اقرب مقهى من هيلتون', null, 'hilton'], ['اقرب مطعم من ماريوت', null, 'marriott'], ['افضل نادي حول شيراتون', null, 'sheraton'],
];
const bs = { n: BQ.length, brand_ok: 0, hotel_ok: 0, slots_ok: 0, slots_n: 0, no_false_brand_ok: 0, no_false_brand_n: 0 }, bfails = [];
BQ.forEach(([q, brand, hk, ex]) => {
  const o = eng.parse(q);
  if (brand) { if (o.brand && o.brand.id === brand) bs.brand_ok++; else bfails.push([q, 'brand', o.brand && o.brand.id, brand]); }
  else { bs.no_false_brand_n++; if (!o.brand) bs.no_false_brand_ok++; else bfails.push([q, 'false-brand', o.brand.id]); }
  const g = goldFor(hk), c = (o.hotelCandidates || []).map(x => x.disp);
  if (c.slice(0, 3).some(x => g.indexOf(x) >= 0)) bs.hotel_ok++; else bfails.push([q, 'hotel', o.hotelText, hk]);
  if (ex) { bs.slots_n++; if (['k', 'maxkm'].every(key => ex[key] === undefined || same(o[key], ex[key]))) bs.slots_ok++; else bfails.push([q, 'slots', o.k, o.maxkm, ex]); }
});
function goldFor(key) {
  const keys = [key].concat(BR[key] || []).map(norm);
  return T.hotels.filter(h => { const nh = norm(h); return keys.some(k => nh.indexOf(k) >= 0); });
}
const hs = { n: HAND.length, service: 0, sort: 0, count: 0, distance: 0, rating: 0, hotel_top1: 0, hotel_top3: 0, hotel_n: 0, hotel_in_gold_pool: 0 };
const fails = [];
HAND.forEach(t => {
  const o = eng.parse(t.q); let ok = true;
  if (o.service === t.svc) hs.service++; else { ok = false; fails.push([t.q, 'service', o.service, t.svc]); }
  if (o.sort === t.sort) hs.sort++; else { ok = false; fails.push([t.q, 'sort', o.sort, t.sort]); }
  if (same(o.k, t.k)) hs.count++; else fails.push([t.q, 'k', o.k, t.k]);
  if (same(o.maxkm, t.maxkm)) hs.distance++; else fails.push([t.q, 'maxkm', o.maxkm, t.maxkm]);
  if (same(o.minr, t.minr)) hs.rating++; else fails.push([t.q, 'minr', o.minr, t.minr]);
  const g = goldFor(t.brand);
  if (g.length) {
    hs.hotel_n++;
    const c = (o.hotelCandidates || []).map(x => x.disp);
    if (c[0] && g.indexOf(c[0]) >= 0) hs.hotel_top1++;
    if (c.slice(0, 3).some(x => g.indexOf(x) >= 0)) hs.hotel_top3++; else fails.push([t.q, 'hotel', o.hotelText, t.brand]);
  }
});

// 3) hotel-name matcher vs the old substring matcher
function baseline(q) {
  const t = String(q).trim().toLowerCase();
  const nrm = s => norm(s).replace(/\b(hotel|hotels|فندق|فنادق)\b/g, ' ').replace(/[^\w\s\u0600-\u06ff]/g, ' ').replace(/\s+/g, ' ').trim();
  for (const h of hotels) if (h.disp === q) return [h.disp];
  const nq = nrm(t); if (!nq) return [];
  let best = null, bs = 0;
  hotels.forEach(h => { const key = nrm(h.n); if (!key) return; const s = key === nq ? 1 : (key.indexOf(nq) >= 0 ? 0.9 : (nq.indexOf(key) >= 0 ? 0.8 : 0)); if (s > bs) { bs = s; best = h.disp; } });
  return best ? [best] : [];
}
function evalSet(items, fnNew) {
  let a1 = 0, a3 = 0, b1 = 0, n = 0;
  items.forEach(it => { n++; const r = fnNew(it.q).map(x => x.disp); if (r[0] && it.gold.indexOf(r[0]) >= 0) a1++; if (r.slice(0, 3).some(x => it.gold.indexOf(x) >= 0)) a3++; const b = baseline(it.q); if (b[0] && it.gold.indexOf(b[0]) >= 0) b1++; });
  return { n, model_top1: a1 / n, model_top3: a3 / n, baseline_top1: b1 / n };
}
const arabic = [];
Object.keys(BR).forEach(key => { const g = goldFor(key); if (g.length) BR[key].forEach(sp => arabic.push({ q: sp, gold: g })); });
let seed = 5; const rnd = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
const latin = [];
T.hotels.filter(h => /^[\x00-\x7f ]+$/.test(h)).forEach(h => {
  const w = N.tokenize(h).filter(x => !/^(hotel|hotels|al|the)$/.test(x) && x.length > 2).slice(0, 2); if (w.join(' ').length < 6) return;
  const clean = w.join(' '); const gold = T.hotels.filter(x => norm(x).indexOf(clean) >= 0);
  let q = clean; const i = 1 + Math.floor(rnd() * (q.length - 2)), r = rnd();
  q = r < .4 ? q.slice(0, i) + q.slice(i + 1) : (r < .7 ? q.slice(0, i) + q[i] + q.slice(i) : q.slice(0, i) + q[i + 1] + q[i] + q.slice(i + 2));
  if (q !== clean && gold.length) latin.push({ q, gold });
});
// honest split: the hand-written Arabic spellings are ALSO shipped as hotel aliases, so with aliases that number is a lookup, not generalisation
const eng0 = new N.Engine(model, hotels, brands);   // no aliases
const matcher = { arabic_spellings_no_aliases: evalSet(arabic, q => eng0.matcher.rank(q, 3)), latin_typos_no_aliases: evalSet(latin, q => eng0.matcher.rank(q, 3)),
                  arabic_spellings_deployed: evalSet(arabic, q => eng.matcher.rank(q, 3)), latin_typos_deployed: evalSet(latin, q => eng.matcher.rank(q, 3)) };

// 4) v3 features — hand-written, none of these sentences is produced by the generator
// fields: near (near-me), cui (food type id), unsup (unsupported service), brand, hotel (brand key for goldFor), k
const V3 = [
 ['اقرب دانكن مني', { near: true, brand: 'dunkin' }], ['وين اقرب ستاربكس حولي', { near: true, brand: 'starbucks' }], ['nearest starbucks near me', { near: true, brand: 'starbucks' }],
 ['برجر قريب مني', { near: true, cui: 'burger' }], ['نادي قريب مني خلال 2 كم', { near: true }], ['ابغى كافيه قريب من موقعي', { near: true }],
 ['وين اقرب مطعم قريب من البيت', { near: true }], ['pizza near me', { near: true, cui: 'pizza' }], ['مغسلة جنبي', { near: true }],
 ['اقرب صيدلية من هيلتون', { unsup: true, hotel: 'hilton' }], ['اقرب مسجد', { unsup: true }], ['وين اقرب بنزين', { unsup: true }], ['اقرب صراف من ماريوت', { unsup: true, hotel: 'marriott' }],
 ['اقرب مطعم شاورما من هيلتون', { cui: 'shawarma', hotel: 'hilton' }], ['ابغى قهوة مختصة جنب الفورسيزونز', { cui: 'specialty', hotel: 'four seasons' }],
 ['مطعم هندي جنب شيراتون', { cui: 'indian', hotel: 'sheraton' }], ['افضل 5 مطاعم بيتزا جنب هيلتون', { cui: 'pizza', hotel: 'hilton', k: 5 }], ['حلويات قريبة من هيلتون', { cui: 'sweets', hotel: 'hilton' }],
 ['دراي كلين قريب من راديسون', { cui: 'drycleaning', hotel: 'radisson' }], ['ابي فطور جنب ماريوت', { cui: 'breakfast', hotel: 'marriott' }],
 ['ستاربك جنب هيلتون', { brand: 'starbucks', hotel: 'hilton' }], ['دنكين جنب هيلتون', { brand: 'dunkin', hotel: 'hilton' }], ['ماكدونلز قريب من ماريوت', { brand: 'mcdonalds', hotel: 'marriott' }],
 ['ستاربوكس عند شيراتون', { brand: 'starbucks', hotel: 'sheraton' }], ['اقرب هرفى لهيلتون', { brand: 'herfy', hotel: 'hilton' }],
 ['اقرب هرفي لسوفيتيل', { brand: 'herfy', hotel: 'sofitel' }], ['اقرب برجر كنج لدبل تري ضمن ٥٠٠ متر', { brand: 'burgerking', hotel: 'doubletree' }],
 ['وين اقرب مغسلة لهيلتون', { hotel: 'hilton' }], ['عطني احسن خمس مطاعم قريبة من موفنبيك', { k: 5, hotel: 'movenpick' }], ['ابي ثلاث كافيهات جنب ماريوت', { k: 3, hotel: 'marriott' }],
 ['اقرب مطعم برجر من هوليداي ان', { cui: 'burger', hotel: 'holiday inn' }], ['برجر كنج جنب هيلتون', { brand: 'burgerking', hotel: 'hilton' }],
 ['مطعم تقييمه فوق 4 جنب ماريوت', { hotel: 'marriott', nobrand: true }], ['وين اقرب كافيه قريب من البيت', { near: true, nobrand: true }],
];
const v3 = { n: V3.length, ok: 0, checks: 0, passed: 0 }, v3fails = [];
V3.forEach(([q, g]) => {
  const o = eng.parse(q), bad = [];
  const chk = (name, cond) => { v3.checks++; if (cond) v3.passed++; else bad.push(name); };
  if (g.near !== undefined) chk('near', !!o.nearMe === g.near); else chk('no-near', !o.nearMe);
  if (g.cui) chk('cuisine', o.cuisine && o.cuisine.id === 'cuisine_' + g.cui);
  if (g.unsup) chk('unsup', !!o.unsupported);
  if (g.brand) chk('brand', o.brand && o.brand.id === g.brand);
  if (g.nobrand) chk('no-brand', !o.brand);
  if (g.k) chk('k', o.k === g.k);
  if (g.hotel) { const gl = goldFor(g.hotel); chk('hotel', o.hotel && gl.indexOf(o.hotel.disp) >= 0); }
  if (g.near) chk('no-hotel-when-near', !o.hotel);
  if (!bad.length) v3.ok++; else v3fails.push([q, bad, o.brand && o.brand.id, o.cuisine && o.cuisine.id, o.hotel && o.hotel.disp, o.k]);
});
// 5) v4: trip planning + tourist / entertainment categories (hand-written)
const V4 = [
 ['سوي لي جدول ٣ ايام وانا ساكن في هيلتون', { trip: 3, hotel: 'hilton' }], ['عندي يومين في الرياض وش اسوي', { trip: 2, nohotel: true }],
 ['رتب لي رحلة يوم واحد احب الاماكن التاريخية', { trip: 1, interests: ['heritage'], nohotel: true }], ['جدول اسبوع للعائلة والاطفال من فندق الفورسيزونز', { trip: 7, interests: ['fun', 'park'], hotel: 'four seasons' }],
 ['plan a 2 day trip from marriott', { trip: 2, hotel: 'marriott' }], ['وين اروح ٣ ايام بالرياض واحب التسوق', { trip: 3, interests: ['mall'], nohotel: true }],
 ['خطة رحلة هادية يومين واحب المندي', { trip: 2, pace: 'relaxed', cui: 'mandi', nohotel: true }], ['ابي برنامج سياحي ٤ ايام', { trip: 4, nohotel: true }],
 ['جدول رحلة من موقعي', { tripAny: true, near: true }], ['عندي يومين في الرياض ومعي اطفال وساكن في ماريوت', { trip: 2, interests: ['fun'], hotel: 'marriott' }], ['ابي مرشد سياحي', { tripAny: true }], ['itinerary for 3 days near hilton i like museums', { trip: 3, interests: ['museum'], hotel: 'hilton' }],
 ['اقرب ملاهي من هيلتون', { attr: 'fun', hotel: 'hilton', notrip: true }], ['مولات قريبة مني', { attr: 'mall', near: true, notrip: true }], ['وين اقرب حديقة', { attr: 'park', notrip: true }],
 ['اماكن سياحية جنب شيراتون', { attr: 'sights', hotel: 'sheraton', notrip: true }], ['اقرب سينما', { attr: 'fun', notrip: true }], ['متحف قريب من الفورسيزونز', { attr: 'sights', hotel: 'four seasons', notrip: true }],
 ['وين اقرب الملاهي', { attr: 'fun', notrip: true }], ['nearest mall to radisson', { attr: 'mall', hotel: 'radisson', notrip: true }],
 ['اقرب مطعم من هيلتون', { noattr: true, notrip: true, hotel: 'hilton' }], ['اقرب سوبرماركت جنب ماريوت', { noattr: true, notrip: true, hotel: 'marriott' }],
];
const v4 = { n: V4.length, ok: 0, checks: 0, passed: 0 }, v4fails = [];
V4.forEach(([q, g]) => {
  const o = eng.parse(q), bad = [], chk = (name, c) => { v4.checks++; if (c) v4.passed++; else bad.push(name); };
  if (g.trip) chk('trip-days', o.trip && o.trip.days === g.trip);
  if (g.tripAny) chk('trip', !!o.trip);
  if (g.notrip) chk('no-trip', !o.trip);
  if (g.interests) chk('interests', o.trip && g.interests.every(i => o.trip.interests.indexOf(i) >= 0));
  if (g.pace) chk('pace', o.trip && o.trip.pace === g.pace);
  if (g.cui) chk('cuisine', o.cuisine && o.cuisine.id === 'cuisine_' + g.cui);
  if (g.attr) chk('attr', o.attraction === g.attr);
  if (g.noattr) chk('no-attr', !o.attraction);
  if (g.near) chk('near', !!o.nearMe);
  if (g.hotel) { const gl = goldFor(g.hotel); chk('hotel', o.hotel && gl.indexOf(o.hotel.disp) >= 0); }
  if (g.nohotel) chk('no-hotel', !o.hotel);
  if (!bad.length) v4.ok++; else v4fails.push([q, bad, o.trip, o.attraction, o.hotel && o.hotel.disp]);
});
let fa4 = { trip: 0, attr: 0, n: 0 };
HAND.concat(BQ.map(b => ({ q: b[0] }))).forEach(t => { const o = eng.parse(t.q); fa4.n++; if (o.trip) fa4.trip++; if (o.attraction) fa4.attr++; });
T.test.forEach(t => { const o = eng.parse(t.text); fa4.n++; if (o.trip) fa4.trip++; if (o.attraction) fa4.attr++; });
v4.false_alarms_on_old_sentences = fa4;

// false alarms: the new rule layer must not fire on the old hand-written / synthetic sentences
let fa = { near: 0, unsup: 0, n: 0 };
HAND.forEach(t => { const o = eng.parse(t.q); fa.n++; if (o.nearMe) fa.near++; if (o.unsupported) fa.unsup++; });
T.test.forEach(t => { const o = eng.parse(t.text); fa.n++; if (o.nearMe && t.gold.hotel) fa.near++; if (o.unsupported) fa.unsup++; });
const out = { synthetic_heldout: synthetic, handwritten: hs, brand_queries: bs, v3_features: Object.assign(v3, { false_alarms: fa }), v4_trip_and_places: v4, matcher };
fs.writeFileSync('metrics.json', JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
console.log('FAILS', JSON.stringify(fails, null, 0));
console.log('BRAND FAILS', JSON.stringify(bfails, null, 0));
console.log('V3 FAILS', JSON.stringify(v3fails, null, 0));
console.log('V4 FAILS', JSON.stringify(v4fails, null, 0));
