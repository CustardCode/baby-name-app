const state = {
  rows: [],
  chartPoints: [],
  searchSexOverride: null,
  lastSearchName: ""
};

const NATIONAL_REPORT_ROWS = [
  ["2025", "Australia", "boy", "Oliver", "1", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Noah", "2", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Theodore", "3", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Henry", "4", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Luca", "5", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Leo", "6", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Hudson", "7", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Charlie", "8", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "Jack", "9", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "boy", "William", "10", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Charlotte", "1", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Amelia", "2", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Isla", "3", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Olivia", "4", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Mia", "5", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Hazel", "6", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Harper", "7", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Matilda", "8", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Sophie", "9", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"],
  ["2025", "Australia", "girl", "Grace", "10", "Australia 2025 national report via McCrindle", "national report / rank only / top 10"]
].map(([year, area, sex, name, rank, source, notes]) => ({
  year,
  state_or_territory: area,
  sex,
  name,
  rank,
  source_name: source,
  notes
}));

const NAME_GROUPS = [
  ["Rebecca", "Bec", "Becca", "Becky", "Rebekah"],
  ["Thomas", "Tom", "Tommy"],
  ["William", "Will", "Billy", "Liam"],
  ["James", "Jim", "Jimmy", "Jamie"],
  ["Alexander", "Alex", "Xander"],
  ["Charlotte", "Charlie", "Lottie"],
  ["Elizabeth", "Eliza", "Liz", "Lizzie", "Beth"],
  ["Matilda", "Tilly", "Tillie"],
  ["Olivia", "Liv", "Livvy"],
  ["Isabella", "Bella", "Izzy"],
  ["Benjamin", "Ben", "Benny"],
  ["Theodore", "Theo", "Teddy"],
  ["Henry", "Harry"],
  ["Joseph", "Joe", "Joey"],
  ["Samuel", "Sam", "Sammy"],
  ["Edward", "Ed", "Eddie", "Ted", "Teddy"],
  ["Katherine", "Catherine", "Kate", "Katie", "Kat"],
  ["Sophia", "Sophie"],
  ["Amelia", "Mia", "Millie"],
  ["Eleanor", "Ellie", "Nell"]
];

const els = {
  sex: document.querySelector("#sexSelect"),
  searchSexLabel: document.querySelector("#searchSexLabel"),
  searchSexButtons: [...document.querySelectorAll("[data-search-sex]")],
  year: document.querySelector("#yearSelect"),
  limit: document.querySelector("#limitInput"),
  rankingTitle: document.querySelector("#rankingTitle"),
  recordCount: document.querySelector("#recordCount"),
  rankingBody: document.querySelector("#rankingBody"),
  nameSearch: document.querySelector("#nameSearch"),
  searchSummary: document.querySelector("#searchSummary"),
  nameStats: document.querySelector("#nameStats"),
  yearCards: document.querySelector("#yearCards"),
  trendCanvas: document.querySelector("#trendCanvas"),
  chartTooltip: document.querySelector("#chartTooltip")
};

let initialisingFromUrl = false;
let lastTrackedSearchKey = "";

function trackEvent(eventName, params = {}) {
  try {
    if (typeof window.gtag !== "function") return;
    window.gtag("event", eventName, params);
  } catch (_) {
    // Analytics must never interrupt the app.
  }
}

function safeSearchTerm(value) {
  const term = titleCase(value).slice(0, 40);
  return /^[A-Za-z][A-Za-z '-]{0,39}$/.test(term) ? term : "";
}

function slugify(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function sexPlural(sex) {
  return sex === "boy" ? "boys" : "girls";
}

function titleCase(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\b[a-z]/g, (char) => char.toUpperCase());
}

function searchNames(value) {
  const wanted = titleCase(value);
  if (!wanted) return [];

  const group = NAME_GROUPS.find((names) => names.some((name) => name.toLowerCase() === wanted.toLowerCase()));
  if (group) return group.map(titleCase);

  const allNames = [...new Set(state.rows.map((row) => row.name))].sort();
  const exact = allNames.filter((name) => name.toLowerCase() === wanted.toLowerCase());
  if (exact.length) return exact;

  return allNames.filter((name) => name.toLowerCase().startsWith(wanted.toLowerCase()));
}

function ordinal(number) {
  const n = Number(number);
  if (!n) return "Not top 100";
  const suffixes = ["th", "st", "nd", "rd"];
  const mod100 = n % 100;
  return `${n}${suffixes[(mod100 - 20) % 10] || suffixes[mod100] || suffixes[0]}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function normaliseRows(rows) {
  return rows
    .map((row) => ({
      year: Number(row.year),
      area: String(row.state_or_territory || "").trim(),
      sex: String(row.sex || "").trim().toLowerCase(),
      name: titleCase(row.name),
      source: String(row.source_name || "").trim(),
      notes: String(row.notes || "").trim(),
      rank: row.rank === "" || row.rank == null ? null : Number(row.rank)
    }))
    .filter((row) => row.year && row.area === "Australia" && ["boy", "girl"].includes(row.sex) && row.name && row.rank);
}

function parseCsv(text) {
  const rows = [];
  let field = "";
  let row = [];
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && inQuotes && next === '"') {
      field += '"';
      index += 1;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  row.push(field);
  if (row.some((value) => value !== "")) rows.push(row);
  if (!rows.length) return [];

  const headers = rows[0].map((header) => header.trim());
  return rows.slice(1).map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])));
}

async function loadRows() {
  const bundledRows = window.BABY_NAME_MASTER || [];
  if (bundledRows.length) return bundledRows;

  const response = await fetch("./data/clean/baby_names_master.csv");
  if (!response.ok) throw new Error(`Could not load baby name data (${response.status})`);
  return parseCsv(await response.text());
}

function setRows(rows) {
  state.rows = normaliseRows([...rows, ...NATIONAL_REPORT_ROWS]);
}

function years() {
  return [...new Set(state.rows.map((row) => row.year))].sort((a, b) => b - a);
}

function lastTenYears() {
  return years().slice(0, 10).sort((a, b) => a - b);
}

function populateYears() {
  const availableYears = years();
  els.year.innerHTML = availableYears.map((year) => `<option value="${year}">${year}</option>`).join("");
  els.year.value = availableYears[0] || "";
}

function rowsForYearSex(year, sex) {
  const rows = state.rows.filter((row) => row.year === year && row.sex === sex);
  if (!rows.length) return [];

  const bestPriority = Math.max(...rows.map(sourcePriority));
  if (bestPriority > 1) {
    const primaryRows = rows.filter((row) => sourcePriority(row) === bestPriority);
    const primaryCutoff = Math.max(...primaryRows.map((row) => row.rank || 0));
    const fillerRows = rows.filter((row) => sourcePriority(row) < bestPriority && row.rank > primaryCutoff);
    return dedupeByName([...primaryRows, ...fillerRows]);
  }

  return dedupeByName(rows);
}

function sourcePriority(row) {
  const source = row.source.toLowerCase();
  const notes = row.notes.toLowerCase();
  if (source.includes("mccrindle") || source.includes("national report") || notes.includes("national report")) return 3;
  if (source.includes("calculated australia total")) return 2;
  if (source.includes("babycenter")) return 1;
  return 0;
}

function dedupeByName(rows) {
  const byName = new Map();
  rows.forEach((row) => {
    const existing = byName.get(row.name);
    const priority = sourcePriority(row);
    const existingPriority = existing ? sourcePriority(existing) : -1;
    if (!existing || priority > existingPriority || (priority === existingPriority && row.rank < existing.rank)) {
      byName.set(row.name, row);
    }
  });
  return [...byName.values()].sort((a, b) => a.rank - b.rank || sourcePriority(b) - sourcePriority(a) || a.name.localeCompare(b.name));
}

function rankForNames(names, year, sex) {
  const wanted = new Set(names.map((name) => name.toLowerCase()));
  const matches = rowsForYearSex(year, sex).filter((row) => wanted.has(row.name.toLowerCase()));
  if (!matches.length) return null;
  return matches.sort((a, b) => a.rank - b.rank)[0];
}

function nameHistory(names, sex) {
  return lastTenYears().map((year) => ({
    year,
    row: rankForNames(names, year, sex)
  }));
}

function inferSearchSex(names) {
  const candidates = ["girl", "boy"].map((sex) => {
    const history = nameHistory(names, sex);
    const ranked = history.filter((item) => item.row);
    const latest = [...ranked].reverse()[0];
    const score = ranked.reduce((total, item) => total + (101 - item.row.rank), 0);
    const bestRank = ranked.length ? Math.min(...ranked.map((item) => item.row.rank)) : Infinity;
    return { sex, rankedCount: ranked.length, latestRank: latest?.row.rank ?? Infinity, bestRank, score };
  });

  candidates.sort((a, b) =>
    b.score - a.score ||
    b.rankedCount - a.rankedCount ||
    a.latestRank - b.latestRank ||
    a.bestRank - b.bestRank
  );

  return candidates[0].score ? candidates[0] : { sex: "girl", rankedCount: 0, latestRank: Infinity, bestRank: Infinity, score: 0 };
}

function sexSearchOptions(names) {
  return Object.fromEntries(["boy", "girl"].map((sex) => {
    const history = nameHistory(names, sex);
    const ranked = history.filter((item) => item.row);
    const allRanked = years()
      .map((year) => ({ year, row: rankForNames(names, year, sex) }))
      .filter((item) => item.row);
    return [sex, { history, ranked, allRanked }];
  }));
}

function updateSearchSexToggle(activeSex, options, hasName, canCompare) {
  const autoSex = els.searchSexLabel.closest(".auto-sex");
  if (autoSex) autoSex.classList.toggle("is-comparison", Boolean(canCompare));

  els.searchSexButtons.forEach((button) => {
    const sex = button.dataset.searchSex;
    const hasResults = Boolean(options?.[sex]?.allRanked.length);
    button.classList.toggle("is-active", hasName && canCompare && sex === activeSex);
    button.disabled = !hasName || !canCompare;
    button.setAttribute("aria-pressed", hasName && sex === activeSex ? "true" : "false");
    button.title = hasName && canCompare && !hasResults ? `No top 100 ${sex} result found` : "";
  });
}

function renderSearch() {
  const name = titleCase(els.nameSearch.value);
  if (name !== state.lastSearchName) {
    state.lastSearchName = name;
    state.searchSexOverride = null;
  }

  if (!name) {
    els.searchSummary.textContent = "Type a name to begin.";
    els.searchSexLabel.textContent = "Auto";
    updateSearchSexToggle("girl", null, false, false);
    els.nameStats.innerHTML = "";
    els.yearCards.innerHTML = "";
    drawChart([]);
    return;
  }

  const names = searchNames(name);
  const inferred = inferSearchSex(names);
  const options = sexSearchOptions(names);
  const hasBoth = Boolean(options.boy.allRanked.length && options.girl.allRanked.length);
  if (!hasBoth) state.searchSexOverride = null;
  const sex = hasBoth && state.searchSexOverride ? state.searchSexOverride : inferred.sex;
  const history = options[sex].history;
  const ranked = options[sex].ranked;
  const latest = history[history.length - 1];
  const best = ranked.length ? ranked.reduce((winner, item) => (item.row.rank < winner.row.rank ? item : winner), ranked[0]) : null;
  const shownNames = [...new Set(ranked.map((item) => item.row.name))];
  const label = names.length > 1 ? `${name} (${names.join(" / ")})` : name;
  els.searchSexLabel.textContent = hasBoth
    ? "Compare"
    : sex === "boy" ? "Boy" : "Girl";
  updateSearchSexToggle(sex, options, true, hasBoth);

  els.searchSummary.textContent = ranked.length
    ? `Top 100 in ${ranked.length} of 10 years.`
    : `No top 100 result for ${label}.`;

  const detailName = shownNames[0] || names[0];
  const detailSlug = slugify(detailName);
  const detailHref = detailSlug ? `./names/${sexPlural(sex)}/${detailSlug}.html` : "";
  const statCards = [
    ["Latest", latest?.row ? ordinal(latest.row.rank) : "Not top 100"],
    ["Best", best ? `${ordinal(best.row.rank)} in ${best.year}` : "Not top 100"],
    ["Listed", `${ranked.length}/10 years`]
  ].map(([label, value]) => `<div class="stat"><span>${label}</span><b>${escapeHtml(value)}</b></div>`);

  statCards.push(
    detailHref
      ? `<a class="stat stat-link" href="${detailHref}" aria-label="View full profile for ${escapeHtml(detailName)}"><span>View full profile</span><b>${escapeHtml(detailName)} <em aria-hidden="true">→</em></b></a>`
      : `<div class="stat"><span>View full profile</span><b>N/A</b></div>`
  );

  els.nameStats.innerHTML = statCards.join("");

  els.yearCards.innerHTML = history
    .map((item) => `
      <div class="year-card ${item.row ? "" : "is-missing"}">
        <span>${item.year}</span>
        <b>${item.row ? ordinal(item.row.rank) : "Not top 100"}</b>
      </div>
    `)
    .join("");

  drawChart(history);

  const safeTerm = safeSearchTerm(name);
  if (safeTerm && !initialisingFromUrl) {
    const searchKey = `${safeTerm}|${sex}|${ranked.length}`;
    if (searchKey !== lastTrackedSearchKey) {
      lastTrackedSearchKey = searchKey;
      trackEvent("name_search", {
        search_term: safeTerm,
        gender: sex,
        result_found: ranked.length > 0,
        listed_years_count: ranked.length
      });
    }
    const url = new URL(window.location.href);
    url.searchParams.set("name", safeTerm);
    if (state.searchSexOverride) url.searchParams.set("sex", state.searchSexOverride);
    else url.searchParams.delete("sex");
    window.history.replaceState({}, "", url);
  }
}

function renderRankings() {
  const sex = els.sex.value;
  const year = Number(els.year.value);
  const limit = Math.min(100, Math.max(1, Number(els.limit.value || 20)));
  const rows = rowsForYearSex(year, sex).filter((row) => row.rank <= limit);
  const sexLabel = sex === "boy" ? "boys" : "girls";

  els.rankingTitle.textContent = `Top ${sexLabel} names \u2014 ${year}`;
  els.recordCount.textContent = `Top ${limit}`;
  els.rankingBody.innerHTML = rows.length
    ? rows.map((row) => `
      <tr>
        <td>${ordinal(row.rank)}</td>
        <td><button class="name-link" type="button" data-name="${escapeHtml(row.name)}" data-rank="${row.rank}">${escapeHtml(row.name)}</button></td>
      </tr>
    `).join("")
    : `<tr><td colspan="2" class="empty">No names found.</td></tr>`;
}

function drawChart(history) {
  const canvas = els.trendCanvas;
  hideChartTooltip();
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(Math.floor(rect.width), 320);
  const height = Math.max(Math.floor(rect.height), 220);
  const ratio = window.devicePixelRatio || 1;
  if (canvas.width !== Math.floor(width * ratio) || canvas.height !== Math.floor(height * ratio)) {
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fffdf9";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#e8e0d4";
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
  state.chartPoints = [];

  if (!history.length) return;

  const isSmall = width < 520;
  const isWide = width > 860;
  const plotWidth = isWide ? Math.min(820, width - 160) : width - (isSmall ? 60 : 88);
  const minX = Math.round((width - plotWidth) / 2) + (isSmall ? 10 : 16);
  const maxX = Math.round((width + plotWidth) / 2) - (isSmall ? 8 : 16);
  const minY = isSmall ? 24 : 34;
  const maxY = height - (isSmall ? 58 : 74);
  const yearLabelY = height - (isSmall ? 16 : 24);
  const missingY = maxY + (yearLabelY - maxY) / 2;
  const maxRank = 100;

  ctx.strokeStyle = "#e8e0d4";
  ctx.lineWidth = 1;
  [1, 25, 50, 75, 100].forEach((rank) => {
    const y = minY + ((rank - 1) / (maxRank - 1)) * (maxY - minY);
    ctx.beginPath();
    ctx.moveTo(minX, y);
    ctx.lineTo(maxX, y);
    ctx.stroke();
  });

  ctx.strokeStyle = "#cec5b7";
  ctx.beginPath();
  ctx.moveTo(minX, minY);
  ctx.lineTo(minX, maxY);
  ctx.lineTo(maxX, maxY);
  ctx.stroke();

  ctx.fillStyle = "#7a746b";
  ctx.font = `700 ${isSmall ? 11 : 12}px sans-serif`;
  ctx.textAlign = "right";
  ctx.fillText("1st", minX - (isSmall ? 12 : 22), minY + 4);
  ctx.fillText("100th", minX - (isSmall ? 12 : 22), maxY + 4);
  ctx.textAlign = "left";

  const points = history.map((item, index) => {
    const x = history.length === 1 ? (minX + maxX) / 2 : minX + (index / (history.length - 1)) * (maxX - minX);
    const y = item.row ? minY + ((item.row.rank - 1) / (maxRank - 1)) * (maxY - minY) : missingY;
    return { x, y, item };
  });
  state.chartPoints = points;

  const rankedPoints = points.filter((point) => point.item.row);
  if (rankedPoints.length > 1) {
    ctx.strokeStyle = "#0f766e";
    ctx.lineWidth = 3.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    rankedPoints.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.stroke();
  }

  points.forEach((point) => {
    ctx.fillStyle = point.item.row ? "#0f766e" : "#8f877c";
    ctx.beginPath();
    ctx.arc(point.x, point.y, point.item.row ? 5.5 : 5, 0, Math.PI * 2);
    ctx.fill();
    if (point.item.row) {
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();
    } else {
      ctx.strokeStyle = "#fffdf9";
      ctx.lineWidth = 2.5;
      ctx.stroke();
    }
  });

  ctx.fillStyle = "#68645d";
  ctx.font = `700 ${isSmall ? 11 : 12}px sans-serif`;
  ctx.textAlign = "center";
  points.forEach((point) => {
    if (!isSmall || point.item.year % 2 === 1 || point.item.year === history[history.length - 1].year) {
      ctx.fillText(String(point.item.year), point.x, yearLabelY);
    }
  });
  ctx.textAlign = "left";
}

function showChartTooltip(point) {
  if (!els.chartTooltip) return;
  const rect = els.trendCanvas.getBoundingClientRect();
  const left = Math.min(Math.max(point.x, 54), rect.width - 54);
  const label = point.item.row ? ordinal(point.item.row.rank) : "Not top 100";
  els.chartTooltip.textContent = `${point.item.year}: ${label}`;
  els.chartTooltip.style.left = `${left}px`;
  els.chartTooltip.style.top = `${point.y}px`;
  els.chartTooltip.classList.toggle("is-below", point.y < 54);
  els.chartTooltip.classList.add("is-visible");
}

function hideChartTooltip() {
  if (!els.chartTooltip) return;
  els.chartTooltip.classList.remove("is-visible");
}

function updateChartTooltip(event) {
  const rect = els.trendCanvas.getBoundingClientRect();
  const source = event.touches?.[0] || event;
  const x = source.clientX - rect.left;
  const y = source.clientY - rect.top;
  const hit = state.chartPoints.find((point) => Math.hypot(point.x - x, point.y - y) <= 16);

  if (hit) showChartTooltip(hit);
  else hideChartTooltip();
}

function renderAll() {
  renderSearch();
  renderRankings();
}

function searchRankingName(name, sex) {
  els.nameSearch.value = name;
  state.lastSearchName = titleCase(name);
  state.searchSexOverride = sex;
  renderSearch();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function trackFilterChange() {
  trackEvent("top_list_filter_change", {
    year: Number(els.year.value),
    gender: els.sex.value,
    show_count: Number(els.limit.value || 20)
  });
}

els.sex.addEventListener("change", () => {
  renderRankings();
  trackFilterChange();
});
els.year.addEventListener("change", () => {
  renderRankings();
  trackFilterChange();
});
els.limit.addEventListener("input", () => {
  renderRankings();
  trackFilterChange();
});
els.nameSearch.addEventListener("input", renderSearch);
els.searchSexButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (button.disabled) return;
    state.searchSexOverride = button.dataset.searchSex;
    renderSearch();
  });
});
els.rankingBody.addEventListener("click", (event) => {
  const button = event.target.closest(".name-link");
  if (button) {
    trackEvent("clicked_ranking_name", {
      name: safeSearchTerm(button.dataset.name || ""),
      rank: Number(button.dataset.rank || 0),
      year: Number(els.year.value),
      gender: els.sex.value
    });
    searchRankingName(button.dataset.name, els.sex.value);
  }
});
els.trendCanvas.addEventListener("mousemove", updateChartTooltip);
els.trendCanvas.addEventListener("mouseleave", hideChartTooltip);
els.trendCanvas.addEventListener("touchstart", updateChartTooltip, { passive: true });
els.trendCanvas.addEventListener("touchmove", updateChartTooltip, { passive: true });
window.addEventListener("resize", () => renderSearch());

async function initialise() {
  try {
    setRows(await loadRows());
    populateYears();
    els.sex.value = "girl";
    const urlName = safeSearchTerm(new URLSearchParams(window.location.search).get("name") || "");
    const urlSex = new URLSearchParams(window.location.search).get("sex");
    if (urlName) {
      initialisingFromUrl = true;
      els.nameSearch.value = urlName;
      if (["boy", "girl"].includes(urlSex)) state.searchSexOverride = urlSex;
    }
    renderAll();
    initialisingFromUrl = false;
  } catch (error) {
    console.error(error);
    els.searchSummary.textContent = "Name data could not be loaded.";
    els.searchSexLabel.textContent = "Auto";
    drawChart([]);
  }
}

initialise();
