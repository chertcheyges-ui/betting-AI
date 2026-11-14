(function(root){
  'use strict';
  function validate(raw) {
    if(!raw || raw.schema_version!==1 || raw.kind!=='synthetic_evaluation' || !Array.isArray(raw.observations) || !raw.observations.length || raw.observations.length>1000) throw new Error('Нужен синтетический учебный набор: от 1 до 1000 наблюдений. Скачайте пример для шаблона.');
    const ids=new Set();
    return {schema_version:1,kind:'synthetic_evaluation',observations:raw.observations.map((row,i)=>{
      if(!row || !Array.isArray(row.probabilities) || row.probabilities.length!==3 || row.probabilities.some(p=>typeof p!=='number'||!Number.isFinite(p)||p<0||p>1)) throw new Error('Наблюдение '+(i+1)+': нужны три вероятности от 0 до 1.');
      const sum=row.probabilities.reduce((a,b)=>a+b,0);
      if(Math.abs(sum-1)>1e-6) throw new Error('Наблюдение '+(i+1)+': сумма вероятностей должна быть 1.');
      if(!Number.isInteger(row.actual)||row.actual<0||row.actual>2) throw new Error('Наблюдение '+(i+1)+': actual должен быть 0, 1 или 2.');
      const id=typeof row.id==='string'&&row.id.trim()?row.id.slice(0,100):'Наблюдение '+(i+1);
      if(ids.has(id))throw new Error('Повторяющийся идентификатор: '+id);ids.add(id);
      // Accepted rounding differences are normalized before all calculations.
      const name=(value,fallback)=>typeof value==='string'&&value.trim()?value.trim().slice(0,80):fallback;
      return {id,home:name(row.home,'Учебный клуб A'),away:name(row.away,'Учебный клуб B'),probabilities:row.probabilities.map(p=>p/sum),actual:row.actual};
    })};
  }
  function score(row){
    const p=row.probabilities;
    const predicted=p.indexOf(Math.max(...p));
    return {predicted,correct:predicted===row.actual,brier:p.reduce((s,v,k)=>s+(v-(k===row.actual?1:0))**2,0),logloss:-Math.log(p[row.actual])};
  }
  function evaluate(dataset){
    const rows=dataset.observations.map(score),n=rows.length;
    const correct=rows.filter(r=>r.correct).length;
    return {n,correct,accuracy:correct/n,brier:rows.reduce((s,r)=>s+r.brier,0)/n,logloss:rows.reduce((s,r)=>s+r.logloss,0)/n};
  }
  function generate(n,confidence){
    if(!Number.isInteger(n)||n<1||n>1000||!Number.isFinite(confidence)||confidence<=0||confidence>10)throw new Error('Некорректные параметры учебного эксперимента.');
    let state=2026;
    const rand=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
    const observations=Array.from({length:n},(_,i)=>{
      const base=[rand()+0.1,rand()+0.1,rand()+0.1],total=base.reduce((a,b)=>a+b);
      const original=base.map(p=>p/total),draw=rand();
      const actual=draw<original[0]?0:draw<original[0]+original[1]?1:2;
      const powered=original.map(p=>p**confidence),sum=powered.reduce((a,b)=>a+b);
      const clubs=['Север','Долина','Атлас','Восток','Приморье','Олимп','Спектр','Горизонт','Маяк','Вектор','Лесной','Рассвет'];
      const home=clubs[i%clubs.length],away=clubs[(i+1+Math.floor(i/clubs.length)%(clubs.length-1))%clubs.length];
      return {id:'Учебный матч '+(i+1),home:'Клуб '+home,away:'Клуб '+away,probabilities:powered.map(p=>p/sum),actual};
    });
    return validate({schema_version:1,kind:'synthetic_evaluation',observations});
  }
  function percentages(probabilities){
    const scaled=probabilities.map(p=>p*10000),units=scaled.map(Math.floor);
    const order=[0,1,2].sort((a,b)=>(scaled[b]-units[b])-(scaled[a]-units[a]));
    const remaining=10000-units.reduce((a,b)=>a+b,0);
    for(let i=0;i<remaining;i++)units[order[i%3]]++;
    return units.map(p=>p/100);
  }
  const api={validate,score,evaluate,generate,percentages};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.EvaluationMath=api;
})(globalThis);
