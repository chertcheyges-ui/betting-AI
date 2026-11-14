const assets = __ASSETS__;
const liveCache = new Map();

const contentTypes = {
  '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};
const statusNames = { NS: 'не начался', '1H': 'первый тайм', HT: 'перерыв', '2H': 'второй тайм', ET: 'дополнительное время', BT: 'перерыв в доп. времени', PEN: 'пенальти', FT: 'завершён', AET: 'завершён' };

function mime(path) {
  const extension = path.slice(path.lastIndexOf('.'));
  return contentTypes[extension] || 'application/octet-stream';
}

async function liveFixture(id, env) {
  const cached = liveCache.get(id);
  if (cached && Date.now() - cached.savedAt < 9 * 60 * 1000) return cached.value;
  const response = await fetch('https://v3.football.api-sports.io/fixtures?id=' + encodeURIComponent(id), {
    headers: { 'x-apisports-key': env.API_FOOTBALL_KEY },
  });
  if (!response.ok) throw new Error('Score source unavailable');
  const raw = await response.json(); const item = raw.response?.[0];
  if (!item) throw new Error('Match not found');
  const fixture = item.fixture || {}; const game = item.goals || {}; const gameStatus = fixture.status || {};
  const value = {
    fixture_id: item.fixture?.id, home: item.teams?.home?.name, away: item.teams?.away?.name,
    kickoff: fixture.date, goals_home: game.home, goals_away: game.away,
    status: gameStatus.short, status_text: statusNames[gameStatus.short] || gameStatus.long,
    elapsed: gameStatus.elapsed, checked_at: new Date().toISOString(),
  };
  liveCache.set(id, { savedAt: Date.now(), value }); return value;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/live') {
      const ids = (url.searchParams.get('ids') || '').split(',').filter(value => /^\d{1,12}$/.test(value)).slice(0, 8);
      if (!env.API_FOOTBALL_KEY) return Response.json({ error: 'Live source is not configured.' }, { status: 503 });
      const matches = await Promise.all(ids.map(async id => {
        try { return await liveFixture(id, env); } catch { return { fixture_id: Number(id), error: true }; }
      }));
      return Response.json({ checked_at: new Date().toISOString(), matches }, { headers: { 'cache-control': 'no-store' } });
    }
    let path = url.pathname === '/' ? '/index.html' : url.pathname;
    if (!assets[path] && !path.includes('.')) path += '.html';
    const asset = assets[path];
    return asset === undefined ? new Response('Not found', { status: 404 }) : new Response(asset, { headers: { 'content-type': mime(path), 'cache-control': path.endsWith('.json') ? 'no-store' : 'public, max-age=300' } });
  },
};
