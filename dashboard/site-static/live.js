'use strict';
const root = document.getElementById('live-matches');
const status = document.getElementById('live-status');
const date = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'время не указано';
const choice = (event, prediction) => {
  const [home, away] = String(event || '').split(' vs ');
  return prediction === 'HOME_WIN' ? 'Победа ' + (home || 'хозяев') : prediction === 'AWAY_WIN' ? 'Победа ' + (away || 'гостей') : prediction === 'DRAW' ? 'Ничья' : 'Нет прогноза';
};
function card(trade, live) {
  const item = document.createElement('article'); item.className = 'ledger-row';
  const body = document.createElement('div'); const title = document.createElement('strong'); const note = document.createElement('p');
  title.textContent = trade.event || 'Матч';
  if (live?.error) note.textContent = 'Начало: ' + date(trade.kickoff) + ' · временно не удалось получить счёт.';
  else if (live) note.textContent = 'Счёт: ' + (live.goals_home ?? '—') + ' : ' + (live.goals_away ?? '—') + ' · ' + (live.status_text || live.status || 'статус уточняется') + (live.elapsed ? ' · ' + live.elapsed + ' мин.' : '') + ' · прогноз: ' + choice(trade.event, trade.prediction);
  else note.textContent = 'Начало: ' + date(trade.kickoff) + ' · матч ещё не получен от источника.';
  body.append(title, note); item.append(body); return item;
}
async function refresh() {
  try {
    const paperResponse = await fetch('paper-trading.json', { cache: 'no-store' });
    const paper = await paperResponse.json(); if (!paperResponse.ok) throw Error();
    const trades = (paper.trades || []).filter(item => item.status === 'OPEN');
    if (!trades.length) { root.textContent = 'Сейчас нет открытых виртуальных прогнозов.'; status.textContent = 'Нет матчей для живой проверки.'; return; }
    const ids = trades.map(item => item.fixture_id).filter(Boolean);
    const liveResponse = await fetch('/api/live?ids=' + encodeURIComponent(ids.join(',')), { cache: 'no-store' });
    const live = await liveResponse.json(); if (!liveResponse.ok) throw Error();
    const byId = new Map((live.matches || []).map(item => [String(item.fixture_id), item]));
    root.replaceChildren(); trades.forEach(trade => root.append(card(trade, byId.get(String(trade.fixture_id)))));
    status.textContent = 'Последняя проверка: ' + date(live.checked_at) + '. Следующая — автоматически примерно через 10 минут.';
  } catch { status.textContent = 'Не удалось получить живой счёт. Повторим проверку автоматически.'; }
}
refresh(); setInterval(refresh, 10 * 60 * 1000);
