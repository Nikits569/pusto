const ntfOverlay = document.getElementById('ntfOverlay');
const ntfForm = document.getElementById('ntfForm');
const ntfSubmitBtn = document.getElementById('ntfSubmitBtn');
const ntfMessage = document.getElementById('ntfFormMessage');
const ntfSuccess = document.getElementById('ntfSuccess');

const NTF_SUBMIT_URL = window.NTF_SUBMIT_URL;

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

function ntfOpen(){
  ntfOverlay.classList.add('active');
  document.body.style.overflow = 'hidden';
}
function ntfClose(){
  ntfOverlay.classList.remove('active');
  document.body.style.overflow = '';
  setTimeout(() => {
    ntfSuccess.classList.remove('active');
    ntfForm.style.display = '';
    ntfMessage.textContent = '';
    ntfMessage.classList.remove('is-error', 'is-success');
  }, 250);
}
ntfOverlay.addEventListener('click', (e) => { if (e.target === ntfOverlay) ntfClose(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') ntfClose(); });

ntfForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  ntfMessage.textContent = '';
  ntfMessage.classList.remove('is-error', 'is-success');
  ntfSubmitBtn.disabled = true;
  ntfSubmitBtn.textContent = 'Надсилаємо...';

  const formData = new FormData(ntfForm);

  try {
    const res = await fetch(NTF_SUBMIT_URL, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: formData,
    });
    const data = await res.json();

    if (res.ok && data.success) {
      ntfForm.style.display = 'none';
      ntfSuccess.classList.add('active');
      ntfForm.reset();
    } else {
      const firstError = data.errors ? Object.values(data.errors)[0][0].message : 'Перевірте поля форми.';
      ntfMessage.textContent = firstError;
      ntfMessage.classList.add('is-error');
    }
  } catch (err) {
    ntfMessage.textContent = 'Не вдалося надіслати. Спробуйте ще раз.';
    ntfMessage.classList.add('is-error');
  } finally {
    ntfSubmitBtn.disabled = false;
    ntfSubmitBtn.textContent = 'Увімкнути сповіщення';
  }
});