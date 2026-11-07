/**
 * Панель проектов: таблица с мгновенным поиском, фильтрами, сортировкой, группировкой и постраничным выводом,
 * плитки-итоги, боковая панель создания / изменения проекта.
 *
 * Данные приходят из <script type="application/json" id="pj-data"> (см. projects.html).
 * Настройки фильтров запоминаются на сервере (POST /projects/filters) для текущего пользователя.
 */
(function () {
  'use strict';

  var rootEl = document.getElementById('pj-root');
  var dataEl = document.getElementById('pj-data');
  if (!rootEl || !dataEl) return;

  var CTX = JSON.parse(dataEl.textContent);
  var DAY = 86400000;
  var STATUSES = CTX.statuses || [];
  var OPEN = CTX.openStatuses || [];
  var SCOL = {
    'В работе': 'var(--color-primary)', 'Запланирован': 'var(--color-muted)', 'Расчеты завершены': 'var(--pj-ok)',
    'Завершен': 'var(--pj-ok)', 'Закрыт': 'var(--color-muted)', 'Отмена': 'var(--pj-bad)'
  };
  var SCLASS = {
    'В работе': 'is-work', 'Запланирован': 'is-plan', 'Расчеты завершены': 'is-calc',
    'Завершен': 'is-done', 'Закрыт': 'is-closed', 'Отмена': 'is-cancel'
  };
  var ACT_LABEL = {
    actual: 'Актуальные и будущие', '30': 'Актуальные + завершённые за 30 дней',
    '90': 'Актуальные + завершённые за 90 дней', all: 'Все проекты, включая архив'
  };

  // ---------- утилиты
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pad(n) { return n < 10 ? '0' + n : String(n); }
  function dnOfIso(s) { if (!s) return null; var p = s.split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / DAY; }
  function dnOfDate(d) { return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / DAY; }
  var T = dnOfDate(new Date());
  function fmtF(n) { if (n == null) return '—'; var d = new Date(n * DAY); return pad(d.getUTCDate()) + '.' + pad(d.getUTCMonth() + 1) + '.' + d.getUTCFullYear(); }
  function fmtS(n) { var d = new Date(n * DAY); return pad(d.getUTCDate()) + '.' + pad(d.getUTCMonth() + 1); }
  function parseRu(s) {
    var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec((s || '').trim());
    if (!m) return null;
    var n = Date.UTC(+m[3], +m[2] - 1, +m[1]) / DAY;
    return new Date(n * DAY).getUTCMonth() === +m[2] - 1 ? n : null;
  }
  function money(n) { return n == null ? '—' : Math.round(n).toLocaleString('ru-RU') + ' ₽'; }
  function plural(n, a, b, c) {
    var m100 = n % 100, m10 = n % 10;
    if (m100 > 10 && m100 < 20) return c;
    return m10 === 1 ? a : (m10 >= 2 && m10 <= 4 ? b : c);
  }
  function hue(s) { var h = 0; s = String(s); for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h; }
  function avatar(n) {
    if (!n) return '';
    var ini = n.replace(/\./g, ' ').trim().split(/\s+/).map(function (x) { return x.charAt(0); }).slice(0, 2).join('').toUpperCase();
    return '<span class="pj-av" style="background:hsl(' + hue(n) + ' 52% 42%)">' + esc(ini) + '</span>';
  }

  // ---------- данные
  var uid = 0;
  var DATA = (CTX.rows || []).map(function (r) {
    return {
      id: ++uid, contract: r.contract, etap: r.etap, url: r.url, kind: r.kind, client: r.client, exec: r.exec, chief: r.chief,
      status: r.status, ps: dnOfIso(r.ps), pe: dnOfIso(r.pe), cs: dnOfIso(r.cs), ce: dnOfIso(r.ce), act: dnOfIso(r.act),
      period: r.period, esum: r.esum, csum: r.csum, tasks: r.tasks, done: r.done
    };
  });
  function isOpen(p) { return OPEN.indexOf(p.status) >= 0; }

  var S = {
    q: '', status: '', flag: '', act: 'actual', sf: '', st: '', ef: '', et: '',
    kinds: {}, execs: {}, chiefs: {}, sort: { col: 'end', asc: false }, group: 'none', size: 25,
    page: 1, open: {}, collapsed: {}, openMs: null
  };
  var DEFAULTS_KEYS = ['status', 'flag', 'act', 'sf', 'st', 'ef', 'et', 'group', 'size', 'sort'];
  (function applySaved() {
    var sv = CTX.saved;
    if (!sv || typeof sv !== 'object') return;
    DEFAULTS_KEYS.forEach(function (k) { if (sv[k] !== undefined && sv[k] !== null) S[k] = sv[k]; });
    ['kinds', 'execs', 'chiefs'].forEach(function (k) { (sv[k] || []).forEach(function (v) { S[k][v] = 1; }); });
    if (S.status && STATUSES.indexOf(S.status) < 0) S.status = '';
    if (!CTX.showChief && S.group === 'chief') S.group = 'none';
  })();

  // ---------- сохранение настроек на сервере (с задержкой, чтобы не слать запрос на каждое нажатие)
  var persistTimer = null;
  function persist() {
    clearTimeout(persistTimer);
    persistTimer = setTimeout(function () {
      var body = {
        status: S.status, flag: S.flag, act: S.act, sf: S.sf, st: S.st, ef: S.ef, et: S.et,
        kinds: Object.keys(S.kinds), execs: Object.keys(S.execs), chiefs: Object.keys(S.chiefs),
        group: S.group, size: S.size, sort: S.sort
      };
      try {
        fetch(CTX.filtersUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          body: JSON.stringify(body)
        });
      } catch (e) { /* настройки не критичны */ }
    }, 400);
  }
  function resetFilters() {
    S.q = ''; S.status = ''; S.flag = ''; S.act = 'actual'; S.sf = ''; S.st = ''; S.ef = ''; S.et = '';
    S.kinds = {}; S.execs = {}; S.chiefs = {};
    $('pj-q').value = '';
  }

  // ---------- фильтрация
  // «Актуальные»: проект ещё идёт (в работе / запланирован, в том числе просроченный) или его плановое окончание сегодня и позже.
  function actualOk(p) {
    if (S.act === 'all') return true;
    if (isOpen(p) || p.pe == null) return true;
    return p.pe >= T - (S.act === 'actual' ? 0 : +S.act);
  }
  function has(set) { return Object.keys(set).length > 0; }
  function matches(p, skipStatus) {
    var q = S.q.trim().toLowerCase();
    if (q && (p.contract + ' ' + p.client + ' ' + p.exec + ' ' + p.chief).toLowerCase().indexOf(q) < 0) return false;
    if (has(S.kinds) && !S.kinds[p.kind]) return false;
    if (has(S.execs) && !S.execs[p.exec]) return false;
    if (has(S.chiefs) && !S.chiefs[p.chief]) return false;
    var sf = parseRu(S.sf), st = parseRu(S.st), ef = parseRu(S.ef), et = parseRu(S.et);
    if (sf != null && (p.ps == null || p.ps < sf)) return false;
    if (st != null && (p.ps == null || p.ps > st)) return false;
    if (ef != null && (p.pe == null || p.pe < ef)) return false;
    if (et != null && (p.pe == null || p.pe > et)) return false;
    if (S.flag === 'soon' && !(isOpen(p) && p.pe != null && p.pe >= T && p.pe <= T + 14)) return false;
    if (S.flag === 'late' && !(isOpen(p) && p.pe != null && p.pe < T)) return false;
    if (!skipStatus && S.status && p.status !== S.status) return false;
    return true;
  }
  function deadline(p) {
    if (!isOpen(p)) return { cls: 'gray', txt: p.status === 'Отмена' ? 'отменён' : (p.act ? 'акт ' + fmtS(p.act) : 'завершён') };
    if (p.pe == null) return { cls: 'gray', txt: 'срок не задан' };
    if (p.pe < T) return { cls: 'bad', txt: 'просрочен ' + (T - p.pe) + ' дн.' };
    var d = p.pe - T;
    return { cls: d <= 14 ? 'warn' : 'ok', txt: d === 0 ? 'срок сегодня' : 'осталось ' + d + ' дн.' };
  }
  function toast(text) {
    var e = $('pj-toast');
    e.textContent = text; e.classList.add('is-show');
    clearTimeout(toast.t); toast.t = setTimeout(function () { e.classList.remove('is-show'); }, 3500);
  }

  // ---------- фильтры: выпадающие списки с галочками, статусы, теги
  function sortedUnique(key) {
    var seen = {}, out = [];
    DATA.forEach(function (p) { if (p[key] && !seen[p[key]]) { seen[p[key]] = 1; out.push(p[key]); } });
    return out.sort(function (a, b) { return a.length - b.length || a.localeCompare(b, 'ru'); });
  }
  var KINDS = sortedUnique('kind'), EXECS = sortedUnique('exec'), CHIEFS = CTX.chiefs || [];

  function msel(key, label, opts, set) {
    var n = Object.keys(set).length;
    var html = '<div class="pj-ms"><button type="button" data-ms="' + key + '" class="' + (n ? 'has' : '') + '" aria-expanded="' + (S.openMs === key) + '">' + label + (n ? ': ' + n : '') + ' ▾</button>';
    if (S.openMs === key) {
      html += '<div class="pj-pop">' + opts.map(function (o) {
        return '<label><input type="checkbox" data-o="' + key + '" value="' + esc(o) + '"' + (set[o] ? ' checked' : '') + ' />' + esc(o) + '</label>';
      }).join('') + '</div>';
    }
    return html + '</div>';
  }

  function renderFilters(base) {
    var hasPeriod = S.sf || S.st || S.ef || S.et;
    var dateBox = '';
    if (S.openMs === 'per') {
      dateBox = '<div class="pj-pop pj-pop--dates"><div class="pj-dr2">' +
        '<div class="pj-lbl">Начало проекта</div><div class="pj-dates"><span>с</span><input id="pj-f-sf" class="js-date" value="' + esc(S.sf) + '" placeholder="dd.mm.YYYY" /><span>по</span><input id="pj-f-st" class="js-date" value="' + esc(S.st) + '" placeholder="dd.mm.YYYY" /></div>' +
        '<div class="pj-lbl">Окончание проекта</div><div class="pj-dates"><span>с</span><input id="pj-f-ef" class="js-date" value="' + esc(S.ef) + '" placeholder="dd.mm.YYYY" /><span>по</span><input id="pj-f-et" class="js-date" value="' + esc(S.et) + '" placeholder="dd.mm.YYYY" /></div>' +
        '<div class="pj-hint">Границы можно задавать по отдельности: например, «окончание с сегодняшней даты» покажет всё, что ещё не закончилось.</div></div></div>';
    }
    $('pj-msels').innerHTML = msel('kind', 'Вид договора', KINDS, S.kinds) + msel('exec', 'Исполнитель', EXECS, S.execs) +
      (CTX.role === 'director' ? msel('chief', 'Руководитель', CHIEFS, S.chiefs) : '') +
      '<div class="pj-ms"><button type="button" data-ms="per" class="' + (hasPeriod ? 'has' : '') + '" aria-expanded="' + (S.openMs === 'per') + '">Даты проекта' + (hasPeriod ? ': заданы' : '') + ' ▾</button>' + dateBox + '</div>';

    Array.prototype.forEach.call(document.querySelectorAll('[data-ms]'), function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); S.openMs = S.openMs === b.getAttribute('data-ms') ? null : b.getAttribute('data-ms'); renderFilters(base); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('input[data-o]'), function (i) {
      i.addEventListener('change', function () {
        var set = { kind: S.kinds, exec: S.execs, chief: S.chiefs }[i.getAttribute('data-o')];
        if (i.checked) set[i.value] = 1; else delete set[i.value];
        S.page = 1; render();
      });
    });
    [['pj-f-sf', 'sf'], ['pj-f-st', 'st'], ['pj-f-ef', 'ef'], ['pj-f-et', 'et']].forEach(function (pair) {
      var e = $(pair[0]);
      if (!e) return;
      e.addEventListener('change', function () { S[pair[1]] = e.value; S.page = 1; render(); });
    });
    if (S.openMs === 'per' && window.initDatePickers) window.initDatePickers($('pj-msels'));

    var rest = base.filter(function (p) { return matches(p, true); });
    $('pj-schips').innerHTML = '<button type="button" class="pj-chip' + (S.status === '' ? ' is-on' : '') + '" data-st="">Все <b>' + rest.length + '</b></button>' +
      STATUSES.map(function (s) {
        var n = rest.filter(function (p) { return p.status === s; }).length;
        return '<button type="button" class="pj-chip' + (S.status === s ? ' is-on' : '') + '" data-st="' + esc(s) + '"><i style="background:' + (SCOL[s] || 'var(--color-muted)') + '"></i>' + esc(s) + ' <b>' + n + '</b></button>';
      }).join('');
    Array.prototype.forEach.call(document.querySelectorAll('[data-st]'), function (c) {
      c.addEventListener('click', function () { S.status = c.getAttribute('data-st'); S.flag = ''; S.page = 1; render(); });
    });

    var tags = [];
    if (S.flag) tags.push({ k: 'flag', t: S.flag === 'soon' ? 'Срок ≤ 14 дней' : 'Просрочено' });
    Object.keys(S.kinds).forEach(function (v) { tags.push({ k: 'kind', t: 'Вид: ' + v, v: v }); });
    Object.keys(S.execs).forEach(function (v) { tags.push({ k: 'exec', t: 'Исп.: ' + v, v: v }); });
    Object.keys(S.chiefs).forEach(function (v) { tags.push({ k: 'chief', t: 'РП: ' + v, v: v }); });
    if (S.act !== 'actual') tags.push({ k: 'act', t: 'Показ: ' + ACT_LABEL[S.act] });
    if (S.sf || S.st) tags.push({ k: 'sf', t: 'Начало: ' + (S.sf || '…') + ' — ' + (S.st || '…') });
    if (S.ef || S.et) tags.push({ k: 'ef', t: 'Окончание: ' + (S.ef || '…') + ' — ' + (S.et || '…') });
    if (S.q) tags.push({ k: 'q', t: 'Поиск: ' + S.q });
    $('pj-tags').innerHTML = (tags.length ? 'Активные фильтры: ' + tags.map(function (t, i) {
      return '<span class="pj-tag">' + esc(t.t) + '<button type="button" data-tg="' + i + '" aria-label="Убрать фильтр">×</button></span>';
    }).join('') + ' <button type="button" class="button is-light is-small" id="pj-tg-clear">Сбросить к умолчанию</button>' : '') +
      '<span class="pj-saved">✓ Настройки фильтров сохраняются для вашей учётной записи</span>';
    Array.prototype.forEach.call(document.querySelectorAll('[data-tg]'), function (b) {
      b.addEventListener('click', function () {
        var t = tags[+b.getAttribute('data-tg')];
        if (t.k === 'flag') S.flag = '';
        else if (t.k === 'kind') delete S.kinds[t.v];
        else if (t.k === 'exec') delete S.execs[t.v];
        else if (t.k === 'chief') delete S.chiefs[t.v];
        else if (t.k === 'act') S.act = 'actual';
        else if (t.k === 'sf') { S.sf = ''; S.st = ''; }
        else if (t.k === 'ef') { S.ef = ''; S.et = ''; }
        else if (t.k === 'q') { S.q = ''; $('pj-q').value = ''; }
        S.page = 1; render();
      });
    });
    var clr = $('pj-tg-clear');
    if (clr) clr.addEventListener('click', function () { resetFilters(); S.page = 1; render(); });
  }

  // ---------- таблица
  function sortVal(p, c) {
    if (c === 'id') return p.contract.toLowerCase() + ('00' + p.etap).slice(-3);
    if (c === 'client') return p.client.toLowerCase();
    if (c === 'chief') return p.chief;
    if (c === 'end') return p.pe == null ? -1e9 : p.pe;
    if (c === 'status') return STATUSES.indexOf(p.status);
    return p.tasks ? p.done / p.tasks : 0;
  }
  function rowHtml(p) {
    var dl = deadline(p), open = !!S.open[p.id];
    var fill = 0;
    if (p.ps != null && p.pe != null) {
      var el = Math.max(0, Math.min(1, (T - p.ps) / Math.max(1, p.pe - p.ps)));
      fill = isOpen(p) ? el : (p.status === 'Отмена' ? 0 : 1);
    }
    var kind = p.kind ? '<span class="pj-kd">' + esc(p.kind) + '</span>' : '';
    var period = p.ps != null || p.pe != null ? (p.ps != null ? fmtS(p.ps) : '…') + ' — ' + (p.pe != null ? fmtF(p.pe) : '…') : 'даты не заданы';
    return '<div class="pj-prow' + (open ? ' is-open' : '') + '" data-id="' + p.id + '">' +
      '<button type="button" class="pj-chev" data-ex="' + p.id + '" aria-label="Подробности" aria-expanded="' + open + '">▶</button>' +
      '<div class="pj-id"><a href="' + esc(p.url) + '">' + esc(p.contract) + '</a><span class="pj-et">этап ' + esc(p.etap) + '</span>' + kind + '</div>' +
      '<div class="pj-cl"><div class="pj-ell" title="' + esc(p.client) + '">' + esc(p.client || '—') + '</div><div class="pj-ell pj-muted pj-small" title="' + esc(p.exec) + '">Исп.: ' + esc(p.exec || '—') + '</div></div>' +
      (CTX.showChief ? '<div class="pj-who">' + avatar(p.chief) + '<span class="pj-ell">' + esc(p.chief) + '</span></div>' : '') +
      '<div class="pj-per" style="--c:' + (SCOL[p.status] || 'var(--color-muted)') + '"><div class="pj-bar"><i style="width:' + fill * 100 + '%"></i></div><div class="pj-d">' + period + '</div></div>' +
      '<div><span class="pj-pill ' + (SCLASS[p.status] || 'is-plan') + '">' + esc(p.status || '—') + '</span><span class="pj-dl is-' + dl.cls + '">' + dl.txt + '</span></div>' +
      '<div class="pj-tk" title="Задач выполнено: ' + p.done + ' из ' + p.tasks + '"><div class="pj-bar pj-bar--ok"><i style="width:' + (p.tasks ? p.done / p.tasks * 100 : 0) + '%"></i></div><span>' + p.done + '/' + p.tasks + '</span></div>' +
      '<div><button type="button" class="pj-dots" data-menu="' + p.id + '" aria-label="Действия">⋯</button></div></div>' +
      (open ? detHtml(p) : '');
  }
  function kv(k, v) { return '<div><div class="pj-k">' + k + '</div><div class="pj-v">' + v + '</div></div>'; }
  function detHtml(p) {
    return '<div class="pj-pdet"><div class="pj-dg">' +
      kv('Договор', fmtF(p.cs) + ' — ' + fmtF(p.ce)) + kv('План проекта', fmtF(p.ps) + ' — ' + fmtF(p.pe)) +
      kv('Период проверки', esc(p.period || '—')) + kv('Дата акта', fmtF(p.act)) +
      kv('Сумма этапа', money(p.esum)) + (CTX.canEdit ? kv('Сумма договора', money(p.csum)) : '') +
      kv('Заказчик', esc(p.client || '—')) + kv('Задачи', p.done + ' из ' + p.tasks + ' выполнено') + '</div>' +
      '<div class="pj-acts"><a class="button is-primary is-small" href="' + esc(p.url) + '">Открыть карточку</a>' +
      (CTX.canEdit ? '<button type="button" class="button is-light is-small" data-edit="' + p.id + '">Изменить</button><button type="button" class="button is-light is-small" data-addetap="' + p.id + '">Добавить этап</button>' : '') +
      '</div></div>';
  }

  function render() {
    var base = DATA.filter(actualOk), hidden = DATA.length - base.length;
    var soon = base.filter(function (p) { return isOpen(p) && p.pe != null && p.pe >= T && p.pe <= T + 14; }).length;
    var late = base.filter(function (p) { return isOpen(p) && p.pe != null && p.pe < T; }).length;
    var work = base.filter(function (p) { return p.status === 'В работе'; }).length;
    function tile(k, cls, t, v, s, on) {
      return '<button type="button" class="pj-kpi ' + cls + (on ? ' is-on' : '') + '" data-k="' + k + '"><div class="pj-kpi__t">' + t + '</div><div class="pj-kpi__v">' + v + '</div><div class="pj-kpi__s">' + s + '</div></button>';
    }
    $('pj-kpis').innerHTML = tile('all', '', 'Актуальных этапов', base.length, S.act === 'all' ? 'всего доступно вам' : 'без старых проектов', !S.status && !S.flag) +
      tile('work', '', 'В работе', work, 'активные проекты', S.status === 'В работе') +
      tile('soon', 'is-warn', 'Срок ≤ 14 дней', soon, 'скоро закончатся', S.flag === 'soon') +
      tile('late', late ? 'is-bad' : 'is-ok', 'Просрочено', late, late ? 'требуют внимания' : 'просрочек нет', S.flag === 'late');
    Array.prototype.forEach.call(document.querySelectorAll('[data-k]'), function (b) {
      b.addEventListener('click', function () {
        var k = b.getAttribute('data-k');
        S.status = k === 'work' ? 'В работе' : ''; S.flag = (k === 'soon' || k === 'late') ? k : ''; S.page = 1; render();
      });
    });

    $('pj-act').innerHTML = [['actual', 'Актуальные'], ['30', '+ 30 дн.'], ['90', '+ 90 дн.'], ['all', 'Все']].map(function (a) {
      return '<button type="button" data-act="' + a[0] + '" class="' + (S.act === a[0] ? 'is-on' : '') + '" title="' + ACT_LABEL[a[0]] + '">' + a[1] + '</button>';
    }).join('');
    Array.prototype.forEach.call(document.querySelectorAll('[data-act]'), function (b) {
      b.addEventListener('click', function () { S.act = b.getAttribute('data-act'); S.page = 1; render(); });
    });
    $('pj-group').value = S.group;
    renderFilters(base);

    var rows = base.filter(function (p) { return matches(p); });
    var sc = S.sort;
    rows = rows.slice().sort(function (a, b) {
      var x = sortVal(a, sc.col), y = sortVal(b, sc.col);
      return ((x < y ? -1 : (x > y ? 1 : 0)) * (sc.asc ? 1 : -1)) || (a.id - b.id);
    });
    $('pj-count').innerHTML = 'Показано ' + rows.length + ' из ' + base.length + ' ' + plural(base.length, 'этапа', 'этапов', 'этапов') +
      (hidden && S.act !== 'all' ? ' <span class="pj-hid">· скрыто ' + hidden + ' ' + plural(hidden, 'старый проект', 'старых проекта', 'старых проектов') + ' (<a href="#" id="pj-show-old">показать</a>)</span>' : '');
    var so = $('pj-show-old');
    if (so) so.addEventListener('click', function (e) { e.preventDefault(); S.act = 'all'; S.page = 1; render(); });

    var pages = Math.max(1, Math.ceil(rows.length / S.size));
    S.page = Math.min(S.page, pages);
    var slice = rows.slice((S.page - 1) * S.size, S.page * S.size);
    function th(c, label) { return '<div class="pj-s' + (sc.col === c ? ' is-on' + (sc.asc ? '' : ' is-desc') : '') + '" data-sort="' + c + '" role="button" tabindex="0">' + label + '</div>'; }

    var body = '';
    if (!rows.length) {
      body = '<div class="pj-empty"><b>Нет проектов по выбранным фильтрам</b>Измените условия поиска или <a href="#" id="pj-empty-clear">сбросьте фильтры</a>.</div>';
    } else if (S.group === 'none') {
      body = slice.map(rowHtml).join('');
    } else {
      var key = function (p) { return S.group === 'status' ? p.status : (S.group === 'chief' ? p.chief : p.client) || '—'; };
      var order = [];
      slice.forEach(function (p) { if (order.indexOf(key(p)) < 0) order.push(key(p)); });
      order.sort(function (a, b) { return S.group === 'status' ? STATUSES.indexOf(a) - STATUSES.indexOf(b) : a.localeCompare(b, 'ru'); });
      body = order.map(function (g) {
        var items = slice.filter(function (p) { return key(p) === g; }), col = !!S.collapsed[g];
        return '<div class="pj-pgrp" data-g="' + esc(g) + '" role="button" tabindex="0"><span class="pj-chv">' + (col ? '▶' : '▼') + '</span>' + esc(g) + ' <span class="pj-n">' + items.length + ' ' + plural(items.length, 'этап', 'этапа', 'этапов') + '</span></div>' + (col ? '' : items.map(rowHtml).join(''));
      }).join('');
    }
    var lt = $('pj-lt');
    lt.className = 'pj-lt' + (CTX.showChief ? '' : ' pj-nochief');
    lt.innerHTML = (rows.length ? '<div class="pj-lh"><div></div>' + th('id', 'Договор · этап') + th('client', 'Заказчик · исполнитель') + (CTX.showChief ? th('chief', 'Руководитель') : '') + th('end', 'Срок проекта') + th('status', 'Статус') + th('tasks', 'Задачи') + '<div></div></div>' : '') + body;
    $('pj-foot-l').innerHTML = rows.length ? 'Строки ' + ((S.page - 1) * S.size + 1) + '–' + Math.min(S.page * S.size, rows.length) + ' из ' + rows.length +
      ' · <label>на странице <select id="pj-size">' + [25, 50, 100].map(function (n) { return '<option' + (n === S.size ? ' selected' : '') + '>' + n + '</option>'; }).join('') + '</select></label>' : '';
    var pg = '';
    if (pages > 1) {
      pg = '<button type="button" class="button is-light is-small" data-pg="' + (S.page - 1) + '"' + (S.page === 1 ? ' disabled' : '') + '>←</button>';
      for (var i = 1; i <= pages; i++) pg += '<button type="button" class="button is-small ' + (i === S.page ? 'is-primary' : 'is-light') + '" data-pg="' + i + '">' + i + '</button>';
      pg += '<button type="button" class="button is-light is-small" data-pg="' + (S.page + 1) + '"' + (S.page === pages ? ' disabled' : '') + '>→</button>';
    }
    $('pj-pager').innerHTML = pg;
    wire();
    persist();
  }

  function toggleOpen(id) { if (S.open[id]) delete S.open[id]; else S.open[id] = 1; render(); }
  function wire() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-sort]'), function (h) {
      var go = function () {
        var c = h.getAttribute('data-sort');
        if (S.sort.col === c) S.sort.asc = !S.sort.asc; else S.sort = { col: c, asc: c !== 'end' && c !== 'tasks' };
        render();
      };
      h.addEventListener('click', go);
      h.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-ex]'), function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); toggleOpen(+b.getAttribute('data-ex')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.pj-prow'), function (r) {
      r.addEventListener('click', function (e) { if (e.target.closest('a, button')) return; toggleOpen(+r.getAttribute('data-id')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-edit]'), function (b) { b.addEventListener('click', function () { openDrawer('edit', +b.getAttribute('data-edit')); }); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-addetap]'), function (b) { b.addEventListener('click', function () { openDrawer('etap', +b.getAttribute('data-addetap')); }); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-menu]'), function (b) { b.addEventListener('click', function (e) { e.stopPropagation(); openMenu(+b.getAttribute('data-menu'), b); }); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-g]'), function (g) {
      var go = function () { var k = g.getAttribute('data-g'); if (S.collapsed[k]) delete S.collapsed[k]; else S.collapsed[k] = 1; render(); };
      g.addEventListener('click', go);
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-pg]'), function (b) {
      b.addEventListener('click', function () { S.page = +b.getAttribute('data-pg'); render(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
    });
    var sz = $('pj-size');
    if (sz) sz.addEventListener('change', function () { S.size = +sz.value; S.page = 1; render(); });
    var ec = $('pj-empty-clear');
    if (ec) ec.addEventListener('click', function (e) { e.preventDefault(); resetFilters(); S.page = 1; render(); });
  }

  // ---------- меню «⋯»
  var menuEl = null;
  function closeMenu() { if (menuEl) { menuEl.parentNode.removeChild(menuEl); menuEl = null; } }
  function openMenu(id, anchor) {
    closeMenu();
    var p = DATA.filter(function (x) { return x.id === id; })[0];
    menuEl = document.createElement('div');
    menuEl.className = 'pj-menu'; menuEl.setAttribute('role', 'menu');
    menuEl.innerHTML = '<a role="menuitem" href="' + esc(p.url) + '">Открыть карточку</a>' +
      (CTX.canEdit ? '<button type="button" role="menuitem" data-a="edit">Изменить</button><button type="button" role="menuitem" data-a="etap">Добавить этап</button>' : '');
    document.body.appendChild(menuEl);
    var r = anchor.getBoundingClientRect(), w = menuEl.offsetWidth, h = menuEl.offsetHeight;
    menuEl.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.right - w)) + 'px';
    menuEl.style.top = (r.bottom + h + 10 > window.innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4) + 'px';
    menuEl.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      closeMenu();
      openDrawer(b.getAttribute('data-a'), id);
    });
  }
  document.addEventListener('click', function (e) {
    if (menuEl && !menuEl.contains(e.target)) closeMenu();
    if (S.openMs && !e.target.closest('.pj-ms') && !e.target.closest('.flatpickr-calendar')) { S.openMs = null; render(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    closeMenu(); closeDrawer();
    if (S.openMs) { S.openMs = null; render(); }
  });

  // ---------- боковая панель: создание и изменение
  var editing = null;
  function datalist(id, items) { return '<datalist id="' + id + '">' + (items || []).map(function (i) { return '<option value="' + esc(i) + '">'; }).join('') + '</datalist>'; }
  function field(name, label, val, o) {
    o = o || {};
    return '<div' + (o.full ? ' class="pj-full"' : '') + '><label for="pj-e-' + name + '">' + label + (o.req ? ' <i>*</i>' : '') + '</label>' +
      '<input id="pj-e-' + name + '" name="' + name + '" type="text" value="' + esc(val == null ? '' : val) + '"' + (o.ro ? ' readonly' : '') +
      (o.list ? ' list="' + o.list + '"' : '') + (o.date ? ' class="js-date" autocomplete="off"' : '') + (o.ph ? ' placeholder="' + o.ph + '"' : '') + ' />' +
      '<div class="pj-em" id="pj-em-' + name + '"></div></div>';
  }
  function plainNum(n) { return n == null ? '' : String(Math.round(n * 100) / 100).replace('.', ','); }

  function openDrawer(mode, id) {
    closeMenu();
    var src = id ? DATA.filter(function (x) { return x.id === id; })[0] : null;
    var p;
    if (mode === 'edit') p = Object.assign({}, src);
    else if (mode === 'etap') {
      var maxEtap = Math.max.apply(null, DATA.filter(function (x) { return x.contract === src.contract; }).map(function (x) { return parseInt(x.etap, 10) || 0; }));
      p = Object.assign({}, src, { etap: String(maxEtap + 1), status: 'Запланирован', ps: T, pe: T + 30, act: null, esum: null, tasks: 0, done: 0, period: String(new Date().getFullYear()) });
    } else {
      p = { contract: '', etap: '1', kind: '', client: '', exec: '', chief: '', status: 'Запланирован', ps: T, pe: T + 30, cs: T, ce: T + 90, act: null, period: String(new Date().getFullYear()), esum: null, csum: null };
    }
    editing = { mode: mode, id: mode === 'edit' ? id : null };
    var ro = mode === 'edit', lockId = mode === 'edit' || mode === 'etap';
    var form = $('pj-form');
    form.action = mode === 'edit' ? CTX.updateUrl : CTX.createUrl;
    $('pj-dr-t').textContent = mode === 'edit' ? 'Изменение проекта' : (mode === 'etap' ? 'Новый этап договора' : 'Создание проекта');
    $('pj-dr-s').textContent = mode === 'edit' ? 'Договор ' + p.contract + ', этап ' + p.etap : (mode === 'etap' ? 'Договор ' + p.contract + ': данные заказчика и исполнителя подставлены' : 'Заполните основные поля договора и этапа');
    var sug = CTX.suggest || {};
    var catalog = CTX.catalog || [];
    $('pj-dr-b').innerHTML = datalist('pj-dl-chief', sug.chief) + datalist('pj-dl-kind', sug.kind) + datalist('pj-dl-client', sug.client) + datalist('pj-dl-exec', sug.exec) +
      '<div class="pj-sec"><h4>Основное</h4><div class="pj-grid2">' +
      field('contract_number', 'Номер договора', p.contract, { req: !ro, ro: lockId }) + field('etap_number', 'Этап', p.etap, { req: !ro, ro: lockId }) +
      field('client_name', 'Заказчик', p.client, { list: 'pj-dl-client', full: true }) + field('executant_name', 'Исполнитель', p.exec, { list: 'pj-dl-exec' }) +
      field('project_chief', 'Руководитель проекта', p.chief, { list: 'pj-dl-chief' }) + field('contract_kind', 'Вид договора', p.kind, { list: 'pj-dl-kind' }) +
      '<div><label for="pj-e-project_status">Статус проекта</label><select id="pj-e-project_status" name="project_status"><option value="">—</option>' +
      catalog.map(function (s) { return '<option' + (s === p.status ? ' selected' : '') + '>' + esc(s) + '</option>'; }).join('') + '</select></div></div></div>' +
      '<div class="pj-sec"><h4>Сроки</h4><div class="pj-grid2">' +
      field('plan_start_date', 'План. дата начала', p.ps == null ? '' : fmtF(p.ps), { date: 1, ph: 'dd.mm.YYYY' }) + field('plan_end_date', 'План. дата окончания', p.pe == null ? '' : fmtF(p.pe), { date: 1, ph: 'dd.mm.YYYY' }) +
      field('contract_start_date', 'Дата начала договора', p.cs == null ? '' : fmtF(p.cs), { date: 1, ph: 'dd.mm.YYYY' }) + field('contract_end_date', 'Дата окончания договора', p.ce == null ? '' : fmtF(p.ce), { date: 1, ph: 'dd.mm.YYYY' }) +
      field('period', 'Период проверки', p.period) + field('act_date', 'Дата акта', p.act == null ? '' : fmtF(p.act), { date: 1, ph: 'dd.mm.YYYY' }) + '</div></div>' +
      '<div class="pj-sec"><h4>Финансы</h4><div class="pj-grid2">' + field('etap_sum', 'Сумма этапа, ₽', plainNum(p.esum)) + field('contr_sum', 'Сумма договора, ₽', plainNum(p.csum)) + '</div></div>';
    $('pj-ov').classList.add('is-show'); $('pj-dr').classList.add('is-show'); $('pj-dr').setAttribute('aria-hidden', 'false');
    if (window.reinitDatePickers) window.reinitDatePickers($('pj-dr-b')); else if (window.initDatePickers) window.initDatePickers($('pj-dr-b'));
    var first = $('pj-dr-b').querySelector('input:not([readonly])');
    if (first) first.focus();
  }
  function closeDrawer() {
    $('pj-ov').classList.remove('is-show'); $('pj-dr').classList.remove('is-show'); $('pj-dr').setAttribute('aria-hidden', 'true'); editing = null;
  }
  function val(name) { var e = document.getElementById('pj-e-' + name); return e ? e.value.trim() : ''; }
  function toNum(s) {
    var v = String(s).replace(/[\s ₽]/g, '').replace(',', '.');
    return v === '' ? null : (isFinite(+v) ? +v : NaN);
  }
  function saveDrawer() {
    if (!editing) return;
    var ok = true;
    Array.prototype.forEach.call(document.querySelectorAll('.pj-em'), function (e) { e.textContent = ''; });
    Array.prototype.forEach.call(document.querySelectorAll('.pj-dr__body input.is-err'), function (e) { e.classList.remove('is-err'); });
    function bad(name, msg) { $('pj-em-' + name).textContent = msg; $('pj-e-' + name).classList.add('is-err'); ok = false; }
    var contract = val('contract_number'), etap = val('etap_number');
    if (!contract) bad('contract_number', 'Укажите номер договора');
    if (!etap) bad('etap_number', 'Укажите номер этапа');
    if (editing.mode !== 'edit' && contract && etap && DATA.some(function (x) { return x.contract === contract && x.etap === etap; })) bad('etap_number', 'Такой этап договора уже существует');
    var d = {};
    ['plan_start_date', 'plan_end_date', 'contract_start_date', 'contract_end_date', 'act_date'].forEach(function (name) {
      var v = val(name);
      if (!v) { d[name] = null; return; }
      var n = parseRu(v);
      if (n == null) bad(name, 'Формат dd.mm.YYYY'); else d[name] = n;
    });
    if (d.plan_start_date != null && d.plan_end_date != null && d.plan_end_date < d.plan_start_date) bad('plan_end_date', 'Окончание раньше начала');
    if (d.contract_start_date != null && d.contract_end_date != null && d.contract_end_date < d.contract_start_date) bad('contract_end_date', 'Окончание раньше начала');
    ['etap_sum', 'contr_sum'].forEach(function (name) { if (Number.isNaN(toNum(val(name)))) bad(name, 'Введите число'); });
    if (!ok) return;
    // суммы уходят на сервер числом без пробелов
    ['etap_sum', 'contr_sum'].forEach(function (name) {
      var e = document.getElementById('pj-e-' + name), n = toNum(e.value);
      e.value = n == null ? '' : String(n);
    });
    $('pj-form').submit();
  }
  $('pj-dr-save').addEventListener('click', saveDrawer);
  $('pj-dr-cancel').addEventListener('click', closeDrawer);
  $('pj-dr-x').addEventListener('click', closeDrawer);
  $('pj-ov').addEventListener('click', closeDrawer);
  $('pj-form').addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); saveDrawer(); } });

  // ---------- подключение
  var createBtn = $('pj-create');
  if (createBtn) createBtn.addEventListener('click', function () { openDrawer('new'); });
  $('pj-q').addEventListener('input', function (e) {
    S.q = e.target.value; S.page = 1;
    var pos = e.target.selectionStart;
    render();
    var q = $('pj-q'); q.focus(); q.setSelectionRange(pos, pos);
  });
  $('pj-group').addEventListener('change', function (e) { S.group = e.target.value; S.collapsed = {}; render(); });
  render();
})();
