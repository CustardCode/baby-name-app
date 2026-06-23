const state = {
  rows: normaliseRows(window.BABY_NAME_MASTER || [])
};

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
  searchSex: document.querySelector("#searchSexSelect"),
  year: document.querySelector("#yearSelect"),
  limit: document.querySelector("#limitInput"),
  rankingTitle: document.querySelector("#rankingTitle"),
  recordCount: document.querySelector("#recordCount"),
  rankingBody: document.querySelector("#rankingBody"),
  nameSearch: document.querySelector("#nameSearch"),
  searchSummary: document.querySelector("#searchSummary"),
  nameStats: document.querySelector("#nameStats"),
  yearCards: document.querySelector("#yearCards"),
  trendBody: document.querySelector("#trendBody"),
  trendCanvas: document.querySelector("#trendCanvas")
};

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

function normaliseRows(rows) {
  return rows
    .map((row) => ({
      year: Number(row.year),
      area: String(row.state_or_territory || "").trim(),
      sex: String(row.sex || "").trim().toLowerCase(),
      name: titleCase(row.name),
      source: String(row.source_name || "").trim(),
      rank: row.rank === "" || row.rank == null ? null : Number(row.rank)
    }))
    .filter((row) => row.year && row.area === "Australia" && ["boy", "girl"].includes(row.sex) && row.name && row.rank);
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
  const babyCenterRows = rows.filter((row) => row.source.toLowerCase().includes("babycenter"));
  return dedupeByName(babyCenterRows.length ? babyCenterRows : rows);
}

function dedupeByName(rows) {
  const byName = new Map();
  rows.forEach((row) => {
    const existing = byName.get(row.name);
    if (!existing || row.rank < existing.rank) byName.set(row.name, row);
  });
  return [...byName.values()].sort((a, b) => a.rank - b.rank || a.name.localeCompare(b.name));
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

function renderSearch() {
  const name = titleCase(els.nameSearch.value);
  const sex = els.searchSex.value;
  const sexLabel = sex === "boy" ? "boys" : "girls";

  if (!name) {
    els.searchSummary.textContent = "Type a name to see the last 10 years.";
    els.nameStats.innerHTML = "";
    els.yearCards.innerHTML = "";
    els.trendBody.innerHTML = "";
    drawChart([]);
    return;
  }

  const names = searchNames(name);
  const history = nameHistory(names, sex);
  const ranked = history.filter((item) => item.row);
  const latest = history[history.length - 1];
  const best = ranked.length ? ranked.reduce((winner, item) => (item.row.rank < winner.row.rank ? item : winner), ranked[0]) : null;
  const shownNames = [...new Set(ranked.map((item) => item.row.name))];
  const label = names.length > 1 ? `${name} (${names.join(" / ")})` : name;

  els.searchSummary.textContent = ranked.length
    ? `${label} appeared in the top 100 ${sexLabel} list in ${ranked.length} of the last 10 years.`
    : `${label} has not appeared in the top 100 ${sexLabel} list in the last 10 years.`;

  els.nameStats.innerHTML = [
    ["This year", latest?.row ? ordinal(latest.row.rank) : "Not top 100"],
    ["Best rank", best ? `${ordinal(best.row.rank)} in ${best.year}` : "Not top 100"],
    ["Sex", sex === "boy" ? "Boy" : "Girl"],
    ["Matched as", shownNames.length ? shownNames.join(", ") : names.join(", ")]
  ]
    .map(([label, value]) => `<div class="stat"><span>${label}</span><b>${value}</b></div>`)
    .join("");

  els.trendBody.innerHTML = history
    .map((item) => `<tr><td>${item.year}</td><td>${item.row ? ordinal(item.row.rank) : "Not top 100"}</td></tr>`)
    .join("");

  els.yearCards.innerHTML = history
    .map((item) => `
      <div class="year-card">
        <span>${item.year}</span>
        <b>${item.row ? ordinal(item.row.rank) : "Not top 100"}</b>
      </div>
    `)
    .join("");

  drawChart(history);
}

function renderRankings() {
  const sex = els.sex.value;
  const year = Number(els.year.value);
  const limit = Number(els.limit.value || 20);
  const rows = rowsForYearSex(year, sex).slice(0, limit);
  const sexLabel = sex === "boy" ? "Boys" : "Girls";

  els.rankingTitle.textContent = `${sexLabel}, ${year}`;
  els.recordCount.textContent = `${rows.length} names`;
  els.rankingBody.innerHTML = rows.length
    ? rows.map((row) => `<tr><td>${ordinal(row.rank)}</td><td>${row.name}</td></tr>`).join("")
    : `<tr><td colspan="2" class="empty">No names found.</td></tr>`;
}

function drawChart(history) {
  const canvas = els.trendCanvas;
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
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#d9d3c8";
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1);

  if (!history.length) return;

  const isSmall = width < 520;
  const minX = isSmall ? 44 : 62;
  const maxX = width - (isSmall ? 16 : 28);
  const minY = 26;
  const maxY = height - (isSmall ? 42 : 48);
  const maxRank = 100;

  ctx.strokeStyle = "#d9d3c8";
  ctx.beginPath();
  ctx.moveTo(minX, minY);
  ctx.lineTo(minX, maxY);
  ctx.lineTo(maxX, maxY);
  ctx.stroke();

  ctx.fillStyle = "#68645d";
  ctx.font = `${isSmall ? 11 : 12}px sans-serif`;
  ctx.fillText("1st", isSmall ? 16 : 24, minY + 4);
  ctx.fillText("100th", isSmall ? 4 : 14, maxY + 4);

  const points = history.map((item, index) => {
    const x = history.length === 1 ? (minX + maxX) / 2 : minX + (index / (history.length - 1)) * (maxX - minX);
    const y = item.row ? minY + ((item.row.rank - 1) / (maxRank - 1)) * (maxY - minY) : maxY + 18;
    return { x, y, item };
  });

  const rankedPoints = points.filter((point) => point.item.row);
  if (rankedPoints.length > 1) {
    ctx.strokeStyle = "#0f766e";
    ctx.lineWidth = 3;
    ctx.beginPath();
    rankedPoints.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.stroke();
  }

  points.forEach((point) => {
    ctx.fillStyle = point.item.row ? "#0f766e" : "#c8c0b5";
    ctx.beginPath();
    ctx.arc(point.x, point.y, point.item.row ? 5 : 4, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.fillStyle = "#68645d";
  points.forEach((point) => {
    if (!isSmall || point.item.year % 2 === 1 || point.item.year === history[history.length - 1].year) {
      ctx.fillText(String(point.item.year), point.x - 14, height - 16);
    }
  });
}

function renderAll() {
  renderSearch();
  renderRankings();
}

els.sex.addEventListener("change", renderRankings);
els.searchSex.addEventListener("change", renderSearch);
els.year.addEventListener("change", renderRankings);
els.limit.addEventListener("input", renderRankings);
els.nameSearch.addEventListener("input", renderSearch);
window.addEventListener("resize", () => renderSearch());

populateYears();
els.sex.value = "girl";
els.searchSex.value = "girl";
els.nameSearch.value = "Rebecca";
renderAll();
