'use strict';
const root = document.getElementById('completed-list');
const status = document.getElementById('completed-status');
const KEY = 'betting-ai-viewed-matches-v1';
const formatDate = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'время не указано';
const matchDay = trade => {
  // "Готовые" are organised by the day the result was confirmed, not by
  // kickoff. A match played late yesterday may be settled after midnight.
  const value = trade.settled_at || trade.kickoff;
  return value ? new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Minsk' }).format(new Date(value)) : 'without-date';
};
const matchDayTitle = key => key === 'without-date' ? 'Дата матча не указана' : new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Minsk', dateStyle: 'full' }).format(new Date(key + 'T12:00:00+03:00'));
const today = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Minsk' }).format(new Date());
const outcome = (event, value) => {
  const [home, away] = String(event || '').split(' vs ');
  if (value === 'HOME_WIN') return 'победа ' + (home || 'хозяев');
  if (value === 'AWAY_WIN') return 'победа ' + (away || 'гостей');
  return value === 'DRAW' ? 'ничья' : 'нет данных';
};
function viewed() { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; } }
function markViewed(id) { const items = viewed(); items[id] = new Date().toISOString(); localStorage.setItem(KEY, JSON.stringify(items)); }
function card(trade) {
  const item = document.createElement('article'); item.className = 'ledger-row';
  const body = document.createElement('div'); const heading = document.createElement('strong'); const note = document.createElement('p');
  heading.textContent = (trade.was_correct ? '✅ ' : '❌ ') + (trade.event || 'Матч');
  const actual = outcome(trade.event, trade.actual_outcome);
  const result = trade.was_correct ? '✅ Ставка сыграла.' : '❌ Ставка не сыграла.';
  const source = trade.score_source ? ' Источник счёта: ' + trade.score_source + '.' : '';
  note.textContent = result + ' Прогноз: ' + outcome(trade.event, trade.prediction) + '. Итог: ' + actual + '. Результат подтверждён: ' + formatDate(trade.settled_at) + '.' + source;
  const button = document.createElement('button'); button.className = 'primary'; button.textContent = 'Просмотрена';
  button.addEventListener('click', () => { markViewed(String(trade.fixture_id)); item.remove(); const left = root.children.length; status.textContent = left ? 'Осталось непросмотренных матчей: ' + left + '.' : 'Все готовые матчи просмотрены и перенесены в историю.'; });
  body.append(heading, note); item.append(body, button); return item;
}
async function load() {
  try {
    const response = await fetch('paper-trading.json', { cache: 'no-store' }); const paper = await response.json(); if (!response.ok) throw Error();
    const seen = viewed(); const currentDay = today();
    const trades = (paper.trades || []).filter(item => item.status === 'SETTLED' && Number(item.stake || 0) > 0 && !seen[String(item.fixture_id)] && matchDay(item) === currentDay);
    root.replaceChildren();
    if (!trades.length) { status.textContent = 'Сегодня готовых ставок пока нет. Тесты без денег и матчи прошлых дней находятся в истории.'; return; }
    const heading = document.createElement('h2');
    heading.textContent = 'Матчи за ' + matchDayTitle(currentDay);
    const list = document.createElement('div');
    list.className = 'ledger-list';
    trades.sort((a, b) => String(b.kickoff || '').localeCompare(String(a.kickoff || ''))).forEach(trade => list.append(card(trade)));
    root.append(heading, list);
    status.textContent = 'Готово к просмотру сегодня: ' + trades.length + '.';
  } catch { status.textContent = 'Не удалось загрузить готовые матчи. Попробуй обновить страницу.'; }
}
load();
