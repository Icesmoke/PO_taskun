"""Вспомогательные расчёты для интерфейса отчётов: быстрые периоды, сохранение фильтров, итоговые плитки, полосы Ганта."""
import datetime as dt
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from reports_service import TaskInterval, assign_colours_to_contracts, merge_intervals

PRESET_LABELS: Dict[str, str] = {
    "7": "7 дней",
    "14": "14 дней",
    "31": "31 день",
    "month": "Месяц",
    "quarter": "Квартал",
    "year": "Год",
}

# Какие быстрые периоды показываются у каждого отчёта (Гант — не более 31 дня).
PERIOD_PRESETS: Dict[str, Tuple[str, ...]] = {
    "gant": ("7", "14", "31", "month"),
    "util": ("7", "31", "month", "quarter"),
    "econ": ("month", "quarter", "year"),
    "exec": ("7", "31", "month"),
}

# Какие поля формы запоминаются между сессиями (всё остальное — разовые действия вроде экспорта).
FILTER_KEYS: Dict[str, Tuple[str, ...]] = {
    "gant": ("period", "date_start", "date_end", "contract_kind", "project_chief", "contract_number"),
    "util": ("period", "date_start", "date_end", "contract_kind", "project_chief"),
    "econ": ("period", "date_start", "date_end", "contract_kind", "project_chief"),
    "exec": ("period", "date_start", "date_end", "project_chief", "contract_number"),
    "plan": (
        "plan_start", "plan_weeks", "project_chief", "contract_kind",
        "show_done", "show_cancel", "group", "norm", "fw_len", "fw_lim",
    ),
}


def pick_filters(report_type: str, source: Mapping[str, Any]) -> Dict[str, str]:
    """Оставляет из запроса только запоминаемые поля с непустыми значениями."""
    out: Dict[str, str] = {}
    for key in FILTER_KEYS.get(report_type, ()):
        value = str(source.get(key, "") or "").strip()
        if value:
            out[key] = value
    return out


def has_filter_params(report_type: str, source: Mapping[str, Any]) -> bool:
    return any(key in source for key in FILTER_KEYS.get(report_type, ()))


def resolve_period(preset: str, today: dt.date) -> Optional[Tuple[dt.date, dt.date]]:
    """Границы быстрого периода относительно сегодняшнего дня; None — если это не быстрый период."""
    if preset in {"7", "14", "31"}:
        return today - dt.timedelta(days=int(preset) - 1), today
    if preset == "month":
        first = today.replace(day=1)
        nxt = (first + dt.timedelta(days=32)).replace(day=1)
        return first, nxt - dt.timedelta(days=1)
    if preset == "quarter":
        first_month = 3 * ((today.month - 1) // 3) + 1
        first = dt.date(today.year, first_month, 1)
        nxt = (first + dt.timedelta(days=93)).replace(day=1)
        return first, nxt - dt.timedelta(days=1)
    if preset == "year":
        return dt.date(today.year, 1, 1), dt.date(today.year, 12, 31)
    return None


def presets_for(report_type: str) -> List[Dict[str, str]]:
    return [{"key": k, "label": PRESET_LABELS[k]} for k in PERIOD_PRESETS.get(report_type, ())]


# ---------------------------------------------------------------------------
# Итоговые плитки
# ---------------------------------------------------------------------------

def _tile(title: str, value: str, sub: str = "", tone: str = "", unit: str = "") -> Dict[str, str]:
    return {"title": title, "value": value, "sub": sub, "tone": tone, "unit": unit}


def money_ru(value: float) -> str:
    """12345678 -> '12 345 678' (неразрывные пробелы между разрядами)."""
    return f"{round(value):,}".replace(",", " ")


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    m100, m10 = n % 100, n % 10
    if 10 < m100 < 20:
        return many
    if m10 == 1:
        return one
    if 2 <= m10 <= 4:
        return few
    return many


def gant_tiles(employees: Sequence[Dict[str, Any]], total_workers: int) -> List[Dict[str, str]]:
    contracts = {b["contract"] for e in employees for b in e["bars"] if not b["vacation"]}
    on_vac = sum(1 for e in employees if any(b["vacation"] for b in e["bars"]))
    dbl = sum(1 for e in employees if e["dbl"])
    return [
        _tile(
            "Сотрудников с задачами в периоде",
            str(len(employees)),
            f"из {total_workers} активных · {on_vac} в отпуске" if total_workers else f"{on_vac} в отпуске",
            unit=f"из {total_workers}" if total_workers else "",
        ),
        _tile("Проектов в периоде", str(len(contracts)), "активных договоров"),
        _tile(
            "Двойная занятость",
            str(dbl),
            "сотрудников с пересекающимися задачами" if dbl else "пересечений нет",
            tone="bad" if dbl else "ok",
        ),
    ]


def util_tiles(rates: Mapping[str, float]) -> List[Dict[str, str]]:
    values = list(rates.values())
    avg = sum(values) / len(values) if values else 0.0
    low = sum(1 for v in values if 0 < v < 50)
    zero = sum(1 for v in values if v == 0)
    return [
        _tile("Средняя утилизация", f"{avg:.1f}%", f"по {len(values)} сотрудникам", tone="ok" if avg >= 70 else "warn"),
        _tile("Недогружены (менее 50%)", str(low), "есть резерв для новых проектов", tone="warn" if low else "ok"),
        _tile("Без проектов", str(zero), "0 проектных дней в периоде", tone="bad" if zero else "ok"),
    ]


def econ_tiles(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    revenue = sum(float(r.get("project_revenue") or 0) for r in rows)
    cost = sum(float(r.get("total_costs") or 0) for r in rows)
    labor = sum(float(r.get("cost_revenue") or 0) for r in rows)
    profit = revenue - cost
    margin = profit / revenue if revenue else 0.0
    loss = sum(1 for r in rows if float(r.get("project_income") or 0) < 0)
    share = (labor / cost * 100) if cost else 0.0
    return [
        _tile("Доход по проектам", money_ru(revenue), f"{len(rows)} {plural_ru(len(rows), 'проект', 'проекта', 'проектов')}", unit="₽"),
        _tile("Всего затрат", money_ru(cost), f"трудозатраты {share:.0f}% · остальное {100 - share:.0f}%" if cost else "", tone="warn", unit="₽"),
        _tile("Прибыль", money_ru(profit), f"убыточных проектов: {loss}", tone="ok" if profit >= 0 else "bad", unit="₽"),
        _tile("Маржа", f"{margin * 100:.1f}%", "прибыль / доход", tone="ok" if margin >= 0.15 else "warn"),
    ]


def exec_tiles(workers: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    tasks = [t for w in workers for p in w["projects"] for t in p["tasks"]]
    total = len(tasks)
    cancelled = sum(1 for t in tasks if str(t.get("status") or "").strip().casefold() == "отмена")
    done = sum(1 for t in tasks if str(t.get("status") or "").strip().casefold() == "выполнено")
    active = total - cancelled
    count = lambda light: sum(1 for t in tasks if t.get("light") == light)  # noqa: E731
    return [
        _tile("Всего задач в периоде", str(total), f"{len(workers)} {plural_ru(len(workers), 'сотрудник', 'сотрудника', 'сотрудников')}"),
        _tile("Выполнено", f"{round(done / active * 100) if active else 0}%", f"{done} из {active} задач", tone="ok"),
        _tile("Срок 2–3 дня", str(count("yellow")), "требуют внимания", tone="warn"),
        _tile("Срок ≤ 1 дня", str(count("red")), "критично", tone="bad" if count("red") else "ok"),
    ]


# ---------------------------------------------------------------------------
# Диаграмма Ганта: сплошные полосы вместо плашки на каждый день
# ---------------------------------------------------------------------------

def is_vacation(contract_number: object) -> bool:
    return str(contract_number or "").strip().casefold().startswith("отпуск")


def build_gantt_bars(
    intervals: Sequence[TaskInterval],
    days: Sequence[dt.date],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Для каждого сотрудника — полосы договоров (смежные дни одного договора склеены) и номера «дорожек»,
    если у сотрудника в один день несколько договоров (двойная занятость).
    Возвращает (employees, цвет договора).
    """
    if not days:
        return [], {}
    start = days[0]
    colours = assign_colours_to_contracts({it.contract_number for it in intervals})

    grouped: Dict[str, Dict[str, List[Tuple[dt.date, dt.date]]]] = {}
    for it in intervals:
        grouped.setdefault(it.worker_name, {}).setdefault(it.contract_number, []).append((it.start_date, it.end_date))

    employees: List[Dict[str, Any]] = []
    for worker in sorted(grouped, key=lambda s: s.casefold()):
        bars: List[Dict[str, Any]] = []
        for contract, intvs in grouped[worker].items():
            for s, e in merge_intervals(intvs):
                bars.append({"contract": contract, "s": s, "e": e})
        bars.sort(key=lambda b: (b["s"], b["e"], b["contract"]))
        lane_end: List[dt.date] = []
        for b in bars:
            lane = next((i for i, last in enumerate(lane_end) if last < b["s"]), None)
            if lane is None:
                lane = len(lane_end)
                lane_end.append(b["e"])
            else:
                lane_end[lane] = max(lane_end[lane], b["e"])
            b["lane"] = lane
        out_bars = []
        for b in bars:
            span = (b["e"] - b["s"]).days + 1
            out_bars.append(
                {
                    "contract": b["contract"],
                    "left": (b["s"] - start).days,
                    "width": span,
                    "lane": b["lane"],
                    "vacation": is_vacation(b["contract"]),
                    "color": colours.get(b["contract"], "#64748b"),
                    "dates": f"{b['s'].strftime('%d.%m.%Y')} – {b['e'].strftime('%d.%m.%Y')}",
                    "label": b["contract"],
                    "show_dates": span >= 6,
                    "short_dates": f"{b['s'].strftime('%d.%m')}–{b['e'].strftime('%d.%m')}",
                }
            )
        employees.append(
            {
                "name": worker,
                "bars": out_bars,
                "lanes": max(1, len(lane_end)),
                "dbl": len(lane_end) > 1,
            }
        )
    return employees, colours


def planning_tiles(plan: Mapping[str, Any], find_len: int, find_limit: int) -> List[Dict[str, str]]:
    first = plan.get("first_window")
    peak = plan.get("peak") or {"n": 0}
    projects = sum(g["count"] for g in plan["groups"])
    if first:
        window = _tile(
            f"Ближайшее свободное окно (от {find_len} нед., до {find_limit} проектов)",
            first["chief"],
            f"с {first['from']} · {first['len']} {first['len_word']}",
            tone="ok",
        )
    else:
        window = _tile(
            f"Ближайшее свободное окно (от {find_len} нед., до {find_limit} проектов)",
            "нет",
            "измените условия поиска",
            tone="warn",
        )
    return [
        window,
        _tile(
            "Пик нагрузки",
            str(peak["n"]),
            f"{peak['chief']} · неделя с {peak['from']}" if peak["n"] else "проектов нет",
            tone="bad" if peak["n"] > plan.get("norm", 4) else "warn",
            unit=plural_ru(peak["n"], "проект", "проекта", "проектов"),
        ),
        _tile("Проектов в периоде", str(projects), f"{len(plan['groups'])} {plural_ru(len(plan['groups']), 'руководитель', 'руководителя', 'руководителей')}"),
    ]


_MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def month_spans(days: Sequence[dt.date]) -> List[Dict[str, Any]]:
    """Подписи месяцев над колонками-днями: [{label, span}]."""
    out: List[Dict[str, Any]] = []
    for d in days:
        key = (d.year, d.month)
        if out and out[-1]["key"] == key:
            out[-1]["span"] += 1
        else:
            out.append({"key": key, "span": 1, "label": f"{_MONTHS_RU[d.month - 1]} {d.year}"})
    return out


def initials(name: object) -> str:
    """«Иванов И.И.» -> «ИИ» для аватара."""
    parts = [p for p in str(name or "").replace(".", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def name_hue(name: object) -> int:
    """Стабильный оттенок аватара по имени."""
    h = 0
    for ch in str(name or ""):
        h = (h * 31 + ord(ch)) % 360
    return h
