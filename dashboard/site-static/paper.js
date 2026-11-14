'use strict';
const $ = id => document.getElementById(id);
const labels = { HOME_WIN: 'Победа хозяев', DRAW: 'Ничья', AWAY_WIN: 'Победа гостей' };
const formatDate = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'время не указано';
function predictionName(event, prediction) {
  const [home, away] = String(event || '').split(' vs ');
  if (prediction === 'HOME_WIN') return home ? 'Победа ' + home : labels.HOME_WIN;
  if (prediction === 'AWAY_WIN') return away ? 'Победа ' + away : labels.AWAY_WIN;
  return prediction === 'DRAW' ? 'Ничья' : 'без прогноза';
}

async function run() {
  try {
    const response = await fetch('wide-testing.json', { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw Error();
    $('total').textContent = data.total_count;
    $('settled').textContent = data.settled_count;
    $('accuracy').textContent = data.accuracy === null ? '—' : (data.accuracy * 100).toFixed(1) + '%';
    $('metrics').textContent = data.settled_count
      ? 'Проверено ' + data.settled_count + ' матчей. Точность — сколько раз прогноз совпал с результатом.'
      : 'Прогнозы уже сохранены до матчей. Когда игры закончатся, я сам сравню их с результатами.';
    const root = $('trades');
    root.replaceChildren();
    const tests = data.tests || [];
    if (!tests.length) {
      root.textContent = 'Первый список из 50 матчей появится после следующего обновления.';
      return;
    }
    for (const test of tests.slice().reverse().slice(0, 50)) {
      const row = document.createElement('article');
      row.className = 'ledger-row';
      const info = document.createElement('div');
      const title = document.createElement('strong');
      const note = document.createElement('p');
      title.textContent = (test.event || 'Матч') + ' · ' + predictionName(test.event, test.prediction);
      note.textContent = test.status === 'OPEN'
        ? 'Начало: ' + formatDate(test.kickoff) + ' · ждём результат · это тест без денег.'
        : 'Начало: ' + formatDate(test.kickoff) + ' · результат: ' + predictionName(test.event, test.actual_outcome) + ' · ' + (test.was_correct ? 'я угадал' : 'не угадал') + ' · результат подтверждён: ' + formatDate(test.settled_at);
      info.append(title, note);
      const badge = document.createElement('span');
      badge.className = 'ledger-amount ' + (test.status === 'OPEN' ? '' : test.was_correct ? 'income' : 'expense');
      badge.textContent = test.status === 'OPEN' ? 'ЖДЁМ' : test.was_correct ? 'УГАДАЛ' : 'НЕ УГАДАЛ';
      row.append(info, badge);
      root.append(row);
    }
  } catch {
    $('trades').textContent = 'Пока не вижу данные большого теста.';
  }
}
run();
