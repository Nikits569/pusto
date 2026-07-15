/**
 * 1. Открывает #topupModal по клику на кнопку "підняти" (.open-topup-modal),
 *    запоминая post_type/post_id именно той карточки, по которой кликнули.
 * 2. По сабмиту тарифа показывает выбор способа оплаты:
 *    - Крипта → крипто-виджет с QR (initPaymentWidget), как раньше.
 *    - Revolut / Українська картка → форма "залиш контакт", заявка уходит
 *      на бэкенд без автоперевірки, адмін підтверджує вручну в адмінці.
 *
 * Подключать ПОСЛЕ payment-widget.js (там определена initPaymentWidget).
 */

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("topupModal");
  if (!modal) return;

  const plansContainer = modal.querySelector(".topup-plans");
  const closeBtn = document.getElementById("closeTopupModal");
  const overlay = modal.querySelector(".topup-modal__overlay");
  if (!plansContainer) return;

  const langPrefix = window.location.pathname.split("/")[1] || "uk";
  const API_BASE = `/${langPrefix}/payments`;

  const PAYMENT_METHOD_LABELS = {
    revolut: "Revolut",
    card_ua: "українську картку",
  };

  // post.type_key в шаблоне отдаёт 'things' / 'jobs' / 'neighbors' (как в urls),
  // а бэкенд ждёт 'things' / 'job' / 'neighbor'. Приводим к одному виду.
  function normalizePostType(section) {
    const map = {
      things: "things",
      jobs: "job",
      job: "job",
      neighbors: "neighbor",
      neighbor: "neighbor",
    };
    return map[section] || section;
  }

  // Общий контейнер под всё, что показываем после выбора тарифа
  // (выбор способа оплаты / крипто-виджет / форма контакта)
  let widgetRoot = modal.querySelector("#payment-widget-root");
  if (!widgetRoot) {
    widgetRoot = document.createElement("div");
    widgetRoot.id = "payment-widget-root";
    widgetRoot.style.display = "none";
    plansContainer.insertAdjacentElement("afterend", widgetRoot);
  }

  function openModal(postType, postId) {
    modal.dataset.postType = postType;
    modal.dataset.postId = postId;

    plansContainer.style.display = "";
    widgetRoot.style.display = "none";
    widgetRoot.innerHTML = "";

    modal.style.display = "flex";
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
  }

  document.querySelectorAll(".open-topup-modal").forEach((btn) => {
    btn.addEventListener("click", () => {
      openModal(normalizePostType(btn.dataset.section), btn.dataset.postId);
    });
  });

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (overlay) overlay.addEventListener("click", closeModal);

  function showMethodChoice(context) {
    plansContainer.style.display = "none";
    widgetRoot.style.display = "block";

    widgetRoot.innerHTML = `
      <div class="pw-card">
        <div class="pw-header">
          <div class="pw-title">Оберіть спосіб оплати</div>
        </div>
        <div class="pw-method-list">
          <button type="button" class="pw-method-btn" data-method="crypto">Крипта (USDT) — миттєве підтвердження</button>
          <button type="button" class="pw-method-btn" data-method="revolut">Revolut</button>
          <button type="button" class="pw-method-btn" data-method="card_ua">Українська картка</button>
        </div>
        <span class="pw-back-link" data-action="back">← назад до тарифів</span>
      </div>
    `;

    widgetRoot.querySelector('[data-action="back"]').addEventListener("click", () => {
      widgetRoot.style.display = "none";
      plansContainer.style.display = "";
    });

    widgetRoot.querySelectorAll(".pw-method-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const method = btn.dataset.method;
        if (method === "crypto") {
          showCryptoWidget(context);
        } else {
          showManualForm(context, method);
        }
      });
    });
  }

  function showCryptoWidget(context) {
    initPaymentWidget(
      "#payment-widget-root",
      "/promotions/create/",
      {
        post_type: context.postType,
        post_id: context.postId,
        duration_days: context.durationDays,
        price_eur: context.priceEur,
      },
      () => {
        window.location.reload();
      }
    );
  }

  function showManualForm(context, method) {
    const methodLabel = PAYMENT_METHOD_LABELS[method] || method;

    widgetRoot.innerHTML = `
      <div class="pw-card">
        <div class="pw-header">
          <div class="pw-title">Залиште контакт</div>
        </div>
        <p style="font-size:13px;color:var(--pw-muted);margin:0 0 14px;">
          Ми зв'яжемось з вами, щоб оформити оплату через ${methodLabel}.
        </p>
        <div class="pw-field">
          <div class="pw-label">Telegram, телефон або email</div>
          <input type="text" class="pw-manual-input" placeholder="@username" />
        </div>
        <button type="button" class="pw-manual-submit">Надіслати заявку</button>
        <span class="pw-back-link" data-action="back">← інший спосіб оплати</span>
      </div>
    `;

    widgetRoot.querySelector('[data-action="back"]').addEventListener("click", () => {
      showMethodChoice(context);
    });

    const input = widgetRoot.querySelector(".pw-manual-input");
    const submitBtn = widgetRoot.querySelector(".pw-manual-submit");

    submitBtn.addEventListener("click", async () => {
      const contact = input.value.trim();
      if (!contact) {
        input.style.borderColor = "#dc2626";
        input.focus();
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Надсилаємо…";

      try {
        const res = await fetch(`${API_BASE}/promotions/create-manual/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            post_type: context.postType,
            post_id: context.postId,
            duration_days: context.durationDays,
            price_eur: context.priceEur,
            payment_method: method,
            contact: contact,
          }),
        });

        if (!res.ok) throw new Error("request failed");

        widgetRoot.innerHTML = `
          <div class="pw-card">
            <div class="pw-success pw-visible" style="position:static;">
              <div class="pw-success-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M20 6L9 17L4 12" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="pw-success-title">Заявку надіслано</div>
              <div class="pw-success-sub">Ми зв'яжемось найближчим часом для підтвердження оплати</div>
            </div>
          </div>
        `;
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Надіслати заявку";
        widgetRoot.insertAdjacentHTML(
          "beforeend",
          `<p style="color:#dc2626;font-size:13px;margin-top:10px;">Не вдалося надіслати заявку. Спробуйте ще раз.</p>`
        );
      }
    });
  }

  modal.querySelectorAll("form.topup-card").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const postType = modal.dataset.postType;
      const postId = modal.dataset.postId;
      const durationDays = parseInt(form.dataset.duration, 10);
      const priceEur = form
        .querySelector(".topup-card__price")
        .textContent.replace(/[^0-9.]/g, ""); // "€5.99" -> "5.99"

      if (!postType || !postId) {
        console.error(
          "topupModal: не задан post_type/post_id — модалка открыта не кнопкой 'підняти'"
        );
        return;
      }

      showMethodChoice({ postType, postId, durationDays, priceEur });
    });
  });
});