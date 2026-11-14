'use strict';
const $ = id => document.getElementById(id);
const labels = { HOME_WIN: 'Победа хозяев', DRAW: 'Ничья', AWAY_WIN: 'Победа гостей' };
function predictionName(event, prediction) {
  const [home, away] = String(event || '').split(' vs ');
  if (prediction === 'HOME_WIN') return home ? 'Победа ' + home : labels.HOME_WIN;
  if (prediction === 'AWAY_WIN') return away ? 'Победа ' + away : labels.AWAY_WIN;
  return prediction === 'DRAW' ? 'Ничья' : 'Пока нет выбора';
}
const formatDate = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Время не указано';
const text = value => value === null || value === undefined || value === '' ? 'Нет данных' : String(value);

function pretty(value) {
  return JSON.stringify(value, null, 2)
    .replaceAll('HOME_WIN', 'Победа хозяев')
    .replaceAll('AWAY_WIN', 'Победа гостей')
    .replaceAll('DRAW', 'Ничья');
}

function section(title, value) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = title;
  const pre = document.createElement('pre');
  pre.textContent = value && (typeof value !== 'object' || Object.keys(value).length) ? pretty(value) : 'Источник не дал эти данные.';
  details.append(summary, pre);
  return details;
}

function summary(event, recommendation) {
  const box = document.createElement('p');
  const prediction = predictionName(event, recommendation?.selection || recommendation?.prediction);
  const confidence = Number.isFinite(recommendation?.model_probability) ? ' · уверенность ' + Number(recommendation.model_probability).toFixed(1) + '%' : '';
  const odds = Number.isFinite(recommendation?.odds) ? ' · коэффициент ' + recommendation.odds : '';
  box.textContent = 'Моё предположение: ' + prediction + confidence + odds + '.';
  return box;
}

function decisionReport(trade) {
  const section = $('selected-decision');
  if (!trade) return;
  section.hidden = false;
  const outcome = predictionName(trade.event, trade.prediction);
  const confidence = Number(trade.model_confidence ?? trade.latest_recommendation?.model_probability);
  const confidenceText = Number.isFinite(confidence) ? 'Уверенность: ' + confidence.toFixed(1) + '%.' : 'Уверенность не сохранилась.';
  const heading = document.createElement('h2');
  heading.textContent = 'Решение по матчу: ' + (trade.event || 'Матч');
  const result = document.createElement('p');
  const madeBet = trade.decision === 'PAPER BET';
  result.textContent = madeBet
    ? 'Я виртуально поставил ' + new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'USD' }).format(trade.stake || 0) + ' на исход «' + outcome + '».'
    : 'Я не стал делать виртуальную ставку на исход «' + outcome + '».';
  const reason = document.createElement('p');
  const reasons = Array.isArray(trade.decision_reasons) && trade.decision_reasons.length
    ? trade.decision_reasons.join(' ')
    : Array.isArray(trade.reasons) && trade.reasons.length ? trade.reasons.join(' ') : '';
  if (madeBet) {
    reason.textContent = 'Почему: программа увидела преимущество у этого исхода по сравнению с коэффициентом. ' + confidenceText + (Number.isFinite(Number(trade.edge)) ? ' Преимущество над оценкой букмекера: ' + Number(trade.edge).toFixed(1) + ' процентных пункта.' : '');
  } else {
    reason.textContent = 'Почему не поставил: ' + (reasons || 'для этого прогноза не хватило уверенности или данных.') + ' ' + confidenceText;
  }
  const safeguard = trade.latest_recommendation?.confidence_note;
  if (safeguard) section.append(Object.assign(document.createElement('p'), { className: 'muted', textContent: 'Защита уверенности: ' + safeguard }));
  const hint = document.createElement('p');
  hint.className = 'muted';
  hint.textContent = 'Ниже — форма команд, травмы, коэффициенты и другие данные, на которые опиралась программа.';
  section.append(heading, result, reason, hint);
}

function createCard(name, recommendation, evidence, history, finished) {
  const card = document.createElement('article');
  card.className = 'ledger-row';
  const body = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = name;
  body.append(title, summary(name, recommendation));
  const note = document.createElement('p');
  note.className = 'muted';
  note.textContent = finished
    ? 'Это данные на момент выбора: ' + formatDate(recommendation?.captured_at) + '.'
    : 'Последнее обновление: ' + formatDate(recommendation?.captured_at) + '.';
  body.append(note);
  if (recommendation?.message) body.append(Object.assign(document.createElement('p'), { textContent: 'Пояснение: ' + recommendation.message }));
  body.append(
    section('Форма команд', evidence?.recent_form),
    section('Игра дома и в гостях', evidence?.home_away_form),
    section('Предыдущие встречи команд', evidence?.h2h),
    section('Травмы и отсутствующие игроки', evidence?.injuries),
    section('Составы', evidence?.lineups),
    section('Нагрузка в календаре', evidence?.schedule_load),
    section('Коэффициенты, которые были доступны', evidence?.odds),
    section('Поиск дополнительной информации в интернете', { status: evidence?.external_source_status, searched_for: evidence?.external_search_for, requires_review: evidence?.external_review_required, signals: evidence?.external_signals }),
    section('Что не удалось получить', { missing_data: evidence?.missing_data, collection_errors: evidence?.collection_errors })
  );
  if (Array.isArray(history) && history.length > 1) {
    const changes = document.createElement('details');
    const header = document.createElement('summary');
    header.textContent = 'Как прогноз менялся (' + history.length + ')';
    const list = document.createElement('ul');
    for (const item of history.slice().reverse()) {
      const row = document.createElement('li');
      row.textContent = formatDate(item.captured_at) + ': ' + predictionName(name, item.selection || item.prediction) + (Number.isFinite(item.model_probability) ? ' · уверенность ' + Number(item.model_probability).toFixed(1) + '%' : '');
      list.append(row);
    }
    changes.append(header, list);
    body.append(changes);
  }
  card.append(body);
  return card;
}

async function load() {
  try {
    const [systemResponse, paperResponse, broadResponse] = await Promise.all([
      fetch('system-status.json', { cache: 'no-store' }),
      fetch('paper-trading.json', { cache: 'no-store' }),
      fetch('broad-analysis.json', { cache: 'no-store' }),
    ]);
    const system = await systemResponse.json();
    const paper = await paperResponse.json();
    const broad = broadResponse.ok ? await broadResponse.json() : { matches: [] };
    if (!systemResponse.ok || !paperResponse.ok) throw Error();
    const selectedId = new URLSearchParams(window.location.search).get('fixture');
    const selectedTrade = (paper.trades || []).find(trade => String(trade.fixture_id) === String(selectedId));
    decisionReport(selectedTrade);
    const wideRoot = $('wide-scan');
    wideRoot.replaceChildren();
    const detailedIds = new Set((system.analysis?.match_details || []).map(item => String(item.fixture_id)));
    const detailedEvents = new Set((system.analysis?.forecasts || []).map(item => String(item.event)));
    const scheduled = system.research?.fixtures || [];
    const wideMatches = scheduled.length ? scheduled : (broad.matches || []);
    if (!wideMatches.length) wideRoot.textContent = 'Список матчей появится после следующего обновления расписания.';
    for (const match of wideMatches) {
      const row = document.createElement('article');
      row.className = 'ledger-row';
      const info = document.createElement('div');
      const title = document.createElement('strong');
      const note = document.createElement('p');
      const hasDetail = detailedIds.has(String(match.fixture_id ?? match.match_id)) || detailedEvents.has(String(match.event));
      title.textContent = match.event || 'Матч';
      const basic = (match.league || 'Лига не указана') + ' · начало: ' + formatDate(match.kickoff);
      const firstPass = match.confidence === null || match.confidence === undefined
        ? '' : ' · первый прогноз: ' + predictionName(match.event, match.prediction) + ' · уверенность ' + match.confidence + '%';
      note.textContent = basic + firstPass + ' · ' + (hasDetail ? 'подробно проверяется' : 'в очереди на подробную проверку');
      info.append(title, note);
      row.append(info);
      wideRoot.append(row);
    }
    const future = $('future');
    const past = $('past');
    future.replaceChildren();
    past.replaceChildren();
    const details = (system.analysis?.match_details || []).length
      ? system.analysis.match_details
      : (system.analysis?.forecasts || []).map(recommendation => ({
          fixture_id: recommendation.fixture_id,
          event: recommendation.event,
          kickoff: recommendation.kickoff,
          recommendation,
          evidence: recommendation.evidence || {},
        }));
    if (!details.length) future.textContent = 'Пока нет будущих матчей с собранными данными.';
    const orderedDetails = selectedId ? details.slice().sort((a, b) => String(b.fixture_id) === String(selectedId) ? 1 : String(a.fixture_id) === String(selectedId) ? -1 : 0) : details;
    for (const item of orderedDetails) {
      const trade = (paper.trades || []).find(value => String(value.fixture_id) === String(item.fixture_id));
      const recommendation = trade?.latest_recommendation || item.recommendation;
      future.append(createCard(item.event || 'Матч', recommendation, recommendation?.evidence || item.evidence, trade?.recommendation_history, false));
    }
    const completed = (paper.trades || []).filter(trade => trade.status === 'SETTLED');
    if (!completed.length) past.textContent = 'Завершённых матчей с прогнозом пока нет.';
    const orderedCompleted = completed.slice().reverse().sort((a, b) => String(b.fixture_id) === String(selectedId) ? 1 : String(a.fixture_id) === String(selectedId) ? -1 : 0);
    for (const trade of orderedCompleted) {
      const original = (trade.recommendation_history || [])[0] || trade.latest_recommendation || {};
      past.append(createCard(trade.event || 'Матч', original, trade.evidence_at_decision || original.evidence, trade.recommendation_history, true));
    }
  } catch {
    $('wide-scan').textContent = 'Пока не удалось открыть широкий список матчей.';
    $('future').textContent = 'Пока не удалось открыть данные матчей.';
    $('past').textContent = 'Пока не удалось открыть сохранённые данные прошлых матчей.';
  }
}
load();
