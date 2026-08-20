from __future__ import annotations

import csv
import html
import json
import re
import shutil
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "clean" / "baby_names_master.csv"
METADATA_PATH = ROOT / "data" / "clean" / "name_metadata.csv"
TEMPLATE_DIR = ROOT / "templates"
NAMES_DIR = ROOT / "names"
RANKINGS_DIR = ROOT / "rankings"
BASE_URL = "https://www.babynamesaustralia.com"
TODAY = date.today().isoformat()
PINTEREST_TAG = """    <!-- Pinterest Tag -->
    <script>
      !function(e){if(!window.pintrk){window.pintrk = function () {
      window.pintrk.queue.push(Array.prototype.slice.call(arguments))};var
      n=window.pintrk;n.queue=[],n.version="3.0";var
      t=document.createElement("script");t.async=!0,t.src=e;var
      r=document.getElementsByTagName("script")[0];
      r.parentNode.insertBefore(t,r)}}("https://s.pinimg.com/ct/core.js");
      pintrk('load', '2612814838872');
      pintrk('page');
      pintrk('track', 'pagevisit');
    </script>
    <noscript>
      <img height="1" width="1" style="display:none;" alt=""
        src="https://ct.pinterest.com/v3/?event=init&tid=2612814838872&noscript=1" />
    </noscript>
"""
ADSENSE_TAG = """    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7321233055716767"
     crossorigin="anonymous"></script>
"""
PINTEREST_VERIFY_META = '    <meta name="p:domain_verify" content="b2d585f99c9355b3fb485c66c08f2c62"/>\n'
FAVOURITES_JS = r"""(() => {
  const STORAGE_KEY = "babyNamesAustralia.favourites.v1";

  function readFavourites() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(parsed) ? parsed.filter((item) => item && item.name && item.url) : [];
    } catch (error) {
      return [];
    }
  }

  function writeFavourites(items) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      return false;
    }
    return true;
  }

  function keyFor(item) {
    return `${String(item.gender || "").toLowerCase()}:${String(item.name || "").toLowerCase()}`;
  }

  function getButtonItem(button) {
    return {
      name: button.dataset.favouriteName || "",
      gender: button.dataset.favouriteGender || "",
      url: button.dataset.favouriteUrl || window.location.pathname,
      latestRank: button.dataset.favouriteLatest || "",
      trend: button.dataset.favouriteTrend || "",
      style: button.dataset.favouriteStyle || "",
    };
  }

  function isFavourite(item) {
    const key = keyFor(item);
    return readFavourites().some((saved) => keyFor(saved) === key);
  }

  function saveFavourite(item) {
    const items = readFavourites();
    const key = keyFor(item);
    if (!items.some((saved) => keyFor(saved) === key)) {
      items.push(item);
      writeFavourites(items);
    }
  }

  function removeFavourite(item) {
    const key = keyFor(item);
    writeFavourites(readFavourites().filter((saved) => keyFor(saved) !== key));
  }

  function renderFavouriteCount() {
    const count = readFavourites().length;
    document.querySelectorAll("[data-favourite-count]").forEach((target) => {
      target.textContent = count ? ` (${count})` : "";
    });
  }

  function updateToggle(button) {
    const item = getButtonItem(button);
    const saved = isFavourite(item);
    button.classList.toggle("is-saved", saved);
    button.setAttribute("aria-pressed", saved ? "true" : "false");
    const label = button.querySelector("[data-favourite-label]");
    if (label) {
      label.textContent = saved ? "Saved" : "Add to favourites";
    }
  }

  function setupFavouriteToggles() {
    document.querySelectorAll("[data-favourite-toggle]").forEach((button) => {
      updateToggle(button);
      button.addEventListener("click", () => {
        const item = getButtonItem(button);
        if (!item.name || !item.url) return;
        if (isFavourite(item)) {
          removeFavourite(item);
        } else {
          saveFavourite(item);
        }
        updateToggle(button);
        renderFavouriteCount();
      });
    });
  }

  function renderFavouritesPage() {
    const list = document.querySelector("[data-favourites-list]");
    const empty = document.querySelector("[data-favourites-empty]");
    if (!list) return;
    const items = readFavourites();
    list.innerHTML = "";
    if (empty) {
      empty.hidden = items.length > 0;
    }
    list.hidden = items.length === 0;
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "favourite-card";
      card.innerHTML = `
        <a class="favourite-card-main" href="${item.url}">
          <span>${item.gender || "Baby name"}</span>
          <strong>${item.name}</strong>
          <em>${item.latestRank || "Ranking profile"}</em>
          <small>${item.trend || item.style || "Saved name"}</small>
          <b>View profile &rarr;</b>
        </a>
        <button type="button" class="favourite-remove">Remove</button>
      `;
      card.querySelector(".favourite-remove").addEventListener("click", () => {
        removeFavourite(item);
        renderFavouriteCount();
        renderFavouritesPage();
      });
      list.appendChild(card);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupFavouriteToggles();
    renderFavouriteCount();
    renderFavouritesPage();
  });

  window.BabyNamesFavourites = {
    getFavourites: readFavourites,
    addFavourite: saveFavourite,
    removeFavourite,
    isFavourite,
    renderFavouriteCount,
  };
})();
"""


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "name"


def profile_visual_class(name: str, sex: str) -> str:
    seed = f"{sex}:{name}".lower()
    index = (sum((position + 1) * ord(char) for position, char in enumerate(seed)) % 15) + 1
    return f"profile-visual-{index:02d}"


def ordinal(value: object) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "Not top 100"
    suffix = "th"
    if number % 100 not in {11, 12, 13}:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def sex_plural(sex: str) -> str:
    return "girls" if sex == "girl" else "boys"


def sex_label(sex: str) -> str:
    return "Girl" if sex == "girl" else "Boy"


def read_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            if raw.get("state_or_territory") != "Australia":
                continue
            if raw.get("sex") not in {"boy", "girl"}:
                continue
            if not raw.get("rank"):
                continue
            raw["rank_int"] = str(int(raw["rank"]))
            rows.append(raw)
    return canonical_rank_rows(rows)


def read_metadata() -> dict[tuple[str, str], dict[str, str]]:
    if not METADATA_PATH.exists():
        return {}

    metadata: dict[tuple[str, str], dict[str, str]] = {}
    with METADATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = row.get("name", "").strip()
            gender = row.get("gender", "").strip().lower()
            if not name or gender not in {"boy", "girl"}:
                continue
            metadata[(name.lower(), gender)] = {key: (value or "").strip() for key, value in row.items()}
    return metadata


def split_values(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def link_for_name(name: str, sex: str, prefix: str = "../../") -> str:
    return f'{prefix}names/{sex_plural(sex)}/{slugify(name)}.html'


def linked_name_list(names: list[str], sex: str, existing_names: set[str]) -> str:
    links = []
    for item in names:
        if item.lower() not in existing_names:
            continue
        links.append(f'<a class="seo-link" href="{link_for_name(item, sex)}">{esc(item)}</a>')
    return "\n".join(links)


def phrase_list(value: str, joiner: str = ", ") -> str:
    items = split_values(value)
    if not items:
        return value
    if len(items) == 1:
        return items[0]
    return joiner.join(items[:-1]) + f" or {items[-1]}"


def display_phrase(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    if text.upper() in {"N/A", "NT", "NSW", "ACT", "WA", "SA", "VIC", "QLD", "TAS"}:
        return text.upper()
    small_words = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of", "or", "the", "to", "with"}
    words = text.split()
    styled = []
    for index, word in enumerate(words):
        if word.isupper() and len(word) <= 4:
            styled.append(word)
            continue
        lowered = word.lower()
        if index and lowered in small_words:
            styled.append(lowered)
            continue
        styled.append(word[:1].upper() + word[1:])
    return " ".join(styled)


def language_phrase(value: str) -> str:
    return phrase_list(value, " / ")


def has_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def source_link(meta: dict[str, str]) -> str:
    if not meta.get("source_url"):
        return ""
    return f' <a class="source-link" href="{esc(meta["source_url"])}">Source: {esc(meta.get("source_name", "name reference"))}</a>.'


def sentence_join(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def natural_list(items: list[str]) -> str:
    clean = [item.strip() for item in items if item and item.strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f" and {clean[-1]}"


def meaning_intro_phrase(meaning: str) -> str:
    lowered = meaning.lower()
    phrase = phrase_list(meaning)
    if has_any(lowered, ["tree", "flower", "plant", "gemstone", "lion"]):
        if not phrase.lower().startswith(("the ", "a ", "an ")):
            phrase = f"the {phrase}"
        return f"linked to {phrase}"
    if has_any(lowered, ["life", "wisdom"]):
        return f"linked to {phrase}"
    if has_any(lowered, ["favour", "favor", "blessing", "grace", "joy", "noble", "strength", "gift"]):
        return f"linked to ideas of {phrase}"
    return f"linked with {phrase}"


def plain_style_tags(style_tags: list[str]) -> list[str]:
    return [tag for tag in style_tags if tag not in {"steady", "rising", "less common", "familiar"}]


def is_rising_trend(trend_label: str) -> bool:
    return trend_label in {"recent rise", "long-term rise"}


def is_falling_trend(trend_label: str) -> bool:
    return trend_label in {"recent fall", "long-term fall"}


def origin_is_multi_source(origin: str, language: str) -> bool:
    text = f"{origin} {language}".lower()
    return "multiple" in text or "several" in text or "across languages" in text


def metadata_for_name(
    name: str,
    sex: str,
    metadata: dict[tuple[str, str], dict[str, str]],
) -> dict[str, str]:
    exact = metadata.get((name.lower(), sex))
    if exact:
        return exact

    return {}


def source_priority(row: dict[str, str]) -> int:
    source = row.get("source_name", "").lower()
    notes = row.get("notes", "").lower()
    if "mccrindle" in source or "national report" in source or "national report" in notes:
        return 3
    if "calculated australia total" in source:
        return 2
    if "babycenter" in source:
        return 1
    return 0


def rows_for_year_sex(rows: list[dict[str, str]], year: str, sex: str) -> list[dict[str, str]]:
    matches = [row for row in rows if row["year"] == year and row["sex"] == sex]
    if not matches:
        return []
    best_priority = max(source_priority(row) for row in matches)
    if best_priority > 1:
        primary = sorted(
            [row for row in matches if source_priority(row) == best_priority],
            key=lambda item: (int(item["rank_int"]), item["name"]),
        )
        used_names = {row["name"].strip().lower() for row in primary}
        fallback = sorted(
            [
                row for row in matches
                if source_priority(row) < best_priority and row["name"].strip().lower() not in used_names
            ],
            key=lambda item: (int(item["rank_int"]), -source_priority(item), item["name"]),
        )
        selected = []
        for display_rank, row in enumerate(primary + fallback, start=1):
            display_row = dict(row)
            display_row["rank"] = str(display_rank)
            display_row["rank_int"] = str(display_rank)
            selected.append(display_row)
    else:
        selected = matches

    by_name: dict[str, dict[str, str]] = {}
    for row in selected:
        key = row["name"].strip().lower()
        existing = by_name.get(key)
        if not existing:
            by_name[key] = row
            continue
        current_key = (source_priority(row), -int(row["rank_int"]))
        existing_key = (source_priority(existing), -int(existing["rank_int"]))
        if current_key > existing_key:
            by_name[key] = row

    return sorted(by_name.values(), key=lambda item: (int(item["rank_int"]), item["name"]))


def canonical_rank_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    canonical: list[dict[str, str]] = []
    for year in sorted({row["year"] for row in rows}):
        for sex in ["girl", "boy"]:
            canonical.extend(rows_for_year_sex(rows, year, sex))
    return canonical


def movement_summary(ranked: list[dict[str, str]], total_years: int) -> tuple[str, str]:
    if len(ranked) < 3:
        return (
            "limited data",
            f"It appears in the top 100 for {len(ranked)} of {total_years} years in our available Australian data, so its trend is too limited to read strongly.",
        )

    first = ranked[0]
    latest = ranked[-1]
    previous = ranked[-2]
    first_rank = int(first["rank_int"])
    latest_rank = int(latest["rank_int"])
    previous_rank = int(previous["rank_int"])
    recent_change = previous_rank - latest_rank
    long_change = first_rank - latest_rank
    missing_count = total_years - len(ranked)
    ranks = [int(row["rank_int"]) for row in ranked]
    rank_spread = max(ranks) - min(ranks)
    best = min(ranked, key=lambda item: int(item["rank_int"]))

    if missing_count > total_years / 2:
        return (
            "limited data",
            f"It appears in the top 100 for {len(ranked)} of {total_years} years in our available Australian data, so its ranking history is more limited.",
        )

    pair_changes = [int(prev["rank_int"]) - int(curr["rank_int"]) for prev, curr in zip(ranked, ranked[1:])]
    biggest_rise = max([change for change in pair_changes if change > 0] or [0])
    biggest_fall = max([abs(change) for change in pair_changes if change < 0] or [0])

    if len(ranked) >= 4 and biggest_rise >= 18 and biggest_fall >= 18 and abs(long_change) < 25:
        return (
            "volatile",
            f"It has moved both up and down across the available years, including a rise of {biggest_rise} places and a fall of {biggest_fall} places.",
        )
    if recent_change >= 8:
        return (
            "recent rise",
            f"It rose recently, moving from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.",
        )
    if recent_change <= -8:
        if long_change >= 15:
            return (
                "long-term rise",
                f"It has a long-term rise from {ordinal(first['rank_int'])} in {first['year']} to {ordinal(latest['rank_int'])} in {latest['year']}, despite falling {abs(recent_change)} places in the latest year-to-year comparison.",
            )
        return (
            "recent fall",
            f"It fell recently, moving from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.",
        )
    if long_change >= 15:
        return (
            "long-term rise",
            f"It has become more popular over the longer term, moving from {ordinal(first['rank_int'])} in {first['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.",
        )
    if long_change <= -15:
        return (
            "long-term fall",
            f"It was more popular earlier in our Australian data, with its best recorded rank at {ordinal(best['rank_int'])} in {best['year']}.",
        )
    if rank_spread <= 15 and missing_count <= 1:
        return (
            "steady",
            "It has been a steady choice in Australia, staying in a fairly tight ranking band across the available years.",
        )
    return (
        "volatile",
        f"It has moved around in popularity, going from {ordinal(first['rank_int'])} in {first['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.",
    )


def current_rank_text(
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    *,
    compact: bool = False,
) -> str:
    current_year = max(years) if years else ""
    if latest:
        return f"{ordinal(latest['rank_int'])} in {latest['year']}"
    if ranked and current_year:
        recent = ranked[-1]
        if compact:
            return f"Not in {current_year} Top 100; last {ordinal(recent['rank_int'])} in {recent['year']}"
        return f"Not in the {current_year} Top 100; most recent appearance was {ordinal(recent['rank_int'])} in {recent['year']}."
    return "No top 100 ranking yet"


def latest_year_movement_text(ranked: list[dict[str, str]]) -> str:
    if len(ranked) < 2:
        return ""
    previous = ranked[-2]
    latest = ranked[-1]
    change = int(previous["rank_int"]) - int(latest["rank_int"])
    base = f"{previous['year']} {ordinal(previous['rank_int'])} to {latest['year']} {ordinal(latest['rank_int'])}"
    if change > 0:
        return f"{base}, up {change}"
    if change < 0:
        return f"{base}, down {abs(change)}"
    return f"{base}, unchanged"


def trend_display_text(trend_label: str, ranked: list[dict[str, str]]) -> str:
    movement = latest_year_movement_text(ranked)
    label = display_phrase(trend_label)
    if movement:
        return f"{label}; {movement}"
    return label


def biggest_moves(ranked: list[dict[str, str]]) -> tuple[str, str]:
    biggest_jump: tuple[int, dict[str, str], dict[str, str]] | None = None
    biggest_drop: tuple[int, dict[str, str], dict[str, str]] | None = None

    for previous, current in zip(ranked, ranked[1:]):
        change = int(previous["rank_int"]) - int(current["rank_int"])
        if change > 0 and (not biggest_jump or change > biggest_jump[0]):
            biggest_jump = (change, previous, current)
        if change < 0 and (not biggest_drop or abs(change) > biggest_drop[0]):
            biggest_drop = (abs(change), previous, current)

    jump_text = "No upward move recorded between listed years."
    drop_text = "No downward move recorded between listed years."
    if biggest_jump:
        places, previous, current = biggest_jump
        jump_text = f"up {places} places from {previous['year']} to {current['year']}"
    if biggest_drop:
        places, previous, current = biggest_drop
        drop_text = f"down {places} places from {previous['year']} to {current['year']}"
    return jump_text, drop_text


def fact_items_for_name(
    meta: dict[str, str],
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    trend_label: str,
    style_tags: list[str],
) -> str:
    if not ranked:
        facts = []
        if meta.get("meaning"):
            facts.append(f"Meaning: {phrase_list(meta['meaning'])}.")
        if meta.get("origin"):
            facts.append(f"Origin: {meta['origin']}.")
        if style_tags:
            facts.append(f"Style: {', '.join(style_tags[:4])}.")
        if not facts:
            facts.append("No top 100 ranking facts are available for this name yet.")
        return "\n".join(f"<li>{esc(item)}</li>" for item in facts)

    latest = ranked[-1]
    best = min(ranked, key=lambda item: int(item["rank_int"]))

    facts = []
    if meta.get("meaning") and "uncertain" not in meta["meaning"].lower():
        facts.append(f"Meaning: {phrase_list(meta['meaning'])}.")
    if meta.get("origin"):
        facts.append(f"Origin: {meta['origin']}.")
    facts.extend([
        f"Current Australian ranking status: {current_rank_text(ranked, years, latest)}",
        f"Best recorded rank: {ordinal(best['rank_int'])} in {best['year']}.",
    ])
    if style_tags:
        facts.append(f"Style: {', '.join(style_tags[:4])}.")
    return "\n".join(f"<li>{esc(item)}</li>" for item in facts)


def style_tags_for_name(name: str, sex: str, meta: dict[str, str], ranked: list[dict[str, str]], trend_label: str) -> list[str]:
    tags: list[str] = []
    origin = f"{meta.get('origin', '')} {meta.get('meaning', '')}".lower()
    language = meta.get("language", "").lower()
    name_key = name.lower()

    if name_key == "alice":
        tags.extend(["classic", "literary", "refined"])
    if name_key == "mia":
        tags.extend(["short", "bright", "international"])

    if "virtue" in origin:
        tags.extend(["classic", "gentle", "virtue", "timeless"])
    if any(word in origin for word in ["flower", "tree", "plant", "gemstone", "island", "olive"]):
        tags.append("nature-inspired")
        tags.append("vintage")
    if any(word in origin for word in ["surname", "occupational"]):
        tags.append("surname-style")
    if has_any(origin, ["biblical"]):
        tags.append("biblical")
    if has_any(origin, ["medieval", "old french", "germanic", "latin", "greek", "hebrew", "celtic", "welsh"]):
        tags.append("historic")
    if any(word in language for word in ["latin", "greek", "hebrew", "germanic", "french"]):
        tags.append("traditional")
    if "hebrew" in language or "biblical" in origin:
        tags.append("biblical")
    if ranked and len(ranked) >= 12:
        tags.append("familiar")
    if is_rising_trend(trend_label):
        tags.append("rising")
    if trend_label == "steady":
        tags.append("steady")
    if trend_label == "limited data":
        tags.append("less common")
    if len(name) <= 4:
        tags.append("short")

    seen: set[str] = set()
    result = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result[:4]


def name_descriptor(sex: str) -> str:
    return "name for girls" if sex == "girl" else "name for boys"


def friendly_intro(
    name: str,
    sex: str,
    meta: dict[str, str],
    ranked: list[dict[str, str]],
    years: list[str],
    trend_label: str,
) -> str:
    tags = style_tags_for_name(name, sex, meta, ranked, trend_label)
    style_phrase = ", ".join(tags[:2]) if tags else "distinctive"
    article = "an" if style_phrase[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
    intro = f"{esc(name)} is {article} {esc(style_phrase)} {name_descriptor(sex)}."

    meaning = meta.get("meaning", "")
    if meaning and "uncertain" not in meaning.lower() and not meaning.lower().startswith(("feminine form", "short form")):
        intro += f" It is usually {esc(meaning_intro_phrase(meaning))}."

    if ranked:
        if len(ranked) == len(years):
            intro += " It has remained a regular favourite in Australia, appearing in the top 100 every year we currently cover."
        elif is_rising_trend(trend_label):
            intro += " It has become more popular in Australia across the available years."
        elif trend_label == "limited data":
            intro += " It appears in fewer years of the Australian top 100, making it less common than many mainstream choices."
        else:
            intro += f" It appears in the Australian top 100 in {len(ranked)} of {len(years)} years we currently cover."
    return intro


def glance_cards_for_name(
    name: str,
    meta: dict[str, str],
    sex: str,
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    best: dict[str, str] | None,
    style_tags: list[str],
    trend_label: str,
) -> str:
    ranked_cards: list[tuple[int, str, str]] = []

    def add_card(priority: int, label: str, value: str | None) -> None:
        if value:
            ranked_cards.append((priority, label, value))

    inherited_from = meta.get("inherited_from", "")
    meaning = meta.get("meaning", "")
    if inherited_from:
        add_card(10, "Name family", inherited_from)
    elif meaning and "uncertain" not in meaning.lower():
        add_card(10, "Meaning", display_phrase(phrase_list(meaning)))

    origin = meta.get("origin") or meta.get("language")
    if origin:
        add_card(20, "Origin", display_phrase(origin))

    add_card(30, "Best rank", f"{ordinal(best['rank_int'])} in {best['year']}" if best else "Not available")
    add_card(40, "Listed years", f"{len(ranked)}/{len(years)} years" if years else "N/A")
    add_card(50, "Trend", trend_display_text(trend_label, ranked))
    add_card(60, "First listed", ranked[0]["year"] if ranked else "N/A")
    if style_tags:
        add_card(70, "Style", display_phrase(", ".join(style_tags)))
    add_card(80, "Length", f"{len(name)} letters")
    add_card(90, "Current rank", current_rank_text(ranked, years, latest, compact=True) if ranked else "N/A")
    add_card(100, "Gender", sex_label(sex))

    cards = [(label, value) for _, label, value in sorted(ranked_cards, key=lambda item: item[0])[:6]]
    return "\n".join(
        f'<div class="glance-card"><span>{esc(label)}</span><b>{esc(value)}</b></div>'
        for label, value in cards
    )


def meaning_content_for_name(name: str, meta: dict[str, str]) -> str:
    meaning = meta.get("meaning", "")
    if not meaning or "uncertain" in meaning.lower():
        return ""

    inherited_from = meta.get("inherited_from", "")
    relationship = meta.get("relationship", "")
    origin_text = f"{meta.get('origin', '')} {meta.get('notes', '')}".lower()

    if inherited_from and relationship:
        return f"<p>{esc(name)} can be used as a {esc(relationship)} for {esc(inherited_from)}. {esc(inherited_from)} is usually linked with {esc(display_phrase(phrase_list(meaning)))}.</p>"
    if meaning.lower().startswith(("feminine form", "short form")):
        return f"<p>{esc(name)} is usually described as a {esc(meaning)}. That makes it feel connected to a wider name family while still working as its own simple choice.</p>"

    paragraphs = [
        f"<p>{esc(name)} is most commonly {esc(meaning_intro_phrase(meaning))}. That meaning gives the name a clear little story without making it feel overworked.</p>"
    ]
    if "hazel tree" in meaning.lower():
        paragraphs.append(
            "<p>The word can also describe the warm brown-green colour associated with hazel eyes, which gives the name a natural and earthy feel.</p>"
        )
    elif "grace" in meaning.lower() and "gratia" in origin_text:
        paragraphs.append(
            "<p>Its Latin connection gives the name a wider meaning family around favour, thanks, kindness and divine grace.</p>"
        )
    elif "noble" in meaning.lower() and "adalheidis" in origin_text:
        paragraphs.append(
            f"<p>That meaning comes through older European roots, so {esc(name)} feels established and refined rather than newly invented.</p>"
        )
    elif has_any(origin_text, ["flower", "tree", "plant", "gemstone", "olive", "island"]):
        paragraphs.append(
            f"<p>Because the meaning is tied to a real-world image, {esc(name)} tends to feel more visual and concrete than names with abstract meanings.</p>"
        )
    elif has_any(origin_text, ["biblical", "hebrew"]):
        paragraphs.append(
            f"<p>For many families, that meaning sits alongside the name's Hebrew or Biblical background.</p>"
        )
    return "\n".join(paragraphs)


def origin_content_for_name(name: str, meta: dict[str, str]) -> str:
    origin = meta.get("origin", "")
    language = meta.get("language", "")
    notes = meta.get("notes", "")
    if not origin and not language:
        return ""

    inherited_from = meta.get("inherited_from", "")
    relationship = meta.get("relationship", "")
    root_name = meta.get("root_name", "")
    root = f" It is connected with the root name {esc(root_name)}." if root_name and root_name.lower() != name.lower() else ""
    inherited = f"{esc(name)} can be used as a {esc(relationship)} of {esc(inherited_from)}. " if inherited_from and relationship else ""
    language_text = f" It is associated with {esc(language_phrase(language))} roots." if language else ""
    note_text = ""
    if "latin gratia" in notes.lower():
        note_text = " It is also connected with the Latin gratia."
    if origin_is_multi_source(origin, language):
        paragraphs = [f"<p>{inherited}{esc(name)} is used across more than one naming tradition, with links to {esc(language_phrase(language) or origin)} usage.{root}{note_text}</p>"]
    else:
        paragraphs = [f"<p>{inherited}{esc(name)} is commonly traced to {esc(origin)}.{language_text}{root}{note_text}</p>"]
    origin_text = f"{origin} {language} {notes}".lower()
    if has_any(origin_text, ["nature name", "flower", "tree", "plant", "gemstone"]):
        paragraphs.append(
            f"<p>It is better understood as a word-name from English usage than as a name built from older personal-name elements.</p>"
        )
    elif "occupational surname" in origin_text:
        paragraphs.append(
            f"<p>That gives {esc(name)} a surname-style background: it began as a family name or job description before becoming a first name.</p>"
        )
    elif has_any(origin_text, ["old french", "germanic"]):
        paragraphs.append(
            f"<p>Names with this background often travelled through several languages before settling into modern English forms, which gives {esc(name)} a sense of history without making it feel dated.</p>"
        )
    elif has_any(origin_text, ["biblical", "hebrew"]):
        paragraphs.append(
            f"<p>Its roots are older than modern English usage, which is why the name can feel both familiar and traditional.</p>"
        )
    return "\n".join(paragraphs)


def titled_note_section(title: str, content: str) -> str:
    if not content.strip():
        return ""
    return f"<section><h2>{esc(title)}</h2>{content}</section>"


def more_about_section_for_name(name: str, sections: list[str]) -> str:
    content = "\n".join(section for section in sections if section.strip())
    if not content.strip():
        return ""
    return f"""
      <section class="box container">
        <header>
          <h2>More about {esc(name)}</h2>
          <p>Meaning, origin and name details</p>
        </header>
        {content}
      </section>
    """


def history_section_for_name(name: str, meta: dict[str, str], style_tags: list[str]) -> str:
    context = f"{meta.get('origin', '')} {meta.get('language', '')} {meta.get('notes', '')}".lower()
    paragraphs: list[str] = []
    if has_any(context, ["nature name", "flower", "tree", "plant", "gemstone"]):
        paragraphs.append(
            f"{esc(name)} fits the long tradition of nature names, but it also works for modern parents because short botanical and colour names have become popular again."
        )
    elif "virtue" in context:
        paragraphs.append(
            f"{esc(name)} belongs to the English virtue-name tradition, alongside names such as Faith, Hope, Mercy and Patience."
        )
    elif "occupational surname" in context:
        paragraphs.append(
            f"{esc(name)} began with a practical occupational meaning, then shifted into modern first-name use as surname-style names became more popular."
        )
    elif has_any(context, ["old french", "medieval", "germanic"]):
        paragraphs.append(
            f"{esc(name)} has a long European naming history, with older forms moving through medieval languages before becoming familiar in English."
        )
    elif has_any(context, ["biblical", "hebrew", "greek", "latin"]):
        paragraphs.append(
            f"{esc(name)} has older roots than many modern baby names, which helps explain why it can feel established rather than trend-made."
        )

    if not paragraphs:
        return ""
    return f"<section><h2>How old is the name {esc(name)}?</h2>{''.join(f'<p>{item}</p>' for item in paragraphs)}</section>"


def religious_section_for_name(name: str, meta: dict[str, str]) -> str:
    context = f"{meta.get('origin', '')} {meta.get('meaning', '')} {meta.get('notes', '')}".lower()
    text = ""
    if "biblical" in context:
        text = f"{esc(name)} has a Biblical background, so it may appeal to families who like names with Jewish or Christian tradition."
    elif "virtue" in context and name.lower() == "grace":
        text = "Grace has strong Christian associations because grace is an important concept in Christian theology. It is also used more broadly to mean elegance, kindness or goodwill."
    elif has_any(context, ["nature name", "flower name", "gemstone name"]):
        text = f"{esc(name)} is not usually considered a Biblical, Catholic or traditional saint name. It is better understood as a nature or word name."
    elif name.lower() == "jasper":
        text = "Jasper has a Christian tradition link through the traditional names of the Magi, although the Bible itself does not give the Magi names."

    if not text:
        return ""
    return f"<section><h2>Is {esc(name)} a religious name?</h2><p>{text}</p></section>"


def style_section_for_name(name: str, sex: str, style_tags: list[str], similar_names: list[str]) -> str:
    if not style_tags:
        return ""

    style_text = natural_list(style_tags[:4])
    sentence = f"{esc(name)} feels {esc(style_text)}."
    if "nature-inspired" in style_tags:
        sentence = f"{esc(name)} fits with nature-inspired names and gentle vintage choices."
    elif "virtue" in style_tags:
        sentence = f"{esc(name)} is a classic virtue name: simple, gentle and timeless."
    elif "surname-style" in style_tags:
        sentence = f"{esc(name)} is a surname-style name with a modern, energetic feel."
    elif "historic" in style_tags:
        sentence = f"{esc(name)} has a historic, established feel without sounding overly formal."

    if similar_names:
        examples = natural_list([esc(item) for item in similar_names[:4]])
        sentence += f" It sits naturally beside names like {examples}: names that feel related in sound, style or popularity."
    return f"<section><h2>What style of name is {esc(name)}?</h2><p>{sentence}</p></section>"


def profile_story_for_name(
    name: str,
    sex: str,
    meta: dict[str, str],
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    best: dict[str, str] | None,
    trend_label: str,
    style_tags: list[str],
    similar_names: list[str],
) -> str:
    context = f"{meta.get('origin', '')} {meta.get('meaning', '')} {meta.get('language', '')} {meta.get('notes', '')}".lower()
    style_words = plain_style_tags(style_tags)
    style_phrase = natural_list(style_words[:2]) if style_words else "distinctive"
    audience = "girls" if sex == "girl" else "boys"
    meaning = meta.get("meaning", "")

    first_parts = [f"{esc(name)} is a {esc(style_phrase.lower())} name for {audience}."]
    if name.lower() == "leo" and "lion" in meaning.lower() and "latin" in context:
        first_parts.append("It comes directly from the Latin word leo, meaning lion.")
        first_parts.append("That gives the name a strong, simple image without making it feel heavy or old-fashioned.")
    elif meaning and "uncertain" not in meaning.lower() and not meaning.lower().startswith(("feminine form", "short form")):
        first_parts.append(f"It is usually {esc(meaning_intro_phrase(meaning))}, giving it a clear meaning without making the name feel too serious.")
    elif meaning.lower().startswith(("feminine form", "short form")):
        first_parts.append(f"It is usually described as a {esc(meaning)}, so it has links to a broader name family while still feeling complete on its own.")

    if "hazel tree" in meaning.lower():
        first_parts.append("The word can also describe the warm brown-green colour associated with hazel eyes, giving the name a natural and earthy feel.")
    elif "gratia" in context and "grace" in meaning.lower():
        first_parts.append("Its Latin connection gives it a wider meaning family around favour, thanks, kindness and divine grace.")
    elif "adalheidis" in context:
        first_parts.append("It is usually traced back through Adelaide to the older Germanic name Adalheidis.")

    if has_any(context, ["nature name", "flower", "tree", "plant", "gemstone", "olive"]):
        first_parts.append(f"{esc(name)} is best understood as an English nature name rather than a name built from ancient personal-name elements.")
    elif "virtue" in context:
        first_parts.append(f"It belongs to the English virtue-name tradition, alongside names such as Faith, Hope, Mercy and Patience.")
    elif "occupational surname" in context:
        first_parts.append(f"It began as an occupational surname before becoming popular as a modern first name.")
    elif has_any(context, ["old french", "germanic"]):
        first_parts.append("The name moved through older European forms before becoming familiar in English.")
    elif "latin" in context:
        first_parts.append(f"It has Latin roots and has been used as a given name in European naming traditions.")
    elif root_name := meta.get("root_name", ""):
        if "hebrew" in context and root_name.lower() != name.lower():
            first_parts.append(f"It is connected to the Hebrew name {esc(root_name)}.")
        elif root_name.lower() != name.lower():
            first_parts.append(f"It is connected to the older root name {esc(root_name)}.")
    elif origin_is_multi_source(meta.get("origin", ""), meta.get("language", "")):
        first_parts.append("It is used across more than one naming tradition, which gives it a flexible international feel.")
    elif meta.get("origin"):
        first_parts.append(f"It comes from {esc(meta['origin'])}.")

    second_parts: list[str] = []
    if has_any(context, ["nature name", "flower", "tree", "plant", "gemstone", "olive"]):
        second_parts.append(f"As a baby name, {esc(name)} feels natural, gentle and a little vintage.")
    elif "virtue" in context:
        second_parts.append(f"As a baby name, {esc(name)} feels simple, classic and timeless.")
    elif "occupational surname" in context:
        second_parts.append(f"As a baby name, {esc(name)} has a surname-style feel: modern, energetic and easy to say.")
    elif origin_is_multi_source(meta.get("origin", ""), meta.get("language", "")):
        second_parts.append(f"As a baby name, {esc(name)} feels compact, easy to say and at home in more than one language.")
    elif has_any(context, ["old french", "germanic", "medieval", "latin", "greek", "celtic", "welsh"]):
        second_parts.append(f"As a baby name, {esc(name)} feels established and familiar without sounding too formal.")
    else:
        second_parts.append(f"For parents, {esc(name)} is easy to imagine in everyday life: simple enough for a child, but still polished enough to grow with them.")

    if name.lower() == "alice":
        second_parts.append("It also has a storybook feeling thanks to Alice's Adventures in Wonderland, which gives the name a gentle literary charm.")

    if "biblical" in context:
        second_parts.append("It also has a Biblical background, which may appeal to families who like names with Jewish or Christian tradition.")
    elif name.lower() == "grace":
        second_parts.append("It has strong Christian associations because grace is an important idea in Christian theology, but it is also used more broadly to suggest elegance, kindness and goodwill.")
    elif name.lower() == "jasper":
        second_parts.append("It also has a Christian tradition link through the traditional names of the Magi, although the Bible itself does not give the Magi names.")
    elif has_any(context, ["nature name", "flower", "gemstone"]):
        second_parts.append(f"It is not usually treated as a Biblical, Catholic or traditional saint name.")

    nicknames = split_values(meta.get("nicknames", ""))
    variants = split_values(meta.get("variants", ""))
    if variants:
        variant_text = ", ".join(esc(item) for item in variants[:3])
        if len(name) <= 4:
            second_parts.append(f"It can stand on its own or sit beside longer related forms such as {variant_text}.")
        else:
            second_parts.append(f"Related forms include {variant_text}.")
    if nicknames:
        if len(name) <= 4:
            second_parts.append(f"Because {esc(name)} is already short, it does not really need a nickname, though {esc(nicknames[0])} can work casually.")
        elif len(nicknames) == 1:
            second_parts.append(f"It is often shortened to {esc(nicknames[0])}.")
        else:
            second_parts.append(f"Nickname options include {', '.join(esc(item) for item in nicknames[:3])}.")

    paragraphs = [sentence_join(first_parts)]
    if second_parts:
        paragraphs.append(sentence_join(second_parts))
    return "\n".join(f"<p>{paragraph}</p>" for paragraph in paragraphs if paragraph)


def short_for_section_for_name(name: str, meta: dict[str, str]) -> str:
    inherited_from = meta.get("inherited_from", "")
    relationship = meta.get("relationship", "")
    root_name = meta.get("root_name", "")
    meaning = meta.get("meaning", "").lower()
    if inherited_from and relationship == "nickname":
        return f"<section><h2>Is {esc(name)} short for anything?</h2><p>{esc(name)} can be used as a short form of {esc(inherited_from)}, but it can also work as a simple name in its own right.</p></section>"
    if meaning.startswith("short form") and root_name and root_name.lower() != name.lower():
        return f"<section><h2>Is {esc(name)} short for anything?</h2><p>{esc(name)} is usually described as a short form connected with {esc(root_name)}.</p></section>"
    return ""


def nicknames_section_for_name(name: str, meta: dict[str, str]) -> str:
    nicknames = split_values(meta.get("nicknames", ""))
    if not nicknames:
        return ""
    if len(name) <= 4:
        text = f"{esc(name)} is already short, so it does not need a nickname, but {esc(nicknames[0])} can work as a casual form."
    elif len(nicknames) == 1:
        text = f"{esc(name)} is often shortened to {esc(nicknames[0])}."
    else:
        text = f"Common nicknames for {esc(name)} include {', '.join(esc(item) for item in nicknames)}."
    return f"<section><h2>Nicknames for {esc(name)}</h2><p>{text}</p></section>"


def variants_section_for_name(name: str, sex: str, meta: dict[str, str], existing_names: set[str]) -> str:
    variants = split_values(meta.get("variants", ""))
    if not variants:
        return ""
    linked_variants = linked_name_list(variants, sex, existing_names)
    intro = f"<p>Variations of {esc(name)} include related spellings or forms from the same name family.</p>"
    if linked_variants:
        return f'<section><h2>Variations of {esc(name)}</h2>{intro}<div class="seo-links">{linked_variants}</div></section>'
    return f"<section><h2>Variations of {esc(name)}</h2><p>Related forms may include {', '.join(esc(item) for item in variants)}.</p></section>"


def australian_context_section_for_name(name: str, meta: dict[str, str]) -> str:
    if name.lower() != "matilda":
        return ""
    return (
        f"<section><h2>Is {esc(name)} an Australian name?</h2>"
        f"<p>{esc(name)} is Germanic in origin, not originally Australian. In Australia, though, it has strong cultural associations through Waltzing Matilda, which gives the name a local familiarity beyond its linguistic roots.</p></section>"
    )


def commonness_section_for_name(name: str, sex: str, ranked: list[dict[str, str]], years: list[str], latest: dict[str, str] | None) -> str:
    if not ranked:
        return ""
    current_year = max(years) if years else ""
    if not latest and current_year:
        most_recent = ranked[-1]
        text = (
            f"{esc(name)} is not in the {esc(current_year)} Australian top 100 for {sex_plural(sex)}. "
            f"Its most recent appearance in the available data was {ordinal(most_recent['rank_int'])} in {most_recent['year']}."
        )
        return f"<section class=\"commonness-note\"><h2>How common is {esc(name)}?</h2><p>{text}</p></section>"
    latest_row = latest
    rank = int(latest_row["rank_int"])
    if rank <= 10:
        text = f"{esc(name)} is very common in the current Australian top 100 data for {sex_plural(sex)}, sitting inside the top 10."
    elif rank <= 30:
        text = f"{esc(name)} is a common choice in the current Australian top 100 data for {sex_plural(sex)}, sitting comfortably inside the top 30."
    elif len(ranked) <= max(3, len(years) // 3):
        text = f"{esc(name)} appears in the Australian top 100, but only in {len(ranked)} of {len(years)} years covered here, so it is less common than names that appear every year."
    elif rank >= 70:
        text = f"{esc(name)} is in the Australian top 100, but it sits lower in the list than the most common names."
    else:
        text = f"{esc(name)} is familiar enough to appear in the Australian top 100, while still being less common than names near the very top."
    return f"<section class=\"commonness-note\"><h2>How common is {esc(name)}?</h2><p>{text}</p></section>"


def popularity_summary_for_name(
    name: str,
    sex: str,
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    best: dict[str, str] | None,
    trend_label: str,
) -> str:
    if not ranked:
        return f"{esc(name)} does not appear in the current Australian top 100 data we have for {sex_plural(sex)}."
    current_year = max(years) if years else ""
    if not latest and current_year:
        most_recent = ranked[-1]
        return (
            f"{esc(name)} is not in the {esc(current_year)} Australian top 100 for {sex_plural(sex)}. "
            f"Its most recent appearance in the available data was {ordinal(most_recent['rank_int'])} in {most_recent['year']}. "
            f"It appeared in the Australian top 100 in {len(ranked)} of {len(years)} years we currently cover."
        )
    most_recent = latest
    latest_rank = int(most_recent["rank_int"])
    top_phrase = ""
    if latest_rank <= 10:
        top_phrase = f", making it one of the most popular {sex_plural(sex)} names in the current data"
    elif latest_rank <= 30:
        top_phrase = f", keeping it comfortably inside the current top 30 for {sex_plural(sex)}"
    if len(ranked) == len(years):
        return f"{esc(name)} is ranked {ordinal(most_recent['rank_int'])} in the latest Australian top 100 data for {sex_plural(sex)} ({most_recent['year']}){top_phrase}. It appeared in the top 100 every year from {years[0]} to {years[-1]}."
    if is_rising_trend(trend_label):
        return f"{esc(name)} is ranked {ordinal(most_recent['rank_int'])} in the latest Australian top 100 data for {sex_plural(sex)} ({most_recent['year']}){top_phrase}. Its trend is best described as {esc(trend_display_text(trend_label, ranked))}."
    if is_falling_trend(trend_label):
        return f"{esc(name)} is ranked {ordinal(most_recent['rank_int'])} in the latest Australian top 100 data for {sex_plural(sex)} ({most_recent['year']}). It was more common earlier in the years we cover, with a best recorded rank of {ordinal(best['rank_int'])} in {best['year']}. Latest-year movement: {esc(latest_year_movement_text(ranked))}."
    return f"{esc(name)} is ranked {ordinal(most_recent['rank_int'])} in the latest Australian top 100 data for {sex_plural(sex)} ({most_recent['year']}){top_phrase}. It appeared in the Australian top 100 in {len(ranked)} of {len(years)} years we currently cover."


def metadata_sections_for_name(name: str, sex: str, meta: dict[str, str], existing_names: set[str]) -> str:
    if not meta:
        return ""

    sections: list[str] = []
    inherited_from = meta.get("inherited_from", "")
    relationship = meta.get("relationship", "")
    source = ""
    if meta.get("source_url"):
        source = f' <a href="{esc(meta["source_url"])}">Source: {esc(meta.get("source_name", "name metadata"))}</a>.'

    glance_items = []
    if inherited_from and relationship:
        glance_items.append(f"{name} is commonly used as a {relationship} for {inherited_from}.")
    if meta.get("meaning"):
        if meta["meaning"].lower().startswith(("feminine form", "short form")):
            glance_items.append(f"Name link: {meta['meaning']}.")
        else:
            glance_items.append(f"Meaning: {meta['meaning']}.")
    if meta.get("origin"):
        glance_items.append(f"Origin: {meta['origin']}.")
    if meta.get("language"):
        glance_items.append(f"Language/root: {meta['language']}.")
    if glance_items:
        sections.append(
            "<section><h2>At a glance</h2><ul class=\"fact-list\">"
            + "\n".join(f"<li>{esc(item)}</li>" for item in glance_items)
            + "</ul></section>"
        )

    if meta.get("meaning"):
        subject = inherited_from if inherited_from else name
        prefix = f"Because {esc(name)} is used as a {esc(relationship)} for {esc(inherited_from)}, " if inherited_from and relationship else ""
        if meta["meaning"].lower().startswith(("feminine form", "short form")):
            meaning_text = f"{prefix}{esc(subject)} is a {esc(meta['meaning'])}."
        else:
            meaning_text = f"{prefix}{esc(subject)} is commonly linked with the meaning {esc(meta['meaning'])}."
        sections.append(
            f"<section><h2>Meaning of {esc(name)}</h2><p>{meaning_text}{source}</p></section>"
        )

    origin_bits = [meta.get("origin"), meta.get("language")]
    origin_text = ". ".join(esc(bit) for bit in origin_bits if bit)
    if origin_text:
        root = f" It is connected with the root name {esc(meta['root_name'])}." if meta.get("root_name") else ""
        inherited = f"{esc(name)} is used as a {esc(relationship)} of {esc(inherited_from)}. " if inherited_from and relationship else ""
        sections.append(f"<section><h2>Origin of {esc(name)}</h2><p>{inherited}{origin_text}.{root}</p></section>")

    variants = linked_name_list(split_values(meta.get("variants", "")), sex, existing_names)
    if variants:
        sections.append(f'<section><h2>Variants of {esc(name)}</h2><div class="seo-links">{variants}</div></section>')

    nicknames = split_values(meta.get("nicknames", ""))
    if nicknames:
        sections.append(
            f"<section><h2>Nicknames for {esc(name)}</h2><p>{', '.join(esc(item) for item in nicknames)}.</p></section>"
        )

    return "\n".join(sections)


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (char_a != char_b),
            ))
        previous = current
    return previous[-1]


def verified_context_tokens(meta: dict[str, str]) -> set[str]:
    text = f"{meta.get('origin', '')} {meta.get('language', '')} {meta.get('notes', '')}".lower()
    useful = {
        "biblical", "hebrew", "latin", "greek", "germanic", "french", "celtic", "welsh",
        "nature", "flower", "tree", "plant", "gemstone", "surname", "occupational",
        "virtue", "medieval", "classic", "traditional", "literary",
    }
    return {token for token in useful if token in text}


def similar_names_for(
    name: str,
    sex: str,
    histories: dict[tuple[str, str], list[dict[str, str]]],
    metadata: dict[tuple[str, str], dict[str, str]],
    existing_names: set[str],
) -> list[str]:
    name_key = name.lower()
    current_meta = metadata.get((name_key, sex), {})
    current_root = current_meta.get("root_name", "").lower()
    current_related = {item.lower() for item in split_values(current_meta.get("related_names", ""))}
    current_context = f"{current_meta.get('origin', '')} {current_meta.get('meaning', '')} {current_meta.get('notes', '')}".lower()
    current_tokens = verified_context_tokens(current_meta)
    current_history = histories.get((name.lower(), sex), [])
    current_latest_rank = int(current_history[-1]["rank_int"]) if current_history else None
    current_recent = movement_delta(current_history[-2], current_history[-1]) if len(current_history) > 1 else None
    candidates: list[tuple[int, str]] = []
    preferred: list[str] = []

    style_groups = {
        "girl:nature": ["Ivy", "Willow", "Violet", "Rose", "Olive", "Lily", "Daisy", "Ruby"],
        "girl:virtue": ["Rose", "Faith", "Hope", "Lily", "Claire", "Eve", "Anna", "Lucy"],
        "girl:historic": ["Clara", "Matilda", "Eleanor", "Charlotte", "Adelaide", "Elizabeth", "Harriet", "Florence"],
        "girl:surname": ["Piper", "Harlow", "Quinn", "Sloane", "Willow", "Hazel", "Harper", "Billie"],
        "boy:historic": ["Felix", "Hugo", "Oscar", "Theodore", "Arthur", "Henry", "Miles", "Otis"],
        "boy:biblical": ["Noah", "Levi", "Elijah", "Ezra", "Jonah", "Isaac", "Jacob", "Samuel"],
        "boy:nature": ["Oliver", "Jasper", "Leo", "River", "Ash", "Rowan", "Oscar", "Arthur"],
    }

    for item in split_values(current_meta.get("related_names", "")):
        preferred.append(item)
    if has_any(current_context, ["nature name", "flower", "tree", "plant", "gemstone", "olive"]):
        preferred.extend(style_groups.get(f"{sex}:nature", []))
    if "virtue" in current_context:
        preferred.extend(style_groups.get(f"{sex}:virtue", []))
    if has_any(current_context, ["old french", "germanic", "medieval", "latin", "greek", "celtic", "welsh"]):
        preferred.extend(style_groups.get(f"{sex}:historic", []))
    if has_any(current_context, ["biblical", "hebrew"]):
        preferred.extend(style_groups.get(f"{sex}:biblical", []))
    if has_any(current_context, ["surname", "occupational"]):
        preferred.extend(style_groups.get(f"{sex}:surname", []))

    result: list[str] = []
    seen_preferred = {name_key}
    for item in preferred:
        key = item.lower()
        if key in seen_preferred or key not in existing_names:
            continue
        seen_preferred.add(key)
        result.append(item)
        if len(result) >= 8:
            return result

    for candidate in sorted(existing_names):
        if candidate == name_key:
            continue
        score = 0
        candidate_meta = metadata.get((candidate, sex), {})
        candidate_name = candidate.title()
        if candidate in current_related:
            score += 80
        if current_root and candidate_meta.get("root_name", "").lower() == current_root:
            score += 28
        if candidate[0] == name_key[0]:
            score += 7
        if candidate[:2] == name_key[:2]:
            score += 12
        if candidate[-1:] == name_key[-1:]:
            score += 5
        if candidate[-2:] == name_key[-2:]:
            score += 10
        if abs(len(candidate) - len(name_key)) <= 1:
            score += 10
        elif abs(len(candidate) - len(name_key)) <= 2:
            score += 5
        distance = edit_distance(name_key, candidate)
        if distance <= 2:
            score += 20
        elif distance <= 3:
            score += 10
        shared_tokens = current_tokens & verified_context_tokens(candidate_meta)
        score += min(18, len(shared_tokens) * 6)
        candidate_history = histories.get((candidate, sex), [])
        if current_latest_rank is not None and candidate_history:
            candidate_rank = int(candidate_history[-1]["rank_int"])
            if abs(candidate_rank - current_latest_rank) <= 15:
                score += 10
            elif abs(candidate_rank - current_latest_rank) <= 30:
                score += 5
        if current_recent is not None and len(candidate_history) > 1:
            candidate_recent = movement_delta(candidate_history[-2], candidate_history[-1])
            if current_recent and candidate_recent and (current_recent > 0) == (candidate_recent > 0):
                score += 4
        if score >= 18:
            candidates.append((score, candidate_name))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    for _, candidate in candidates:
        if candidate.lower() not in seen_preferred:
            result.append(candidate)
            seen_preferred.add(candidate.lower())
        if len(result) >= 8:
            break
    return result


def clean_generated() -> None:
    for path in [NAMES_DIR, RANKINGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def name_page_path(name: str, sex: str) -> Path:
    return NAMES_DIR / sex_plural(sex) / f"{slugify(name)}.html"


def name_page_url(name: str, sex: str) -> str:
    return f"{BASE_URL}/names/{sex_plural(sex)}/{slugify(name)}.html"


def ranking_page_path(year: str, sex: str) -> Path:
    return RANKINGS_DIR / f"top-{sex_plural(sex)}-{year}.html"


def ranking_page_url(year: str, sex: str) -> str:
    return f"{BASE_URL}/rankings/top-{sex_plural(sex)}-{year}.html"


def json_ld_script(data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


def breadcrumb_schema(items: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": url,
            }
            for index, (name, url) in enumerate(items, start=1)
        ],
    }


def name_schema_json(
    name: str,
    sex: str,
    canonical: str,
    title: str,
    description: str,
    meta: dict[str, str],
    latest: dict[str, str] | None,
    similar_names: list[str],
) -> str:
    about: dict[str, object] = {
        "@type": "DefinedTerm",
        "name": name,
        "inDefinedTermSet": "Australian Baby Names",
    }
    if meta.get("meaning") and "uncertain" not in meta["meaning"].lower():
        about["description"] = f"{name} means {phrase_list(meta['meaning'])}."
    if meta.get("origin"):
        about["termCode"] = meta["origin"]

    page: dict[str, object] = {
        "@type": "WebPage",
        "@id": canonical,
        "url": canonical,
        "name": title,
        "description": html.unescape(description),
        "isPartOf": {
            "@type": "WebSite",
            "name": "Australian Baby Name Rankings",
            "url": f"{BASE_URL}/",
        },
        "about": about,
    }
    if latest:
        page["mainEntity"] = {
            "@type": "Thing",
            "name": name,
            "description": f"{name} ranked {ordinal(latest['rank_int'])} for baby {sex_plural(sex)} in Australia in {latest['year']}.",
        }
    if similar_names:
        page["mentions"] = [{"@type": "Thing", "name": item} for item in similar_names[:6]]

    return json_ld_script({
        "@context": "https://schema.org",
        "@graph": [
            page,
            breadcrumb_schema([
                ("Home", f"{BASE_URL}/"),
                (f"{sex_plural(sex).title()} names", f"{BASE_URL}/names/{sex_plural(sex)}/"),
                (name, canonical),
            ]),
        ],
    })


def ranking_schema_json(
    year: str,
    sex: str,
    canonical: str,
    title: str,
    description: str,
    ranked_rows: list[dict[str, str]],
) -> str:
    return json_ld_script({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "@id": canonical,
                "url": canonical,
                "name": title,
                "description": html.unescape(description),
                "isPartOf": {
                    "@type": "WebSite",
                    "name": "Australian Baby Name Rankings",
                    "url": f"{BASE_URL}/",
                },
                "mainEntity": {
                    "@type": "ItemList",
                    "name": f"Top baby {sex_label(sex).lower()} names in Australia {year}",
                    "numberOfItems": len(ranked_rows[:100]),
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": int(row["rank_int"]),
                            "name": row["name"],
                            "url": name_page_url(row["name"], sex),
                        }
                        for row in ranked_rows[:100]
                    ],
                },
            },
            breadcrumb_schema([
                ("Home", f"{BASE_URL}/"),
                (f"{sex_label(sex)} names {year}", canonical),
            ]),
        ],
    })


def discovery_schema_json(
    title: str,
    canonical: str,
    description: str,
    items: list[tuple[str, str]],
) -> str:
    return json_ld_script({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "@id": canonical,
                "url": canonical,
                "name": title,
                "description": description,
                "isPartOf": {
                    "@type": "WebSite",
                    "name": "Australian Baby Name Rankings",
                    "url": f"{BASE_URL}/",
                },
                "mainEntity": {
                    "@type": "ItemList",
                    "numberOfItems": len(items),
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": index,
                            "name": name,
                            "url": url,
                        }
                        for index, (name, url) in enumerate(items[:150], start=1)
                    ],
                },
            },
            breadcrumb_schema([
                ("Home", f"{BASE_URL}/"),
                (title, canonical),
            ]),
        ],
    })


def truncate_meta(text: str, limit: int = 155) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    shortened = re.sub(r"\b(and|or|plus|with|including)$", "", shortened).rstrip(" ,.;:")
    return shortened + "."


def seo_title_for_name(name: str, sex: str, meta: dict[str, str], latest: dict[str, str] | None) -> str:
    return f"{esc(name)} Baby {esc(sex_label(sex))} Name Meaning, Origin & Popularity"


def seo_description_for_name(
    name: str,
    sex: str,
    meta: dict[str, str],
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    best: dict[str, str] | None,
    similar_names: list[str],
) -> str:
    parts: list[str] = []
    inherited_from = meta.get("inherited_from", "")
    if inherited_from:
        parts.append(f"{name} baby {sex_label(sex).lower()} name profile: link to {inherited_from}.")
    elif meta.get("meaning") and "uncertain" not in meta["meaning"].lower():
        parts.append(f"{name} baby {sex_label(sex).lower()} name meaning: {phrase_list(meta['meaning'])}.")
    elif meta.get("origin"):
        parts.append(f"{name} baby {sex_label(sex).lower()} name origin: {meta['origin']}.")
    else:
        parts.append(f"{name} baby {sex_label(sex).lower()} name profile.")

    if latest:
        parts.append(f"Ranked {ordinal(latest['rank_int'])} for baby {sex_plural(sex)} in Australia in {latest['year']}.")
    elif ranked:
        parts.append(current_rank_text(ranked, years, latest))

    extras = []
    if meta.get("nicknames"):
        extras.append("nicknames")
    if meta.get("variants"):
        extras.append("variations")
    if similar_names:
        extras.append("similar names")
    if extras:
        parts.append(f"Includes {natural_list(extras)}.")

    return esc(truncate_meta(" ".join(parts)))


def history_rows_for_name(years: list[str], by_year: dict[str, dict[str, str]]) -> str:
    rows: list[str] = []
    for year in sorted(years, reverse=True):
        if year in by_year:
            rank = ordinal(by_year[year]["rank_int"])
            rows.append(f"<tr><td>{year}</td><td>{rank}</td></tr>")
        else:
            rows.append(f'<tr class="unlisted-row"><td>{year}</td><td><span class="rank-unlisted">Not in top 100</span></td></tr>')
    return "\n".join(rows)


def related_links_for_name(name: str, sex: str, ranked: list[dict[str, str]], latest_year: str) -> list[str]:
    links = [
        f'<a class="seo-link" href="./">All {sex_plural(sex)} names</a>',
        f'<a class="seo-link" href="../../popular-baby-{sex_label(sex).lower()}-names-australia.html">Popular {sex_label(sex).lower()} names</a>',
        f'<a class="seo-link" href="../../baby-name-popularity-checker-australia.html">Baby Name Popularity Checker</a>',
        f'<a class="seo-link" href="../../rankings/top-{sex_plural(sex)}-{latest_year}.html">Top {sex_plural(sex)} {latest_year}</a>',
        f'<a class="seo-link" href="../../classic-baby-names.html">Classic baby names</a>',
        f'<a class="seo-link" href="../../unique-australian-baby-names.html">Unique Australian baby names</a>',
    ]
    ranked_years = [row["year"] for row in sorted(ranked, key=lambda item: item["year"], reverse=True)]
    for year in ranked_years[:4]:
        links.append(f'<a class="seo-link" href="../../rankings/top-{sex_plural(sex)}-{year}.html">{esc(name)} in {year}</a>')
    links.append(f'<a class="seo-link" href="../../data-sources.html">Data sources</a>')
    return list(dict.fromkeys(links))


def visible_breadcrumbs_for_name(name: str, sex: str) -> str:
    label = f"{sex_label(sex)} Names"
    return (
        '<nav class="breadcrumbs" aria-label="Breadcrumb">'
        '<a href="../../">Home</a>'
        '<span aria-hidden="true">&rsaquo;</span>'
        f'<a href="./">{esc(label)}</a>'
        '<span aria-hidden="true">&rsaquo;</span>'
        f'<span aria-current="page">{esc(name)}</span>'
        '</nav>'
    )


def category_discovery_links_for_name(
    name: str,
    sex: str,
    ranked: list[dict[str, str]],
    years: list[str],
    latest: dict[str, str] | None,
    style_tags: list[str],
    trend_label: str,
) -> list[tuple[str, str, str]]:
    links: list[tuple[str, str, str]] = []
    listed_count = len(ranked)
    latest_rank = int(latest["rank_int"]) if latest else None
    tag_text = " ".join(style_tags).lower()

    if latest_rank is not None and latest_rank <= 50:
        links.append(
            (
                f"../../popular-baby-{sex_label(sex).lower()}-names-australia.html",
                f"Popular {sex_label(sex).lower()} names",
                "Browse more names parents are already loving.",
            )
        )

    if (
        "classic" in tag_text
        or "traditional" in tag_text
        or "historic" in tag_text
        or listed_count >= max(6, len(years) - 2)
    ):
        links.append(
            (
                "../../classic-baby-names.html",
                "Classic baby names",
                "Explore names with a familiar, lasting feel.",
            )
        )

    if (
        "distinctive" in tag_text
        or "less common" in tag_text
        or trend_label == "limited data"
        or listed_count <= 3
        or (latest_rank is not None and latest_rank >= 70)
    ):
        links.append(
            (
                "../../unique-australian-baby-names.html",
                "Unique Australian baby names",
                "Find names that feel a little less expected.",
            )
        )

    deduped: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for href, title, text in links:
        if href in seen:
            continue
        seen.add(href)
        deduped.append((href, title, text))
    return deduped[:3]


def keep_exploring_section_for_name(
    name: str,
    sex: str,
    similar_names: list[str],
    existing_names: set[str],
    category_links: list[tuple[str, str, str]],
    latest_year: str,
) -> str:
    similar = []
    seen = {name.lower()}
    for item in similar_names:
        key = item.lower()
        if key in seen or key not in existing_names:
            continue
        seen.add(key)
        similar.append(
            f'<a class="explore-link" data-track="similar-name" href="{slugify(item)}.html">{esc(item)}</a>'
        )
        if len(similar) >= 6:
            break

    panels: list[str] = []
    if similar:
        if len(similar) >= 4:
            panels.append(
            '<section class="explore-panel explore-panel-wide">'
            f'<h3>Names similar to {esc(name)}</h3>'
            f'<p>If you like {esc(name)}, these names may fit the same shortlist.</p>'
            f'<div class="explore-links">{"".join(similar)}</div>'
            '</section>'
            )

    style_links = list(category_links)
    fallback_style_links = [
        (
            f"../../popular-baby-{sex_label(sex).lower()}-names-australia.html",
            f"Popular {sex_label(sex).lower()} names",
            "Browse more names parents are already loving.",
        ),
        (
            "../../baby-names-with-beautiful-meanings.html",
            "Names with beautiful meanings",
            "Explore names with meaning notes and ranking context.",
        ),
        (
            "../../classic-baby-names.html",
            "Classic baby names",
            "Find established names with long-running appeal.",
        ),
        (
            f"../../rising-baby-{sex_label(sex).lower()}-names.html",
            f"Rising {sex_label(sex).lower()} names",
            "See names moving upward in the rankings.",
        ),
        (
            "../../unique-australian-baby-names.html",
            "Unique Australian names",
            "Find names outside the most obvious shortlist.",
        ),
    ]
    existing_hrefs = {href for href, _, _ in style_links}
    for href, title, text in fallback_style_links:
        if len(style_links) >= 4:
            break
        if href in existing_hrefs:
            continue
        style_links.append((href, title, text))
        existing_hrefs.add(href)

    if style_links:
        categories = "".join(
            f'<a class="explore-card" data-track="category-discovery" href="{href}">'
            f'<span>{esc(title)}</span><em>{esc(text)}</em></a>'
            for href, title, text in style_links
        )
        panels.append(
            '<section class="explore-panel">'
            '<h3>Browse by style</h3>'
            f'<div class="explore-card-list">{categories}</div>'
            '</section>'
        )

    actions = [
        (
            "../../#name-explorer",
            "Search another name",
            "Go back to the name explorer.",
            "search-another-name",
        ),
        (
            "../../baby-name-popularity-checker-australia.html",
            "Compare baby name popularity",
            "Check meaning, ranking and trend together.",
            "compare-popularity",
        ),
        (
            f"../../rankings/top-{sex_plural(sex)}-{latest_year}.html",
            f"Latest {sex_plural(sex)} rankings",
            f"Scan the current top {sex_plural(sex)} list.",
            "latest-rankings",
        ),
    ]
    action_cards = "".join(
        f'<a class="explore-card" data-track="{track}" href="{href}">'
        f'<span>{esc(title)}</span><em>{esc(text)}</em></a>'
        for href, title, text, track in actions
    )
    panels.append(
        '<section class="explore-panel">'
        '<h3>Keep exploring</h3>'
        f'<div class="explore-card-list">{action_cards}</div>'
        '</section>'
    )

    return (
        '<section class="box container keep-exploring">'
        '<header><h2>Keep Exploring</h2><p>More ways to build your baby name shortlist.</p></header>'
        f'<div class="explore-grid">{"".join(panels)}</div>'
        '</section>'
    )


def signed_movement(delta: int) -> str:
    if delta > 0:
        return f"up {delta}"
    if delta < 0:
        return f"down {abs(delta)}"
    return "steady"


def signed_movement_label(delta: int) -> str:
    if delta > 0:
        return f"+{delta}"
    if delta < 0:
        return f"-{abs(delta)}"
    return "0"


def place_word(count: int) -> str:
    return "place" if abs(int(count)) == 1 else "places"


def signed_movement_phrase(delta: int) -> str:
    if delta > 0:
        return f"up {delta} {place_word(delta)}"
    if delta < 0:
        return f"down {abs(delta)} {place_word(delta)}"
    return "steady"


def rank_hash(value: object) -> str:
    try:
        return f"#{int(value)}"
    except (TypeError, ValueError):
        return "N/A"


def article_phrase(value: str) -> str:
    phrase = value.strip()
    if not phrase:
        return phrase
    lowered = phrase.lower()
    if lowered.startswith(("a ", "an ", "the ")):
        return phrase
    article = "an" if lowered[:1] in {"a", "e", "i", "o", "u"} else "a"
    return f"{article} {phrase}"


def meaning_reference(value: str) -> str:
    phrase = phrase_list(value).strip()
    if not phrase:
        return phrase
    lowered = phrase.lower()
    if lowered.startswith(("a ", "an ", "the ")):
        return phrase
    if any(term in lowered for term in ["tree", "flower", "plant", "river", "rose", "lily", "violet", "olive"]):
        return f"the {phrase}"
    return phrase


def hazel_botanical_svg() -> str:
    return """<svg class="pilot-botanical-art" viewBox="0 0 520 320" aria-hidden="true" focusable="false">
          <g fill="none" stroke-linecap="round" stroke-linejoin="round">
            <path class="branch" d="M96 250 C180 188 230 132 318 82 C358 60 406 46 468 34" />
            <path class="branch light" d="M255 118 C272 72 304 43 349 20" />
            <path class="branch light" d="M310 88 C333 130 368 161 430 177" />
            <path class="branch light" d="M174 190 C149 153 121 130 78 119" />
          </g>
          <g class="leaf">
            <path d="M315 86 C280 55 283 17 343 5 C394 16 396 63 353 94 C337 101 326 99 315 86Z" />
            <path d="M363 64 C394 31 443 34 470 82 C457 131 407 139 371 103 C357 89 355 78 363 64Z" />
            <path d="M411 172 C370 159 352 116 385 78 C438 67 472 101 462 151 C448 176 431 181 411 172Z" />
            <path d="M101 122 C143 105 184 126 196 174 C170 217 122 213 91 176 C78 151 82 134 101 122Z" />
            <path d="M202 162 C246 148 284 177 288 226 C256 265 210 252 188 211 C178 188 183 172 202 162Z" />
          </g>
          <g class="leaf-lines" fill="none" stroke-linecap="round">
            <path d="M319 84 L352 18" /><path d="M365 66 L455 82" /><path d="M412 167 L392 86" />
            <path d="M107 126 L189 174" /><path d="M207 164 L279 226" />
            <path d="M336 42 L367 39 M329 58 L376 62 M391 82 L448 106 M397 104 L448 137 M130 139 L176 140 M122 157 L183 167 M218 181 L270 188 M211 200 L269 218" />
          </g>
          <g class="catkins">
            <path d="M286 95 C274 127 272 157 280 187" />
            <ellipse cx="279" cy="115" rx="10" ry="18" /><ellipse cx="277" cy="144" rx="9" ry="17" /><ellipse cx="282" cy="171" rx="8" ry="15" />
            <path d="M248 124 C238 153 237 181 246 207" />
            <ellipse cx="243" cy="143" rx="8" ry="15" /><ellipse cx="241" cy="168" rx="8" ry="15" /><ellipse cx="247" cy="192" rx="7" ry="13" />
          </g>
        </svg>"""


def pilot_small_icon(kind: str) -> str:
    icons = {
        "nature": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 24C16 24 24 16 24 6C14 6 6 14 6 24Z"/><path d="M10 22L23 9"/></svg>',
        "rank": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M8 24V14M16 24V8M24 24V18"/><path d="M5 24H27"/></svg>',
        "rise": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 22L13 15L18 20L27 9"/><path d="M20 9H27V16"/></svg>',
        "trophy": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M10 6H22V12C22 17 19 20 16 20C13 20 10 17 10 12V6Z"/><path d="M10 9H6C6 14 8 16 11 16M22 9H26C26 14 24 16 21 16M16 20V25M12 26H20"/></svg>',
        "calendar": '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="8" width="20" height="18" rx="2"/><path d="M11 5V11M21 5V11M6 14H26"/></svg>',
        "clock": '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="10"/><path d="M16 10V17L21 20"/></svg>',
        "meaning": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M8 24C18 24 24 16 24 7C14 7 8 14 8 24Z"/><path d="M11 22C14 17 18 13 23 9"/></svg>',
        "origin": '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="10"/><path d="M6 16H26M16 6C19 9 20 13 20 16C20 19 19 23 16 26M16 6C13 9 12 13 12 16C12 19 13 23 16 26"/></svg>',
        "heart": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 26S6 20 6 12C6 8 11 6 16 11C21 6 26 8 26 12C26 20 16 26 16 26Z"/></svg>',
    }
    return icons.get(kind, icons["nature"])


def name_profile_dataset(
    rows: list[dict[str, str]],
    metadata: dict[tuple[str, str], dict[str, str]],
    name: str,
    sex: str,
) -> dict[str, object] | None:
    years = sorted({row["year"] for row in rows})
    history = rows_for_name(rows, name, sex)
    if not history:
        return None

    latest_year = max(years)
    latest = history[-1]
    current = latest if latest["year"] == latest_year else None
    previous = history[-2] if len(history) > 1 else None
    first = history[0]
    best = min(history, key=lambda item: int(item["rank_int"]))
    worst = max(history, key=lambda item: int(item["rank_int"]))
    meta = metadata_for_name(name, sex, metadata)
    trend_label, trend_summary = movement_summary(history, len(years))
    style_tags = style_tags_for_name(name, sex, meta, history, trend_label)
    latest_delta = int(previous["rank_int"]) - int(latest["rank_int"]) if previous else 0
    overall_delta = int(first["rank_int"]) - int(latest["rank_int"])
    context = " ".join([
        name,
        meta.get("meaning", ""),
        meta.get("origin", ""),
        meta.get("language", ""),
        meta.get("notes", ""),
        " ".join(style_tags),
    ]).lower()

    return {
        "name": name,
        "sex": sex,
        "years": years,
        "history": history,
        "latest_year": latest_year,
        "latest": latest,
        "current": current,
        "is_current": current is not None,
        "previous": previous,
        "first": first,
        "best": best,
        "worst": worst,
        "meta": meta,
        "trend_label": trend_label,
        "trend_summary": trend_summary,
        "style_tags": style_tags,
        "latest_delta": latest_delta,
        "overall_delta": overall_delta,
        "overall_move": overall_delta,
        "recent_move": latest_delta,
        "latest_rank": int(latest["rank_int"]),
        "best_rank": int(best["rank_int"]),
        "context": context,
    }


def pilot_identity_tags(profile: dict[str, object]) -> list[str]:
    sex = str(profile["sex"])
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    style_tags = [str(item) for item in profile.get("style_tags", [])]
    tags: list[str] = []
    if "nature-inspired" in [tag.lower() for tag in style_tags]:
        tags.append("Nature")
    language = str(meta.get("language", "") or meta.get("origin", "")) if isinstance(meta, dict) else ""
    if language:
        tags.append(display_phrase(language))
    tags.append(sex_label(sex))
    for candidate in style_tags:
        if candidate.lower() in {"vintage", "classic", "short", "nickname-ready"}:
            tags.append(display_phrase(candidate))
        if len(tags) >= 3:
            break
    return list(dict.fromkeys(tags))[:3]


def pilot_identity_tag_html(profile: dict[str, object]) -> str:
    icons = {
        "nature": "nature",
        "english": "origin",
        "girl": "heart",
        "boy": "heart",
        "vintage": "meaning",
        "classic": "meaning",
        "short": "meaning",
    }
    tags = []
    for tag in pilot_identity_tags(profile):
        icon_key = icons.get(tag.lower(), "meaning")
        tags.append(
            f'<span>{pilot_small_icon(icon_key)}{esc(tag)}</span>'
        )
    return "".join(tags)


def pilot_intro_sentence(profile: dict[str, object]) -> str:
    name = str(profile["name"])
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    best = profile["best"] if isinstance(profile.get("best"), dict) else None
    style_tags = [str(item).lower() for item in profile.get("style_tags", [])]
    descriptors = []
    if "nature-inspired" in style_tags:
        descriptors.append("nature-inspired")
    if "vintage" in style_tags:
        descriptors.append("vintage")
    origin = str(meta.get("origin", "")) if isinstance(meta, dict) else ""
    if origin:
        descriptors.append(display_phrase(origin))
    clean_descriptors = []
    for descriptor in dict.fromkeys(descriptors[:2]):
        phrase = re.sub(r"\s+", " ", str(descriptor)).strip()
        phrase = phrase[:1].lower() + phrase[1:] if phrase else phrase
        clean_descriptors.append(phrase)
    descriptor_text = ", ".join(clean_descriptors)
    if descriptor_text:
        article = "An" if descriptor_text[:1].lower() in {"a", "e", "i", "o", "u"} else "A"
        suffix = "" if descriptor_text.lower().endswith(" name") else " name"
        descriptor_text = f"{article} {descriptor_text}{suffix}"
    else:
        descriptor_text = f"A baby {sex_label(str(profile['sex'])).lower()} name"
    latest_year = str(profile.get("latest_year", ""))
    is_current = bool(profile.get("is_current"))
    if latest and not is_current:
        return f"{descriptor_text} with Australian ranking history, though it is not in the {latest_year} Top 100."
    if latest and best and latest["year"] == best["year"] and latest["rank_int"] == best["rank_int"]:
        return f"{descriptor_text} that reached its highest Australian ranking in {latest['year']} at {ordinal(latest['rank_int'])}."
    if latest and first:
        return f"{descriptor_text} with Australian ranking history from {first['year']} to {latest['year']}."
    return f"{descriptor_text} with Australian ranking history and profile notes."


def pilot_stat_cards(profile: dict[str, object]) -> str:
    history = profile["history"] if isinstance(profile.get("history"), list) else []
    years = profile["years"] if isinstance(profile.get("years"), list) else []
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    best = profile["best"] if isinstance(profile.get("best"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    latest_delta = int(profile.get("latest_delta", 0))
    latest_year = str(profile.get("latest_year", ""))
    is_current = bool(profile.get("is_current"))
    latest_rank = ordinal(latest["rank_int"]) if latest else "N/A"
    latest_rank_year = latest["year"] if latest else ""
    best_rank = ordinal(best["rank_int"]) if best else "N/A"
    best_year = best["year"] if best else ""
    if latest and not is_current:
        status_label = "Current status"
        status_value = "Outside Top 100"
        status_meta = f"Most recent {rank_hash(latest['rank_int'])} in {latest['year']}"
        movement = "Dropped out"
        movement_meta = f"not in {latest_year}" if latest_year else "latest list"
    else:
        status_label = "Latest rank"
        status_value = rank_hash(latest["rank_int"]) if latest else latest_rank
        status_meta = f"in {latest_rank_year}" if latest_rank_year else ""
        movement = "Steady" if previous and latest_delta == 0 else signed_movement_label(latest_delta) if previous else "First listed"
        movement_meta = f"from {previous['year']}" if previous else (f"in {latest_rank_year}" if latest_rank_year else "No previous year")
    trend = str(profile.get("trend_label", "ranking history"))
    trend = trend[:1].upper() + trend[1:] if trend else "Ranking history"
    if ";" in trend:
        trend = trend.split(";")[0]
    cards = [
        ("rank", status_label, status_value, status_meta),
        ("trophy", "Best rank", rank_hash(best["rank_int"]) if best else best_rank, f"in {best_year}" if best_year else ""),
        ("rise", "Latest movement", movement, movement_meta),
        ("rise", "Trend", trend, "ranking history"),
        ("calendar", "First listed", first["year"] if first else "N/A", ordinal(first["rank_int"]) if first else ""),
        ("clock", "Years ranked", f"{len(history)} of {len(years)}", f"{history[0]['year']} to {history[-1]['year']}" if history else "years covered"),
    ]
    return "".join(
        '<article class="pilot-stat-card">'
        f'<i>{pilot_small_icon(icon)}</i>'
        f'<span>{esc(label)}</span>'
        f'<strong>{esc(value)}</strong>'
        f'<em>{esc(meta)}</em>'
        '</article>'
        for icon, label, value, meta in cards
    )


def rank_history_svg(name: str, history: list[dict[str, str]]) -> str:
    if not history:
        return ""
    width = 980
    height = 430
    left = 76
    right = 34
    top = 48
    bottom = 74
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_for(index: int) -> float:
        return left + plot_width * (index / max(1, len(history) - 1))

    def y_for(rank: int) -> float:
        return top + plot_height * ((rank - 1) / 99)

    points = [(x_for(index), y_for(int(row["rank_int"])), row) for index, row in enumerate(history)]
    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    area_points = f"{left},{top + plot_height} {line_points} {left + plot_width},{top + plot_height}"
    grid = []
    for rank in [1, 25, 50, 75, 100]:
        y = y_for(rank)
        label = "1st" if rank == 1 else f"{rank}th"
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" />')
        grid.append(f'<text x="{left - 16}" y="{y + 5:.1f}" text-anchor="end">{label}</text>')
    labels = []
    for index, (x, _, row) in enumerate(points):
        is_edge = index in {0, len(points) - 1}
        if is_edge or index % 2 == 0:
            labels.append(f'<text x="{x:.1f}" y="{height - 25}" text-anchor="middle">{esc(row["year"])}</text>')
    circles = []
    for index, (x, y, row) in enumerate(points):
        latest = index == len(points) - 1
        radius = 8 if latest else 5
        css_class = "latest-point" if latest else "history-point"
        circles.append(
            f'<circle class="{css_class}" cx="{x:.1f}" cy="{y:.1f}" r="{radius}">'
            f'<title>{esc(row["year"])}: {esc(ordinal(row["rank_int"]))}</title>'
            '</circle>'
        )
    latest = history[-1]
    return (
        f'<svg class="pilot-rank-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(name)} Australian ranking history from {esc(history[0]["year"])} to {esc(latest["year"])}">'
        '<g class="rank-grid">'
        + "".join(grid)
        + '</g>'
        '<g class="rank-labels">'
        + "".join(labels)
        + '</g>'
        f'<polygon class="rank-area" points="{area_points}" />'
        f'<polyline class="rank-line" points="{line_points}" />'
        + "".join(circles)
        + f'<text class="latest-label" x="{points[-1][0] - 12:.1f}" y="{points[-1][1] - 18:.1f}" text-anchor="end">{esc(ordinal(latest["rank_int"]))}</text>'
        '</svg>'
    )


def pilot_popularity_summary(profile: dict[str, object]) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    best = profile["best"] if isinstance(profile.get("best"), dict) else None
    latest_delta = int(profile.get("latest_delta", 0))
    latest_year = str(profile.get("latest_year", ""))
    is_current = bool(profile.get("is_current"))
    if not latest:
        return f"{name} has ranking history in the Australian baby-name data for {sex_plural(sex)}."
    if not is_current:
        parts = [
            f"{name} is not in the {latest_year} Top 100 for {sex_plural(sex)}.",
            f"Its most recent ranked appearance is {ordinal(latest['rank_int'])} in {latest['year']}."
        ]
    else:
        parts = [
            f"{name} ranks {ordinal(latest['rank_int'])} for {sex_plural(sex)} in the latest available Australian data ({latest['year']})."
        ]
    if best and latest["year"] == best["year"] and latest["rank_int"] == best["rank_int"]:
        parts.append(f"That is also its highest recorded rank in the years currently covered.")
    elif best:
        parts.append(f"Its best recorded rank is {ordinal(best['rank_int'])} in {best['year']}.")
    if first:
        overall_delta = int(first["rank_int"]) - int(latest["rank_int"])
        parts.append(f"Since first appearing at {ordinal(first['rank_int'])} in {first['year']}, it has moved {signed_movement_phrase(overall_delta)} overall.")
    if previous and is_current:
        direction = "rose" if latest_delta > 0 else "fell" if latest_delta < 0 else "held steady"
        if latest_delta:
            parts.append(f"In the latest year-to-year comparison it {direction} {abs(latest_delta)} {place_word(latest_delta)}.")
        else:
            parts.append("It held the same rank in the latest year-to-year comparison.")
    elif previous and not is_current:
        parts.append(f"Before dropping out of the latest Top 100, it moved from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.")
    return " ".join(parts)


def pilot_milestones(profile: dict[str, object]) -> str:
    history = profile["history"] if isinstance(profile.get("history"), list) else []
    if not history:
        return ""
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    best = profile["best"] if isinstance(profile.get("best"), dict) else None
    milestones: list[tuple[str, str, str]] = []
    if best:
        milestones.append(("Highest-ever rank", f"{rank_hash(best['rank_int'])}", f"in {best['year']}"))
    for threshold in [10, 20, 50]:
        entry = next((row for row in history if int(row["rank_int"]) <= threshold), None)
        if entry:
            milestones.append((f"Entered Top {threshold}", entry["year"], f"ranked {ordinal(entry['rank_int'])}"))
    if first:
        milestones.append(("First listed in Australia", first["year"], ordinal(first["rank_int"])))
    biggest = None
    for prev, curr in zip(history, history[1:]):
        delta = int(prev["rank_int"]) - int(curr["rank_int"])
        if delta > 0 and (biggest is None or delta > biggest[0]):
            biggest = (delta, prev, curr)
    if biggest:
        milestones.append(("Biggest yearly rise", f"+{biggest[0]} {place_word(biggest[0])}", f"{biggest[1]['year']} to {biggest[2]['year']}"))
    if previous and latest:
        delta = int(previous["rank_int"]) - int(latest["rank_int"])
        if delta:
            milestones.append(("Latest movement", f"{signed_movement_label(delta)} {place_word(delta)}", f"{previous['year']} to {latest['year']}"))
    cards = []
    seen = set()
    for title, value, note in milestones:
        key = (title, value, note)
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            '<article class="pilot-milestone">'
            f'<i>{pilot_small_icon("trophy" if not cards else "rank")}</i>'
            f'<span>{esc(title)}</span>'
            f'<strong>{esc(value)}</strong>'
            f'<em>{esc(note)}</em>'
            '</article>'
        )
        if len(cards) >= 6:
            break
    return "".join(cards)


def pilot_info_sections(profile: dict[str, object]) -> str:
    name = str(profile["name"])
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    cards = []
    meaning = str(meta.get("meaning", "")) if isinstance(meta, dict) else ""
    origin = str(meta.get("origin", "")) if isinstance(meta, dict) else ""
    if meaning and "uncertain" not in meaning.lower():
        meaning_text = meaning_reference(meaning)
        cards.append(
            '<section class="pilot-info-card pilot-meaning-card">'
            f'<div class="pilot-info-title">{pilot_small_icon("meaning")}<h2>Meaning</h2></div>'
            f'<p>The name {esc(name)} is commonly linked to {esc(meaning_text)}.</p>'
            f'<div class="pilot-nutshell"><span>In a nutshell</span><strong>{esc(name)} means &ldquo;{esc(phrase_list(meaning))}&rdquo;.</strong></div>'
            '</section>'
        )
    if origin:
        origin_text = article_phrase(origin)
        cards.append(
            '<section class="pilot-info-card pilot-origin-card">'
            f'<div class="pilot-info-title">{pilot_small_icon("origin")}<h2>Origin</h2></div>'
            f'<p>{esc(name)} is usually described as {esc(origin_text)}.</p>'
            f'<div class="pilot-nutshell"><span>Origin in brief</span><strong>{esc(display_phrase(origin))}</strong></div>'
            '</section>'
        )
    if not cards:
        return ""
    return '<section class="pilot-info-grid">' + "".join(cards) + '</section>'


def pilot_faq_items(profile: dict[str, object]) -> list[tuple[str, str]]:
    name = str(profile["name"])
    sex = str(profile["sex"])
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    latest_delta = int(profile.get("latest_delta", 0))
    latest_year = str(profile.get("latest_year", ""))
    is_current = bool(profile.get("is_current"))
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    items: list[tuple[str, str]] = []
    if latest:
        if not is_current:
            popularity_answer = f"{name} is not in the {latest_year} Top 100 for baby {sex_plural(sex)}. Its most recent appearance was {rank_hash(latest['rank_int'])} in {latest['year']}."
        elif int(latest["rank_int"]) <= 10:
            popularity_answer = f"Yes. {name} ranked {rank_hash(latest['rank_int'])} for baby {sex_plural(sex)} in Australia in {latest['year']}, placing it inside the current top 10."
        else:
            popularity_answer = f"{name} ranked {rank_hash(latest['rank_int'])} for baby {sex_plural(sex)} in Australia in {latest['year']}."
        items.append((
            f"Is {name} a popular name in Australia?",
            popularity_answer
        ))
    if previous and latest:
        if latest_delta > 0:
            answer = f"Yes. {name} moved from {rank_hash(previous['rank_int'])} in {previous['year']} to {rank_hash(latest['rank_int'])} in {latest['year']}, a rise of {latest_delta} {place_word(latest_delta)}."
        elif latest_delta < 0:
            answer = f"In the latest comparison, {name} moved from {rank_hash(previous['rank_int'])} in {previous['year']} to {rank_hash(latest['rank_int'])} in {latest['year']}, a fall of {abs(latest_delta)} {place_word(latest_delta)}."
        else:
            answer = f"{name} held the same rank from {previous['year']} to {latest['year']}."
        if first and latest:
            answer += f" Over the full visible history it moved from {rank_hash(first['rank_int'])} in {first['year']} to {rank_hash(latest['rank_int'])} in {latest['year']}."
        items.append((f"Is {name} becoming more popular?", answer))
    items.append((f"Is {name} a girl or boy name?", f"On Baby Names Australia, {name} appears as a baby {sex_label(sex).lower()} name."))
    meaning = str(meta.get("meaning", "")) if isinstance(meta, dict) else ""
    if meaning and "uncertain" not in meaning.lower():
        items.append((f"What does {name} mean?", f"{name} is most commonly linked to {meaning_reference(meaning)}."))
    origin = str(meta.get("origin", "")) if isinstance(meta, dict) else ""
    if origin:
        items.append((f"What is the origin of {name}?", f"{name} is usually described as {article_phrase(origin)}."))
    nicknames = split_values(str(meta.get("nicknames", ""))) if isinstance(meta, dict) else []
    if nicknames:
        items.append((f"Is {name} short for anything?", f"{name} is usually used as its own name. Nickname options include {phrase_list('; '.join(nicknames))}."))
    return items


def pilot_faq_html(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    return "".join(
        '<details class="pilot-faq-item">'
        f'<summary>{esc(question)}</summary>'
        f'<p>{esc(answer)}</p>'
        '</details>'
        for question, answer in items
    )


def pilot_similar_cards(
    name: str,
    sex: str,
    similar_names: list[str],
    histories: dict[tuple[str, str], list[dict[str, str]]],
    metadata: dict[tuple[str, str], dict[str, str]],
    existing_names: set[str],
) -> str:
    cards = []
    for item in similar_names:
        if item.lower() not in existing_names:
            continue
        history = histories.get((item.lower(), sex), [])
        latest = history[-1] if history else None
        meta = metadata_for_name(item, sex, metadata)
        trend_label, _ = movement_summary(history, len(history)) if len(history) >= 3 else ("Ranking profile", "")
        tags = style_tags_for_name(item, sex, meta, history, trend_label)
        descriptor = tags[0] if tags else (f"Latest {ordinal(latest['rank_int'])}" if latest else "Profile")
        latest_text = f"Latest {rank_hash(latest['rank_int'])}" if latest else "Ranking profile"
        cards.append(
            f'<a class="pilot-similar-card" href="{slugify(item)}.html">'
            f'<i class="pilot-name-illustration">{pilot_small_icon("nature" if descriptor.lower().startswith("nature") else "heart")}</i>'
            f'<span>{esc(descriptor)}</span>'
            f'<strong>{esc(item)}</strong>'
            f'<em>{esc(latest_text)}</em>'
            '<b>View profile &rarr;</b>'
            '</a>'
        )
        if len(cards) >= 6:
            break
    if len(cards) < 4:
        return ""
    return "".join(cards)


def pilot_category_cards(profile: dict[str, object]) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    candidates = []
    for definition in LANDING_PAGE_DEFINITIONS:
        if definition["sex"] not in {"all", sex}:
            continue
        score = landing_category_score(profile, definition)
        if score is None:
            continue
        candidates.append((score, definition))
    priority = ["nature", "vintage", "rising", "cute", "unique", "beautiful_meaning", "nicknames", "australian"]
    candidates.sort(key=lambda item: (priority.index(item[1]["kind"]) if item[1]["kind"] in priority else 99, -item[0]))
    cards = []
    for _, definition in candidates[:4]:
        cards.append(
            f'<a class="pilot-category-card" href="../../{definition["slug"]}.html">'
            f'<span>{esc(definition["heading"])}</span>'
            f'<em>{esc(landing_reason(profile, definition))}</em>'
            '<b>Explore &rarr;</b>'
            '</a>'
        )
    if not cards:
        return ""
    return (
        '<section class="pilot-section pilot-discovery-section">'
        f'<header><h2>If you like {esc(name)}, explore these name lists</h2></header>'
        f'<div class="pilot-category-grid">{"".join(cards)}</div>'
        '</section>'
    )


def pilot_favourites_script(path_prefix: str) -> str:
    return f'    <script src="{path_prefix}favourites.js" defer></script>\n'


def write_favourites_js() -> None:
    write_if_changed(ROOT / "favourites.js", FAVOURITES_JS)


def pilot_topbar(path_prefix: str = "../../") -> str:
    return f"""    <nav class="pilot-topbar" aria-label="Site navigation">
      <a class="pilot-brand" href="{path_prefix}">BabyNames<span>Australia</span><em aria-hidden="true">&hearts;</em></a>
      <div class="pilot-nav-links" aria-label="Popular sections">
        <a href="{path_prefix}names/girls/">Baby Names</a>
        <a href="{path_prefix}popular-baby-girl-names-australia.html">Popular</a>
        <a href="{path_prefix}unique-australian-baby-names.html">Unique</a>
        <a href="{path_prefix}classic-baby-names.html">Vintage</a>
        <a href="{path_prefix}baby-name-popularity-checker-australia.html">Tools</a>
      </div>
      <a class="pilot-favourites-link" href="{path_prefix}favourites.html" aria-label="View favourite baby names">♡ Favourites<span data-favourite-count></span></a>
      <form class="pilot-top-search" action="{path_prefix}" method="get">
        <label class="sr-only" for="pilot-site-search">Search a name</label>
        <input id="pilot-site-search" name="name" type="search" placeholder="Search a name..." />
        <button type="submit" aria-label="Search baby names">Search</button>
      </form>
    </nav>"""


def pilot_schema_json(
    profile: dict[str, object],
    canonical: str,
    title: str,
    description: str,
    similar_names: list[str],
    faq_items: list[tuple[str, str]],
) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    graph: list[dict[str, object]] = [
        {
            "@type": "WebPage",
            "@id": canonical,
            "url": canonical,
            "name": title,
            "description": description,
            "isPartOf": {
                "@type": "WebSite",
                "name": "Australian Baby Name Rankings",
                "url": f"{BASE_URL}/",
            },
            "about": {
                "@type": "DefinedTerm",
                "name": name,
                "inDefinedTermSet": "Australian Baby Names",
                "description": f"{name} means {meta.get('meaning', 'baby name')}." if isinstance(meta, dict) and meta.get("meaning") else f"{name} baby name.",
            },
            "mainEntity": {
                "@type": "Thing",
                "name": name,
                "description": f"{name} ranked {ordinal(latest['rank_int'])} for baby {sex_plural(sex)} in Australia in {latest['year']}." if latest else f"{name} baby name profile.",
            },
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE_URL}/"},
                {"@type": "ListItem", "position": 2, "name": f"{sex_label(sex)}s names", "item": f"{BASE_URL}/names/{sex_plural(sex)}/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
            ],
        },
    ]
    if similar_names:
        graph[0]["mentions"] = [{"@type": "Thing", "name": item} for item in similar_names[:6]]
    if faq_items:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
                for question, answer in faq_items
            ],
        })
    return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": graph}, separators=(",", ":")) + "</script>"


def pilot_name_profile_html(
    rows: list[dict[str, str]],
    metadata: dict[tuple[str, str], dict[str, str]],
    name: str,
    sex: str,
    histories: dict[tuple[str, str], list[dict[str, str]]] | None = None,
    existing_by_sex: dict[str, set[str]] | None = None,
) -> str:
    profile = name_profile_dataset(rows, metadata, name, sex)
    if not profile:
        raise ValueError(f"No ranking history found for {name} / {sex}")

    years = profile["years"] if isinstance(profile.get("years"), list) else []
    history = profile["history"] if isinstance(profile.get("history"), list) else []
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    canonical = name_page_url(name, sex)
    title = f"{name} Name Meaning, Origin & Popularity in Australia"
    description = truncate_meta(
        f"{name} baby {sex_label(sex).lower()} name meaning, origin and Australian popularity. "
        f"See ranking history, milestones, similar names and FAQs."
    )
    if histories is None or existing_by_sex is None:
        by_name_sex = {(row["name"], row["sex"]) for row in rows}
        existing_by_sex = {
            item_sex: {item_name.lower() for item_name, sex_value in by_name_sex if sex_value == item_sex}
            for item_sex in ["girl", "boy"]
        }
        histories = {
            (item_name.lower(), item_sex): rows_for_name(rows, item_name, item_sex)
            for item_name, item_sex in by_name_sex
        }
    similar_names = similar_names_for(name, sex, histories, metadata, existing_by_sex[sex])
    faq_items = pilot_faq_items(profile)
    schema_json = pilot_schema_json(profile, canonical, title, description, similar_names, faq_items)
    head_html = shared_head_html(
        title,
        description,
        canonical,
        "../../styles.css",
        "../../assets/favicon.ico",
        "../../assets/favicon-32x32.png",
        "../../assets/apple-touch-icon.png",
        schema_json,
        "article",
    )
    identity_tags = pilot_identity_tag_html(profile)
    chart = rank_history_svg(name, history)
    movement_line = ""
    rank_transition = ""
    if latest and not bool(profile.get("is_current")):
        latest_year = str(profile.get("latest_year", ""))
        movement_line = (
            '<div class="pilot-movement-callout">'
            f'<span>{esc(latest["year"])} {esc(rank_hash(latest["rank_int"]))}</span>'
            '<b aria-hidden="true">&rarr;</b>'
            f'<span>{esc(latest_year)} outside Top 100</span>'
            '<strong>Dropped out</strong>'
            '</div>'
        )
    elif latest and previous:
        delta = int(profile.get("latest_delta", 0))
        direction_word = "Up" if delta > 0 else "Down" if delta < 0 else "Steady"
        movement_text = f"{direction_word} {abs(delta)} {place_word(delta)}" if delta else "Steady"
        movement_line = (
            '<div class="pilot-movement-callout">'
            f'<span>{esc(previous["year"])} {esc(rank_hash(previous["rank_int"]))}</span>'
            '<b aria-hidden="true">&rarr;</b>'
            f'<span>{esc(latest["year"])} {esc(rank_hash(latest["rank_int"]))}</span>'
            f'<strong>{esc(movement_text)}</strong>'
            '</div>'
        )
        rank_transition = f"{previous['year']} {rank_hash(previous['rank_int'])} to {latest['year']} {rank_hash(latest['rank_int'])}"
    info_sections = pilot_info_sections(profile)
    similar_cards = pilot_similar_cards(name, sex, similar_names, histories, metadata, existing_by_sex[sex])
    similar_section = ""
    if similar_cards:
        similar_section = (
            '<section class="pilot-section">'
            f'<header><h2>Names similar to {esc(name)}</h2></header>'
            f'<div class="pilot-similar-grid">{similar_cards}</div>'
            '</section>'
        )
    faq_html = pilot_faq_html(faq_items)
    faq_section = ""
    if faq_html:
        faq_section = (
            '<section class="pilot-section pilot-faq-section">'
            '<header><p>Quick answers</p>'
            f'<h2>Questions about {esc(name)}</h2></header>'
            f'<div class="pilot-faq-list">{faq_html}</div>'
            '</section>'
        )
    meaning_origin_section = ""
    if info_sections:
        meaning_origin_section = (
            '<section class="pilot-section pilot-info-section">'
            f'{info_sections}'
            '</section>'
        )
    history_rows = "".join(
        f'<tr><td>{esc(row["year"])}</td><td>{esc(rank_hash(row["rank_int"]))}</td></tr>'
        for row in reversed(history)
    )
    source_year = latest["year"] if latest else (max(years) if years else "")
    latest_rank_text = f"{rank_hash(latest['rank_int'])} in {latest['year']}" if latest else "Ranking profile"
    favourite_trend = str(profile.get("trend_label", "Ranking history"))
    favourite_trend = favourite_trend.split(";")[0]
    favourite_trend = favourite_trend[:1].upper() + favourite_trend[1:] if favourite_trend else "Ranking history"
    favourite_style = pilot_identity_tags(profile)[0] if pilot_identity_tags(profile) else sex_label(sex)
    favourite_url = f"/names/{sex_plural(sex)}/{slugify(name)}.html"
    return f"""<!doctype html>
<html lang="en">
  {head_html}
  <body class="profile-pilot-page">
{pilot_topbar("../../")}

    <main class="pilot-page-shell">
      <section class="pilot-hero-panel">
        <div class="pilot-hero-copy">
          {visible_breadcrumbs_for_name(name, sex)}
          <div class="pilot-title-row">
            <h1>{esc(name)}</h1>
            <button class="pilot-favourite" type="button" aria-pressed="false" data-favourite-toggle data-favourite-name="{esc(name)}" data-favourite-gender="{esc(sex_label(sex))}" data-favourite-url="{esc(favourite_url)}" data-favourite-latest="{esc(latest_rank_text)}" data-favourite-trend="{esc(favourite_trend)}" data-favourite-style="{esc(favourite_style)}">{pilot_small_icon("heart")} <span data-favourite-label>Add to favourites</span></button>
          </div>
          <div class="pilot-identity-tags">{identity_tags}</div>
          <p>{esc(pilot_intro_sentence(profile))}</p>
        </div>
        <div class="pilot-hero-art">
          {hazel_botanical_svg()}
        </div>
      </section>

      <section class="pilot-summary-strip" aria-label="{esc(name)} at a glance">
        <div class="pilot-stat-grid">
          {pilot_stat_cards(profile)}
        </div>
      </section>

      <div class="pilot-history-jump">
        <a href="#ranking-history">View ranking history</a>
      </div>

      <section id="ranking-history" class="pilot-chart-layout" aria-label="{esc(name)} popularity history">
        <article class="pilot-chart-card">
          <header>
            <h2>Popularity of {esc(name)} in Australia</h2>
          </header>
          <div class="pilot-chart-frame">
            {chart}
          </div>
          <div class="pilot-chart-notes">
            {movement_line}
            <p>{esc(pilot_popularity_summary(profile))}</p>
          </div>
          <details class="pilot-rank-details">
            <summary>View yearly ranks</summary>
            <table>
              <thead><tr><th>Year</th><th>Rank</th></tr></thead>
              <tbody>{history_rows}</tbody>
            </table>
          </details>
        </article>
        <aside class="pilot-milestone-box">
          <h2>Popularity milestones</h2>
          <div class="pilot-milestone-grid">
          {pilot_milestones(profile)}
          </div>
        </aside>
      </section>

      <section class="pilot-knowledge-grid">
        {meaning_origin_section}

        {faq_section}
      </section>

      {similar_section}

      {pilot_category_cards(profile)}

      <section class="pilot-data-box">
        <div>
          <h2>About the data</h2>
          <p>Popularity figures use the Australian ranking datasets used by Baby Names Australia, with source-priority rules applied where public sources overlap.</p>
        </div>
        <div>
          <span>Latest data year</span>
          <strong>{esc(source_year)}</strong>
        </div>
        <div>
          <span>Last updated</span>
          <strong>{esc(TODAY)}</strong>
        </div>
        <div>
          <span>Useful links</span>
          <a href="../../data-sources.html">Data sources</a>
          <a href="../../rankings/top-{sex_plural(sex)}-{esc(str(source_year))}.html">{esc(str(source_year))} rankings</a>
        </div>
      </section>
    </main>

    <footer class="pilot-footer">
      <div>
        <h2>Keep exploring baby names</h2>
        <p>Search another name, compare popularity, or browse the latest Australian baby-name rankings.</p>
        <nav class="seo-links" aria-label="Footer links">
          <a href="../../#name-explorer">Name explorer</a>
          <a href="../../baby-name-popularity-checker-australia.html">Popularity checker</a>
          <a href="../../rankings/top-{sex_plural(sex)}-{esc(str(source_year))}.html">Latest {sex_plural(sex)} rankings</a>
        </nav>
      </div>
    </footer>
{pilot_favourites_script("../../")}
  </body>
</html>
"""


def generate_single_name_pilot_page(
    rows: list[dict[str, str]],
    metadata: dict[tuple[str, str], dict[str, str]],
    name: str = "Hazel",
    sex: str = "girl",
) -> Path:
    path = name_page_path(name, sex)
    write_if_changed(path, pilot_name_profile_html(rows, metadata, name, sex))
    return path


def generate_favourites_page(sitemap_urls: list[str]) -> None:
    canonical = f"{BASE_URL}/favourites.html"
    title = "Favourite Baby Names | Baby Names Australia"
    description = "Save baby names you love and return to your shortlist on this device."
    head_html = shared_head_html(
        title,
        description,
        canonical,
        "./styles.css",
        "./assets/favicon.ico",
        "./assets/favicon-32x32.png",
        "./assets/apple-touch-icon.png",
        "",
        "website",
    )
    content = f"""<!doctype html>
<html lang="en">
  {head_html}
  <body class="profile-pilot-page favourites-page">
{pilot_topbar("./")}

    <main class="pilot-page-shell favourites-shell">
      <section class="favourites-hero">
        <p class="section-kicker">Saved shortlist</p>
        <h1>Your favourite baby names</h1>
        <p>Save names as you browse and return to your shortlist anytime on this device.</p>
      </section>

      <section class="favourites-panel" aria-live="polite">
        <div class="favourites-grid" data-favourites-list></div>
        <div class="favourites-empty" data-favourites-empty>
          <h2>No favourites yet</h2>
          <p>Browse baby names and tap the heart on any name you want to save.</p>
          <nav class="seo-links" aria-label="Start exploring">
            <a href="./#name-explorer">Name Explorer</a>
            <a href="./baby-name-popularity-checker-australia.html">Baby Name Popularity Checker</a>
            <a href="./names/girls/">Girl Names</a>
            <a href="./names/boys/">Boy Names</a>
            <a href="./rising-baby-girl-names.html">Rising Names</a>
          </nav>
        </div>
      </section>

      <p class="favourites-device-note">Favourites are saved on this device.</p>
    </main>

{pilot_favourites_script("./")}
  </body>
</html>
"""
    write_if_changed(ROOT / "favourites.html", content)
    sitemap_urls.append(canonical)


def related_links_for_ranking(year: str, sex: str, years: list[str]) -> str:
    available = sorted(years, reverse=True)
    links = [
        f'<a href="./top-{"boys" if sex == "girl" else "girls"}-{year}.html">Top {"boys" if sex == "girl" else "girls"} {year}</a>',
        f'<a href="../names/{sex_plural(sex)}/">All {sex_plural(sex)} names</a>',
        f'<a href="../popular-baby-{sex_label(sex).lower()}-names-australia.html">Popular {sex_label(sex).lower()} names</a>',
    ]
    index = available.index(year)
    if index + 1 < len(available):
        older = available[index + 1]
        links.append(f'<a href="./top-{sex_plural(sex)}-{older}.html">Top {sex_plural(sex)} {older}</a>')
    if index - 1 >= 0:
        newer = available[index - 1]
        links.append(f'<a href="./top-{sex_plural(sex)}-{newer}.html">Top {sex_plural(sex)} {newer}</a>')
    links.append('<a href="../data-sources.html">Data sources</a>')
    return "\n".join(links)


def generate_name_pages(
    rows: list[dict[str, str]],
    sitemap_urls: list[str],
    metadata: dict[tuple[str, str], dict[str, str]],
) -> None:
    by_name_sex: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_name_sex[(row["name"], row["sex"])].append(row)
    existing_by_sex = {
        sex: {name.lower() for (name, item_sex) in by_name_sex if item_sex == sex}
        for sex in ["girl", "boy"]
    }
    histories = {
        (name.lower(), sex): rows_for_name(rows, name, sex)
        for name, sex in by_name_sex
    }

    girl_count = sum(1 for _, sex in by_name_sex if sex == "girl")
    boy_count = sum(1 for _, sex in by_name_sex if sex == "boy")
    print(f"Detected {girl_count} girl name pages and {boy_count} boy name pages")
    updated_count = 0
    for (name, sex), name_rows in sorted(by_name_sex.items(), key=lambda item: (item[0][1], item[0][0])):
        path = name_page_path(name, sex)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_if_changed(path, pilot_name_profile_html(rows, metadata, name, sex, histories, existing_by_sex))
        sitemap_urls.append(name_page_url(name, sex))
        updated_count += 1
    print(f"Updated {updated_count} individual name pages")


def rows_for_name(rows: list[dict[str, str]], name: str, sex: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for year in sorted({row["year"] for row in rows}):
        matches = [row for row in rows_for_year_sex(rows, year, sex) if row["name"].lower() == name.lower()]
        if matches:
            result.append(matches[0])
    return result


def generate_ranking_pages(rows: list[dict[str, str]], sitemap_urls: list[str]) -> None:
    template = read_template("ranking-page-template.html")
    years = sorted({row["year"] for row in rows}, reverse=True)
    for year in years:
        for sex in ["girl", "boy"]:
            ranked_rows = [
                row for row in rows_for_year_sex(rows, year, sex)
                if int(row["rank_int"]) <= 100
            ]
            if not ranked_rows:
                continue
            top_name = ranked_rows[0]["name"]
            title = f"Top 100 Baby {sex_label(sex)} Names in Australia {year}"
            heading = f"Top baby {sex_label(sex).lower()} names in Australia — {year}"
            summary = f"These were the top baby {sex_label(sex).lower()} names in Australia for {year} based on available ranking data."
            description = truncate_meta(
                f"See the top 100 baby {sex_label(sex).lower()} names in Australia for {year}. "
                f"{top_name} ranked #1, with full rankings and links to name meaning and popularity pages."
            )
            table_rows = "\n".join(
                "<tr>"
                f"<td>{ordinal(row['rank_int'])}</td>"
                f"<td><a href=\"../names/{sex_plural(sex)}/{slugify(row['name'])}.html\">{esc(row['name'])}</a></td>"
                f"<td>{sex_label(sex)}</td>"
                "</tr>"
                for row in ranked_rows[:100]
            )
            path = ranking_page_path(year, sex)
            canonical = ranking_page_url(year, sex)
            safe_description = esc(description)
            schema_json = ranking_schema_json(year, sex, canonical, title, safe_description, ranked_rows)
            write_if_changed(
                path,
                render(
                    template,
                    {
                        "title": title,
                        "description": safe_description,
                        "canonical_url": canonical,
                        "schema_json": schema_json,
                        "heading": heading,
                        "summary": summary,
                        "topbar": pilot_topbar("../"),
                        "ranking_rows": table_rows,
                        "ranking_insights": ranking_insights_for_page(ranked_rows, year, sex),
                        "ranking_feature_cards": ranking_feature_cards_for_page(ranked_rows, sex),
                        "related_links": related_links_for_ranking(year, sex, years),
                        "favourites_script": pilot_favourites_script("../"),
                    },
                ),
            )
            sitemap_urls.append(canonical)


def ranking_insights_for_page(ranked_rows: list[dict[str, str]], year: str, sex: str) -> str:
    top_three = ", ".join(row["name"] for row in ranked_rows[:3])
    outside_top_50 = sum(1 for row in ranked_rows if int(row["rank_int"]) > 50)
    return (
        '<div class="ranking-insight-strip">'
        f'<div><span>Top three</span><b>{esc(top_three)}</b></div>'
        f'<div><span>List size</span><b>{len(ranked_rows[:100])} names</b></div>'
        f'<div><span>Outside top 50</span><b>{outside_top_50} names</b></div>'
        f'<div><span>Year</span><b>{esc(year)}</b></div>'
        '</div>'
    )


def ranking_feature_cards_for_page(ranked_rows: list[dict[str, str]], sex: str) -> str:
    cards = []
    for row in ranked_rows[:3]:
        name = row["name"]
        cards.append(
            '<a class="ranking-feature-card" href="../names/'
            f'{sex_plural(sex)}/{slugify(name)}.html">'
            f'<span>{ordinal(row["rank_int"])}</span>'
            f'<b>{esc(name)}</b>'
            f'<em>View meaning and popularity history</em>'
            '</a>'
        )
    return "\n".join(cards)


def shared_head_html(
    title: str,
    description: str,
    canonical: str,
    stylesheet: str,
    favicon: str,
    favicon_png: str,
    apple_icon: str,
    schema_json: str = "",
    og_type: str = "website",
) -> str:
    return f"""<head>
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-7E2KMVP098"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());

      gtag('config', 'G-7E2KMVP098');
    </script>

{PINTEREST_TAG}
{ADSENSE_TAG}
{PINTEREST_VERIFY_META}    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(description)}" />
    <meta name="robots" content="index, follow" />
    <meta name="theme-color" content="#4eb980" />
    <link rel="canonical" href="{esc(canonical)}" />
    <link rel="icon" href="{favicon}" sizes="any" />
    <link rel="icon" type="image/png" sizes="32x32" href="{favicon_png}" />
    <link rel="apple-touch-icon" href="{apple_icon}" />
    <meta property="og:type" content="{esc(og_type)}" />
    <meta property="og:title" content="{esc(title)}" />
    <meta property="og:description" content="{esc(description)}" />
    <meta property="og:url" content="{esc(canonical)}" />
    <meta property="og:site_name" content="Australian Baby Name Rankings" />
    <meta property="og:image" content="https://www.babynamesaustralia.com/assets/social-preview.png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="Australian Baby Names search and ranking explorer" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{esc(title)}" />
    <meta name="twitter:description" content="{esc(description)}" />
    <meta name="twitter:image" content="https://www.babynamesaustralia.com/assets/social-preview.png" />
    <link rel="stylesheet" href="{stylesheet}" />
    {schema_json}
  </head>"""


def discovery_page_html(
    title: str,
    description: str,
    canonical: str,
    body_title: str,
    body_intro: str,
    cards_html: str,
    schema_json: str,
    depth: str = ".",
    theme: str = "data",
) -> str:
    stylesheet = f"{depth}/styles.css" if depth != "." else "./styles.css"
    favicon = f"{depth}/assets/favicon.ico" if depth != "." else "./assets/favicon.ico"
    favicon_png = f"{depth}/assets/favicon-32x32.png" if depth != "." else "./assets/favicon-32x32.png"
    apple_icon = f"{depth}/assets/apple-touch-icon.png" if depth != "." else "./assets/apple-touch-icon.png"
    home = f"{depth}/" if depth != "." else "./"
    top_girls = f"{depth}/rankings/top-girls-2025.html" if depth != "." else "./rankings/top-girls-2025.html"
    top_boys = f"{depth}/rankings/top-boys-2025.html" if depth != "." else "./rankings/top-boys-2025.html"
    head_html = shared_head_html(
        title,
        description,
        canonical,
        stylesheet,
        favicon,
        favicon_png,
        apple_icon,
        schema_json,
    )
    return f"""<!doctype html>
<html lang="en">
  {head_html}
  <body class="profile-pilot-page directive-page discovery-page landing-theme-{esc(theme)}">
{pilot_topbar(f"{depth}/" if depth != "." else "./")}
    <header id="header">
      <span class="logo" aria-hidden="true">A</span>
      <h1>{esc(body_title)}</h1>
      <p>{esc(body_intro)}</p>
      <div class="header-actions">
        <a class="button" href="{home}#name-explorer">Search baby names</a>
        <a class="button alt" href="{home}#top-rankings">Browse rankings</a>
      </div>
    </header>

    <main id="main">
      <header class="major container medium">
        <h2>{esc(body_title)}</h2>
        <p>Open a name to see meaning, origin, similar names and Australian ranking history.</p>
      </header>

      <section class="box container discovery-list">
        {cards_html}
      </section>

      <footer class="major container medium">
        <h2>Keep exploring</h2>
        <div class="seo-links">
          <a href="{top_girls}">Top girls 2025</a>
          <a href="{top_boys}">Top boys 2025</a>
          <a href="{home}">Name explorer</a>
        </div>
      </footer>
    </main>

    <footer id="site-footer">
      <div class="container medium">
        <h2>Find the name that fits</h2>
        <p>Search meanings, origins, rankings and similar names in the Australian baby-name explorer.</p>
      </div>
    </footer>
{pilot_favourites_script(f"{depth}/" if depth != "." else "./")}
  </body>
</html>
"""


def discovery_cards(items: list[dict[str, str]], prefix: str = ".") -> str:
    cards = []
    for item in items:
        href = f"{prefix}/names/{sex_plural(item['sex'])}/{slugify(item['name'])}.html"
        meta = item.get("meta", "")
        cards.append(
            f'<a class="discovery-card" href="{href}">'
            f'<span>{esc(item["label"])}</span>'
            f'<b>{esc(item["name"])}</b>'
            f'<em>{esc(meta)}</em>'
            f'</a>'
        )
    return f'<div class="discovery-grid">{"".join(cards)}</div>'


LANDING_PAGE_DEFINITIONS: list[dict[str, str]] = [
    {
        "slug": "cute-baby-girl-names",
        "kind": "cute",
        "sex": "girl",
        "title": "Cute Baby Girl Names in Australia | Sweet Name Ideas",
        "heading": "Cute baby girl names",
        "intro": "Soft, friendly girl names, checked against the Australian rankings.",
        "description": "Browse cute baby girl names in Australia with current rankings, recent movement, meanings, origins and links to full name profiles.",
        "editorial_intro": "Cute girl names do not all sit in one style. Some are familiar names already near the top of the rankings, while others are softer nickname-style choices further down the list. This collection keeps the feeling gentle but still practical, showing current rank, recent movement and profile links beside each name.",
    },
    {
        "slug": "cute-baby-boy-names",
        "kind": "cute",
        "sex": "boy",
        "title": "Cute Baby Boy Names in Australia | Sweet Name Ideas",
        "heading": "Cute baby boy names",
        "intro": "Warm, easy-to-say boy names with current Australian ranking context.",
        "description": "Browse cute baby boy names in Australia with current rankings, recent movement, meanings, origins and links to full name profiles.",
        "editorial_intro": "Cute boy names often work because they feel approachable rather than formal. This list brings together shorter sounds, friendly endings and names that still have enough substance to grow with a child. Use the ranking details to see which choices are already common and which are quieter options.",
    },
    {
        "slug": "unique-baby-girl-names",
        "kind": "unique",
        "sex": "girl",
        "title": "Unique Baby Girl Names in Australia | Less Common Ideas",
        "heading": "Unique baby girl names",
        "intro": "Girl names that appear in the data without sitting right at the top.",
        "description": "Find unique baby girl names in Australia using real ranking data, with meanings, origins, movement and profile links.",
        "editorial_intro": "Unique does not have to mean unfamiliar. These girl names are still visible in the Australian data, but many sit outside the most crowded part of the rankings. That makes the page useful if you want something recognisable enough to compare, but not one of the obvious top-list choices.",
    },
    {
        "slug": "unique-baby-boy-names",
        "kind": "unique",
        "sex": "boy",
        "title": "Unique Baby Boy Names in Australia | Less Common Ideas",
        "heading": "Unique baby boy names",
        "intro": "Boy names with ranking history that feel less expected.",
        "description": "Find unique baby boy names in Australia using real ranking data, with meanings, origins, movement and profile links.",
        "editorial_intro": "This collection focuses on boy names that have enough Australian ranking history to be useful, but are not sitting among the most common current choices. It is a good place to look when you want something with a little more room around it, without guessing blindly.",
    },
    {
        "slug": "vintage-baby-girl-names",
        "kind": "vintage",
        "sex": "girl",
        "title": "Vintage Baby Girl Names in Australia | Classic Name Ideas",
        "heading": "Vintage baby girl names",
        "intro": "Older-style girl names, shown with their current Australian ranking story.",
        "description": "Explore vintage baby girl names in Australia with ranking history, meanings, origins and links to full profiles.",
        "editorial_intro": "Vintage girl names can feel familiar without feeling flat. This collection leans into names with an older or more established style, then shows how they are actually behaving in the Australian rankings now. Some are steady favourites; others are quieter names that may suit parents who like a more traditional sound.",
    },
    {
        "slug": "vintage-baby-boy-names",
        "kind": "vintage",
        "sex": "boy",
        "title": "Vintage Baby Boy Names in Australia | Classic Name Ideas",
        "heading": "Vintage baby boy names",
        "intro": "Older-style boy names with Australian popularity history beside them.",
        "description": "Explore vintage baby boy names in Australia with ranking history, meanings, origins and links to full profiles.",
        "editorial_intro": "Vintage boy names often have weight because they have been used across generations. This page keeps that older-name feel, but pairs it with the current ranking picture so you can see which names are still widely used and which ones feel more tucked away.",
    },
    {
        "slug": "short-baby-girl-names",
        "kind": "short",
        "sex": "girl",
        "title": "Short Baby Girl Names in Australia | 3 to 5 Letter Names",
        "heading": "Short baby girl names",
        "intro": "Three to five letter girl names with ranking history to compare.",
        "description": "Browse short baby girl names in Australia, including 3 to 5 letter names with rankings, movement, meanings and origins.",
        "editorial_intro": "Short girl names are easy to say and easy to remember, but they can still carry very different styles. This list keeps to three to five letters and adds the Australian ranking context beside each option, so a simple name can still be compared properly.",
    },
    {
        "slug": "short-baby-boy-names",
        "kind": "short",
        "sex": "boy",
        "title": "Short Baby Boy Names in Australia | 3 to 5 Letter Names",
        "heading": "Short baby boy names",
        "intro": "Three to five letter boy names with current popularity context.",
        "description": "Browse short baby boy names in Australia, including 3 to 5 letter names with rankings, movement, meanings and origins.",
        "editorial_intro": "Short boy names can feel strong, relaxed or nickname-like depending on the name. This collection keeps the list tight by length, then lets the ranking data do the useful work: current position, recent movement and links to the fuller name profile.",
    },
    {
        "slug": "nature-baby-girl-names",
        "kind": "nature",
        "sex": "girl",
        "title": "Nature Baby Girl Names in Australia | Floral and Earthy Ideas",
        "heading": "Nature baby girl names",
        "intro": "Nature-linked girl names, from familiar favourites to quieter choices.",
        "description": "Explore nature baby girl names in Australia with ranking data, meanings, origins and links to full baby-name profiles.",
        "editorial_intro": "Nature-inspired girl names in this collection range from familiar choices already near the top of the rankings to gentler options sitting further down the list. Where the meaning or origin notes support the theme, they are included; where they do not, the ranking story stays the focus.",
    },
    {
        "slug": "nature-baby-boy-names",
        "kind": "nature",
        "sex": "boy",
        "title": "Nature Baby Boy Names in Australia | Earthy Name Ideas",
        "heading": "Nature baby boy names",
        "intro": "Nature-linked boy names with Australian ranking history attached.",
        "description": "Explore nature baby boy names in Australia with ranking data, meanings, origins and links to full baby-name profiles.",
        "editorial_intro": "Nature boy names can be direct, surname-like or simply outdoorsy in feel. This page keeps the category grounded by showing names that appear in the Australian data, with meaning notes where available and ranking movement where the latest comparison tells a clear story.",
    },
    {
        "slug": "australian-girl-names",
        "kind": "australian",
        "sex": "girl",
        "title": "Australian Girl Names | Popular Names in Australia",
        "heading": "Australian girl names",
        "intro": "Girl names currently visible in Australian popularity data.",
        "description": "Browse Australian girl names using current popularity rankings, movement, meanings, origins and profile links.",
        "editorial_intro": "This page is about names used in Australia, not names claimed to originate here. It gathers girl names from the ranking data so parents can compare what is currently popular, what is moving and which profiles are worth opening for meaning and similar-name ideas.",
    },
    {
        "slug": "australian-boy-names",
        "kind": "australian",
        "sex": "boy",
        "title": "Australian Boy Names | Popular Names in Australia",
        "heading": "Australian boy names",
        "intro": "Boy names currently visible in Australian popularity data.",
        "description": "Browse Australian boy names using current popularity rankings, movement, meanings, origins and profile links.",
        "editorial_intro": "This is a locally focused list of boy names appearing in the Australian ranking data. It does not pretend the names were invented in Australia; it simply gives you a practical way to browse what Australian parents are actually using and compare the popularity story behind each name.",
    },
    {
        "slug": "rising-baby-girl-names",
        "kind": "rising",
        "sex": "girl",
        "title": "Rising Baby Girl Names in Australia | Names Moving Up",
        "heading": "Rising baby girl names",
        "intro": "Girl names with a clear upward move in the latest ranking comparison.",
        "description": "See rising baby girl names in Australia based on real ranking movement, with current ranks, meanings and profile links.",
        "editorial_intro": "A rising name is not just a name that feels fashionable. For this page, the movement comes from the ranking data itself: names that improved in the latest year-to-year comparison. Open the profiles to see whether the rise is part of a longer pattern or a newer jump.",
    },
    {
        "slug": "rising-baby-boy-names",
        "kind": "rising",
        "sex": "boy",
        "title": "Rising Baby Boy Names in Australia | Names Moving Up",
        "heading": "Rising baby boy names",
        "intro": "Boy names with a clear upward move in the latest ranking comparison.",
        "description": "See rising baby boy names in Australia based on real ranking movement, with current ranks, meanings and profile links.",
        "editorial_intro": "These boy names have climbed in the most recent ranking comparison available on the site. Some are already well known; others are still sitting lower in the Top 100. The point is to show movement clearly, so you can spot names gaining attention without relying on guesswork.",
    },
    {
        "slug": "uncommon-baby-girl-names",
        "kind": "uncommon",
        "sex": "girl",
        "title": "Uncommon Baby Girl Names in Australia | Ranked but Less Common",
        "heading": "Uncommon baby girl names",
        "intro": "Ranked girl names that sit below the most common current picks.",
        "description": "Browse uncommon baby girl names in Australia using ranking data, meanings, origins and full name profiles.",
        "editorial_intro": "Uncommon girl names here are not pulled from nowhere. They appear in the Australian ranking data, but currently sit away from the busiest part of the list. That makes them useful for parents who want something less common while still being able to check real popularity history.",
    },
    {
        "slug": "uncommon-baby-boy-names",
        "kind": "uncommon",
        "sex": "boy",
        "title": "Uncommon Baby Boy Names in Australia | Ranked but Less Common",
        "heading": "Uncommon baby boy names",
        "intro": "Ranked boy names that sit below the most common current picks.",
        "description": "Browse uncommon baby boy names in Australia using ranking data, meanings, origins and full name profiles.",
        "editorial_intro": "This list keeps to boy names with actual Australian ranking history, then focuses on choices sitting below the most obvious current favourites. It is built for browsing names that feel a little less expected while still giving you something factual to compare.",
    },
    {
        "slug": "baby-girl-names-outside-top-50",
        "kind": "outside_top_50",
        "sex": "girl",
        "title": "Baby Girl Names Outside the Top 50 in Australia",
        "heading": "Baby girl names outside the top 50",
        "intro": "Girl names still in the Top 100, but outside the current Top 50.",
        "description": "Find baby girl names outside the top 50 in Australia, with current rankings, movement, meanings and profile links.",
        "editorial_intro": "Names outside the Top 50 can be a useful middle ground: known enough to appear in the current Australian Top 100, but not among the most common choices. This page shows those girl names with their latest rank and recent movement so the list feels useful, not random.",
    },
    {
        "slug": "baby-boy-names-outside-top-50",
        "kind": "outside_top_50",
        "sex": "boy",
        "title": "Baby Boy Names Outside the Top 50 in Australia",
        "heading": "Baby boy names outside the top 50",
        "intro": "Boy names still in the Top 100, but outside the current Top 50.",
        "description": "Find baby boy names outside the top 50 in Australia, with current rankings, movement, meanings and profile links.",
        "editorial_intro": "This page is for boy names that are still visible in the current Australian Top 100, but sit below the Top 50. It is a practical place to browse names with enough usage to track, while avoiding the very front of the list.",
    },
    {
        "slug": "baby-names-with-beautiful-meanings",
        "kind": "beautiful_meaning",
        "sex": "all",
        "title": "Baby Names With Beautiful Meanings | Australia Rankings",
        "heading": "Baby names with beautiful meanings",
        "intro": "Names with meaning notes, paired with Australian ranking context.",
        "description": "Browse baby names with beautiful meanings, including Australian rankings, origins, movement and links to full name profiles.",
        "editorial_intro": "A good meaning can make a name feel more personal, but it should not have to stand alone. This collection only uses meaning notes available in the site metadata, then pairs them with Australian ranking context so you can weigh both the story of the name and how often it is being used.",
    },
    {
        "slug": "baby-name-nicknames-and-longer-forms",
        "kind": "nicknames",
        "sex": "all",
        "title": "Baby Name Nicknames and Longer Forms | Australia Rankings",
        "heading": "Baby name nicknames and longer forms",
        "intro": "Names with nickname, variant or longer-form notes where available.",
        "description": "Explore baby name nicknames and longer forms with Australian ranking data, meanings, origins and profile links.",
        "editorial_intro": "Some parents start with the nickname; others want the fuller version first. This page brings together names where the site has nickname, variant or longer-form notes, then keeps the Australian ranking data visible so each option can be compared beyond the sound of the name.",
    },
]


NATURE_TERMS = {
    "flower", "floral", "tree", "plant", "green", "bloom", "rose", "lily", "hazel", "ivy", "daisy",
    "olive", "willow", "violet", "river", "island", "lake", "sea", "sky", "stone", "gemstone", "earth",
    "lion", "bear", "wolf", "forest", "meadow",
}
NATURE_NAME_SEEDS = {
    "amber", "archer", "asha", "asher", "ashlee", "ashleigh", "ashley", "ashton", "aurora", "blake",
    "brodie", "chloe", "cleo", "daisy", "eve", "evelyn", "finn", "flynn", "gemma", "hazel", "hudson",
    "hunter", "isla", "ivy", "jade", "jasper", "kai", "kaia", "lachlan", "leo", "leon", "leonardo",
    "lily", "luna", "maeve", "malakai", "mia", "nova", "oakley", "olive", "oliver", "olivia",
    "parker", "phoebe", "river", "rose", "ruby", "sean", "skye", "summer", "violet", "willow",
}

VINTAGE_SEEDS = {
    "alice", "arthur", "charlotte", "edward", "florence", "harriet", "henry", "joseph", "matilda",
    "theodore", "victoria", "violet", "william", "eleanor", "elizabeth", "george", "alfred", "frankie",
    "archie", "alfie", "clara", "edie", "edith", "mabel", "maggie", "harvey", "hugo", "oscar", "leo",
}

BEAUTIFUL_MEANING_TERMS = {
    "joy", "grace", "favour", "favor", "love", "beloved", "gift", "blessing", "peace", "hope", "life",
    "wisdom", "noble", "light", "bright", "happy", "bloom", "green", "strength", "lion", "free",
}
LANDING_THEME_BY_KIND = {
    "cute": "soft",
    "short": "soft",
    "vintage": "vintage",
    "nature": "nature",
    "classic": "vintage",
    "rising": "data",
    "outside_top_50": "data",
    "australian": "data",
    "unique": "editorial",
    "uncommon": "editorial",
    "beautiful_meaning": "editorial",
    "nicknames": "editorial",
}


def landing_theme(definition: dict[str, str]) -> str:
    return LANDING_THEME_BY_KIND.get(definition["kind"], "editorial")


def rank_movement_text(previous: dict[str, str] | None, latest: dict[str, str] | None) -> str:
    if not previous or not latest:
        return ""
    change = int(previous["rank_int"]) - int(latest["rank_int"])
    if change > 0:
        return f"Up {change} {place_word(change)} from {previous['year']}"
    if change < 0:
        return f"Down {abs(change)} {place_word(change)} from {previous['year']}"
    return f"Held at {ordinal(latest['rank_int'])} from {previous['year']}"


def movement_delta(previous: dict[str, str] | None, latest: dict[str, str] | None) -> int:
    if not previous or not latest:
        return 0
    return int(previous["rank_int"]) - int(latest["rank_int"])


def landing_intro_copy(definition: dict[str, str], profiles: list[dict[str, object]]) -> str:
    editorial_intro = definition.get("editorial_intro", "").strip()
    if editorial_intro:
        return editorial_intro

    total = len(profiles)
    rising_count = sum(1 for profile in profiles if int(profile["recent_move"]) > 0)
    outside_top_50 = sum(1 for profile in profiles if int(profile["latest_rank"]) > 50)
    meaning_count = sum(
        1 for profile in profiles
        if isinstance(profile.get("meta"), dict)
        and profile["meta"].get("meaning")
        and "uncertain" not in profile["meta"]["meaning"].lower()
    )
    sex = definition["sex"]
    audience = "baby names" if sex == "all" else f"baby {sex_label(sex).lower()} names"
    return (
        f"This collection contains {total} {audience} selected from the Australian ranking data used by Baby Names Australia. "
        f"Each idea includes current popularity context where available, so the page works as more than a style list. "
        f"{rising_count} names here moved up in the most recent year-to-year comparison, {outside_top_50} currently sit outside the top 50, "
        f"and {meaning_count} have verified meaning notes. Open any name to see the full ranking history, meaning, origin and similar names."
    )


def landing_badges(profile: dict[str, object], definition: dict[str, str]) -> list[str]:
    badges: list[str] = []
    latest_rank = int(profile["latest_rank"])
    recent_move = int(profile["recent_move"])
    name = str(profile["name"])
    context = str(profile["context"])
    kind = definition["kind"]
    if recent_move > 0:
        badges.append("RISING")
    if latest_rank <= 20:
        badges.append("TOP 20")
    elif latest_rank <= 50:
        badges.append("TOP 50")
    else:
        badges.append("OUTSIDE TOP 50")
    if len(name) <= 5:
        badges.append(f"{len(name)} LETTERS")
    if kind == "nature" or any(term in context for term in NATURE_TERMS):
        badges.append("NATURE")
    if kind == "vintage" or "historic" in context or "traditional" in context:
        badges.append("VINTAGE")
    return badges[:3]


def sparkline_svg(profile: dict[str, object]) -> str:
    history = profile.get("history")
    if not isinstance(history, list) or len(history) < 2:
        return ""
    points = []
    width = 160
    height = 52
    pad = 7
    ranks = [int(row["rank_int"]) for row in history]
    min_rank = min(ranks)
    max_rank = max(ranks)
    spread = max(1, max_rank - min_rank)
    for index, row in enumerate(history):
        x = pad + (width - pad * 2) * (index / max(1, len(history) - 1))
        y = pad + (height - pad * 2) * ((int(row["rank_int"]) - min_rank) / spread)
        points.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    start_year = history[0]["year"]
    end_year = history[-1]["year"]
    return (
        '<svg class="mini-sparkline" viewBox="0 0 160 52" role="img" '
        f'aria-label="{esc(profile["name"])} ranking movement from {esc(start_year)} to {esc(end_year)}">'
        '<path class="spark-grid" d="M7 7H153M7 45H153" />'
        f'<polyline points="{line}" />'
        f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="3.5" />'
        '</svg>'
    )


def landing_profiles(
    rows: list[dict[str, str]],
    metadata: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, object]]:
    years = sorted({row["year"] for row in rows})
    latest_year = max(years)
    by_name_sex = sorted({(row["name"], row["sex"]) for row in rows}, key=lambda item: (item[1], item[0]))
    profiles: list[dict[str, object]] = []
    for name, sex in by_name_sex:
        history = rows_for_name(rows, name, sex)
        if not history:
            continue
        latest = history[-1]
        previous = history[-2] if len(history) > 1 else None
        first = history[0]
        best = min(history, key=lambda item: int(item["rank_int"]))
        meta = metadata_for_name(name, sex, metadata)
        trend_label, _ = movement_summary(history, len(years))
        style_tags = style_tags_for_name(name, sex, meta, history, trend_label)
        context = " ".join([
            name,
            meta.get("meaning", ""),
            meta.get("origin", ""),
            meta.get("language", ""),
            meta.get("notes", ""),
            " ".join(style_tags),
        ]).lower()
        recent_move = int(previous["rank_int"]) - int(latest["rank_int"]) if previous else 0
        overall_move = int(first["rank_int"]) - int(latest["rank_int"])
        profiles.append({
            "name": name,
            "sex": sex,
            "history": history,
            "latest": latest,
            "previous": previous,
            "first": first,
            "best": best,
            "meta": meta,
            "trend_label": trend_label,
            "style_tags": style_tags,
            "context": context,
            "latest_rank": int(latest["rank_int"]),
            "previous_rank": int(previous["rank_int"]) if previous else None,
            "best_rank": int(best["rank_int"]),
            "recent_move": recent_move,
            "overall_move": overall_move,
            "latest_year": latest_year,
        })
    return profiles


def landing_category_score(profile: dict[str, object], definition: dict[str, str]) -> int | None:
    sex = str(profile["sex"])
    if definition["sex"] != "all" and definition["sex"] != sex:
        return None
    kind = definition["kind"]
    name = str(profile["name"])
    key = name.lower()
    latest_rank = int(profile["latest_rank"])
    recent_move = int(profile["recent_move"])
    overall_move = int(profile["overall_move"])
    context = str(profile["context"])
    meta = profile["meta"]  # type: ignore[assignment]
    meaning = str(meta.get("meaning", "")) if isinstance(meta, dict) else ""
    nicknames = str(meta.get("nicknames", "")) if isinstance(meta, dict) else ""
    root_name = str(meta.get("root_name", "")) if isinstance(meta, dict) else ""
    variants = str(meta.get("variants", "")) if isinstance(meta, dict) else ""

    if kind == "short":
        if 3 <= len(name) <= 5:
            return (6 - len(name)) * 20 + max(0, 110 - latest_rank)
        return None
    if kind == "outside_top_50":
        if latest_rank > 50:
            return max(0, 110 - latest_rank) + max(0, recent_move) * 2
        return None
    if kind == "uncommon":
        if latest_rank >= 55:
            return latest_rank + max(0, overall_move)
        return None
    if kind == "unique":
        if latest_rank >= 35:
            bonus = 25 if meaning and "uncertain" not in meaning.lower() else 0
            return latest_rank + max(0, overall_move) + bonus
        return None
    if kind == "rising":
        if recent_move >= 8:
            return recent_move * 10 + max(0, 105 - latest_rank)
        return None
    if kind == "australian":
        return max(0, 130 - latest_rank) + (20 if latest_rank <= 20 else 0)
    if kind == "nature":
        if key in NATURE_NAME_SEEDS or any(term in context for term in NATURE_TERMS):
            return max(0, 110 - latest_rank) + (30 if meaning and "uncertain" not in meaning.lower() else 0)
        return None
    if kind == "vintage":
        if key in VINTAGE_SEEDS or "historic" in context or "traditional" in context or "classic" in context:
            listed = len(profile["history"]) if isinstance(profile["history"], list) else 0
            return listed * 8 + max(0, 110 - latest_rank)
        return None
    if kind == "cute":
        cute_shape = len(name) <= 6 or key.endswith(("ie", "y", "a", "o", "i"))
        if cute_shape:
            return max(0, 110 - latest_rank) + (20 if len(name) <= 5 else 0)
        return None
    if kind == "beautiful_meaning":
        if meaning and "uncertain" not in meaning.lower() and any(term in meaning.lower() for term in BEAUTIFUL_MEANING_TERMS):
            return max(0, 120 - latest_rank) + 40
        if meaning and "uncertain" not in meaning.lower():
            return max(0, 80 - latest_rank)
        return None
    if kind == "nicknames":
        if nicknames or (root_name and root_name.lower() != key) or variants:
            return max(0, 110 - latest_rank) + (25 if nicknames else 0) + (15 if root_name and root_name.lower() != key else 0)
        return None
    return None


def landing_reason(profile: dict[str, object], definition: dict[str, str]) -> str:
    name = str(profile["name"])
    kind = definition["kind"]
    latest = profile["latest"]
    previous = profile["previous"]
    meta = profile["meta"]  # type: ignore[assignment]
    meaning = str(meta.get("meaning", "")) if isinstance(meta, dict) else ""
    origin = str(meta.get("origin", "")) if isinstance(meta, dict) else ""
    movement = rank_movement_text(previous if isinstance(previous, dict) else None, latest if isinstance(latest, dict) else None)

    if kind == "short":
        return f"{name} keeps the sound compact at {len(name)} letters, with ranking history available if you want to compare it properly."
    if kind == "outside_top_50":
        return f"{name} still appears in the latest Top 100, but sits below the current Top 50."
    if kind in {"unique", "uncommon"}:
        return f"{name} is visible in the rankings without being one of the current front-of-list choices."
    if kind == "rising" and movement:
        return f"{name} has recent momentum in the data, moving {movement.lower()}."
    if kind == "australian":
        return f"{name} appears in the Australian ranking data, which makes it useful for a local popularity check."
    if kind == "nature":
        if meaning and "uncertain" not in meaning.lower():
            return f"The meaning note for {name} gives it a nature link: {phrase_list(meaning)}."
        return f"{name} has a nature-style feel in this shortlist, with ranking history included for context."
    if kind == "vintage":
        if origin:
            return f"{name} has an older-name feel, with origin notes linked to {origin}."
        return f"{name} brings a more established style to the Australian ranking list."
    if kind == "cute":
        return f"{name} has the lighter, friendly sound this shortlist is built around."
    if kind == "beautiful_meaning" and meaning:
        return f"The available meaning note for {name} is {phrase_list(meaning)}."
    if kind == "nicknames":
        nicknames = str(meta.get("nicknames", "")) if isinstance(meta, dict) else ""
        root_name = str(meta.get("root_name", "")) if isinstance(meta, dict) else ""
        if nicknames:
            return f"The notes for {name} include nickname options: {phrase_list(nicknames)}."
        if root_name and root_name.lower() != name.lower():
            return f"{name} links back to {root_name} in the available name notes."
    if isinstance(latest, dict):
        return f"{name} appears in the latest Australian data at {ordinal(latest['rank_int'])} in {latest['year']}."
    return f"{name} has enough ranking history to be useful in this collection."


def landing_stat_lines(profile: dict[str, object]) -> list[str]:
    latest = profile["latest"]
    previous = profile["previous"]
    meta = profile["meta"]  # type: ignore[assignment]
    lines: list[str] = []
    if isinstance(latest, dict):
        lines.append(f"Current rank: {ordinal(latest['rank_int'])} in {latest['year']}")
    if isinstance(previous, dict):
        lines.append(f"Previous rank: {ordinal(previous['rank_int'])} in {previous['year']}")
        movement = rank_movement_text(previous, latest if isinstance(latest, dict) else None)
        if movement:
            lines.append(f"Movement: {movement}")
    if isinstance(meta, dict) and meta.get("meaning") and "uncertain" not in meta["meaning"].lower():
        lines.append(f"Meaning: {phrase_list(meta['meaning'])}")
    if isinstance(meta, dict) and meta.get("origin"):
        lines.append(f"Origin: {meta['origin']}")
    return lines


def featured_movement_text(previous: dict[str, str] | None, latest: dict[str, str] | None) -> str:
    movement = movement_delta(previous, latest)
    if movement > 0:
        return f"+{movement} {place_word(movement)}"
    if movement < 0:
        return f"-{abs(movement)} {place_word(movement)}"
    return "Held steady"


def featured_support_copy(profile: dict[str, object], definition: dict[str, str]) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    latest = profile["latest"] if isinstance(profile["latest"], dict) else None
    previous = profile["previous"] if isinstance(profile["previous"], dict) else None
    movement = movement_delta(previous, latest)
    latest_rank = int(profile["latest_rank"])
    kind = definition["kind"]
    sex_text = sex_plural(sex)
    rank_band = "top 20" if latest_rank <= 20 else "top 50" if latest_rank <= 50 else "top 100"
    if movement > 0 and previous and latest:
        return (
            f"{name} is the clearest story in this list: it climbed from {ordinal(previous['rank_int'])} in {previous['year']} "
            f"to {ordinal(latest['rank_int'])} in {latest['year']}. Its current ranking sits inside the {sex_text} {rank_band}, "
            "so it is worth a closer look if you like names with momentum."
        )
    if kind in {"unique", "uncommon", "outside_top_50"} and latest:
        return (
            f"{name} gives this list a more distinctive option: its current rank is "
            f"{ordinal(latest['rank_int'])} in {latest['year']}, outside the most common top-name choices."
        )
    if latest:
        return (
            f"{name} anchors this collection with a current rank of {ordinal(latest['rank_int'])} "
            f"in {latest['year']} for {sex_text}. Open the profile for the full year-by-year view."
        )
    return f"{name} is a useful starting point for this collection, with Australian ranking history to compare."


def feature_reason_card(title: str, text: str) -> str:
    return (
        '<div class="feature-reason">'
        f'<strong>{esc(title)}</strong>'
        f'<p>{esc(text)}</p>'
        '</div>'
    )


def add_feature_reason(reasons: list[tuple[str, str]], title: str, text: str) -> None:
    if len(reasons) >= 3:
        return
    clean_title = title.strip()
    clean_text = text.strip()
    if not clean_title or not clean_text:
        return
    if any(existing_title == clean_title for existing_title, _ in reasons):
        return
    reasons.append((clean_title, clean_text))


def verified_meaning(meta: dict[str, str]) -> str:
    meaning = str(meta.get("meaning", "")).strip()
    if not meaning or "uncertain" in meaning.lower() or meaning.upper() == "N/A":
        return ""
    return meaning


def verified_origin(meta: dict[str, str]) -> str:
    origin = str(meta.get("origin", "") or meta.get("language", "")).strip()
    if not origin or origin.upper() == "N/A":
        return ""
    return origin


def trend_reason_text(profile: dict[str, object]) -> tuple[str, str]:
    name = str(profile["name"])
    trend_label = str(profile.get("trend_label", ""))
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    if trend_label == "recent rise" and previous and latest:
        return (
            "Recent rise",
            f"{name} moved from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.",
        )
    if trend_label == "recent fall" and previous and latest:
        return (
            "Recent fall",
            f"{name} slipped from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.",
        )
    if trend_label == "long-term rise" and first and latest:
        recent_context = f" Latest-year movement: {latest_year_movement_text([previous, latest])}." if previous else ""
        return (
            "Long-term rise",
            f"Across the available history, {name} is stronger than its first listed rank of {ordinal(first['rank_int'])} in {first['year']}.{recent_context}",
        )
    if trend_label == "long-term fall" and first and latest:
        recent_context = f" Latest-year movement: {latest_year_movement_text([previous, latest])}." if previous else ""
        return (
            "Long-term fall",
            f"{name} was higher earlier in the available data, so the profile gives useful historical context.{recent_context}",
        )
    if trend_label == "volatile":
        return (
            "Volatile history",
            f"{name} has moved around across the available ranking years rather than following a straight line.",
        )
    if trend_label == "steady":
        return (
            "Steady history",
            f"{name} has stayed in a relatively consistent ranking band across the available years.",
        )
    return (
        "Limited data",
        f"{name} has fewer ranking observations, so the most recent listed rank is the clearest signal.",
    )


def featured_why_items(
    profile: dict[str, object],
    definition: dict[str, str],
    collection: list[dict[str, object]],
) -> list[tuple[str, str]]:
    name = str(profile["name"])
    kind = definition["kind"]
    sex = str(profile["sex"])
    sex_text = sex_plural(sex)
    latest = profile["latest"] if isinstance(profile.get("latest"), dict) else None
    previous = profile["previous"] if isinstance(profile.get("previous"), dict) else None
    first = profile["first"] if isinstance(profile.get("first"), dict) else None
    best = profile["best"] if isinstance(profile.get("best"), dict) else None
    meta = profile["meta"] if isinstance(profile.get("meta"), dict) else {}
    meaning = verified_meaning(meta)
    origin = verified_origin(meta)
    latest_rank = int(profile["latest_rank"])
    recent_move = int(profile["recent_move"])
    overall_move = int(profile["overall_move"])
    history_years = len(profile["history"]) if isinstance(profile.get("history"), list) else 0
    reasons: list[tuple[str, str]] = []

    positive_recent = [item for item in collection if int(item["recent_move"]) > 0]
    biggest_recent = max(positive_recent, key=lambda item: (int(item["recent_move"]), -int(item["latest_rank"])), default=None)
    biggest_long = max(collection, key=lambda item: (int(item["overall_move"]), -int(item["latest_rank"])), default=None)
    highest_current = min(collection, key=lambda item: int(item["latest_rank"]), default=None)
    lowest_current = max(collection, key=lambda item: int(item["latest_rank"]), default=None)
    longest_history = max(collection, key=lambda item: len(item["history"]) if isinstance(item.get("history"), list) else 0, default=None)
    best_peak = min(collection, key=lambda item: int(item["best_rank"]), default=None)

    if kind == "rising":
        if biggest_recent is profile and recent_move > 0:
            add_feature_reason(reasons, "Biggest riser", f"{name} recorded the largest latest-year improvement among the names in this collection.")
        elif recent_move > 0 and previous and latest:
            add_feature_reason(reasons, "Recent rise", f"{name} improved from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.")
        if latest_rank <= 50:
            add_feature_reason(reasons, "Top 50", f"Its current ranking places it inside Australia's top 50 for {sex_text}.")
        if biggest_long is profile and overall_move > 0:
            add_feature_reason(reasons, "Strongest long-term rise", f"{name} has the strongest overall improvement in this collection across its available history.")

    elif kind == "nature":
        if meaning and any(term in meaning.lower() for term in NATURE_TERMS):
            add_feature_reason(reasons, "Nature meaning", f"The available name notes link {name} with {phrase_list(meaning)}.")
        elif origin:
            add_feature_reason(reasons, "Origin note", f"{name} has {origin} origin or language notes in the available name data.")
        if latest:
            add_feature_reason(reasons, "Current rank", f"{name} ranks {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")
        if recent_move:
            add_feature_reason(reasons, "Recent movement", rank_movement_sentence(name, previous, latest))

    elif kind in {"vintage", "classic"}:
        if longest_history is profile and history_years:
            add_feature_reason(reasons, "Long ranking history", f"{name} has one of the longest visible ranking histories in this collection, appearing across {history_years} listed years.")
        elif history_years >= 8:
            add_feature_reason(reasons, "Established choice", f"{name} appears across {history_years} listed years in the available ranking data.")
        if recent_move > 0 and previous and latest:
            add_feature_reason(reasons, "Comeback signal", f"{name} improved from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.")
        if best_peak is profile and best:
            add_feature_reason(reasons, "Best historical peak", f"Its best visible rank is {ordinal(best['rank_int'])} in {best['year']}, the strongest peak in this collection.")

    elif kind in {"unique", "uncommon"}:
        if latest_rank > 50:
            add_feature_reason(reasons, "Less common now", f"{name} currently sits outside Australia's top 50, away from the most common choices.")
        if lowest_current is profile:
            add_feature_reason(reasons, "Most distinctive pick", f"It is one of the lower-ranked names in this collection, which makes it a more distinctive shortlist option.")
        if meaning:
            add_feature_reason(reasons, "Meaning note", f"The available name notes list the meaning as {phrase_list(meaning)}.")

    elif kind == "outside_top_50":
        distance = max(1, latest_rank - 50)
        add_feature_reason(reasons, "Outside top 50", f"{name} is {distance} places beyond the current top 50 cutoff.")
        if lowest_current is profile:
            add_feature_reason(reasons, "Lower-ranked choice", f"It is one of the least common names highlighted on this page.")
        if recent_move:
            add_feature_reason(reasons, "Recent movement", rank_movement_sentence(name, previous, latest))

    elif kind == "cute":
        add_feature_reason(reasons, "Soft shortlist style", f"{name} has a friendly, easy-to-say shape that fits this cute-name collection.")
        if latest:
            add_feature_reason(reasons, "Current rank", f"The current rank is {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")
        if meaning:
            add_feature_reason(reasons, "Meaning note", f"The available name notes list the meaning as {phrase_list(meaning)}.")

    elif kind == "short":
        add_feature_reason(reasons, f"{len(name)} letters", f"{name} is compact, simple to spell and fits the short-name brief cleanly.")
        if latest:
            add_feature_reason(reasons, "Current rank", f"The current rank is {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")
        if recent_move:
            add_feature_reason(reasons, "Recent movement", rank_movement_sentence(name, previous, latest))

    elif kind == "beautiful_meaning":
        if meaning:
            add_feature_reason(reasons, "Meaning-led pick", f"{name} is featured because the available name notes list the meaning as {phrase_list(meaning)}.")
        if origin:
            add_feature_reason(reasons, "Origin note", f"The available name notes link {name} with {origin}.")
        if latest:
            add_feature_reason(reasons, "Popularity context", f"It also has ranking context: {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")

    elif kind == "nicknames":
        nicknames = str(meta.get("nicknames", "")).strip()
        root_name = str(meta.get("root_name", "")).strip()
        if nicknames:
            add_feature_reason(reasons, "Nickname options", f"The available name notes list nickname options: {phrase_list(nicknames)}.")
        if root_name and root_name.lower() != name.lower():
            add_feature_reason(reasons, "Longer form link", f"{name} links back to {root_name} in the available name notes.")
        if latest:
            add_feature_reason(reasons, "Current rank", f"The current rank is {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")

    else:
        if highest_current is profile:
            add_feature_reason(reasons, "Highest current rank", f"{name} is the highest-ranked name in this collection's current ranking data.")
        if latest:
            add_feature_reason(reasons, "Current rank", f"The current rank is {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")
        if recent_move:
            add_feature_reason(reasons, "Recent movement", rank_movement_sentence(name, previous, latest))

    trend_title, trend_text = trend_reason_text(profile)
    movement_reason_titles = {"Recent movement", "Comeback signal"}
    already_explains_recent_move = (
        trend_title in {"Recent rise", "Recent fall"}
        and any(title in movement_reason_titles for title, _ in reasons)
    )
    if not already_explains_recent_move:
        add_feature_reason(reasons, trend_title, trend_text)
    if first and latest and overall_move > 0:
        add_feature_reason(reasons, "Overall improvement", f"{name} has moved from {ordinal(first['rank_int'])} in {first['year']} to {ordinal(latest['rank_int'])} in {latest['year']}.")
    if latest:
        rank_title = "Top 20" if latest_rank <= 20 else "Top 50" if latest_rank <= 50 else "Top 100"
        add_feature_reason(reasons, rank_title, f"{name} is currently {ordinal(latest['rank_int'])} in {latest['year']} for {sex_text}.")
    if origin:
        add_feature_reason(reasons, "Origin note", f"The available name notes link {name} with {origin}.")
    if meaning:
        add_feature_reason(reasons, "Meaning note", f"The available name notes list the meaning as {phrase_list(meaning)}.")
    if history_years:
        add_feature_reason(reasons, "Ranking history", f"{name} appears across {history_years} listed years in the available Australian data.")

    return reasons[:3]


def rank_movement_sentence(name: str, previous: dict[str, str] | None, latest: dict[str, str] | None) -> str:
    movement = movement_delta(previous, latest)
    if not previous or not latest:
        return f"{name} has limited year-to-year movement data."
    if movement > 0:
        return f"{name} improved from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}."
    if movement < 0:
        return f"{name} moved from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}."
    return f"{name} held the same rank in the latest year-to-year comparison."


def featured_why_panel(
    profile: dict[str, object],
    definition: dict[str, str],
    collection: list[dict[str, object]],
) -> str:
    name = str(profile["name"])
    reasons = featured_why_items(profile, definition, collection)
    cards = "".join(feature_reason_card(title, text) for title, text in reasons)
    return (
        '<aside class="landing-feature-why">'
        f'<h5>Why {esc(name)} stands out</h5>'
        f'<div class="feature-reason-list">{cards}</div>'
        '</aside>'
    )


def landing_feature_card(
    profile: dict[str, object],
    definition: dict[str, str],
    collection: list[dict[str, object]] | None = None,
) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    latest = profile["latest"] if isinstance(profile["latest"], dict) else None
    previous = profile["previous"] if isinstance(profile["previous"], dict) else None
    badges = "".join(f"<span>{esc(badge)}</span>" for badge in landing_badges(profile, definition))
    latest_text = f"{ordinal(latest['rank_int'])} in {latest['year']}" if latest else "Ranking profile"
    previous_text = f"{ordinal(previous['rank_int'])} in {previous['year']}" if previous else "N/A"
    movement_text = featured_movement_text(previous, latest)
    why_panel = featured_why_panel(profile, definition, collection or [profile])
    return (
        '<article class="landing-feature-card">'
        '<div class="landing-feature-copy">'
        f'<p class="feature-kicker">Featured {esc(sex_label(sex).lower())} name</p>'
        f'<h4><a href="./names/{sex_plural(sex)}/{slugify(name)}.html">{esc(name)}</a></h4>'
        f'<div class="landing-badges">{badges}</div>'
        '<div class="feature-stat-grid">'
        f'<div><span>Now</span><b>{esc(latest_text)}</b></div>'
        f'<div><span>Was</span><b>{esc(previous_text)}</b></div>'
        f'<div class="feature-stat-highlight"><span>Change</span><b>{esc(movement_text)}</b></div>'
        '</div>'
        f'<p>{esc(featured_support_copy(profile, definition))}</p>'
        f'<a class="feature-profile-link" href="./names/{sex_plural(sex)}/{slugify(name)}.html">View {esc(name)} popularity history</a>'
        '</div>'
        f'{why_panel}'
        '</article>'
    )


def landing_name_card(profile: dict[str, object], definition: dict[str, str], featured: bool = False) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    latest = profile["latest"] if isinstance(profile["latest"], dict) else None
    previous = profile["previous"] if isinstance(profile["previous"], dict) else None
    meta = profile["meta"] if isinstance(profile["meta"], dict) else {}
    meaning = meta.get("meaning", "")
    origin = meta.get("origin", "") or meta.get("language", "")
    movement = movement_delta(previous, latest)
    badges = "".join(f"<span>{esc(badge)}</span>" for badge in landing_badges(profile, definition))
    movement_label = "No recent change"
    if movement > 0:
        movement_label = f"Up {movement}"
    elif movement < 0:
        movement_label = f"Down {abs(movement)}"
    meaning_line = ""
    if meaning and "uncertain" not in meaning.lower():
        meaning_line = f'<p class="landing-meaning">{esc(phrase_list(meaning))}</p>'
    elif origin:
        meaning_line = f'<p class="landing-meaning">{esc(origin)}</p>'
    sparkline = sparkline_svg(profile) if featured or definition["kind"] in {"rising", "outside_top_50", "australian"} else ""
    article_class = "landing-name-card is-featured" if featured else "landing-name-card"
    latest_text = f"{ordinal(latest['rank_int'])} in {latest['year']}" if latest else "Ranking profile"
    previous_text = f"{ordinal(previous['rank_int'])} in {previous['year']}" if previous else "N/A"
    return (
        f'<article class="{article_class}">'
        f'<div class="landing-card-top"><span>{esc(sex_label(sex))}</span><a href="./names/{sex_plural(sex)}/{slugify(name)}.html">{esc(name)}</a></div>'
        f'<div class="landing-badges">{badges}</div>'
        f"{meaning_line}"
        '<div class="landing-rank-strip">'
        f'<div><span>Latest</span><b>{esc(latest_text)}</b></div>'
        f'<div><span>Previous</span><b>{esc(previous_text)}</b></div>'
        f'<div><span>Movement</span><b>{esc(movement_label)}</b></div>'
        '</div>'
        f"{sparkline}"
        f'<p>{esc(landing_reason(profile, definition))}</p>'
        f'<a class="text-link" href="./names/{sex_plural(sex)}/{slugify(name)}.html">View {esc(name)} popularity history</a>'
        "</article>"
    )


def landing_name_cards(
    profiles: list[dict[str, object]],
    definition: dict[str, str],
    featured: bool = False,
    collection: list[dict[str, object]] | None = None,
) -> str:
    cards = []
    for profile in profiles:
        if featured:
            cards.append(landing_feature_card(profile, definition, collection or profiles))
        else:
            cards.append(landing_name_card(profile, definition, featured))
    grid_class = "landing-feature-grid" if featured else "landing-name-grid"
    return f'<div class="{grid_class}">{"".join(cards)}</div>'


def landing_section_bucket(profile: dict[str, object], definition: dict[str, str]) -> str:
    kind = definition["kind"]
    latest_rank = int(profile["latest_rank"])
    recent_move = int(profile["recent_move"])
    overall_move = int(profile["overall_move"])
    name = str(profile["name"])
    context = str(profile["context"])
    if kind == "rising":
        if recent_move >= 10:
            return "Fastest risers"
        if latest_rank <= 50:
            return "Approaching the top 50"
        return "More names gaining momentum"
    if kind in {"unique", "uncommon"}:
        if latest_rank > 75:
            return "Hidden gems"
        if recent_move > 0:
            return "Rising choices"
        return "Familiar but less common"
    if kind == "outside_top_50":
        if recent_move > 0:
            return "Outside the top 50 and rising"
        if latest_rank > 75:
            return "Lower-ranked choices"
        return "Names just beyond the top 50"
    if kind == "vintage":
        if recent_move > 0:
            return "Vintage names making a comeback"
        if latest_rank <= 30:
            return "Timeless favourites"
        return "Less common vintage choices"
    if kind == "cute":
        if recent_move > 0:
            return "Cute names currently rising"
        if len(name) <= 5:
            return "Short and sweet"
        if "historic" in context or "traditional" in context:
            return "Cute vintage choices"
        return "Familiar but less common"
    if kind == "short":
        if len(name) <= 4:
            return "Tiny names with big style"
        if recent_move > 0:
            return "Short names moving up"
        return "More short favourites"
    if kind == "nature":
        if recent_move > 0:
            return "Nature names with momentum"
        if latest_rank <= 50:
            return "Popular nature-style names"
        return "Earthy names outside the top 50"
    if kind == "australian":
        if latest_rank <= 20:
            return "Current Australian favourites"
        if recent_move > 0:
            return "Names moving up locally"
        return "More names used in Australia"
    if kind == "beautiful_meaning":
        if "grace" in context or "joy" in context or "blessing" in context or "gift" in context:
            return "Gentle meanings"
        if "noble" in context or "strength" in context or "lion" in context:
            return "Strong meanings"
        return "More meaningful names"
    if kind == "nicknames":
        meta = profile["meta"] if isinstance(profile["meta"], dict) else {}
        if meta.get("nicknames"):
            return "Names with nickname options"
        if meta.get("root_name") and str(meta["root_name"]).lower() != name.lower():
            return "Short forms and longer forms"
        return "Name families to explore"
    return "More name ideas"


def landing_insight(profile_list: list[dict[str, object]]) -> str:
    rising = [profile for profile in profile_list if int(profile["recent_move"]) > 0]
    outside = [profile for profile in profile_list if int(profile["latest_rank"]) > 50]
    strongest = max(profile_list, key=lambda profile: int(profile["recent_move"])) if profile_list else None
    parts = []
    if rising:
        parts.append(f"{len(rising)} names in this collection rose in the latest year-to-year comparison.")
    if outside:
        parts.append(f"{len(outside)} names currently sit outside Australia's top 50.")
    if strongest and int(strongest["recent_move"]) > 0:
        movement = int(strongest["recent_move"])
        parts.append(f"The strongest recent mover here is {strongest['name']}, up {movement} {place_word(movement)}.")
    if not parts:
        parts.append("This collection is selected from names with available Australian ranking history.")
    return " ".join(parts)


def featured_landing_profile(profiles: list[dict[str, object]]) -> dict[str, object] | None:
    if not profiles:
        return None
    rising = [profile for profile in profiles if int(profile["recent_move"]) > 0]
    if rising:
        return max(rising, key=lambda profile: (int(profile["recent_move"]), -int(profile["latest_rank"])))
    return profiles[0]


def featured_landing_insight(profile: dict[str, object], definition: dict[str, str]) -> str:
    name = str(profile["name"])
    sex = str(profile["sex"])
    latest = profile["latest"] if isinstance(profile["latest"], dict) else None
    previous = profile["previous"] if isinstance(profile["previous"], dict) else None
    movement = movement_delta(previous, latest)
    latest_text = f"its current rank is {ordinal(latest['rank_int'])} in {latest['year']}" if latest else "has available Australian ranking history"
    sex_text = sex_plural(sex)
    if movement > 0 and previous and latest:
        return (
            f"Spotlight pick: {name} made the sharpest move in this collection, rising {movement} {place_word(movement)} "
            f"from {ordinal(previous['rank_int'])} in {previous['year']} to {ordinal(latest['rank_int'])} in {latest['year']}."
        )
    if movement < 0 and previous and latest:
        return (
            f"Spotlight pick: {name} gives this collection useful ranking context, with {latest_text} for {sex_text} "
            f"after moving from {ordinal(previous['rank_int'])} in {previous['year']}."
        )
    return f"Spotlight pick: {name} gives this collection a clear starting point, with {latest_text} for {sex_text}."


def landing_sections(profiles: list[dict[str, object]], definition: dict[str, str]) -> str:
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for profile in profiles:
        buckets[landing_section_bucket(profile, definition)].append(profile)
    sections = []
    for title, items in buckets.items():
        if not items:
            continue
        visible_items = items[:12]
        sections.append(
            '<section class="landing-subsection">'
            f'<header class="discovery-section-header"><h3>{esc(title)}</h3><p>{esc(landing_insight(visible_items))}</p></header>'
            f'{landing_name_cards(visible_items, definition)}'
            '</section>'
        )
        if len(sections) >= 4:
            break
    return "\n".join(sections)


def related_landing_links(definition: dict[str, str]) -> str:
    sex = definition["sex"]
    current = definition["slug"]
    candidates = []
    for item in LANDING_PAGE_DEFINITIONS:
        if item["slug"] == current:
            continue
        if sex == "all" or item["sex"] == sex or item["sex"] == "all":
            candidates.append(item)
    priority = ["unique", "cute", "short", "vintage", "rising", "outside_top_50", "uncommon", "australian", "beautiful_meaning", "nicknames"]
    candidates.sort(key=lambda item: (priority.index(item["kind"]) if item["kind"] in priority else 99, item["heading"]))
    links = [f'<a href="./{esc(item["slug"])}.html">{esc(item["heading"].capitalize())}</a>' for item in candidates[:6]]
    if sex in {"girl", "boy"}:
        links.append(f'<a href="./rankings/top-{sex_plural(sex)}-2025.html">Top {sex_plural(sex)} 2025</a>')
    else:
        links.append('<a href="./rankings/top-girls-2025.html">Top girls 2025</a>')
        links.append('<a href="./rankings/top-boys-2025.html">Top boys 2025</a>')
    links.append('<a href="./#name-explorer">Baby name popularity checker</a>')
    return "\n".join(links)


def related_landing_tiles(definition: dict[str, str]) -> str:
    sex = definition["sex"]
    current = definition["slug"]
    candidates = []
    for item in LANDING_PAGE_DEFINITIONS:
        if item["slug"] == current:
            continue
        if sex == "all" or item["sex"] == sex or item["sex"] == "all":
            candidates.append(item)
    priority = ["cute", "unique", "vintage", "short", "nature", "rising", "outside_top_50", "uncommon", "beautiful_meaning", "nicknames", "australian"]
    candidates.sort(key=lambda item: (priority.index(item["kind"]) if item["kind"] in priority else 99, item["heading"]))
    cards = []
    for item in candidates[:6]:
        cards.append(
            f'<a class="explore-tile landing-theme-{esc(landing_theme(item))}" href="./{esc(item["slug"])}.html">'
            f'<span>{esc(item["kind"].replace("_", " "))}</span>'
            f'<b>{esc(item["heading"].capitalize())}</b>'
            f'<em>{esc(item["intro"])}</em>'
            '</a>'
        )
    return f'<div class="explore-tile-grid">{"".join(cards)}</div>'


def landing_schema_json(definition: dict[str, str], canonical: str, profiles: list[dict[str, object]]) -> str:
    items = [(str(profile["name"]), name_page_url(str(profile["name"]), str(profile["sex"]))) for profile in profiles[:40]]
    return discovery_schema_json(definition["title"], canonical, definition["description"], items)


def landing_page_html(definition: dict[str, str], profiles: list[dict[str, object]]) -> str:
    canonical = f"{BASE_URL}/{definition['slug']}.html"
    featured_profile = featured_landing_profile(profiles)
    featured = [featured_profile] if featured_profile else []
    remaining = [profile for profile in profiles if profile is not featured_profile]
    related = related_landing_tiles(definition)
    top_girls = "./rankings/top-girls-2025.html"
    top_boys = "./rankings/top-boys-2025.html"
    theme = landing_theme(definition)
    head_html = shared_head_html(
        definition["title"],
        definition["description"],
        canonical,
        "./styles.css",
        "./assets/favicon.ico",
        "./assets/favicon-32x32.png",
        "./assets/apple-touch-icon.png",
        landing_schema_json(definition, canonical, profiles),
    )
    return f"""<!doctype html>
<html lang="en">
  {head_html}
  <body class="profile-pilot-page directive-page discovery-page landing-page landing-theme-{esc(theme)}">
{pilot_topbar("./")}
    <header id="header">
      <span class="logo" aria-hidden="true">A</span>
      <h1>{esc(definition["heading"])}</h1>
      <p>{esc(definition["intro"])}</p>
      <div class="header-actions">
        <a class="button" href="./#name-explorer">Search baby names</a>
        <a class="button alt" href="./#top-rankings">Browse rankings</a>
      </div>
    </header>

    <main id="main">
      <header class="major container landing-intro">
        <h2>{esc(definition["heading"])}</h2>
        <p>{esc(landing_intro_copy(definition, profiles))}</p>
      </header>

      <section class="box container landing-list">
        <header class="discovery-section-header">
          <h3>Featured name</h3>
          <p>{esc(featured_landing_insight(featured_profile, definition)) if featured_profile else esc(landing_insight(profiles))}</p>
        </header>
        {landing_name_cards(featured, definition, featured=True, collection=profiles)}
      </section>

      <section class="box container landing-list">
        {landing_sections(remaining, definition)}
      </section>

      <section class="box container landing-list">
        <header class="discovery-section-header">
          <h3>Related baby name lists</h3>
          <p>Keep browsing by style, popularity or current Australian ranking lists.</p>
        </header>
        {related}
      </section>

      <footer class="major container medium">
        <h2>Compare the rankings</h2>
        <div class="seo-links">
          <a href="{top_girls}">Top girls 2025</a>
          <a href="{top_boys}">Top boys 2025</a>
          <a href="./baby-name-popularity-checker-australia.html">Baby name popularity checker</a>
        </div>
      </footer>
    </main>

    <footer id="site-footer">
      <div class="container medium">
        <h2>Find the name that fits</h2>
        <p>Search meanings, origins, ranking history and similar names in the Australian baby-name explorer.</p>
      </div>
    </footer>
{pilot_favourites_script("./")}
  </body>
</html>
"""


def select_landing_profiles(profiles: list[dict[str, object]], definition: dict[str, str]) -> list[dict[str, object]]:
    scored: list[tuple[int, dict[str, object]]] = []
    for profile in profiles:
        score = landing_category_score(profile, definition)
        if score is not None:
            scored.append((score, profile))
    scored.sort(key=lambda item: (-item[0], int(item[1]["latest_rank"]), str(item[1]["name"])))
    limit = 40 if len(scored) >= 40 else len(scored)
    if limit >= 20:
        limit = min(40, limit)
    return [profile for _, profile in scored[:limit]]


def generate_landing_pages(
    rows: list[dict[str, str]],
    sitemap_urls: list[str],
    metadata: dict[tuple[str, str], dict[str, str]],
) -> None:
    profiles = landing_profiles(rows, metadata)
    for definition in LANDING_PAGE_DEFINITIONS:
        selected = select_landing_profiles(profiles, definition)
        if not selected:
            continue
        path = ROOT / f"{definition['slug']}.html"
        write_if_changed(path, landing_page_html(definition, selected))
        sitemap_urls.append(f"{BASE_URL}/{definition['slug']}.html")


def generate_discovery_pages(
    rows: list[dict[str, str]],
    sitemap_urls: list[str],
    metadata: dict[tuple[str, str], dict[str, str]],
) -> None:
    years = sorted({row["year"] for row in rows})
    latest_year = max(years)
    by_name_sex = sorted({(row["name"], row["sex"]) for row in rows}, key=lambda item: (item[1], item[0]))
    histories = {
        (name.lower(), sex): rows_for_name(rows, name, sex)
        for name, sex in by_name_sex
    }

    for sex in ["girl", "boy"]:
        all_items = []
        for name, item_sex in by_name_sex:
            if item_sex != sex:
                continue
            history = histories[(name.lower(), sex)]
            latest = history[-1] if history else None
            best = min(history, key=lambda item: int(item["rank_int"])) if history else None
            meta_text = f"Latest {ordinal(latest['rank_int'])} in {latest['year']}" if latest else "Ranking profile"
            if best:
                meta_text += f" · Best {ordinal(best['rank_int'])}"
            all_items.append({"name": name, "sex": sex, "label": sex_label(sex), "meta": meta_text})
        canonical = f"{BASE_URL}/names/{sex_plural(sex)}/"
        title = f"Baby {sex_label(sex)} Names in Australia | Meanings & Popularity"
        description = f"Browse Australian baby {sex_label(sex).lower()} names with meaning, origin, similar names and yearly popularity rankings."
        path = NAMES_DIR / sex_plural(sex) / "index.html"
        write_if_changed(
            path,
            discovery_page_html(
                title,
                description,
                canonical,
                f"Baby {sex_label(sex).lower()} names",
                f"Browse Australian baby {sex_label(sex).lower()} names and open any profile.",
                discovery_cards(all_items, "../.."),
                discovery_schema_json(title, canonical, description, [(item["name"], name_page_url(item["name"], sex)) for item in all_items]),
                depth="../..",
                theme="soft",
            ),
        )
        sitemap_urls.append(canonical)

        latest_rows = rows_for_year_sex(rows, latest_year, sex)[:100]
        popular_items = [
            {
                "name": row["name"],
                "sex": sex,
                "label": ordinal(row["rank_int"]),
                "meta": f"Top {sex_label(sex).lower()} name in {latest_year}",
            }
            for row in latest_rows
        ]
        popular_path = ROOT / f"popular-baby-{sex_label(sex).lower()}-names-australia.html"
        popular_url = f"{BASE_URL}/popular-baby-{sex_label(sex).lower()}-names-australia.html"
        popular_title = f"Popular Baby {sex_label(sex)} Names in Australia {latest_year}"
        popular_description = f"Explore popular baby {sex_label(sex).lower()} names in Australia for {latest_year}, with links to meanings, origins and ranking histories."
        write_if_changed(
            popular_path,
            discovery_page_html(
                popular_title,
                popular_description,
                popular_url,
                f"Popular baby {sex_label(sex).lower()} names",
                f"The current top baby {sex_label(sex).lower()} names in Australia.",
                discovery_cards(popular_items),
                discovery_schema_json(popular_title, popular_url, popular_description, [(item["name"], name_page_url(item["name"], sex)) for item in popular_items]),
                theme="data",
            ),
        )
        sitemap_urls.append(popular_url)

    all_profiles = []
    for name, sex in by_name_sex:
        history = histories[(name.lower(), sex)]
        if not history:
            continue
        latest = history[-1]
        best = min(history, key=lambda item: int(item["rank_int"]))
        meta = metadata_for_name(name, sex, metadata)
        trend_label, _ = movement_summary(history, len(years))
        style_tags = style_tags_for_name(name, sex, meta, history, trend_label)
        all_profiles.append({
            "name": name,
            "sex": sex,
            "latest_rank": int(latest["rank_int"]),
            "best_rank": int(best["rank_int"]),
            "listed": len(history),
            "style_tags": style_tags,
        })
    rich_profiles = landing_profiles(rows, metadata)

    unique_profiles = [
        {
            "name": item["name"],
            "sex": item["sex"],
            "label": sex_label(item["sex"]),
            "meta": f"Less common · Latest {ordinal(item['latest_rank'])}",
        }
        for item in sorted(all_profiles, key=lambda item: (-item["latest_rank"], item["name"]))[:80]
    ]
    unique_url = f"{BASE_URL}/unique-australian-baby-names.html"
    unique_title = "Unique Australian Baby Names | Less Common Name Ideas"
    unique_description = "Browse less common Australian baby names from the top 100 data, with links to meanings, origins and popularity history."
    write_if_changed(
        ROOT / "unique-australian-baby-names.html",
        landing_page_html(
            {
                "slug": "unique-australian-baby-names",
                "kind": "unique",
                "sex": "all",
                "title": unique_title,
                "heading": "Unique Australian baby names",
                "intro": "Less common names that still appear in the Australian ranking data.",
                "description": unique_description,
                "editorial_intro": "This page is for names that have ranking history in Australia but are not sitting at the very front of the current lists. It is a practical way to browse less common ideas without losing the ability to check rank, movement, meaning notes and a full profile.",
            },
            sorted(rich_profiles, key=lambda item: (-int(item["latest_rank"]), item["name"]))[:48],
        ),
    )
    sitemap_urls.append(unique_url)

    classic_profiles = [
        {
            "name": item["name"],
            "sex": item["sex"],
            "label": sex_label(item["sex"]),
            "meta": f"Listed {item['listed']} years · Best {ordinal(item['best_rank'])}",
        }
        for item in sorted(all_profiles, key=lambda item: (-item["listed"], item["best_rank"], item["name"]))
        if item["listed"] >= max(8, len(years) - 2) or "historic" in item["style_tags"]
    ][:80]
    classic_url = f"{BASE_URL}/classic-baby-names.html"
    classic_title = "Classic Baby Names in Australia | Timeless Name Ideas"
    classic_description = "Explore classic baby names in Australia with long-running ranking history, meanings, origins and similar name ideas."
    write_if_changed(
        ROOT / "classic-baby-names.html",
        landing_page_html(
            {
                "slug": "classic-baby-names",
                "kind": "classic",
                "sex": "all",
                "title": classic_title,
                "heading": "Classic baby names",
                "intro": "Long-running names with an established feel in Australian ranking history.",
                "description": classic_description,
                "editorial_intro": "Classic names tend to earn that label through use over time. This collection favours names with longer Australian ranking histories or an established style, then shows their current rank and movement so the page feels useful for today rather than just nostalgic.",
            },
            [
                profile
                for profile in sorted(rich_profiles, key=lambda item: (-len(item["history"]), int(item["best_rank"]), item["name"]))
                if len(profile["history"]) >= max(8, len(years) - 2)
                or "historic" in str(profile["context"])
                or "traditional" in str(profile["context"])
            ][:48],
        ),
    )
    sitemap_urls.append(classic_url)


def generate_2026_watchlist_page(rows: list[dict[str, str]], sitemap_urls: list[str]) -> None:
    years = sorted({row["year"] for row in rows})
    latest_year = max(years)
    recent_years = years[-3:]
    latest_label = latest_year

    current_items = []
    for sex in ["girl", "boy"]:
        for row in rows_for_year_sex(rows, latest_year, sex)[:20]:
            current_items.append(
                {
                    "name": row["name"],
                    "sex": sex,
                    "label": f"{ordinal(row['rank_int'])} {sex_label(sex)}",
                    "meta": f"Current leader from the latest public {latest_label} list",
                }
            )

    momentum_items = []
    for sex in ["girl", "boy"]:
        latest_rows = rows_for_year_sex(rows, latest_year, sex)
        for row in latest_rows:
            history = rows_for_name(rows, row["name"], sex)
            recent_history = [item for item in history if item["year"] in recent_years]
            if len(recent_history) < 2:
                continue
            first = recent_history[0]
            latest = recent_history[-1]
            movement = int(first["rank_int"]) - int(latest["rank_int"])
            if movement <= 0:
                continue
            momentum_items.append(
                {
                    "name": row["name"],
                    "sex": sex,
                    "label": f"Up {movement}",
                    "meta": f"{sex_label(sex)} name moving from {ordinal(first['rank_int'])} to {ordinal(latest['rank_int'])}",
                    "movement": movement,
                    "rank": int(latest["rank_int"]),
                }
            )

    momentum_items = sorted(
        momentum_items,
        key=lambda item: (-int(item["movement"]), int(item["rank"]), item["name"]),
    )[:40]

    all_items = current_items + momentum_items
    canonical = f"{BASE_URL}/baby-names-2026-watchlist.html"
    title = "Australian Baby Names 2026 Watchlist | Trends to Watch"
    description = (
        "A 2026 baby-name watchlist for Australia using the latest public 2025 rankings "
        "and recent popularity movement. Not final 2026 birth-registration data."
    )
    note = (
        "Official 2026 Australian baby-name rankings are not public yet. "
        "This watchlist keeps 2026 separate from the real ranking charts and uses the latest "
        "public rankings plus recent movement to show names worth watching."
    )
    cards_html = f"""
        <div class="watchlist-note">
          <strong>Not final 2026 rankings.</strong>
          <span>{esc(note)}</span>
        </div>
        <header class="discovery-section-header">
          <h3>Current leaders from {esc(latest_label)}</h3>
          <p>The strongest names in the latest public ranking data.</p>
        </header>
        {discovery_cards(current_items)}
        <header class="discovery-section-header">
          <h3>Names with recent momentum</h3>
          <p>Names climbing across the most recent public years.</p>
        </header>
        {discovery_cards(momentum_items)}
    """
    write_if_changed(
        ROOT / "baby-names-2026-watchlist.html",
        discovery_page_html(
            title,
            description,
            canonical,
            "Australian baby names 2026 watchlist",
            "Names to watch while official 2026 ranking data is not yet public.",
            cards_html,
            discovery_schema_json(title, canonical, description, [(item["name"], name_page_url(item["name"], item["sex"])) for item in all_items]),
            theme="data",
        ),
    )
    sitemap_urls.append(canonical)


def generate_data_sources(sitemap_urls: list[str]) -> None:
    url = f"{BASE_URL}/data-sources.html"
    content = f"""<!doctype html>
<html lang="en">
  <head>
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-7E2KMVP098"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());

      gtag('config', 'G-7E2KMVP098');
    </script>

{PINTEREST_TAG}
{ADSENSE_TAG}
{PINTEREST_VERIFY_META}    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Australian Baby Name Data Sources</title>
    <meta name="description" content="Learn what Australian baby-name ranking data this site uses, including years covered and missing data notes." />
    <meta name="robots" content="index, follow" />
    <meta name="theme-color" content="#4eb980" />
    <link rel="canonical" href="{url}" />
    <link rel="icon" href="./assets/favicon.ico" sizes="any" />
    <link rel="icon" type="image/png" sizes="32x32" href="./assets/favicon-32x32.png" />
    <link rel="apple-touch-icon" href="./assets/apple-touch-icon.png" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="Australian Baby Name Data Sources" />
    <meta property="og:description" content="Learn what Australian baby-name ranking data this site uses." />
    <meta property="og:url" content="{url}" />
    <meta property="og:site_name" content="Australian Baby Name Rankings" />
    <meta property="og:image" content="https://www.babynamesaustralia.com/assets/social-preview.png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="Australian Baby Names search and ranking explorer" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="Australian Baby Name Data Sources" />
    <meta name="twitter:description" content="Learn what Australian baby-name ranking data this site uses." />
    <meta name="twitter:image" content="https://www.babynamesaustralia.com/assets/social-preview.png" />
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body class="profile-pilot-page directive-page sources-page">
{pilot_topbar("./")}
    <header id="header">
      <span class="logo" aria-hidden="true">A</span>
      <h1>Data sources</h1>
      <p>How the Australian baby-name rankings are put together.</p>
      <div class="header-actions">
        <a class="button" href="./">Back to explorer</a>
        <a class="button alt" href="./rankings/top-girls-2025.html">Top girls 2025</a>
      </div>
    </header>

    <main id="main">
      <header class="major container medium">
        <h2>Australian baby name data sources</h2>
        <p>The app uses public Australia-wide baby-name ranking data and applies a consistent source priority when sources overlap.</p>
      </header>

      <section class="box container">
        <header>
          <h2>Coverage notes</h2>
          <p>What the data means</p>
        </header>
        <p>Rankings are based on available Australian baby-name data. Where multiple sources cover the same year and gender, official or reported national ranking rows are preferred first, calculated Australia-wide totals are used next, and broader public lists are used only as fallback or to fill names beyond the higher-priority source cut-off.</p>
        <p>If a name is missing from a year, it may mean the name was outside the published list, not that it had zero births.</p>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr><th>Years covered</th><td>2008-2025 from the public ranking rows currently available to the site.</td></tr>
              <tr><th>Gender coverage</th><td>Boys and girls.</td></tr>
              <tr><th>List type</th><td>Mostly published top-100 rankings. The public pages focus on rank order because birth counts are not consistently available across sources.</td></tr>
              <tr><th>Overlap handling</th><td>When sources disagree for the same name, year and gender, the higher-priority source is shown so name pages and ranking pages stay consistent.</td></tr>
              <tr><th>Meaning and origin metadata</th><td>Stored separately in data/clean/name_metadata.csv. Not every name has meaning data yet, and meanings or origins can vary by source.</td></tr>
              <tr><th>Last updated</th><td>{TODAY}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer class="major container medium">
        <h2>Keep exploring</h2>
        <div class="seo-links">
          <a href="./">Search names</a>
          <a href="./rankings/top-girls-2025.html">Top girls 2025</a>
          <a href="./rankings/top-boys-2025.html">Top boys 2025</a>
          <a href="./privacy.html">Privacy</a>
        </div>
      </footer>
    </main>

    <footer id="site-footer">
      <div class="container medium">
        <h2>Built for comparing names</h2>
        <p>Search names, check ranking histories and open full profiles from the Australian baby-name explorer.</p>
      </div>
    </footer>
{pilot_favourites_script("./")}
  </body>
</html>
"""
    write_if_changed(ROOT / "data-sources.html", content)
    sitemap_urls.append(url)


def generate_privacy_page(sitemap_urls: list[str]) -> None:
    url = f"{BASE_URL}/privacy.html"
    content = f"""<!doctype html>
<html lang="en">
  <head>
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-7E2KMVP098"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());

      gtag('config', 'G-7E2KMVP098');
    </script>

{PINTEREST_TAG}
{ADSENSE_TAG}
{PINTEREST_VERIFY_META}    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Privacy Policy | Baby Names Australia</title>
    <meta name="description" content="Privacy information for Baby Names Australia, including how Google Analytics is used." />
    <meta name="robots" content="index, follow" />
    <meta name="theme-color" content="#4eb980" />
    <link rel="canonical" href="{url}" />
    <link rel="icon" href="./assets/favicon.ico" sizes="any" />
    <link rel="icon" type="image/png" sizes="32x32" href="./assets/favicon-32x32.png" />
    <link rel="apple-touch-icon" href="./assets/apple-touch-icon.png" />
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body class="profile-pilot-page directive-page sources-page">
{pilot_topbar("./")}
    <header id="header">
      <span class="logo" aria-hidden="true">A</span>
      <h1>Privacy policy</h1>
      <p>How Baby Names Australia handles simple site usage information.</p>
      <div class="header-actions">
        <a class="button" href="./">Back to explorer</a>
        <a class="button alt" href="./data-sources.html">Data sources</a>
      </div>
    </header>

    <main id="main">
      <header class="major container medium">
        <h2>Privacy at a glance</h2>
        <p>Baby Names Australia is a public baby-name search and ranking website. You do not need an account to use it.</p>
      </header>

      <section class="box container">
        <header>
          <h2>Analytics</h2>
          <p>Google Analytics 4</p>
        </header>
        <p>This site uses Google Analytics 4 to understand how people use the website, such as which pages are visited, approximate location, device type, browser type and general interaction patterns.</p>
        <p>Analytics information is used in aggregate to improve the site. It is not used to personally identify visitors.</p>
        <p>Google may use cookies or similar technologies to provide this analytics service. You can limit cookies or analytics tracking through your browser settings or privacy tools.</p>
      </section>

      <section class="box container">
        <header>
          <h2>Information you enter</h2>
          <p>Name searches</p>
        </header>
        <p>The site lets you type baby names into the name explorer. Searches are used to show matching ranking information in your browser. The site does not require names, email addresses, accounts or payment details.</p>
      </section>

      <section class="box container">
        <header>
          <h2>Data sources</h2>
          <p>Public ranking information</p>
        </header>
        <p>The baby-name rankings, meanings and origin notes are built from public ranking data and curated name-note files used by the site. You can read more on the <a href="./data-sources.html">data sources page</a>.</p>
      </section>

      <footer class="major container medium">
        <h2>Keep exploring</h2>
        <div class="seo-links">
          <a href="./">Name explorer</a>
          <a href="./rankings/top-girls-2025.html">Top girls 2025</a>
          <a href="./rankings/top-boys-2025.html">Top boys 2025</a>
        </div>
      </footer>
    </main>
{pilot_favourites_script("./")}
  </body>
</html>
"""
    write_if_changed(ROOT / "privacy.html", content)
    sitemap_urls.append(url)


def local_path_for_url(url: str) -> Path | None:
    if not url.startswith(BASE_URL):
        return None
    relative = url[len(BASE_URL):].lstrip("/")
    if not relative:
        relative = "index.html"
    return ROOT / relative


def lastmod_for_url(url: str) -> str:
    path = local_path_for_url(url)
    if path and path.exists():
        return date.fromtimestamp(path.stat().st_mtime).isoformat()
    return TODAY


def generate_sitemap(urls: list[str]) -> None:
    unique_urls = list(dict.fromkeys(urls))
    entries = "\n".join(
        f"  <url><loc>{esc(url)}</loc><lastmod>{lastmod_for_url(url)}</lastmod></url>"
        for url in unique_urls
    )
    write_if_changed(
        ROOT / "sitemap.xml",
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n',
    )


def generate_robots() -> None:
    write_if_changed(
        ROOT / "robots.txt",
        "User-agent: *\nAllow: /\n\nSitemap: https://www.babynamesaustralia.com/sitemap.xml\n",
    )


def main() -> None:
    rows = read_rows()
    metadata = read_metadata()
    clean_generated()
    write_favourites_js()
    sitemap_urls = [f"{BASE_URL}/"]
    generate_name_pages(rows, sitemap_urls, metadata)
    generate_ranking_pages(rows, sitemap_urls)
    generate_discovery_pages(rows, sitemap_urls, metadata)
    generate_landing_pages(rows, sitemap_urls, metadata)
    generate_2026_watchlist_page(rows, sitemap_urls)
    generate_data_sources(sitemap_urls)
    generate_privacy_page(sitemap_urls)
    generate_favourites_page(sitemap_urls)
    if (ROOT / "baby-name-popularity-checker-australia.html").exists():
        sitemap_urls.append(f"{BASE_URL}/baby-name-popularity-checker-australia.html")
    generate_sitemap(sitemap_urls)
    generate_robots()
    print(f"Generated {len(sitemap_urls)} sitemap URLs")


if __name__ == "__main__":
    main()
