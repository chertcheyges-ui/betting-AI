'use strict';
const $ = id => document.getElementById(id);
const usd = value => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'USD' }).format(value || 0);
const formatDate = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'В начале проверки';
let operations = [];
function openReason(trade) {
  window.location.href = 'insights.html?fixture=' + encodeURIComponent(trade.fixture_id || '');
}
function predictionName(event, prediction) {
  const [home, away] = String(event || '').split(' vs ');
  if (prediction === 'HOME_WIN') return home ? 'Победа ' + home : 'Победа хозяев';
  if (prediction === 'AWAY_WIN') return away ? 'Победа ' + away : 'Победа гостей';
  return prediction === 'DRAW' ? 'Ничья' : 'Нет прогноза';
}

function renderOperations(rows) {
  const root = $('ledger-list');
  root.replaceChildren();
  if (!rows.length) {
    root.textContent = 'Операций пока нет.';
    return;
  }
  for (const row of rows) {
    const el = document.createElement('article');
    el.className = 'ledger-row';
    const info = document.createElement('div');
    const title = document.createElement('strong');
    const note = document.createElement('p');
    title.textContent = row.title || 'Виртуальная операция';
    note.textContent = formatDate(row.date) + (row.note ? ' · ' + row.note : '');
    info.append(title, note);
    const amount = document.createElement('span');
    amount.className = 'ledger-amount ' + (row.type === 'income' ? 'income' : 'expense');
    amount.textContent = row.type === 'income' ? '+' + usd(row.amount) : (row.type === 'expense' || row.type === 'loss') ? '−' + usd(row.amount) : '—';
    el.append(info, amount);
    root.append(el);
  }
}

function downloadCsv() {
  const csv = ['date,type,amount_usd,title,note', ...operations.map(row => [
    row.date || '', row.type || '', row.amount || 0,
    '"' + String(row.title || '').replaceAll('"', '""') + '"',
    '"' + String(row.note || '').replaceAll('"', '""') + '"',
  ].join(','))].join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  link.download = 'betting-ai-virtual-finances.csv';
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

async function renderPaper() {
  try {
    const response = await fetch('shared-finance.json', { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw Error();
    $('paper-bankroll').textContent = usd(data.bankroll);
    $('paper-exposure').textContent = usd(data.open_exposure);
    $('paper-reserve').textContent = usd(data.profit_reserve);
    const settled = (data.trades || []).filter(item => item.status === 'SETTLED' && item.decision === 'PAPER BET');
    const won = settled.filter(item => item.was_correct).reduce((sum, item) => sum + Math.max(0, Number(item.virtual_pnl) || 0), 0);
    const lost = settled.filter(item => !item.was_correct).reduce((sum, item) => sum + Math.abs(Math.min(0, Number(item.virtual_pnl) || 0)), 0);
    $('paper-won').textContent = '+' + usd(won);
    $('paper-lost').textContent = '−' + usd(lost);
    $('paper-pnl').textContent = (data.virtual_pnl >= 0 ? '+' : '') + usd(data.virtual_pnl);
    const policy = data.financial_policy || {};
    const minMatches = Number(policy.limit_review_min_matches) || 20;
    const targetMatches = Number(policy.limit_review_target_matches) || 50;
    const completed = Number(data.settled_count) || 0;
    $('financial-policy').textContent = (Number(policy.profit_reserve_percent) || 50) + '% каждого выигрыша остаётся в резерве · после проигрыша сумма следующей ставки не увеличивается · лимиты пересмотрим только после ' + minMatches + '–' + targetMatches + ' завершённых матчей. Сейчас: ' + completed + '.';
    const latest = data.latest_result;
    if (latest) {
      $('latest-result').hidden = false;
      const result = latest.was_correct ? 'Виртуальная ставка сыграла.' : 'Виртуальная ставка не сыграла.';
      $('latest-result-text').textContent = (latest.event || 'Матч') + ' · ' + result + ' Изменение банка: ' + (latest.virtual_pnl >= 0 ? '+' : '') + usd(latest.virtual_pnl) + '. Начало: ' + formatDate(latest.kickoff) + '. Результат подтверждён: ' + formatDate(latest.settled_at) + '.';
    }
    const reservePercent = Number(data.profit_reserve_percent) || 50;
    $('paper-finance-note').textContent = 'Старт: ' + usd(data.starting_bankroll) + ' · свободно для новых ставок: ' + usd(data.available_bankroll) + ' · ' + reservePercent + '% выигрыша сохранено в резерве · только виртуальные деньги.';
    const root = $('paper-finance-list');
    root.replaceChildren();
    const trades = data.trades || [];
    if (!trades.length) root.textContent = 'Пока я не поставил виртуальные деньги.';
    for (const trade of trades.slice().reverse()) {
      const row = document.createElement('article');
      row.className = 'ledger-row decision-row';
      row.tabIndex = 0;
      row.setAttribute('role', 'link');
      row.setAttribute('aria-label', 'Открыть причину решения по матчу ' + (trade.event || ''));
      const info = document.createElement('div');
      const name = document.createElement('strong');
      const note = document.createElement('p');
      let status;
      if (trade.status === 'CANCELLED') status = 'СТАВКА ОТМЕНЕНА';
      else if (trade.decision !== 'PAPER BET') status = 'СТАВКУ НЕ ДЕЛАЛ';
      else if (trade.status !== 'SETTLED') status = 'ЖДЁМ РЕЗУЛЬТАТ СТАВКИ';
      else status = trade.was_correct ? '✓ СТАВКА СЫГРАЛА' : '✕ СТАВКА НЕ СЫГРАЛА';
      name.textContent = (trade.sport === 'basketball' ? 'Баскетбол · ' : '') + (trade.event || 'Матч') + ' · ' + status;
      const decision = trade.decision === 'PAPER BET' ? 'сумма: ' + usd(trade.stake) : 'без виртуальной ставки';
      const odds = Number(trade.odds) > 1 ? ' · коэффициент: ' + Number(trade.odds).toFixed(2) : ' · коэффициент: нет данных';
      const ending = trade.status === 'CANCELLED' ? ' · ' + (trade.cancellation_reason || 'Ставка отменена.') : trade.status === 'SETTLED' ? ' · итог: ' + usd(trade.virtual_pnl) + ' · результат подтверждён: ' + formatDate(trade.settled_at) + (trade.score_source ? ' · источник счёта: ' + trade.score_source : '') : ' · ждём результат';
      note.textContent = 'Начало: ' + formatDate(trade.kickoff) + ' · прогноз: ' + predictionName(trade.event, trade.prediction) + odds + ' · ' + decision + ending;
      info.append(name, note);
      const link = document.createElement('span');
      link.className = 'reason-link';
      link.textContent = 'Почему это решение →';
      row.append(info, link);
      row.onclick = () => openReason(trade);
      row.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openReason(trade); } };
      root.append(row);
    }
    operations = data.operations || [];
    renderOperations(operations);
  } catch {
    $('paper-finance-note').textContent = 'Пока не вижу данные виртуального банка.';
  }
}

$('export-ledger').onclick = downloadCsv;
renderPaper();
