"""
Injects the v2 NLP (brand search + dialog) into the single-file page.
Usage: python3 build_page.py page.html out.html     (needs model.json, brands.json, metrics.json, nlp_core.js, finder.js)
Edits the page's main script in 4 small places (brand-aware render), swaps the NLP code/model, replaces the UI glue.
"""
import json, re, sys
src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding='utf8').read()
def rep(s, old, new, count=1):
    assert s.count(old) == count, (old[:60], s.count(old))
    return s.replace(old, new)

SC = re.compile(r'<script(?![^>]*application/json)[^>]*>.*?</script>', re.S)
scripts = [(m.start(), m.end()) for m in SC.finditer(h)]
assert len(scripts) == 3
main, core, glue = (h[a:b] for a, b in scripts)

# ---- 1) main script: brand-aware search/render
main = rep(main, "  window.__nearestAll = nearestAll;\n", """  window.__nearestAll = nearestAll;

  // brand / named place (دانكن، ستاربكس…): nearest (or best) branches across the brand's categories
  var BFIND = null;
  function nearestBrand(lat, lng, brand, k, maxKm, minRating, smart) {
    if (!BFIND) BFIND = new HotelFinder.Finder(P);
    var rows = BFIND.byBrand(brand, brand.cats).map(function (x) {
      var d = haversine(lat, lng, x.row[1], x.row[2]), dk = Math.round(d * 100) / 100;
      return { name: x.row[0], lat: x.row[1], lng: x.row[2], rating: x.row[3], n: x.row[4], d: dk, exact: d, walk: Math.round(dk * 1.3 / 5 * 60), cat: x.cat };
    });
    if (maxKm != null) rows = rows.filter(function (r) { return r.d <= maxKm; });
    if (minRating != null) rows = rows.filter(function (r) { return r.rating != null && r.rating >= minRating; });
    if (smart) {
      var m = 20;
      rows.forEach(function (r) {
        var C = MEAN[r.cat] || 4, v = r.n || 0, R = r.rating == null ? C : r.rating, bayes = (v / (v + m)) * R + (m / (v + m)) * C;
        r.score = 0.5 * Math.exp(-r.d / 1.0) + 0.5 * (bayes - 1) / 4;
      });
      rows.sort(function (a, b) { return b.score - a.score; });
    } else rows.sort(function (a, b) { return a.exact - b.exact; });
    return rows.slice(0, k);
  }
  window.__setBrand = function (b) {
    st.brand = b || null;
    if (b) {
      st.svc = b.cats[0] || st.svc;
      Array.prototype.forEach.call($('chips').children, function (c) { c.setAttribute('aria-pressed', false); });
    }
    render();
  };
""")
main = rep(main, "results = st.svc === 'all' ? nearestAll(h.lat, h.lng, k, mkm, mrt, sm) : nearest(h.lat, h.lng, st.svc, k, mkm, mrt, sm);",
  "results = st.brand ? nearestBrand(h.lat, h.lng, st.brand, k, mkm, mrt, sm) : (st.svc === 'all' ? nearestAll(h.lat, h.lng, k, mkm, mrt, sm) : nearest(h.lat, h.lng, st.svc, k, mkm, mrt, sm));")
main = rep(main, "$('legend').hidden = st.svc !== 'all';", "$('legend').hidden = st.brand ? true : st.svc !== 'all';")
main = rep(main, "$('rtitle').textContent = st.svc === 'all' ?", "$('rtitle').textContent = st.brand ? (st.sort === 'smart' ? 'أفضل ' : 'أقرب ') + st.brand.disp + (st.sort === 'smart' ? ' قرب ' : ' لـ ') + h.disp : st.svc === 'all' ?")
main = rep(main, "if (st.svc === 'all' && results.length) {", "if (!st.brand && st.svc === 'all' && results.length) {")
main = rep(main, "      st.svc = s[0];\n      Array.prototype", "      st.svc = s[0]; st.brand = null;\n      Array.prototype")
# directions from the hotel (or the user's position) instead of a bare pin; walking under 1.5 km
main = rep(main, "  function mapsUrl(lat, lng) { return 'https://www.google.com/maps/search/?api=1&query=' + lat + ',' + lng; }",
  "  function mapsUrl(lat, lng) {\n    var h = st.hotel; if (!h) return 'https://www.google.com/maps/search/?api=1&query=' + lat + ',' + lng;\n    var d = haversine(h.lat, h.lng, lat, lng);\n    return 'https://www.google.com/maps/dir/?api=1&origin=' + h.lat + '%2C' + h.lng + '&destination=' + lat + '%2C' + lng + '&travelmode=' + (d <= 1.5 ? 'walking' : 'driving');\n  }")
main = rep(main, "el('a', 'go', 'الخريطة')", "el('a', 'go', 'الاتجاهات')")
main = rep(main, "var SVC = [['all', 'الكل'], ['restaurant', 'مطعم'], ['cafe', 'كافيه'], ['gym', 'نادي'], ['supermarket', 'سوبرماركت'], ['laundry', 'مغسلة']];",
  "var SVC = [['all', 'الكل'], ['restaurant', 'مطعم'], ['cafe', 'كافيه'], ['gym', 'نادي'], ['supermarket', 'سوبرماركت'], ['laundry', 'مغسلة'], ['sights', 'معالم'], ['fun', 'ترفيه'], ['mall', 'مولات'], ['park', 'حدائق']];")
main = rep(main, "    MEAN[s] = t / c;", "    MEAN[s] = c ? t / c : 4;   // OpenStreetMap places have no ratings")
main = rep(main, "var GRP = { restaurant: 'المطاعم', cafe: 'الكافيهات', gym: 'النوادي', supermarket: 'السوبرماركت', laundry: 'المغاسل' };",
  "var GRP = { restaurant: 'المطاعم', cafe: 'الكافيهات', gym: 'النوادي', supermarket: 'السوبرماركت', laundry: 'المغاسل', sights: 'المعالم', fun: 'الترفيه', mall: 'المولات', park: 'الحدائق' };")
main = rep(main, "  window.__nearestAll = nearestAll;\n", "  window.__nearestAll = nearestAll;\n  window.__P = P;\n")
main = rep(main, "  window.__setBrand = function (b) {", "  window.__setOrigin = function (o) { setHotel(o); };   // a hotel row or the user's own position {lat, lng, isLoc}\n  window.__setBrand = function (b) {")

# ---- 2) NLP model + brands data
model = json.load(open('model.json', encoding='utf8')); model['meta']['metrics'] = json.load(open('metrics.json', encoding='utf8'))
h2 = h[:scripts[0][0]] + main + h[scripts[0][1]:]
h2 = re.sub(r'(<script type="application/json" id="nlp-model">).*?(</script>)', lambda m: m.group(1) + json.dumps(model, ensure_ascii=False, separators=(',', ':')) + m.group(2), h2, flags=re.S)
brands = open('brands.json', encoding='utf8').read()
h2 = rep(h2, '<script type="application/json" id="nlp-model">', '<script type="application/json" id="brands-data">' + brands + '</script>\n<script type="application/json" id="nlp-model">')

# ---- 2b) OpenStreetMap places: four new search categories + the planner's data
places = json.load(open('places.json', encoding='utf8'))
pm = re.search(r'(<script type="application/json" id="poi-data">)(.*?)(</script>)', h2, re.S)
POI = json.loads(pm.group(2))
def nm(r): return r[4] + ' (' + r[5] + ')' if r[4] and r[5] else (r[4] or r[5])
POI['sights'] = [[nm(r), r[2], r[3], None, None] for r in places['rows'] if r[1] in ('heritage', 'museum') and r[7] == 1]
POI['fun'] = [[nm(r), r[2], r[3], None, None] for r in places['rows'] if r[1] in ('fun', 'show') and r[7] == 1]
POI['mall'] = [[nm(r), r[2], r[3], None, None] for r in places['rows'] if r[1] == 'mall']
POI['park'] = [[nm(r), r[2], r[3], None, None] for r in places['rows'] if r[1] == 'park']
h2 = h2[:pm.start(2)] + json.dumps(POI, ensure_ascii=False, separators=(',', ':')) + h2[pm.end(2):]
h2 = rep(h2, '<script type="application/json" id="brands-data">', '<script type="application/json" id="places-data">' + json.dumps(places, ensure_ascii=False, separators=(',', ':')) + '</script>\n<script type="application/json" id="brands-data">')

# ---- 3) NLP code + finder
sc = [(m.start(), m.end()) for m in SC.finditer(h2)]
core_new = '<script>\n' + open('nlp_core.js', encoding='utf8').read() + '\n</script>\n<script>\n' + open('finder.js', encoding='utf8').read() + '\n</script>\n<script>\n' + open('trip.js', encoding='utf8').read() + '\n</script>'
# ---- 4) UI glue
g = glue
g = rep(g, "function setHotel(disp) { inp.value = disp; fire(inp, 'input'); $('hsuggest').textContent = ''; }", "function setHotel(disp) { prevHotel = ''; inp.value = disp; fire(inp, 'input'); $('hsuggest').textContent = ''; afterOrigin(); }")
g = rep(g, "    if (v.length < 2 || exact[inp.value]) return;", "    return;   // v4: the dropdown list replaces these «هل تقصد» chips")
g = rep(g, "  var eng = new HotelNLP.Engine(M, rows);", "  var BR = JSON.parse($('brands-data').textContent);\n  var eng = new HotelNLP.Engine(M, rows, BR, { hotelAliases: M.hotelAliases });")
g = rep(g, "var SVC_NAME = { all:", "var SVC_NAME = { sights: 'معالم سياحية', fun: 'ترفيه', mall: 'مولات', park: 'حدائق', brand: 'علامة', all:")
g = rep(g, "return { n: h.n, a: h.a, disp: h.n || h.a }; });", "return { n: h.n, a: h.a, disp: h.n || h.a, lat: h.lat, lng: h.lng }; });")
a, b = g.index("  function ask(text) {"), g.index("  /* --- natural-language box --- */")
new_ask = r"""  var prevHotel = '';    // hotel hidden while the field is open for picking another
  var pendingTrip = null, lastTrip = null;   // a trip waiting for a hotel / the trip on screen
  var waiting = false;   // we asked «في أي فندق؟» and expect the next message to name it
  var LOC_LABEL = '📍 موقعك الحالي', myPos = null;
  var HROWS = rows.filter(function (r) { return r.lat != null; }), hav = HotelFinder.haversine;
  function hasIntent(p) { return !!(p.brand || p.cuisine || (p.service && (p.serviceConf || 0) >= 0.7)); }
  function ambiguous(rk) {                              // exact alias hits («هيلتون») tie across a hotel family → still ask
    if (!rk.length) return null;
    var top = rk[0].score, gap = top >= 0.98 ? 0.03 : 0.3;
    var t = rk.filter(function (x) { return x.score >= 0.5 && x.score >= top - gap; });
    return t.length > 1 ? t : null;
  }
  function choose(out, list) {                          // several hotels share the name: search with the best guess, offer the others
    waiting = false; setHotel(list[0].disp);
    out.appendChild(el('div', 'nlp-lbl', 'في أكثر من فندق بهذا الاسم — بحثت عن «\u2068' + list[0].disp + '\u2069». لو تقصد فندق ثاني:'));
    var row = el('div', 'nlp-alts');
    list.slice(1, 5).forEach(function (c) { row.appendChild(chipBtn(c.disp, function () { setHotel(c.disp); out.textContent = ''; out.appendChild(el('div', 'nlp-lbl', 'تمام، الفندق: ' + c.disp)); })); });
    out.appendChild(row);
  }

  /* ---------- my location (Geolocation API: needs HTTPS and the user's permission) ---------- */
  function nearestHotels(pos, n) {
    return HROWS.map(function (h) { return { h: h, d: hav(pos.lat, pos.lng, h.lat, h.lng) }; }).sort(function (a, b) { return a.d - b.d; }).slice(0, n || 3);
  }
  function locErr(code) {
    if (code === 1) return 'ما سمحت للصفحة بمعرفة موقعك. فعّل إذن الموقع من إعدادات المتصفح، أو اكتب اسم الفندق.';
    if (code === 3) return 'تأخر تحديد موقعك. جرّب مرة ثانية أو اكتب اسم الفندق.';
    if (code === 'unsupported') return 'متصفحك ما يدعم تحديد الموقع. اكتب اسم الفندق.';
    return 'ما قدر الجهاز يحدد موقعك الحين. تأكد إن خدمة الموقع شغالة، أو اكتب اسم الفندق.';
  }
  function locate(cb) {
    if (!navigator.geolocation) return cb('unsupported');
    if (myPos && Date.now() - myPos.t < 120000) return cb(null, myPos);
    navigator.geolocation.getCurrentPosition(function (p) {
      myPos = { lat: p.coords.latitude, lng: p.coords.longitude, acc: p.coords.accuracy, t: Date.now() }; cb(null, myPos);
    }, function (e) { cb(e && e.code ? e.code : 'err'); }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 120000 });
  }
  function useLocationAsOrigin(pos) {
    prevHotel = ''; inp.value = LOC_LABEL; $('hsuggest').textContent = '';
    window.__setOrigin({ disp: 'موقعك', n: 'موقعك الحالي', a: '', lat: pos.lat, lng: pos.lng, t: '', isLoc: true });
    $('hinfo').textContent = 'دقة تحديد الموقع ± ' + Math.max(1, Math.round(pos.acc || 0)) + ' م';
    afterOrigin();
  }
  function hotelChips(out, list, label, pos) {
    var row = el('div', 'nlp-alts');
    if (label) row.appendChild(el('span', 'nlp-lbl', label));
    list.forEach(function (x) { row.appendChild(chipBtn('\u2068' + x.h.disp + '\u2069' + (x.d < 0.05 ? ' · هنا' : ' · ' + kmLabel(x.d)), function () { setHotel(x.h.disp); out.textContent = ''; out.appendChild(el('div', 'nlp-lbl', 'تمام، الفندق: ' + x.h.disp)); })); });
    if (pos) row.appendChild(chipBtn(LOC_LABEL, function () { useLocationAsOrigin(pos); out.textContent = ''; out.appendChild(el('div', 'nlp-lbl', 'تمام، أبحث من موقعك الحالي.')); }));
    out.appendChild(row);
  }
  // mode 'pick' = the 📍 button (find my hotel); mode 'near' = a question like «اقرب دانكن مني»
  function fromMyLocation(out, mode, shareText) {
    var note = el('div', 'nlp-lbl', 'جاري تحديد موقعك…'); out.appendChild(note);
    locate(function (err, pos) {
      if (note.parentNode) note.parentNode.removeChild(note);
      if (err) { out.appendChild(el('div', 'nlp-warn', locErr(err))); waiting = true; return; }
      var near = nearestHotels(pos, 3);
      if (!near.length || near[0].d > 50) {
        out.appendChild(el('div', 'nlp-warn', 'موقعك خارج الرياض (أقرب فندق في البيانات على بعد ' + Math.round(near.length ? near[0].d : 0) + ' كم). البيانات حالياً لمدينة الرياض فقط، اكتب اسم فندق فيها.'));
        waiting = true; return;
      }
      waiting = false;
      if (mode === 'pick' && near[0].d <= 0.3) {
        setHotel(near[0].h.disp);
        out.appendChild(el('div', 'nlp-lbl', near[0].d < 0.05 ? 'يبدو إنك في «' + near[0].h.disp + '».' : 'يبدو إنك في «' + near[0].h.disp + '» (على بعد ' + kmLabel(near[0].d) + ' منك).'));
        hotelChips(out, near.slice(1), 'مو هو؟', pos);
        return;
      }
      useLocationAsOrigin(pos);
      out.appendChild(el('div', 'nlp-lbl', mode === 'pick' ? 'ما فيه فندق ملاصق لموقعك، فبحثت من موقعك مباشرة. أو اختر فندقك:' : 'بحثت من موقعك الحالي. لو تبغى من فندق:'));
      hotelChips(out, near, '');
      if (shareText) shareRow(out, shareText);
    });
  }

  /* ---------- shareable link: the question lives in the URL (#q=…) ---------- */
  function setShare(text) { try { history.replaceState(null, '', location.pathname + location.search + '#q=' + encodeURIComponent(text)); } catch (e) {} }
  function shareRow(out, text) {
    var r = el('div', 'nlp-alts nlp-share'), b = chipBtn('مشاركة هذا البحث', function () {
      var url = location.href;
      if (navigator.share) { navigator.share({ title: 'أقرب خدمة للفندق', text: text, url: url }).catch(function () {}); return; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { b.textContent = 'تم نسخ الرابط ✓'; }, function () { b.textContent = url; });
      else b.textContent = url;
    });
    r.appendChild(b); out.appendChild(r);
  }

  function ask(text) {
    var out = $('nlp-out'); out.textContent = '';
    text = (text || '').trim(); if (!text) return;
    var p = eng.parse(text);
    if (p.trip) { waiting = false; askTrip(out, p, text); return; }
    if (p.unsupported && !p.brand && !p.cuisine) {
      out.appendChild(el('div', 'nlp-warn', 'ما عندي بيانات «' + p.unsupported + '» حالياً. المتوفر: مطاعم، كافيهات، نوادي، سوبرماركت، مغاسل، معالم سياحية، ملاهي وترفيه، مولات، حدائق، وأسماء محلات مثل دانكن وستاربكس.'));
      return;
    }
    if (!hasIntent(p)) {
      if (p.nearMe) { p.service = 'all'; }
      else {                                               // maybe the user just typed a hotel name (reply to our question)
        var rk = eng.suggest(text, 6);
        if (rk.length && rk[0].score >= (waiting ? 0.5 : 0.6)) {
          var amb = ambiguous(rk); if (amb) return choose(out, amb);
          setHotel(rk[0].disp); waiting = false; out.appendChild(el('div', 'nlp-lbl', 'تمام، الفندق: ' + rk[0].disp)); return;
        }
        out.appendChild(el('div', 'nlp-warn', waiting ? 'ما قدرت أحدد الفندق. اكتب اسمه كما تعرفه (مثلاً: هيلتون، ماريوت، فورسيزونز).' : 'ما فهمت طلبك. جرب مثلاً: «اقرب دانكن من فندق هيلتون» أو «مطعم شاورما قريب مني».'));
        return;
      }
    }
    waiting = false; showTab('search');
    prevHotel = ''; inp.value = ''; fire(inp, 'change'); $('hsuggest').textContent = '';   // new question = fresh start: forget the previous hotel and its results
    var ambH = p.hotel ? ambiguous(p.hotelCandidates || []) : null;
    var pills = el('div', 'nlp-pills');
    if (p.brand) pills.appendChild(pill('العلامة', p.brand.disp));
    else if (p.cuisine) pills.appendChild(pill('النوع', p.cuisine.disp));
    else pills.appendChild(pill('الخدمة', SVC_NAME[p.service]));
    pills.appendChild(pill('الترتيب', p.sort === 'smart' ? 'الأفضل (قرب + تقييم)' : 'الأقرب'));
    if (p.hotel) pills.appendChild(pill('الفندق', p.hotel.disp));
    else if (p.nearMe) pills.appendChild(pill('من', 'موقعك'));
    pills.appendChild(pill('عدد النتائج', String(p.k || 5)));
    if (p.maxkm != null) pills.appendChild(pill('أقصى مسافة', kmLabel(p.maxkm)));
    if (p.minr != null) pills.appendChild(pill('أقل تقييم', String(p.minr)));
    out.appendChild(el('div', 'nlp-lbl', 'فهمت من سؤالك:')); out.appendChild(pills);
    if (p.brandFixed && p.brand) out.appendChild(el('div', 'nlp-lbl', 'صحّحت «' + p.brandFixed + '» إلى «' + p.brand.disp + '».'));

    setSelect('k', p.k || 5, String(p.k || 5));
    setSelect('maxkm', p.maxkm != null ? p.maxkm : '', p.maxkm != null ? kmLabel(p.maxkm) : '');
    setSelect('minr', p.minr != null ? p.minr : '', String(p.minr));
    var sb = document.querySelector('#sort button[data-v="' + p.sort + '"]'); if (sb) sb.click();
    if (p.brand) window.__setBrand({ id: p.brand.id, disp: p.brand.disp, match: p.brand.match, cats: p.brand.cats });
    else if (p.cuisine) window.__setBrand({ id: p.cuisine.id, disp: p.cuisine.disp, match: p.cuisine.match, cats: p.cuisine.cats });
    else { var chip = document.querySelector('#chips .chip[data-v="' + p.service + '"]'); if (chip) chip.click(); }
    setShare(text);

    if (p.nearMe && !p.hotel) { fromMyLocation(out, 'near', text); return; }
    var msg = null;
    if (p.hotel) {
      if (ambH) { choose(out, ambH); shareRow(out, text); return; }
      setHotel(p.hotel.disp);
    } else if (p.hotelText) {
      msg = 'ما قدرت أحدد الفندق «' + p.hotelText + '».';
      var cs = (p.hotelCandidates || []).filter(function (c) { return c.score >= 0.3; }).slice(0, 3);
      if (cs.length) { var r2 = el('div', 'nlp-alts'); cs.forEach(function (c) { r2.appendChild(chipBtn(c.disp, function () { setHotel(c.disp); waiting = false; })); }); out.appendChild(r2); }
      waiting = true;
    } else { msg = 'تمام، في أي فندق إنت؟ اكتب اسم الفندق، أو استخدم موقعك.'; waiting = true; }
    if (msg) {
      out.appendChild(el('div', waiting ? 'nlp-warn' : 'nlp-lbl', msg));
      if (waiting) { var lr = el('div', 'nlp-alts'); lr.appendChild(chipBtn(LOC_LABEL, function () { out.textContent = ''; fromMyLocation(out, 'near'); })); out.appendChild(lr); }
    }
    if (!waiting) shareRow(out, text);
  }

"""
g = g[:a] + new_ask + g[b:]
g = rep(g, "  /* --- \"about the model\" card --- */", r"""  /* --- hotel combobox: a custom list, because the native <datalist> barely opens on phones (used twice) --- */
  var TYPE_AR = { hotel: 'فندق', apartment: 'شقق مفروشة', hostel: 'نزل', motel: 'موتيل', resort: 'منتجع', guest_house: 'بيت ضيافة' };
  var META = {}; JSON.parse($('hotels-data').textContent).forEach(function (h) { META[h.n || h.a] = h; });
  var NORMK = rows.map(function (r) { return { r: r, k: HotelNLP.normalize((r.n || '') + ' ' + (r.a || '')) }; });
  function makeCombo(input, onPick) {
    input.removeAttribute('list');
    var dd = el('div', 'hdd'); dd.id = 'hdd-' + input.id; dd.setAttribute('role', 'listbox'); dd.setAttribute('aria-label', 'أماكن السكن'); dd.hidden = true;
    input.parentNode.appendChild(dd);
    input.setAttribute('role', 'combobox'); input.setAttribute('aria-controls', dd.id); input.setAttribute('aria-expanded', 'false'); input.setAttribute('aria-autocomplete', 'list');
    var items = [], sel = -1, fresh = false;
    function list(text) {
      var t = (text || '').trim();
      if (!t || t === LOC_LABEL || (fresh && exact[t])) {                // just opened: everything, nearest first when we know where you are
        var all = rows.slice();
        if (myPos) all.sort(function (a, b) { return hav(myPos.lat, myPos.lng, a.lat, a.lng) - hav(myPos.lat, myPos.lng, b.lat, b.lng); });
        else all.sort(function (a, b) { return a.disp.localeCompare(b.disp, 'ar'); });
        return { list: all, all: true };
      }
      var nq = HotelNLP.normalize(t), seen = {}, out = [];
      NORMK.forEach(function (x) { if (x.k.indexOf(nq) >= 0) { out.push(x.r); seen[x.r.disp] = 1; } });
      eng.suggest(t, 15).forEach(function (c) { if (c.score >= 0.35 && !seen[c.disp]) { seen[c.disp] = 1; var r = rows.filter(function (x) { return x.disp === c.disp; })[0]; if (r) out.push(r); } });
      return { list: out, all: false };
    }
    function render() {
      var res = list(input.value), L = res.list; dd.textContent = ''; items = L; sel = -1;
      dd.appendChild(el('div', 'hdd-head', !L.length ? 'ما لقيت مكان سكن بهذا الاسم' : res.all ? 'كل أماكن السكن (' + L.length + ')' + (myPos ? '، الأقرب لك أولاً' : '') : 'النتائج (' + L.length + ')'));
      L.forEach(function (r, i) {
        var m = META[r.disp] || {}, o = el('div', 'hdd-opt'); o.setAttribute('role', 'option'); o.id = dd.id + '-' + i;
        o.appendChild(el('bdi', 'hdd-nm', r.disp));
        var meta = [TYPE_AR[m.t] || 'فندق']; if (m.s) meta.push(m.s + ' نجوم'); if (m.a && m.n && m.a !== m.n) meta.push(m.a);
        if (myPos) meta.push(kmLabel(hav(myPos.lat, myPos.lng, r.lat, r.lng)));
        o.appendChild(el('span', 'hdd-meta', meta.join('، ')));
        o.addEventListener('mousedown', function (e) { e.preventDefault(); });
        o.addEventListener('click', function () { pick(i); });
        dd.appendChild(o);
      });
    }
    function open() { render(); dd.hidden = false; input.setAttribute('aria-expanded', 'true'); }
    function close() { dd.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); fresh = false; }
    function pick(i) { var r = items[i]; if (!r) return; close(); input.blur(); onPick(r); }
    function move(dir) {
      if (dd.hidden) open(); var n = items.length; if (!n) return; sel = (sel + dir + n) % n;
      Array.prototype.forEach.call(dd.querySelectorAll('.hdd-opt'), function (o, i) {
        o.classList.toggle('on', i === sel);
        if (i === sel) { if (o.scrollIntoView) o.scrollIntoView({ block: 'nearest' }); input.setAttribute('aria-activedescendant', o.id); }
      });
    }
    input.addEventListener('focus', function () { fresh = true; open(); });
    input.addEventListener('click', function () { if (dd.hidden) { fresh = true; open(); } });
    input.addEventListener('input', function () { if (document.activeElement !== input) return; fresh = false; open(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter' && !dd.hidden) { e.preventDefault(); pick(sel >= 0 ? sel : 0); }
      else if (e.key === 'Escape') close();
    });
    input.addEventListener('blur', function () { setTimeout(close, 150); });
  }
  makeCombo(inp, function (r) { setHotel(r.disp); });
  function afterOrigin() {}                       // v5: trips live in the tour-guide tab, the services hotel no longer drives them

  /* --- tabs: services search / tour guide --- */
  function showTab(name, scroll) {
    ['search', 'guide'].forEach(function (t) {
      var on = t === name; $('tab-' + t).hidden = !on;
      var b = $('tab-btn-' + t); b.setAttribute('aria-selected', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1;
    });
    if (name === 'guide' && !G.origin && inp.value && exact[inp.value]) { var r0 = rows.filter(function (x) { return x.disp === inp.value; })[0]; if (r0) setGuideOrigin({ lat: r0.lat, lng: r0.lng, disp: r0.disp }, null, true); }
    if (scroll) try { $('tabs').scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (e) {}
  }
  ['search', 'guide'].forEach(function (t) { $('tab-btn-' + t).onclick = function () { showTab(t); }; });
  $('tabs').addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var next = $('tab-search').hidden ? 'search' : 'guide'; showTab(next); $('tab-btn-' + next).focus();
  });
  $('hero-guide').onclick = function () { showTab('guide', true); };

  /* --- المرشد السياحي --- */
  var PLACES = HotelTrip.loadPlaces(JSON.parse($('places-data').textContent));
  var CHAIN_KEYS = BR.filter(function (b) { return b.seed; }).reduce(function (a, b) { return a.concat(b.match); }, []);
  var AR_DIG = function (n) { return String(n).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'[d]; }); };
  var ORD = ['الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع'];
  var DAYS_OPT = [[1, 'يوم'], [2, 'يومين'], [3, '٣ أيام'], [4, '٤ أيام'], [5, '٥ أيام'], [7, 'أسبوع']];
  var INT_OPT = [['heritage', 'تاريخ وتراث'], ['museum', 'متاحف'], ['fun', 'ترفيه وملاهي'], ['mall', 'تسوق'], ['park', 'حدائق ومشي'], ['kids', 'معي أطفال']];
  var FOOD_OPT = [['', 'أي شي'], ['mandi', 'مندي'], ['kabsa', 'كبسة'], ['grill', 'مشويات'], ['burger', 'برجر'], ['pizza', 'بيتزا'], ['sushi', 'سوشي'], ['indian', 'هندي'], ['lebanese', 'لبناني'], ['seafood', 'بحري']];
  var CUI_BY_ID = {}; (HotelNLP.CUISINE || []).forEach(function (c) { CUI_BY_ID[c[0]] = c; });
  var CAT_DOT = { heritage: 'sights', museum: 'sights', fun: 'fun', show: 'fun', mall: 'mall', park: 'park' };
  // a local guide's short, practical notes (place-specific where we are sure, otherwise by kind of place)
  var TIPS = [
    [/الطريف|turaif|الدرعية|diriyah|الغصيبة/i, 'حي الطريف في الدرعية مسجّل في قائمة اليونسكو للتراث العالمي، وجنبه مطل البجيري بمطاعمه ومقاهيه.'],
    [/المتحف الوطني|قصر المربع|murabba|national museum/i, 'مركز الملك عبدالعزيز التاريخي: المتحف الوطني وقصر المربع وحدائقهم في مكان واحد.'],
    [/المصمك|masmak|الثميري|thumairi/i, 'قلب الرياض القديمة: قلعة المصمك الطينية، وحولها سوق الزل والأسواق الشعبية.'],
    [/بوليفارد|boulevard/i, 'منطقة ترفيه ومطاعم وعروض، وتكون في أوج نشاطها وقت موسم الرياض.'],
    [/مركز المملكة|kingdom centre/i, 'في أعلى البرج جسر السماء، ومنظر الرياض منه بالليل يستاهل.'],
    [/وادي نمار/, 'سد وبحيرة وممشى، وأحلى وقت له العصر لين المغرب.'],
    [/صقر الجزيرة|sakr al jazeera/i, 'متحف طيران فيه طائرات حقيقية معروضة، يعجب الكبار والصغار.'],
    [/واحة الملك سلمان للعلوم|science oasis/i, 'مركز علوم تفاعلي يناسب الأطفال.'],
    [/حديقة الحيوانات|zoo/i, 'حديقة حيوانات الرياض في الملز، مناسبة للعائلة.'],
    [/المسار الرياضي|sports boulevard/i, 'مسار طويل للمشي والدراجات، حلو بعد العصر.']];
  var CAT_TIP = { heritage: 'البس شي مريح للمشي، والمكان أحلى قبل الظهر أو بعد العصر.', museum: 'خصص له ساعة ونص إلى ساعتين.',
    fun: 'الترفيه في الرياض يزدحم بالليل، خصوصاً نهاية الأسبوع.', show: 'شيّك على مواعيد العروض واحجز قبل لا تروح.',
    mall: 'مكيّف ويناسب وقت الحر، وفيه أكل وقهوة.', park: 'أحلى وقت للحدائق العصر لين المغرب.' };
  function tipFor(s) {
    var t = (s.ar || '') + ' ' + (s.en || ''); for (var i = 0; i < TIPS.length; i++) if (TIPS[i][0].test(t)) return TIPS[i][1];
    if (s.cat === 'park' && s.slot === 'morning') return 'تمشّى فيه الصبح قبل ما يحمى الجو، وخذ معك ماء.';
    if (s.cat === 'park' && s.slot === 'evening') return 'الحديقة بالليل أبرد وأهدى، مناسبة للجلسة والمشي.';
    return CAT_TIP[s.cat] || '';
  }
  var THEME_W = { heritage: 'تاريخ', museum: 'تاريخ', park: 'طبيعة', mall: 'تسوق', fun: 'ترفيه', show: 'سينما' };
  function themeOf(d) {
    var w = []; d.stops.forEach(function (s) { var x = !s.meal && THEME_W[s.cat]; if (x && w.indexOf(x) < 0) w.push(x); });
    return w.length > 1 ? w.slice(0, -1).join('، ') + ' و' + w[w.length - 1] : (w[0] || '');
  }
  function dayAdvice(d) {
    var first = d.stops.filter(function (s) { return !s.meal; })[0], hasFun = d.stops.some(function (s) { return s.cat === 'fun' || s.cat === 'show'; });
    if (first && (first.cat === 'heritage' || first.cat === 'park') && first.slot === 'morning') return 'ابدأ بدري: الأماكن المفتوحة تحلى قبل حر الظهر.';
    if (hasFun) return 'خلّ الترفيه آخر اليوم، أغلبه يفتح ويزدحم بعد المغرب.';
    return 'يوم الجمعة كثير من الأماكن تفتح بعد الصلاة، فخطط على هالأساس.';
  }
  function hoursEl(h) {   // OpenStreetMap opening_hours → one line per rule, times as an isolated LTR run
    var DAY_AR = { Mo: 'الإثنين', Tu: 'الثلاثاء', We: 'الأربعاء', Th: 'الخميس', Fr: 'الجمعة', Sa: 'السبت', Su: 'الأحد' };
    var box = el('div', 'g-hours');
    if (h === '24/7') { box.textContent = 'مفتوح ٢٤ ساعة'; return box; }
    h.split(/;\s*/).forEach(function (rule) {
      var m = rule.match(/^(.*?)\s*((?:\d{1,2}:\d{2}-\d{1,2}:\d{2}(?:,\s*)?)+|off)$/), line = el('div');
      if (!m) { line.textContent = rule; box.appendChild(line); return; }
      var days = m[1].replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su)\b/g, function (d) { return DAY_AR[d]; }).replace(/,\s*/g, '، ').trim();
      line.appendChild(document.createTextNode('الدوام ' + (days || 'يومياً') + ': '));
      var t = el('bdi', null, m[2] === 'off' ? 'مغلق' : m[2].replace(/-/g, '–').replace(/,\s*/g, ' / ')); t.dir = m[2] === 'off' ? 'rtl' : 'ltr';
      line.appendChild(t); box.appendChild(line);
    });
    return box;
  }
  function cleanName(s) { return HotelNLP.normalize(s).replace(/['’`´]/g, '').replace(/[^a-zء-ي0-9 ]/g, ' ').replace(/\s+/g, ' ').trim(); }

  var G = { days: 2, interests: [], food: '', pace: 'normal', origin: null, waiting: false, plan: null };
  var gInp = $('g-hotel');
  function segButtons(box, opts, key, onPick) {
    opts.forEach(function (o) {
      var b = el('button', 'g-opt', o[1]); b.type = 'button'; b.dataset.v = o[0];
      b.onclick = function () { onPick(o[0]); syncControls(); }; box.appendChild(b);
    });
  }
  segButtons($('g-days'), DAYS_OPT, 'days', function (v) { G.days = v; });
  segButtons($('g-int'), INT_OPT, 'interests', function (v) { var i = G.interests.indexOf(v); if (i >= 0) G.interests.splice(i, 1); else G.interests.push(v); });
  segButtons($('g-food'), FOOD_OPT, 'food', function (v) { G.food = v; });
  segButtons($('g-pace'), [['normal', 'عادي: ٣ أماكن باليوم'], ['relaxed', 'هادئ: مكانين']], 'pace', function (v) { G.pace = v; });
  function syncControls() {
    function mark(box, test) { Array.prototype.forEach.call($(box).children, function (b) { b.setAttribute('aria-pressed', test(b.dataset.v) ? 'true' : 'false'); }); }
    mark('g-days', function (v) { return +v === G.days; });
    mark('g-int', function (v) { return G.interests.indexOf(v) >= 0; });
    mark('g-food', function (v) { return v === G.food; });
    mark('g-pace', function (v) { return v === G.pace; });
  }
  syncControls();
  function originNote(text, warn) { var n = $('g-origin-note'); n.textContent = text || ''; n.className = 'g-note' + (warn ? ' warn' : ''); $('g-q-origin').classList.toggle('need', !!warn); }
  function setGuideOrigin(o, label, quiet) {
    G.origin = o; gInp.value = label || o.disp; originNote('');
    if (!quiet && (G.waiting || G.plan)) buildGuide();
  }
  makeCombo(gInp, function (r) { setGuideOrigin({ lat: r.lat, lng: r.lng, disp: r.disp }); });
  function guideLocate() {
    originNote('جاري تحديد موقعك…');
    locate(function (err, pos) {
      if (err) { originNote(locErr(err), true); return; }
      var near = nearestHotels(pos, 1);
      if (!near.length || near[0].d > 50) { originNote('موقعك خارج الرياض، والمرشد حالياً للرياض فقط. اختر فندقاً فيها.', true); return; }
      if (near[0].d <= 0.3) setGuideOrigin({ lat: near[0].h.lat, lng: near[0].h.lng, disp: near[0].h.disp });
      else setGuideOrigin({ lat: pos.lat, lng: pos.lng, disp: 'موقعك الحالي' }, LOC_LABEL);
    });
  }
  $('g-loc').onclick = guideLocate;
  $('g-go').onclick = function () { buildGuide(); };

  function buildGuide(opts) {
    if (!G.origin) {
      G.waiting = true; originNote('اختر وين ساكن أول، أو اضغط «موقعي»، وأرتب لك الجدول على طول.', true);
      try { gInp.focus({ preventScroll: true }); } catch (e) {}
      if (!G.plan) renderIdeas();
      return;
    }
    G.waiting = false;
    var ints = [];
    G.interests.forEach(function (i) { (i === 'kids' ? ['fun', 'park'] : [i]).forEach(function (x) { if (ints.indexOf(x) < 0) ints.push(x); }); });
    var cu = G.food && CUI_BY_ID[G.food];
    var meal = cu ? cu[2].map(function (w) { return HotelNLP.tokenize(w).join(' '); }) : null;
    var plan = HotelTrip.plan({ origin: G.origin, days: G.days, interests: ints, pace: G.pace, places: PLACES, restaurants: window.__P.restaurant,
      clean: cleanName, mealMatch: meal, excludeMatch: CHAIN_KEYS, avoid: opts && opts.avoid, avoidRest: opts && opts.avoidRest });
    G.plan = plan; renderPlan(plan); setGuideHash();
  }
  function ideaCard(title, sub, cfg) {
    var b = el('button', 'g-idea'); b.type = 'button';
    b.appendChild(el('strong', null, title)); b.appendChild(el('span', null, sub));
    b.onclick = function () { G.days = cfg.days; G.interests = cfg.interests.slice(); G.pace = cfg.pace || 'normal'; syncControls(); buildGuide(); };
    return b;
  }
  function renderIdeas() {
    var box = $('g-plan'); box.textContent = '';
    box.appendChild(el('h3', 'g-ideas-h', 'ما تدري من وين تبدأ؟ جرّب فكرة جاهزة'));
    var g = el('div', 'g-ideas');
    g.appendChild(ideaCard('أول زيارة للرياض', 'يومين: الدرعية، الرياض القديمة، وسهرة في البوليفارد', { days: 2, interests: [] }));
    g.appendChild(ideaCard('يوم تاريخ وتراث', 'المتحف الوطني، المصمك، والطريف', { days: 1, interests: ['heritage', 'museum'] }));
    g.appendChild(ideaCard('عطلة مع العيال', 'يومين ملاهي وحدائق ومتاحف تفاعلية', { days: 2, interests: ['kids'] }));
    g.appendChild(ideaCard('تسوق وسهرة', 'يوم مولات ثم ترفيه بالليل', { days: 1, interests: ['mall', 'fun'] }));
    box.appendChild(g);
  }
  function stopName(s) {
    var a = el('a', 'g-name'); a.href = s.url; a.target = '_blank'; a.rel = 'noopener';
    if (!s.meal && s.ar && s.en) { a.appendChild(el('bdi', null, s.ar)); a.appendChild(el('span', 'g-en', '')).appendChild(el('bdi', null, s.en)); }
    else a.appendChild(el('bdi', null, s.name));
    return a;
  }
  function legLine(L, back) {
    return (back ? 'الرجوع للفندق: ' : '') + (L.mode === 'مشي' ? AR_DIG(L.min) + ' د مشي' : AR_DIG(L.min) + ' د بالسيارة') + (back ? '' : ' من المحطة اللي قبل');
  }
  function renderPlan(plan) {
    var box = $('g-plan'); box.textContent = '';
    var head = el('header', 'g-plan-head');
    var n = plan.days.length;
    head.appendChild(el('h2', 'g-title', 'جدولك في الرياض: ' + (n === 1 ? 'يوم واحد' : n === 2 ? 'يومين' : AR_DIG(n) + ' أيام')));
    var from = el('p', 'g-from', 'الانطلاق من '); from.appendChild(el('bdi', null, plan.origin.disp)); head.appendChild(from);
    var act = el('div', 'g-actions');
    var again = el('button', 'g-act', 'اقترح جدول مختلف'); again.type = 'button';
    again.onclick = function () {
      var av = {}, ar = {}; plan.days.forEach(function (d) { d.stops.forEach(function (s) { if (s.cl) av[s.cl] = 1; if (s.k) ar[s.k] = 1; }); });
      buildGuide({ avoid: av, avoidRest: ar });
    };
    var share = el('button', 'g-act', 'شارك الجدول'); share.type = 'button';
    share.onclick = function () {
      var url = location.href;
      if (navigator.share) { navigator.share({ title: 'جدولي في الرياض', url: url }).catch(function () {}); return; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { share.textContent = 'تم نسخ الرابط'; }, function () {});
    };
    var print = el('button', 'g-act', 'اطبعه أو احفظه PDF'); print.type = 'button';
    print.onclick = function () { document.body.classList.add('print-guide'); window.print(); };
    act.appendChild(again); act.appendChild(share); act.appendChild(print); head.appendChild(act);
    box.appendChild(head);
    if (n < plan.asked) box.appendChild(el('p', 'g-note warn', 'ما لقيت أماكن كافية لـ ' + AR_DIG(plan.asked) + ' أيام بدون تكرار، فرتبت ' + AR_DIG(n) + '.'));
    var days = el('div', 'g-days');
    plan.days.forEach(function (d) {
      var sec = el('section', 'g-day'); sec.setAttribute('aria-label', 'اليوم ' + ORD[d.n - 1]);
      var dh = el('div', 'g-day-head');
      dh.appendChild(el('h3', null, 'اليوم ' + ORD[d.n - 1]));
      var th = themeOf(d); if (th) dh.appendChild(el('p', 'g-theme', th));
      sec.appendChild(dh);
      var ol = el('ol', 'g-rail');
      d.stops.forEach(function (s) {
        var li = el('li', 'g-stop' + (s.meal ? ' meal' : '') + ' slot-' + s.slot);
        var tm = el('div', 'g-time'); tm.appendChild(el('span', null, s.time)); tm.appendChild(el('small', null, s.label)); li.appendChild(tm);
        li.appendChild(el('span', 'g-dot' + (s.meal ? '' : ' s-' + CAT_DOT[s.cat])));
        var body = el('div', 'g-body');
        body.appendChild(stopName(s));
        var tags = el('div', 'g-tags');
        if (s.meal) tags.appendChild(el('span', 'g-tag', (s.slot === 'lunch' ? 'غداء' : 'عشاء') + '، ★ ' + s.rating + ' من ' + AR_DIG(s.reviews) + ' تقييم'));
        else tags.appendChild(el('span', 'g-tag s-' + CAT_DOT[s.cat], s.catAr));
        body.appendChild(tags);
        if (!s.meal) { var tip = tipFor(s); if (tip) body.appendChild(el('p', 'g-tip', tip)); }
        if (!s.meal && s.also && s.also.length) body.appendChild(el('p', 'g-also', 'بنفس المكان: ' + s.also.join('، ')));
        if (!s.meal && s.hours) body.appendChild(hoursEl(s.hours));
        body.appendChild(el('div', 'g-leg', legLine(s.leg)));
        li.appendChild(body); ol.appendChild(li);
      });
      sec.appendChild(ol);
      var foot = el('div', 'g-day-foot');
      foot.appendChild(el('p', 'g-advice', dayAdvice(d)));
      if (d.back) foot.appendChild(el('div', 'g-leg', legLine(d.back, true) + '، ومجموع تنقل اليوم حوالي ' + AR_DIG(Math.round(d.km)) + ' كم'));
      var a = el('a', 'g-route', 'افتح مسار اليوم في خرائط Google'); a.href = d.route; a.target = '_blank'; a.rel = 'noopener';
      foot.appendChild(a); sec.appendChild(foot);
      days.appendChild(sec);
    });
    box.appendChild(days);
    box.appendChild(el('p', 'g-fine', 'الأوقات تقديرية، وتأكد من أوقات الدوام قبل ما تروح. المطاعم مختارة بالتقييم وعدد المراجعات وقربها من المحطة. بيانات المعالم والترفيه © OpenStreetMap contributors.'));
  }
  window.addEventListener('afterprint', function () { document.body.classList.remove('print-guide'); });

  // shareable link: #guide=… keeps the choices (a location can't be shared, a hotel can)
  function setGuideHash() {
    var o = { d: G.days, i: G.interests.join(','), f: G.food, p: G.pace };
    if (G.origin && G.origin.disp !== 'موقعك الحالي') o.h = G.origin.disp;
    try { history.replaceState(null, '', location.pathname + location.search + '#guide=' + encodeURIComponent(JSON.stringify(o))); } catch (e) {}
  }
  function loadGuideHash() {
    var m = location.hash.match(/^#guide=(.+)$/); if (!m) return false;
    try {
      var o = JSON.parse(decodeURIComponent(m[1]));
      G.days = +o.d || 2; G.interests = o.i ? String(o.i).split(',').filter(Boolean) : []; G.food = o.f || ''; G.pace = o.p === 'relaxed' ? 'relaxed' : 'normal';
      syncControls(); showTab('guide');
      var r = o.h && rows.filter(function (x) { return x.disp === o.h; })[0];
      if (r) setGuideOrigin({ lat: r.lat, lng: r.lng, disp: r.disp }, null, true);
      buildGuide();
    } catch (e) { return false; }
    return true;
  }

  // a trip question typed in the question box («جدول يومين وانا ساكن في هيلتون») → fill the guide and open it
  function askTrip(out, p, text) {
    var t = p.trip;
    G.days = t.days || 2;
    G.interests = t.interests.slice();
    if (/اطفال|عيال|بزران|عائل|kids|family/.test(p.tokens.join(' '))) { G.interests = G.interests.filter(function (i) { return i !== 'fun' && i !== 'park'; }); G.interests.push('kids'); }
    G.food = p.cuisine && FOOD_OPT.some(function (f) { return 'cuisine_' + f[0] === p.cuisine.id; }) ? p.cuisine.id.replace('cuisine_', '') : '';
    G.pace = t.pace; syncControls();
    out.appendChild(el('div', 'nlp-lbl', 'فتحت لك المرشد السياحي ورتبت الجدول هناك.'));
    showTab('guide', true);
    if (p.hotel) setGuideOrigin({ lat: p.hotel.hotel.lat, lng: p.hotel.hotel.lng, disp: p.hotel.disp }, null, true);
    if (p.nearMe && !p.hotel) { G.waiting = true; guideLocate(); return; }
    buildGuide();
  }

  /* --- 📍 find my hotel from my location --- */
  $('loc-btn').onclick = function () { var out = $('nlp-out'); out.textContent = ''; fromMyLocation(out, 'pick'); };

  /* --- voice input (Web Speech API: Chrome / Safari; hidden where unsupported) --- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition, mic = $('nlp-mic');
  if (SR && mic) {
    mic.hidden = false; var rec = null;
    mic.onclick = function () {
      if (rec) { rec.stop(); return; }
      rec = new SR(); rec.lang = 'ar-SA'; rec.interimResults = true; rec.maxAlternatives = 1;
      mic.classList.add('on'); mic.setAttribute('aria-pressed', 'true');
      rec.onresult = function (e) {
        var t = ''; for (var i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
        q.value = t; if (e.results[e.results.length - 1].isFinal) ask(q.value);
      };
      rec.onerror = function (e) { var out = $('nlp-out'); out.textContent = ''; out.appendChild(el('div', 'nlp-warn', e.error === 'not-allowed' ? 'ما سمحت للصفحة باستخدام المايك.' : 'ما قدرت أسمعك، جرّب مرة ثانية أو اكتب سؤالك.')); };
      rec.onend = function () { rec = null; mic.classList.remove('on'); mic.setAttribute('aria-pressed', 'false'); };
      rec.start();
    };
  }

  /* --- opened from a shared link (#q=…) --- */
  try { var hm = location.hash.match(/^#q=(.+)$/); if (hm) { q.value = decodeURIComponent(hm[1]); ask(q.value); } } catch (e) {}
  if (!loadGuideHash()) renderIdeas();

  /* --- "about the model" card --- */""")
g = rep(g, "pc(m.synthetic_heldout.service_acc)", "pc(m.synthetic_heldout.service_acc_non_brand)")
g = g.replace("mt.arabic_spellings.", "mt.arabic_spellings_no_aliases.").replace("mt.latin_typos.", "mt.latin_typos_no_aliases.")
g = rep(g, "      ['اكتشاف اسم الفندق في الجملة (F1)', pc(m.synthetic_heldout.hotel_span_f1), '—']\n",
  "      ['اكتشاف اسم الفندق في الجملة (F1)', pc(m.synthetic_heldout.hotel_span_f1), '—'],\n      ['اكتشاف العلامة (دانكن، ستاربكس…) — علامات لم يشاهدها المودل (F1)', pc(m.synthetic_heldout.brand_detect_f1_unseen_brands), pc(m.brand_queries.brand_ok / (m.brand_queries.n - m.brand_queries.no_false_brand_n))],\n      ['المزايا الجديدة: «قريب مني»، نوع الأكل، تصحيح الإملاء، خدمات غير متوفرة', '—', pc(m.v3_features.passed / m.v3_features.checks)]\n")
h3 = h2[:sc[1][0]] + core_new + h2[sc[1][1]:]
sc = [(m.start(), m.end()) for m in SC.finditer(h3)]
assert len(sc) == 5, len(sc)
h3 = h3[:sc[4][0]] + '<script>\n' + g.split('<script>\n', 1)[1] + h3[sc[4][1]:]
# example buttons
ex = '<button type="button" class="nlp-ex">nearest restaurant to radisson within 500 m</button>'
h3 = rep(h3, ex, ex + '<button type="button" class="nlp-ex">اقرب دانكن مني</button><button type="button" class="nlp-ex">مطعم شاورما جنب هيلتون</button><button type="button" class="nlp-ex">ستار بكس جنب الشيرتون</button>')
MIC = '<button type="button" class="nlp-mic" id="nlp-mic" aria-label="اسأل بصوتك" title="اسأل بصوتك" aria-pressed="false" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button>'
h3 = rep(h3, '<button type="button" class="nlp-go" id="nlp-go">افهم</button>', MIC + '<button type="button" class="nlp-go" id="nlp-go">افهم</button>')
h3 = rep(h3, '<input type="text" id="hotel" list="hotels" autocomplete="off" placeholder="اختر الفندق" dir="auto">',
  '<div class="hrow"><input type="text" id="hotel" list="hotels" autocomplete="off" placeholder="اختر الفندق" dir="auto"><button type="button" class="loc-btn" id="loc-btn" title="حدد فندقي من موقعي">📍 موقعي</button></div>')
h3 = rep(h3, '.nlp-warn { margin-top: 6px; font-size: .84rem; color: var(--mark); }', '''.nlp-warn { margin-top: 6px; font-size: .84rem; color: var(--mark); }
.hrow { display: flex; gap: 8px; } .hrow input { flex: 1; min-width: 0; }
.loc-btn, .nlp-mic { font: inherit; font-size: .88rem; cursor: pointer; background: var(--surface-2); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 0 12px; min-height: 42px; white-space: nowrap; }
.loc-btn:hover, .nlp-mic:hover { border-color: var(--accent); }
.nlp-mic { padding: 0 11px; display: inline-flex; align-items: center; justify-content: center; } .nlp-mic svg { width: 18px; height: 18px; }
.nlp-mic.on { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); animation: nlpPulse 1.2s ease-in-out infinite; }
@keyframes nlpPulse { 50% { opacity: .55; } }
@media (prefers-reduced-motion: reduce) { .nlp-mic.on { animation: none; } }
.nlp-share { margin-top: 8px; }''')
h3 = rep(h3, 'فيُفهم «ماريوت» و«Marriott» و«marriot».</p>', 'فيُفهم «ماريوت» و«Marriott» و«marriot».</p>\n    <p>فوق النماذج طبقة قواعد صغيرة: تفهم «قريب مني» وتستخدم موقعك (بإذنك)، وتبحث بنوع الأكل في أسماء المطاعم (شاورما، بيتزا، مندي…)، وتصحّح أخطاء إملاء أسماء السلاسل المعروفة (ستاربك ← ستاربكس)، وتقول بصراحة إذا طلبت خدمة ما عندنا بياناتها (صيدلية، مسجد…).</p>')
# ---- v4 HTML / CSS: trip section, dropdown, colours for the new categories, examples, about text
GUIDE = """  <div class="wrap" id="tab-guide" role="tabpanel" aria-labelledby="tab-btn-guide" hidden>
    <div class="g-grid">
      <section class="card g-build" aria-label="خطط رحلتك">
        <h2 class="g-h">المرشد السياحي</h2>
        <p class="g-lead">قل لي كم يوم عندك ووش تحب، وأرتب لك أيامك في الرياض: وين تروح، ووين تاكل، وكم يبعد كل مكان عن اللي قبله.</p>
        <div class="g-q"><span class="lbl" id="g-days-l">كم يوم عندك؟</span><div class="g-seg" id="g-days" role="group" aria-labelledby="g-days-l"></div></div>
        <div class="g-q" id="g-q-origin"><label for="g-hotel" class="lbl">وين ساكن؟</label><div class="hrow"><input type="text" id="g-hotel" autocomplete="off" dir="auto" placeholder="اختر فندقك"><button type="button" class="loc-btn" id="g-loc">📍 موقعي</button></div><div class="g-note" id="g-origin-note" aria-live="polite"></div></div>
        <div class="g-q"><span class="lbl" id="g-int-l">وش تحب؟ <small>تقدر تختار أكثر من وحدة</small></span><div class="g-chips" id="g-int" role="group" aria-labelledby="g-int-l"></div></div>
        <div class="g-q"><span class="lbl" id="g-food-l">أكلك المفضل</span><div class="g-chips" id="g-food" role="group" aria-labelledby="g-food-l"></div></div>
        <div class="g-q"><span class="lbl" id="g-pace-l">إيقاع اليوم</span><div class="g-seg" id="g-pace" role="group" aria-labelledby="g-pace-l"></div></div>
        <button type="button" class="g-go" id="g-go">رتّب لي الجدول</button>
      </section>
      <section class="g-plan" id="g-plan" aria-live="polite" aria-label="الجدول"></section>
    </div>
  </div>

"""
h3 = rep(h3, '  <div class="wrap"><section class="card mlcard">', GUIDE + '  <div class="wrap"><section class="card mlcard">')
h3 = rep(h3, '        <div class="stats" id="stats"></div>\n      </div>', '        <div class="stats" id="stats"></div>\n        <button type="button" class="hero-guide" id="hero-guide">خطّط يومك في الرياض مع المرشد السياحي</button>\n      </div>')
h3 = rep(h3, '  </section>\n\n  <div class="wrap">\n    <div class="grid">', '  </section>\n\n  <div class="wrap"><nav class="tabs" id="tabs" role="tablist" aria-label="أقسام الصفحة"><button type="button" class="tab" role="tab" id="tab-btn-search" aria-controls="tab-search" aria-selected="true">خدمات قريبة<small>مطاعم وكافيهات ومحلات حول فندقك</small></button><button type="button" class="tab" role="tab" id="tab-btn-guide" aria-controls="tab-guide" aria-selected="false" tabindex="-1">المرشد السياحي<small>جدول أيامك في الرياض</small></button></nav></div>\n\n  <div class="wrap" id="tab-search" role="tabpanel" aria-labelledby="tab-btn-search">\n    <div class="grid">')
h3 = rep(h3, '<button type="button" class="nlp-ex">ستار بكس جنب الشيرتون</button>', '<button type="button" class="nlp-ex">ستار بكس جنب الشيرتون</button><button type="button" class="nlp-ex">جدول يومين وأنا ساكن في الفورسيزونز</button><button type="button" class="nlp-ex">اقرب ملاهي من هيلتون</button>')
CSS4 = """
.hrow { position: relative; }
.hdd { position: absolute; top: calc(100% + 4px); inset-inline: 0; z-index: 40; max-height: min(340px, 55vh); overflow-y: auto; overscroll-behavior: contain; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 12px 32px rgba(0,0,0,.18); padding: 4px; }
.hdd[hidden] { display: none; }
.hdd-head { font-size: .75rem; color: var(--muted); padding: 6px 10px 4px; font-weight: 600; }
.hdd-opt { padding: 8px 10px; border-radius: 7px; cursor: pointer; display: flex; flex-direction: column; gap: 2px; }
.hdd-opt:hover, .hdd-opt.on { background: var(--surface-2); }
.hdd-nm { font-weight: 600; font-size: .9rem; } .hdd-meta { font-size: .75rem; color: var(--muted); }
.trip-card { margin-top: 16px; } .trip-card[hidden] { display: none; }
.trip-head h2 { margin: 0 0 2px; font-size: 1.2rem; } .trip-from { margin: 0 0 4px; font-weight: 600; font-size: .92rem; } .trip-sub { color: var(--muted); font-size: .88rem; margin: 0 0 14px; }
.trip-days { display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 14px; }
.trip-day { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; background: var(--surface-2); min-width: 0; }
.trip-day h3 { margin: 0; font-size: 1rem; display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.trip-day h3 small { color: var(--muted); font-weight: 500; font-size: .76rem; }
.trip-stops { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.trip-stop { display: grid; grid-template-columns: 54px 1fr; gap: 10px; }
.trip-time { font-variant-numeric: tabular-nums; font-weight: 700; font-size: .86rem; } .trip-time small { display: block; color: var(--muted); font-weight: 500; font-size: .72rem; }
.trip-nm { font-weight: 600; color: var(--ink); text-decoration: none; overflow-wrap: anywhere; } .trip-nm:hover { text-decoration: underline; }
.trip-meal .trip-time { color: var(--muted); }
.trip-meta { font-size: .78rem; color: var(--muted); overflow-wrap: anywhere; } .trip-leg { font-size: .74rem; color: var(--muted); }
.trip-back { margin-top: 10px; }
.trip-actions { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
.trip-btn { font-size: .82rem; text-decoration: none; background: var(--accent); color: var(--accent-ink); border-radius: 8px; padding: 6px 12px; display: inline-block; }
.trip-note { font-size: .78rem; color: var(--muted); margin: 14px 0 0; }
:root { --c-sights: #b0463e; --c-sights-ink: #ffffff; --c-fun: #b8357f; --c-fun-ink: #ffffff; --c-mall: #127f84; --c-mall-ink: #ffffff; --c-park: #567d1c; --c-park-ink: #ffffff; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --c-sights: #f0928a; --c-sights-ink: #2a0703; --c-fun: #f08ccb; --c-fun-ink: #2b0620; --c-mall: #6fd3d6; --c-mall-ink: #032426; --c-park: #b2db74; --c-park-ink: #172603; } }
:root[data-theme="dark"] { --c-sights: #f0928a; --c-sights-ink: #2a0703; --c-fun: #f08ccb; --c-fun-ink: #2b0620; --c-mall: #6fd3d6; --c-mall-ink: #032426; --c-park: #b2db74; --c-park-ink: #172603; }
""" + "\n".join(".s-%s circle, .num.s-%s, .sd.s-%s { fill: var(--c-%s); background: var(--c-%s); color: var(--c-%s-ink); }\n.s-%s text { fill: var(--c-%s-ink); }" % ((c,) * 8) for c in ['sights', 'fun', 'mall', 'park'])
CSS5 = """
:root { --sky-morning: #f3c76b; --sky-noon: #8fc0d6; --sky-asr: #e39a3b; --sky-dusk: #6b5fb0; --sky-night: #142a3d; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --sky-night: #9fb3d6; } }
:root[data-theme="dark"] { --sky-night: #9fb3d6; }
.hero-guide { margin-top: 16px; font: inherit; font-weight: 700; font-size: 1rem; cursor: pointer; background: var(--accent); color: var(--accent-ink); border: 0; border-radius: 999px; padding: 12px 22px; box-shadow: var(--shadow); }
.hero-guide:hover { filter: brightness(1.08); }
.tabs { position: relative; z-index: 3; box-shadow: var(--shadow); display: flex; gap: 6px; margin: 18px 0 14px; padding: 5px; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; width: fit-content; max-width: 100%; }
.tab { font: inherit; font-weight: 700; font-size: .98rem; border: 0; background: transparent; color: var(--ink); padding: 9px 18px; border-radius: 12px; cursor: pointer; display: flex; flex-direction: column; align-items: flex-start; gap: 1px; text-align: start; }
.tab small { font-weight: 500; font-size: .74rem; color: var(--muted); }
.tab[aria-selected="true"] { background: var(--accent); color: var(--accent-ink); } .tab[aria-selected="true"] small { color: inherit; opacity: .85; }
.tab:focus-visible, .g-opt:focus-visible, .g-go:focus-visible, .g-act:focus-visible, .g-idea:focus-visible, .hero-guide:focus-visible, .loc-btn:focus-visible, .g-route:focus-visible { outline: 3px solid var(--mark); outline-offset: 2px; }
#tab-search[hidden], #tab-guide[hidden] { display: none; }
.tabs { margin-top: -76px; } #tab-search .grid { margin-top: 0; }
@media (min-width: 880px) { .tabs { margin-top: -96px; } }
@media (max-width: 640px) { .tabs { width: 100%; } .tab { flex: 1; align-items: center; text-align: center; padding: 11px 10px; } .tab small { display: none; } .hero-guide { width: 100%; } }   /* the tabs take the cards' place on the skyline; the cards sit right under them */
.g-grid { display: grid; grid-template-columns: minmax(290px, 360px) minmax(0, 1fr); gap: 18px; align-items: start; }
@media (min-width: 901px) { .g-build { position: sticky; top: 12px; } }
@media (max-width: 900px) { .g-grid { grid-template-columns: minmax(0, 1fr); } }
.g-build { display: flex; flex-direction: column; gap: 16px; }
.g-h { font-family: var(--display); font-size: 1.7rem; margin: 0; line-height: 1.25; }
.g-lead { margin: -8px 0 0; color: var(--muted); font-size: .92rem; line-height: 1.75; }
.g-q .lbl { display: block; font-weight: 700; margin-bottom: 8px; }
.g-q .lbl small { font-weight: 500; color: var(--muted); font-size: .78rem; margin-inline-start: 4px; }
.g-seg, .g-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.g-opt { font: inherit; font-size: .86rem; cursor: pointer; background: var(--surface-2); color: var(--ink); border: 1px solid var(--line); border-radius: 999px; padding: 7px 13px; min-height: 38px; }
.g-opt:hover { border-color: var(--accent); }
.g-opt[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.g-q.need input { border-color: var(--mark); outline: 2px solid var(--mark); }
.g-note { font-size: .82rem; color: var(--muted); margin-top: 6px; min-height: 0; } .g-note:empty { display: none; } .g-note.warn { color: var(--mark); font-weight: 600; }
.g-go { font: inherit; font-weight: 700; font-size: 1.04rem; cursor: pointer; background: var(--accent); color: var(--accent-ink); border: 0; border-radius: 12px; padding: 14px; }
.g-plan { min-width: 0; }
.g-ideas-h { font-family: var(--display); font-size: 1.2rem; margin: 6px 0 12px; }
.g-ideas { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.g-idea { font: inherit; text-align: start; cursor: pointer; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; color: var(--ink); }
.g-idea strong { font-family: var(--display); font-size: 1.08rem; font-weight: 600; } .g-idea span { color: var(--muted); font-size: .85rem; line-height: 1.6; }
.g-idea:hover { border-color: var(--accent); }
.g-plan-head { margin: 2px 0 16px; }
.g-title { font-family: var(--display); font-size: clamp(1.45rem, 3.2vw, 2.1rem); font-weight: 600; margin: 0; line-height: 1.2; }
.g-from { margin: 4px 0 0; color: var(--muted); font-weight: 600; }
.g-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.g-act { font: inherit; font-size: .84rem; cursor: pointer; background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 999px; padding: 7px 14px; }
.g-act:hover { border-color: var(--accent); }
.g-days { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 16px; }
.g-day { background: var(--surface); border: 1px solid var(--line); border-radius: 20px; padding: 18px 16px 16px; box-shadow: var(--shadow); min-width: 0; }
.g-day-head h3 { font-family: var(--display); font-size: 1.4rem; font-weight: 600; margin: 0; }
.g-theme { margin: 2px 0 0; color: var(--muted); font-size: .9rem; }
.g-rail { list-style: none; margin: 16px 0 0; padding: 0; position: relative; display: flex; flex-direction: column; gap: 18px; }
.g-rail::before { content: ""; position: absolute; inset-inline-start: 69px; top: 10px; bottom: 10px; width: 4px; border-radius: 4px; background: linear-gradient(to bottom, var(--sky-morning), var(--sky-noon) 28%, var(--sky-asr) 52%, var(--sky-dusk) 76%, var(--sky-night)); }
.g-stop { display: grid; grid-template-columns: 58px 26px minmax(0, 1fr); align-items: start; }
.g-time span { display: block; font-family: var(--display); font-size: 1.08rem; font-weight: 600; font-variant-numeric: tabular-nums; direction: ltr; text-align: right; }
.g-time small { display: block; color: var(--muted); font-size: .74rem; }
.g-dot { width: 16px; height: 16px; border-radius: 50%; margin: 6px auto 0; border: 3px solid var(--surface); box-shadow: 0 0 0 1px var(--line); position: relative; z-index: 1; background: var(--muted); }
.g-dot.s-sights { background: var(--c-sights); } .g-dot.s-fun { background: var(--c-fun); } .g-dot.s-mall { background: var(--c-mall); } .g-dot.s-park { background: var(--c-park); }
.meal .g-dot { background: var(--surface); box-shadow: 0 0 0 2px var(--muted); width: 12px; height: 12px; margin-top: 8px; border-width: 2px; }
.g-body { min-width: 0; padding-inline-start: 4px; }
.g-name { font-weight: 700; color: var(--ink); text-decoration: none; font-size: 1.02rem; line-height: 1.45; overflow-wrap: anywhere; display: block; }
.g-name:hover { text-decoration: underline; }
.g-en { display: block; font-weight: 500; color: var(--muted); font-size: .8rem; }
.meal .g-name { font-weight: 600; font-size: .95rem; }
.g-tags { margin-top: 5px; display: flex; gap: 6px; flex-wrap: wrap; }
.g-tag { font-size: .74rem; padding: 2px 10px; border-radius: 999px; background: var(--surface-2); color: var(--muted); border: 1px solid var(--line); }
.g-tag.s-sights { background: var(--c-sights); color: var(--c-sights-ink); border-color: transparent; } .g-tag.s-fun { background: var(--c-fun); color: var(--c-fun-ink); border-color: transparent; }
.g-tag.s-mall { background: var(--c-mall); color: var(--c-mall-ink); border-color: transparent; } .g-tag.s-park { background: var(--c-park); color: var(--c-park-ink); border-color: transparent; }
.g-tip { margin: 7px 0 0; font-size: .86rem; line-height: 1.7; }
.g-also, .g-hours { font-size: .78rem; color: var(--muted); margin: 5px 0 0; line-height: 1.6; }
.g-leg { font-size: .76rem; color: var(--muted); margin-top: 5px; }
.g-day-foot { margin-top: 16px; padding-top: 12px; border-top: 1px dashed var(--line); display: flex; flex-direction: column; gap: 8px; }
.g-advice { margin: 0; font-size: .86rem; line-height: 1.65; background: var(--surface-2); border-radius: 10px; padding: 9px 12px; }
.g-route { align-self: flex-start; font-size: .88rem; font-weight: 600; text-decoration: none; background: var(--accent); color: var(--accent-ink); padding: 9px 15px; border-radius: 10px; }
.g-fine { font-size: .78rem; color: var(--muted); margin: 16px 0 0; line-height: 1.6; }
@media print {
  body.print-guide * { visibility: hidden; }
  body.print-guide #g-plan, body.print-guide #g-plan * { visibility: visible; }
  body.print-guide #g-plan { position: absolute; inset-inline: 0; top: 0; }
  body.print-guide .g-actions, body.print-guide .g-route { display: none; }
  body.print-guide .g-day { box-shadow: none; break-inside: avoid; }
}
"""
h3 = rep(h3, '.nlp-share { margin-top: 8px; }', '.nlp-share { margin-top: 8px; }' + CSS4 + CSS5)
h3 = rep(h3, '(صيدلية، مسجد…).</p>', '(صيدلية، مسجد…).</p>\n    <p>وفيه «المرشد السياحي» (تبويب خاص، أو اكتب سؤالك هنا): اكتب مثلاً «جدول ٣ أيام وأنا ساكن في هيلتون وأحب التاريخ» فيرتب لك كل يوم (صباح، غداء، عصر، مساء، عشاء) بأماكن قريبة من بعض ومن فندقك، ويختار المطاعم بالتقييم وعدد المراجعات. المعالم والترفيه والمولات والحدائق مأخوذة من OpenStreetMap (© OpenStreetMap contributors) وليس فيها تقييمات، فأهميتها تقديرية.</p>')
open(dst, 'w', encoding='utf8').write(h3)
print('wrote', dst, len(h3))
