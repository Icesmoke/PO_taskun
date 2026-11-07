/**
 * Карточка проекта: задачи этапа в виде списка и канбан-доски.
 *
 * Данные приходят из <script type="application/json" id="tk-data"> (см. project_card.html).
 * Перенос карточки между колонками сразу сохраняет статус (POST JSON → task_status);
 * правки в боковой панели, новые и удалённые задачи копятся в браузере и сохраняются
 * кнопкой «Сохранить изменения» обычной формой save_tasks (весь этап целиком, как и раньше).
 */
(function () {
  'use strict';

  var rootEl = document.getElementById('tk-root');
  var dataEl = document.getElementById('tk-data');
  if (!rootEl || !dataEl) return;

  var CTX = JSON.parse(dataEl.textContent);
  var MODE = CTX.mode; // all | partial | view
  var ME = CTX.me || '';
  var DAY = 86400000;
  var HOLIDAYS = {};
  (CTX.holidays || []).forEach(function (h) { HOLIDAYS[h] = 1; });

  var STATUS_META = {
    'План': { c: 'var(--tk-plan)', d: 'Запланирована к выполнению' },
    'В работе': { c: 'var(--tk-work)', d: 'В процессе исполнения' },
    'Выполнено': { c: 'var(--tk-done)', d: 'Задача выполнена' },
    'Отмена': { c: 'var(--tk-cancel)', d: 'Задача отменена' }
  };
  var NO_STATUS = { c: 'var(--tk-none)', d: 'Статус не выбран' };
  function meta(name) { return STATUS_META[name] || NO_STATUS; }

  var STATUSES = CTX.statuses || [];
  var uidSeq = 0;
  var tasks = (CTX.tasks || []).map(function (t) {
    return {
      uid: ++uidSeq, id: t.id, name: t.name, desc: t.desc, worker: t.worker, status: t.status,
      start: t.start, end: t.end, comment: t.comment, file: t.file,
      // значения, известные серверу на момент загрузки: по ним проверяется, что строка не менялась
      orig: t.id != null ? { name: t.name, worker: t.worker, start: t.start, end: t.end } : null
    };
  });

  var S = { view: 'list', q: '', workers: {}, over: false, mine: false, sort: { col: null, asc: true }, editUid: null, undo: null };
  var dirty = !!CTX.draft;
  var skipUnload = false;
  try { var saved = localStorage.getItem('tk-view'); if (saved === 'board' || saved === 'list') S.view = saved; } catch (e) { /* без localStorage */ }

  function $(id) { return document.getElementById(id); }
  var el = {
    board: $('tk-board'), list: $('tk-list'), main: $('tk-main'), none: $('tk-none'),
    pbar: $('tk-pbar'), ptxt: $('tk-ptxt'), chips: $('tk-chips'), q: $('tk-q'),
    over: $('tk-over'), mine: $('tk-mine'), mineWrap: $('tk-mine-wrap'), hint: $('tk-hint'),
    unsaved: $('tk-unsaved'), unsavedText: $('tk-unsaved-text'), save: $('tk-save'), discard: $('tk-discard'),
    add: $('tk-add'), xlsxBtn: $('tk-xlsx-btn'), xlsxFile: $('tk-xlsx-file'), xlsxForm: $('tk-xlsx'),
    vBoard: $('tk-v-board'), vList: $('tk-v-list'),
    ov: $('tk-ov'), dr: $('tk-dr'), drTitle: $('tk-dr-title'), drBody: $('tk-dr-body'),
    drSave: $('tk-dr-save'), drCancel: $('tk-dr-cancel'), drX: $('tk-dr-x'), drDel: $('tk-dr-del'),
    toast: $('tk-toast'), toastT: $('tk-toast-t'), toastU: $('tk-toast-u'), form: $('tk-form')
  };

  // ---------- утилиты
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pad(n) { return n < 10 ? '0' + n : String(n); }
  function parseIso(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function toIso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function fmtShort(s) { if (!s) return '—'; var d = parseIso(s); return pad(d.getDate()) + '.' + pad(d.getMonth() + 1); }
  function fmtFull(s) { if (!s) return '—'; var p = s.split('-'); return p[2] + '.' + p[1] + '.' + p[0]; }
  function toRu(s) { return s ? fmtFull(s) : ''; }
  function fromRu(s) {
    var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec((s || '').trim());
    if (!m) return null;
    var d = new Date(+m[3], +m[2] - 1, +m[1]);
    return (d.getMonth() === +m[2] - 1) ? m[3] + '-' + m[2] + '-' + m[1] : null;
  }
  var today = new Date(); today.setHours(0, 0, 0, 0);

  function initials(n) {
    return n.replace(/\./g, ' ').trim().split(/\s+/).map(function (x) { return x.charAt(0); }).slice(0, 2).join('') || '?';
  }
  function hue(n) { var h = 0; for (var i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) % 360; return h; }
  function avatar(n, cls) {
    if (!n) return '<span class="tk-av ' + (cls || '') + ' is-empty" title="Исполнитель не указан">?</span>';
    return '<span class="tk-av ' + (cls || '') + '" style="background:hsl(' + hue(n) + ' 52% 42%)" title="' + esc(n) + '">' + esc(initials(n)) + '</span>';
  }
  function plural(n, a, b, c) {
    var m100 = n % 100, m10 = n % 10;
    if (m100 > 10 && m100 < 20) return c;
    return m10 === 1 ? a : (m10 >= 2 && m10 <= 4 ? b : c);
  }

  // Рабочие дни строго после today и до end включительно (пн–пт без праздников РФ) — как remaining_workdays в отчётах.
  function workdaysTo(end) {
    var n = 0, d = new Date(today.getTime() + DAY);
    while (d <= end) {
      var w = d.getDay();
      if (w !== 0 && w !== 6 && !HOLIDAYS[toIso(d)]) n++;
      d = new Date(d.getTime() + DAY);
    }
    return n;
  }
  function isOpen(t) { return t.status === 'План' || t.status === 'В работе'; }
  function deadline(t) {
    if (!isOpen(t)) return { cls: 'gray', txt: t.status === 'Выполнено' ? 'готово' : (t.status === 'Отмена' ? 'отмена' : ''), over: false };
    if (!t.end) return { cls: 'gray', txt: 'без срока', over: false };
    var end = parseIso(t.end);
    if (end < today) {
      var late = Math.round((today - end) / DAY);
      return { cls: 'red', txt: 'просрочено ' + late + ' дн.', over: true };
    }
    var n = workdaysTo(end);
    return { cls: n > 3 ? 'green' : (n > 1 ? 'yellow' : 'red'), txt: n === 0 ? 'срок сегодня' : n + ' раб. дн.', over: false };
  }

  var can = {
    move: function (t) { return MODE === 'all' || (MODE === 'partial' && !!ME && t.worker === ME); },
    editAll: function () { return MODE === 'all'; },
    editPart: function (t) { return MODE === 'partial' && !!ME && t.worker === ME; },
    add: function () { return MODE === 'all'; }
  };

  function byUid(uid) { for (var i = 0; i < tasks.length; i++) if (tasks[i].uid === uid) return tasks[i]; return null; }
  function workersInTasks() {
    var seen = {}, out = [];
    tasks.forEach(function (t) { if (t.worker && !seen[t.worker]) { seen[t.worker] = 1; out.push(t.worker); } });
    return out.sort();
  }

  function visibleTasks() {
    var q = S.q.trim().toLowerCase();
    var anyWorker = Object.keys(S.workers).length > 0;
    return tasks.filter(function (t) {
      if (q && (t.name + ' ' + t.desc).toLowerCase().indexOf(q) < 0) return false;
      if (anyWorker && !S.workers[t.worker]) return false;
      if (S.over && !deadline(t).over) return false;
      if (S.mine && t.worker !== ME) return false;
      return true;
    });
  }

  // ---------- верхняя часть: прогресс, фильтры, подсказки
  function renderTop() {
    var total = tasks.length;
    function cnt(k) { return tasks.filter(function (t) { return t.status === k; }).length; }
    var active = tasks.filter(function (t) { return t.status !== 'Отмена'; }).length;
    var done = cnt('Выполнено');
    var noStatus = tasks.filter(function (t) { return STATUSES.indexOf(t.status) < 0; }).length;
    var segs = STATUSES.map(function (s) {
      return '<i style="width:' + (total ? cnt(s) / total * 100 : 0) + '%;background:' + meta(s).c + '" title="' + esc(s) + ': ' + cnt(s) + '"></i>';
    }).join('');
    if (noStatus) segs += '<i style="width:' + noStatus / total * 100 + '%;background:' + NO_STATUS.c + '" title="Без статуса: ' + noStatus + '"></i>';
    el.pbar.innerHTML = segs;
    el.ptxt.innerHTML = '<b>' + done + ' из ' + active + '</b> выполнено (' + (active ? Math.round(done / active * 100) : 0) + '%) · ' +
      STATUSES.map(function (s) { return '<span class="tk-dot" style="background:' + meta(s).c + '"></span>' + esc(s) + ' ' + cnt(s); }).join('&nbsp;&nbsp;');

    var ws = workersInTasks();
    var any = Object.keys(S.workers).length > 0;
    el.chips.innerHTML = '<button type="button" class="tk-chip is-all' + (any ? '' : ' is-on') + '" data-w="">Все</button>' +
      ws.map(function (w) {
        return '<button type="button" class="tk-chip' + (S.workers[w] ? ' is-on' : '') + '" data-w="' + esc(w) + '">' + avatar(w, 'is-sm') + esc(w) + '</button>';
      }).join('');
    Array.prototype.forEach.call(el.chips.querySelectorAll('.tk-chip'), function (b) {
      b.onclick = function () {
        var w = b.getAttribute('data-w');
        if (!w) S.workers = {}; else if (S.workers[w]) delete S.workers[w]; else S.workers[w] = 1;
        render();
      };
    });

    el.mineWrap.hidden = MODE !== 'partial';
    if (el.add) el.add.hidden = !can.add();
    if (el.xlsxBtn) el.xlsxBtn.hidden = !can.add();

    el.vBoard.classList.toggle('is-on', S.view === 'board');
    el.vList.classList.toggle('is-on', S.view === 'list');
    el.vBoard.setAttribute('aria-selected', S.view === 'board' ? 'true' : 'false');
    el.vList.setAttribute('aria-selected', S.view === 'list' ? 'true' : 'false');

    var hint;
    if (S.view === 'board') {
      hint = MODE === 'all' ? 'Перетащите карточку в другую колонку — статус сохранится сразу. ' :
        (MODE === 'partial' ? 'Вы можете переносить только свои задачи (карточки других исполнителей помечены замком). ' : 'Режим просмотра: перенос недоступен. ');
      hint += 'Без мыши: кнопка «⋯» на карточке открывает меню «Перенести в…».';
    } else {
      hint = 'Клик по названию открывает карточку задачи, клик по заголовку столбца — сортировка. ' +
        (MODE === 'view' ? '' : 'Статус можно сменить прямо в строке.');
    }
    el.hint.textContent = hint;

    el.unsaved.hidden = !dirty;
    if (dirty) {
      el.unsavedText.textContent = CTX.draft
        ? 'Задачи загружены из XLSX и ещё не сохранены. Проверьте их и нажмите «Сохранить изменения».'
        : 'Есть несохранённые изменения (правки, новые или удалённые задачи).';
      el.discard.hidden = !!CTX.draft;
    }
  }

  // ---------- доска
  function cardHtml(t) {
    var m = meta(t.status), dl = deadline(t), mv = can.move(t);
    var elapsed = 0;
    if (t.start && t.end) {
      var a = parseIso(t.start), b = parseIso(t.end);
      elapsed = Math.max(0, Math.min(1, (today - a) / Math.max(DAY, b - a)));
    }
    var period = (t.start || t.end) ? fmtShort(t.start) + ' – ' + fmtShort(t.end) : 'даты не заданы';
    var extras = '';
    if (t.comment) extras += '<span title="' + esc(t.comment) + '"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 3h12v8H7l-3 3v-3H2z"/></svg>Комментарий</span>';
    if (t.file) extras += '<span title="' + esc(t.file) + '"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M10 4 5.5 8.5a1.6 1.6 0 0 0 2.3 2.3L12 6.6a3 3 0 0 0-4.2-4.2L3.4 6.8a4.4 4.4 0 0 0 6.2 6.2"/></svg>Файл</span>';
    return '<article class="tk-card' + (t.status === 'Выполнено' ? ' is-done' : '') + (t.status === 'Отмена' ? ' is-cancel' : '') + (mv ? '' : ' is-locked') +
      '" style="--c:' + m.c + '" data-uid="' + t.uid + '" data-drag="' + (mv ? '1' : '0') + '" tabindex="0">' +
      (mv ? '<button type="button" class="tk-card__dots" data-menu="' + t.uid + '" aria-label="Действия с задачей" title="Перенести / открыть">⋯</button>'
          : (MODE === 'view' ? '' : '<svg class="tk-card__lock" viewBox="0 0 16 16" fill="currentColor" aria-label="Нет прав переносить эту задачу"><title>Нет прав переносить эту задачу</title><path d="M4 7V5a4 4 0 1 1 8 0v2h1v7H3V7h1Zm1.5 0h5V5a2.5 2.5 0 0 0-5 0v2Z"/></svg>')) +
      '<div class="tk-card__t">' + esc(t.name || 'Без названия') + '</div>' +
      (t.desc ? '<div class="tk-card__d">' + esc(t.desc) + '</div>' : '') +
      '<div class="tk-card__m"><div class="tk-card__w">' + avatar(t.worker) + '<span class="tk-card__n">' + esc(t.worker || 'Не назначен') + '</span></div>' +
      '<span class="tk-card__dt tk-tl--' + dl.cls + '" title="' + esc(fmtFull(t.start) + ' — ' + fmtFull(t.end)) + '">' + period + (dl.txt ? ' · ' + esc(dl.txt) : '') + '</span></div>' +
      (t.status === 'В работе' && t.start && t.end ? '<div class="tk-card__tm" title="Прошло ' + Math.round(elapsed * 100) + '% срока"><i style="width:' + elapsed * 100 + '%"></i></div>' : '') +
      (extras ? '<div class="tk-card__ex">' + extras + '</div>' : '') + '</article>';
  }

  function renderBoard() {
    var vis = visibleTasks();
    var cols = STATUSES.map(function (s) { return { k: s, label: s, m: meta(s) }; });
    if (tasks.some(function (t) { return STATUSES.indexOf(t.status) < 0; })) cols.push({ k: '', label: 'Без статуса', m: NO_STATUS, readonly: true });
    el.board.innerHTML = cols.map(function (c) {
      var items = vis.filter(function (t) { return c.k ? t.status === c.k : STATUSES.indexOf(t.status) < 0; });
      var total = tasks.filter(function (t) { return c.k ? t.status === c.k : STATUSES.indexOf(t.status) < 0; }).length;
      return '<section class="tk-col" style="--c:' + c.m.c + '" data-status="' + esc(c.k) + '"' + (c.readonly ? ' data-readonly="1"' : '') + '>' +
        '<div class="tk-col__h"><div class="tk-col__r1"><span class="tk-col__nm">' + esc(c.label) + '</span><span class="tk-col__cnt">' + items.length + (items.length !== total ? ' / ' + total : '') + '</span></div>' +
        '<div class="tk-col__ds">' + esc(c.m.d) + '</div></div>' +
        '<div class="tk-col__b">' + (items.length ? items.map(cardHtml).join('') : '<div class="tk-empty">' + (total ? 'Нет задач по фильтру' : (MODE === 'view' ? 'Нет задач' : 'Перетащите задачу сюда')) + '</div>') + '</div></section>';
    }).join('');

    Array.prototype.forEach.call(el.board.querySelectorAll('.tk-card'), function (card) {
      var uid = +card.getAttribute('data-uid');
      card.addEventListener('click', function (e) { if (e.target.closest('.tk-card__dots')) return; openDrawer(uid); });
      card.addEventListener('keydown', function (e) {
        if (e.target !== card) return;
        if (e.key === 'Enter') openDrawer(uid);
        if (e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) { e.preventDefault(); openMenu(uid, card); }
      });
    });
    Array.prototype.forEach.call(el.board.querySelectorAll('.tk-card__dots'), function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); openMenu(+b.getAttribute('data-menu'), b); });
    });
    initDnd();
  }

  function clearOver() {
    Array.prototype.forEach.call(el.board.querySelectorAll('.tk-col'), function (c) { c.classList.remove('is-over'); });
  }

  function initDnd() {
    var bodies = el.board.querySelectorAll('.tk-col__b');
    if (window.Sortable) {
      // SortableJS: перетаскивание мышью и касанием (на сенсорных экранах — с небольшим удержанием)
      Array.prototype.forEach.call(bodies, function (body) {
        if (body.parentNode.getAttribute('data-readonly')) return;
        window.Sortable.create(body, {
          group: 'tk', draggable: '.tk-card[data-drag="1"]', filter: '.tk-card__dots', preventOnFilter: false,
          animation: 120, ghostClass: 'is-ghost', delay: 150, delayOnTouchOnly: true, emptyInsertThreshold: 24,
          onMove: function (evt) { clearOver(); var c = evt.to.closest('.tk-col'); if (c && !c.getAttribute('data-readonly')) c.classList.add('is-over'); },
          onEnd: function (evt) {
            clearOver();
            var to = evt.to.closest('.tk-col');
            var uid = +evt.item.getAttribute('data-uid');
            if (to && evt.to !== evt.from && !to.getAttribute('data-readonly')) moveTask(uid, to.getAttribute('data-status'));
            else renderBoard(); // вернуть исходный порядок
          }
        });
      });
      return;
    }
    // запасной вариант без библиотеки: встроенный drag-and-drop браузера (только мышь)
    Array.prototype.forEach.call(el.board.querySelectorAll('.tk-card[data-drag="1"]'), function (card) {
      card.draggable = true;
      card.addEventListener('dragstart', function (e) { e.dataTransfer.setData('text/plain', card.getAttribute('data-uid')); e.dataTransfer.effectAllowed = 'move'; card.classList.add('is-ghost'); });
      card.addEventListener('dragend', function () { card.classList.remove('is-ghost'); clearOver(); });
    });
    Array.prototype.forEach.call(el.board.querySelectorAll('.tk-col'), function (col) {
      if (col.getAttribute('data-readonly')) return;
      col.addEventListener('dragover', function (e) { e.preventDefault(); col.classList.add('is-over'); });
      col.addEventListener('dragleave', function (e) { if (!col.contains(e.relatedTarget)) col.classList.remove('is-over'); });
      col.addEventListener('drop', function (e) { e.preventDefault(); clearOver(); moveTask(+e.dataTransfer.getData('text/plain'), col.getAttribute('data-status')); });
    });
  }

  // ---------- список
  function renderList() {
    var rows = visibleTasks(), sc = S.sort;
    if (sc.col) {
      rows = rows.slice().sort(function (a, b) {
        function get(t) {
          if (sc.col === 'worker') return t.worker || '';
          if (sc.col === 'start') return t.start || '';
          if (sc.col === 'end') return t.end || '';
          if (sc.col === 'status') return STATUSES.indexOf(t.status) < 0 ? 99 : STATUSES.indexOf(t.status);
          return (t.name || '').toLowerCase();
        }
        var x = get(a), y = get(b);
        return (x < y ? -1 : (x > y ? 1 : 0)) * (sc.asc ? 1 : -1);
      });
    }
    var starts = tasks.map(function (t) { return t.start; }).filter(Boolean).sort();
    var ends = tasks.map(function (t) { return t.end; }).filter(Boolean).sort();
    var A = starts.length ? parseIso(starts[0]) : today, B = ends.length ? parseIso(ends[ends.length - 1]) : today;
    if (today < A) A = today;
    if (today > B) B = today;
    var span = Math.max(DAY, B - A);
    function pct(d) { return Math.max(0, Math.min(100, (parseIso(d) - A) / span * 100)); }
    function th(c, label) { return '<th data-s="' + c + '" aria-sort="' + (sc.col === c ? (sc.asc ? 'ascending' : 'descending') : 'none') + '">' + label + '<span class="tk-ar">' + (sc.col === c ? (sc.asc ? '▲' : '▼') : '') + '</span></th>'; }

    if (!rows.length) { el.list.innerHTML = '<div class="tk-nodata">Нет задач по выбранным фильтрам.</div>'; return; }
    el.list.innerHTML = '<table class="tk-table"><thead><tr>' + th('name', 'Задача') + th('worker', 'Исполнитель') + th('start', 'Сроки') + th('status', 'Статус') + '<th class="is-static"></th></tr></thead><tbody>' +
      rows.map(function (t) {
        var m = meta(t.status), dl = deadline(t), mv = can.move(t);
        var bar = '';
        if (t.start && t.end) {
          var l = pct(t.start), r = pct(t.end);
          bar = '<div class="tk-tlbar" style="--c:' + m.c + '"><i style="left:' + l + '%;width:' + Math.max(1.5, r - l) + '%"></i><u style="left:' + pct(toIso(today)) + '%"></u></div>';
        }
        var label = t.status ? esc(t.status) : 'Без статуса';
        return '<tr data-uid="' + t.uid + '"><td><div class="tk-lt__t" data-open="' + t.uid + '" tabindex="0" role="button">' + esc(t.name || 'Без названия') + '</div>' +
          (t.desc ? '<div class="tk-lt__d" title="' + esc(t.desc) + '">' + esc(t.desc) + '</div>' : '') + '</td>' +
          '<td><div class="tk-lt__w">' + avatar(t.worker) + esc(t.worker || 'Не назначен') + '</div></td>' +
          '<td>' + bar + '<div class="tk-lt__dt">' + ((t.start || t.end) ? esc(fmtFull(t.start) + ' — ' + fmtFull(t.end)) : 'даты не заданы') +
          (dl.txt ? ' · <span class="tk-pill tk-tl--' + dl.cls + '">' + esc(dl.txt) + '</span>' : '') + '</div></td>' +
          '<td><button type="button" class="tk-st" style="--c:' + m.c + '" data-menu="' + t.uid + '"' + (mv ? '' : ' disabled') + '><i></i>' + label + (mv ? ' ▾' : '') + '</button></td>' +
          '<td class="tk-lt__ic">' + (t.comment ? '<span title="' + esc(t.comment) + '">💬</span> ' : '') + (t.file ? '<span title="' + esc(t.file) + '">📎</span>' : '') + '</td></tr>';
      }).join('') + '</tbody></table>';

    Array.prototype.forEach.call(el.list.querySelectorAll('th[data-s]'), function (h) {
      h.onclick = function () { var c = h.getAttribute('data-s'); if (sc.col === c) sc.asc = !sc.asc; else { sc.col = c; sc.asc = true; } renderList(); };
    });
    Array.prototype.forEach.call(el.list.querySelectorAll('[data-open]'), function (e) {
      var open = function () { openDrawer(+e.getAttribute('data-open')); };
      e.onclick = open;
      e.onkeydown = function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); open(); } };
    });
    Array.prototype.forEach.call(el.list.querySelectorAll('button.tk-st:not([disabled])'), function (b) {
      b.onclick = function (e) { e.stopPropagation(); openMenu(+b.getAttribute('data-menu'), b); };
    });
  }

  function render() {
    var empty = tasks.length === 0;
    el.none.hidden = !empty;
    el.main.hidden = empty;
    renderTop();
    if (empty) return;
    el.board.hidden = S.view !== 'board';
    el.list.hidden = S.view !== 'list';
    if (S.view === 'board') renderBoard(); else renderList();
  }

  // ---------- перенос статуса
  function postStatus(t, status) {
    return fetch(CTX.statusUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ task_id: t.id, status: status, expect: t.orig })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok && j.ok === true, error: j.error || 'Не удалось сохранить статус.' }; });
    }, function () { return { ok: false, error: 'Нет связи с сервером. Статус не сохранён.' }; });
  }

  function shortName(n) { n = n || 'Без названия'; return n.length > 40 ? n.slice(0, 40) + '…' : n; }

  function moveTask(uid, status, silent) {
    var t = byUid(uid);
    if (!t || t.status === status) { render(); return; }
    if (!can.move(t)) { toast('Нет прав переносить эту задачу'); render(); return; }
    var prev = t.status;
    t.status = status;
    render();
    function undo() { moveTask(uid, prev, true); }
    if (t.id == null) {
      // задача ещё не в БД (новая или из XLSX): статус уйдёт вместе с общим сохранением
      dirty = true; renderTop();
      if (!silent) toast('«' + shortName(t.name) + '» → ' + status + ' (не забудьте сохранить)', undo);
      return;
    }
    postStatus(t, status).then(function (res) {
      if (res.ok) { if (!silent) toast('«' + shortName(t.name) + '» → ' + status, undo); return; }
      t.status = prev; render(); toast(res.error);
    });
  }

  var toastTimer = null;
  function toast(text, undo) {
    el.toastT.textContent = text;
    el.toastU.hidden = !undo;
    S.undo = undo || null;
    el.toast.classList.add('is-show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.classList.remove('is-show'); }, 6000);
  }
  el.toastU.onclick = function () { var u = S.undo; S.undo = null; el.toast.classList.remove('is-show'); if (u) u(); };

  // ---------- меню «Перенести в…»
  var menuEl = null;
  function closeMenu() { if (menuEl) { menuEl.parentNode.removeChild(menuEl); menuEl = null; } }
  function openMenu(uid, anchor) {
    closeMenu();
    var t = byUid(uid); if (!t) return;
    var mv = can.move(t);
    menuEl = document.createElement('div');
    menuEl.className = 'tk-menu';
    menuEl.setAttribute('role', 'menu');
    menuEl.innerHTML = '<h6>Перенести в</h6>' + STATUSES.map(function (s) {
      return '<button type="button" role="menuitem" data-to="' + esc(s) + '" style="--c:' + meta(s).c + '"' + ((!mv || s === t.status) ? ' disabled' : '') + '><i></i>' + esc(s) + (s === t.status ? ' (текущий)' : '') + '</button>';
    }).join('') + '<hr><button type="button" role="menuitem" data-open="1">Открыть карточку</button>';
    document.body.appendChild(menuEl);
    var r = anchor.getBoundingClientRect(), w = menuEl.offsetWidth, h = menuEl.offsetHeight;
    menuEl.style.left = Math.min(window.innerWidth - w - 8, Math.max(8, r.right - w)) + 'px';
    menuEl.style.top = (r.bottom + h + 12 > window.innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4) + 'px';
    menuEl.onclick = function (e) {
      var b = e.target.closest('button');
      if (!b || b.disabled) return;
      var to = b.getAttribute('data-to');
      closeMenu();
      if (to) moveTask(uid, to); else openDrawer(uid);
    };
    var first = menuEl.querySelector('button:not([disabled])');
    if (first) first.focus();
  }
  document.addEventListener('click', function (e) {
    if (menuEl && !menuEl.contains(e.target) && !e.target.closest('.tk-card__dots, .tk-st')) closeMenu();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeMenu(); closeDrawer(); }
  });

  // ---------- боковая панель: просмотр и правка задачи
  function field(label, html, full) { return '<div' + (full ? ' class="tk-full"' : '') + '><label>' + label + '</label>' + html + '</div>'; }
  function openDrawer(uid, isNew) {
    closeMenu();
    var t = isNew ? { uid: null, id: null, name: '', desc: '', worker: '', status: STATUSES[0] || '', start: '', end: '', comment: '', file: '' } : byUid(uid);
    if (!t) return;
    S.editUid = isNew ? 'new' : uid;
    var full = can.editAll(), part = !full && can.editPart(t), ro = !full && !part;
    function dis(f) { return (ro || (!full && ['status', 'start', 'end', 'comment', 'file'].indexOf(f) < 0)) ? ' disabled' : ''; }
    var workers = (CTX.workers || []).slice();
    if (t.worker && workers.indexOf(t.worker) < 0) workers.push(t.worker);
    var statuses = STATUSES.slice();
    if (t.status && statuses.indexOf(t.status) < 0) statuses.push(t.status);

    el.drTitle.textContent = isNew ? 'Новая задача' : 'Задача';
    el.drBody.innerHTML =
      (ro ? '<div class="tk-note">' + (MODE === 'view' ? 'Режим просмотра: редактирование недоступно.' : 'Эта задача назначена другому исполнителю — изменить её нельзя.') + '</div>' :
        (part ? '<div class="tk-note">Вы можете менять статус, даты, комментарий и рабочий файл своих задач.</div>' : '')) +
      field('Задача', '<input id="tk-e-name" type="text" value="' + esc(t.name) + '"' + dis('name') + ' />', true) +
      field('Описание', '<textarea id="tk-e-desc"' + dis('desc') + '>' + esc(t.desc) + '</textarea>', true) +
      field('Исполнитель', '<select id="tk-e-worker"' + dis('worker') + '><option value="">(не выбран)</option>' + workers.map(function (w) { return '<option' + (w === t.worker ? ' selected' : '') + '>' + esc(w) + '</option>'; }).join('') + '</select>') +
      field('Статус', '<select id="tk-e-status"' + dis('status') + '><option value="">(не выбран)</option>' + statuses.map(function (s) { return '<option' + (s === t.status ? ' selected' : '') + '>' + esc(s) + '</option>'; }).join('') + '</select>') +
      field('Дата начала', '<input id="tk-e-start" type="text" class="js-date" value="' + esc(toRu(t.start)) + '" placeholder="dd.mm.YYYY"' + dis('start') + ' />') +
      field('Дата окончания', '<input id="tk-e-end" type="text" class="js-date" value="' + esc(toRu(t.end)) + '" placeholder="dd.mm.YYYY"' + dis('end') + ' />') +
      field('Комментарий', '<input id="tk-e-comment" type="text" value="' + esc(t.comment) + '"' + dis('comment') + ' />', true) +
      field('Рабочий файл', '<input id="tk-e-file" type="text" value="' + esc(t.file) + '"' + dis('file') + ' />', true);
    el.drSave.hidden = ro;
    el.drDel.hidden = !(full && !isNew);
    el.ov.classList.add('is-show');
    el.dr.classList.add('is-show');
    el.dr.setAttribute('aria-hidden', 'false');
    if (window.initDatePickers) window.initDatePickers(el.drBody);
    var firstInput = el.drBody.querySelector('input:not([disabled]), select:not([disabled])');
    if (firstInput) firstInput.focus();
  }
  function closeDrawer() {
    el.ov.classList.remove('is-show');
    el.dr.classList.remove('is-show');
    el.dr.setAttribute('aria-hidden', 'true');
    S.editUid = null;
  }
  function val(id) { var n = $(id); return n ? n.value.trim() : ''; }
  function saveDrawer() {
    var isNew = S.editUid === 'new';
    var t = isNew ? { uid: ++uidSeq, id: null, orig: null } : byUid(S.editUid);
    if (!t) return;
    var full = can.editAll(), part = !full && can.editPart(t);
    if (!full && !part) return;
    var start = val('tk-e-start'), end = val('tk-e-end');
    var startIso = start ? fromRu(start) : '', endIso = end ? fromRu(end) : '';
    if ((start && !startIso) || (end && !endIso)) { toast('Неверный формат даты (ожидается dd.mm.YYYY).'); return; }
    if (startIso && endIso && endIso < startIso) { toast('Дата окончания раньше даты начала.'); return; }
    if (full && !val('tk-e-name')) { toast('Укажите название задачи.'); return; }
    var next = { status: $('tk-e-status').value, start: startIso, end: endIso, comment: val('tk-e-comment'), file: val('tk-e-file') };
    if (full) { next.name = val('tk-e-name'); next.desc = val('tk-e-desc'); next.worker = $('tk-e-worker').value; }
    var changed = isNew;
    Object.keys(next).forEach(function (k) { if (t[k] !== next[k]) changed = true; });
    Object.keys(next).forEach(function (k) { t[k] = next[k]; });
    if (isNew) { t.name = t.name || ''; tasks.push(t); }
    if (changed) dirty = true;
    closeDrawer();
    render();
    if (changed) toast('Изменения применены в таблице. Нажмите «Сохранить изменения», чтобы записать их в БД.');
  }
  el.drSave.onclick = saveDrawer;
  el.drDel.onclick = function () {
    var t = byUid(S.editUid);
    if (!t || !window.confirm('Удалить задачу «' + (t.name || 'Без названия') + '»? Изменение вступит в силу после сохранения.')) return;
    tasks = tasks.filter(function (x) { return x.uid !== t.uid; });
    dirty = true;
    closeDrawer();
    render();
  };
  el.ov.onclick = closeDrawer;
  el.drX.onclick = closeDrawer;
  el.drCancel.onclick = closeDrawer;

  // ---------- общее сохранение этапа (прежний обработчик save_tasks)
  function addHidden(form, name, value) {
    var i = document.createElement('input');
    i.type = 'hidden'; i.name = name; i.value = value == null ? '' : value;
    form.appendChild(i);
  }
  function submitSave() {
    var form = el.form;
    form.innerHTML = '';
    addHidden(form, 'tasks_count', tasks.length);
    tasks.forEach(function (t, i) {
      addHidden(form, 'task_name_' + i, t.name);
      addHidden(form, 'task_adenda_' + i, t.desc);
      addHidden(form, 'worker_name_' + i, t.worker);
      addHidden(form, 'task_start_date_' + i, toRu(t.start));
      addHidden(form, 'task_end_date_' + i, toRu(t.end));
      addHidden(form, 'task_comment_' + i, t.comment);
      addHidden(form, 'working_file_' + i, t.file);
      addHidden(form, 'task_status_' + i, t.status);
    });
    skipUnload = true;
    form.submit();
  }
  el.save.onclick = submitSave;
  el.discard.onclick = function () { skipUnload = true; window.location.reload(); };
  window.addEventListener('beforeunload', function (e) {
    if (dirty && !skipUnload) { e.preventDefault(); e.returnValue = ''; }
  });

  // ---------- загрузка XLSX
  if (el.xlsxBtn) {
    el.xlsxBtn.onclick = function () {
      if (dirty && !CTX.draft && !window.confirm('Есть несохранённые изменения. Загрузка файла заменит их. Продолжить?')) return;
      el.xlsxFile.click();
    };
    el.xlsxFile.onchange = function () { if (el.xlsxFile.files.length) { skipUnload = true; el.xlsxForm.submit(); } };
  }

  // ---------- подключение
  if (el.add) el.add.onclick = function () { openDrawer(null, true); };
  el.vBoard.onclick = function () { S.view = 'board'; try { localStorage.setItem('tk-view', 'board'); } catch (e) { /* ok */ } render(); };
  el.vList.onclick = function () { S.view = 'list'; try { localStorage.setItem('tk-view', 'list'); } catch (e) { /* ok */ } render(); };
  el.q.oninput = function () { S.q = el.q.value; render(); };
  el.over.onchange = function () { S.over = el.over.checked; render(); };
  el.mine.onchange = function () { S.mine = el.mine.checked; render(); };
  render();
})();
