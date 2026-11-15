'use strict';
const $ = id => document.getElementById(id);
const usd = n => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'USD' }).format(n || 0);
const formatDate = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'время не указано';
function openReason(trade) {
  window.location.href = 'insights.html?fixture=' + encodeURIComponent(trade.fixture_id || '');
}
function predictionName(event, prediction) {
  const [home, away] = String(event || '').split(' vs ');
  if (prediction === 'HOME_WIN') return home ? 'Победа ' + home : 'Победа хозяев';
  if (prediction === 'AWAY_WIN') return away ? 'Победа ' + away : 'Победа гостей';
  return prediction === 'DRAW' ? 'Ничья' : 'Нет прогноза';
}

function card(trade, message) {
  const el = document.createElement('article');
  el.className = 'ledger-row decision-row';
  if (trade.fixture_id) el.tabIndex = 0;
  if (trade.fixture_id) el.setAttribute('role', 'link');
  el.setAttribute('aria-label', 'Открыть причину решения по матчу ' + (trade.event || ''));
  const box = document.createElement('div');
  const title = document.createElement('strong');
  const text = document.createElement('p');
  title.textContent = trade.event || 'Матч';
  text.textContent = 'Прогноз: ' + predictionName(trade.event, trade.prediction) + ' · ' + message;
  box.append(title, text);
  const link = document.createElement('span');
  link.className = 'reason-link';
  link.textContent = 'Почему это решение →';
  el.append(box);
  if (!trade.fixture_id) return el;
  el.append(link);
  el.onclick = () => openReason(trade);
  el.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openReason(trade); } };
  return el;
}

async function load() {
  const status = $('decisions-status');
  try {
    const [paper, broad] = await Promise.all([
      loadOptionalMatchData('paper-trading.json'),
      loadOptionalMatchData('broad-analysis.json'),
    ]);
    if (!paper && !broad) throw Error();
    const now = Date.now();
    const upcoming = item => Date.parse(item.kickoff) > now;
    const ledger = (paper?.trades || []).filter(item => item.status === 'OPEN' && upcoming(item));
    const keys = new Set(ledger.map(footballObservationKey));
    const preliminary = (broad?.matches || []).filter(item => upcoming(item) && !keys.has(footballObservationKey(item)));
    const rows = [...ledger, ...preliminary].sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff));
    renderMatchGroups($('match-decisions'), rows, item => matchCategory(item), item => {
      const detail = hasVirtualStake(item)
        ? 'виртуальная сумма ' + usd(item.stake)
        : item.decision_reasons?.[0] || item.message || 'без ставки';
      return card(item, 'начало: ' + formatDate(item.kickoff) + ' · ' + detail);
    }, 'ledger-list');
    status.textContent = 'Предстоящих матчей: ' + rows.length + '.';
  } catch {
    status.textContent = 'Не удалось загрузить список решений.';
  }
}
load();
