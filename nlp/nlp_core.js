/* HotelNLP — Arabic/English query understanding + fuzzy hotel matching. Runs in browser and Node. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.HotelNLP = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---------- text normalisation + tokenisation (must mirror train.py) ---------- */
  function normalize(s) {
    s = String(s == null ? '' : s).toLowerCase();
    s = s.replace(/[\u00c0-\u017f]/g, function (c) { return c.normalize('NFD').charAt(0); });
    s = s.replace(/[\u0660-\u0669]/g, function (d) { return String(d.charCodeAt(0) - 0x660); })
         .replace(/[\u06f0-\u06f9]/g, function (d) { return String(d.charCodeAt(0) - 0x6f0); });
    s = s.replace(/[\u064b-\u0652\u0640]/g, '').replace(/[\u0623\u0625\u0622]/g, '\u0627').replace(/\u0649/g, '\u064a')
         .replace(/\u0629/g, '\u0647').replace(/\u0624/g, '\u0648').replace(/\u0626/g, '\u064a');
    return s;
  }
  var TOK = /[a-z]+|[\u0621-\u064a]+|\d+(?:\.\d+)?/g;
  function tokenize(s) { return normalize(s).match(TOK) || []; }
  function isNum(t) { return t.charCodeAt(0) >= 48 && t.charCodeAt(0) <= 57; }
  function sh(t) { return isNum(t) ? '#' : t; }

  /* ---------- features (mirror train.py) ---------- */
  function sentFeats(toks) {
    var f = [], n = toks.length, i, w, k, p;
    for (i = 0; i < n; i++) {
      w = sh(toks[i]); f.push('w=' + w);
      if (w !== '#') {
        p = '<' + w + '>';
        for (k = 3; k <= 4; k++) for (var j = 0; j + k <= p.length; j++) f.push('c' + k + '=' + p.substr(j, k));
      }
      if (i + 1 < n) f.push('b=' + w + '_' + sh(toks[i + 1]));
    }
    return f;
  }
  function tagFeats(toks, i, lex) {
    var n = toks.length, t = toks[i], w = sh(t);
    function at(j) { return j < 0 ? '<s>' : (j >= n ? '</s>' : sh(toks[j])); }
    var f = ['b', 'w=' + w, 'w-1=' + at(i - 1), 'w-2=' + at(i - 2), 'w+1=' + at(i + 1), 'w+2=' + at(i + 2),
      'w-1|w=' + at(i - 1) + '|' + w, 'w|w+1=' + w + '|' + at(i + 1), 'w-2|w-1=' + at(i - 2) + '|' + at(i - 1)];
    if (isNum(t)) { f.push('dig'); if (t.indexOf('.') >= 0) f.push('dot'); }
    else {
      f.push(/^[a-z]/.test(t) ? 'lat' : 'ar');
      for (var k = 1; k <= 3; k++) if (t.length >= k) { f.push('p' + k + '=' + t.substr(0, k)); f.push('s' + k + '=' + t.substr(t.length - k)); }
    }
    f.push('len=' + Math.min(t.length, 7));
    if (lex) { if (lex[t]) f.push('blex'); if (i > 0 && lex[toks[i - 1]]) f.push('blex-1'); if (i + 1 < n && lex[toks[i + 1]]) f.push('blex+1'); }
    return f;
  }

  /* ---------- linear model inference ---------- */
  function scoreLinear(model, feats) {
    var C = model.classes.length, s = model.bias.slice(), W = model.w, i, j, v;
    for (i = 0; i < feats.length; i++) { v = W[feats[i]]; if (v) for (j = 0; j < C; j++) s[j] += v[j]; }
    return s;
  }
  function softmax(s) {
    var m = Math.max.apply(null, s), e = s.map(function (x) { return Math.exp(x - m); }), z = e.reduce(function (a, b) { return a + b; }, 0);
    return e.map(function (x) { return x / z; });
  }
  function classify(model, toks) {
    var p = softmax(scoreLinear(model, sentFeats(toks))), b = 0;
    for (var i = 1; i < p.length; i++) if (p[i] > p[b]) b = i;
    return { label: model.classes[b], conf: p[b], probs: p };
  }
  function tagTokens(model, toks, lex) {
    var tags = [];
    for (var i = 0; i < toks.length; i++) {
      var s = scoreLinear(model, tagFeats(toks, i, lex)), b = 0;
      for (var j = 1; j < s.length; j++) if (s[j] > s[b]) b = j;
      tags.push(model.classes[b]);
    }
    for (i = 0; i < tags.length; i++) {            // repair: I-X without a start becomes B-X
      if (tags[i].charAt(0) === 'I' && (i === 0 || tags[i - 1].slice(2) !== tags[i].slice(2))) tags[i] = 'B' + tags[i].slice(1);
    }
    return tags;
  }
  function spans(toks, tags) {
    var out = {}, cur = null;
    tags.forEach(function (t, i) {
      if (t === 'O') { cur = null; return; }
      var kind = t.slice(2);
      if (t.charAt(0) === 'B' || !cur || cur.kind !== kind) { cur = { kind: kind, toks: [] }; (out[kind] = out[kind] || []).push(cur); }
      cur.toks.push(toks[i]);
    });
    return out;
  }

  /* ---------- quantities ---------- */
  var NUMW = { 'واحد': 1, 'واحده': 1, 'اثنين': 2, 'اثنان': 2, 'ثنين': 2, 'اثنتين': 2, 'ثلاث': 3, 'ثلاثه': 3, 'اربع': 4, 'اربعه': 4,
    'خمس': 5, 'خمسه': 5, 'ست': 6, 'سته': 6, 'سبع': 7, 'سبعه': 7, 'ثمان': 8, 'ثمانيه': 8, 'تسع': 9, 'تسعه': 9, 'عشر': 10, 'عشره': 10,
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10 };
  var FRAC = { 'نص': 0.5, 'نصف': 0.5, 'half': 0.5, 'ربع': 0.25, 'quarter': 0.25 };
  var UNIT_M = { 'م': 1, 'متر': 1, 'امتار': 1, 'm': 1, 'meter': 1, 'meters': 1, 'metres': 1, 'metre': 1 };
  var UNIT_KM = { 'كم': 1, 'كيلو': 1, 'كيلومتر': 1, 'km': 1, 'kilometer': 1, 'kilometers': 1, 'kilometre': 1, 'kilometres': 1 };
  function parseQuantity(toks) {
    var num = null, unit = null;
    toks.forEach(function (t) {
      if (isNum(t)) { num = parseFloat(t); }
      else if (t === 'ونص' || t === 'ونصف') { num = (num || 0) + 0.5; }
      else if (t === 'كيلوين' || t === 'كيلومترين') { num = 2; unit = 'km'; }
      else if (UNIT_M[t]) { unit = 'm'; }
      else if (UNIT_KM[t]) { unit = 'km'; }
      else if (FRAC[t] != null) { num = (num !== null && num >= 1) ? num + FRAC[t] : FRAC[t]; }
      else if (NUMW[t] != null) { num = (num !== null && num < 10 && NUMW[t] === 10) ? num + 10 : NUMW[t]; }
    });
    if (num === null && unit === 'km') num = 1;
    return { num: num, unit: unit };
  }

  /* ---------- phonetic skeleton (Arabic & Latin -> shared coarse consonant code) ---------- */
  var AR_MAP = { 'ب': 'b', 'ت': 't', 'ث': 't', 'ج': 'j', 'ح': 'h', 'خ': 'x', 'د': 'd', 'ذ': 'd', 'ر': 'r', 'ز': 's', 'س': 's', 'ش': 'S', 'ص': 's',
    'ض': 'd', 'ط': 't', 'ظ': 'd', 'غ': 'j', 'ف': 'f', 'ق': 'k', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h', 'و': 'w', 'ي': 'y' };
  function skeletonWord(w) {
    var out = '', i, c;
    if (/^[a-z]/.test(w)) {
      w = w.replace(/^al(?=[a-z]{3,})/, '');
      w = w.replace(/tch|sch|sh|ch/g, 'S').replace(/ph/g, 'f').replace(/th/g, 't').replace(/kh/g, 'x').replace(/gh/g, 'j').replace(/ck/g, 'k')
           .replace(/q/g, 'k').replace(/c(?=[eiy])/g, 's').replace(/c/g, 'k').replace(/v/g, 'f')
           .replace(/z/g, 's').replace(/p/g, 'b').replace(/g/g, 'j').replace(/oo|ou/g, 'u');
      for (i = 0; i < w.length; i++) {
        c = w.charAt(i);
        if ('aeiou'.indexOf(c) >= 0) continue;
        if ((c === 'w' || c === 'y') && i > 0) continue;
        out += c;
      }
    } else {
      if (w.length >= 4 && w.indexOf('\u0627\u0644') === 0) w = w.slice(2);
      for (i = 0; i < w.length; i++) {
        c = AR_MAP[w.charAt(i)]; if (!c) continue;
        if ((c === 'w' || c === 'y') && i > 0) continue;
        out += c;
      }
    }
    return out.replace(/(.)\1+/g, '$1');
  }
  var STOP = { 'hotel': 1, 'hotels': 1, 'فندق': 1, 'فنادق': 1, 'al': 1, 'ال': 1, 'the': 1, 'by': 1, 'riyadh': 1, 'الرياض': 1, 'بالرياض': 1, 'ar': 1, 'لفندق': 1, 'للفندق': 1, 'بفندق': 1, 'الفندق': 1 };
  function keyWords(text) { return tokenize(text).filter(function (t) { return !isNum(t) && !STOP[t] && t.length > 1; }).map(function (t) { return (t.length >= 6 && t.indexOf('\u0627\u0644') === 0) ? t.slice(2) : t; }); }

  /* ---------- TF-IDF char n-gram index over hotel names ---------- */
  function grams(words) {
    var g = {};
    words.forEach(function (w) {
      var p = '^' + w + '$';
      for (var n = 2; n <= 3; n++) for (var i = 0; i + n <= p.length; i++) { var k = p.substr(i, n); g[k] = (g[k] || 0) + 1; }
    });
    return g;
  }
  function Matcher(hotels, opts) {
    var perAlt = !!(opts && opts.perAlt);   // also score each alias on its own (a long official name must not dilute «دبل تري»)
    var self = this, docs = [], df1 = {}, df2 = {};
    var seen = {};
    hotels.forEach(function (h) {
      var disp = h.disp || h.n || h.a; if (seen[disp]) return; seen[disp] = 1;
      var texts = [h.n, h.a].concat(h.alts || []).filter(Boolean), w1 = [], w2 = [];
      texts.forEach(function (t) { var kw = keyWords(t); w1 = w1.concat(kw); w2 = w2.concat(kw.map(skeletonWord).filter(Boolean)); });
      var altg = perAlt ? (h.alts || []).map(function (t) { var kw = keyWords(t); return { g1: grams(kw), g2: grams(kw.map(skeletonWord).filter(Boolean)) }; }).filter(function (x) { return Object.keys(x.g1).length; }) : [];
      docs.push({ h: h, disp: disp, g1: grams(w1), g2: grams(w2), n1: 0, n2: 0, nk: w1.length, alts: altg });
    });
    docs.forEach(function (d) {
      Object.keys(d.g1).forEach(function (k) { df1[k] = (df1[k] || 0) + 1; });
      Object.keys(d.g2).forEach(function (k) { df2[k] = (df2[k] || 0) + 1; });
    });
    var N = docs.length;
    function idf(df, k) { return Math.log((N + 1) / ((df[k] || 0) + 1)) + 1; }
    function vec(g, df) { var v = {}, n = 0; Object.keys(g).forEach(function (k) { var x = (1 + Math.log(g[k])) * idf(df, k); v[k] = x; n += x * x; }); return { v: v, n: Math.sqrt(n) || 1 }; }
    docs.forEach(function (d) { d.v1 = vec(d.g1, df1); d.v2 = vec(d.g2, df2); d.alts.forEach(function (a) { a.v1 = vec(a.g1, df1); a.v2 = vec(a.g2, df2); }); });
    function cos(a, b) { var s = 0; for (var k in a.v) if (b.v[k]) s += a.v[k] * b.v[k]; return s / (a.n * b.n); }
    this.size = N;
    this.rank = function (query, top) {
      var kw = keyWords(query);
      if (!kw.length) return [];
      var q1 = vec(grams(kw), df1), q2 = vec(grams(kw.map(skeletonWord).filter(Boolean)), df2), latinQ = /^[a-z]/.test(kw[0]);
      var res = docs.map(function (d) {
        var a = cos(q1, d.v1), b = cos(q2, d.v2);
        d.alts.forEach(function (al) { a = Math.max(a, cos(q1, al.v1)); if (!latinQ) b = Math.max(b, cos(q2, al.v2)); });   // Latin query: alias sound-alike would blur hotel families
        var sc = Math.max(a, 0.93 * b); return { disp: d.disp, hotel: d.h, score: sc, bucket: Math.round(sc * 33), nk: d.nk, lex: a, pho: b };
      });
      res.sort(function (x, y) { return (y.bucket - x.bucket) || (x.nk - y.nk) || (y.score - x.score); });
      return res.slice(0, top || 5);
    };
  }

  /* ---------- extra lexicons (rule layer on top of the models) ---------- */
  // "near me": the user wants results around their own position, not a hotel
  var NEARME1 = { 'مني': 1, 'حولي': 1, 'جنبي': 1, 'موقعي': 1, 'مكاني': 1, 'جواري': 1, 'بجنبي': 1, 'البيت': 1, 'بيتي': 1, 'المنزل': 1, 'منزلي': 1 };
  var CUE_W = { 'من': 1, 'عند': 1, 'جنب': 1, 'قرب': 1, 'حول': 1, 'في': 1, 'to': 1, 'by': 1, 'of': 1, 'from': 1, 'near': 1, 'around': 1, 'close': 1 };
  var NEARME2 = { 'near me': 1, 'around me': 1, 'close to me': 1, 'nearby me': 1, 'my location': 1, 'قريب مني': 1, 'قريبه مني': 1 };
  // services we have NO data for: answer honestly instead of guessing a category
  var UNSUP = [
    ['صيدليات', ['صيدليه', 'صيدليات', 'صيدلية', 'pharmacy', 'pharmacies', 'دوا', 'ادويه']], ['مستشفيات وعيادات', ['مستشفي', 'مستشفيات', 'hospital', 'طوارئ', 'مستوصف', 'عياده', 'clinic']],
    ['مساجد', ['مسجد', 'مساجد', 'جامع', 'mosque', 'مصلى']], ['صرافات وبنوك', ['صراف', 'بنك', 'بنوك', 'atm', 'bank']],
    ['محطات وقود', ['بنزين', 'محطه', 'محطات', 'وقود', 'gas', 'petrol', 'fuel']],
    ['حلاقين وصالونات', ['حلاق', 'حلاقه', 'صالون', 'barber', 'salon']],
    ['مواقف', ['مواقف', 'باركنج', 'parking']], ['تاكسي', ['تاكسي', 'تكسي', 'اوبر', 'uber', 'taxi']]];
  var UNSUP_IDX = {}; UNSUP.forEach(function (u) { u[1].forEach(function (w) { UNSUP_IDX[normalize(w)] = u[0]; }); });
  // food / cafe types: matched against place NAMES (Arabic + English), searched like a chain
  var CUISINE = [
    ['shawarma', 'مطعم شاورما', ['شاورما', 'شاورمه', 'shawarma', 'shawerma', 'shawarmer'], ['restaurant']],
    ['burger', 'مطعم برجر', ['برجر', 'برغر', 'برقر', 'burger', 'burgers'], ['restaurant']],
    ['pizza', 'مطعم بيتزا', ['بيتزا', 'pizza'], ['restaurant']],
    ['mandi', 'مطعم مندي', ['مندي', 'مظبي', 'مضبي', 'mandi', 'madhbi'], ['restaurant']],
    ['kabsa', 'مطعم كبسة', ['كبسه', 'كبسات', 'kabsa'], ['restaurant']],
    ['grill', 'مشويات', ['مشويات', 'شوايه', 'مشاوي', 'grill', 'grills', 'bbq'], ['restaurant']],
    ['broast', 'بروست', ['بروست', 'broast', 'دجاج', 'chicken'], ['restaurant']],
    ['sushi', 'سوشي', ['سوشي', 'sushi', 'ياباني', 'japanese'], ['restaurant']],
    ['falafel', 'فلافل وفول', ['فلافل', 'falafel', 'فول', 'فوال', 'foul'], ['restaurant']],
    ['seafood', 'مأكولات بحرية', ['سمك', 'اسماك', 'بحري', 'بحريه', 'seafood', 'fish'], ['restaurant']],
    ['indian', 'مطعم هندي', ['هندي', 'indian', 'برياني', 'biryani'], ['restaurant']],
    ['chinese', 'مطعم صيني', ['صيني', 'chinese'], ['restaurant']],
    ['italian', 'مطعم إيطالي', ['ايطالي', 'italian', 'باستا', 'pasta'], ['restaurant']],
    ['lebanese', 'مطعم لبناني', ['لبناني', 'lebanese', 'شامي', 'syrian'], ['restaurant']],
    ['turkish', 'مطعم تركي', ['تركي', 'turkish'], ['restaurant']],
    ['sweets', 'حلويات', ['حلويات', 'حلا', 'sweets', 'dessert', 'desserts', 'كيك', 'cake', 'pastry'], ['restaurant', 'cafe']],
    ['icecream', 'آيس كريم', ['ايس كريم', 'ايسكريم', 'بوظه', 'ice cream', 'gelato', 'باسكن'], ['restaurant', 'cafe']],
    ['bakery', 'مخبز / فطائر', ['مخبز', 'مخابز', 'افران', 'فطاير', 'فطائر', 'bakery', 'bakeries', 'معجنات'], ['restaurant']],
    ['juice', 'عصائر', ['عصير', 'عصاير', 'عصائر', 'juice', 'juices'], ['restaurant', 'cafe']],
    ['breakfast', 'فطور', ['فطور', 'breakfast'], ['restaurant', 'cafe']],
    ['specialty', 'قهوة مختصة', ['مختصه', 'specialty', 'speciality'], ['cafe']],
    ['drycleaning', 'دراي كلين', ['دراي', 'dry clean', 'dry cleaning', 'كوي'], ['laundry']]];
  var CUI_KEYS = []; // [normalized-key, tokens-length, entry]
  CUISINE.forEach(function (c) { c[2].forEach(function (w) { var k = tokenize(w); if (k.length) CUI_KEYS.push([k.join(' '), k.length, c]); }); });
  CUI_KEYS.sort(function (a, b) { return b[1] - a[1]; });
  // ordinary words that look like brand typos (البيت ≈ البيك …)
  var NOT_BRAND = { 'هايبرماركت': 1, 'هايبر': 1, 'سوبر': 1, 'اسواق': 1, 'سوق': 1, 'تموينات': 1, 'بقاله': 1, 'بقالات': 1, 'مخبز': 1, 'كوفي': 1, 'كافي': 1, 'مقهي': 1, 'مقاهي': 1, 'صاله': 1, 'لياقه': 1, 'مغاسل': 1, 'غسيل': 1, 'ملابس': 1, 'اغراض': 1, 'خضار': 1, 'فواكه': 1, 'مشويات': 1, 'وجبه': 1, 'فطور': 1, 'غدا': 1, 'عشا': 1, 'مطاعم': 1, 'ماركت': 1, 'البيت': 1, 'بيت': 1, 'البيك': 0, 'الحين': 1, 'قريبه': 1, 'كافيه': 1, 'كافيهات': 1, 'قهوه': 1, 'مطاعم': 1, 'مطعم': 1, 'نادي': 1, 'مغسله': 1, 'سوبرماركت': 1, 'ماركت': 1, 'بيتزا': 1, 'برجر': 1, 'شاورما': 1, 'فتنس': 1 };
  function dl(a, b) {             // Damerau-Levenshtein (optimal string alignment)
    var m = a.length, n = b.length, d = [], i, j;
    for (i = 0; i <= m; i++) { d[i] = [i]; } for (j = 0; j <= n; j++) d[0][j] = j;
    for (i = 1; i <= m; i++) for (j = 1; j <= n; j++) {
      var c = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
      if (i > 1 && j > 1 && a.charAt(i - 1) === b.charAt(j - 2) && a.charAt(i - 2) === b.charAt(j - 1)) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
    return d[m][n];
  }
  var RATE_CUE = { 'تقييم': 1, 'تقييمه': 1, 'تقييمها': 1, 'بتقييم': 1, 'فوق': 1, 'اعلى': 1, 'rating': 1, 'rated': 1, 'above': 1 };
  var AFTER_NUM_BAD = { 'نجوم': 1, 'نجمه': 1, 'stars': 1, 'star': 1, 'دقايق': 1, 'دقائق': 1, 'دقيقه': 1, 'minutes': 1, 'ونص': 1, 'ونصف': 1 };

  // tourist / entertainment places (OpenStreetMap data): service ids used by the page
  var ATTR = [
    ['fun', ['ملاهي', 'العاب', 'ترفيه', 'ترفيهي', 'ترفيهيه', 'تسليه', 'وناسه', 'فعاليات', 'بوليفارد', 'سينما', 'سينمات', 'افلام', 'مسرح', 'مسرحيه', 'amusement', 'entertainment', 'fun', 'cinema', 'cinemas', 'movies', 'theatre', 'theater', 'boulevard', 'karting', 'كارتينج', 'بولينج', 'bowling', 'حديقه الحيوانات', 'zoo']],
    ['mall', ['مول', 'مولات', 'تسوق', 'شوبنق', 'mall', 'malls', 'shopping', 'مجمع تجاري', 'مراكز تجاريه']],
    ['park', ['حديقه', 'حدائق', 'منتزه', 'منتزهات', 'ممشى', 'ممشي', 'park', 'parks', 'garden', 'walk']],
    ['sights', ['معالم', 'معلم', 'سياحي', 'سياحيه', 'سياحه', 'اماكن سياحيه', 'تاريخي', 'تاريخيه', 'تراثي', 'تراثيه', 'تراث', 'اثار', 'اثري', 'متحف', 'متاحف', 'قلعه', 'الدرعيه', 'المصمك', 'museum', 'museums', 'heritage', 'historic', 'historical', 'sights', 'landmarks', 'attractions', 'tourist']]];
  var ATTR_KEYS = [], ATTR_W = {};
  ATTR.forEach(function (a) { a[1].forEach(function (w) { var k = tokenize(w); if (k.length) { ATTR_KEYS.push([k.join(' '), k.length, a[0]]); k.forEach(function (x) { ATTR_W[x] = 1; }); } }); });
  ATTR_KEYS.sort(function (a, b) { return b[1] - a[1]; });
  // trip planning («جدول ٣ ايام»، «وش اسوي في الرياض»، «plan my trip»)
  var TRIP_W = { 'مرشد': 1, 'المرشد': 1, 'انبسط': 1, 'نستانس': 1, 'استانس': 1, 'اتونس': 1, 'نتونس': 1, 'جدول': 1, 'جدولي': 1, 'جدوله': 1, 'خطه': 1, 'خطتي': 1, 'برنامج': 1, 'رحله': 1, 'رحلتي': 1, 'جوله': 1, 'itinerary': 1, 'plan': 1, 'trip': 1, 'schedule': 1, 'tour': 1, 'sightseeing': 1, 'رتب': 1, 'رتبلي': 1, 'نظم': 1 };
  var TRIP_2 = { 'وش اسوي': 1, 'ايش اسوي': 1, 'وين اروح': 1, 'وين نروح': 1, 'وش نسوي': 1, 'what to': 1, 'things to': 1, 'where to': 1, 'وين اطلع': 1, 'وين نطلع': 1 };
  var DAY_W = { 'يوم': 1, 'ايام': 1, 'days': 1, 'day': 1, 'ليالي': 1, 'ليله': 1, 'nights': 1, 'night': 1, 'يومين': 1, 'ليلتين': 1, 'اسبوع': 1, 'week': 1 };
  var INTEREST = { heritage: ['تاريخ', 'تاريخي', 'تاريخيه', 'تراث', 'تراثي', 'تراثيه', 'قديم', 'قديمه', 'اثار', 'اثري', 'الدرعيه', 'درعيه', 'المصمك', 'history', 'historical', 'heritage', 'culture', 'ثقافه', 'ثقافي'],
    museum: ['متحف', 'متاحف', 'museum', 'museums'],
    fun: ['ملاهي', 'العاب', 'ترفيه', 'ترفيهي', 'تسليه', 'وناسه', 'مغامره', 'فعاليات', 'بوليفارد', 'اطفال', 'والاطفال', 'عيال', 'بزران', 'عائله', 'للعائله', 'عائلي', 'عائلتي', 'kids', 'family', 'fun', 'amusement', 'entertainment'],
    show: ['سينما', 'افلام', 'مسرح', 'مسرحيات', 'حفلات', 'cinema', 'movies', 'theatre', 'concerts'],
    mall: ['تسوق', 'مول', 'مولات', 'شوبنق', 'shopping', 'mall', 'malls'],
    park: ['حدائق', 'حديقه', 'منتزه', 'منتزهات', 'طبيعه', 'مشي', 'ممشى', 'parks', 'park', 'nature', 'walking'] };
  var INT_IDX = {}; Object.keys(INTEREST).forEach(function (k) { INTEREST[k].forEach(function (w) { INT_IDX[normalize(w)] = k; }); });
  // words that are never part of a hotel name in these sentences
  var NOT_HOTEL = { 'الرياض': 1, 'بالرياض': 1, 'riyadh': 1, 'احب': 1, 'نحب': 1, 'like': 1, 'love': 1, 'اسوي': 1, 'نسوي': 1, 'اروح': 1, 'نروح': 1, 'عندي': 1, 'عندنا': 1, 'سوي': 1, 'لي': 1, 'هادي': 1, 'هاديه': 1, 'رايق': 1 };
  // «التاريخية»، «والمندي»، «واحب» → match the word lists without the article / conjunction
  var LEX_ALL = {};
  [CUI_KEYS.map(function (x) { return x[0]; }), Object.keys(ATTR_W), Object.keys(UNSUP_IDX), Object.keys(INT_IDX), Object.keys(TRIP_W), Object.keys(DAY_W), Object.keys(NOT_HOTEL)].forEach(function (l) { l.forEach(function (w) { w.split(' ').forEach(function (x) { LEX_ALL[x] = 1; }); }); });
  function stripCl(t) {
    if (LEX_ALL[t]) return t;
    var c = [t.replace(/^وال/, ''), t.replace(/^ال/, ''), t.replace(/^و/, ''), t.replace(/^بال/, ''), t.replace(/^لل/, '')];
    for (var i = 0; i < c.length; i++) if (c[i] !== t && c[i].length >= 3 && LEX_ALL[c[i]]) return c[i];
    return t;
  }
  function tripWord(t) { t = stripCl(t); return !!(LEX_ALL[t] && !CUE_W[t]); }   // trip / interest / food / city words are never a hotel name
  function detectTrip(toks) {
    toks = toks.map(stripCl);
    var hit = false, days = null, i;
    for (i = 0; i < toks.length; i++) {
      var t = toks[i], two = t + ' ' + (toks[i + 1] || '');
      if (TRIP_W[t] || TRIP_2[two]) hit = true;
      if (t === 'يومين' || t === 'ليلتين') days = 2;
      if (t === 'اسبوع' || t === 'week') days = 7;
      if ((t === 'يوم' || t === 'ايام' || t === 'days' || t === 'day' || t === 'ليالي' || t === 'nights') && i > 0) { var pv = toks[i - 1], v = isNum(pv) ? parseFloat(pv) : NUMW[pv]; if (v != null && v >= 1 && v <= 14) days = Math.round(v); }
      if ((t === 'يوم' || t === 'day') && toks[i + 1] && /^(واحد|واحده|one)$/.test(toks[i + 1])) days = 1;
    }
    var visitVerb = toks.some(function (t) { return /^(اروح|ازور|نزور|نروح|اطلع|visit|explore|اقضي|نقضي|بقعد|بجلس|جالس|اسوي|نسوي|عندي|عندنا|ساكن|ساكنين|نازل|نازلين|الرياض|بالرياض|riyadh|معي|معنا|زياره|زيارتي|visiting|staying)$/.test(t); });
    if (!hit && !(days && visitVerb)) return null;
    var interests = [];
    toks.forEach(function (t) { var k = INT_IDX[t]; if (k && interests.indexOf(k) < 0) interests.push(k); });
    if (interests.indexOf('fun') >= 0 && /اطفال|عيال|بزران|عائل|kids|family/.test(toks.join(' ')) && interests.indexOf('park') < 0) interests.push('park');
    var relaxed = toks.some(function (t) { return /^(هادي|هاديه|مريح|مريحه|رايق|relaxed|chill|slow)$/.test(t); });
    return { days: days, interests: interests, pace: relaxed ? 'relaxed' : 'normal' };
  }

  /* ---------- end-to-end parse ---------- */
  function Engine(model, hotels, brands, opts) {
    this.model = model;
    var al = opts && opts.hotelAliases;
    if (al && hotels) hotels = hotels.map(function (h) {
      var nm = normalize((h.n || '') + ' ' + (h.a || '')), alts = (h.alts || []).slice();
      Object.keys(al).forEach(function (key) { if (nm.indexOf(normalize(key)) >= 0) alts = alts.concat(al[key]); });
      return alts.length ? Object.assign({}, h, { alts: alts }) : h;
    });
    this.matcher = new Matcher(hotels || [], { perAlt: true });
    this.lex = {}; (model.lex || []).forEach(function (t) { this.lex[t] = 1; }, this);
    this.brands = brands || [];
    this.brandById = {}; this.aliasMap = {};
    var self = this, bl = [];
    this.brands.forEach(function (b) {
      self.brandById[b.id] = b;
      b.aliases.forEach(function (a) { var k = tokenize(a).join(' '); if (k && !self.aliasMap[k]) self.aliasMap[k] = b; });
      bl.push({ disp: b.id, n: b.disp, alts: b.aliases });
    });
    this.brandMatcher = new Matcher(bl);
    var seeds = this.brands.filter(function (b) { return b.seed; });
    this.seedMatcher = new Matcher(seeds.map(function (b) { return { disp: b.id, n: b.disp, alts: b.aliases }; }));
    this.seedAliases = [];
    seeds.forEach(function (b) { b.aliases.forEach(function (a) { var t = tokenize(a); if (t.length === 1 && t[0].length >= 5) self.seedAliases.push([t[0], b]); }); });
  }
  // typo-tolerant chain detection, restricted to well-known (seed) chains: «ستاربك»، «دنكين»، «ماكدونلز»
  Engine.prototype.fuzzyBrand = function (toks, tags) {
    var best = null, bs = 0;
    for (var i = 0; i < toks.length; i++) {
      var t = toks[i];
      if (t.length < 4 || isNum(t) || NOT_BRAND[t] || NEARME1[t] || UNSUP_IDX[t] || (tags[i] !== 'O' && tags[i].slice(2) !== 'BRAND')) continue;
      var r = this.seedMatcher.rank(t, 1), sc = r.length ? r[0].score : 0, b = r.length ? this.brandById[r[0].disp] : null;
      if (sc < 0.76) {
        for (var j = 0; j < this.seedAliases.length; j++) {
          var a = this.seedAliases[j][0], lim = Math.max(a.length, t.length) >= 8 ? 2 : (Math.min(a.length, t.length) >= 5 ? 1 : 0);
          if (lim && Math.abs(a.length - t.length) <= lim && dl(a, t) <= lim) { sc = 0.8; b = this.seedAliases[j][1]; break; }
        }
      }
      if (sc >= 0.76 && sc > bs && this.matcher.rank(t, 1).every(function (h) { return h.score < 0.8; })) { bs = sc; best = { brand: b, score: sc, text: t }; }
    }
    return best;
  };
  // exact alias scan over token n-grams: catches «دانكن» even when the tagger misses it
  Engine.prototype.scanBrand = function (toks) {
    for (var n = Math.min(3, toks.length); n >= 1; n--)
      for (var i = 0; i + n <= toks.length; i++) {
        var k = toks.slice(i, i + n).join(' '), b = this.aliasMap[k];
        if (b && (k.length >= 3 || n > 1)) return { brand: b, span: [i, i + n], text: k };
      }
    return null;
  };
  Engine.prototype.parse = function (text) {
    var M = this.model, toks = tokenize(text), out = { text: text, tokens: toks };
    if (!toks.length) return out;
    var sv = classify(M.service, toks), so = classify(M.sort, toks), tags = tagTokens(M.tagger, toks, this.lex), sp = spans(toks, tags);
    out.service = sv.label; out.serviceConf = sv.conf; out.sort = so.label; out.sortConf = so.conf; out.tags = tags;
    function first(kind) { return sp[kind] && sp[kind][0] ? sp[kind][0].toks : null; }
    var c = first('COUNT'); if (c) { var q = parseQuantity(c); if (q.num != null && q.num >= 1 && q.num <= 50) out.k = Math.round(q.num); }
    var d = first('DIST');
    if (d) { var qd = parseQuantity(d); if (qd.num != null) { var km = qd.unit === 'm' ? qd.num / 1000 : (qd.unit === 'km' ? qd.num : (qd.num >= 50 ? qd.num / 1000 : qd.num)); if (km > 0 && km <= 50) out.maxkm = Math.round(km * 1000) / 1000; } }
    var r = first('RATE'); if (r) { var qr = parseQuantity(r); if (qr.num != null && qr.num > 0 && qr.num <= 5) out.minr = qr.num; }
    // near me
    var nearIdx = {};
    toks.forEach(function (t, i) { if (NEARME1[t] && !((t === 'البيت' || t === 'المنزل') && /^(اغراض|اهل|ادوات|مستلزمات|لوازم)$/.test(toks[i - 1] || ''))) nearIdx[i] = 1; if (i + 1 < toks.length && NEARME2[t + ' ' + toks[i + 1]]) { nearIdx[i] = 1; nearIdx[i + 1] = 1; } if (i + 2 < toks.length && NEARME2[t + ' ' + toks[i + 1] + ' ' + toks[i + 2]]) { nearIdx[i] = nearIdx[i + 1] = nearIdx[i + 2] = 1; } });
    if (Object.keys(nearIdx).length) out.nearMe = true;
    // unsupported service (pharmacy, mosque …)
    for (var ui = 0; ui < toks.length; ui++) { var ut = stripCl(toks[ui]); if (UNSUP_IDX[ut]) { out.unsupported = UNSUP_IDX[ut]; break; } }
    // count written as a word/number that the tagger missed («خمس مطاعم»)
    if (out.k == null) for (var ci = 0; ci < toks.length; ci++) {
      var tg = tags[ci].slice(2), tk = toks[ci];
      if (tg === 'DIST' || tg === 'RATE' || tg === 'COUNT' || tg === 'HOTEL') continue;
      var val = isNum(tk) ? parseFloat(tk) : (NUMW[tk] != null ? NUMW[tk] : null);
      if (val == null || val !== Math.round(val) || val < 1 || val > 50) continue;
      var nx = toks[ci + 1], pv = toks[ci - 1];
      if (!nx || UNIT_M[nx] || UNIT_KM[nx] || AFTER_NUM_BAD[nx] || (pv && RATE_CUE[pv])) continue;
      out.k = val; tags[ci] = 'B-COUNT'; break;
    }
    // ---- brand / named place (دانكن، ستاربكس، ...)
    var bt = first('BRAND'), bm = null, scan = this.scanBrand(toks);
    if (bt && bt.every(function (t) { return NUMW[t] != null || isNum(t) || nearIdxHas(t); })) bt = null;   // «خمس» / «مني» are not brands
    function nearIdxHas(t) { return !!(NEARME1[t] || t === 'near' || t === 'me'); }
    if (scan) bm = { brand: scan.brand, score: 1, text: scan.text };
    else if (bt && this.brands.length) { var br = this.brandMatcher.rank(bt.join(' '), 3); if (br.length && br[0].score >= 0.75) bm = { brand: this.brandById[br[0].disp], score: br[0].score, text: bt.join(' ') }; else out.brandText = bt.join(' '); }
    if (!bm && this.brands.length) { var fz = this.fuzzyBrand(toks, tags); if (fz) { bm = fz; out.brandFixed = fz.text; } }
    if (bm) {
      out.brand = { id: bm.brand.id, disp: bm.brand.disp, match: bm.brand.match, cats: Object.keys(bm.brand.cats).filter(function (c) { return bm.brand.cats[c] >= 0.1 * bm.brand.n; }).sort(function (a, b2) { return bm.brand.cats[b2] - bm.brand.cats[a]; }), score: bm.score, text: bm.text };
      out.service = 'brand'; out.serviceConf = 1;
    }
    // food / cafe type → searched by place name («مطعم شاورما»، «قهوة مختصة»)
    var btoks = toks.map(stripCl);
    if (!bm) {
      var ntext = ' ' + btoks.join(' ') + ' ';
      for (var cu = 0; cu < CUI_KEYS.length; cu++) if (ntext.indexOf(' ' + CUI_KEYS[cu][0] + ' ') >= 0) {
        var ce = CUI_KEYS[cu][2];
        if (ce[3].length === 1 && out.service !== ce[3][0] && out.service !== 'all' && (out.serviceConf || 0) > 0.9 && ce[0] !== 'breakfast') continue;   // e.g. «نادي» + «دجاج» → keep gym
        out.cuisine = { id: 'cuisine_' + ce[0], disp: ce[1], match: ce[2].map(function (w) { return tokenize(w).join(' '); }), cats: ce[3] };
        if (ce[3].length === 1) { out.service = ce[3][0]; out.serviceConf = Math.max(out.serviceConf || 0, 0.95); }
        else if (out.service !== 'restaurant' && out.service !== 'cafe') { out.service = ce[3][0]; out.serviceConf = Math.max(out.serviceConf || 0, 0.9); }
        break;
      }
    }
    // tourist / entertainment places
    if (!bm && !out.cuisine) {
      var at = ' ' + btoks.join(' ') + ' ';
      for (var ai = 0; ai < ATTR_KEYS.length; ai++) if (at.indexOf(' ' + ATTR_KEYS[ai][0] + ' ') >= 0) { out.attraction = ATTR_KEYS[ai][2]; out.service = out.attraction; out.serviceConf = 0.95; break; }
    }
    out.trip = detectTrip(toks);
    if (out.trip) { out.serviceConf = Math.max(out.serviceConf || 0, 0.9); }
    if (out.unsupported && !bm && !out.cuisine && !out.attraction) { out.serviceConf = 0; }
    // first hotel span that is still a name once «near me» / city / trip words are dropped («في الرياض … ساكن في ماريوت»)
    var h = null;
    (sp.HOTEL || []).some(function (span) {
      var t = span.toks.filter(function (w) { return !tripWord(w) && !nearIdxHas(w) && !CUE_W[w]; });
      if (t.length) { h = t; return true; } return false;
    });
    var self = this;
    function rankH(words) {
      var rk = self.matcher.rank(words.join(' '), 6), w2 = words.slice();
      if (w2.length && /^\u0644[\u0621-\u064a]{3,}/.test(w2[0]) && w2[0] !== '\u0644\u0644') { w2[0] = w2[0].slice(1); var rk2 = self.matcher.rank(w2.join(' '), 6); if (rk2.length && (!rk.length || rk2[0].score > rk[0].score)) rk = rk2; }
      return rk;
    }
    var rk = h ? rankH(h) : [];
    if (h && (!rk.length || rk[0].score < 0.6)) {                // weak span: try it with the word before it («لدبل تري»)
      var at = toks.indexOf(h[0]);
      if (at > 0 && tags[at - 1] === 'O') { var hx = [toks[at - 1]].concat(h), rx = rankH(hx); if (rx.length && (!rk.length || rx[0].score > rk[0].score + 0.05)) { h = hx; rk = rx; } }
    }
    if (!h || !rk.length || rk[0].score < 0.5) {
      var fb = this.hotelFallback(toks, tags, bm, nearIdx);
      if (fb) { var rf = rankH(fb); if (rf.length && (!rk.length || rf[0].score > rk[0].score)) { h = fb; rk = rf; } }
    }
    if (h) {
      out.hotelText = h.join(' ');
      out.hotelCandidates = rk;
      if (rk.length && rk[0].score >= 0.5) out.hotel = rk[0];
    }
    return out;
  };
  // tagger missed the hotel: try single tokens / bigrams that are not already a brand/distance/count/rating span, with a high bar
  Engine.prototype.hotelFallback = function (toks, tags, bm, nearIdx) {
    var best = null, bs = 0.78, i, n, txt, w, rk;
    for (n = 2; n >= 1; n--) for (i = 0; i + n <= toks.length; i++) {
      var ok = true; for (var j = i; j < i + n; j++) if ((tags[j] !== 'O' && !(tags[j].slice(2) === 'BRAND' && !bm)) || isNum(toks[j]) || (nearIdx && nearIdx[j]) || tripWord(toks[j]) || NUMW[toks[j]] != null) ok = false;
      if (!ok) continue;
      w = toks.slice(i, i + n);
      if (bm && bm.text && w.join(' ').indexOf(bm.text) >= 0) continue;
      var cands = [w]; if (/^\u0644[\u0621-\u064a]{3,}/.test(w[0]) && w[0] !== '\u0644\u0644') { var w2 = w.slice(); w2[0] = w2[0].slice(1); cands.push(w2); }
      for (var c = 0; c < cands.length; c++) {
        txt = cands[c].join(' '); if (txt.length < 4) continue;
        rk = this.matcher.rank(txt, 1);
        if (rk.length && rk[0].score > bs) { bs = rk[0].score; best = cands[c]; }
      }
    }
    return best;
  };
  Engine.prototype.suggest = function (text, n) { return this.matcher.rank(text, n || 3); };

  return { normalize: normalize, keyWords: keyWords, CUISINE: CUISINE, UNSUP: UNSUP, ATTR: ATTR, INTEREST: INTEREST, tokenize: tokenize, skeletonWord: skeletonWord, Engine: Engine, Matcher: Matcher, parseQuantity: parseQuantity, sentFeats: sentFeats, tagFeats: tagFeats, classify: classify, tagTokens: tagTokens };
});
