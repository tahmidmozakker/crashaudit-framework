# জমির পরিমাপ — Land Measurement App (Bangladesh)

An offline-first web app (PWA) for Bangladeshi land units. Install it from Chrome
on a phone and it behaves like a native app — its own icon, no browser bars, and
it keeps working with no internet.

## What's in it

| Tab | Contents |
|---|---|
| রূপান্তর | Live converter across 21 units — কাঠা, বিঘা, শতাংশ, কানি, পাকি, গন্ডা, করা, ক্রান্তি, ছটাক, অযুতাংশ, বর্গফুট, বর্গহাত, বর্গগজ, বর্গলিংক, বর্গচেইন, বর্গমিটার, আয়ের, একর, হেক্টর, বর্গকিলোমিটার, বর্গমাইল. Tap any result to copy it. |
| তালিকা | The full traditional reference lists (কাঠা / কানি / বিঘা / পাকি / শতাংশ / একর / হেক্টর / গন্ডা পরিমাপক), with search and highlighting, plus a note on the figures in the popular lists that contradict each other. |
| পরিভাষা | খতিয়ান, পর্চা, চিটা, দখলনামা, বয়নামা, জমাবন্দি, দাখিলা, হুকুমনামা, জমা খারিজ, মৌজা — what each document is. |
| অ্যাপ | Install instructions plus an in-page install button on Chrome. |

Bengali numerals by default; the `১২৩` button in the header switches to Latin digits.

## Conversion basis

Everything converts through **square feet**, so the units stay consistent with
each other:

```
১ কাঠা   = ৭২০ বর্গফুট        ২০ কাঠা = ১ বিঘা        ১৬ ছটাক = ১ কাঠা
১ শতাংশ  = ৪৩৫.৬ বর্গফুট      ১০০ শতাংশ = ১ একর      ১০০ অযুতাংশ = ১ শতাংশ
১ কানি   = ২৪ কাঠা = ২০ গন্ডা  ১ গন্ডা = ৪ করা         ১ করা = ৪ ক্রান্তি
১ হাত    = ১.৫ ফুট            ১ লিংক = ০.৬৬ ফুট       ১ আয়ের = ১০০ বর্গমিটার
```

কানি is taken as the 40-শতাংশ (24-কাঠা) কানি. The 120-শতাংশ কানি used in some
areas is three times that. Local names and measures vary by region — the local
land office's figure is the one that counts for any deed or survey.

Rates live in `data.js` (`UNITS`), as do the reference lists (`TABLES`), the
list of contradictions (`CAVEATS`) and the glossary (`GLOSSARY`). Edit that one
file to change any number or wording.

## Install on a phone

1. Open the app's URL in **Chrome** (Android) or **Safari** (iPhone).
2. Android: ⋮ menu → *Install app* / *Add to Home screen* → *Install*.
   iPhone: share button → *Add to Home Screen* → *Add*.
3. Open it once while online; after that it runs fully offline.

Installation requires the page to be served over **HTTPS** (or `localhost`) —
opening `index.html` as a `file://` path will show the app but Chrome will not
offer to install it and the offline cache will not register.

## Hosting it

Any static host works — nothing runs on the server.

**GitHub Pages:** merge this folder to the default branch, then Settings →
Pages → Source: *Deploy from a branch*, branch `main`, folder `/ (root)`. The
app is then at `https://<user>.github.io/<repo>/land-converter/`.

**Local check:**

```bash
cd land-converter
python3 -m http.server 8000
# then open http://localhost:8000/
```

## Files

```
index.html            app shell and all page structure
styles.css            styling, light + dark theme
data.js               units, conversion rates, reference tables, glossary
app.js                converter, search, tabs, install prompt
sw.js                 service worker (offline cache) — bump CACHE after edits
manifest.webmanifest  PWA metadata: name, icons, colours, display mode
icons/                generated PNG icons
tools/make_icons.py   regenerates icons/ (no third-party libraries needed)
```

After changing any file, bump the `CACHE` version string in `sw.js` so
installed copies pick up the new version.
