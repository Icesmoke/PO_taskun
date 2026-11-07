import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from utils import format_date_ddmmyyyy, parse_date_from_ddmmyyyy
from workdays import WorkdayCalendar, calendar_for_period


@dataclass(frozen=True)
class TaskInterval:
    worker_name: str
    contract_number: str
    start_date: dt.date
    end_date: dt.date


def daterange_inclusive(start: dt.date, end: dt.date) -> List[dt.date]:
    if start > end:
        return []
    days = (end - start).days
    return [start + dt.timedelta(days=i) for i in range(days + 1)]


def merge_intervals(intervals: List[Tuple[dt.date, dt.date]]) -> List[Tuple[dt.date, dt.date]]:
    """
    Merge inclusive intervals [start,end].
    """
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: List[Tuple[dt.date, dt.date]] = []
    cur_s, cur_e = intervals[0]
    for s, e in intervals[1:]:
        # overlap or contiguous
        if s <= cur_e + dt.timedelta(days=1):
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


def union_days_count(intervals: List[Tuple[dt.date, dt.date]]) -> int:
    merged = merge_intervals(intervals)
    total = 0
    for s, e in merged:
        total += (e - s).days + 1
    return total


def build_utilisation_model(
    intervals: Sequence[TaskInterval],
    *,
    calendar: WorkdayCalendar,
) -> Tuple[List[str], Dict[str, Dict[str, int]]]:
    """
    Returns:
    - employees: sorted list of worker_name
    - days_by_worker_and_contract[worker][contract] = total union days
    """
    by_key: Dict[Tuple[str, str], List[Tuple[dt.date, dt.date]]] = {}
    for it in intervals:
        key = (it.worker_name, it.contract_number)
        by_key.setdefault(key, []).append((it.start_date, it.end_date))

    days_by_worker_and_contract: Dict[str, Dict[str, int]] = {}
    employees_set: Set[str] = set()
    for (worker, contract), intvs in by_key.items():
        # Union of workdays across all intervals
        merged = merge_intervals(intvs)
        day_set: Set[dt.date] = set()
        for s, e in merged:
            day_set |= calendar.workdays_inclusive(s, e)
        days = len(day_set)
        employees_set.add(worker)
        days_by_worker_and_contract.setdefault(worker, {})[contract] = days

    employees = sorted(employees_set)
    return employees, days_by_worker_and_contract


def employee_project_workdays(
    intervals: Sequence[TaskInterval],
    *,
    calendar: WorkdayCalendar,
) -> Dict[str, int]:
    """Unique workdays per employee with any project work (union across contracts)."""
    by_worker: Dict[str, List[Tuple[dt.date, dt.date]]] = {}
    for it in intervals:
        by_worker.setdefault(it.worker_name, []).append((it.start_date, it.end_date))

    out: Dict[str, int] = {}
    for worker, intvs in by_worker.items():
        merged = merge_intervals(intvs)
        day_set: Set[dt.date] = set()
        for s, e in merged:
            day_set |= calendar.workdays_inclusive(s, e)
        out[worker] = len(day_set)
    return out


def colour_palette() -> List[str]:
    # A small palette; will be cycled by contract_number.
    return [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]


def assign_colours_to_contracts(contract_numbers: Iterable[str]) -> Dict[str, str]:
    palette = colour_palette()
    mapping: Dict[str, str] = {}
    for i, c in enumerate(sorted(set(contract_numbers))):
        mapping[c] = palette[i % len(palette)]
    return mapping


def build_gantt_model(
    intervals: Sequence[TaskInterval],
    days: Sequence[dt.date],
) -> Tuple[List[str], List[dt.date], Dict[str, Dict[dt.date, List[str]]], Dict[str, str]]:
    """
    For each worker and each day: list of contract_numbers the worker is occupied on that day.
    Deduplicated per cell.
    """
    # Pre-group by (worker, contract): list of intervals
    grouped: Dict[Tuple[str, str], List[Tuple[dt.date, dt.date]]] = {}
    for it in intervals:
        grouped.setdefault((it.worker_name, it.contract_number), []).append((it.start_date, it.end_date))

    employees = sorted({it.worker_name for it in intervals})
    contract_numbers = {it.contract_number for it in intervals}
    colour_by_contract = assign_colours_to_contracts(contract_numbers)

    # For each employee/day gather contract numbers
    cell_contracts: Dict[str, Dict[dt.date, Set[str]]] = {w: {d: set() for d in days} for w in employees}
    for (worker, contract), intvs in grouped.items():
        for day in days:
            for s, e in intvs:
                if s <= day <= e:
                    cell_contracts[worker][day].add(contract)
                    break

    # Convert sets to sorted lists for stable rendering
    cell_contracts_list: Dict[str, Dict[dt.date, List[str]]] = {}
    for w in employees:
        cell_contracts_list[w] = {d: sorted(list(cell_contracts[w][d])) for d in days}

    return employees, list(days), cell_contracts_list, colour_by_contract


_ACTIVE_TASK_STATUSES = {"план", "в работе"}
_GRAY_TASK_STATUSES = {"выполнено", "отмена"}


def _parse_db_date(value: object) -> Optional[dt.date]:
    s = format_date_ddmmyyyy(value)
    if not s:
        return None
    try:
        return parse_date_from_ddmmyyyy(s)
    except Exception:
        return None


def _pct(done: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return 100.0 * done / total


def task_traffic_light(status: str, remaining_workdays: int) -> str:
    st = (status or "").strip().casefold()
    if st in _GRAY_TASK_STATUSES:
        return "gray"
    if st in _ACTIVE_TASK_STATUSES:
        if remaining_workdays > 3:
            return "green"
        if remaining_workdays > 1:
            return "yellow"
        return "red"
    return ""


def _task_light_text(status: str, end: Optional[dt.date], remaining: int, today: dt.date) -> str:
    """Подпись к светофору срока: «5 раб. дн.», «просрочено 3 дн.», «готово»."""
    st = (status or "").strip().casefold()
    if st == "выполнено":
        return "готово"
    if st == "отмена":
        return "отмена"
    if st not in _ACTIVE_TASK_STATUSES or end is None:
        return ""
    if end < today:
        return f"просрочено {(today - end).days} дн."
    return "срок сегодня" if remaining == 0 else f"{remaining} раб. дн."


def build_execution_report(
    rows: Sequence[Dict[str, Any]],
    *,
    today: dt.date,
    enabled_short_names: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Hierarchy: worker → project stage → tasks.
    Days are summed task durations (working days). Done = status «Выполнено».
    """
    dated: List[dt.date] = [today]
    parsed: List[Dict[str, Any]] = []
    for r in rows:
        worker = str(r.get("worker_name") or "").strip()
        if not worker:
            continue
        if enabled_short_names is not None and worker not in enabled_short_names:
            continue
        enabled = r.get("worker_enabled")
        if enabled is not None and int(enabled or 0) == 0:
            continue
        t_start = _parse_db_date(r.get("task_start_date"))
        t_end = _parse_db_date(r.get("task_end_date"))
        p_start = _parse_db_date(r.get("plan_start_date"))
        p_end = _parse_db_date(r.get("plan_end_date"))
        for d in (t_start, t_end, p_start, p_end):
            if d:
                dated.append(d)
        parsed.append(
            {
                "worker_name": worker,
                "worker_full_name": str(r.get("worker_full_name") or "").strip(),
                "contract_number": str(r.get("contract_number") or "").strip(),
                "etap_number": str(r.get("etap_number") if r.get("etap_number") is not None else "").strip(),
                "project_status": str(r.get("project_status") or "").strip(),
                "plan_start": p_start,
                "plan_end": p_end,
                "task_name": str(r.get("task_name") or "").strip(),
                "task_status": str(r.get("task_status") or "").strip(),
                "task_start": t_start,
                "task_end": t_end,
            }
        )
    if not parsed:
        return []

    cal = calendar_for_period(min(dated), max(dated))
    workers: Dict[str, Dict[str, Any]] = {}

    for item in parsed:
        wkey = item["worker_name"]
        worker = workers.setdefault(
            wkey,
            {
                "worker_name": wkey,
                "full_name": item["worker_full_name"],
                "status": "",
                "start": "",
                "end": "",
                "days": 0,
                "done": 0,
                "total": 0,
                "pct": None,
                "projects": {},
            },
        )
        if item["worker_full_name"] and not worker["full_name"]:
            worker["full_name"] = item["worker_full_name"]

        pkey = (item["contract_number"], item["etap_number"])
        project = worker["projects"].setdefault(
            pkey,
            {
                "contract_number": item["contract_number"],
                "etap_number": item["etap_number"],
                "status": item["project_status"],
                "start": format_date_ddmmyyyy(item["plan_start"]) if item["plan_start"] else "",
                "end": format_date_ddmmyyyy(item["plan_end"]) if item["plan_end"] else "",
                "days": 0,
                "done": 0,
                "total": 0,
                "pct": None,
                "tasks": [],
            },
        )

        days = 0
        if item["task_start"] and item["task_end"]:
            days = len(cal.workdays_inclusive(item["task_start"], item["task_end"]))
        remaining = cal.remaining_workdays(today, item["task_end"]) if item["task_end"] else 0
        is_done = (item["task_status"] or "").strip().casefold() == "выполнено"
        done_n = 1 if is_done else 0
        project["tasks"].append(
            {
                "task_name": item["task_name"] or "—",
                "status": item["task_status"],
                "start": format_date_ddmmyyyy(item["task_start"]) if item["task_start"] else "",
                "end": format_date_ddmmyyyy(item["task_end"]) if item["task_end"] else "",
                "days": days,
                "done": done_n,
                "total": 1,
                "pct": 100.0 if is_done else 0.0,
                "light": task_traffic_light(item["task_status"], remaining),
                "light_text": _task_light_text(item["task_status"], item["task_end"], remaining, today),
            }
        )
        project["days"] += days
        project["done"] += done_n
        project["total"] += 1
        worker["days"] += days
        worker["done"] += done_n
        worker["total"] += 1

    out: List[Dict[str, Any]] = []
    for wkey in sorted(workers.keys()):
        worker = workers[wkey]
        projects_list: List[Dict[str, Any]] = []
        for pkey in sorted(worker["projects"].keys(), key=lambda x: (x[0], x[1])):
            project = worker["projects"][pkey]
            project["pct"] = _pct(project["done"], project["total"])
            projects_list.append(project)
        worker["projects"] = projects_list
        worker["pct"] = _pct(worker["done"], worker["total"])
        out.append(worker)
    return out



# ---------------------------------------------------------------------------
# Отчёт «Планирование проектов»: проекты по неделям и нагрузка руководителей
# ---------------------------------------------------------------------------

PLAN_WEEK_PX = 46  # ширина колонки-недели; то же значение задаётся в CSS через --plan-wk
PLAN_ALLOWED_WEEKS = (13, 26, 39, 52)
PLAN_DEFAULT_WEEKS = 26
PLAN_DEFAULT_NORM = 4
PLAN_NO_CHIEF = "— не назначен —"
_PLAN_MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def planning_monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    m100, m10 = n % 100, n % 10
    if 10 < m100 < 20:
        return many
    if m10 == 1:
        return one
    if 2 <= m10 <= 4:
        return few
    return many


def planning_status_class(status: object) -> str:
    st = str(status or "").strip().casefold()
    if st == "отмена":
        return "cancel"
    if st == "в работе":
        return "work"
    if st == "запланирован":
        return "plan"
    return "done"


def _format_contract_kind(value: object) -> str:
    if value is None or str(value).strip() == "":
        return ""
    try:
        f = float(value)
        return str(int(f)) if f == int(f) else str(f)
    except (TypeError, ValueError):
        return str(value).strip()


def _planning_load_class(n: int, norm: int) -> Tuple[str, float]:
    """CSS-класс и прозрачность заливки для числа проектов руководителя в неделю."""
    if n <= 0:
        return "l0", 0.0
    if n <= norm:
        return "l1", round(0.12 + 0.40 * n / norm, 2)
    if n == norm + 1:
        return "l2", 0.0
    return "l3", 0.0


def build_planning_report(
    rows: Sequence[Dict[str, Any]],
    *,
    start: dt.date,
    weeks: int,
    norm: int,
    today: dt.date,
    chief: Optional[str] = None,
    contract_kind: Optional[str] = None,
    show_done: bool = True,
    show_cancel: bool = False,
    find_len: Optional[int] = None,
    find_limit: Optional[int] = None,
    show_find: bool = False,
) -> Dict[str, Any]:
    """
    Недельная диаграмма проектов (plan_start_date … plan_end_date) и нагрузка руководителей.

    Нагрузка = число проектов руководителя, пересекающих неделю (пн–вс). Считается по всем
    его проектам, кроме отменённых, независимо от фильтров вида договора и показа завершённых.
    Записи «Отпуск …» (учёт отсутствий) в отчёт не попадают.
    """
    start = planning_monday(start)
    weeks = max(1, int(weeks))
    norm = max(1, int(norm))
    end = start + dt.timedelta(days=7 * weeks - 1)
    cur_monday = planning_monday(today)

    # --- нормализация строк
    items: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, dt.date, dt.date]] = set()
    skipped_invalid = 0
    for r in rows:
        contract = str(r.get("contract_number") or "").strip()
        if contract.casefold().startswith("отпуск"):
            continue
        try:
            p_start = dt.date.fromisoformat(str(r.get("plan_start"))[:10])
            p_end = dt.date.fromisoformat(str(r.get("plan_end"))[:10])
        except (TypeError, ValueError):
            skipped_invalid += 1
            continue
        if p_end < p_start:
            skipped_invalid += 1
            continue
        etap = str(r.get("etap_number") if r.get("etap_number") is not None else "").strip()
        key = (contract, etap, p_start, p_end)
        if key in seen:
            continue
        seen.add(key)
        status = str(r.get("project_status") or "").strip()
        items.append(
            {
                "contract": contract,
                "etap": etap,
                "kind": _format_contract_kind(r.get("contract_kind")),
                "client": str(r.get("client_name") or "").strip(),
                "chief": str(r.get("project_chief") or "").strip() or PLAN_NO_CHIEF,
                "status": status,
                "cls": planning_status_class(status),
                "start": p_start,
                "end": p_end,
            }
        )

    # --- сетка недель и месяцев
    week_list: List[Dict[str, Any]] = []
    months: List[Dict[str, Any]] = []
    for i in range(weeks):
        monday = start + dt.timedelta(weeks=i)
        thursday = monday + dt.timedelta(days=3)
        week_list.append(
            {
                "monday": monday,
                "sunday": monday + dt.timedelta(days=6),
                "iso_week": thursday.isocalendar()[1],
                "label": monday.strftime("%d.%m"),
                "is_current": monday == cur_monday,
            }
        )
        key_m = (thursday.year, thursday.month)
        if months and months[-1]["key"] == key_m:
            months[-1]["span"] += 1
        else:
            months.append({"key": key_m, "span": 1, "label": f"{_PLAN_MONTHS[thursday.month - 1]} {thursday.year}"})

    # --- нагрузка по руководителям и неделям
    chiefs_all = sorted({it["chief"] for it in items}, key=lambda s: s.casefold())
    counted = [it for it in items if it["cls"] != "cancel"]
    load: Dict[str, List[int]] = {c: [0] * weeks for c in chiefs_all}
    for it in counted:
        for i, w in enumerate(week_list):
            if it["start"] <= w["sunday"] and it["end"] >= w["monday"]:
                load[it["chief"]][i] += 1
    totals_n = [sum(load[c][i] for c in chiefs_all) for i in range(weeks)]
    tot_max = max([1] + totals_n)
    totals = [
        {
            "n": n,
            "alpha": round(0.5 * n / tot_max, 2),
            "title": f"Неделя {week_list[i]['iso_week']}: {n} {_plural_ru(n, 'проект', 'проекта', 'проектов')} у всех руководителей",
        }
        for i, n in enumerate(totals_n)
    ]

    # --- рабочие дни для подсказок
    cal: Optional[WorkdayCalendar] = None
    if items:
        cal = calendar_for_period(min(it["start"] for it in items), max(it["end"] for it in items))

    def duration_text(it: Dict[str, Any]) -> str:
        cal_days = (it["end"] - it["start"]).days + 1
        wd = len(cal.workdays_inclusive(it["start"], it["end"])) if cal else 0
        weeks_f = f"{cal_days / 7:.1f}".replace(".", ",")
        return f"{cal_days} кал. дн. (~{weeks_f} нед.), {wd} раб. дн."

    def to_bar(it: Dict[str, Any]) -> Dict[str, Any]:
        a, b = max(it["start"], start), min(it["end"], end)
        left_w = (a - start).days / 7
        width_w = max(6 / PLAN_WEEK_PX, ((b - a).days + 1) / 7)
        px = width_w * PLAN_WEEK_PX
        s_txt, e_txt = it["start"].strftime("%d.%m"), it["end"].strftime("%d.%m")
        label = f"{s_txt} – {e_txt}" if px >= 118 else (s_txt if px >= 70 else "")
        tip = (
            f"Договор {it['contract']}, этап {it['etap'] or '—'}\n"
            f"{it['client']}\n"
            f"Руководитель: {it['chief']}\n"
            f"Срок: {it['start'].strftime('%d.%m.%Y')} – {it['end'].strftime('%d.%m.%Y')}\n"
            f"Длительность: {duration_text(it)}\n"
            f"Статус: {it['status'] or '—'}"
        )
        return {
            "contract": it["contract"],
            "etap": it["etap"],
            "client": it["client"],
            "chief": it["chief"],
            "cls": it["cls"],
            "left": round(left_w, 4),
            "width": round(width_w, 4),
            "clip_l": it["start"] < start,
            "clip_r": it["end"] > end,
            "label": label,
            "title": tip,
            "start": it["start"].strftime("%d.%m.%Y"),
            "end": it["end"].strftime("%d.%m.%Y"),
            "status": it["status"],
        }

    # --- видимые проекты
    def is_visible(it: Dict[str, Any]) -> bool:
        if it["end"] < start or it["start"] > end:
            return False
        if contract_kind and it["kind"] != contract_kind:
            return False
        if it["cls"] == "done" and not show_done:
            return False
        if it["cls"] == "cancel" and not show_cancel:
            return False
        return True

    shown_chiefs = [c for c in chiefs_all if not chief or c == chief]
    do_find = find_len is not None and find_limit is not None
    all_results: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    for c in shown_chiefs:
        mine = sorted(
            (it for it in items if it["chief"] == c and is_visible(it)),
            key=lambda x: (x["start"], x["end"], x["contract"]),
        )
        cells = []
        for i, n in enumerate(load[c]):
            cls, alpha = _planning_load_class(n, norm)
            w = week_list[i]
            cells.append(
                {
                    "n": n,
                    "cls": cls,
                    "alpha": alpha,
                    "is_current": w["is_current"],
                    "title": f"{c} · неделя {w['iso_week']} ({w['monday'].strftime('%d.%m')}–{w['sunday'].strftime('%d.%m')}): "
                    f"{n} {_plural_ru(n, 'проект', 'проекта', 'проектов')}",
                }
            )
        windows: List[Dict[str, Any]] = []
        if do_find:
            run_start = -1
            for i in range(weeks + 1):
                # окна ищем только с текущей недели: прошлое для планирования не нужно
                ok = i < weeks and load[c][i] <= find_limit and week_list[i]["sunday"] >= today
                if ok and run_start < 0:
                    run_start = i
                if not ok and run_start >= 0:
                    length = i - run_start
                    if length >= find_len:
                        windows.append({"start_idx": run_start, "len": length})
                        all_results.append(
                            {
                                "chief": c,
                                "start_idx": run_start,
                                "len": length,
                                "len_word": _plural_ru(length, "неделя", "недели", "недель"),
                                "from": week_list[run_start]["monday"].strftime("%d.%m"),
                                "to": week_list[i - 1]["sunday"].strftime("%d.%m"),
                            }
                        )
                    run_start = -1
        groups.append(
            {
                "name": c,
                "cells": cells,
                "count": sum(1 for it in mine if it["cls"] != "cancel"),
                "peak": max(load[c]) if load[c] else 0,
                "windows": windows if show_find else [],
                "projects": [to_bar(it) for it in mine],
            }
        )

    flat = sorted(
        (it for it in items if is_visible(it) and (not chief or it["chief"] == chief)),
        key=lambda x: (x["start"], x["end"], x["contract"]),
    )
    peak: Dict[str, Any] = {"n": 0, "chief": "", "from": ""}
    for g in groups:
        for i, cell in enumerate(g["cells"]):
            if cell["n"] > peak["n"]:
                peak = {"n": cell["n"], "chief": g["name"], "from": week_list[i]["monday"].strftime("%d.%m")}
    today_offset = None
    if start <= today <= end:
        today_offset = round((today - start).days / 7 + 1 / 14, 4)

    return {
        "start": start,
        "end": end,
        "weeks": week_list,
        "months": months,
        "totals": totals,
        "groups": groups,
        "flat_projects": [to_bar(it) for it in flat],
        "chiefs_all": chiefs_all,
        "kinds": sorted({it["kind"] for it in items if it["kind"]}, key=lambda s: (len(s), s)),
        "today_offset": today_offset,
        "find_results": all_results if show_find else [],
        "first_window": min(all_results, key=lambda r: r["start_idx"]) if all_results else None,
        "peak": peak,
        "do_find": show_find,
        "skipped_invalid": skipped_invalid,
        "week_px": PLAN_WEEK_PX,
        "norm": norm,
    }
