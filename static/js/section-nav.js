(() => {
  const nav = document.querySelector('.section-nav');
  const toggle = document.querySelector('.section-nav-toggle');
  const links = [...nav.querySelectorAll('a')];
  const sections = links.map(link => document.getElementById(link.hash.slice(1)));
  const close = () => {
    toggle.setAttribute('aria-expanded', 'false');
    toggle.querySelector('span').textContent = '+';
  };
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    toggle.querySelector('span').textContent = open ? '−' : '+';
  });
  nav.addEventListener('click', event => {
    if (event.target.closest('a')) close();
  });
  nav.addEventListener('keydown', event => {
    if (event.key === 'Escape') { close(); toggle.focus(); }
  });
  let pending = false;
  const update = () => {
    pending = false;
    let current = 0;
    sections.forEach((section, index) => {
      if (section.getBoundingClientRect().top <= 110) current = index;
    });
    links.forEach((link, index) => {
      if (index === current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  const schedule = () => {
    if (!pending) { pending = true; requestAnimationFrame(update); }
  };
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  window.addEventListener('load', schedule);
  document.fonts.ready.then(schedule);
  update();
})();
