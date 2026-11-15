'use strict';

function hasVirtualStake(trade) {
  return trade?.decision === 'PAPER BET' && Number(trade.stake) > 0
    && ['OPEN', 'SETTLED'].includes(trade.status);
}

function matchCategory(trade, prediction = trade?.prediction) {
  if (hasVirtualStake(trade)) return 'stake';
  return ['HOME_WIN', 'DRAW', 'AWAY_WIN'].includes(prediction) ? 'forecast' : 'pending';
}

function renderMatchGroups(root, rows, category, card, listClass) {
  root.replaceChildren();
  const groups = new Map([['stake', []], ['forecast', []], ['pending', []]]);
  for (const row of rows) groups.get(category(row)).push(row);
  for (const [key, title] of [
    ['stake', 'Ставки с виртуальной суммой'],
    ['forecast', 'Прогнозы без ставки'],
    ['pending', 'Матчи без прогноза'],
  ]) {
    const items = groups.get(key);
    if (key === 'pending' && !items.length) continue;
    const section = document.createElement('section');
    section.style.gridColumn = '1 / -1';
    const heading = document.createElement('h3');
    heading.textContent = title;
    const list = document.createElement('div');
    list.className = listClass;
    if (items.length) {
      for (const item of items) list.append(card(item));
    } else {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'В этой группе пока нет матчей.';
      list.append(empty);
    }
    section.append(heading, list);
    root.append(section);
  }
}

async function loadOptionalMatchData(file) {
  try {
    const response = await fetch(file, {cache: 'no-store'});
    if (response.ok) return await response.json();
  } catch {
    // The main match list is still usable.
  }
  return null;
}

function footballObservationKey(item) {
  return String(item.event || '').trim().toLowerCase() + '|' + Date.parse(item.kickoff);
}

function footballObservations(wide, trades) {
  const booked = new Set(trades.map(footballObservationKey));
  return (wide?.tests || []).filter(item =>
    matchCategory(null, item.prediction) === 'forecast' && !booked.has(footballObservationKey(item))
  ).map(item => ({...item, fixture_id: 'wide-' + item.match_id, observation: true}));
}
