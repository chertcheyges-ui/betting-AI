'use strict';

function renderApprovedBets(root, ledger, outcomeName) {
  const node = (tag, label) => {
    const element = document.createElement(tag);
    element.textContent = label;
    return element;
  };
  root.replaceChildren();
  if (!Array.isArray(ledger?.trades)) {
    root.append(node('p', 'Журнал виртуальных ставок пока недоступен.'));
    return;
  }

  const bets = ledger.trades.filter(trade =>
    trade?.decision === 'PAPER BET' && Number(trade.stake) > 0
    && ['OPEN', 'SETTLED'].includes(trade.status)
  );
  const active = bets.filter(trade => trade.status === 'OPEN');
  const recent = bets.filter(trade => trade.status === 'SETTLED')
    .sort((a, b) => String(b.settled_at || '').localeCompare(String(a.settled_at || '')))
    .slice(0, 3);
  const money = new Intl.NumberFormat('ru-RU', {style: 'currency', currency: 'USD'});

  if (!active.length) root.append(node('p', 'Сейчас открытых виртуальных ставок нет.'));
  for (const [title, items] of [['Открытые виртуальные ставки', active], ['Последние завершённые ставки', recent]]) {
    if (!items.length) continue;
    root.append(node('h3', title));
    const list = document.createElement('ul');
    for (const trade of items) {
      const details = [outcomeName(trade.event, trade.prediction), money.format(trade.stake)];
      if (Number(trade.odds) > 1) details.push('коэффициент ' + Number(trade.odds).toFixed(2));
      if (trade.status === 'SETTLED') {
        if (trade.was_correct === true) details.push('ставка сыграла');
        if (trade.was_correct === false) details.push('ставка не сыграла');
      }
      const line = document.createElement('li');
      line.append(node('strong', trade.event || 'Матч'), node('p', details.join(' · ')));
      list.append(line);
    }
    root.append(list);
  }
}
