(() => {
  const dialog = document.getElementById('figure-viewer');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const image = document.getElementById('figure-image');
  const viewport = dialog.querySelector('.figure-viewport');
  const zoom = document.getElementById('figure-zoom');
  let opener;
  function setZoom(value) {
    viewport.classList.toggle('is-zoomed', value);
    zoom.setAttribute('aria-pressed', String(value));
    zoom.textContent = value ? 'Fit to screen' : 'Zoom in';
  }
  document.querySelectorAll('.figure-link').forEach(link => {
    link.setAttribute('aria-haspopup', 'dialog');
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      image.src = link.href;
      image.alt = link.querySelector('img').alt;
      document.getElementById('figure-title').textContent = link.dataset.figureTitle;
      setZoom(false);
      dialog.showModal();
      document.body.classList.add('figure-open');
      viewport.scrollTo(0, 0);
    });
  });
  zoom.addEventListener('click', () => setZoom(zoom.getAttribute('aria-pressed') !== 'true'));
  document.getElementById('figure-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => {
    document.body.classList.remove('figure-open');
    image.removeAttribute('src');
    opener?.focus({preventScroll: true});
  });
})();
