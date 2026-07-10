  document.addEventListener("DOMContentLoaded", () => {
    function removeCard(cardEl) {
      const pages = cardEl.closest(".pages");
      const link = cardEl.closest("a.card-link");
      if (link) link.remove();
      else if (pages) pages.remove();
      else cardEl.remove();

      // убираем пустые плейсхолдеры рекламы
      document.querySelectorAll(".adv").forEach(ad => {
        if (!ad.textContent.trim() && ad.children.length === 0) ad.remove();
      });
    }

    document.querySelectorAll(".pages[data-cover-url]").forEach(async (pages) => {
      const url = pages.dataset.coverUrl;

      try {
        const res = await fetch(url, { method: "GET" });
        const ct = (res.headers.get("content-type") || "").toLowerCase();

        // 404/500 или вернули HTML "Page not found" вместо image/*
        if (!res.ok || !ct.startsWith("image/")) {
          removeCard(pages);
        }
      } catch (e) {
        removeCard(pages);
      }
    });
  });