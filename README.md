# XETAFIT — Landing Page

**Fizz your way to wellness.** A single-product landing page for XETAFIT Apple
Cider Vinegar Effervescent Tablets, Pack of 4. Built with **HTML and CSS**, plus a small JavaScript controller for the Benefits scroll animation. No frameworks or build step.

The copy follows `XETAFIT_Landing_Page_Content_V9_Benefits_Update.pdf` (Content V9)
and the CTA plan matches it. The **visual and motion system** is a rebuild modelled
on the supplied beverage-site reference recording: saturated red page, deep
burgundy contrast panels, warm cream product cards, golden purchase buttons,
heavy sans headlines with an editorial serif, a floating capsule header, giant
low-opacity serif lettering and numbered editorial layouts. Only XETAFIT's own
logo, packaging and photography are used; nothing from the reference brand.

---

## 1. Run it

No build step.

- **Quickest:** double-click `index.html`.
- **Closer to production:**
  ```bash
  cd xetafit-landing
  python -m http.server 8080      # then open http://localhost:8080
  ```

Fonts (DM Sans, Cormorant Garamond) load from Google Fonts. Offline, the page
falls back to system fonts.

## 2. Project structure

```text
xetafit-landing/
├── index.html            12 sections (V9 order) + footer
├── certificate.html      Certificate of Analysis details (batch NX3649)
├── css/
│   ├── style.css         tokens, components, header + menu, phone-first section layouts, certificate page
│   ├── responsive.css    tablet / desktop compositions (640 · 760 · 960 · 1100 · 1440 px, short desktops)
│   └── animations.css    all motion: hero sequence, reveals, scroll zoom, lettering drift, breathing, nav highlight
├── assets/
│   ├── source/           xetafit-tube-front.png: the studio packshot every product image is built from
│   ├── images/           product, tablet and bubble renders, photographs, certificate previews
│   └── documents/        original COA PDF (byte-identical copy)
└── tools/
    ├── render_product.py      builds all product + tablet renders from assets/source (see §5b)
    ├── render_props.py        ray-traces glass/prop renders and the hero bubble sprites (see §5c)
    ├── compose_comparison.py  places the tube render into the finished-drink photo for 08 (see §5c)
    ├── build_hero_layers.py   the hero opening layers: cap, open tube, inner wall, tablet frame strips (see §4b)
    ├── make_fizz.py           generates the hero bubble markup and writes it into index.html
    ├── make_responsive.py     smaller copies of the large images for srcset
    ├── extract_logo.py        cuts the official logo out of the brand's creative (see §3)
    └── prepare_assets.py      builds the certificate previews
```

## 3. Design system

**Colour.** Sampled from the reference frames, then contrast-checked (WCAG):

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--red` | `#DF1635` | page background, open sections, the stages behind product renders | white text 4.9:1 |
| `--burgundy` | `#AE0E29` | contrast panels (02, 05, 08, 10), lifestyle card, final card, safety notes | white 7.3:1, gold 4.5:1 |
| `--burgundy-deep` | `#A3071E` | header capsules, footer | white 8.1:1 |
| `--cream` | `#FDF2E3` | product container, step / review / comparison cards, cream panels (06, 11) | ink 17:1 |
| `--gold` | `#FDAB1C` | purchase buttons only (Buy now, Add to cart, Get your 4-pack) | ink text 9.9:1 |
| `--gold-hi` | `#FAC53C` | italic headline accents, numerals, labels on burgundy | 3.1:1 on red: large type only |
| `--ink` | `#1E0D09` | text on cream, logo plate, small badges | |
| `--ink-soft` / `--red-ink` | `#6B4A40` / `#B50F2C` | secondary text / red accents on cream | 7.1:1 / 6.1:1 |

Rules: small text on red is always white (cream is 4.4:1); gold text on red is only
used at headline sizes. The green-and-white packaging is never recoloured: its
contrast with the red is the point.

**Type.** DM Sans 800 capitals for headlines (tight tracking), with an italic
Cormorant Garamond accent in gold (`.h2 em`). Editorial panels use all-serif
capitals (`.h2--serif`: Benefits, Lifestyle). Cormorant also sets product names,
step names, numerals and the giant background lettering (always lining figures).
DM Sans 400–700 for body, labels and buttons. All sizes use `clamp()`. The hero
headline is one line from 1100 px up, two lines on tablets, three on phones.

**Surfaces.** The page is red. A section is either *open* (on the red) or a
*panel*: a rounded burgundy or cream block inset 8–14 px from the page edge, so a
strip of red shows between neighbouring blocks, as in the reference. Each surface
sets `--fg / --head / --em / --soft / --line / --focus`, and every component reads
those, so a component works on any surface.

| # | Section | Surface | Composition |
|---|---|---|---|
| 01 | Hero | red | one-line headline; copy + CTA · tube with two tablets · three facts; "Fizz. Sip. Repeat." marquee behind the tube |
| 02 | The switch | burgundy panel | copy + gold check list; tilted tube on a red stage with the cream "old way" card |
| 03 | Product + purchase | red | giant "Pack of 4 · 60 Tablets" lettering behind one large cream container: pack image left, purchase column right |
| 04 | How it works | red | three cream cards with the photographed drop / fizz / sip stages and dark number badges |
| 05 | Benefits | burgundy panel | tube centred, six benefits with gold serif numerals either side, gold CTA |
| 06 | Ingredients | cream panel | tube on a red stage with "500 mg" lettering; "Per tablet" facts label with the sodium notice |
| 07 | Lifestyle | red | full campaign photograph with a burgundy card overlapping its lower left |
| 08 | Comparison | burgundy panel | cream card (liquid ACV) vs red card (XETAFIT), matching cream-studio photographs, gold "vs" disc |
| 09 | Reviews | red | four cream placeholder cards (verified reviews only), gold CTA |
| 10 | Quality | burgundy panel | certificate preview on a paper stack + batch details, View certificate |
| 11 | FAQ | cream panel | heading + always-visible safety card; native `<details>` list with hairline dividers |
| 12 | Final | red | burgundy card: headline, Buy now, four-pack photograph breaking out of the card top |

**Header.** Three floating capsules: the official logo on a near-black plate
(its orange mark is 1.4:1 on the red and 5.6:1 on the plate, so the plate is
needed), a centred burgundy navigation group whose active link turns cream as
you scroll, and on the right a certificate icon plus the cream **Product** pill.
Below 960 px the navigation becomes a **Menu** capsule that opens a full-height
burgundy menu. It is CSS only: the menu shows while `#menu` is the URL target,
and following any link inside it changes the target, so it closes by itself.
Opening it does not move the page.

**Buttons.** Compact capsules with a small arrow, 42 px (50 px for `.btn--lg`):
`.btn--gold` purchase, `.btn--cream` information, `.btn--ghost` outline on dark.
Hover and keyboard focus: the colour lightens over 0.24 s, the button lifts 1 px
and the arrow moves 3 px. The disabled Add to cart is a muted cream with a
not-allowed cursor.

## 4. Motion (CSS only)

Native scrolling: no snapping, no scroll-jacking, no JavaScript. Easing is
`cubic-bezier(.22, 1, .36, 1)` throughout; only `transform`, `scale`,
`translate` and `opacity` animate.

| Motion | Where | How |
|---|---|---|
| Hero sequence | 01, on load | header drops in; headline lines rise out of masks one after another; copy and facts follow; the Buy now row arrives last |
| Product opening | 01, on load, once | the tube stands upright and settles; its cap lifts fully clear, two tablets come out one after the other, the cap closes (see §4b) |
| Hero idle | 01, from 3.3 s | the tube floats 8 px on a 6 s cycle over a floor shadow that widens and softens as it rises; each tablet floats 8–13 px on its own clock, independently of the tube |
| Marquee | 01 | "Fizz. Sip. Repeat." in giant serif at 13 % white, 64 s seamless right-to-left loop, behind the tube, clear of the copy and facts |
| Carbonation | 01 only | 104 rendered bubbles, about 15 new a second (about 10 on phones) |
| Section entrances | every section | play **once** when a block is 10vh into view. Text 0.68 s fade-up, staggered; products 0.95 s (0.97 → 1); cards 0.75 s rise, staggered; photographs 1.25 s settle inside their frames (1.08 → 1); the two comparison cards slide in from opposite sides; Add to cart arrives last in the product card |
| Scroll-linked zoom | photographs and product compositions (not the hero tube, which stays at 1:1 for a sharp label) | `scale` 1.00 entering → peak at mid-viewport → 1.00 leaving: 1.05 for photographs (inside their rounded frames), 1.03 for compositions that also breathe |
| Lettering drift | 03, 12 | the giant background lettering slides sideways with the scroll, the two bands in opposite directions |
| Breathing | pack, benefits tube, ingredients tube, final photograph | 1.00 → 1.02, 6.4–8 s a cycle, starting after the entrance, on its own nested wrapper |
| Light | product renders, campaign photographs | a soft light band sweeps each render every 10 s (masked to its silhouette); a slow daylight shift over the photos |
| Hover | buttons, header, cards, certificate | buttons 0.24 s; cards lift 3–4 px; the certificate straightens |
| Navigation / FAQ | header / 11 | the link of the section in view becomes a cream capsule; answers open and close smoothly where `::details-content` is supported |

**One transform, one element.** `.rv` triggers, its children play the entrance,
`.zoom` follows the scroll, `.breathe` loops. **"Play once when seen" without
JavaScript:** `.rv` runs a scroll-driven animation (`animation-timeline: view()`)
whose only job is to set the registered property `--seen` to 1. The children's
time-based entrances start paused, and `@container style(--seen: 1)` sets them
running, so they finish and hold even if you stop scrolling.

**Watch out:** `overflow: hidden` makes a scroll container, and `view()` inside it
would track that box instead of the page. Frames around zooming images use
`overflow: clip`.

| Situation | Result |
|---|---|
| Chrome / Edge 115+, Safari 26+ | full experience |
| Browsers without scroll-driven animations (e.g. current Firefox) | every section visible at once, no scroll zoom or drift; the hero sequence, marquee, bubbles, floating and breathing still run |
| `prefers-reduced-motion: reduce` | no animation, no bubbles, no smooth scrolling; everything visible |

Safety information (the sodium notice, the safety card) is never animated or hidden.

**Tested** in Chrome 157 (headless, DevTools protocol) at 1920×1080, 1440×900,
1280×720, 1024×768, 768×1024 and 390×844. Results: no horizontal overflow on
either page; the headline never collides with the tube; the hero facts and CTA
stay clear of the marquee; all 83 revealed elements reach full opacity after
scrolling; zoom measured at 1.00 / 1.05 / 1.00; the menu opens without moving the
page and closes on navigation; reduced motion leaves zero running animations.
**Not yet tested:** Safari, Firefox, real touch devices, frame-rate profiling on
low-end phones.

### 4b. The hero product opening (CSS only, plays once)

| Time | What happens |
|---|---|
| 0–0.6 s | the closed tube stands upright and settles 6 px onto its floor shadow, which forms underneath |
| 0.6–1.3 s | the cap unseats and lifts fully clear (about 14 % of the art height, 4° tilt), then hovers over the open mouth; both tablets sit deep, so the mouth reads dark and open |
| 1.3–2.0 s | tablet 1 rises out of the opening behind the front lip, glides left above the rim, then floats down to its place (settled at 2.3 s) |
| 2.0–2.7 s | tablet 2 (one tablet lower in the tube) rises out, glides right above the rim, then floats down to the lower right (settled at 3.25 s) |
| 2.7–3.3 s | the cap comes back down, aligns with the mouth and seats; the closed tube takes over again |
| 3.3 s on | idle floating: tube 8 px / 6 s; tablets 9–13 px / 6.4 s and 8–12 px / 7.2 s (scaled with the art), independent of the tube; each tablet starts as it lands |

The flight paths were checked frame by frame against the real layer masks: once a
tablet is in front of the tube it never overlaps the tube wall, the cap or the other
tablet, and below the rim it keeps at least 2 % of the art height from the tube's sides.

**Layers** (`tools/build_hero_layers.py`, about 3 minutes; `--tubes` skips the tablets).
All tube layers share one 360 × 1369 canvas, so they register exactly:

| File | What it is |
|---|---|
| `hero-tube.webp`, `hero-tube-190.webp` | the closed tube at full source resolution, plus a pre-scaled copy for 1× screens (`srcset`) |
| `hero-cap.webp` | the cap alone, cut along the real cap/label seam, so it is pixel-identical to the cap on the closed tube |
| `hero-tube-open.webp` | the tube without its cap: label, front wall and front lip; the opening itself is transparent |
| `hero-tube-inner.webp` | what is seen through the opening: the far half of the rim and the shaded inner wall |
| `hero-tablet-1.webp`, `hero-tablet-2.webp` | 16 ray-traced frames each (320 px), from lying flat in the tube to the resting angle; CSS steps through them in flight |

The source photo never shows the tube without its cap, so the open state is built
from geometry, not invented artwork: the camera elevation (8.2°) is measured from
the cap's top ellipse, the opening is that ellipse at the body radius, the label's
own top green band continues up to the rim, and the rim and inner wall use the
studio shading measured on the white label paper. No printed detail is created or
changed. The tablets are the same 3D model, seed and spin as `tablet-a/b`, sized to
fit the tube (radius 0.89 × its inner radius).

**Stacking** inside `.hero__product`, back to front: inner wall (`.hero__well`) ·
tablets while inside (z-index 2) · open tube · closed tube · cap · tablets once their
lowest edge clears the front lip (z-index 6). Horizontal and vertical motion run on
separate wrappers (`.tab` and `.tab__y`), so each flight path is a smooth curve; the
idle bob (`.tab__bob`) and the frame strip (`.tab__img`) are nested inside. The idle
float of the tube runs on `.hero__closed` (the only tube layer visible after 3 s), so the
tablets drift independently instead of riding along with the tube. The lifted cap
hovers above both tablet paths and never touches them. All
distances are in `cqh` (1 % of the art height), so the sequence scales with every
breakpoint and never reaches the headline, CTA or facts.

**Sharpness.** The tube is no longer rotated or scroll-zoomed in the hero (both made
the browser resample the label). The packshot itself is 1024 × 1536 and the tube in
it is about 360 × 1370 px. That is enough for the hero at 2× pixel density, but a
**studio render of the tube at about 2000 px tall** would be the next step up, and
would rebuild every layer with `python tools/build_hero_layers.py`.

**Fallbacks.** Reduced motion: no sequence, the closed tube and both tablets are
shown at their final positions, nothing floats. The opening layers are preloaded;
the closed tube is always the base state, so the product never stays hidden.

## 5. Integration points (search the HTML for `INTEGRATION POINT`)

| What | Where | Status |
|---|---|---|
| **Add to cart** | `#buy` → `<form class="cart">` | **Inactive by design.** The button is `disabled` and a visible note says the store is not connected. To activate: set `action` (e.g. Shopify `/cart/add`), put the **four-pack variant ID** in `name="id"`, then remove `disabled` and the `.cart-status` note. Only the four-pack may be added. |
| **Live price / stock / delivery** | `#buy` → `<dl class="live">` | Placeholders (`.pending`). Fill server-side or via store templating. No price is hard-coded. |
| **Customer reviews** | `#reviews` → `<ul class="review-track">` | Four labelled placeholders. Replace them with verified, permission-cleared reviews only (exact text, reviewer name as displayed, platform, date), then delete the `.dev-note`. |
| **Logo** | header and footer of both pages | Official logo in place (256 × 68 raster cut from the brand's creative by `tools/extract_logo.py`). Swap `assets/images/xetafit-logo.png` for the official SVG when available. |

### CTA plan (V9), as built

| Section | CTA | Target |
|---|---|---|
| 01 Hero | Buy now (+ Pack of 4 card) | `#buy` |
| 03 Product | Add to cart | store (inactive until connected) |
| 05 Benefits | Get your 4-pack | `#buy` |
| 09 Reviews | Get your 4-pack | `#buy` |
| 10 Quality | View certificate | `certificate.html` (which links the original PDF) |
| 12 Final | Buy now (+ Pack of 4 card) | `#buy` |

The header has no Buy Now button, because V9 allows Buy Now only in scenes
01 and 12. Its right-hand pill is the "Product" navigation link to `#buy`.

## 5b. Product renders (one master asset, reused everywhere)

Every product image on the page comes from **one** studio packshot,
`assets/source/xetafit-tube-front.png`, via `tools/render_product.py`:

```bash
pip install numpy pillow opencv-python-headless
python tools/render_product.py                 # everything (~1 min)
python tools/render_product.py --tubes         # tube views, shadows, four-pack only
python tools/render_product.py --tablets       # the two tablets only
python tools/render_product.py my-photo.png    # rebuild from a different packshot
```

| File | What it is | Used in |
|---|---|---|
| `tube-front.webp` | master front view with a geometric anti-aliased matte (no white fringe) | 05 benefits, the hero light-sweep mask |
| `tube-angle.webp` | the same tube turned 24° on its axis: label re-projected on a 3D cylinder under the same studio light | 06 ingredients, 08 comparison composite |
| `tube-tilt.webp` | the turned tube leaning 24° | 02 the switch |
| `tube-shadow.webp` / `tube-shadow-soft.webp` | the real ground shadow lifted from the studio shot (contact line + falloff) / a diffused version for floating tubes | under every single tube |
| `pack4.webp` (+ `pack4-640.webp`) | four tubes in a receding row, each label turned slightly, with ground shadows and occlusion shadows between tubes | 03 product container |
| `tablet-a.webp`, `tablet-b.webp` | two effervescent tablets ray-marched in 3D: pale mint, chalky, porous, green flecks, lit like the tube | 02 switch, 06 ingredients (the hero uses the same two tablets as frame strips, §4b) |

The tube is a surface of revolution, so its outline, cap and base are identical
at any rotation and only the label moves. The script reads each label point
from the source, removes the source's own studio shading (measured on the white
label areas) and applies the shading of its new position. The lights stay fixed
while the tube turns. Label areas the source never shows (the far side, past
~65°) continue each row's band colour. Shadows are separate images placed in
tube-relative percentages (`.tube__shadow` in `css/style.css`, numbers from
`tools/render-placement.json`). No CSS `drop-shadow` is used on product images.

**Limits, honestly:** this is image-based 3D, not a modelled CAD render. The
front view is the supplied packshot itself. Turned views are accurate for small
turns, but the far side of the label is synthesised from the band colours. For
full 360° accuracy, supply the flat label artwork (dieline) or photos from more angles.

## 5c. Realistic props and the fizz atmosphere

No illustrated elements remain: the SVG glass plates, the line-art bottle,
jigger, plate, laptop and bag icons, and the CSS-drawn bubbles, ripples and foam
are all gone. `tools/render_props.py` (about 1.5 min) ray-traces the replacements
with refraction, Fresnel reflections from studio softboxes, total internal
reflection, Beer-Lambert absorption and scattering in the drink:

| File | What it is | Used in |
|---|---|---|
| `glass-water.webp`, `glass-drink.webp`, `glass-shine.webp`, `glass-fizz.webp`, `glass-mask.webp` | the tumbler as registered layers (rendered on the earlier forest green) | not used |
| `glass-drink-arch.webp` | the finished drink on the earlier lifestyle arch colour | not used |
| `shot-amber.webp` | shot glass of liquid ACV (rendered on `#F6EBD3`, the tile colour behind it) | 02 the switch ("the old way") |
| `plinth.webp` | clay plinth with contact shadow | not used |
| `bubble-1..3.webp` | hero carbonation sprites: thin bright meniscus ring, warm inner edge, specular point (`python tools/render_props.py --bubbles` rebuilds only these) | 01 hero |
| `tablet-c.webp` | a third tablet render, lying flat (from `render_product.py`) | not used |

Each render sits on the exact colour of the area it is placed on, so edges never show.

**Carbonation (hero only).** The other sections get their sparkle from light
and movement on existing visuals, not from particles (see §4). To change the
bubble count, sizes or speeds, edit the settings at the top of
`tools/make_fizz.py` and run it: it rewrites the hero field in `index.html` and
prints the resulting bubbles per second.

**Photographs.** Sections 04, 07, 08 and 12 use photographs (prompts in
`assets/images/*-prompt.txt` and `refinement-generation-notes.txt`):
`preparation-sequence.webp` (04, one file cropped three ways), `lifestyle-workspace.webp`
(07), `comparison-vinegar.webp` (08, left) and `final-product-drink.webp` (12). The two
large photos have 768 px copies for phones (`tools/make_responsive.py`).

**Comparison composite.** The XETAFIT side of 08 needs the tube beside a prepared
drink in the same cream studio light as the vinegar photo. `tools/compose_comparison.py`
builds `comparison-xetafit.webp` from the "sip" frame of `preparation-sequence.webp`
and `tube-angle.webp`: the tube is sized to about 1.1 × the tumbler, warm-graded to the
photo's light, softened to its sharpness and given a contact shadow and a soft cast
shadow. The label itself is not altered. Replace it with a real photograph of the
pack and a prepared glass when one exists.

## 6. Assets to replace before launch

1. **Packshot source.** Everything is built from `assets/source/xetafit-tube-front.png`
   (1024 × 1536). A real studio photo or official 3D render of the current pack,
   front-on on white at about 2000 px tall, can replace it. Re-run
   `tools/render_product.py` and every image on the page updates.
2. **Official logo SVG** (the header currently uses a 256 × 68 raster cut from the brand's creative: crisp on standard screens, slightly soft on high-density ones).
3. **Ingredient photography.** The brief asks for realistic green apples and
   pomegranate in section 06. The project has no such photographs, and none were
   invented, so 06 shows the tube and a tablet on red, and the only fruit is the
   artwork on the pack label. Supply a licensed or shot photograph (green apples,
   a split pomegranate, a tablet; on a plain background) and it can drop into the
   red stage in `.ing__stage`.
4. **A real XETAFIT + glass photograph** to replace the 08 composite (see §5c), and
   *(optional)* more lifestyle moments (morning, active, on the move).
5. Verified reviews (see §5).

## 7. Open questions for the client (unchanged from V9)

1. **Flavour name.** V9 says *Green Apple + Pomegranate flavour*; the pack art says *Green Apple Flavor*; the COA says *(green Apple)*. The site follows V9.
2. **Dose and daily limit.** V9 points to "the currently approved label" without numbers, so the site states none.
3. **Four-pack SKU, live price, stock** (§5).
4. **COA batch.** NX3649 (mfd 08/2025, exp 01/2027) should match the stock being sold.
5. **"With The Mother"** is presented as the brand's description. The COA does not verify it, and the site says so.
   **Note:** the new packshot's label does *not* say "With The Mother". It reads "Daily Plant-Based",
   "Enzyme, Antioxidants" and "Health Supplement (with Natural Sweetener)", which differs from the
   earlier pack art ("With The Mother", "Energize. Metabolize."). Please confirm which label is
   current. If "With The Mother" is no longer on pack, the ingredients note should change. Also
   check that the label's "Antioxidants" wording is cleared, since the site copy itself makes no such claim.
6. **Review permissions** for any XETAFIT / Flipkart / Amazon reviews.
