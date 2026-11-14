'use strict';
const root = document.getElementById('history-list');
const updated = document.getElementById('updated');
const formatDate = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'время не указано';
const outcome = (event, value) => {
  const [home, away] = String(event || '').split(' vs ');
  return value === 'HOME_WIN' ? 'победа ' + (home || 'хозяев') : value === 'AWAY_WIN' ? 'победа ' + (away || 'гостей') : value === 'DRAW' ? 'ничья' : 'нет данных';
};
const eventName = match => match.event || ((match.home || 'Команда') + ' vs ' + (match.away || 'Команда'));

function card(match, trade) {
  const item = document.createElement('article'); item.className = 'match-card';
  const title = document.createElement('h3'); title.textContent = eventName(match);
  const score = document.createElement('p'); score.className = 'fixture-score';
  score.textContent = Number.isInteger(match.goals_home) && Number.isInteger(match.goals_away) ? match.goals_home + ' : ' + match.goals_away : 'Счёт не указан';
  const details = document.createElement('p'); details.className = 'muted'; details.textContent = (match.league || 'Лига не указана') + ' · начало: ' + formatDate(match.kickoff);
  const forecast = document.createElement('p'); forecast.className = 'muted';
  forecast.textContent = trade
    ? (trade.was_correct ? '✅ Прогноз совпал' : '❌ Прогноз не совпал') + ' · прогноз: ' + outcome(eventName(match), trade.prediction) + ' · виртуальный итог: ' + new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'USD' }).format(trade.virtual_pnl || 0)
    : 'По этому матчу система не делала отдельный прогноз.';
  item.append(title, score, details, forecast); return item;
}
async function load() {
  try {
    const [historyResponse, paperResponse] = await Promise.all([fetch('history.json', { cache: 'no-store' }), fetch('paper-trading.json', { cache: 'no-store' })]);
    const history = await historyResponse.json(); const paper = await paperResponse.json(); if (!historyResponse.ok || !paperResponse.ok) throw Error();
    const trades = new Map((paper.trades || []).filter(item => item.status === 'SETTLED').map(item => [String(item.fixture_id), item]));
    const records = new Map((history.matches || []).map(item => [String(item.fixture_id), item]));
    trades.forEach((trade, id) => { if (!records.has(id)) { const [home, away] = String(trade.event || '').split(' vs '); records.set(id, { fixture_id: trade.fixture_id, home, away, kickoff: trade.kickoff }); } });
    const all = [...records.values()].sort((a, b) => String(b.kickoff || '').localeCompare(String(a.kickoff || '')));
    root.replaceChildren();
    if (!all.length) { updated.textContent = 'Завершённых матчей пока нет.'; return; }
    all.forEach(match => root.append(card(match, trades.get(String(match.fixture_id)))));
    updated.textContent = 'В полном архиве: ' + all.length + ' завершённых матчей. Прогноз отмечен там, где он был сделан.';
  } catch { updated.textContent = 'Не удалось загрузить историю.'; }
}
load();
