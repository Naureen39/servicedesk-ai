"""Phase 7 item 7.2: downloads real photos from Unsplash for the 8 search terms the plan
names, using Unsplash's own public search endpoint (the same one unsplash.com's website calls)
since no Unsplash API key is configured. Skips Unsplash+ ("premium_photo-...") results, which
require a paid license this project doesn't have. Fetches pre-sized AVIF and WebP variants
directly from Unsplash's imgix-backed CDN (?w=...&fm=avif / &fm=webp) at the plan's 3
responsive widths, plus a tiny blurred placeholder, and writes photographer credits to
docs/CREDITS.md.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = FRONTEND_DIR / "public" / "images"
CREDITS_PATH = FRONTEND_DIR.parent / "docs" / "CREDITS.md"

WIDTHS = [640, 1280, 1920]
FORMATS = ["webp", "avif"]

SEARCH_TERMS = [
    "car service technician",
    "modern car dealership showroom",
    "mechanic tablet diagnostics",
    "tire change workshop",
    "customer handing keys",
    "electric vehicle charging",
    "brake repair close up",
    "service advisor desk",
]

PER_TERM = 4
BRAND_LOGO_HINTS = re.compile(r"\b(toyota|honda|ford|bmw|mercedes|audi|tesla logo|chevrolet|nissan logo)\b", re.IGNORECASE)


def fetch_json(url: str) -> dict:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    result = subprocess.run(["curl", "-s", "-L", url], capture_output=True, timeout=30, check=True)
    return result.stdout


def slugify(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    credits: list[dict] = []
    seen_ids: set[str] = set()

    for term in SEARCH_TERMS:
        query = urllib.parse.quote(term)
        data = fetch_json(f"https://unsplash.com/napi/search/photos?query={query}&per_page=10")
        picked = 0
        for result in data.get("results", []):
            if picked >= PER_TERM:
                break
            photo_id = result["id"]
            if photo_id in seen_ids:
                continue
            base_url = result["urls"].get("raw", "")
            if "plus.unsplash.com" in base_url or "premium_photo" in base_url:
                continue
            description = (result.get("alt_description") or "") + " " + (result.get("description") or "")
            if BRAND_LOGO_HINTS.search(description):
                continue

            slug = f"{slugify(term)}-{photo_id.lower()}"
            photo_dir = IMAGES_DIR / slug
            expected_files = len(WIDTHS) * len(FORMATS) + 1  # + blur.webp
            if photo_dir.exists() and len(list(photo_dir.glob("*"))) >= expected_files:
                credits.append(
                    {"slug": slug, "search_term": term, "photographer": result["user"]["name"], "unsplash_url": result["links"]["html"]}
                )
                seen_ids.add(photo_id)
                picked += 1
                print(f"[{len(credits):2d}] {slug} (already downloaded)".encode("ascii", "replace").decode("ascii"))
                continue
            photo_dir.mkdir(parents=True, exist_ok=True)

            raw_url = base_url.split("?")[0]
            for width in WIDTHS:
                for fmt in FORMATS:
                    out_path = photo_dir / f"{width}.{fmt}"
                    url = f"{raw_url}?w={width}&q=75&fm={fmt}&fit=crop&auto=compress"
                    out_path.write_bytes(fetch_bytes(url))
                    time.sleep(0.15)

            blur_bytes = fetch_bytes(f"{raw_url}?w=24&q=40&fm=webp&blur=20")
            (photo_dir / "blur.webp").write_bytes(blur_bytes)

            credits.append(
                {
                    "slug": slug,
                    "search_term": term,
                    "photographer": result["user"]["name"],
                    "unsplash_url": result["links"]["html"],
                }
            )
            seen_ids.add(photo_id)
            picked += 1
            print(f"[{len(credits):2d}] {slug} -- {result['user']['name']}".encode("ascii", "replace").decode("ascii"))

    manifest_path = IMAGES_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(credits, indent=2), encoding="utf-8")

    lines = [
        "# Image Credits\n",
        "Photos in `frontend/public/images/` are real photographs from Unsplash (Section 7.2),",
        "downloaded via Unsplash's public search endpoint since no API key is configured for",
        "this project, converted to AVIF/WebP at 640/1280/1920px via Unsplash's own imgix CDN.\n",
    ]
    for c in credits:
        lines.append(f"- **{c['slug']}** (\"{c['search_term']}\") -- Photo by [{c['photographer']}]({c['unsplash_url']}) on Unsplash")
    CREDITS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nDownloaded {len(credits)} photos. Credits written to {CREDITS_PATH}")


if __name__ == "__main__":
    main()
