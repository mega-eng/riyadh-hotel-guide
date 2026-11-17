/* Finder + Dialog — turns a parsed query (nlp_core.js) into an answer, and asks for what is missing (hotel name).
   Runs in browser and Node. POI rows: [name, lat, lng, rating|null, reviews|null]; hotels: {n, a, lat, lng}. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./nlp_core.js'));
  else root.HotelFinder = factory(root.HotelNLP);
})(typeof self !== 'undefined' ? self : this, function (N) {
  'use strict';
  var CATS = ['restaurant', 'cafe', 'gym', 'supermarket', 'laundry'];
  var CAT_AR = { restaurant: 'مطعم', cafe: 'كافيه', gym: 'نادي', supermarket: 'سوبرماركت', laundry: 'مغسلة' };

  function haversine(a, b, c, d) {
    var R = 6371, r = Math.PI / 180, dLat = (c - a) * r, dLng = (d - b) * r;
    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a * r) * Math.cos(c * r) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function clean(s) { return N.normalize(s).replace(/['’`´]/g, '').replace(/[^a-z\u0621-\u064a0-9 ]/g, ' ').replace(/\s+/g, ' ').trim(); }

  function Finder(poi, brands) {
    this.poi = poi; this.cache = {};
    this.names = {};
    CATS.forEach(function (c) { this.names[c] = (poi[c] || []).map(function (x) { return clean(x[0] || ''); }); }, this);
  }
  // all POIs of the given categories whose name contains one of the brand's match keys
  Finder.prototype.byBrand = function (brand, cats) {
    var out = [], self = this;
    (cats && cats.length ? cats : CATS).forEach(function (c) {
      (self.poi[c] || []).forEach(function (x, i) {
        var nm = self.names[c][i];
        for (var j = 0; j < brand.match.length; j++) if (nm.indexOf(brand.match[j]) >= 0) { out.push({ cat: c, row: x }); return; }
      });
    });
    return out;
  };
  // "smart" = rating shrunk toward 4.0 by review count (so 5.0 from 3 reviews doesn't beat 4.6 from 900), small distance penalty
  function smartScore(r, km) { var rt = r.row[3], v = r.row[4] || 0; if (rt == null) return 3.2 - 0.1 * km; return (rt * v + 4.0 * 25) / (v + 25) - 0.12 * km; }

  Finder.prototype.search = function (q, hotel) {
    var self = this, cands;
    if (q.brand) cands = this.byBrand(q.brand, q.brand.cats);
    else if (q.service && q.service !== 'all') cands = (this.poi[q.service] || []).map(function (x) { return { cat: q.service, row: x }; });
    else { cands = []; CATS.forEach(function (c) { (self.poi[c] || []).forEach(function (x) { cands.push({ cat: c, row: x }); }); }); }
    var lat = hotel.lat, lng = hotel.lng, k = q.k || (q.service === 'all' ? 5 : 3);
    cands.forEach(function (r) { r.km = haversine(lat, lng, r.row[1], r.row[2]); });
    var radius = q.maxkm != null ? q.maxkm : (q.sort === 'smart' ? 5 : Infinity);
    var okRate = function (r) { return q.minr == null || (r.row[3] != null && r.row[3] >= q.minr); };
    var inR = cands.filter(function (r) { return r.km <= radius && okRate(r); });
    if (inR.length < k && q.maxkm == null) inR = cands.filter(okRate);        // user gave no radius: widen instead of returning too few
    cands = inR;
    if (q.service === 'all' && !q.brand) {                    // one best per category
      var out = [];
      CATS.forEach(function (c) { var l = cands.filter(function (r) { return r.cat === c; }).sort(function (a, b) { return a.km - b.km; }); if (l[0]) out.push(l[0]); });
      return out;
    }
    if (q.sort === 'smart') { cands.forEach(function (r) { r.score = smartScore(r, r.km); }); cands.sort(function (a, b) { return b.score - a.score; }); }
    else cands.sort(function (a, b) { return a.km - b.km; });
    return cands.slice(0, k);
  };

  /* ---------------- dialog ---------------- */
  function fmtKm(km) { return km < 1 ? Math.round(km * 1000) + ' م' : km.toFixed(1) + ' كم'; }
  function describe(q) {
    if (q.brand) return (q.sort === 'smart' ? 'أفضل ' : 'أقرب ') + q.brand.disp;
    if (q.service === 'all') return 'الخدمات القريبة';
    return (q.sort === 'smart' ? 'أفضل ' : 'أقرب ') + CAT_AR[q.service];
  }
  function Dialog(engine, finder) { this.e = engine; this.f = finder; this.ctx = { hotel: null }; this.pending = null; }

  // returns {type, message, results?, choices?, hotel?, query?}
  Dialog.prototype.say = function (text) {
    var e = this.e, p = this.pending, q, hotelTextOnly = false;
    if (p) {                                          // we asked for a hotel (or to pick one) — try the reply as a hotel first
      var rk = e.matcher.rank(text, 6);
      var looksLikeNewQuery = e.parse(text);
      if (hasIntent(looksLikeNewQuery) && looksLikeNewQuery.hotel == null && !(rk[0] && rk[0].score >= 0.7 && N.tokenize(text).length <= 4)) { p = null; this.pending = null; }
      else if (p) {
        var pick = this.pickFromChoices(text, p.choices);
        var h = pick || (rk[0] && rk[0].score >= 0.5 ? rk[0].hotel : null);
        var amb = !pick && h ? ambiguousHotels(rk) : null;
        if (amb) return this.clarify(p.q, amb.map(function (x) { return x.hotel; }));
        if (!h) return { type: 'ask_hotel', message: 'ما قدرت أحدد الفندق. اكتب اسمه كما تعرفه (مثلاً: هيلتون، ماريوت، فورسيزونز).', query: p.q };
        q = p.q; this.pending = null; this.ctx.hotel = h; return this.answer(q, h);
      }
    }
    q = e.parse(text);
    if (!hasIntent(q)) {
      // no service at all: maybe the user just named a hotel (set context) or typed something we don't understand
      var r2 = e.matcher.rank(text, 3);
      if (r2[0] && r2[0].score >= 0.6) { this.ctx.hotel = r2[0].hotel; return { type: 'hotel_set', hotel: r2[0].hotel, message: 'تمام، الفندق: ' + (r2[0].hotel.n || r2[0].hotel.a) + '. وش تبغى أدور لك قريب منه؟ (مطعم، كافيه، دانكن، نادي…)' }; }
      return { type: 'not_understood', message: 'ما فهمت طلبك. جرب مثلاً: «اقرب دانكن من فندق هيلتون» أو «افضل 3 كافيهات جنب ماريوت».' };
    }
    if (q.hotel) {
      var c = q.hotelCandidates || [], top = c[0];
      var tie = ambiguousHotels(c);
      if (tie) return this.clarify(q, tie.map(function (x) { return x.hotel; }));
      this.ctx.hotel = top.hotel; return this.answer(q, top.hotel);
    }
    if (this.ctx.hotel && !q.hotelText) { var a = this.answer(q, this.ctx.hotel); a.assumedHotel = true; a.message += '\n(حسبتها من نفس الفندق السابق؛ لو تقصد فندق ثاني اذكر اسمه.)'; return a; }   // follow-up in the same conversation: reuse the hotel
    this.pending = { q: q };
    return { type: 'ask_hotel', message: 'تمام، ' + describe(q) + ' — بس في أي فندق إنت؟ اكتب اسم الفندق.', query: q };
  };
  function ambiguousHotels(rk) {
    if (!rk.length || rk[0].score >= 0.98) return null;
    var tie = rk.filter(function (x) { return x.score >= 0.5 && x.score >= rk[0].score - 0.3; });
    return tie.length > 1 ? tie : null;
  }
  function hasIntent(q) { return !!(q.brand || (q.service && (q.serviceConf || 0) >= 0.7)); }
  Dialog.prototype.clarify = function (q, hotels) {
    hotels = hotels.slice(0, 4); this.pending = { q: q, choices: hotels };
    return { type: 'clarify_hotel', message: 'لقيت أكثر من فندق بهذا الاسم، أي واحد تقصد؟', choices: hotels.map(function (h) { return h.n || h.a; }), hotels: hotels, query: q };
  };
  Dialog.prototype.pickFromChoices = function (text, choices) {
    if (!choices) return null;
    var t = N.tokenize(text), num = t.length === 1 && /^[1-9]$/.test(t[0]) ? +t[0] : null;
    if (num && choices[num - 1]) return choices[num - 1];
    var best = null, bs = 0, kw = N.keyWords(text);
    choices.forEach(function (h) { var nm = clean(h.n || h.a), s = kw.filter(function (w) { return nm.indexOf(w) >= 0; }).length; if (s > bs) { bs = s; best = h; } });
    return bs ? best : null;
  };
  Dialog.prototype.answer = function (q, hotel) {
    var res = this.f.search(q, hotel), hn = hotel.n || hotel.a;
    if (!res.length) {
      var hint = q.brand ? ' ما لقيت فرع ' + q.brand.disp + (q.maxkm != null ? ' ضمن ' + fmtKm(q.maxkm) : '') + ' قريب من ' + hn + '. جرب توسع المسافة.' : ' ما لقيت نتائج مطابقة قريبة من ' + hn + '.';
      return { type: 'no_results', message: hint.trim(), hotel: hotel, query: q };
    }
    var lines = res.map(function (r, i) { return (i + 1) + '. ' + r.row[0] + ' — ' + fmtKm(r.km) + (r.row[3] != null ? ' — ' + r.row[3] + '★' : ''); });
    return { type: 'results', message: describe(q) + ' من ' + hn + ':\n' + lines.join('\n'), results: res, hotel: hotel, query: q };
  };
  return { Finder: Finder, Dialog: Dialog, haversine: haversine };
});
