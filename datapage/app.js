(function () {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') e.className = v;
    else if (k === 'dataset') Object.assign(e.dataset, v);
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  kids.flat().forEach(c => { if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c)); });
  return e;
}
const svgEl = html => { const d = document.createElement('div'); d.innerHTML = html; return d.firstElementChild; };
let _uid = 0; const uid = () => 'f' + (++_uid);
const num = x => { if (x == null || x === '') return null; const n = parseFloat(String(x).replace(/\s/g, '').replace(',', '.')); return isFinite(n) ? n : null; };
const debounce = (fn, ms) => { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; };

const SRC = { nameplate: 'Шильдик', passport: 'Паспорт', measured: 'Измерил', stated: 'Со слов', certificate: 'Сертификат', unknown: 'Не знаю' };
const KEY = 'stamp-shop-data-v1';
const MAX_PRESSES = 12;

/* ------------------------------------------------------------ содержание */
const PRESS_MAIN = [
  { type: 'choice', key: 'kind', label: 'Тип пресса', must: true, fig: 'press:t-frame',
    what: 'От типа зависит, как крепится штамп и как подаётся металл.',
    how: ['Встаньте сбоку от пресса и посмотрите на станину (корпус).',
      'Станина в форме буквы С, открыта спереди: кривошипный открытый.',
      'Две стойки по бокам, сверху перемычка: кривошипный закрытый.',
      'Сверху цилиндр с маслом и шлангами: гидравлический.'],
    opts: [['crank_open', 'Кривошипный открытый', 'станина буквой С'], ['crank_closed', 'Кривошипный закрытый', 'две стойки'],
      ['hydraulic', 'Гидравлический', 'цилиндр с маслом'], ['unknown', 'Не знаю', '']] },
  { type: 'num', key: 'force', label: 'Номинальное усилие', must: true, fig: 'plate:t-np-force|press:t-plate', ph: 'например 630',
    units: [['kN', 'кН'], ['t', 'т (тонны)']], src: ['nameplate', 'passport', 'stated', 'unknown'],
    chk: (v, u) => (u === 'kN' && v < 100) ? 'Меньше 100 кН это пресс меньше 10 тонн. Если на табличке тонны, переключите единицу на «т».'
      : (u === 't' && v > 400) ? 'Больше 400 тонн вряд ли. Если на табличке кН, переключите единицу на «кН».' : null,
    what: 'Какое усилие пресс может развивать. От него зависит, какие штампы на него можно ставить. Главное число в этой карточке.',
    how: ['Найдите на станине металлическую табличку (шильдик). Обычно спереди или сбоку, размером с книжку.',
      'Найдите строку «Усилие номинальное», «Номинальное усилие» или «Р ном».',
      'Выберите единицу так, как написано на табличке: кН (килоньютоны) или т (тонны).',
      'Табличка не читается? Посмотрите паспорт пресса. Нет ни того ни другого: выберите «Не знаю» и сфотографируйте пресс целиком.'],
    tip: '630 кН это примерно 63 тонны: кН делите на 10.' },
  { type: 'num', key: 'table_lr', label: 'Стол: слева направо', must: true, fig: 'table:t-tablelr', unit: 'мм', ph: 'например 700', range: [150, 2500],
    src: ['measured', 'passport', 'unknown'],
    what: 'Ширина рабочей поверхности, на которую ставят штамп. Штамп должен поместиться на стол вместе с местом под прихваты.',
    how: ['Встаньте перед прессом, как оператор.', 'Рулеткой измерьте рабочую поверхность от левого края до правого. Если на столе лежит подштамповая плита, мерьте по ней.',
      'Боковые выступы и приливы не считайте, только ровную площадку.'] },
  { type: 'num', key: 'table_fb', label: 'Стол: спереди назад', must: true, fig: 'table:t-tablefb|press:t-tablefb', unit: 'мм', ph: 'например 500', range: [100, 2000],
    src: ['measured', 'passport', 'unknown'],
    what: 'Глубина рабочей поверхности, от вас в сторону станины.',
    how: ['Рулеткой от передней кромки стола (ближе к вам) до задней (у станины).', 'Если стол уходит под станину и края не видно, мерьте до станины.'] },
  { type: 'num', key: 'shut_max', label: 'Закрытая высота пресса (наибольшая)', must: true, fig: 'press:t-shut,t-slide,t-table', unit: 'мм', ph: 'например 280', range: [80, 1000],
    src: ['passport', 'measured', 'unknown'],
    what: 'Расстояние от стола до нижней плоскости ползуна, когда ползун опущен до конца, а регулировка стоит на самой большой высоте. Штамп по высоте должен быть ниже этого числа.',
    how: ['Лучший источник: паспорт пресса. Ищите «закрытая высота» или «расстояние между столом и ползуном в нижнем положении».',
      'Нет паспорта: наладчик выводит ползун в нижнее положение (пресс обесточен, маховик проворачивают вручную), вы измеряете рулеткой от стола до нижней плоскости ползуна.',
      'Мерьте до стола или до плиты, лежащей на столе, и отметьте это ниже.'],
    warn: 'под ползун руками не залезаем. Проворот и замер только с наладчиком, пресс обесточен.' },
  { type: 'choice', key: 'shut_ref', label: 'Закрытая высота мерена до чего', fig: 'press:t-shut,t-bolster,t-table', small: true,
    opts: [['table', 'До стола', ''], ['bolster', 'До плиты на столе', ''], ['unknown', 'Не знаю', '']] },
  { type: 'num', key: 'shut_adj', label: 'Регулировка закрытой высоты', must: true, fig: 'press:t-adjust', unit: 'мм', ph: 'например 60', range: [5, 400],
    src: ['passport', 'measured', 'unknown'],
    what: 'На сколько миллиметров можно поднять или опустить ползун регулировкой (винтом в верхней части ползуна). Показывает, штампы какой высоты встанут.',
    how: ['Смотрите в паспорте: «величина регулировки закрытой высоты», обычно 40–100 мм.', 'Паспорта нет: выберите «Не знаю».'] },
  { type: 'num', key: 'shank', label: 'Отверстие под хвостовик, диаметр', must: true, fig: 'ram:t-shank-d,t-jaws-in|caliper:t-jaws-in', unit: 'мм', ph: 'например 50', range: [15, 150],
    src: ['measured', 'passport', 'unknown'],
    what: 'В ползуне снизу есть круглое отверстие. В него входит хвостовик штампа, круглый штырь на верхней плите штампа. Нужен диаметр отверстия, чтобы штамп точно вставал.',
    how: ['Пресс выключен. Осмотрите нижнюю плоскость ползуна: круглое отверстие посередине.',
      'Штангенциркуль: маленькие верхние (внутренние) губки вставьте в отверстие и разведите до касания стенок. Держите поперёк отверстия и ищите наибольшее число.',
      'Вместо круглого отверстия паз, прижимная планка или его вообще не видно: сфотографируйте и выберите «Не знаю».'] },
  { type: 'multi', key: 'feed', label: 'Как подают металл', must: true, fig: 'press',
    what: 'Влияет на то, можно ли делать штампы для рулона.',
    opts: [['manual', 'Вручную', 'рабочий кладёт заготовку или полосу'], ['auto', 'Автоматическая подача', 'валки сами протягивают полосу'],
      ['decoiler', 'Разматыватель рулона', 'рулон на катушке'], ['unknown', 'Не знаю', '']] },
];
const PRESS_MORE = [
  { type: 'text', key: 'model', label: 'Модель пресса', fig: 'plate:t-np-model', ph: 'например КД2126', what: 'Написана на шильдике, в строке «Модель» или «Тип».' },
  { type: 'num', key: 'stroke', label: 'Ход ползуна', fig: 'plate:t-np-stroke|press:t-stroke', unit: 'мм', ph: 'например 100', range: [5, 500],
    src: ['nameplate', 'passport', 'unknown'],
    what: 'На сколько миллиметров ползун ходит вверх-вниз. Написано на шильдике («Ход ползуна») или в паспорте.' },
  { type: 'yn', key: 'bolster', label: 'Есть ли подштамповая плита', fig: 'press:t-bolster',
    what: 'Толстая плита, лежащая на столе. Штамп ставят на неё.' },
  { type: 'longtext', key: 'notes', label: 'Что ещё важно про этот пресс', what: 'Люфты, ремонты, ограничения, всё что цех знает про этот пресс.' },
];

const MACHINES = [
  ['lathe', 'Токарный станок', 'Деталь вращается в патроне, резец стоит на месте. Точит валы, втулки, колонки штампа.'],
  ['mill', 'Фрезерный станок', 'Вращается инструмент (фреза), стол с заготовкой ездит. Делает плиты, окна, карманы. Есть ли ЧПУ, напишите справа.'],
  ['drill', 'Сверлильный станок', 'Вертикальная стойка со сверлом и столом. Отверстия под винты и штифты.'],
  ['jig', 'Координатно-расточной станок', 'Похож на фрезерный, но с очень точными шкалами на столе. Отверстия под штифты и колонки с точностью в сотые доли мм. Такие станки редкие и стоят отдельно.'],
  ['grinder', 'Плоскошлифовальный станок', 'Абразивный круг над столом, часто с магнитной плитой. Делает поверхности ровными и параллельными: нужен для плит и закалённых деталей штампа.'],
  ['edm', 'Электроэрозионный проволочный станок', 'Тонкая проволока режет металл электрической искрой, часто в ванне с водой. Режет закалённую сталь по сложному контуру: пуансоны и окна матриц.'],
  ['guillotine', 'Гильотина (ножницы для листа)', 'Длинный нож режет лист по прямой, включается педалью. Справа напишите наибольшую толщину листа и длину реза.'],
  ['brake', 'Листогиб', 'Длинный клин давит лист в V-образную канавку. Нужен, если часть гибов можно делать без штампа.'],
];
const HEAT = [['own', 'Своя печь', 'закаливаем сами'], ['outsourced', 'На стороне', 'отдаём другой организации'], ['none', 'Не закаливаем', ''], ['unknown', 'Не знаю', '']];

const GLOSSARY = [
  ['Пресс', [
    ['Шильдик', 'Металлическая табличка на станине. На ней модель, усилие, ход, год выпуска. Обычно спереди или сбоку, размером с книжку.', 'plate:t-np-model,t-np-force,t-np-stroke|press:t-plate'],
    ['Ползун', 'Подвижная часть пресса, ходит вверх-вниз. К нему крепится верхняя часть штампа.', 'press:t-slide'],
    ['Стол', 'Неподвижная плита внизу. На неё ставят нижнюю часть штампа.', 'press:t-table|table:t-tabletop'],
    ['Подштамповая плита', 'Толстая плита, которая лежит на столе. Штамп ставят на неё.', 'press:t-bolster'],
    ['Провальное отверстие', 'Окно в столе. Через него вниз падают вырубленные кусочки.', 'press:t-opening|table:t-opening'],
    ['Ход ползуна', 'Расстояние, которое ползун проходит от самого верхнего положения до самого нижнего.', 'press:t-stroke'],
    ['ВМТ и НМТ', 'Верхняя и нижняя мёртвые точки: самое верхнее и самое нижнее положение ползуна. Штамп режет и гнёт около НМТ.', 'press:t-slide'],
    ['Закрытая высота пресса', 'Расстояние от стола до нижней плоскости ползуна в нижнем положении. Штамп должен помещаться в это расстояние.', 'press:t-shut'],
    ['Вылет', 'Расстояние от оси ползуна до станины. Чем больше вылет, тем дальше от края можно штамповать.', 'press:t-throat'],
    ['Хвостовик', 'Круглый штырь сверху штампа. Входит в отверстие ползуна и центрирует штамп.', 'die:t-d2|press:t-shank|ram:t-shank-hole'],
    ['кН и тонны', 'Усилие пресса пишут в килоньютонах или тоннах. Быстро: кН делить на 10, получатся тонны. 630 кН это около 63 т.', 'plate:t-np-force'],
  ]],
  ['Деталь', [
    ['Полка', 'Отогнутая часть детали. Высоту полки мерят от наружной стороны основания до края полки.', ''],
    ['Радиус гиба', 'Насколько плавно согнут металл. Измеряют внутри изгиба радиусомером.', 'radius:t-rin,t-gauge,t-thk'],
    ['Развёртка', 'Плоская заготовка, из которой гнётся деталь. Программа считает её по замерам детали и радиусу гиба.', ''],
    ['Подсечка (ступенька)', 'Два встречных изгиба рядом: часть детали поднимается и снова идёт ровно.', ''],
    ['Пружинение', 'После гибки металл слегка разгибается назад. Поэтому угол гибочного штампа уточняют при пробе.', ''],
  ]],
  ['Штамп', null],
  ['Инструмент', [
    ['Штангенциркуль', 'Измерительный инструмент с губками. Наружные (большие) губки мерят снаружи, внутренние (верхние маленькие) мерят отверстия, выдвижная штанга мерит глубину.', 'caliper'],
    ['Как читать нониус', 'Целые миллиметры читаем слева от нуля подвижной шкалы. Десятые по той риске подвижной шкалы, которая точно совпала с риской основной шкалы.', 'vernier:t-int,t-dec'],
  ]],
  ['Операции', [
    ['Пробивка и вырубка', 'Пробивка: пуансон вырезает отверстие, вырезанный кусок идёт в отход. Вырубка: пуансон вырезает саму деталь.', 'die:t-d7,t-d11,t-d12'],
    ['Перемычка', 'Полоска металла между двумя вырезами или между вырезом и краем. Слишком тонкая рвётся и коробится.', ''],
    ['Гильотина', 'Ножницы для листа: режут прямые заготовки. Штамп потом обрезает только сложные участки контура.', ''],
  ]],
];

/* ------------------------------------------------------------ состояние */
const blankPress = id => ({ id, name: '', kind: '', model: '', force: { u: 'kN' }, table_lr: {}, table_fb: {}, shut_max: {}, shut_ref: '', shut_adj: {}, shank: {},
  feed: [], stroke: {}, bolster: '', notes: '' });
function fresh() { return { v: 1, tab: 'presses', pseq: 1, shop: { name: '' }, presses: [blankPress('P1')], machines: {}, heat: '', mnotes: {}, part: {}, photos: {}, notes: '' }; }
function load() {
  try { const r = localStorage.getItem(KEY); if (!r) return null; const s = JSON.parse(r); return s && s.presses ? Object.assign(fresh(), s) : null; } catch (e) { return null; }
}
let S = load() || fresh();
const persist = debounce(() => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* хранилище недоступно */ } }, 250);
let REG = [];
const reg = (sec, done, unk) => REG.push({ sec, done, unk });

/* ------------------------------------------------------------ панель рисунков */
const panel = () => $('#figpanel');
function showFigs(spec, open) {
  if (!spec) return;
  const p = panel(); const figs = $$('figure[data-fig]', p);
  figs.forEach(f => { f.hidden = true; $$('.on', f).forEach(e => e.classList.remove('on')); const fg = $('.fig', f); if (fg) fg.classList.remove('has-on'); });
  spec.split('|').forEach(part => {
    const [key, ids = ''] = part.split(':'); const f = figs.find(x => x.dataset.fig === key.trim()); if (!f) return;
    f.hidden = false;
    const list = ids.split(',').map(s => s.trim()).filter(Boolean);
    list.forEach(id => ['', 'lab-'].forEach(pre => { const e = document.getElementById(key + '__' + pre + id); if (e) e.classList.add('on'); }));
    $$('.legend button', f).forEach(b => b.classList.toggle('on', list.includes(b.dataset.id)));
    if (list.length) $('.fig', f).classList.add('has-on');
  });
  if (open) document.body.classList.add('fig-open');
}
const closeSheet = () => document.body.classList.remove('fig-open');

/* ------------------------------------------------------------ поля */
function shell(def, controls, o = {}) {
  const el = h('div', { class: 'field' });
  el.append(h('div', { class: 'fhead' }, o.forId ? h('label', { for: o.forId }, def.label) : h('span', { class: 'lab', id: o.lid }, def.label),
    def.must ? h('span', { class: 'tag must' }, 'главное') : null));
  if (def.what) el.append(h('p', { class: 'what' }, def.what));
  controls.forEach(c => el.append(c));
  if (def.how || def.tip || def.warn) {
    const d = h('details', { class: 'how' }); if (o.open) d.open = true;
    d.append(h('summary', {}, def.how ? 'Где взять и как измерить' : 'Подсказка'));
    if (def.how) d.append(h('ol', {}, def.how.map(s => h('li', {}, s))));
    if (def.warn) d.append(h('p', { class: 'danger' }, 'Безопасность: ' + def.warn));
    if (def.tip) d.append(h('p', { class: 'tip' }, def.tip));
    el.append(d);
  }
  if (def.fig) {
    el.append(h('button', { type: 'button', class: 'showfig', onclick: () => showFigs(def.fig, true) }, 'Показать на рисунке'));
    el.addEventListener('focusin', () => showFigs(def.fig, false));
  }
  return el;
}
const commit = () => { persist(); refresh(); };

function fNum(def, holder, sec, o) {
  const st = holder[def.key] = holder[def.key] || {}; if (def.units && !st.u) st.u = def.units[0][0];
  const id = uid(); const input = h('input', { type: 'text', inputmode: 'decimal', autocomplete: 'off', id, placeholder: def.ph || '', 'aria-describedby': id + 'm' });
  input.value = st.v || '';
  const msg = h('p', { class: 'msg', id: id + 'm', 'aria-live': 'polite' });
  let unitEl;
  if (def.units) {
    unitEl = h('select', { 'aria-label': 'Единица измерения' }, def.units.map(([v, l]) => h('option', { value: v }, l)));
    unitEl.value = st.u; unitEl.addEventListener('change', () => { st.u = unitEl.value; sync(); commit(); });
  } else unitEl = h('span', { class: 'unit' }, def.unit || '');
  const btns = def.src.map(k => h('button', { type: 'button', class: 'chip' + (k === 'unknown' ? ' unk' : ''), 'aria-pressed': 'false',
    onclick: () => { st.s = st.s === k ? '' : k; if (st.s === 'unknown') { st.v = ''; input.value = ''; } sync(); commit(); } }, SRC[k]));
  function sync() {
    btns.forEach((b, i) => b.setAttribute('aria-pressed', st.s === def.src[i] ? 'true' : 'false'));
    input.disabled = st.s === 'unknown'; msg.className = 'msg'; msg.textContent = '';
    if (st.s === 'unknown') { msg.textContent = 'Записано «не знаю». Программа пометит это место и не будет считать его проверенным.'; return; }
    if (!st.v) return;
    const n = num(st.v);
    if (n == null) { msg.className = 'msg bad'; msg.textContent = 'Введите число, например ' + (def.ph || '12,5').replace('например ', '') + '.'; return; }
    let t = def.chk ? def.chk(n, st.u) : null;
    if (!t && def.range && (n < def.range[0] || n > def.range[1])) t = `Обычно от ${def.range[0]} до ${def.range[1]} ${def.unit || ''}. Проверьте число и единицу.`;
    if (t) { msg.className = 'msg bad'; msg.textContent = t; return; }
    if (!st.s) msg.textContent = 'Выберите ниже, откуда это число.';
  }
  input.addEventListener('input', () => { st.v = input.value.trim(); if (st.s === 'unknown') st.s = ''; sync(); commit(); });
  sync();
  if (sec) reg(sec, () => st.s === 'unknown' || (num(st.v) != null && !!st.s), () => st.s === 'unknown');
  return shell(def, [h('div', { class: 'row' }, input, unitEl), h('div', { class: 'chips', role: 'group', 'aria-label': 'Откуда число' }, btns), msg], Object.assign({ forId: id }, o));
}
function fText(def, holder, sec, o, key = def.key) {
  const id = uid(); const long = def.type === 'longtext';
  const input = long ? h('textarea', { id, placeholder: def.ph || '' }) : h('input', { type: 'text', id, class: 'wide', placeholder: def.ph || '', autocomplete: 'off' });
  input.value = holder[key] || '';
  input.addEventListener('input', () => { holder[key] = input.value; commit(); });
  if (sec && !long) reg(sec, () => !!(holder[key] || '').trim(), () => false);
  return shell(def, [h('div', { class: 'row' }, input)], Object.assign({ forId: id }, o));
}
function fChoice(def, holder, sec, o) {
  const lid = uid(); const btns = [];
  const paint = () => btns.forEach(([b, v]) => b.setAttribute('aria-checked', holder[def.key] === v ? 'true' : 'false'));
  def.opts.forEach(([v, t1, t2, fig]) => {
    const kids = [];
    const ic = def.key === 'kind' ? window.DATA.ICONS.press[v] : null; if (ic) kids.push(h('span', { class: 'fig ico' }, svgEl(ic)));
    kids.push(h('span', {}, h('span', { class: 't1' }, t1), t2 ? h('span', { class: 't2' }, t2) : null));
    const b = h('button', { type: 'button', class: 'opt', role: 'radio', 'aria-checked': 'false',
      onclick: () => { holder[def.key] = holder[def.key] === v ? '' : v; paint(); commit(); },
      onfocus: () => fig && showFigs(fig, false), onmouseenter: () => fig && showFigs(fig, false) }, kids);
    btns.push([b, v]);
  });
  paint();
  if (sec && !def.small) reg(sec, () => !!holder[def.key], () => holder[def.key] === 'unknown');
  return shell(def, [h('div', { class: 'opts' + (def.key === 'kind' ? ' icons' : ''), role: 'radiogroup', 'aria-labelledby': lid }, btns.map(x => x[0]))],
    Object.assign({ lid }, o));
}
function fMulti(def, holder, sec, o) {
  const lid = uid(); const btns = [];
  const paint = () => btns.forEach(([b, v]) => b.setAttribute('aria-pressed', holder[def.key].includes(v) ? 'true' : 'false'));
  holder[def.key] = holder[def.key] || [];
  def.opts.forEach(([v, t1, t2]) => {
    const b = h('button', { type: 'button', class: 'opt', 'aria-pressed': 'false', onclick: () => {
      let a = holder[def.key];
      if (v === 'unknown') a = a.includes('unknown') ? [] : ['unknown'];
      else { a = a.filter(x => x !== 'unknown'); a = a.includes(v) ? a.filter(x => x !== v) : a.concat(v); }
      holder[def.key] = a; paint(); commit(); } },
      h('span', {}, h('span', { class: 't1' }, t1), t2 ? h('span', { class: 't2' }, t2) : null));
    btns.push([b, v]);
  });
  paint();
  if (sec) reg(sec, () => holder[def.key].length > 0, () => holder[def.key].includes('unknown'));
  return shell(def, [h('div', { class: 'opts', role: 'group', 'aria-labelledby': lid }, btns.map(x => x[0]))], Object.assign({ lid }, o));
}
function fYN(def, holder, sec, o) {
  const lid = uid(); const btns = [];
  const paint = () => btns.forEach(([b, v]) => b.setAttribute('aria-pressed', holder[def.key] === v ? 'true' : 'false'));
  [['yes', 'Есть'], ['no', 'Нет'], ['unknown', 'Не знаю']].forEach(([v, t]) => {
    const b = h('button', { type: 'button', class: v === 'unknown' ? 'unk' : '', 'aria-pressed': 'false',
      onclick: () => { holder[def.key] = holder[def.key] === v ? '' : v; paint(); commit(); } }, t);
    btns.push([b, v]);
  });
  paint();
  if (sec) reg(sec, () => !!holder[def.key], () => holder[def.key] === 'unknown');
  return shell(def, [h('div', { class: 'seg', role: 'group', 'aria-labelledby': lid }, btns.map(x => x[0]))], Object.assign({ lid }, o));
}
function field(def, holder, sec, o = {}) {
  return ({ num: fNum, text: fText, longtext: fText, choice: fChoice, multi: fMulti, yn: fYN })[def.type](def, holder, sec, o);
}

/* ------------------------------------------------------------ разделы */
function renderPresses(root) {
  root.append(h('h2', { class: 'sec' }, 'Прессы'),
    h('p', { class: 'intro' }, 'На каждый пресс заведите отдельную карточку. Начните с главного: усилие, стол, закрытая высота, отверстие под хвостовик. Остальное можно позже. Когда нажмёте в поле, справа (на телефоне по кнопке «Показать на рисунке») подсветится то, о чём речь.'),
    h('div', { class: 'warn' }, h('b', {}, 'Безопасность'),
      'Замеры под ползуном и проворот маховика делает только наладчик или под его присмотром: пресс обесточен и заблокирован, руки под ползун не ставим. Шильдик, паспорт и размеры стола не требуют включать пресс.'));
  S.presses.forEach((p, i) => {
    const card = h('section', { class: 'card', 'aria-label': 'Пресс ' + (i + 1) });
    const nm = h('input', { type: 'text', class: 'nm', placeholder: 'Как назвать (например, у окна)', 'aria-label': 'Название пресса', autocomplete: 'off' });
    nm.value = p.name || ''; nm.addEventListener('input', () => { p.name = nm.value; persist(); });
    const head = h('div', { class: 'cardhead' }, h('h3', {}, 'Пресс ' + (i + 1)), nm);
    if (S.presses.length > 1) {
      const del = h('button', { type: 'button', class: 'btn ghost danger' }, 'Удалить');
      del.addEventListener('click', () => {
        if (del.dataset.arm) { S.presses.splice(i, 1); persist(); renderAll(); return; }
        del.dataset.arm = '1'; del.textContent = 'Точно удалить? Нажмите ещё раз';
        setTimeout(() => { delete del.dataset.arm; del.textContent = 'Удалить'; }, 4000);
      });
      head.append(del);
    }
    card.append(head);
    PRESS_MAIN.forEach(d => card.append(field(d, p, 'presses', { open: i === 0 })));
    const more = h('details', { class: 'how' }, h('summary', {}, 'Ещё данные про этот пресс (можно позже)'));
    PRESS_MORE.forEach(d => more.append(field(d, p, null, {})));
    card.append(more);
    root.append(card);
  });
  if (S.presses.length < MAX_PRESSES) root.append(h('div', { class: 'btns' }, h('button', { type: 'button', class: 'btn ghost', onclick: () => {
    S.pseq = (S.pseq || S.presses.length) + 1; S.presses.push(blankPress('P' + S.pseq)); persist(); renderAll(); setTab('presses'); window.scrollTo({ top: document.body.scrollHeight }); } }, 'Добавить пресс')));
}
function renderMachines(root) {
  root.append(h('h2', { class: 'sec' }, 'Станки и цех'),
    h('p', { class: 'intro' }, 'Нужно понять, что цех делает сам, а что придётся заказывать. От этого зависит, какие штампы мы проектируем: для закалённых деталей нужны шлифовка и закалка. Отметьте по каждому станку: есть или нет. В поле справа можно написать размеры или что важно.'));
  const box = h('div', { class: 'card' });
  S.mnotes = S.mnotes || {};
  MACHINES.forEach(([k, name, what]) => {
    S.machines[k] = S.machines[k] || '';
    const holder = S.machines; const btns = [];
    const paint = () => btns.forEach(([b, v]) => b.setAttribute('aria-pressed', holder[k] === v ? 'true' : 'false'));
    [['yes', 'Есть'], ['no', 'Нет'], ['unknown', 'Не знаю']].forEach(([v, t]) => btns.push([h('button', { type: 'button', class: v === 'unknown' ? 'unk' : '', 'aria-pressed': 'false',
      onclick: () => { holder[k] = holder[k] === v ? '' : v; paint(); commit(); } }, t), v]));
    paint();
    const note = h('input', { type: 'text', placeholder: 'Размеры, ЧПУ, точность (можно пусто)', 'aria-label': 'Заметка: ' + name, autocomplete: 'off' });
    note.value = S.mnotes[k] || ''; note.addEventListener('input', () => { S.mnotes[k] = note.value; persist(); });
    reg('machines', () => !!holder[k], () => holder[k] === 'unknown');
    box.append(h('div', { class: 'mach' }, h('span', { class: 'fig ico' }, svgEl(window.DATA.ICONS.machines[k])), h('div', {}, h('div', { class: 'lab' }, name), h('p', { class: 'what' }, what)),
      h('div', { class: 'ctl' }, h('div', { class: 'seg', role: 'group', 'aria-label': name }, btns.map(x => x[0])), note)));
  });
  root.append(box);
  const heat = { type: 'choice', key: 'heat', label: 'Закалка деталей штампа', must: true, what: 'Рабочие части штампа (пуансоны, матрицы) для серий больше 1000 штук обычно закаляют нагревом и быстрым охлаждением. Нужно понять, есть ли у вас такая возможность.', opts: HEAT };
  const c2 = h('div', { class: 'card' }); c2.append(field(heat, S, 'machines', {}));
  const nm = { type: 'text', key: 'name', label: 'Название цеха или компании', ph: 'для подписи отчётов' };
  c2.append(field(nm, S.shop, null, {}));
  root.append(c2);
}
function renderGlossary(root) {
  root.append(h('h2', { class: 'sec' }, 'Словарь'), h('p', { class: 'intro' }, 'Нажмите на слово: рисунок покажет, что это.'));
  const gl = h('div', { class: 'gl' });
  GLOSSARY.forEach(([title, items]) => {
    gl.append(h('h3', {}, title));
    const list = items || window.DATA.DIE_LEGEND.map(([n, id, t, d]) => [t, d, 'die:' + id]);
    list.forEach(([k, v, fig]) => gl.append(h('button', { type: 'button', class: 'term', onclick: () => showFigs(fig || 'press', true) },
      h('span', { class: 'k' }, k), h('span', { class: 'v' }, v))));
  });
  root.append(gl);
}
const PHOTOS = [['plate', 'Шильдик каждого пресса, крупно, чтобы читались все строки'], ['passport', 'Страница паспорта пресса с техническими характеристиками (если есть)'],
  ['pressview', 'Каждый пресс целиком сбоку: видно стол, ползун, станину'], ['table', 'Стол каждого пресса сверху, с рулеткой вдоль стола']];

function summaryRows() {
  const secs = { presses: [0, 0, 0], machines: [0, 0, 0] };
  REG.forEach(r => { const s = secs[r.sec]; s[1]++; if (r.done()) { s[0]++; if (r.unk()) s[2]++; } });
  return secs;
}
function renderSend(root) {
  root.append(h('h2', { class: 'sec' }, 'Отправить'),
    h('p', { class: 'intro' }, 'Нажмите «Скопировать» и отправьте текст тому, кто ведёт проект. Фото пришлите отдельно. Неполные данные тоже можно отправлять: программа покажет, чего не хватает. Детали сюда не вносятся: для каждой новой детали будет свой простой раздел.'));
  const sum = h('table', { class: 'sum', id: 'sumtab' }); root.append(sum);
  const out = h('textarea', { class: 'out', id: 'exportbox', readonly: true, 'aria-label': 'Текст для отправки' });
  const status = h('p', { class: 'status', 'aria-live': 'polite', id: 'sendstatus' });
  const copyBtn = h('button', { type: 'button', class: 'btn', onclick: async () => {
    out.value = exportText(); let ok = false;
    try { await navigator.clipboard.writeText(out.value); ok = true; } catch (e) { try { out.select(); ok = document.execCommand('copy'); } catch (e2) { ok = false; } }
    status.textContent = ok ? 'Скопировано. Вставьте в сообщение.' : 'Не удалось скопировать автоматически. Выделите текст ниже и скопируйте вручную.'; } }, 'Скопировать');
  const saveBtn = h('button', { type: 'button', class: 'btn ghost', id: 'savebtn', hidden: true, onclick: async () => {
    try { await DL.save({ filename: 'shop-data.json', data: exportText() }); status.textContent = 'Файл сохранён.'; } catch (e) { status.textContent = e && e.code === 'declined' ? 'Сохранение отменено.' : 'Не удалось сохранить файл. Используйте «Скопировать».'; } } }, 'Сохранить файлом');
  root.append(h('div', { class: 'btns' }, copyBtn, saveBtn), status);
  root.append(h('details', { class: 'how' }, h('summary', {}, 'Показать текст'), out));
  root.append(h('h3', { class: 'sub' }, 'Фото, которые нужны'));
  const ul = h('ul', { class: 'checks' });
  PHOTOS.forEach(([k, t]) => { const cb = h('input', { type: 'checkbox' }); cb.checked = !!S.photos[k]; cb.addEventListener('change', () => { S.photos[k] = cb.checked; persist(); });
    ul.append(h('li', {}, h('label', {}, cb, h('span', {}, t)))); });
  root.append(ul);
  root.append(h('h3', { class: 'sub' }, 'Что понадобится от конструктора'),
    h('p', { class: 'intro' }, 'Один раз: лист «Нормы цеха», около 30 минут (10 главных пунктов, остальное просмотреть). Дальше на каждый штамп лист проверки, около 10 минут. Отвечать можно голосовым. Числа, зазоры и усилия считает программа, конструктор проверяет то, что видно только по опыту.'));
  const notes = { type: 'longtext', key: 'notes', label: 'Что ещё важно', what: 'Любые замечания по цеху, деталям и оборудованию.' };
  root.append(field(notes, S, null, {}));
  root.append(h('h3', { class: 'sub' }, 'Продолжить на другом устройстве'),
    h('p', { class: 'intro' }, 'Данные хранятся в этом браузере. Чтобы перенести на другой телефон или компьютер, скопируйте черновик и вставьте там.'));
  const dbox = h('textarea', { class: 'out', 'aria-label': 'Черновик', placeholder: 'Сюда вставьте черновик' });
  const dstat = h('p', { class: 'status', 'aria-live': 'polite' });
  root.append(dbox, h('div', { class: 'btns' },
    h('button', { type: 'button', class: 'btn ghost', onclick: async () => { dbox.value = JSON.stringify(S); try { await navigator.clipboard.writeText(dbox.value); dstat.textContent = 'Черновик скопирован.'; } catch (e) { dbox.select(); dstat.textContent = 'Скопируйте текст вручную.'; } } }, 'Скопировать черновик'),
    h('button', { type: 'button', class: 'btn ghost', onclick: () => { try { const s = JSON.parse(dbox.value); if (!s || !s.presses) throw 0; S = Object.assign(fresh(), s); persist(); renderAll(); dstat.textContent = ''; } catch (e) { dstat.textContent = 'Это не черновик. Вставьте текст, скопированный кнопкой «Скопировать черновик».'; } } }, 'Загрузить черновик')), dstat);
  const clr = h('button', { type: 'button', class: 'btn ghost danger' }, 'Очистить всё');
  clr.addEventListener('click', () => { if (clr.dataset.arm) { S = fresh(); persist(); renderAll(); return; }
    clr.dataset.arm = '1'; clr.textContent = 'Точно очистить всё? Нажмите ещё раз'; setTimeout(() => { delete clr.dataset.arm; clr.textContent = 'Очистить всё'; }, 4000); });
  root.append(h('div', { class: 'btns' }, clr));
}

/* ------------------------------------------------------------ выгрузка */
const r3 = x => Math.round(x * 1000) / 1000;
function val(st, mult = 1) {
  if (!st || st.s === 'unknown' || num(st.v) == null) return { value: null, source: 'unknown' };
  const o = { value: r3(num(st.v) * mult), source: st.s || 'stated' }; if (!st.s) o.note = 'источник не указан'; return o;
}
function exportObj() {
  const pr = S.presses.map((p, i) => ({
    id: p.id, name: (p.name || '').trim() || 'Пресс ' + (i + 1), kind: p.kind && p.kind !== 'unknown' ? p.kind : 'unknown',
    model: p.model ? { value: p.model.trim(), source: 'stated' } : { value: null, source: 'unknown' },
    force_kn: val(p.force, p.force.u === 't' ? 9.80665 : 1), stroke_mm: val(p.stroke), shut_height_max_mm: val(p.shut_max),
    shut_height_measured_to: p.shut_ref || null, shut_adjust_mm: val(p.shut_adj), table_lr_mm: val(p.table_lr), table_fb_mm: val(p.table_fb),
    shank_d_mm: val(p.shank), feed: (p.feed || []).filter(x => x !== 'unknown').map(x => x === 'auto' ? 'roll' : x === 'decoiler' ? 'coil' : x),
    has_bolster_plate: p.bolster || null, notes: (p.notes || '').trim() }));
  const yn = v => v === 'yes' ? true : v === 'no' ? false : null;
  return {
    format: 'stamp-shop-data/1', exported_at: new Date().toISOString(),
    shop: { name: (S.shop.name || '').trim(), has_guillotine: yn(S.machines.guillotine),
      heat_treatment: ({ own: 'yes', outsourced: 'outsourced', none: 'no' })[S.heat] || 'unknown', presses: pr,
      machines: MACHINES.map(([k, name]) => ({ type: k, name, available: S.machines[k] ? (S.machines[k] === 'unknown' ? null : S.machines[k] === 'yes') : null,
        answered: !!S.machines[k], note: (S.mnotes[k] || '').trim() })) },
    photos_taken: PHOTOS.filter(([k]) => S.photos[k]).map(([k]) => k), notes: (S.notes || '').trim(),
    page_progress: (() => { const s = summaryRows(); const o = {}; ['presses', 'machines'].forEach(k => { o[k] = { answered: s[k][0], total: s[k][1], unknown: s[k][2] }; }); return o; })() };
}
const exportText = () => JSON.stringify(exportObj(), null, 2);

/* ------------------------------------------------------------ вкладки, прогресс, старт */
const TABS = [['presses', 'Прессы', 'presses', 'press'], ['machines', 'Станки и цех', 'machines', null],
  ['glossary', 'Словарь', null, 'press'], ['send', 'Отправить', null, null]];
let DL = null;
function setTab(name) {
  S.tab = name; persist();
  TABS.forEach(([k]) => { const b = $('#tab-' + k), s = $('#sec-' + k); b.setAttribute('aria-selected', k === name ? 'true' : 'false'); s.hidden = k !== name; });
  const t = TABS.find(x => x[0] === name); const lay = $('#layout');
  lay.classList.toggle('nofig', !t[3]); closeSheet();
  if (t[3]) showFigs(t[3], false);
  if (name === 'send') { $('#exportbox').value = exportText(); updateSummary(); }
}
function updateSummary() {
  const secs = summaryRows(); const rows = [['presses', 'Прессы'], ['machines', 'Станки и цех']];
  const t = $('#sumtab'); if (!t) return; t.replaceChildren();
  rows.forEach(([k, n]) => { const s = secs[k]; t.append(h('tr', {}, h('td', {}, n), h('td', {}, `${s[0]} из ${s[1]}` + (s[2] ? `, из них «не знаю»: ${s[2]}` : '')))); });
}
function refresh() {
  const secs = summaryRows(); let d = 0, t = 0, u = 0;
  Object.values(secs).forEach(s => { d += s[0]; t += s[1]; u += s[2]; });
  $('#progfill').style.width = t ? Math.round(d / t * 100) + '%' : '0';
  $('#progtxt').textContent = `Заполнено ${d} из ${t}` + (u ? `. Из них «не знаю»: ${u}` : '') + '.';
  TABS.forEach(([k, , sec]) => { const n = $('#tab-' + k + ' .n'); if (n && sec) n.textContent = `${secs[sec][0]}/${secs[sec][1]}`; });
  if (S.tab === 'send') { updateSummary(); const b = $('#exportbox'); if (b) b.value = exportText(); }
}
function renderAll() {
  REG = []; _uid = 0;
  const map = { presses: renderPresses, machines: renderMachines, glossary: renderGlossary, send: renderSend };
  TABS.forEach(([k]) => { const s = $('#sec-' + k); s.replaceChildren(); map[k](s); });
  setTab(S.tab || 'presses'); refresh();
  if (DL) { const b = $('#savebtn'); if (b) b.hidden = false; }
}
function init() {
  const nav = $('#tabs');
  TABS.forEach(([k, n, sec]) => nav.append(h('button', { type: 'button', role: 'tab', class: 'tab', id: 'tab-' + k, 'aria-controls': 'sec-' + k, onclick: () => { setTab(k); $('#sec-' + k).scrollIntoView({ block: 'start' }); } },
    n, sec ? h('span', { class: 'n' }, '') : null)));
  $('#sheetclose').addEventListener('click', closeSheet); $('#scrim').addEventListener('click', closeSheet);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });
  $$('#figpanel .legend button').forEach(b => b.addEventListener('click', () => showFigs('die:' + b.dataset.id, false)));
  renderAll();
  try { if (window.claude && window.claude.use) window.claude.use('downloads').then(d => { DL = d; const b = $('#savebtn'); if (b && d) b.hidden = false; }).catch(() => {}); } catch (e) { /* без capability */ }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
