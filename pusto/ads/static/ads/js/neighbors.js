
const GUEST_KEY = "guest_favorites_v1";

function getCookieRaw(name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(
    new RegExp("(^|;\\s*)" + escaped + "=([^;]*)")
  );
  return match ? match[2] : null;
}

function setCookie(name, value, days = 365) {
  const d = new Date();
  d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
  document.cookie =
    `${name}=${encodeURIComponent(value)}; path=/; expires=${d.toUTCString()}; SameSite=Lax`;
}

function loadGuestFavs() {
  try {
    const rawCookie = getCookieRaw(GUEST_KEY);
    if (rawCookie) {
      return JSON.parse(decodeURIComponent(rawCookie));
    }
  } catch (e) {
    console.error("Cookie parse error:", e);
  }

  try {
    const rawLs = localStorage.getItem(GUEST_KEY);
    return rawLs ? JSON.parse(rawLs) : {};
  } catch (e) {
    console.error("localStorage parse error:", e);
    return {};
  }
}

function saveGuestFavs(data) {
  try {
    const json = JSON.stringify(data);
    setCookie(GUEST_KEY, json);
    localStorage.setItem(GUEST_KEY, json);
  } catch (e) {
    console.error("Favorites save error:", e);
  }
}

function normalizeFavsShape(data) {
  if (!data || typeof data !== "object") return {};

  ["ThingsPost", "NeighborPost", "JobPost"].forEach((key) => {
    if (!Array.isArray(data[key])) {
      data[key] = [];
    }

    data[key] = data[key]
      .map((v) => Number(v))
      .filter((v) => Number.isInteger(v));
  });

  return data;
}

function isGuestFavorite(contentType, objectId) {
  const data = normalizeFavsShape(loadGuestFavs());
  return data[contentType].includes(objectId);
}

function toggleGuestFavorite(contentType, objectId) {
  const data = normalizeFavsShape(loadGuestFavs());

  if (!Array.isArray(data[contentType])) {
    data[contentType] = [];
  }

  const list = data[contentType];
  const index = list.indexOf(objectId);

  let isActive = false;

  if (index === -1) {
    list.push(objectId);
    isActive = true;
  } else {
    list.splice(index, 1);
    isActive = false;
  }

  data[contentType] = list.slice(-200);
  saveGuestFavs(data);

  return isActive;
}

function applyFavUI(btn, isActive) {
  const icon = btn.querySelector(".favorite-icon");

  btn.classList.toggle("is-active", isActive);

  if (icon) {
    icon.textContent = isActive ? "♥" : "♡";
  }

  btn.setAttribute(
    "aria-label",
    isActive ? "Видалити з обраного" : "Додати в обране"
  );
}

function initGuestFavButtons() {
  document.querySelectorAll(".js-fav-btn").forEach((btn) => {
    const contentType = btn.dataset.contentType;
    const objectId = Number(btn.dataset.objectId);

    if (!contentType || !Number.isInteger(objectId)) {
      console.warn("Invalid favorite button data:", btn);
      return;
    }

    applyFavUI(btn, isGuestFavorite(contentType, objectId));
  });
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".js-fav-btn");
  if (!btn) return;

  e.preventDefault();
  e.stopPropagation();

  const contentType = btn.dataset.contentType;
  const objectId = Number(btn.dataset.objectId);

  if (!contentType || !Number.isInteger(objectId)) {
    console.warn("Invalid favorite click data:", btn);
    return;
  }

  const isActive = toggleGuestFavorite(contentType, objectId);
  applyFavUI(btn, isActive);

  console.log("Saved favorites:", normalizeFavsShape(loadGuestFavs()));
});

document.addEventListener("DOMContentLoaded", initGuestFavButtons);
