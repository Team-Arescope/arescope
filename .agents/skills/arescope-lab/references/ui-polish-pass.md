# UI polish pass on the LAB site (unslop)

When the user asks to clean up, unslop or redesign `arescope.mrfenek.eu.cc`, run this
pass. It is a polish, not a rebuild: the warm-carbon/copper palette, Manrope + DM
Mono, the section order and the layout are deliberate and stay.

## 1. Audit what is rendered, not what the markup contains

`static/mission.css` ends with a wall of overrides, several of which hide whole
blocks with `display:none!important` — `.sidebar`, `.metrics`, `.notice`,
`.panel-heading`, `.map-legend`, `.page-footer`, `.utc-label`. The live screen is
only: topbar, icon rail (`shell.js`), full-bleed map stage and its empty state.

- Start from a screenshot and `getComputedStyle`, not from `index.html`: polishing
  hidden blocks wastes the pass and leaves the real screen untouched.
- Inventory once with `grep -oE "[^{]*\{[^}]*display:none[^}]*\}" static/mission.css`
  and keep that list in mind for every later check.

## 2. Edit minified CSS by appending one override block

`mission.css` and `style.css` are single-line minified files. Do not rewrite rules
in place; append a block at the end of `mission.css` (it loads after `style.css`)
under a `/* ── unslop polish pass ── */` comment, grouped by the pass order:
spacing → colour → icons → copy → type → details → motion. Keep `!important` where
the base rules already use it.

## 3. Check geometry numerically before claiming a visual fix

A decorative layer can be present, styled and invisible. `.map-grid` carried the
right background-image and `opacity: .55` yet rendered nothing because its
`getBoundingClientRect()` was `1280×0` — a background on a zero-height div.

- For every layer you touch print `rect.width × rect.height`, `opacity` and the
  computed `background-image`.
- Force the box: `position:absolute!important; inset:0!important; width/height:100%`.
- Same rule for any "I made it more visible" claim: prove size, then look.

## 4. Copy rules the user accepted

- Sentence case everywhere except the wordmark `ARESCOPE LAB`; no wide tracking on
  labels (`letter-spacing: 0`), 11 px minimum.
- One statement per fact. A header line saying `live-скан доступен` next to body
  copy saying `не live` reads as a contradiction even though both are true about
  different layers — name the current state instead, e.g. `Live-скан: нет данных`.
- Empty state = state + concrete facts + one action. Facts carry crater name,
  extent, step and source (`Кратер Гейла, около 1×1 км, шаг ~8 м. Данные NASA MRO
  HiRISE, не live.`); the button is the action, not a third restatement.
- No API paths or developer footnotes in the interface (`GET /api/demo · НЕ LIVE`
  was removed).
- No unicode glyphs as icons (`+ ▶ ◈ ⌁ ◉`); inline lucide SVG at 16–20 px, stroke
  1.25–1.5, colour inherited from the text role.

## 5. Palette and type stay

Viewport `#0d0907` (never `#000`, it reads as a dead screen), copper accent
`#ee8a5b`, hairlines at 12–14 % of the text colour instead of full-strength
copper borders, Manrope for copy and DM Mono for numbers. These are the product's
character, not slop — do not swap them for a generic dark theme.

## 6. Verify and publish

- `static/` is served straight from the repo directory, so saving a file publishes
  it. Take the "before" snapshot first.
- Snapshot both states with the unslop script:
  `cd /root/.agents/tools/unslop-node && node /root/.hermes/skills/creative/unslop/scripts/snapshot.mjs <url> <out.html> <label> --dark`
  — it writes the page and `<label>.live.png`.
- The user's tab holds old `mission.css`/`shell.js`: re-check with CDP
  `Network.setCacheDisabled` before reloading, and say "hard refresh" in the reply.
- Keep `docs/qa/unslop-before.png` and `docs/qa/unslop-after.png` in the repo as the
  evidence the pass happened; gitignore the scratch `unslop/` folder.
- Motion after the pass: colour-only transitions (~140 ms ease-out), a
  `:focus-visible` ring, a 1 px press shift. No pulse, no scale on hover.

## 7. Reporting

The user reviews by screenshot and by numbers. Report per pass what changed, list
what was deliberately not changed (palette, type, layout, section order), and
admit what is still imperfect instead of calling the screen finished. The unslop
method carries a CC BY 4.0 credit to Damir Sokolovsky; keep it if the techniques
are reused outside this project.
