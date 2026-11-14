const defaults = {
  BY: ['BYN', 'Europe/Minsk'], RU: ['RUB', 'Europe/Moscow'],
  KZ: ['KZT', 'Asia/Almaty'], AM: ['AMD', 'Asia/Yerevan'],
  AZ: ['AZN', 'Asia/Baku'], KG: ['KGS', 'Asia/Bishkek'],
  MD: ['MDL', 'Europe/Chisinau'], TJ: ['TJS', 'Asia/Dushanbe'],
  UZ: ['UZS', 'Asia/Tashkent'], TM: ['TMT', 'Asia/Ashgabat']
};
const controls = Object.fromEntries(['country', 'currency', 'timezone'].map(id => [id, document.getElementById(id)]));
const status = document.getElementById('settings-status');
function clock() {
  const now = new Date();
  const target = document.getElementById('local-clock');
  target.dateTime = now.toISOString();
  target.textContent = new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'long', timeStyle: 'short', timeZone: controls.timezone.value
  }).format(now);
}
try {
  const saved = JSON.parse(localStorage.getItem('betting-ai-display') || '{}');
  for (const [id, control] of Object.entries(controls)) {
    if (saved && [...control.options].some(option => option.value === saved[id])) control.value = saved[id];
  }
  status.textContent = 'Настройки сохраняются только в этом браузере.';
} catch {
  status.textContent = 'Сохранение настроек недоступно; изменения действуют до закрытия страницы.';
}
for (const [id, control] of Object.entries(controls)) {
  control.addEventListener('change', () => {
    if (id === 'country') {
      [controls.currency.value, controls.timezone.value] = defaults[control.value];
    }
    try {
      localStorage.setItem('betting-ai-display', JSON.stringify(Object.fromEntries(Object.entries(controls).map(([key, value]) => [key, value.value]))));
      status.textContent = 'Настройки сохранены в этом браузере.';
    } catch {
      status.textContent = 'Настройки применены. Браузер не разрешил их сохранить.';
    }
    clock();
  });
}
clock();
setInterval(clock, 60000);
