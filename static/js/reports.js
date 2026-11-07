/**
 * Отчёты: быстрые периоды, поиск по сотруднику, сортировка и раскрытие строк таблиц,
 * сворачивание дерева «Выполнение задач», фильтр по светофору, подсветка договоров на диаграмме Ганта.
 */
(function () {
  'use strict';

  function pad(n) { return n < 10 ? '0' + n : String(n); }
  function fmt(d) { return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear(); }

  // ---------- быстрые периоды (на сервере границы пересчитываются так же, здесь — для отображения)
  function presetRange(key) {
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var y = today.getFullYear(), m = today.getMonth();
    if (key === '7' || key === '14' || key === '31') {
      var s = new Date(today); s.setDate(today.getDate() - (parseInt(key, 10) - 1));
      return [s, today];
    }
    if (key === 'month') return [new Date(y, m, 1), new Date(y, m + 1, 0)];
    if (key === 'quarter') { var q = Math.floor(m / 3) * 3; return [new Date(y, q, 1), new Date(y, q + 3, 0)]; }
    if (key === 'year') return [new Date(y, 0, 1), new Date(y, 11, 31)];
    return null;
  }

  var form = document.getElementById('rp-form');
  if (form) {
    var periodEl = document.getElementById('rp-period');
    var ds = document.getElementById('rp-ds'), de = document.getElementById('rp-de');
    Array.prototype.forEach.call(document.querySelectorAll('#rp-presets button'), function (btn) {
      btn.addEventListener('click', function () {
        var range = presetRange(btn.getAttribute('data-preset'));
        if (!range) return;
        periodEl.value = btn.getAttribute('data-preset');
        ds.value = fmt(range[0]); de.value = fmt(range[1]);
        if (window.setDateInput) { window.setDateInput(ds, ds.value); window.setDateInput(de, de.value); }
        form.submit();
      });
    });
    [ds, de].forEach(function (el) {
      if (!el) return;
      el.addEventListener('change', function () {
        periodEl.value = 'custom';
        Array.prototype.forEach.call(document.querySelectorAll('#rp-presets button'), function (b) { b.classList.remove('is-on'); });
      });
    });
  }

  // ---------- поиск по сотруднику (Гант и утилизация)
  var q = document.getElementById('rp-q');
  if (q) {
    q.addEventListener('input', function () {
      var needle = q.value.trim().toLowerCase();
      Array.prototype.forEach.call(document.querySelectorAll('.rp-grow--emp, tr.rp-main[data-name]'), function (row) {
        var hit = !needle || (row.getAttribute('data-name') || '').indexOf(needle) >= 0;
        row.style.display = hit ? '' : 'none';
        var detail = row.getAttribute('data-name') && document.querySelector('tr.rp-detail[data-detail-for="' + row.getAttribute('data-name') + '"]');
        if (detail) detail.style.display = hit ? '' : 'none';
      });
    });
  }

  // ---------- таблицы: сортировка и раскрытие строк
  function initTable(table) {
    var tbody = table.tBodies[0];
    var sortKey = null, asc = true;

    function pairs() {
      return Array.prototype.map.call(tbody.querySelectorAll('tr.rp-main'), function (row) {
        var key = row.getAttribute('data-key') || row.getAttribute('data-name');
        return { row: row, detail: tbody.querySelector('tr.rp-detail[data-detail-for="' + key + '"]') };
      });
    }
    function apply(key, ascending) {
      var th = table.querySelector('th[data-sort="' + key + '"]');
      var isNum = th && th.getAttribute('data-type') === 'num';
      var list = pairs().sort(function (a, b) {
        var x = a.row.getAttribute('data-sort-' + key) || '', y = b.row.getAttribute('data-sort-' + key) || '';
        if (isNum) { x = parseFloat(x) || 0; y = parseFloat(y) || 0; }
        return (x < y ? -1 : (x > y ? 1 : 0)) * (ascending ? 1 : -1);
      });
      list.forEach(function (p) { tbody.appendChild(p.row); if (p.detail) tbody.appendChild(p.detail); });
      Array.prototype.forEach.call(table.querySelectorAll('th[data-sort]'), function (h) {
        h.setAttribute('aria-sort', h === th ? (ascending ? 'ascending' : 'descending') : 'none');
      });
    }
    Array.prototype.forEach.call(table.querySelectorAll('th[data-sort]'), function (th) {
      th.addEventListener('click', function () {
        var key = th.getAttribute('data-sort');
        if (sortKey === key) asc = !asc; else { sortKey = key; asc = th.getAttribute('data-type') === 'text'; }
        apply(sortKey, asc);
      });
    });
    var def = table.getAttribute('data-default-sort');
    if (def) { var p = def.split(':'); sortKey = p[0]; asc = p[1] === 'asc'; apply(sortKey, asc); }

    function toggle(row) {
      var key = row.getAttribute('data-key') || row.getAttribute('data-name');
      var detail = tbody.querySelector('tr.rp-detail[data-detail-for="' + key + '"]');
      if (!detail) return;
      var open = detail.hidden;
      detail.hidden = !open;
      row.classList.toggle('is-open', open);
      row.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    tbody.addEventListener('click', function (e) {
      var row = e.target.closest('tr.rp-main');
      if (row && tbody.contains(row) && !e.target.closest('a, button')) toggle(row);
    });
    tbody.addEventListener('keydown', function (e) {
      var row = e.target.closest('tr.rp-main');
      if (row && e.target === row && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggle(row); }
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll('table[data-sortable]'), initTable);

  var cols = document.getElementById('rp-econ-cols');
  if (cols) {
    cols.addEventListener('change', function () {
      var t = document.getElementById('rp-econ');
      if (t) t.classList.toggle('show-cols', cols.checked);
    });
  }

  // ---------- выполнение задач: дерево и фильтр по светофору
  var tree = document.getElementById('exec-report-table');
  if (tree) {
    function hideSubtree(id, hide) {
      Array.prototype.forEach.call(tree.querySelectorAll('[data-exec-parent="' + id + '"]'), function (row) {
        row.hidden = hide;
        var btn = row.querySelector('.exec-toggle');
        if (btn) { btn.setAttribute('aria-expanded', hide ? 'false' : 'true'); btn.textContent = hide ? '▶' : '▼'; }
        var cid = row.getAttribute('data-exec-id');
        if (cid) hideSubtree(cid, hide);
      });
    }
    tree.addEventListener('click', function (e) {
      var btn = e.target.closest('.exec-toggle');
      var row = btn ? btn.closest('tr') : e.target.closest('tr.rp-w, tr.rp-p');
      if (!row || !tree.contains(row)) return;
      var id = row.getAttribute('data-exec-id');
      if (!id) return;
      var b = row.querySelector('.exec-toggle');
      var open = b.getAttribute('aria-expanded') !== 'false';
      b.setAttribute('aria-expanded', open ? 'false' : 'true');
      b.textContent = open ? '▶' : '▼';
      hideSubtree(id, open);
    });
    function setAll(open) {
      Array.prototype.forEach.call(tree.querySelectorAll('tr.rp-w'), function (r) {
        var b = r.querySelector('.exec-toggle');
        b.setAttribute('aria-expanded', open ? 'true' : 'false');
        b.textContent = open ? '▼' : '▶';
        hideSubtree(r.getAttribute('data-exec-id'), !open);
        if (open) Array.prototype.forEach.call(tree.querySelectorAll('tr.rp-p .exec-toggle'), function (pb) { pb.setAttribute('aria-expanded', 'true'); pb.textContent = '▼'; });
      });
    }
    var c1 = document.getElementById('rp-collapse-all'), c2 = document.getElementById('rp-expand-all');
    if (c1) c1.addEventListener('click', function () { setAll(false); });
    if (c2) c2.addEventListener('click', function () { setAll(true); });

    var filter = document.getElementById('rp-light-filter');
    if (filter) {
      filter.addEventListener('click', function (e) {
        var chip = e.target.closest('.rp-chip');
        if (!chip) return;
        var light = chip.getAttribute('data-light');
        Array.prototype.forEach.call(filter.querySelectorAll('.rp-chip'), function (c) { c.classList.toggle('is-on', c === chip); });
        // скрываем через отдельный атрибут, чтобы не сбивать состояние «свёрнуто / развёрнуто»
        Array.prototype.forEach.call(tree.querySelectorAll('tr.rp-k'), function (r) {
          r.toggleAttribute('data-filtered', !!light && r.getAttribute('data-light') !== light);
        });
        Array.prototype.forEach.call(tree.querySelectorAll('tr.rp-p'), function (p) {
          var id = p.getAttribute('data-exec-id');
          var any = tree.querySelector('tr.rp-k[data-exec-parent="' + id + '"]:not([data-filtered])');
          p.toggleAttribute('data-filtered', !any);
        });
        Array.prototype.forEach.call(tree.querySelectorAll('tr.rp-w'), function (w) {
          var id = w.getAttribute('data-exec-id');
          var any = tree.querySelector('tr.rp-p[data-exec-parent="' + id + '"]:not([data-filtered])');
          w.toggleAttribute('data-filtered', !any);
        });
      });
    }
  }

  // ---------- диаграмма Ганта: подсветка договора
  var gin = document.getElementById('rp-gin');
  if (gin) {
    var pinned = null;
    function mark(contract) {
      Array.prototype.forEach.call(gin.querySelectorAll('.rp-gbar'), function (b) { b.classList.toggle('is-hit', contract !== null && b.getAttribute('data-c') === contract); });
      gin.classList.toggle('is-hl', contract !== null);
    }
    Array.prototype.forEach.call(gin.querySelectorAll('.rp-gbar'), function (b) {
      b.addEventListener('mouseenter', function () { if (pinned === null && !b.classList.contains('is-vac')) mark(b.getAttribute('data-c')); });
      b.addEventListener('mouseleave', function () { if (pinned === null) mark(null); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.rp-legend [data-pin]'), function (chip) {
      chip.addEventListener('click', function () {
        var c = chip.getAttribute('data-pin');
        pinned = pinned === c ? null : c;
        Array.prototype.forEach.call(document.querySelectorAll('.rp-legend [data-pin]'), function (x) { x.classList.toggle('is-on', pinned !== null && x === chip); });
        mark(pinned);
      });
    });
  }
})();
