'use strict';
const basketballNavStyle = document.createElement('link');
basketballNavStyle.rel = 'stylesheet'; basketballNavStyle.href = 'basketball-nav.css';
document.head.append(basketballNavStyle);
const nav = document.querySelector('[data-basketball-nav]');
if (nav) {
  const page = location.pathname.split('/').pop() || 'basketball.html';
  const active = href => page === href ? ' class="active"' : '';
  const matchesOpen = ['basketball.html','basketball-decisions.html','basketball-live.html','basketball-completed.html'].includes(page) ? ' open' : '';
  nav.innerHTML = `<a href="index.html">Футбол</a><details${matchesOpen}><summary>Баскетбол · Матчи</summary><div class="basket-nav-links"><a href="basketball-decisions.html"${active('basketball-decisions.html')}>В обработке</a><a href="basketball-live.html"${active('basketball-live.html')}>Ждут результата</a><a href="basketball-completed.html"${active('basketball-completed.html')}>Готовые</a></div></details><a href="basketball-history.html"${active('basketball-history.html')}>История</a><a href="basketball-audit.html"${active('basketball-audit.html')}>Аудитор</a><a href="finance.html">Финансы</a>`;
  const menu = nav.querySelector('details');
  menu.addEventListener('mouseenter', () => menu.open = true);
  menu.addEventListener('mouseleave', () => { if (!matchesOpen) menu.open = false; });
}
