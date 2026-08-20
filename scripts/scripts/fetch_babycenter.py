from __future__ import annotations

import csv
import html
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
BASE_URL = "https://www.babycenter.com.au/baby-names/most-popular/top-baby-names-{year}"
USER_AGENT = "Mozilla/5.0"

FIELDS = [
    "year",
    "state_or_territory",
    "sex",
    "name",
    "count",
    "rank",
    "source_url",
    "source_name",
    "notes",
]


def proper_case(value: str) -> str:
    text = html.unescape(re.sub(r"<.*?>", "", value)).strip()
    return " ".join(part[:1].upper() + part[1:].lower() for part in text.split())


def fetch_html(year: int) -> str:
    url = BASE_URL.format(year=year)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def parse_rows(page_html: str, year: int) -> list[dict[str, str]]:
    table_match = re.search(r'<div class="topNamesWrapper">.*?</table>', page_html, flags=re.I | re.S)
    if not table_match:
        return parse_legacy_rows(page_html, year)

    rows: list[dict[str, str]] = []
    source_url = BASE_URL.format(year=year)
    for row_html in re.findall(r"<tr>(.*?)</tr>", table_match.group(0), flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)
        if len(cells) < 3:
            continue
        rank_text = re.sub(r"\D+", "", cells[0])
        if not rank_text:
            continue
        rank = int(rank_text)
        girl = proper_case(cells[1])
        boy = proper_case(cells[2])
        if girl:
            rows.append(make_row(year, "girl", girl, rank, source_url))
        if boy:
            rows.append(make_row(year, "boy", boy, rank, source_url))
    return rows


def parse_legacy_rows(page_html: str, year: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    source_url = BASE_URL.format(year=year)
    for sex, label in [("girl", "girls"), ("boy", "boys")]:
        pattern = rf'<h2[^>]*>\s*Top\s+\d+\s+names\s+for\s+{label}\s*</h2>\s*<ol>(.*?)</ol>'
        match = re.search(pattern, page_html, flags=re.I | re.S)
        names = []
        if match:
            names = [proper_case(item) for item in re.findall(r"<li[^>]*>(.*?)</li>", match.group(1), flags=re.I | re.S)]
        embedded_names = parse_embedded_names(page_html, sex)
        if len(embedded_names) > len(names):
            names = embedded_names
        for rank, name in enumerate([name for name in names if name], start=1):
            row = make_row(year, sex, name, rank, source_url)
            row["notes"] = f"Australia-wide BabyCenter ranking / rank only / legacy top {len(names)}"
            rows.append(row)
    return rows


def parse_embedded_names(page_html: str, sex: str) -> list[str]:
    key = "popularGirlNames" if sex == "girl" else "popularBoyNames"
    match = re.search(rf'"{key}":\{{"babynameSearches":\[(.*?)\]', page_html, flags=re.I | re.S)
    if not match:
        return []
    names = re.findall(r'"name":"([^"]+)"', match.group(1))
    return [proper_case(name) for name in names]


def make_row(year: int, sex: str, name: str, rank: int, source_url: str) -> dict[str, str]:
    return {
        "year": str(year),
        "state_or_territory": "Australia",
        "sex": sex,
        "name": name,
        "count": "",
        "rank": str(rank),
        "source_url": source_url,
        "source_name": f"BabyCenter Australia top baby names {year}",
        "notes": "Australia-wide BabyCenter ranking / rank only / top 100",
    }


def write_rows(year: int, rows: list[dict[str, str]]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"babycenter_australia_{year}_top_names.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    if len(sys.argv) > 1:
        years = [int(arg) for arg in sys.argv[1:]]
    else:
        years = list(range(2010, 2026))

    total = 0
    for year in years:
        try:
            rows = parse_rows(fetch_html(year), year)
        except Exception as exc:
            print(f"{year}: skipped ({exc})")
            continue
        if not rows:
            print(f"{year}: skipped (no top-name table found)")
            continue
        path = write_rows(year, rows)
        total += len(rows)
        print(f"{year}: wrote {len(rows)} rows to {path.name}")
    print(f"Done. Wrote {total} BabyCenter rows.")


if __name__ == "__main__":
    main()
