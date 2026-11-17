# أقرب خدمة للفندق + المرشد السياحي (الرياض)

صفحة ويب واحدة تشتغل داخل المتصفح بدون سيرفر ولا API. تكتب سؤالك بالعربي (لهجة أو فصحى) أو بالإنجليزي، وتطلع لك أقرب الخدمات حول فندقك، أو جدول رحلة كامل في الرياض.

**جرّبها:** افتح `index.html`، أو فعّل GitHub Pages للمستودع.

| المرشد السياحي | على الجوال |
|---|---|
| ![جدول يومين](docs/guide-desktop.png) | ![يوم على الجوال](docs/guide-phone.png) |

## وش تسوي

- **خدمات قريبة**: مطاعم، كافيهات، نوادي، سوبرماركت، مغاسل، معالم، ترفيه، مولات، حدائق، حول 162 مكان سكن.
  - تفهم أسماء المحلات: «اقرب دانكن من هيلتون»، «ستار بكس جنب الشيرتون».
  - تفهم نوع الأكل: «مطعم شاورما».
  - تفهم موقعك: «برجر قريب مني».
  - تصحح أخطاء الإملاء: «ستاربك» ← ستاربكس.
- **المرشد السياحي**: «عندي يومين في الرياض ومعي اطفال وساكن في ماريوت» يطلع جدولاً لكل يوم (صباح، غداء، عصر، مساء، عشاء).
  - الأماكن قريبة من بعض ومن الفندق، ولكل يوم رابط مساره في خرائط Google.
  - مع كل محطة نصيحة قصيرة من المرشد.
- **📍 موقعي**: يحدد فندقك من موقعك، أو يبحث من مكانك مباشرة. يحتاج HTTPS، وGitHub Pages يوفره.
- **بحث بالصوت** (Chrome وSafari)، **روابط مشاركة**، و**طباعة الجدول أو حفظه PDF**.

## كيف يشتغل الذكاء الاصطناعي

ما فيه نموذج لغة كبير. كل شي خفيف ويشتغل في المتصفح:

- **3 نماذج Logistic Regression** مدرَّبة بـ scikit-learn على جمل اصطناعية (لهجة سعودية، فصحى، إنجليزي):
  - مصنّف نوع الخدمة.
  - مصنّف «أقرب أو أفضل».
  - واسم كلمات (BIO) يستخرج الفندق والعلامة والمسافة والتقييم والعدد.
- **مطابقة أسماء الفنادق** بـ TF-IDF على مقاطع الحروف، مع بصمة نطقية عربي ↔ إنجليزي.
- **طبقة قواعد** فوق النماذج: «قريب مني»، نوع الأكل، تصحيح الإملاء، الخدمات غير المتوفرة، طلبات الرحلات.
- **مخطِّط الرحلات** (`nlp/trip.js`) يختار المعالم حسب وقت اليوم والاهتمامات والقرب، والمطاعم بالتقييم مع عدد المراجعات.

التفاصيل والنتائج في [`nlp/README.md`](nlp/README.md).

## إعادة البناء

```bash
cd nlp
python3 build_brands.py page_v1.html
python3 train.py page_v1.html
node eval.js
python3 build_places.py riyadh_places.tsv places.json
python3 build_page.py page_v1.html ../index.html
```

## البيانات والتنبيهات

- **المعالم والترفيه والمولات والحدائق** من OpenStreetMap: © OpenStreetMap contributors، رخصة [ODbL](https://www.openstreetmap.org/copyright). ما فيها تقييمات، وأوقات الدوام متوفرة لأماكن قليلة.
- **بيانات التدريب اصطناعية**، فأرقام الاختبار الاصطناعي متفائلة. الجمل المكتوبة يدوياً هي المقياس الأصدق، والخطوة الجاية جمع أسئلة حقيقية.
- **أوقات الجدول تقديرية**. تأكد من أوقات الدوام قبل الذهاب.

---

**English summary.** A single-page, in-browser (no server, no API) Arabic/English natural-language assistant for Riyadh hotel guests: nearest services, named chains, cuisine, "near me" via geolocation, and a day-by-day trip planner (tour guide) built from OpenStreetMap places and rated restaurants. NLU uses three small logistic-regression models plus a TF-IDF/phonetic hotel-name matcher and a rule layer. Hand-written test sets are in `nlp/eval.js`. The synthetic test scores are optimistic.
