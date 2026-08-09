/**
 * Does every colour pair in the theme actually meet contrast requirements?
 *
 *   node scripts/check-contrast.mjs
 *
 * Reads the OKLCH tokens straight out of `src/app/globals.css`, converts them to sRGB, and
 * checks the pairs that actually appear together in the UI — in BOTH themes. Colour work
 * done by eye passes on the designer's monitor and fails on someone else's; this is the
 * cheap way to know rather than hope.
 *
 * WCAG 2.1 ratios are used rather than APCA. APCA is the better perceptual model and is
 * what Radix Colors targets, but it is not yet a normative requirement, and a portfolio
 * project is judged against the standard people actually cite. AA is the bar: 4.5:1 for
 * body text, 3:1 for large text and for UI component boundaries (SC 1.4.11).
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, "../src/app/globals.css"), "utf8");

/** oklch(L C H) -> linear sRGB -> relative luminance, per WCAG 2.1. */
function oklchToRgb(l, c, h) {
  const hr = (h * Math.PI) / 180;
  const a = c * Math.cos(hr);
  const b = c * Math.sin(hr);

  const l_ = l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = l - 0.0894841775 * a - 1.291485548 * b;

  const L = l_ ** 3;
  const M = m_ ** 3;
  const S = s_ ** 3;

  return [
    +4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S,
    -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S,
    -0.0041960863 * L - 0.7034186147 * M + 1.707614701 * S,
  ];
}

function luminance([r, g, b]) {
  // Already linear-light from the OKLab transform, so no de-gamma step — just clamp,
  // because out-of-gamut values would otherwise produce a nonsense ratio.
  const clamp = (v) => Math.min(1, Math.max(0, v));
  return 0.2126 * clamp(r) + 0.7152 * clamp(g) + 0.0722 * clamp(b);
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Pull `--name: oklch(l c h);` declarations out of a `:root` / `.dark` block. */
function tokens(blockName) {
  const start = css.indexOf(blockName);
  if (start === -1) return {};
  const block = css.slice(start, css.indexOf("}", start));
  const found = {};
  for (const [, name, l, c, h] of block.matchAll(
    /--([\w-]+):\s*oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)/g,
  )) {
    found[name] = oklchToRgb(Number(l), Number(c), Number(h));
  }
  return found;
}

// Pairs that genuinely sit on top of each other in the UI. `min` is the AA requirement:
// 4.5 for body text, 3 for large text and for non-text UI boundaries.
const PAIRS = [
  ["foreground", "background", 4.5, "body text"],
  ["muted-foreground", "background", 4.5, "secondary text"],
  ["muted-foreground", "muted", 4.5, "text on muted panels"],
  ["primary-foreground", "primary", 4.5, "text on the primary button"],
  ["accent-foreground", "accent", 4.5, "text on hover/active surfaces"],
  ["destructive", "background", 4.5, "error text"],
  // SC 1.4.11 covers boundaries REQUIRED to identify a control — a form field's edge —
  // not decorative rules. Holding every divider to 3:1 produces a harsh, boxed-in page and
  // is not what the criterion asks for, so the two are checked separately and honestly.
  ["input", "background", 3, "form field boundary (SC 1.4.11)"],
  ["border", "background", 1.4, "decorative dividers (visible, not required to be 3:1)"],
  ["ring", "background", 3, "focus indicator"],
  // Gold is NOT checked as text on the page background, and that is deliberate rather
  // than an omission: a gold dark enough to reach 3:1 on white has stopped being gold and
  // become olive. In light mode it is a fill or a rule — decorative, carrying no
  // information, so no contrast minimum applies. What must pass is text sitting ON it,
  // and the darkened `gold-foreground` for anywhere gold has to be text.
  ["gold-ink", "gold", 4.5, "text on a gold fill"],
  // Display size only, so the large-text bar applies rather than the body-text one.
  ["gold-strong", "background", 3, "gold at display size (SC 1.4.3)"],
  ["band-foreground", "band", 4.5, "text on the closing CTA band"],
  ["gold-foreground", "background", 4.5, "gold used as small text"],
  ["gold-foreground", "gold-muted", 4.5, "gold text on a gold-tinted panel"],
];

let failures = 0;
for (const [themeName, selector] of [
  ["LIGHT", ":root {"],
  ["DARK", ".dark {"],
]) {
  const t = tokens(selector);
  console.log(`\n  ${themeName}`);
  for (const [fg, bg, min, label] of PAIRS) {
    if (!t[fg] || !t[bg]) {
      console.log(`    SKIP  ${label} (${fg} or ${bg} not defined as oklch)`);
      continue;
    }
    const r = ratio(t[fg], t[bg]);
    const ok = r >= min;
    if (!ok) failures++;
    console.log(
      `    ${ok ? "PASS" : "FAIL"}  ${r.toFixed(2)}:1  (needs ${min}:1)  ${label}`,
    );
  }
}

console.log(
  failures === 0
    ? "\n  All checked pairs meet WCAG AA.\n"
    : `\n  ${failures} pair(s) below AA — fix before shipping.\n`,
);
process.exit(failures === 0 ? 0 : 1);
