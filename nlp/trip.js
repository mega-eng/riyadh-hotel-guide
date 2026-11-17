/* HotelTrip: day-by-day trip planner for visitors, built around where they stay.
   Places come from OpenStreetMap (places.json), restaurants from the page's POI data.
   Runs in the browser and in Node. No ratings exist for OSM places, so "importance" is an honest proxy
   (category, bilingual name, known opening hours); restaurants are ranked by rating shrunk by review count. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.HotelTrip = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var CAT_AR = { heritage: 'تراث وتاريخ', museum: 'متحف', fun: 'ترفيه', show: 'سينما ومسرح', mall: 'تسوق', park: 'حديقة ومنتزه' };
  // what fits each part of the day (Riyadh: outdoors early or after sunset, entertainment at night)
  var SLOTS = [
    { key: 'morning', label: 'الصباح', time: '10:00', cats: { heritage: 1, museum: 1, park: 0.55 } },
    { key: 'lunch', label: 'الغداء', time: '13:30', meal: true },
    { key: 'afternoon', label: 'العصر', time: '16:30', cats: { park: 1, museum: 0.85, mall: 0.8, heritage: 0.75 } },
    { key: 'evening', label: 'المساء', time: '19:30', cats: { fun: 1, mall: 0.9, show: 0.75, park: 0.4 } },
    { key: 'dinner', label: 'العشاء', time: '21:30', meal: true }
  ];
  // not a lunch/dinner place even though it sits in the restaurant file
  var NOT_MEAL = /حلويات|حلا|مخبز|مخابز|افران|bakery|bakeries|patisserie|pastry|pâtisserie|juice|عصير|عصاير|محامص|محمصه|roaster|roastery|شاهي|tea|coffee|قهوه|كافيه|cafe|café|ice ?cream|ايس ?كريم|باسكن|baskin|دونات|donut|كيك|cake|mille|كريب|crepe|waffle|فوال|فول|foul|فطور|breakfast|بوظه|gelato|chocolate|شوكولا|تمور|dates|بقاله|ماركت/;
  function hav(a, b, c, d) {
    var r = Math.PI / 180, x = Math.sin((c - a) * r / 2) * Math.sin((c - a) * r / 2) + Math.cos(a * r) * Math.cos(c * r) * Math.sin((d - b) * r / 2) * Math.sin((d - b) * r / 2);
    return 12742 * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  function loadPlaces(json) {
    return json.rows.map(function (r) {
      var ar = r[4], en = r[5];
      return { id: r[0], cat: r[1], lat: r[2], lng: r[3], ar: ar, en: en, hours: r[6], tier: r[7], w: r[8], cl: r[9],
        name: ar ? (en ? ar + ' (' + en + ')' : ar) : en };
    });
  }
  // driving estimate on Riyadh roads: detour factor 1.35, ~32 km/h door to door, +4 min parking
  function leg(km) {
    if (km < 0.8) return { km: km, min: Math.max(2, Math.round(km / 4.5 * 60)), mode: 'مشي' };
    return { km: km, min: Math.round(km * 1.35 / 32 * 60) + 4, mode: 'سيارة' };
  }
  function routeUrl(origin, stops) {
    var f = function (p) { return p.lat.toFixed(6) + '%2C' + p.lng.toFixed(6); };
    return 'https://www.google.com/maps/dir/?api=1&origin=' + f(origin) + '&destination=' + f(origin) +
      (stops.length ? '&waypoints=' + stops.map(f).join('%7C') : '') + '&travelmode=driving';
  }
  function placeUrl(p) { return 'https://www.google.com/maps/search/?api=1&query=' + p.lat + '%2C' + p.lng; }

  /* opt: { origin:{lat,lng,disp}, days, interests:[cat], pace:'normal'|'relaxed', places, restaurants:[[name,lat,lng,rating,n]],
            clean:fn(name)->normalized, mealMatch:[keys]|null, excludeMatch:[keys], maxKm } */
  function plan(opt) {
    var O = opt.origin, days = Math.max(1, Math.min(7, opt.days || 2)), maxKm = opt.maxKm || 30;
    var interests = opt.interests || [], places = opt.places.filter(function (p) { return p.tier === 1; });
    var clean = opt.clean || function (s) { return String(s || '').toLowerCase(); };
    var R = (opt.restaurants || []).map(function (r) { return { name: r[0], lat: r[1], lng: r[2], rating: r[3], n: r[4] || 0, k: clean(r[0]) }; })
      .filter(function (r) { return r.rating != null && r.n >= 25 && r.rating >= 3.8 && !NOT_MEAL.test(r.k); });
    var excl = opt.excludeMatch || [], meal = opt.mealMatch || null;
    var usedCl = {}, usedRest = {}, out = [], avoid = opt.avoid || {}, avoidRest = opt.avoidRest || {};   // avoid: «اقترح جدول مختلف»
    var slots = opt.pace === 'relaxed' ? SLOTS.filter(function (s) { return s.key !== 'afternoon'; }) : SLOTS;
    function interestF(cat) {
      if (!interests.length) return 1;
      if (interests.indexOf(cat) >= 0) return 1.7;
      if (cat === 'museum' && interests.indexOf('heritage') >= 0) return 1.4;   // history lovers like museums
      return 0.45;
    }
    function clusterAlso(p) {
      return opt.places.filter(function (q) { return q.cl === p.cl && q.id !== p.id && q.tier === 1; }).slice(0, 3).map(function (q) { return q.ar || q.en; });
    }
    function pickRest(at, mealKey) {
      for (var rad = 1.5; rad <= 4.5; rad += 1.5) {
        var best = null, bs = -1e9;
        R.forEach(function (r) {
          if (usedRest[r.k]) return;
          var km = hav(at.lat, at.lng, r.lat, r.lng); if (km > rad) return;
          if (excl.some(function (m) { return r.k.indexOf(m) >= 0; })) return;                        // skip fast-food chains
          var bayes = (r.rating * r.n + 4.0 * 40) / (r.n + 40), sc = bayes - 0.15 * km - (avoidRest[r.k] ? 0.5 : 0);
          if (meal && meal.some(function (m) { return r.k.indexOf(m) >= 0; })) sc += 0.6;              // the food they asked for
          if (sc > bs) { bs = sc; best = r; best._km = km; }
        });
        if (best) { usedRest[best.k] = 1; return best; }
      }
      return null;
    }
    // what they said they like may happen at any time of day (malls open in the morning; fun/shows stay evening-only)
    if (interests.length) slots = slots.map(function (s) {
      if (s.meal) return s;
      var c = Object.assign({}, s.cats);
      interests.forEach(function (i) { if (!c[i] && !(s.key === 'morning' && (i === 'fun' || i === 'show'))) c[i] = 0.7; });
      return Object.assign({}, s, { cats: c });
    });
    for (var d = 0; d < days; d++) {
      var day = { n: d + 1, stops: [], km: 0 }, prev = O, dayCats = {}, visits = 0;
      slots.forEach(function (slot) {
        if (slot.meal) {
          if (!visits) return;                                     // no lunch stop on a day that has nothing yet
          var r = pickRest(prev);
          if (r) { var L = leg(hav(prev.lat, prev.lng, r.lat, r.lng)); day.stops.push({ slot: slot.key, label: slot.label, time: slot.time, meal: true, k: r.k, name: r.name, lat: r.lat, lng: r.lng, rating: r.rating, reviews: r.n, leg: L, url: placeUrl(r) }); day.km += L.km; prev = r; }
          return;
        }
        var best = null, bs = -1e9;
        places.forEach(function (p) {
          if (usedCl[p.cl]) return;
          var cw = slot.cats[p.cat]; if (!cw) return;
          var dO = hav(O.lat, O.lng, p.lat, p.lng); if (dO > maxKm) return;
          var dP = hav(prev.lat, prev.lng, p.lat, p.lng);
          var sc = p.w * cw * interestF(p.cat) - 0.012 * dO - (prev === O ? 0 : 0.03 * dP) - (dayCats[p.cat] ? 0.35 : 0) - (avoid[p.cl] ? 0.6 : 0);
          if (sc > bs) { bs = sc; best = p; }
        });
        if (!best) return;
        usedCl[best.cl] = 1; dayCats[best.cat] = 1; visits++;
        var L = leg(hav(prev.lat, prev.lng, best.lat, best.lng));
        day.stops.push({ slot: slot.key, label: slot.label, time: slot.time, name: best.name, ar: best.ar, en: best.en, cat: best.cat, cl: best.cl, catAr: CAT_AR[best.cat], hours: best.hours,
          also: clusterAlso(best), lat: best.lat, lng: best.lng, leg: L, url: placeUrl(best) });
        day.km += L.km; prev = best;
      });
      if (!visits) break;                                          // ran out of places
      var back = leg(hav(prev.lat, prev.lng, O.lat, O.lng)); day.back = back; day.km += back.km;
      day.km = Math.round(day.km * 10) / 10;
      day.route = routeUrl(O, day.stops);
      out.push(day);
    }
    return { origin: O, days: out, asked: days, interests: interests };
  }
  return { plan: plan, loadPlaces: loadPlaces, CAT_AR: CAT_AR, routeUrl: routeUrl, hav: hav };
});
