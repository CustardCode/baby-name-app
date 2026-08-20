from __future__ import annotations

import csv
import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
NAMES_PATH = ROOT / "data" / "clean" / "baby_names_master.csv"
METADATA_PATH = ROOT / "data" / "clean" / "name_metadata.csv"
OUTPUT_PATH = ROOT / "data" / "research" / "name_wikipedia_sources.csv"

USER_AGENT = "AustralianBabyNameExplorer/1.0 (local research script)"
API_URL = "https://en.wikipedia.org/w/api.php"


def request_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise
            wait_seconds = 8 * (attempt + 1)
            print(f"Rate limited by Wikipedia; waiting {wait_seconds}s", flush=True)
            time.sleep(wait_seconds)
    raise RuntimeError("unreachable")


def wiki_api(params: dict[str, str]) -> dict:
    query = urlencode({"format": "json", "formatversion": "2", **params})
    return request_json(f"{API_URL}?{query}")


def read_names() -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    with NAMES_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("state_or_territory") != "Australia":
                continue
            if row.get("sex") not in {"boy", "girl"}:
                continue
            if not row.get("rank"):
                continue
            seen.add((row["name"].strip(), row["sex"].strip()))
    return sorted(seen, key=lambda item: (item[1], item[0].lower()))


def read_known_urls() -> dict[tuple[str, str], str]:
    if not METADATA_PATH.exists():
        return {}
    urls: dict[tuple[str, str], str] = {}
    with METADATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = row.get("name", "").strip()
            gender = row.get("gender", "").strip()
            url = row.get("source_url", "").strip()
            if name and gender and "wikipedia.org/wiki/" in url:
                urls[(name.lower(), gender)] = url
    return urls


def title_from_url(url: str) -> str:
    return url.rsplit("/wiki/", 1)[-1].replace("_", " ")


def title_candidates(name: str, known_url: str = "") -> list[str]:
    candidates = []
    if known_url:
        candidates.append(title_from_url(known_url))
    candidates.extend([
        f"{name} (given name)",
        f"{name} (name)",
        name,
    ])
    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def page_summary(title: str) -> dict[str, str] | None:
    data = wiki_api({
        "action": "query",
        "prop": "extracts|pageprops",
        "exintro": "1",
        "explaintext": "1",
        "redirects": "1",
        "titles": title,
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    page = pages[0]
    extract = (page.get("extract") or "").strip()
    resolved_title = page.get("title", title)
    if not extract:
        return None
    lowered = extract.lower()
    is_name_page = any(
        marker in lowered
        for marker in [
            "given name",
            "masculine name",
            "feminine name",
            "unisex name",
            "surname",
            "personal name",
        ]
    )
    if not is_name_page:
        return None
    return {
        "source_name": f"Wikipedia - {resolved_title}",
        "source_url": f"https://en.wikipedia.org/wiki/{quote(resolved_title.replace(' ', '_'))}",
        "source_title": resolved_title,
        "source_extract": extract,
    }


def find_source(name: str, sex: str, known_url: str = "") -> dict[str, str]:
    for title in title_candidates(name, known_url):
        try:
            found = page_summary(title)
        except (HTTPError, URLError, TimeoutError):
            found = None
        if found:
            return found

    return {
        "source_name": "",
        "source_url": "",
        "source_title": "",
        "source_extract": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public Wikipedia research extracts for baby-name pages.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of missing rows to fetch. Default fetches all.")
    parser.add_argument("--retry-missing", action="store_true", help="Retry rows that already exist but have no source URL.")
    args = parser.parse_args()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    known_urls = read_known_urls()
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing[(row["name"], row["gender"])] = row

    names = read_names()
    fieldnames = ["name", "gender", "source_name", "source_url", "source_title", "source_extract"]
    rows = [existing[key] for key in sorted(existing, key=lambda item: (item[1], item[0].lower()))]
    fetched = 0

    for index, (name, sex) in enumerate(names, 1):
        existing_row = existing.get((name, sex))
        if existing_row and (existing_row.get("source_url") or not args.retry_missing):
            continue
        if args.limit and fetched >= args.limit:
            break
        source = find_source(name, sex, known_urls.get((name.lower(), sex), ""))
        row = {
            "name": name,
            "gender": sex,
            "source_name": source["source_name"],
            "source_url": source["source_url"],
            "source_title": source["source_title"],
            "source_extract": source["source_extract"],
        }
        rows.append(row)
        existing[(name, sex)] = row
        rows = [item for item in rows if not (item["name"] == name and item["gender"] == sex)]
        rows.append(row)
        fetched += 1
        status = "found" if source["source_url"] else "missing"
        print(f"{index}/{len(names)} {name} ({sex}): {status}", flush=True)
        with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda item: (item["gender"], item["name"].lower())))
        time.sleep(1.0)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda item: (item["gender"], item["name"].lower())))

    found_count = sum(1 for row in rows if row["source_url"])
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Found sources for {found_count} of {len(rows)} name/gender pages")


if __name__ == "__main__":
    main()
