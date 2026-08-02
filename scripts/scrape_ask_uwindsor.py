"""One-shot polite scraper for ask.uwindsor.ca (Oracle RightNow knowledge base).

Enumerates every published answer from the site's own sitemap, fetches each
detail page, caches the raw HTML, and extracts clean structured data.

Design notes (defend these out loud):
- Source of truth is the sitemap (/ci/sitemap/answers/page/1), not link-crawling
  or a_id brute-force. It lists all answers + a `lastmod` timestamp each.
- `a_id` is the stable primary key; the URL slug is decoration.
- Raw HTML is cached to disk so re-parsing / re-chunking never re-hits the server.
- `lastmod` is stored so a future incremental refresh can re-fetch only changed
  answers (diff stored lastmod vs sitemap) instead of pulling all 558 again.
- Rate-limited to ~1 req/sec, honest identifying User-Agent (no bot spoofing).

Run:  uv run python scripts/scrape_ask_uwindsor.py
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError

BASE = "https://ask.uwindsor.ca"
SITEMAP_URL = f"{BASE}/ci/sitemap/answers/page/1"
USER_AGENT = (
    "winchat-learning-scraper/1.0 "
    "(personal RAG study project; contact gs130899@gmail.com)"
)
REQUEST_DELAY_S = 1.2  # be polite: ~1 request/second

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "ask_uwindsor"
RAW_DIR = OUT_DIR / "raw"
ANSWERS_DIR = OUT_DIR / "answers"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch(url: str) -> str:
    """GET a URL as text with our honest User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


class _AnswerTextExtractor(HTMLParser):
    """Capture the inner HTML of <div class="... rn_AnswerText ...">.

    Tracks tag depth so we stop at the matching closing </div>, not the first one.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.capturing = False
        self._depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class", "") or ""
        if not self.capturing and tag == "div" and "rn_AnswerText" in classes:
            self.capturing = True
            self._depth = 1
            return
        if self.capturing:
            if tag == "div":
                self._depth += 1
            self.parts.append(self.get_starttag_text() or f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if not self.capturing:
            return
        if tag == "div":
            self._depth -= 1
            if self._depth == 0:
                self.capturing = False
                return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.capturing:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.capturing:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self.capturing:
            self.parts.append(f"&#{name};")


def _html_to_text(html: str) -> str:
    """Strip tags to readable plain text (block tags -> newlines)."""
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_answer(html: str) -> tuple[str, str, str]:
    """Return (question, answer_html, answer_text) from a detail page."""
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    title = unescape(m.group(1).strip()) if m else ""
    question = re.sub(r"^ask\.UWindsor\s*-\s*", "", title).strip()

    extractor = _AnswerTextExtractor()
    extractor.feed(html)
    answer_html = "".join(extractor.parts).strip()
    answer_text = _html_to_text(answer_html)
    return question, answer_html, answer_text


def parse_sitemap(xml: str) -> list[dict[str, str]]:
    """Return [{a_id, url, lastmod}] for every answer in the sitemap."""
    entries: list[dict[str, str]] = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        if not loc:
            continue
        url = unescape(loc.group(1).strip())
        aid = re.search(r"/a_id/(\d+)", url)
        lastmod = re.search(r"<lastmod>(.*?)</lastmod>", block)
        entries.append(
            {
                "a_id": aid.group(1) if aid else "",
                "url": url,
                "lastmod": lastmod.group(1).strip() if lastmod else "",
            }
        )
    return entries


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

    print("fetching sitemap>>>", SITEMAP_URL)
    sitemap_xml = fetch(SITEMAP_URL)
    (OUT_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    entries = parse_sitemap(sitemap_xml)
    print("answers listed>>>", len(entries))

    jsonl_path = OUT_DIR / "answers.jsonl"
    records: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    with jsonl_path.open("w", encoding="utf-8") as jsonl:
        for i, entry in enumerate(entries, start=1):
            aid, url, lastmod = entry["a_id"], entry["url"], entry["lastmod"]
            canonical = f"{BASE}/app/answers/detail/a_id/{aid}"
            try:
                html = fetch(canonical)
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"  [{i}/{len(entries)}] a_id={aid} FAILED: {exc}")
                failures.append({"a_id": aid, "url": canonical, "error": str(exc)})
                time.sleep(REQUEST_DELAY_S)
                continue

            (RAW_DIR / f"{aid}.html").write_text(html, encoding="utf-8")
            question, answer_html, answer_text = parse_answer(html)
            record = {
                "a_id": aid,
                "question": question,
                "answer_text": answer_text,
                "answer_html": answer_html,
                "url": url,
                "lastmod": lastmod,
                "fetched_at": _now_iso(),
            }
            (ANSWERS_DIR / f"{aid}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)

            if i % 25 == 0 or i == len(entries):
                print(f"  [{i}/{len(entries)}] a_id={aid} :: {question[:60]}")
            time.sleep(REQUEST_DELAY_S)

    manifest = {
        "source": BASE,
        "sitemap": SITEMAP_URL,
        "scraped_at": _now_iso(),
        "listed": len(entries),
        "saved": len(records),
        "failed": len(failures),
        "failures": failures,
        "files": {
            "raw_html": str(RAW_DIR.relative_to(OUT_DIR.parent.parent)),
            "per_answer_json": str(ANSWERS_DIR.relative_to(OUT_DIR.parent.parent)),
            "combined_jsonl": str(jsonl_path.relative_to(OUT_DIR.parent.parent)),
        },
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("done>>>", f"{len(records)} saved, {len(failures)} failed")
    print("output>>>", OUT_DIR)


if __name__ == "__main__":
    main()
