'use strict';
const $ = id => document.getElementById(id);
const date = value => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Minsk' }).format(new Date(value)) : 'Время уточняется';
const state = value => ({FT:'Завершён',NS:'Не начался',LIVE:'В игре',POSTPONED:'Перенесён'})[value] || value || 'Статус уточняется';
function kickoff(match) { return match.date && match.time ? match.date + 'T' + match.time + '+03:00' : null; }
function betLine(match, trade) { const line=document.createElement('p'); line.className='meta'; if(!trade){line.textContent='Ставка: не делал — этот матч не прошёл денежную проверку.'; return line;} const team=trade.prediction==='HOME_WIN'?match.home:match.away; const result=trade.status==='SETTLED'?(trade.was_correct?' · ставка сыграла · выигрыш +'+Number(trade.virtual_pnl||0).toFixed(2)+' $':' · ставка не сыграла · потеря '+Number(Math.abs(trade.virtual_pnl||0)).toFixed(2)+' $'): ' · ждём результат'; line.textContent='Ставка: победа '+team+' · сумма '+Number(trade.stake||0).toFixed(2)+' $ · '+(trade.bookmaker||'букмекер')+' '+Number(trade.odds||0).toFixed(2)+result+'.'; return line; }
function card(match, recommendation, trade, analysis) {
  const card = document.createElement('article'); card.className = 'match';
  const meta = document.createElement('p'); meta.className = 'meta'; meta.textContent = match.league + ' · ' + date(kickoff(match));
  const title = document.createElement('h3'); title.textContent = match.home + ' — ' + match.away;
  const score = document.createElement('p'); score.className = 'score';
  score.textContent = match.home_score !== null && match.home_score !== undefined ? match.home_score + ' : ' + match.away_score : state(match.status);
  card.append(meta, title, score);
  if (recommendation && trade && trade.status!=='CANCELLED') { const forecast=document.createElement('p'); forecast.className='meta'; const team=recommendation.prediction==='HOME_WIN'?match.home:match.away; const odds=Number(recommendation.bookmaker_odds)>1 ? ' · коэффициент '+recommendation.bookmaker+': '+Number(recommendation.bookmaker_odds).toFixed(2) : ' · ждём коэффициент букмекера'; forecast.textContent='Прогноз модели: победа '+team+' · уверенность '+recommendation.confidence+'%'+odds+'.'; card.append(forecast); }
  else if (match.bookmaker_odds) { const odds=document.createElement('p'); odds.className='meta'; odds.textContent='Коэффициенты '+match.bookmaker_odds.bookmaker+': '+match.home+' '+Number(match.bookmaker_odds.home).toFixed(2)+' · '+match.away+' '+Number(match.bookmaker_odds.away).toFixed(2)+'.'; card.append(odds); }
  card.append(trade && trade.status!=='CANCELLED' ? betLine(match, trade) : basketballForecastLine(match, analysis, recommendation));
  return card;
}
function groupTitle(match) { if (['FT','AOT','FINAL'].includes(String(match.status).toUpperCase())) return 'Готовые'; if (['LIVE','1Q','2Q','3Q','4Q','HT'].includes(String(match.status).toUpperCase())) return 'Ждут результата'; return 'В обработке'; }
async function load() {
  $('refresh').disabled = true;
  try {
    const [response, analysis, tradesResponse] = await Promise.all([fetch('basketball-report.json', {cache:'no-store'}), loadBasketballForecasts(), fetch('basketball-paper-trading.json', {cache:'no-store'})]); const report = await response.json(); const ledger=tradesResponse.ok ? await tradesResponse.json() : {}; if (!response.ok) throw Error();
    renderApprovedBets($('approved-bets'), ledger, (event, prediction) => {
      const [home, away] = String(event).split(' vs ');
      const team = {HOME_WIN: home, AWAY_WIN: away}[prediction];
      return team ? 'Победа ' + team : 'Исход уточняется';
    });
    const matches = Array.isArray(report.matches) ? report.matches : [];
    $('total').textContent = matches.length; $('leagues').textContent = new Set(matches.map(item => item.league)).size;
    $('state').textContent = report.collection_status === 'success' ? 'Данные готовы' : 'Проверяем';
    $('updated').textContent = 'Дата матчей: ' + (report.requested_date || '—') + ' · обновлено: ' + date(report.generated_at) + ' · источник: ' + (report.source || '—');
    const root = $('matches'); root.replaceChildren();
    if (!matches.length) { const empty = document.createElement('p'); empty.textContent = 'На сегодня источник не вернул баскетбольные матчи.'; root.append(empty); }
    { const recommendations=new Map((analysis?.recommendations||[]).map(item=>[String(item.match_id),item])); const trades=new Map((ledger.trades||[]).map(item=>[String(item.fixture_id),item])); ['В обработке','Ждут результата','Готовые'].forEach(title => { const items=matches.filter(match=>groupTitle(match)===title); if(!items.length)return; const section=document.createElement('section'); section.className='match-group'; section.style.gridColumn='1 / -1'; const heading=document.createElement('h2');heading.textContent=title;const list=document.createElement('div');list.className='grid';items.forEach(match=>list.append(card(match,recommendations.get(String(match.id)),trades.get(String(match.id)),analysis)));section.append(heading,list);root.append(section); });
      const upcoming = Array.isArray(report.upcoming_matches) ? report.upcoming_matches : [];
      if (upcoming.length) {
        const heading = document.createElement('h2');
        heading.textContent = 'Предстоящие матчи · следующий день';
        heading.style.gridColumn = '1 / -1';
        root.append(heading);
        for (const match of upcoming) {
          root.append(card(match, recommendations.get(String(match.id)), trades.get(String(match.id)), analysis));
        }
      }
    }
  } catch { renderApprovedBets($('approved-bets'), null); $('updated').textContent = 'Данные временно недоступны. Повторите обновление позже.'; }
  finally { $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', load); load();
