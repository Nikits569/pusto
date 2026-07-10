document.querySelectorAll('.copyText').forEach(el => {
    el.addEventListener('click', () => {
        const content = el.dataset.content;

        navigator.clipboard.writeText(content).then(() => {
            alert('Текст скопирован');
        });
    });
})