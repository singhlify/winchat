/**
 * Accessibility audit + screenshots, across the viewports that matter.
 *
 *   node scripts/audit-ui.mjs [baseUrl]
 *
 * Both jobs live in one script because they answer the same question: what does this
 * actually look and behave like? Splitting them means one of them stops being run.
 *
 * axe-core catches the failures that are invisible by inspection: contrast on rendered
 * pixels rather than on tokens, missing accessible names, ARIA that does not match the role.
 * It is a floor, not a ceiling. Axe finds roughly a third of real issues, so a clean run
 * means "no automated failures", never "accessible".
 *
 * The screenshots are there because reading the source is not the same as seeing the page.
 * That gap is how a mobile sidebar toggle stayed invisible for a whole session while the
 * markup looked correct.
 */

import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const base = process.argv[2] ?? "http://localhost:3000";
const OUT = process.env.AUDIT_OUT ?? join(tmpdir(), "winchat-ui-audit");
mkdirSync(OUT, { recursive: true });

// 390 is an iPhone 14/15; 1280 is the commonest laptop. Both themes, because a palette that
// works in one and not the other is the single most common dark-mode bug.
const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844 },
  { name: "desktop", width: 1280, height: 900 },
];
const PAGES = ["/", "/app", "/sources"];
const THEMES = ["light", "dark"];

const browser = await chromium.launch();
let totalViolations = 0;

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      colorScheme: theme,
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();

    for (const path of PAGES) {
      const label = `${path === "/" ? "landing" : path.slice(1)}-${viewport.name}-${theme}`;
      try {
        await page.goto(base + path, { waitUntil: "networkidle", timeout: 45000 });
      } catch {
        // networkidle never settles on the chat page while a stream is open; the paint is
        // what matters, so fall back rather than failing the whole run.
        await page.goto(base + path, { waitUntil: "domcontentloaded", timeout: 45000 });
      }
      await page.waitForTimeout(600);

      // Scroll the whole page before capturing. `fullPage` alone does NOT fire
      // IntersectionObserver for below-fold content, so scroll-revealed sections screenshot
      // as blank, which reads as a rendering bug that is not there. Verified: the stats
      // band captured empty while measuring opacity 1 in a real browser.
      await page.evaluate(async () => {
        const step = window.innerHeight * 0.8;
        for (let y = 0; y < document.body.scrollHeight; y += step) {
          window.scrollTo(0, y);
          await new Promise((r) => setTimeout(r, 120));
        }
        window.scrollTo(0, 0);
      });
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${OUT}/${label}.png`, fullPage: path === "/" });

      // Only audit each page once per theme. A11y results do not differ by width here,
      // and running it four times just makes the output harder to read.
      if (viewport.name === "desktop") {
        const { violations } = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
          .analyze();

        if (violations.length) {
          console.log(`\n  ${path}  (${theme})`);
          for (const v of violations) {
            totalViolations++;
            console.log(`    ${v.impact?.toUpperCase() ?? "?"}  ${v.id}, ${v.help}`);
            for (const node of v.nodes.slice(0, 2)) {
              console.log(`        ${node.target.join(" ")}`);
            }
          }
        }
      }
    }
    await context.close();
  }
}

await browser.close();
console.log(
  totalViolations === 0
    ? "\n  axe: no automated violations (a floor, not proof of accessibility)\n"
    : `\n  axe: ${totalViolations} violation(s) above\n`,
);
console.log(`  screenshots: ${OUT}\n`);
