(() => {
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
