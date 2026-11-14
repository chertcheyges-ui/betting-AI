'use strict';
const byId=id=>document.getElementById(id);
const math=globalThis.EvaluationMath;
const labels=['Победа хозяев','Ничья','Победа гостей'];
let dataset;
const storageKey='betting-ai-study-v1';
const format=(n,d=4)=>Number.isFinite(n)?new Intl.NumberFormat('ru-RU',{maximumFractionDigits:d}).format(n):'∞';
function studyMessage(text,error=false){byId('study-message').textContent=text;byId('study-message').className=error?'error':'';}
function saveExperiment(){
 try{
   localStorage.setItem(storageKey,JSON.stringify({dataset,label:byId('dataset-label').textContent,selected:Number(byId('observation').value),size:byId('sample-size').value,confidence:byId('confidence').value}));
   byId('study-storage').textContent='Учебный эксперимент сохранён в этом браузере. После перезагрузки можно продолжить. «Начать заново» заменит его новым примером.';
 }catch{
   byId('study-storage').textContent='Браузер не разрешил сохранение. Скачайте набор, чтобы продолжить позже.';
 }
}
function drawObservation(){
 const row=dataset.observations[Number(byId('observation').value)],score=math.score(row);
 byId('study-match-name').textContent=row.home+' — '+row.away;
 byId('row-position').textContent=(Number(byId('observation').value)+1)+' / '+dataset.observations.length;
 byId('previous').disabled=Number(byId('observation').value)===0;
 byId('next').disabled=Number(byId('observation').value)===dataset.observations.length-1;
 const names=[row.home,'Ничья',row.away],percentages=math.percentages(row.probabilities);
 const root=byId('probabilities');root.replaceChildren();
 row.probabilities.forEach((p,i)=>{
   const wrapper=document.createElement('div');wrapper.className='prob-row';
   const heading=document.createElement('div');heading.className='prob-heading';
   const title=document.createElement('span');title.textContent=i===1?'Ничья':'Победа: '+names[i];
   const value=document.createElement('strong');value.textContent=format(percentages[i],2)+'%';
   heading.append(title,value);
   const track=document.createElement('div');track.className='prob-track';
   const fill=document.createElement('div');fill.className='prob-fill';fill.style.width=(p*100)+'%';
   track.append(fill);wrapper.append(heading,track);root.append(wrapper);
 });
 const winner=index=>index===1?'Ничья':'Победа: '+names[index];
 const maximum=Math.max(...row.probabilities);
 const ties=row.probabilities.map((p,i)=>p===maximum?i:null).filter(i=>i!==null);
 byId('predicted').textContent=ties.length>1?'Равная максимальная вероятность: '+ties.map(winner).join('; ')+'. Для accuracy выбран первый класс.':'Наибольшая вероятность: '+winner(score.predicted)+'.';
 byId('actual').textContent='Известный результат: '+winner(row.actual)+'. '+(score.correct?'Совпало.':'Не совпало.');
 byId('row-score').textContent='Ошибка наблюдения: Brier = '+format(score.brier)+'; log loss = '+format(score.logloss)+'. Сумма вероятностей: 100%.';
}
function loadDataset(raw,label){
 const next=math.validate(raw),metrics=math.evaluate(next);
 dataset=next;
 byId('dataset-label').textContent=label;
 byId('accuracy').textContent=format(metrics.accuracy*100,1)+'%';
 byId('correct-count').textContent=metrics.correct+' из '+metrics.n+' наблюдений';
 byId('brier').textContent=format(metrics.brier);byId('logloss').textContent=format(metrics.logloss);
 const brierDelta=metrics.brier-2/3,logDelta=metrics.logloss-Math.log(3);
 const delta=n=>(n>=0?'+':'')+format(n);
 byId('comparison').textContent='Разница с равномерными вероятностями: Brier '+delta(brierDelta)+'; log loss '+delta(logDelta)+'. Отрицательная разница означает меньшую ошибку. Это результат только выбранного учебного набора.';
 byId('observation').replaceChildren(...dataset.observations.map((row,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=row.id+' · '+row.home+' — '+row.away;return option;}));
 drawObservation();
}
byId('generate').onclick=()=>{loadDataset(math.generate(Number(byId('sample-size').value),Number(byId('confidence').value)),'Встроенный синтетический пример');saveExperiment();studyMessage('Эксперимент пересчитан.');};
byId('study-reset').onclick=()=>{
 byId('sample-size').value='100';byId('confidence').value='1';
 loadDataset(math.generate(100,1),'Встроенный синтетический пример');saveExperiment();studyMessage('Открыт новый стандартный пример.');
};
byId('observation').onchange=()=>{drawObservation();saveExperiment();};
for(const [id,step] of [['previous',-1],['next',1]])byId(id).onclick=()=>{
 const index=Number(byId('observation').value)+step;
 if(index<0||index>=dataset.observations.length)return;
 byId('observation').value=String(index);drawObservation();saveExperiment();
};
byId('study-import').onclick=()=>byId('study-file').click();
byId('study-file').onchange=async event=>{
 const file=event.target.files[0];if(!file)return;
 byId('study-import').disabled=true;
 try{
   if(file.size>2*1024*1024)throw new Error('Максимальный размер файла — 2 МБ.');
   const raw=JSON.parse(await file.text());loadDataset(raw,'Загруженный учебный набор');
   saveExperiment();studyMessage('Набор загружен. Данные обработаны только в браузере.');
 }catch(error){studyMessage(error instanceof SyntaxError?'Не удалось прочитать JSON. Выберите учебный файл.':error.message,true);}
 finally{event.target.value='';byId('study-import').disabled=false;}
};
byId('study-download').onclick=()=>{
 const url=URL.createObjectURL(new Blob([JSON.stringify(dataset,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='synthetic-evaluation.json';link.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
};
try{
 const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
 if(saved){
   loadDataset(saved.dataset,'Сохранённый учебный набор');
   for(const [id,key] of [['sample-size','size'],['confidence','confidence']])if([...byId(id).options].some(o=>o.value===saved[key]))byId(id).value=saved[key];
   if(Number.isInteger(saved.selected)&&saved.selected>=0&&saved.selected<dataset.observations.length){byId('observation').value=String(saved.selected);drawObservation();}
   byId('study-storage').textContent='Восстановлен последний учебный эксперимент из этого браузера.';
 }else{loadDataset(math.generate(100,1),'Встроенный синтетический пример');saveExperiment();}
}catch{
 loadDataset(math.generate(100,1),'Встроенный синтетический пример');
 byId('study-storage').textContent='Сохранённый эксперимент недоступен. Открыт стандартный пример; скачайте набор для резервной копии.';
}
