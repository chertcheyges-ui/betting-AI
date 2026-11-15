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
  else note.textContent = 'Начало: ' + date(trade.kickoff) + ' · ждём подтверждённый счёт.';
  if (!live || live.error) note.textContent += ' · прогноз: ' + choice(trade.event, trade.prediction);
  body.append(title, note); item.append(body); return item;
}
async function refresh() {
  try {
    const [paper, wide] = await Promise.all([
      loadOptionalMatchData('paper-trading.json'), loadOptionalMatchData('wide-testing.json'),
    ]);
    if (!paper && !wide) throw Error();
    const now = Date.now();
    const ledger = paper?.trades || [];
    const trades = [...ledger, ...footballObservations(wide, ledger)].filter(item =>
      item.status === 'OPEN' && Date.parse(item.kickoff) <= now);
    const ids = trades.filter(item => !item.observation).map(item => item.fixture_id).filter(Boolean);
    const live = ids.length ? await loadOptionalMatchData('/api/live?ids=' + encodeURIComponent(ids.join(','))) : null;
    const byId = new Map((live?.matches || []).map(item => [String(item.fixture_id), item]));
    renderMatchGroups(root, trades, item => matchCategory(item),
      trade => card(trade, byId.get(String(trade.fixture_id))), 'ledger-list');
    status.textContent = live?.checked_at
      ? 'Последняя проверка: ' + date(live.checked_at) + '.'
      : trades.length ? 'Живой счёт пока недоступен.' : 'Сейчас нет матчей, ожидающих результата.';
  } catch { status.textContent = 'Не удалось получить живой счёт. Повторим проверку автоматически.'; }
}
refresh(); setInterval(refresh, 10 * 60 * 1000);
