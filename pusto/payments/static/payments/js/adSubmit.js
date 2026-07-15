document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("adSubmitModal");
  if (!modal) return;

  const overlay = modal.querySelector(".ad-submit-modal__overlay");
  const closeBtn = document.getElementById("closeAdSubmitModal");
  const selectedPlanEl = document.getElementById("adSubmitSelectedPlan");

  const form = document.getElementById("adSubmitForm");
  const errorBox = document.getElementById("adSubmitError");
  const successBox = document.getElementById("adSubmitSuccess");

  const typeOrderInput = document.getElementById("adTypeOrder");
  const durationInput = document.getElementById("adDurationDays");
  const priceInput = document.getElementById("adPriceEur");

  const imageInput = document.getElementById("adImageInput");
  const textInput = document.getElementById("adTextInput");
  const linkInput = document.getElementById("adLinkInput");

  const previewCard = document.getElementById("adPreviewCard");
  const previewBadge = document.getElementById("adPreviewBadge");
  const previewImage = document.getElementById("adPreviewImage");
  const previewImagePlaceholder = document.getElementById("adPreviewImagePlaceholder");
  const previewText = document.getElementById("adPreviewText");

  const textLabel = document.getElementById("adTextLabel");
  const textHint = document.getElementById("adTextHint");

  function getCookie(name) {
    let v = null;
    document.cookie.split(";").forEach((c) => {
      c = c.trim();
      if (c.startsWith(name + "=")) v = decodeURIComponent(c.substring(name.length + 1));
    });
    return v;
  }

  function applyTypeToPreview(typeOrder) {
    const isBanner = typeOrder === "banner";

    previewCard.classList.toggle("ad-submit-preview__card--banner", isBanner);
    previewCard.classList.toggle("ad-submit-preview__card--post", !isBanner);
    previewBadge.style.display = isBanner ? "none" : "block";

    textLabel.textContent = isBanner
      ? textLabel.dataset.labelBanner
      : textLabel.dataset.labelPost;
    textHint.style.display = isBanner ? "block" : "none";

    previewText.textContent = isBanner
      ? previewText.dataset.placeholderBanner
      : previewText.dataset.placeholderPost;

    textInput.placeholder = isBanner
      ? textInput.dataset.placeholderBanner
      : textInput.dataset.placeholderPost;

    linkInput.placeholder = isBanner
      ? linkInput.dataset.placeholderBanner
      : linkInput.dataset.placeholderPost;
  }

  function resetForm(typeOrder) {
    form.reset();
    form.style.display = "";
    successBox.style.display = "none";
    errorBox.style.display = "none";
    previewImage.style.display = "none";
    previewImage.src = "";
    previewImagePlaceholder.style.display = "block";
    applyTypeToPreview(typeOrder);
  }

  function openModal(typeOrder, durationDays, priceEur, label) {
    resetForm(typeOrder);   // сначала сбрасываем форму
  
    typeOrderInput.value = typeOrder;   // потом проставляем нужные значения
    durationInput.value = durationDays;
    priceInput.value = priceEur;
  
    selectedPlanEl.textContent = `${label} — €${priceEur}`;
  
    modal.style.display = "flex";
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  document.querySelectorAll(".open-ad-submit").forEach((btn) => {
    btn.addEventListener("click", () => {
      openModal(
        btn.dataset.typeOrder,
        btn.dataset.durationDays,
        btn.dataset.priceEur,
        btn.dataset.label
      );
    });
  });

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (overlay) overlay.addEventListener("click", closeModal);

  // --- live превью фото ---
  imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    if (!file) {
      previewImage.style.display = "none";
      previewImagePlaceholder.style.display = "block";
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImage.src = e.target.result;
      previewImage.style.display = "block";
      previewImagePlaceholder.style.display = "none";
    };
    reader.readAsDataURL(file);
  });

  // --- live превью тексту ---
  textInput.addEventListener("input", () => {
    const isBanner = typeOrderInput.value === "banner";
    const placeholder = isBanner
      ? previewText.dataset.placeholderBanner
      : previewText.dataset.placeholderPost;
    previewText.textContent = textInput.value.trim() || placeholder;
  });

  // --- сабміт заявки ---
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    errorBox.style.display = "none";

    const submitBtn = form.querySelector(".ad-submit-form__submit");
    submitBtn.disabled = true;

    try {
      const formData = new FormData(form);

      const resp = await fetch(form.dataset.submitUrl, {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
        body: formData,
      });

      const data = await resp.json().catch(() => ({}));

      if (!resp.ok) {
        errorBox.textContent = data.error || "Сталася помилка. Спробуйте ще раз.";
        errorBox.style.display = "block";
        submitBtn.disabled = false;
        return;
      }

      form.style.display = "none";
      successBox.style.display = "flex";
    } catch (err) {
      errorBox.textContent = "Помилка мережі. Спробуйте ще раз.";
      errorBox.style.display = "block";
      submitBtn.disabled = false;
    }
  });
});
