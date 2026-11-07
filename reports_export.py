"""Выгрузка отчётов в Excel (xlsx). Каждая функция принимает уже посчитанные данные отчёта и возвращает байты файла."""
import datetime as dt
from io import BytesIO
from typing import Any, Dict, List, Mapping, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_HEAD_FILL = PatternFill("solid", fgColor="E5E7EB")
_HEAD_FONT = Font(bold=True)
_TOTAL_FILL = PatternFill("solid", fgColor="F3F4F6")
_THIN = Side(style="thin", color="D1D5DB")
_BORDER = Border(bottom=_THIN)
_INT_FMT = "#,##0"
_PCT_FMT = "0.0%"


def _title(ws: Worksheet, text: str, subtitle: str) -> int:
    """Заголовок отчёта в первых строках листа; возвращает номер строки, с которой начинать таблицу."""
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = subtitle
    ws["A2"].font = Font(color="6B7280")
    return 4


def _head(ws: Worksheet, row: int, headers: Sequence[str], widths: Optional[Sequence[float]] = None) -> None:
    for col, text in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=text)
        c.font = _HEAD_FONT
        c.fill = _HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = _BORDER
    if widths:
        for col, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _bytes(wb: Workbook) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _period_text(date_start: str, date_end: str, extra: str = "") -> str:
    base = f"Период: {date_start} — {date_end}"
    return f"{base}. {extra}".strip() if extra else base


def _stamp() -> str:
    return dt.datetime.now().strftime("Сформировано %d.%m.%Y %H:%M")


def export_gantt(
    *,
    employees: Sequence[str],
    days: Sequence[dt.date],
    cells: Mapping[str, Mapping[dt.date, Sequence[str]]],
    date_start: str,
    date_end: str,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Диаграмма Ганта"
    r0 = _title(ws, "Диаграмма Ганта", _period_text(date_start, date_end) + " · " + _stamp())
    _head(ws, r0, ["Сотрудник"] + [d.strftime("%d.%m") for d in days], [26] + [11] * len(days))
    weekend_fill = PatternFill("solid", fgColor="F3F4F6")
    busy_fill = PatternFill("solid", fgColor="DBEAFE")
    for i, name in enumerate(employees, start=r0 + 1):
        ws.cell(row=i, column=1, value=name)
        for j, d in enumerate(days, start=2):
            contracts = list(cells.get(name, {}).get(d, []))
            c = ws.cell(row=i, column=j, value=", ".join(contracts))
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.font = Font(size=9)
            if contracts:
                c.fill = busy_fill
            elif d.weekday() >= 5:
                c.fill = weekend_fill
    return _bytes(wb)


def export_utilisation(
    *,
    employees: Sequence[str],
    by_employee: Mapping[str, Mapping[str, int]],
    total_days: Mapping[str, int],
    period_workdays: int,
    rate: Mapping[str, float],
    date_start: str,
    date_end: str,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Утилизация"
    r0 = _title(ws, "Отчёт по утилизации", _period_text(date_start, date_end, f"Рабочих дней в периоде: {period_workdays}.") + " · " + _stamp())
    _head(ws, r0, ["Сотрудник", "Проектных дней", "Рабочих дней", "Утилизация"], [28, 16, 16, 14])
    for i, name in enumerate(employees, start=r0 + 1):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=int(total_days.get(name, 0)))
        ws.cell(row=i, column=3, value=int(period_workdays))
        c = ws.cell(row=i, column=4, value=float(rate.get(name, 0.0)) / 100.0)
        c.number_format = _PCT_FMT
    ws2 = wb.create_sheet("По проектам")
    r1 = _title(ws2, "Утилизация по проектам", _period_text(date_start, date_end) + " · " + _stamp())
    _head(ws2, r1, ["Сотрудник", "Проект (договор)", "Дней"], [28, 26, 10])
    row = r1 + 1
    for name in employees:
        for contract, days in (by_employee.get(name) or {}).items():
            ws2.cell(row=row, column=1, value=name)
            ws2.cell(row=row, column=2, value=contract)
            ws2.cell(row=row, column=3, value=int(days))
            row += 1
    return _bytes(wb)


def export_economy(*, rows: Sequence[Mapping[str, Any]], date_start: str, date_end: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Экономика проектов"
    r0 = _title(ws, "Экономика проектов", _period_text(date_start, date_end) + " · " + _stamp())
    headers = [
        "Номер проекта", "Этап проекта", "Заказчик", "Доход по проекту", "Затраты по проекту", "Затраты на премии",
        "Затраты на командировки", "Затраты на подрядчиков", "Всего затрат", "Прибыль проекта", "Маржа",
    ]
    _head(ws, r0, headers, [22, 10, 34, 16, 16, 16, 18, 18, 16, 16, 10])
    money_keys = ["project_revenue", "cost_revenue", "bonus_cost", "voyages_cost", "contracters_cost", "total_costs", "project_income"]
    sums = {k: 0.0 for k in money_keys}
    row = r0 + 1
    for r in rows:
        ws.cell(row=row, column=1, value=r.get("contract_number"))
        ws.cell(row=row, column=2, value=r.get("etap_number"))
        ws.cell(row=row, column=3, value=r.get("client_name"))
        for col, key in enumerate(money_keys, start=4):
            v = float(r.get(key) or 0)
            sums[key] += v
            c = ws.cell(row=row, column=col, value=v)
            c.number_format = _INT_FMT
        margin = r.get("margin_rate")
        c = ws.cell(row=row, column=11, value=float(margin) if margin is not None else None)
        c.number_format = _PCT_FMT
        row += 1
    ws.cell(row=row, column=1, value="Итого").font = _HEAD_FONT
    for col, key in enumerate(money_keys, start=4):
        c = ws.cell(row=row, column=col, value=sums[key])
        c.number_format = _INT_FMT
        c.font = _HEAD_FONT
    c = ws.cell(row=row, column=11, value=(sums["project_income"] / sums["project_revenue"]) if sums["project_revenue"] else None)
    c.number_format = _PCT_FMT
    c.font = _HEAD_FONT
    for col in range(1, 12):
        ws.cell(row=row, column=col).fill = _TOTAL_FILL
    return _bytes(wb)


def export_execution(*, workers: Sequence[Mapping[str, Any]], date_start: str, date_end: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Выполнение задач"
    r0 = _title(ws, "Выполнение задач", _period_text(date_start, date_end) + " · " + _stamp())
    _head(ws, r0, ["Сотрудник", "Договор", "Этап", "Задача", "Статус", "Начало", "Окончание", "Дней"], [24, 22, 8, 40, 14, 12, 12, 8])
    row = r0 + 1
    for w in workers:
        for p in w["projects"]:
            for t in p["tasks"]:
                values = [w["worker_name"], p["contract_number"], p["etap_number"], t["task_name"], t["status"], t["start"], t["end"], t["days"]]
                for col, v in enumerate(values, start=1):
                    ws.cell(row=row, column=col, value=v)
                row += 1
    return _bytes(wb)


def export_planning(*, plan: Mapping[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Нагрузка по неделям"
    weeks = plan["weeks"]
    period = f"{plan['start'].strftime('%d.%m.%Y')} — {plan['end'].strftime('%d.%m.%Y')}"
    r0 = _title(ws, "Планирование проектов: нагрузка руководителей", f"Период: {period}. Число проектов руководителя в неделю (пн–вс). " + _stamp())
    _head(ws, r0, ["Руководитель"] + [f"{w['label']}\n(нед. {w['iso_week']})" for w in weeks], [26] + [8] * len(weeks))
    ws.row_dimensions[r0].height = 32
    for i, g in enumerate(plan["groups"], start=r0 + 1):
        ws.cell(row=i, column=1, value=g["name"])
        for j, cell in enumerate(g["cells"], start=2):
            c = ws.cell(row=i, column=j, value=cell["n"])
            c.alignment = Alignment(horizontal="center")
    ws2 = wb.create_sheet("Проекты")
    r1 = _title(ws2, "Планирование проектов: список проектов", f"Период: {period}. " + _stamp())
    _head(ws2, r1, ["Руководитель", "Договор", "Этап", "Заказчик", "Начало (план)", "Окончание (план)", "Статус"], [26, 22, 8, 36, 16, 16, 18])
    row = r1 + 1
    for g in plan["groups"]:
        for b in g["projects"]:
            for col, v in enumerate([g["name"], b["contract"], b["etap"], b["client"], b["start"], b["end"], b["status"]], start=1):
                ws2.cell(row=row, column=col, value=v)
            row += 1
    return _bytes(wb)
