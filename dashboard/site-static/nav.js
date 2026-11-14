'use strict';

const contrast = document.createElement('link');
contrast.rel = 'stylesheet';
contrast.href = 'contrast.css';
document.head.append(contrast);

// Four clear areas of the dashboard. The first one contains the three stages
// through which every analysed match passes.
const nav = document.querySelector('header nav');
if (nav) {
  const page = location.pathname.split('/').pop() || 'index.html';
  const current = href => page === href ? ' aria-current="page"' : '';
  const matchesCurrent = ['index.html', 'decisions.html', 'live.html', 'completed.html'].includes(page);
  nav.className = 'section-nav';
  nav.innerHTML = `
    <details class="nav-group"${matchesCurrent ? ' open' : ''}>
      <summary>Матчи</summary>
      <div class="nav-links">
        <a href="decisions.html"${current('decisions.html')}>В обработке</a>
        <a href="live.html"${current('live.html')}>Ждут результата</a>
        <a href="completed.html"${current('completed.html')}>Готовые</a>
      </div>
    </details>
    <a class="nav-main-link" href="paper.html"${current('paper.html')}>История</a>
    <a class="nav-main-link" href="audit.html"${current('audit.html')}>Аудитор</a>
    <a class="nav-main-link" href="finance.html"${current('finance.html')}>Финансы</a>
    <a class="nav-main-link" href="basketball.html">Баскетбол</a>`;
}
