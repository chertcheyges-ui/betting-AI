'use strict';

const element = id => document.getElementById(id);
const today = () => new Intl.DateTimeFormat('sv-SE', {timeZone: 'Europe/Minsk'}).format(new Date());

async function readAuditData(path) {
  const response = await fetch(path, {cache: 'no-store'});
  if (!response.ok) throw Error();
  return response.json();
}

function auditObservations(matches, analysis, trades) {
  const stakes = new Set(trades.filter(t => t.decision === 'PAPER BET' && Number(t.stake) > 0
    && ['OPEN', 'SETTLED'].includes(t.status)).map(t => String(t.fixture_id)));
  const rows = [];
  for (const match of matches) {
    if (stakes.has(String(match.id))) continue;
    const forecast = basketballForecast(match, analysis);
    const actual = basketballFinalOutcome(match);
    if (actual && ['HOME_WIN', 'AWAY_WIN'].includes(forecast?.prediction)) {
      rows.push({match, forecast, correct: forecast.prediction === actual});
    }
  }
  return rows.sort((a, b) => String(b.match.date || '').localeCompare(String(a.match.date || '')));
}

function missCard({match, forecast}) {
  const card = document.createElement('article');
  card.className = 'match';
  const title = document.createElement('h3');
  title.textContent = match.home + ' — ' + match.away;
  const score = document.createElement('p');
  score.textContent = [match.date, match.home_score + ':' + match.away_score].filter(Boolean).join(' · ');
  card.append(title, score, basketballForecastLine(match, null, forecast));
  if (forecast.reason) {
    const basis = document.createElement('p');
    basis.className = 'meta';
    basis.textContent = forecast.reason;
    card.append(basis);
  }
  return card;
}

async function load() {
  const [report, history, analysis, ledger] = await Promise.allSettled([
    readAuditData('basketball-report.json'), readAuditData('basketball-history.json'),
    loadBasketballForecasts(), readAuditData('basketball-paper-trading.json'),
  ]);
  const snapshot = report.value;
  element('fresh').textContent = snapshot?.requested_date === today() && snapshot?.collection_status === 'success'
    ? 'Готов' : 'Нужно обновить';
  element('matches').textContent = snapshot?.matches?.length ?? '—';
  if (!Array.isArray(history.value?.matches) || !analysis.value || !Array.isArray(ledger.value?.trades)) {
    element('message').textContent = 'Для сверки пока недоступна история, прогнозы или журнал ставок.';
    return;
  }
  const rows = auditObservations(history.value.matches, analysis.value, ledger.value.trades);
  const misses = rows.filter(row => !row.correct);
  element('accuracy').textContent = rows.length ? (rows.length - misses.length) + ' из ' + rows.length : '—';
  element('message').textContent = rows.length
    ? 'Сверены прогнозы без ставки, для которых есть финальный счёт. В карточках показаны данные на момент прогноза.'
    : 'Пока нет прогнозов без ставки с подтверждённым итоговым счётом.';
  const list = element('misses');
  list.replaceChildren(...misses.slice(0, 10).map(missCard));
  if (!misses.length) list.textContent = 'Ошибок среди сверенных прогнозов пока нет.';
}

load();
