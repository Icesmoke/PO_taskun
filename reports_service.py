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

