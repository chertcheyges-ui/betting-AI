'use strict';
const $ = id => document.getElementById(id);
function outcome(event, value) {
  const [home, away] = String(event || '').split(' vs ');
  if (value === 'HOME_WIN') return 'победа ' + (home || 'хозяев');
  if (value === 'AWAY_WIN') return 'победа ' + (away || 'гостей');
  return value === 'DRAW' ? 'ничья' : 'нет данных';
}
function card(title, text) {
  const item = document.createElement('article'); item.className = 'ledger-row';
  const body = document.createElement('div'); const heading = document.createElement('strong'); const note = document.createElement('p');
  heading.textContent = title; note.textContent = text; body.append(heading, note); item.append(body); return item;
}
async function load() {
  try {
    const response = await fetch('audit-report.json', { cache: 'no-store' });
    const report = await response.json(); if (!response.ok) throw Error();
    $('tested').textContent = report.tested ?? '—'; $('correct').textContent = report.correct ?? '—';
    $('accuracy').textContent = report.accuracy === null || report.accuracy === undefined ? '—' : report.accuracy.toFixed(1) + '%';
    $('summary').textContent = report.summary || 'Отчёт пока недоступен.';
    const mistakes = $('mistakes'); mistakes.replaceChildren();
    if (!(report.mistakes || []).length) mistakes.textContent = 'Пока нет ошибок для разбора.';
    (report.mistakes || []).forEach(item => {
      const gap = item.gap === null || item.gap === undefined ? '' : ' Разница с ближайшим исходом: ' + item.gap + ' п.п.';
      const odds = Number(item.odds) > 1 ? ' Коэффициент был ' + Number(item.odds).toFixed(2) + '.' : ' Коэффициент не был доступен.';
      mistakes.append(card(item.event, 'Я ожидал: ' + outcome(item.event, item.prediction) + '. Получилось: ' + outcome(item.event, item.actual_outcome) + '. Уверенность была ' + item.confidence + '%. ' + odds + ' ' + (item.reasons || []).join(' ') + gap));
    });
    const results = $('results'); results.replaceChildren();
    if (!(report.results || []).length) results.textContent = 'Завершённых прогнозов пока нет.';
    (report.results || []).forEach(item => {
      const odds = Number(item.odds) > 1 ? Number(item.odds).toFixed(2) : '—';
      const status = item.was_correct ? '✓ Прогноз сыграл' : '✕ Прогноз не сыграл';
      results.append(card(item.event, status + ' · прогноз: ' + outcome(item.event, item.prediction) + ' · итог: ' + outcome(item.event, item.actual_outcome) + ' · коэффициент: ' + odds + ' · уверенность: ' + item.confidence + '%.' ));
    });
    const improvements = $('improvements'); improvements.replaceChildren();
    const applied = report.applied_changes || [];
    applied.forEach(item => improvements.append(card(item.title, item.text)));
    (report.learning_actions || []).forEach(item => improvements.append(card(item.title, item.text)));
    (report.by_decision || []).forEach(item => improvements.append(card(
      'Точность: ' + item.label,
      'Проверено: ' + item.tested + ' · совпало: ' + item.correct + ' · точность: ' + (item.accuracy === null ? '—' : item.accuracy + '%') + '.'
    )));
    (report.improvements || []).forEach(item => improvements.append(card(item.title, item.text)));
    if (!applied.length && !(report.improvements || []).length) improvements.textContent = 'После следующей проверки здесь появится список улучшений.';
    const reliability = $('reliability'); reliability.replaceChildren();
    const groups = [...(report.reliability?.leagues || []), ...(report.reliability?.teams || [])];
    if (!groups.length) reliability.textContent = 'Рейтинг появится после завершённых матчей.';
    groups.forEach(item => reliability.append(card(item.name, 'Проверено: ' + item.tested + ' · точность: ' + (item.accuracy === null ? '—' : item.accuracy + '%') + ' · ' + item.status + '.')));
    const patterns = report.patterns || {};
    const patternRoot = $('patterns'); patternRoot.replaceChildren();
    patternRoot.append(
      card('Слабая уверенность', (patterns.low_confidence || 0) + ' завершённых прогнозов были сделаны с уверенностью ниже 45%.'),
      card('Почти равные шансы', (patterns.close_calls || 0) + ' прогнозов имели слишком близкие варианты исхода.'),
      card('Составы', (patterns.missing_lineups || 0) + ' завершённых прогнозов были без подтверждённых составов.'),
      card('Травмы', (patterns.missing_injuries || 0) + ' завершённых прогнозов были без данных о травмах.')
    );
  } catch {
    $('summary').textContent = 'Отчёт аудитора появится после ближайшего обновления программы.';
  }
}
load();
