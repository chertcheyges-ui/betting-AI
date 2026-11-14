'use strict';
const $ = id => document.getElementById(id);
const zones = {BY:'Europe/Minsk',RU:'Europe/Moscow',KZ:'Asia/Almaty',AM:'Asia/Yerevan',AZ:'Asia/Baku',KG:'Asia/Bishkek',MD:'Europe/Chisinau',TJ:'Asia/Dushanbe',UZ:'Asia/Tashkent',TM:'Asia/Ashgabat'};
const fieldNames = {recent_form:'Форма команд',home_away_form:'Домашняя и гостевая форма',h2h:'Очные встречи',injuries:'Травмы',lineups:'Составы',odds:'Рыночные данные',schedule_load:'Календарная нагрузка',match_statistics:'Статистика игры'};
const matchStatuses={TBD:'Время уточняется',NS:'Не начался','1H':'Первый тайм',HT:'Перерыв','2H':'Второй тайм',ET:'Дополнительное время',BT:'Перерыв',P:'Серия пенальти',FT:'Завершён',AET:'Завершён после доп. времени',PEN:'Завершён по пенальти',PST:'Перенесён',CANC:'Отменён',ABD:'Прерван',SUSP:'Приостановлен',INT:'Остановлен',AWD:'Технический результат',WO:'Неявка',LIVE:'В игре'};
const statFields=[['shots_on_goal','Удары в створ'],['total_shots','Всего ударов'],['possession','Владение мячом, %'],['corners','Угловые'],['fouls','Фолы'],['yellow_cards','Жёлтые карточки'],['red_cards','Красные карточки']];
const finished=m=>['FT','AET','PEN','AWD','WO'].includes(m.status);
const hasStatistics=m=>!!(m.home_stats&&m.away_stats);
const goal=value=>Number.isInteger(value)&&value>=0?value:null;
const matchScore=m=>m.goals_home!==null&&m.goals_away!==null?m.goals_home+' : '+m.goals_away:'— : —';
let report = null, selected = null, lastFocus = null, loadRevision=0;
let systemSnapshot = null;
let paperSnapshot = null;
const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const object = value => value && typeof value === 'object' && !Array.isArray(value);
const text = (value, fallback = 'Не указано') => typeof value === 'string' && value.trim() ? value.slice(0,300) : fallback;
function element(tag, content, cls) { const node = document.createElement(tag); if(content !== undefined) node.textContent = content; if(cls) node.className = cls; return node; }
function message(value, error = false) { $('message').textContent = value; $('message').className = error ? 'error' : ''; }
function date(value) { if(!value) return 'Время не указано'; return new Intl.DateTimeFormat('ru-RU',{dateStyle:'medium',timeStyle:'short',timeZone:$('timezone').value}).format(new Date(value)); }
function validDate(value) { return typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)); }
function form(value) {
  if(!object(value) || !Number.isInteger(value.matches) || value.matches <= 0) return null;
  return Object.fromEntries(['matches','wins','draws','losses','goals_for','goals_against','points_per_game'].map(key => [key,number(value[key]) ? value[key] : null]));
}
function matchStats(value){
 if(!object(value))return null;
 const stats=Object.fromEntries(statFields.map(([key])=>[key,number(value[key])&&(key!=='possession'||value[key]<=100)?value[key]:null]));
 return Object.values(stats).some(value=>value!==null)?stats:null;
}
function validate(raw) {
  if(!object(raw) || raw.schema_version !== 1 || !Array.isArray(raw.matches) || raw.matches.length > 500 || !validDate(raw.generated_at)) throw new Error('Неверный формат отчёта. Используйте JSON, созданный скриптом выгрузки проекта.');
  if(!['success','degraded','error'].includes(raw.collection_status)) throw new Error('В отчёте отсутствует корректный статус сбора данных.');
  return {schema_version:1,report_kind:raw.report_kind==='fixture_statistics'?'fixture_statistics':'legacy',requested_date:text(raw.requested_date,''),fixtures_found:Number.isInteger(raw.fixtures_found)?raw.fixtures_found:null,generated_at:raw.generated_at,source:text(raw.source),demo:raw.demo === true,collection_status:raw.collection_status,rate_limited:raw.rate_limited === true,matches:raw.matches.map((match,i) => {
    if(!object(match) || typeof match.home !== 'string' || !match.home.trim() || typeof match.away !== 'string' || !match.away.trim()) throw new Error('Матч №'+(i+1)+': отсутствуют названия команд.');
    return {id:String(i),home:text(match.home),away:text(match.away),league:text(match.league),country:text(match.country,''),kickoff:validDate(match.kickoff)?match.kickoff:null,status:matchStatuses[match.status]?match.status:'TBD',goals_home:goal(match.goals_home),goals_away:goal(match.goals_away),home_stats:matchStats(match.home_stats),away_stats:matchStats(match.away_stats),statistics_state:text(match.statistics_state,'unavailable'),missing:Array.isArray(match.missing)?match.missing.filter(x=>typeof x==='string').slice(0,30).map(x=>x.slice(0,100)):['Неизвестна полнота данных'],home_form:form(match.home_form),away_form:form(match.away_form),h2h_count:Number.isInteger(match.h2h_count)&&match.h2h_count>=0?match.h2h_count:null};
  })};
}
function hasForm(match) { return !!(match.home_form && match.away_form); }
function incomplete(match) { return !!match.missing.length || !hasForm(match); }
function render() {
  const matches=report?.matches || [];
  $('mode').textContent = !report ? 'Нет отчёта' : report.demo ? 'Демонстрационные данные' : report.report_kind==='fixture_statistics'?'Реальные данные · снимок':'Загруженный отчёт';
  const statuses={success:'Сбор завершён',degraded:'Данные неполные',error:'Ошибка сбора'};
  $('source').textContent = report ? 'Источник: '+report.source+' · '+statuses[report.collection_status]+(report.rate_limited?' · Лимит API':'') : 'Загрузите файл или откройте деморежим.';
  $('generated').textContent = report ? 'Создан: '+date(report.generated_at) : '';
  $('total').textContent=report?matches.length:'—'; $('with-form').textContent=report?matches.filter(hasStatistics).length:'—'; $('incomplete').textContent=report?matches.filter(finished).length:'—';
  $('download').disabled=!report;
  const query=$('query').value.trim().toLocaleLowerCase('ru');
  const filtered=matches.filter(m=>(m.home+' '+m.away+' '+m.league+' '+m.country).toLocaleLowerCase('ru').includes(query)).filter(m=>$('filter').value==='all'||($('filter').value==='statistics'?hasStatistics(m):$('filter').value==='finished'?finished(m):$('filter').value==='upcoming'?['NS','TBD'].includes(m.status):incomplete(m)));
  $('result-count').textContent=report?'Показано '+filtered.length+' из '+matches.length+(report.requested_date?' · '+report.requested_date:''):'';
  $('match-list').replaceChildren();
  for(const match of filtered){
    const card=element('article',undefined,'match-card');
    const meta=element('div',undefined,'card-meta');meta.append(element('span',match.league+(match.country?' · '+match.country:'')),element('span',date(match.kickoff)));
    const name=element('h3');name.append(element('span',match.home),element('span','—','teams-vs'),element('span',match.away));
    const summary=element('p',matchScore(match)+' · '+matchStatuses[match.status],'fixture-score');
    const bottom=element('div',undefined,'card-bottom');
    const badge=element('span',hasStatistics(match)?'Есть статистика игры':'Счёт и расписание','badge');
    const button=element('button','Подробнее →');button.addEventListener('click',()=>openMatch(match,button));
    bottom.append(badge,button);card.append(meta,name,summary,bottom);$('match-list').append(card);
  }
  $('empty').hidden=filtered.length>0;
  if(report) {$('empty').replaceChildren(element('h3',matches.length?'Ничего не найдено':'В отчёте нет матчей'),element('p',matches.length?'Измените запрос или выберите «Все матчи».':'Источник не вернул матчи. Проверьте статус сбора данных и создайте новый отчёт.'));}
  else {$('empty').replaceChildren(element('h3','Загрузите реальные данные'),element('p','Нажмите «Открыть последний снимок» или загрузите файл отчёта.'));}
}
function detail(match) {
  const root=$('match-detail'); root.replaceChildren();
  const heading=element('h2',match.home+' — '+match.away);heading.id='match-title';
  root.append(heading,element('p',match.league+' · '+date(match.kickoff),'report-date'));
  root.append(element('p',matchScore(match)+' · '+matchStatuses[match.status],'fixture-score'));
  root.append(element('p','Состояние на момент снимка: '+date(report.generated_at)+'. Страница не является прямой трансляцией.','muted'));
  if(report.demo) root.append(element('p','Демонстрационный матч. Команды и статистика вымышлены.','section-note'));
  const gameStats=element('section',undefined,'detail-section');gameStats.append(element('h3','Статистика игры'));
  const statHead=element('div',undefined,'stat-row');statHead.append(element('span',match.home),element('span','Показатель'),element('span',match.away));gameStats.append(statHead);
  for(const [key,label] of statFields){
    const value=side=>side&&number(side[key])?new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(side[key]):'—';
    const row=element('div',undefined,'stat-row');row.append(element('span',value(match.home_stats)),element('span',label),element('span',value(match.away_stats)));gameStats.append(row);
  }
  if(!hasStatistics(match)){
    const reasons={not_started:'Матч ещё не начался или статистика для этого статуса не собирается.',not_requested:'Подробная статистика не запрашивалась: снимок использует ограниченное число API-запросов.',unavailable:'API не вернул подробную статистику этого матча.',request_error:'Не удалось получить статистику: ошибка API или ограничение тарифа.'};
    gameStats.append(element('p',reasons[match.statistics_state]||'Подробная статистика не передана в отчёте.','section-note'));
  }
  root.append(gameStats);
  if(hasForm(match)){
  const stats=element('section',undefined,'detail-section');stats.append(element('h3','Форма команд'));
  const header=element('div',undefined,'stat-row');header.append(element('span',match.home),element('span','Показатель'),element('span',match.away));stats.append(header);
  for(const [key,label] of [['matches','Матчей в выборке'],['wins','Побед'],['draws','Ничьих'],['losses','Поражений'],['goals_for','Забито голов'],['goals_against','Пропущено голов'],['points_per_game','Очков за матч']]) {
    const format=f=>f&&number(f[key])?new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(f[key]):'—';
    const row=element('div',undefined,'stat-row');row.append(element('span',format(match.home_form)),element('span',label),element('span',format(match.away_form)));stats.append(row);
  }
  stats.append(element('p','«—» означает отсутствие данных. Числа относятся к выборке источника, а не обязательно ко всему сезону.','muted'));root.append(stats);
  root.append(element('p',match.h2h_count===null?'История очных встреч не передана.':'Очные встречи до матча: '+match.h2h_count,'section-note'));
  }
  const missing=[...new Set([...match.missing.map(key=>fieldNames[key]||key),...(!match.home_form?['Форма хозяев']:[]),...(!match.away_form?['Форма гостей']:[])])];
  root.append(element('p',missing.length?'Требуют дополнения: '+missing.join(', '):'Пропуски в переданном отчёте не отмечены.','section-note'+(missing.length?' warn':'')));
  root.append(element('p','Источник фактических данных: '+report.source+'.','muted'));
}
function openMatch(match,button){selected=match;lastFocus=button;detail(match);$('match-dialog').showModal();}
$('close-dialog').onclick=()=>$('match-dialog').close();
$('match-dialog').addEventListener('close',()=>{selected=null;if(lastFocus?.isConnected)lastFocus.focus();else $('query').focus();});
function setReport(raw,origin='file') {
  const next=validate(raw);report=next;$('query').value='';$('filter').value='all';render();
  let note=next.demo?'Демонстрационный файл: вымышленные данные.':origin==='site'?'Открыт последний опубликованный снимок API-Football. Это сохранённые данные, а не прямой эфир.':'Отчёт загружен. Файл обработан только в вашем браузере.';
  if(next.rate_limited)note+=' Источник сообщил об ограничении API: данные неполные.';
  else if(next.collection_status!=='success')note+=' Сбор данных завершился с проблемами.';
  if(!next.demo && Date.now()-Date.parse(next.generated_at)>86400000) note+=' Отчёт старше суток; сведения могли измениться.';
  message(note);
}
async function loadLatest(){
 const revision=++loadRevision;
 const reportPath=$('report-date').value || 'latest-report.json';
 $('latest').disabled=true;message('Загружаем отчёт по матчам…');
 try{
   const response=await fetch(reportPath,{cache:'no-store'});
   if(!response.ok)throw new Error('Снимок пока недоступен. Загрузите локальный отчёт или попробуйте позже.');
   const raw=await response.json();if(revision===loadRevision)setReport(raw,'site');
 }catch(error){if(revision===loadRevision)message(location.protocol==='file:'?'Для автоматической загрузки откройте опубликованный сайт. Здесь можно загрузить JSON через кнопку.':error.message,true);}
 finally{$('latest').disabled=false;}
}
async function loadReportDates(){
  try{
    const response=await fetch('reports/index.json',{cache:'no-store'});
    const raw=await response.json();
    if(!response.ok || !Array.isArray(raw.reports)) return;
    const picker=$('report-date');
    for(const item of raw.reports){
      if(!/^\d{4}-\d{2}-\d{2}$/.test(String(item.date))) continue;
      const option=document.createElement('option');
      option.value='reports/'+item.date+'.json';
      option.textContent=new Intl.DateTimeFormat('ru-RU',{dateStyle:'long',timeZone:'Europe/Minsk'}).format(new Date(item.date+'T12:00:00+03:00'))+' · '+(Number(item.matches)||0)+' матчей';
      picker.append(option);
    }
  }catch{}
}
function systemText(value, fallback='—') { return typeof value === 'string' && value ? value : fallback; }
function money(value) { return typeof value === 'number' && Number.isFinite(value) ? '$'+new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(value) : '—'; }
function predictionName(event, prediction) { const [home,away]=String(event||'').split(' vs '); if(prediction==='HOME_WIN'||prediction==='Home')return home?'Победа '+home:'Победа хозяев'; if(prediction==='AWAY_WIN'||prediction==='Away')return away?'Победа '+away:'Победа гостей'; return prediction==='DRAW'||prediction==='Draw'?'Ничья':'Пока нет прогноза'; }
function statusClass(value) { return /APPROVE|PASS|READY|COMPLETE|WITHIN/.test(String(value)) ? 'good' : /REJECT|FAIL|BLOCKED|NO BET|HOLD|NO ACTION/.test(String(value)) ? 'blocked' : 'neutral'; }
function simpleStatus(value) { const labels = {"NO BET":"Не ставим", "NO ACTION":"Сейчас без действий", "CFO REVIEW REQUIRED":"Проверяем сумму", "WITHIN LIMITS":"Лимиты в порядке", "BLOCKED":"Остановлено для проверки", "PASS":"Проверено", "HOLD":"Ждём"}; return labels[value] || value || '—'; }
function addSystemCard(label, value, detail='') { const card=element('article',undefined,'system-card'); card.append(element('span',label,'muted'),element('strong',systemText(value),'system-status '+statusClass(value)),element('small',detail||' ')); return card; }
function renderSystem() {
  const root=$('system-cards'); root.replaceChildren(); const decisionRoot=$('system-decision'); const candidatesRoot=$('system-candidates'); candidatesRoot.replaceChildren();
  if(!systemSnapshot) { root.append(addSystemCard('Система','Нет сохранённого запуска','Запустите обновление данных на компьютере, где хранится проект.')); decisionRoot.hidden=true; return; }
  const s=systemSnapshot; const r=s.research||{}, d=s.data||{}, analysis=s.analysis||{}, risk=s.risk||{}, f=s.financial||{}, audit=s.audit||{}, committee=s.committee||{};
  const pageCheck=audit.dashboard_check||{};
  const auditDetail=pageCheck.current ? 'Сегодняшние матчи на сайте: '+(pageCheck.matches||0) : (pageCheck.expected_date ? 'Сегодняшний отчёт нужно обновить.' : simpleStatus(audit.recommendation));
  $('system-updated').textContent='Снимок создан: '+date(s.generated_at)+(r.requested_date?' · дата матчей: '+r.requested_date:'');
  root.append(addSystemCard('Матчи',String(r.fixtures_found||0),systemText(r.status)),addSystemCard('Данные',(d.fixtures_processed||0)+' обработано',d.api_rate_limited?'Лимит API достигнут':systemText(d.status)),addSystemCard('Риск',simpleStatus(risk.stake_decision),simpleStatus(risk.risk_level)),addSystemCard('Финансы',simpleStatus(f.financial_status),f.bankroll!==undefined?'Банк: '+money(f.bankroll)+' · доступно: '+money(f.remaining_daily_risk):'Банк будет показан после следующего обновления.'),addSystemCard('Аудит',simpleStatus(audit.audit_status),auditDetail));
  decisionRoot.hidden=false;
  const paused=String(committee.reason||'').startsWith('Hard pause is active');
  decisionRoot.className='decision-card '+statusClass(committee.decision);
  decisionRoot.replaceChildren(element('h2','Решение комитета'));
  if(paused) decisionRoot.append(element('p','Действует пауза. Новые виртуальные ставки временно остановлены.'));
  const picks=element('div');
  decisionRoot.append(picks);
  renderApprovedBets(picks,paperSnapshot,predictionName);
  const forecasts=analysis.forecasts||[];
  if(forecasts.length) { candidatesRoot.append(element('h3','Мои прогнозы')); for(const c of forecasts) { const card=element('article',undefined,'candidate-card'); const forecast=predictionName(c.event,c.selection||c.prediction); const verdict=c.status==='READY'&&c.selection?'Готов поставить виртуально':'Только наблюдаю: я недостаточно уверен'; card.append(element('strong',systemText(c.event,'Матч не указан')+' · '+forecast),element('p',[verdict,c.model_probability!==undefined&&'уверенность '+Number(c.model_probability).toFixed(1)+'%',c.odds!==undefined&&'коэффициент '+c.odds].filter(Boolean).join(' · '))); candidatesRoot.append(card); } }
  else { candidatesRoot.append(element('p','Сейчас нет готовых прогнозов.','muted')); }
}
function validSystem(raw) { return raw && raw.schema_version===1 && validDate(raw.generated_at) && object(raw); }
async function loadSystem(manual=false) {
  const button=$('refresh-system'), status=$('system-refresh-status');
  const previous=systemSnapshot?.generated_at;
  button.disabled=true;
  if(manual) status.textContent='Проверяем, появился ли новый отчёт…';
  try {
    const response=await fetch('system-status.json',{cache:'no-store'});
    if(!response.ok) throw new Error();
    const raw=await response.json();
    if(!validSystem(raw)) throw new Error();
    systemSnapshot=raw;
    if(manual) status.textContent=raw.generated_at===previous
      ? 'Новый отчёт ещё не опубликован. Показан последний доступный отчёт.'
      : 'Загружен последний опубликованный отчёт.';
  } catch {
    if(systemSnapshot) status.textContent='Не удалось проверить обновление. Последний загруженный отчёт остался на экране.';
    else $('system-updated').textContent='Не удалось загрузить отчёт. Попробуйте проверить ещё раз.';
    if(!systemSnapshot) status.textContent='';
  } finally {
    button.disabled=false;
    renderSystem();
  }
}
function renderPaper() { const cards=$('paper-cards'), history=$('paper-history'); cards.replaceChildren(); history.replaceChildren(); if(!paperSnapshot){$('paper-updated').textContent='Снимок виртуального эксперимента пока недоступен.';cards.append(addSystemCard('Paper trading','Нет данных','Прогнозы появятся после следующего цикла.'));return} const p=paperSnapshot; $('paper-updated').textContent='Обновлено: '+date(p.updated_at)+' · только виртуальные позиции';cards.append(addSystemCard('Открытые прогнозы',String(p.open_count||0),'До завершения матча'),addSystemCard('Проверено',String(p.settled_count||0),'Сверено с реальным счётом'),addSystemCard('Точность',p.accuracy===null?'—':(p.accuracy*100).toFixed(1)+'%','Доля верных прогнозов'),addSystemCard('Brier score',p.brier_score===null?'—':p.brier_score.toFixed(3),'Ниже — лучше'),addSystemCard('Log loss',p.log_loss===null?'—':p.log_loss.toFixed(3),'Ниже — лучше')); const trades=(p.trades||[]).slice().reverse().slice(0,5); if(!trades.length){history.append(element('p','Первый прогноз появится после ближайшего цикла анализа.','muted'));return} history.append(element('h3','Последние прогнозы и результаты')); for(const t of trades){const row=element('article',undefined,'candidate-card');const outcome=t.status==='OPEN'?'Ожидаем итог матча.':(t.was_correct?'Прогноз совпал с результатом.':'Прогноз не совпал: '+(t.reasons||[]).join(' '));row.append(element('strong',(t.event||'Матч')+' · '+predictionName(t.event,t.prediction)),element('p',outcome));history.append(row)} }
async function loadPaper() { try { const response=await fetch('paper-trading.json',{cache:'no-store'}); const raw=await response.json(); paperSnapshot=response.ok&&raw&&raw.schema_version===1?raw:null; } catch {paperSnapshot=null} renderPaper(); renderSystem(); }
$('latest').onclick=loadLatest;
$('report-date').addEventListener('change',loadLatest);
$('refresh-system').onclick=()=>Promise.all([loadSystem(true),loadPaper()]);
$('import').onclick=()=>$('report-file').click();
$('report-file').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  const revision=++loadRevision;
  $('import').disabled=true;message('Читаем отчёт…');
  try{if(file.size>2*1024*1024)throw new Error('Файл слишком большой. Максимум — 2 МБ.');const raw=JSON.parse(await file.text());if(revision===loadRevision)setReport(raw);}
  catch(error){message(error instanceof SyntaxError?'Не удалось прочитать JSON. Выберите файл отчёта.':error.message,true);}
  finally{event.target.value='';$('import').disabled=false;}
});
$('download').onclick=()=>{if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=element('a');a.href=url;a.download=report.demo?'demo-match-report.json':'match-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('clear').onclick=()=>{++loadRevision;report=null;$('query').value='';$('filter').value='all';render();message('Отчёт очищен. Можно открыть последний снимок или загрузить другой файл.');};
$('query').addEventListener('input',render);$('filter').addEventListener('change',render);
$('settings-toggle').onclick=()=>{const open=$('settings').hidden;$('settings').hidden=!open;$('settings-toggle').setAttribute('aria-expanded',String(open));};
try{const saved=JSON.parse(localStorage.getItem('betting-ai-display')||'{}');for(const id of ['country','timezone'])if(saved&&[...$(id).options].some(o=>o.value===saved[id]))$(id).value=saved[id];}catch{}
for(const id of ['country','timezone'])$(id).addEventListener('change',()=>{if(id==='country')$('timezone').value=zones[$('country').value];try{localStorage.setItem('betting-ai-display',JSON.stringify({country:$('country').value,timezone:$('timezone').value}));message('Настройки сохранены. Время матчей обновлено.');}catch{message('Настройки применены. Сохранение в браузере недоступно.');}render();if(selected)detail(selected);});
render();
renderSystem();
renderPaper();
loadSystem();
loadPaper();
loadReportDates();
loadLatest();
