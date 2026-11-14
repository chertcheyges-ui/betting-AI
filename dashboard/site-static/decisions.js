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
  el.tabIndex = 0;
  el.setAttribute('role', 'link');
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
  el.append(box, link);
  el.onclick = () => openReason(trade);
  el.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openReason(trade); } };
  return el;
}

async function load() {
  try {
    const response = await fetch('paper-trading.json', { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw Error();
    const all = data.trades || [];
    const approved = all.filter(trade => trade.decision === 'PAPER BET');
    const watch = all.filter(trade => trade.decision === 'WATCH');
    const skip = all.filter(trade => trade.decision === 'NO BET');
    $('approved-count').textContent = approved.length;
    $('watch-count').textContent = watch.length;
    $('skip-count').textContent = skip.length;
    const approvedRoot = $('approved');
    const watchRoot = $('watch');
    const skipRoot = $('skip');
    approvedRoot.replaceChildren();
    watchRoot.replaceChildren();
    skipRoot.replaceChildren();
    if (!approved.length) approvedRoot.textContent = 'Пока я не поставил виртуальные деньги.';
    else approved.forEach(trade => approvedRoot.append(card(trade, 'начало: ' + formatDate(trade.kickoff) + ' · виртуально поставил ' + usd(trade.stake) + (trade.status === 'SETTLED' ? ' · итог: ' + usd(trade.virtual_pnl) + ' · результат подтверждён: ' + formatDate(trade.settled_at) : ' · ждём результат'))));
    if (!watch.length) watchRoot.textContent = 'Все сохранённые прогнозы достаточно уверенные.';
    else watch.forEach(trade => {
      const reason = Array.isArray(trade.decision_reasons) && trade.decision_reasons.length
        ? trade.decision_reasons[0]
        : 'я недостаточно уверен в этом прогнозе.';
      watchRoot.append(card(trade, 'начало: ' + formatDate(trade.kickoff) + ' · ' + reason + (trade.status === 'SETTLED' ? ' · результат подтверждён: ' + formatDate(trade.settled_at) : '')));
    });
    if (!skip.length) skipRoot.textContent = 'Пока нет матчей, которые система полностью отклонила.';
    else skip.forEach(trade => {
      const reason = Array.isArray(trade.decision_reasons) && trade.decision_reasons.length
        ? trade.decision_reasons[0]
        : 'для этого матча не хватает подтверждённых данных.';
      skipRoot.append(card(trade, 'начало: ' + formatDate(trade.kickoff) + ' · ' + reason));
    });
  } catch {
    $('approved').textContent = 'Пока не вижу список решений.';
  }
}
load();
