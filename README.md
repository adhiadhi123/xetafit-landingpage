# XETAFIT — Landing Page (Redesign)

**Fizz your way to wellness.** A single-product landing page for XETAFIT Apple
Cider Vinegar Effervescent Tablets, Pack of 4. Built with **HTML and CSS only**:
no JavaScript and no frameworks.

The copy follows `XETAFIT_Landing_Page_Content_V9_Benefits_Update.pdf` (Content V9)
scene by scene, and the CTA plan matches it exactly. The visual design follows
the six-frame storyboard: colour-block sheets, a floating pill navigation,
rounded cream product containers, centred product compositions with numbered
facts, and giant translucent editorial type.

---

## 1. Run it

No build step.

- **Quickest:** double-click `index.html`.
- **Closer to production:**
  ```bash
  cd xetafit-landing
  python -m http.server 8080      # then open http://localhost:8080
  ```

Fonts (DM Sans, Cormorant Garamond, Inter) load from Google Fonts. Offline, the
page falls back to system fonts.

## 2. Project structure

```text
xetafit-landing/
├── index.html            12 sections (V9 order) + footer
├── certificate.html      Certificate of Analysis details (batch NX3649)
├── css/
│   ├── style.css         design tokens, components, mobile-first section layouts, certificate page
│   ├── responsive.css    tablet / desktop compositions (640 · 760 · 960 · 1100 · 1440 px)
│   └── animations.css    all motion: hero entrance + carbonation, reveals, scroll zoom, breathing, ambient light, nav highlight
├── assets/
│   ├── source/           xetafit-tube-front.png — the studio packshot every product image is built from
│   ├── images/           product, tablet, glass, prop and bubble renders; certificate previews
│   └── documents/        original COA PDF (byte-identical copy)
└── tools/
    ├── render_product.py     builds all product + tablet renders from assets/source (see §5b)
    ├── render_props.py       ray-traces the glass, drink, shot glass, plinth and bubbles (see §5c)
    ├── make_fizz.py          generates the hero bubble markup and writes it into index.html
    ├── props-geometry.json   water-surface / base positions the glass CSS uses
    ├── render-placement.json shadow offsets the CSS uses (written by render_product.py)
    └── prepare_assets.py     builds the certificate previews (its storyboard product cut-outs are no longer used)
```

## 3. Design system

| Token | Value | Use |
|---|---|---|
| `--coral` | `#F46B62` Grapefruit Coral | hero and promotional sheets |
| `--green` | `#174D3A` Deep Forest Green | headlines, contrast sections, buttons |
| `--cream` | `#FFF8E9` Warm Cream | content sheets, product containers, cards |

Tonal steps of the same three colours, each contrast-checked against WCAG AA:

| Token | Value | Why it exists |
|---|---|---|
| `--green-ink` | `#0F3127` | body text on coral (4.8:1). Forest green on coral is 3.3:1, so it is used only for large headlines. |
| `--coral-deep` | `#C2423B` | the inset Benefits panel; cream text on it is 4.8:1 |
| `--coral-ink` | `#B83F38` | coral-coloured text on cream (5.2:1) |
| `--coral-soft` | `#F7A59E` | coral accent text on green (5.0:1) |

Cream text is never placed directly on coral (2.8:1).

**Type:** DM Sans 700 for bold capital headlines; Cormorant Garamond 500/600 (with
italics) for editorial accents, product names and numerals (always with
lining figures); Inter 400/500/600 for body text and labels.

**Section sheets:** every section after the hero slides over the previous one
with rounded top corners (`.sec + .sec`). That overlap is the colour transition
between sections. Themes (`.sec--coral`, `.sec--cream`, `.sec--green`) set
the colour variables that every component reads.

| # | Section | Sheet | Composition |
|---|---|---|---|
| 01 | Hero | coral | one-line headline (V9), product centred between copy and facts, giant translucent type |
| 02 | The switch | cream | editorial copy + coral product stage with the "old way" card |
| 03 | Product + purchase | coral | cream product container; the pack image breaks out of the top |
| 04 | How it works | green | three photographed preparation stages: drop, fizz, sip |
| 05 | Benefits | coral (deep panel) | tube centred, six numbered benefits either side |
| 06 | Ingredients | cream | coral product photo + "per tablet" fact label + sodium notice |
| 07 | Lifestyle | green | lifestyle photograph + three routine moments |
| 08 | Comparison | cream | split "Liquid ACV vs XETAFIT" panel |
| 09 | Reviews | coral | placeholder review cards (verified reviews only) |
| 10 | Test report | green | certificate preview + batch details |
| 11 | FAQ | cream | sticky heading + always-visible safety card + accordion |
| 12 | Final | coral | green card: headline, Buy Now, four-pack-and-drink photograph |

## 4. Motion (CSS only)

Native scrolling: no snapping, no scroll-jacking, no JavaScript. Anchor links
scroll smoothly when motion is allowed. Easing is `cubic-bezier(.22, 1, .36, 1)`
throughout, and only `transform`, `scale`, `translate` and `opacity` animate.

| Motion | Where | How |
|---|---|---|
| Carbonation | **hero only** | 104 rendered bubbles (60% 4–5 px, 30% 7–9 px, 10% 11–14 px), about **15 new bubbles a second** (about 10 on phones, where every third is hidden). Each has its own start height (weighted to the lower and middle hero), rise distance, speed (larger bubbles rise faster), sideways drift and peak opacity. Five loose chains rise from fixed "nucleation points", like a real glass. Bubbles fade in where they start and fade out towards the top. They sit behind all content, never block clicks, and are clipped to the hero. |
| Hero entrance | 01 | on page load: headline lines, product, supporting text, CTA and facts, staggered |
| Section entrances | every section | played **once** when a block is 10vh into the viewport (see below). Text 0.55–0.75 s fade-up; products 0.9–1.1 s zoom-in (0.94 → 1); photographs 1.3 s cinematic settle (1.08 → 1); certificate 1 s scale-in. The switch slides its two halves in from left and right, the comparison its two columns from opposite sides. Preparation steps, benefits (icon first, then text), review cards and FAQ rows follow each other. Review cards and FAQ rows never zoom. |
| Scroll-linked zoom | hero, product, how it works, ingredients, lifestyle, comparison, certificate, final | `scale` follows the element's position: 1.00 entering → peak at the centre of the viewport → 1.00 leaving. Peak 1.035 for product images, 1.05 for photographs, 1.03 where the image also breathes. Photographs zoom **inside** their rounded frames, so nothing spills onto the content around them. The hero tube is anchored near its cap, so it never grows into the headline. |
| Breathing | hero tube + tablets, four-pack, benefits tube, ingredients tube, final photograph | 1.00 → 1.02 → 1.00, 6.4–8 s per cycle, starting after the entrance. Lives on its own nested wrapper, so scroll zoom × breathing never exceeds about 1.05. |
| Product light | hero, product, benefits and ingredients renders | a soft band of light sweeps across the render every 10 s, masked to the render's own silhouette |
| Ambient | tablets (hero, switch, ingredients); lifestyle and final photographs | tablets drift a few pixels; a slow daylight shift moves across the two campaign photographs |
| Marquee | 01 | "Drop. Fizz. Sip." at 12% opacity, 70 s seamless right-to-left loop, below the CTA and facts |
| Hover | buttons, cards, certificate | buttons 0.22 s; cards lift; the certificate straightens |
| FAQ / Nav | 11 / nav | smooth open and close where `::details-content` is supported; the link of the section in view is highlighted |

**One transform, one element.** Each visual is nested so that no two animations
fight over the same property: the `.rv` trigger holds the composition, `.reveal`
(or the trigger's direct child) plays the entrance, `.zoom` follows the scroll,
and `.breathe` loops. The sheen, light and drift layers sit inside those.

**"Play once when seen" without JavaScript.** A trigger (`.rv`) runs a
scroll-driven animation (`animation-timeline: view()`) whose only job is to set
the registered property `--seen` to `1`. Its children carry normal time-based
entrances that start *paused*, and `@container style(--seen: 1)` switches them to
*running*. They then hold their last frame, so text is never left half-faded
when you stop scrolling.

**Watch out:** an element with `overflow: hidden` is a scroll container, and
`view()` inside it tracks that box instead of the page. Frames that hold zooming
images therefore clip with `overflow: clip`.

### What each browser gets

| Situation | Result |
|---|---|
| Chrome / Edge 115+, Safari 26+ | full experience |
| Browsers without scroll-driven animations (e.g. current Firefox) | every section visible at once, no scroll zoom; hero entrance, bubbles, breathing and light sweeps still run |
| `prefers-reduced-motion: reduce` | no animation at all: no bubbles, light sweeps, breathing or zoom; no smooth scrolling; all content visible |

Essential information (sodium, precautions, the safety card) is never hidden
behind animation or interaction.

**Tested** in Chrome 157 (headless, DevTools protocol) at 1440×900, 1280×720 and
390×844 (mobile emulation). Checks covered: the zoom scale at three scroll
positions per visual, entrances caught mid-play and settled, every revealed
element at full opacity afterwards, the light sweep frame by frame, reduced
motion, and no horizontal overflow. **Not yet tested:** Safari, Firefox, Edge and
real touch devices; frame-rate profiling on low-end phones.

## 5. Integration points (search the HTML for `INTEGRATION POINT`)

| What | Where | Status |
|---|---|---|
| **Add to cart** | `#buy` → `<form class="cart">` | **Inactive by design.** The button is `disabled` and a visible note says the store is not connected. To activate: set `action` (e.g. Shopify `/cart/add`), put the **four-pack variant ID** in `name="id"`, then remove `disabled` and the `.cart-status` note. Only the four-pack may be added. |
| **Live price / stock / delivery** | `#buy` → `<dl class="live">` | Placeholders (`.pending`). Fill server-side or via store templating. No price is hard-coded. |
| **Customer reviews** | `#reviews` → `<ul class="review-track">` | Four labelled placeholders. Replace them with verified, permission-cleared reviews only (exact text, reviewer name as displayed, platform, date), then delete the `.dev-note`. |
| **Logo** | nav + footer of both pages (`LOGO PLACEHOLDER`) | Text wordmark only. Swap in the official XETAFIT logo SVG. |

### CTA plan (V9), as built

| Section | CTA | Target |
|---|---|---|
| 01 Hero | Buy now (+ Pack of 4 card) | `#buy` |
| 03 Product | Add to cart | store (inactive until connected) |
| 05 Benefits | Get your 4-pack | `#buy` |
| 09 Reviews | Get your 4-pack | `#buy` |
| 10 Test report | View certificate | `certificate.html` (which links the original PDF) |
| 12 Final | Buy now (+ Pack of 4 card) | `#buy` |

The navigation has no Buy Now button, because V9 allows Buy Now only in scenes
01 and 12. Its right-hand pill is the "Product" navigation link.

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
| `tube-front.webp` | master front view with a geometric anti-aliased matte (no white fringe) | hero, benefits, lifestyle |
| `tube-angle.webp` | the same tube turned 24° on its axis: label re-projected on a 3D cylinder under the same studio light | ingredients, lifestyle, reviews |
| `tube-tilt.webp` | the turned tube leaning 24° | the switch, lifestyle |
| `tube-shadow.webp` / `tube-shadow-soft.webp` | the real ground shadow lifted from the studio shot (contact line + falloff) / a diffused version for floating tubes | under every single tube |
| `pack4.webp` | four tubes in a receding row, each label turned slightly, with ground shadows and occlusion shadows between tubes | product card, comparison, final |
| `tablet-a.webp`, `tablet-b.webp` | two effervescent tablets ray-marched in 3D: pale mint, chalky, porous, green flecks, lit like the tube | hero (exactly two), switch, how it works, ingredients, final fizz |

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
| `glass-water.webp`, `glass-drink.webp`, `glass-shine.webp`, `glass-fizz.webp`, `glass-mask.webp` | the tumbler as registered layers (rendered on forest green) | 04 how it works, 12 final fizz |
| `glass-drink-arch.webp` | the finished drink on the lifestyle arch colour | 07 lifestyle |
| `shot-amber.webp` | shot glass of liquid ACV (rendered on the cream card colour) | 02 the switch ("the old way"), 08 comparison |
| `plinth.webp` | clay plinth with contact shadow | 07 lifestyle (three product sets) |
| `bubble-1..3.webp` | hero carbonation sprites tuned for coral: thin bright meniscus ring, deeper-coral inner edge, specular point (`python tools/render_props.py --bubbles` rebuilds only these) | 01 hero |
| `tablet-c.webp` | a third tablet render, lying flat (from `render_product.py`) | 07 lifestyle |

Each render sits on the exact colour of the area it is placed on, so edges never show.

**Carbonation (hero only).** The other sections get their sparkle from light
and movement on existing visuals, not from particles (see §4). To change the
bubble count, sizes or speeds, edit the settings at the top of
`tools/make_fizz.py` and run it: it rewrites the hero field in `index.html` and
prints the resulting bubbles per second.

**Note:** sections 04, 07, 08 and 12 now use photographs (prompts in
`assets/images/*-prompt.txt` and `refinement-generation-notes.txt`). The glass,
shot-glass and plinth renders above are still in `assets/images`, but the page no
longer references them.

## 6. Assets to replace before launch

1. **Packshot source.** Everything is built from `assets/source/xetafit-tube-front.png`
   (1024 × 1536). A real studio photo or official 3D render of the current pack,
   front-on on white at about 2000 px tall, can replace it. Re-run
   `tools/render_product.py` and every image on the page updates.
2. **Official logo SVG.**
3. *(Optional)* real photography for lifestyle moments or fruit, if wanted. The site
   shows no fruit imagery of its own; the only fruit is the artwork on the pack label.
4. Verified reviews (see §5).

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
