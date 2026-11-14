'use strict';

async function loadBasketballForecasts() {
  try {
    const response = await fetch('basketball-analysis.json', {cache: 'no-store'});
    if (response.ok) return await response.json();
  } catch {
    // Match scores and recorded bets can still be displayed.
  }
  return null;
}

function basketballForecastLine(match, analysis, currentForecast) {
  const line = document.createElement('p');
  line.className = 'meta';
  const forecast = currentForecast || analysis?.forecast_history?.[String(match.id)]
    || analysis?.recommendations?.find(item => String(item.match_id) === String(match.id));
  const team = {HOME_WIN: match.home, AWAY_WIN: match.away}[forecast?.prediction];
  if (!team) {
    line.textContent = analysis ? 'Прогноз без ставки не сохранён.' : 'Прогнозы временно недоступны.';
    return line;
  }

  const details = ['Прогноз без ставки: победа ' + team];
  const final = ['FT', 'FINAL', 'AOT'].includes(String(match.status).trim().toUpperCase());
  const validScore = value => value != null && String(value).trim() !== ''
    && Number.isInteger(Number(value)) && Number(value) >= 0;
  if (final && validScore(match.home_score) && validScore(match.away_score)
      && Number(match.home_score) !== Number(match.away_score)) {
    const winner = Number(match.home_score) > Number(match.away_score) ? 'HOME_WIN' : 'AWAY_WIN';
    details.push(forecast.prediction === winner ? '✓ Прогноз угадан' : '✕ Прогноз не угадан');
  } else {
    details.push(final ? 'Итоговый счёт уточняется' : 'Ждём итоговый счёт');
  }
  line.textContent = details.join(' · ');
  return line;
}
