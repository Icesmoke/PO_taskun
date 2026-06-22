import datetime as dt
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from workdays import WorkdayCalendar


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

