

function initPaymentWidget(selector, url, payload, onSuccess) {
  const root = document.querySelector(selector);
  if (!root) return;

  const langPrefix = window.location.pathname.split("/")[1] || "uk";

  function getCookie(name) {
    let v = null;
    document.cookie.split(";").forEach((c) => {
      c = c.trim();
      if (c.startsWith(name + "=")) v = decodeURIComponent(c.substring(name.length + 1));
    });
    return v;
  }

  root.innerHTML = `
    <div class="pw-card">
      <div class="pw-header">
        <div class="pw-title">Оплата USDT (TRC20)</div>
        <div class="pw-timer" id="pwTimer">--:--</div>
      </div>
      <div class="pw-loading" id="pwLoading">Створюємо замовлення…</div>
      <div class="pw-content" id="pwContent" style="display:none;">
        <div class="pw-qr-wrap">
          <img class="pw-qr" id="pwQr" alt="QR code" />
        </div>

        <div class="pw-field">
          <div class="pw-label">Сума до оплати (точно)</div>
          <div class="pw-value-row">
            <span class="pw-value" id="pwAmount"></span>
            <button type="button" class="pw-copy-btn" data-copy="amount">Копіювати</button>
          </div>
        </div>

        <div class="pw-field">
          <div class="pw-label">Адреса (мережа TRC20)</div>
          <div class="pw-value-row">
            <span class="pw-value pw-value--address" id="pwAddress"></span>
            <button type="button" class="pw-copy-btn" data-copy="address">Копіювати</button>
          </div>
        </div>

        <div class="pw-status">
          <span class="pw-status-dot"></span>
          <span id="pwStatusText">Очікуємо надходження платежа…</span>
        </div>
      </div>

      <div class="pw-success" id="pwSuccess">
        <div class="pw-success-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 6L9 17L4 12" stroke="#16a34a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="pw-success-title">Оплату отримано!</div>
        <div class="pw-success-sub">Оголошення скоро підніметься в списку</div>
      </div>

      <div class="pw-error" id="pwError" style="display:none;"></div>
    </div>
  `;

  const loadingEl = root.querySelector("#pwLoading");
  const contentEl = root.querySelector("#pwContent");
  const successEl = root.querySelector("#pwSuccess");
  const errorEl = root.querySelector("#pwError");
  const timerEl = root.querySelector("#pwTimer");
  const qrEl = root.querySelector("#pwQr");
  const amountEl = root.querySelector("#pwAmount");
  const addressEl = root.querySelector("#pwAddress");

  let pollInterval = null;
  let countdownInterval = null;
  let orderData = null;

  function showError(message) {
    loadingEl.style.display = "none";
    errorEl.style.display = "block";
    errorEl.textContent = message || "Сталася помилка. Спробуйте ще раз.";
  }

  function formatTimeLeft(msLeft) {
    if (msLeft <= 0) return "00:00";
    const totalSeconds = Math.floor(msLeft / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function startCountdown(expiresAtISO) {
    const expiresAt = new Date(expiresAtISO).getTime();

    function tick() {
      const msLeft = expiresAt - Date.now();
      timerEl.textContent = formatTimeLeft(msLeft);

      if (msLeft <= 0) {
        clearInterval(countdownInterval);
        clearInterval(pollInterval);
        showError("Час очікування платежу вичерпано. Оновіть сторінку та спробуйте ще раз.");
      }
    }

    tick();
    countdownInterval = setInterval(tick, 1000);
  }

  function startPolling(orderId) {
    async function checkStatus() {
      try {
        const res = await fetch(`/${langPrefix}/payments/orders/${orderId}/status/`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.status === "paid") {
          clearInterval(pollInterval);
          clearInterval(countdownInterval);
          contentEl.style.display = "none";
          successEl.classList.add("pw-visible");
          if (typeof onSuccess === "function") {
            setTimeout(onSuccess, 1500);
          }
        } else if (data.status === "expired") {
          clearInterval(pollInterval);
          clearInterval(countdownInterval);
          showError("Термін дії замовлення закінчився. Оновіть сторінку та спробуйте ще раз.");
        }
      } catch (err) {}
    }

    checkStatus();
    pollInterval = setInterval(checkStatus, 5000);
  }

  root.addEventListener("click", (e) => {
    const btn = e.target.closest(".pw-copy-btn");
    if (!btn || !orderData) return;

    const field = btn.dataset.copy;
    const text = field === "amount" ? orderData.amount : orderData.address;

    navigator.clipboard.writeText(text).then(() => {
      const original = btn.textContent;
      btn.textContent = "Скопійовано!";
      setTimeout(() => (btn.textContent = original), 1500);
    });
  });

  (async function createOrder() {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "request failed");
      }

      orderData = await res.json();

      loadingEl.style.display = "none";
      contentEl.style.display = "block";

      qrEl.src = orderData.qr_code;
      amountEl.textContent = `${orderData.amount} ${orderData.currency}`;
      addressEl.textContent = orderData.address;

      startCountdown(orderData.expires_at);
      startPolling(orderData.order_id);
    } catch (err) {
      showError("Не вдалося створити замовлення. Спробуйте ще раз.");
    }
  })();
}
