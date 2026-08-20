from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
MASTER_CSV = CLEAN_DIR / "baby_names_master.csv"
MASTER_JS = CLEAN_DIR / "baby_names_master.js"

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

STATE_ALIASES = {
    "new south wales": "NSW",
    "victoria": "VIC",
    "queensland": "QLD",
    "western australia": "WA",
    "south australia": "SA",
    "tasmania": "TAS",
    "australian capital territory": "ACT",
    "northern territory": "NT",
    "australia": "Australia",
}

SEX_ALIASES = {
    "boys": "boy",
    "male": "boy",
    "m": "boy",
    "boy": "boy",
    "girls": "girl",
    "female": "girl",
    "f": "girl",
    "girl": "girl",
}


def proper_case(name: str) -> str:
    parts = str(name or "").strip().split()
    return " ".join(part[:1].upper() + part[1:].lower() for part in parts if part)


def clean_int(value: str) -> str:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return ""


def clean_state(value: str) -> str:
    text = str(value or "").strip()
    return STATE_ALIASES.get(text.lower(), text.upper() if len(text) <= 3 else text)


def clean_sex(value: str) -> str:
    text = str(value or "").strip().lower()
    return SEX_ALIASES.get(text, text)


def normalise_row(raw: dict[str, str], fallback_source: str) -> dict[str, str] | None:
    lower = {str(k).strip().lower(): v for k, v in raw.items()}
    row = {
        "year": clean_int(lower.get("year", "")),
        "state_or_territory": clean_state(lower.get("state_or_territory", lower.get("state", ""))),
        "sex": clean_sex(lower.get("sex", lower.get("gender", ""))),
        "name": proper_case(lower.get("name", lower.get("given_name", ""))),
        "count": clean_int(lower.get("count", lower.get("births", ""))),
        "rank": clean_int(lower.get("rank", "")),
        "source_url": str(lower.get("source_url", "")).strip(),
        "source_name": str(lower.get("source_name", fallback_source)).strip() or fallback_source,
        "notes": str(lower.get("notes", "")).strip(),
    }

    if not row["year"] or not row["state_or_territory"] or row["sex"] not in {"boy", "girl"} or not row["name"]:
        return None
    if not row["count"] and "count unavailable" not in row["notes"].lower() and "rank only" not in row["notes"].lower():
        row["notes"] = append_note(row["notes"], "count unavailable")
    return row


def append_note(notes: str, extra: str) -> str:
    if not notes:
        return extra
    if extra.lower() in notes.lower():
        return notes
    return f"{notes}; {extra}"


def read_raw_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(RAW_DIR.glob("*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for raw in csv.DictReader(handle):
                row = normalise_row(raw, path.stem)
                if row:
                    rows.append(row)
    return rows


def calculate_missing_ranks(rows: list[dict[str, str]]) -> None:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["year"], row["state_or_territory"], row["sex"])].append(row)

    for group_rows in groups.values():
        if any(not row["rank"] for row in group_rows) and all(row["count"] for row in group_rows):
            ordered = sorted(group_rows, key=lambda item: (-int(item["count"]), item["name"]))
            previous_count = None
            previous_rank = 0
            for index, row in enumerate(ordered, start=1):
                count = int(row["count"])
                rank = previous_rank if count == previous_count else index
                row["rank"] = str(rank)
                row["notes"] = append_note(row["notes"], "rank calculated from count")
                previous_count = count
                previous_rank = rank


def add_australia_calculated_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], dict[str, dict[str, object]]] = defaultdict(dict)
    direct_australia = {
        (row["year"], row["sex"])
        for row in rows
        if row["state_or_territory"] == "Australia"
    }
    for row in rows:
        if row["state_or_territory"] == "Australia" or not row["count"]:
            continue
        key = (row["year"], row["sex"])
        entry = groups[key].setdefault(row["name"], {"count": 0, "states": set(), "sources": set()})
        entry["count"] = int(entry["count"]) + int(row["count"])
        entry["states"].add(row["state_or_territory"])
        entry["sources"].add(row["source_name"])

    calculated: list[dict[str, str]] = []
    for (year, sex), names in groups.items():
        if (year, sex) in direct_australia:
            continue
        ordered = sorted(names.items(), key=lambda item: (-int(item[1]["count"]), item[0]))
        previous_count = None
        previous_rank = 0
        for index, (name, entry) in enumerate(ordered, start=1):
            count = int(entry["count"])
            rank = previous_rank if count == previous_count else index
            states = ", ".join(sorted(entry["states"]))
            calculated.append(
                {
                    "year": year,
                    "state_or_territory": "Australia",
                    "sex": sex,
                    "name": name,
                    "count": str(count),
                    "rank": str(rank),
                    "source_url": "",
                    "source_name": "Calculated Australia total from available state/territory data",
                    "notes": f"calculated from available state/territory data; included states: {states}; incomplete if states/years are missing",
                }
            )
            previous_count = count
            previous_rank = rank

    return rows + calculated


def write_outputs(rows: list[dict[str, str]]) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted(
        rows,
        key=lambda row: (
            int(row["year"]),
            row["state_or_territory"],
            row["sex"],
            int(row["rank"] or 999999),
            row["name"],
        ),
    )
    with MASTER_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    MASTER_JS.write_text(
        "window.BABY_NAME_MASTER = "
        + json.dumps(rows, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    rows = read_raw_rows()
    calculate_missing_ranks(rows)
    rows = add_australia_calculated_rows(rows)
    write_outputs(rows)
    print(f"Wrote {len(rows)} rows to {MASTER_CSV}")


if __name__ == "__main__":
    main()
