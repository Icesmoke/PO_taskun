from typing import Any, Dict, List

import datetime as dt
import logging
import os
from typing import Set, Tuple

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session

from config import (
    HOST,
    PORT,
    EXCEL_TEMPLATE_PATH,
    SECRET_KEY,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_FILE_DIR,
)
from db import (
    bonus_row_exists,
    contracter_row_exists,
    create_project,
    create_worker,
    disable_worker,
    project_stage_exists,
    voyage_row_exists,
    fetch_project_statuses,
    fetch_project_status_catalog,
    fetch_projects,
    fetch_project_tasks,
    fetch_tasks_date_bounds_for_reports,
    fetch_tasks_intervals_for_reports,
    fetch_report_contract_kinds,
    fetch_report_project_chiefs,
    fetch_economy_report_rows,
    fetch_economy_revenue_rows,
    fetch_done_tasks_for_economy,
    fetch_economy_addon_sums_by_stage,
    fetch_done_task_status_name,
    fetch_task_statuses,
    fetch_worker_by_short_name,
    fetch_worker_roles,
    fetch_workers,
    fetch_worker_short_names,
    fetch_bonuses,
    fetch_voyages,
    fetch_contracters_rows,
    fetch_distinct_values,
    insert_bonus,
    insert_voyage,
    insert_contracter,
    delete_bonus_by_rid,
    delete_voyage_by_rid,
    delete_contracter_by_rid,
    replace_project_tasks,
    update_project_fields,
)
from excel_parser import parse_tasks_from_xlsx
from utils import (
    format_date_ddmmyyyy,
    normalize_sqlite_timestamp_date,
    parse_date_from_ddmmyyyy,
    verify_worker_password,
)
from reports_service import (
    TaskInterval,
    build_gantt_model,
    build_utilisation_model,
    daterange_inclusive,
)
from workdays import calendar_for_period

logger = logging.getLogger("po_taskun")

_SECURITY_CSP = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "img-src 'self' data:; "
    "frame-ancestors 'none';"
)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = SECRET_KEY

    # Server-side session storage to support drafts.
    app.config.update(
        SESSION_TYPE="filesystem",
        SESSION_FILE_DIR=SESSION_FILE_DIR,
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
        SESSION_COOKIE_HTTPONLY=SESSION_COOKIE_HTTPONLY,
        SESSION_COOKIE_SAMESITE=SESSION_COOKIE_SAMESITE,
        SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
    )
    Session(app)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _SECURITY_CSP
        return response

    app.jinja_env.filters["format_date"] = format_date_ddmmyyyy
    def _format_int_grouped(value: object) -> str:
        try:
            if value is None:
                return "0"
            v = float(value)
        except Exception:
            return "0"
        s = f"{v:,.0f}"
        # Use space as thousands separator
        return s.replace(",", " ")

    app.jinja_env.filters["format_int_grouped"] = _format_int_grouped

    @app.context_processor
    def inject_globals():
        user = session.get("user")
        return {"current_user": user}

    # --- Helpers ---
    def require_login():
        if "user" not in session:
            return redirect(url_for("login"))
        return None

    def current_role() -> str:
        return session["user"]["worker_role"]

    def current_short_name() -> str:
        return session["user"]["short_name"]

    def arm_for_role(worker_role: str) -> str:
        # Human-readable ARM labels.
        if worker_role == "Директор":
            return "АРМ Директора"
        if worker_role == "Руководитель проекта":
            return "АРМ Руководителя проекта"
        if worker_role == "Консультант":
            return "АРМ Консультанта"
        if worker_role == "Администратор":
            return "АРМ Администратора"
        return "unknown"

    def is_admin(worker_role: str) -> bool:
        return worker_role == "Администратор"

    def can_edit_tasks(worker_role: str) -> bool:
        return worker_role in {"Директор", "Руководитель проекта"}

    def edit_mode(worker_role: str) -> str:
        if worker_role in {"Директор", "Руководитель проекта"}:
            return "all"
        if worker_role == "Консультант":
            return "partial"
        return "view"

    def can_upload_tasks(worker_role: str) -> bool:
        return edit_mode(worker_role) == "all"

    def can_save_tasks(worker_role: str) -> bool:
        return edit_mode(worker_role) in {"all", "partial"}

    def is_director(worker_role: str) -> bool:
        return worker_role == "Директор"

    def can_use_data_input(worker_role: str) -> bool:
        return worker_role == "Директор"

    # --- Routes ---
    @app.get("/")
    def root():
        if "user" in session:
            return redirect(url_for("projects"))
        return redirect(url_for("login"))

    @app.get("/login")
    def login():
        workers = fetch_workers(enabled_only=True)
        return render_template("login.html", workers=workers)

    @app.post("/login")
    def login_post():
        short_name = request.form.get("short_name", "").strip()
        password = request.form.get("password", "")
        if not short_name:
            flash("Выберите пользователя.", "error")
            return redirect(url_for("login"))
        worker = fetch_worker_by_short_name(short_name, for_auth=True)
        if not worker:
            flash("Пользователь не найден или отключен (enabled = 0).", "error")
            return redirect(url_for("login"))
        if not verify_worker_password(worker.get("password"), password):
            flash("Неправильный пароль", "error")
            return redirect(url_for("login"))

        session["user"] = {
            "workers_id": worker["workers_id"],
            "short_name": worker["short_name"],
            "full_name": worker["full_name"],
            "worker_role": worker["worker_role"],
        }
        return redirect(url_for("projects"))

    @app.post("/logout")
    def logout():
        session.clear()
        flash("Вы вышли из аккаунта.", "success")
        return redirect(url_for("login"))

    @app.get("/profile")
    def profile():
        redir = require_login()
        if redir:
            return redir
        user = session["user"]
        # Stage 1: photo absent -> placeholder
        return render_template("profile.html", user=user, arm=arm_for_role(user["worker_role"]))

    @app.get("/projects")
    def projects():
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        short_name = current_short_name()

        if is_admin(role):
            return redirect(url_for("rights_user_panel"))

        # Filters
        contract_kinds = request.args.getlist("contract_kind") or None
        executant_names = request.args.getlist("executant_name") or None
        project_chiefs = request.args.getlist("project_chief") or None
        statuses = request.args.getlist("project_status") or None
        period_start = request.args.get("period_start") or None
        period_end = request.args.get("period_end") or None

        # Basic validation: dd.mm.YYYY if provided.
        if period_start:
            try:
                parse_date_from_ddmmyyyy(period_start)
            except Exception:
                flash("Неверный формат периода начала (ожидается dd.mm.YYYY).", "error")
                period_start = None
        if period_end:
            try:
                parse_date_from_ddmmyyyy(period_end)
            except Exception:
                flash("Неверный формат периода окончания (ожидается dd.mm.YYYY).", "error")
                period_end = None

        projects_rows = fetch_projects(
            role=role,
            current_short_name=short_name,
            contract_kinds=contract_kinds,
            executant_names=executant_names,
            project_chiefs=project_chiefs,
            statuses=statuses,
            period_start=period_start,
            period_end=period_end,
        )

        # Filter choice lists:
        # contract_kind/executant_name can be derived from projects table, keep it simple.
        # (We avoid heavy joins for pilot.)
        all_kinds = sorted({str(p["contract_kind"]) for p in projects_rows if p["contract_kind"] is not None})
        all_executants = sorted({p["executant_name"] for p in projects_rows if p["executant_name"] is not None})
        all_project_chiefs = fetch_report_project_chiefs(role, short_name) if is_director(role) else []
        all_statuses = fetch_project_statuses()
        status_catalog = fetch_project_status_catalog() if is_director(role) else []

        return render_template(
            "projects.html",
            role=role,
            arm=arm_for_role(role),
            projects=projects_rows,
            all_kinds=all_kinds,
            all_executants=all_executants,
            all_project_chiefs=all_project_chiefs,
            all_statuses=all_statuses,
            status_catalog=status_catalog,
            contract_kinds=contract_kinds or [],
            executant_names=executant_names or [],
            project_chiefs=project_chiefs or [],
            statuses=statuses or [],
            period_start=period_start or "",
            period_end=period_end or "",
        )

    @app.post("/projects/create")
    def create_project_post():
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        if not is_director(role):
            flash("Создание проекта доступно только Директору.", "error")
            return redirect(url_for("projects"))

        def empty_to_none(v: Any) -> Any:
            if v is None:
                return None
            if isinstance(v, str):
                s = v.strip()
                return s if s != "" else None
            return v

        contract_number = (request.form.get("contract_number") or "").strip()
        etap_number = (request.form.get("etap_number") or "").strip()
        if not contract_number or not etap_number:
            flash("Заполните обязательные поля: Номер договора и Этап.", "error")
            return redirect(url_for("projects"))

        # Dates are expected as dd.mm.YYYY in UI; normalize to sqlite-compatible timestamps.
        def norm_date_ddmmyyyy(v: str) -> Any:
            s = (v or "").strip()
            if not s:
                return None
            try:
                parse_date_from_ddmmyyyy(s)
            except Exception:
                raise ValueError("Неверный формат даты (ожидается dd.mm.YYYY).")
            return normalize_sqlite_timestamp_date(s)

        try:
            project_status = empty_to_none(request.form.get("project_status"))
            if project_status is not None:
                catalog = set(fetch_project_status_catalog())
                if project_status not in catalog:
                    flash("Некорректный статус проекта.", "error")
                    return redirect(url_for("projects"))

            project = {
                "contract_number": contract_number,
                "contract_kind": empty_to_none(request.form.get("contract_kind")),
                "client_name": empty_to_none(request.form.get("client_name")),
                "executant_name": empty_to_none(request.form.get("executant_name")),
                "contract_start_date": norm_date_ddmmyyyy(request.form.get("contract_start_date", "")),
                "contract_end_date": norm_date_ddmmyyyy(request.form.get("contract_end_date", "")),
                "plan_start_date": norm_date_ddmmyyyy(request.form.get("plan_start_date", "")),
                "plan_end_date": norm_date_ddmmyyyy(request.form.get("plan_end_date", "")),
                "project_status": project_status,
                "etap_number": etap_number,
                "period": empty_to_none(request.form.get("period")),
                "project_chief": empty_to_none(request.form.get("project_chief")),
                "etap_sum": empty_to_none(request.form.get("etap_sum")),
                "contr_sum": empty_to_none(request.form.get("contr_sum")),
                "act_date": norm_date_ddmmyyyy(request.form.get("act_date", "")),
            }
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("projects"))

        try:
            create_project(project)
        except Exception:
            logger.exception("create_project failed for contract=%s etap=%s", contract_number, etap_number)
            flash("Не удалось создать проект. Обратитесь к администратору.", "error")
            return redirect(url_for("projects"))

        flash("Проект создан.", "success")
        return redirect(url_for("projects"))

    @app.post("/projects/update")
    def update_project():
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        if not is_director(role):
            flash("Редактирование проектов доступно только Директору.", "error")
            return redirect(url_for("projects"))

        contract_number = request.form.get("contract_number", "").strip()
        etap_number = request.form.get("etap_number", "").strip()
        plan_start_ui = request.form.get("plan_start_date", "").strip()
        plan_end_ui = request.form.get("plan_end_date", "").strip()
        act_date_ui = request.form.get("act_date", "").strip()
        project_status = request.form.get("project_status", "").strip()

        if not contract_number or not etap_number:
            flash("Не указан проект для сохранения.", "error")
            return redirect(url_for("projects"))

        # Validate status against catalog
        catalog = set(fetch_project_status_catalog())
        if project_status not in catalog:
            flash("Некорректный статус проекта.", "error")
            return redirect(url_for("projects"))

        try:
            parse_date_from_ddmmyyyy(plan_start_ui)
            parse_date_from_ddmmyyyy(plan_end_ui)
        except Exception:
            flash("Неверный формат дат (ожидается dd.mm.YYYY).", "error")
            return redirect(url_for("projects"))

        plan_start_db = normalize_sqlite_timestamp_date(plan_start_ui)
        plan_end_db = normalize_sqlite_timestamp_date(plan_end_ui)
        act_date_db = None
        if act_date_ui:
            try:
                parse_date_from_ddmmyyyy(act_date_ui)
            except Exception:
                flash("Неверный формат даты акта (ожидается dd.mm.YYYY).", "error")
                return redirect(url_for("projects"))
            act_date_db = normalize_sqlite_timestamp_date(act_date_ui)

        update_project_fields(
            contract_number=contract_number,
            etap_number=etap_number,
            plan_start_date=plan_start_db,
            plan_end_date=plan_end_db,
            project_status=project_status,
            act_date=act_date_db,
        )

        flash("Проект обновлен.", "success")
        return redirect(url_for("projects"))

    @app.get("/project/<path:contract_number>/<etap_number>")
    def project_card(contract_number: str, etap_number: str):
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        short_name = current_short_name()

        if is_admin(role):
            flash("На этапе 1 для Администратора доступен только просмотр профиля.", "error")
            return redirect(url_for("profile"))

        # Visibility check by contract + stage
        projects_rows = fetch_projects(
            role=role,
            current_short_name=short_name,
            contract_kinds=None,
            executant_names=None,
            statuses=None,
            period_start=None,
            period_end=None,
        )
        allowed = any(
            p["contract_number"] == contract_number and str(p.get("etap_number") or "") == str(etap_number)
            for p in projects_rows
        )
        if not allowed:
            flash("Нет доступа к выбранному проекту.", "error")
            return redirect(url_for("projects"))

        # project info from exact contract + stage row
        project_info = next(
            (
                p
                for p in projects_rows
                if p["contract_number"] == contract_number and str(p.get("etap_number") or "") == str(etap_number)
            ),
            None,
        )
        if project_info is None:
            flash("Карточка проекта не найдена в БД.", "error")
            return redirect(url_for("projects"))

        tasks_db = fetch_project_tasks(contract_number, etap_number)
        draft_key = f"draft::{contract_number}::{etap_number}"
        tasks_draft = session.get(draft_key)
        tasks = tasks_draft if tasks_draft is not None else tasks_db

        mode = edit_mode(role)

        return render_template(
            "project_card.html",
            project=project_info,
            tasks=tasks,
            contract_number=contract_number,
            etap_number=etap_number,
            workers=fetch_worker_short_names(),
            task_statuses=fetch_task_statuses(),
            arm=arm_for_role(role),
            edit_mode=mode,
        )

    @app.get("/reports")
    def reports():
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        if role not in {"Директор", "Руководитель проекта"}:
            flash("Панель отчетов доступна только Директору и Руководителю проекта.", "error")
            return redirect(url_for("projects"))

        # Type of report
        report_type = request.args.get("report_type", "gant").strip().lower()
        if report_type not in {"gant", "util", "econ"}:
            report_type = "gant"

        # Filters
        contract_kind = request.args.get("contract_kind", "").strip() or None
        project_chief = request.args.get("project_chief", "").strip() or None
        sort_by = request.args.get("sort_by", "").strip().lower() or None
        sort_dir = request.args.get("sort_dir", "desc").strip().lower()
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"

        # Chief role is forced to their project chief filter
        is_chief = role == "Руководитель проекта"
        effective_project_chief = current_short_name() if is_chief else project_chief

        date_start_raw = request.args.get("date_start", "").strip()
        date_end_raw = request.args.get("date_end", "").strip()

        # Defaults from DB
        default_min_iso, default_max_iso = fetch_tasks_date_bounds_for_reports(
            worker_role=role,
            current_short_name=current_short_name(),
            contract_kind=contract_kind,
            project_chief=project_chief,
        )

        def iso_to_ddmmyyyy(iso: str) -> str:
            # iso is YYYY-MM-DD
            parts = iso.split("-")
            if len(parts) != 3:
                return ""
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{d:02d}-{m:02d}-{y:04d}"

        if not date_start_raw:
            date_start_raw = iso_to_ddmmyyyy(default_min_iso) if default_min_iso else ""
        if not date_end_raw:
            date_end_raw = iso_to_ddmmyyyy(default_max_iso) if default_max_iso else ""

        # If still empty, fallback to last 14..next 14 days
        today = dt.date.today()
        if not date_start_raw:
            date_start_raw = (today - dt.timedelta(days=14)).strftime("%d.%m.%Y")
        if not date_end_raw:
            date_end_raw = (today + dt.timedelta(days=14)).strftime("%d.%m.%Y")

        try:
            date_start = parse_date_from_ddmmyyyy(date_start_raw)
            date_end = parse_date_from_ddmmyyyy(date_end_raw)
        except Exception:
            flash("Неверный формат дат (ожидается dd.mm.YYYY).", "error")
            return redirect(url_for("reports", report_type=report_type))

        if date_start > date_end:
            flash("Дата начала должна быть не позже даты окончания.", "error")
            return redirect(url_for("reports", report_type=report_type))

        # Гант: не более 31 дня между датами. Раньше был redirect без date_* в URL —
        # при широком MIN/MAX из БД (типично у руководителя проекта) получался бесконечный 302.
        if report_type == "gant" and (date_end - date_start).days > 31:
            date_end = date_start + dt.timedelta(days=31)
            date_end_raw = date_end.strftime("%d.%m.%Y")
            flash(
                "Для диаграммы Ганта период не более 31 дня; дата окончания автоматически сокращена.",
                "success",
            )

        # Prepare ISO dates for SQL
        start_iso = date_start.isoformat()
        end_iso = date_end.isoformat()

        # Fetch task intervals (overlap-filtered in SQL)
        rows = fetch_tasks_intervals_for_reports(
            start_date_iso=start_iso,
            end_date_iso=end_iso,
            worker_role=role,
            current_short_name=current_short_name(),
            contract_kind=contract_kind,
            project_chief=effective_project_chief,
        )

        # Convert to domain model and clip to selected date range
        intervals: List[TaskInterval] = []
        for r in rows:
            s_raw = r["task_start_date"]
            e_raw = r["task_end_date"]
            s = dt.date.fromisoformat(s_raw)
            e = dt.date.fromisoformat(e_raw)
            s2 = max(s, date_start)
            e2 = min(e, date_end)
            if s2 <= e2:
                intervals.append(
                    TaskInterval(
                        worker_name=r["worker_name"],
                        contract_number=r["contract_number"],
                        start_date=s2,
                        end_date=e2,
                    )
                )

        # Filter choices
        contract_kinds = fetch_report_contract_kinds(role, current_short_name())
        project_chiefs = fetch_report_project_chiefs(role, current_short_name())

        gant_employees: List[str] = []
        gant_days: List[dt.date] = []
        gant_cells: Dict[str, Dict[dt.date, List[str]]] = {}
        gant_colors: Dict[str, str] = {}

        util_employees: List[str] = []
        util_by_employee: Dict[str, Dict[str, int]] = {}
        util_total_by_employee: Dict[str, int] = {}

        economy_rows: List[Dict[str, Any]] = []
        done_status_name = fetch_done_task_status_name()

        if report_type == "gant":
            gant_days = daterange_inclusive(date_start, date_end)
            if intervals:
                gant_employees, gant_days, gant_cells, gant_colors = build_gantt_model(intervals, gant_days)
        elif report_type == "util":
            if intervals:
                cal = calendar_for_period(date_start, date_end)
                util_employees, util_by_employee = build_utilisation_model(intervals, calendar=cal)
                for w in util_employees:
                    util_total_by_employee[w] = sum(util_by_employee.get(w, {}).values())
        else:
            cal = calendar_for_period(date_start, date_end)

            revenue_rows = fetch_economy_revenue_rows(
                start_date_iso=start_iso,
                end_date_iso=end_iso,
                worker_role=role,
                current_short_name=current_short_name(),
                contract_kind=contract_kind,
                project_chief=effective_project_chief,
            )
            done_tasks = fetch_done_tasks_for_economy(
                start_date_iso=start_iso,
                end_date_iso=end_iso,
                worker_role=role,
                current_short_name=current_short_name(),
                contract_kind=contract_kind,
                project_chief=effective_project_chief,
                done_status_name=done_status_name,
            )

            # Затраты по проекту: рабочие дни × ставка, в разрезе (договор, этап)
            cost_by_worker_contract_etap: Dict[Tuple[str, str, str], Set[dt.date]] = {}
            rate_by_worker: Dict[str, float] = {}
            for t in done_tasks:
                worker = t["worker_name"]
                contract = t["contract_number"]
                etap = str(t.get("etap_number") if t.get("etap_number") is not None else "")
                s = dt.date.fromisoformat(t["task_start_date"])
                e = dt.date.fromisoformat(t["task_end_date"])
                s2 = max(s, date_start)
                e2 = min(e, date_end)
                if s2 > e2:
                    continue
                cost_by_worker_contract_etap.setdefault((worker, contract, etap), set()).update(
                    cal.workdays_inclusive(s2, e2)
                )
                rate_by_worker[worker] = float(t.get("tarif_per_hour") or 0) * 8.0

            cost_by_stage: Dict[Tuple[str, str], float] = {}
            for (worker, contract, etap), days_set in cost_by_worker_contract_etap.items():
                key_st = (str(contract), etap)
                cost_by_stage[key_st] = cost_by_stage.get(key_st, 0.0) + len(days_set) * rate_by_worker.get(
                    worker, 0.0
                )

            stage_pairs: List[Tuple[str, str]] = []
            for r in revenue_rows:
                c = str(r["contract_number"])
                e = str(r.get("etap_number") if r.get("etap_number") is not None else "")
                stage_pairs.append((c, e))

            bonus_map, voyage_map, contracter_map = fetch_economy_addon_sums_by_stage(stage_pairs)

            economy_rows = []
            for r in revenue_rows:
                contract = str(r["contract_number"])
                etap = str(r.get("etap_number") if r.get("etap_number") is not None else "")
                key_st = (contract, etap)
                revenue = float(r.get("project_revenue") or 0)
                cost_rev = float(cost_by_stage.get(key_st, 0.0))
                bonus_cost = float(bonus_map.get(key_st, 0.0))
                voyages_cost = float(voyage_map.get(key_st, 0.0))
                contracters_cost = float(contracter_map.get(key_st, 0.0))
                total_costs = cost_rev + bonus_cost + voyages_cost + contracters_cost
                income = revenue - total_costs
                margin = (income / revenue) if revenue else None
                economy_rows.append(
                    {
                        "contract_number": contract,
                        "etap_number": etap,
                        "client_name": r.get("client_name"),
                        "project_revenue": revenue,
                        "cost_revenue": cost_rev,
                        "bonus_cost": bonus_cost,
                        "voyages_cost": voyages_cost,
                        "contracters_cost": contracters_cost,
                        "total_costs": total_costs,
                        "project_income": income,
                        "margin_rate": margin,
                    }
                )

            # Sorting for economy report
            if sort_by in {"margin", "income", "cost"}:
                reverse = sort_dir == "desc"

                def key_fn(r: Dict[str, Any]) -> float:
                    if sort_by == "margin":
                        v = r.get("margin_rate")
                        return float(v) if v is not None else float("-inf")
                    if sort_by == "income":
                        return float(r.get("project_income") or 0)
                    return float(r.get("total_costs") or 0)

                economy_rows.sort(key=key_fn, reverse=reverse)

        return render_template(
            "reports.html",
            report_type=report_type,
            date_start=date_start_raw,
            date_end=date_end_raw,
            contract_kind=contract_kind,
            project_chief=effective_project_chief,
            is_chief=is_chief,
            contract_kinds=contract_kinds,
            project_chiefs=project_chiefs,
            # gant
            gant_employees=gant_employees,
            gant_days=gant_days,
            gant_cells=gant_cells,
            gant_colors=gant_colors,
            # util
            util_employees=util_employees,
            util_by_employee=util_by_employee,
            util_total_by_employee=util_total_by_employee,
            # economy
            economy_rows=economy_rows,
            sort_by=sort_by or "",
            sort_dir=sort_dir,
        )

    @app.get("/data_input")
    def data_input():
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        if not can_use_data_input(role):
            flash("Панель «Ввод данных» доступна только Директору и Руководителю проекта.", "error")
            return redirect(url_for("projects"))

        tab = (request.args.get("tab") or "bonuses").strip().lower()
        if tab not in {"bonuses", "voyages", "contracters"}:
            tab = "bonuses"

        f_contract = request.args.getlist("contract_number") or []
        f_worker = request.args.getlist("worker_name") or []
        f_contracter = request.args.getlist("contracter_name") or []

        bonuses_rows: List[Dict[str, Any]] = []
        voyages_rows: List[Dict[str, Any]] = []
        contracters_rows: List[Dict[str, Any]] = []

        if tab == "bonuses":
            bonuses_rows = fetch_bonuses(contract_numbers=f_contract or None, worker_names=f_worker or None)
        elif tab == "voyages":
            voyages_rows = fetch_voyages(contract_numbers=f_contract or None, worker_names=f_worker or None)
        else:
            contracters_rows = fetch_contracters_rows(
                contract_numbers=f_contract or None,
                contracter_names=f_contracter or None,
            )

        return render_template(
            "data_input.html",
            arm=arm_for_role(role),
            role=role,
            tab=tab,
            # selected filters
            f_contract=f_contract,
            f_worker=f_worker,
            f_contracter=f_contracter,
            # filter options
            filter_contracts_bonus=fetch_distinct_values("bonuses", "contract_number"),
            filter_workers_bonus=fetch_distinct_values("bonuses", "worker_name"),
            filter_contracts_voy=fetch_distinct_values("voyages", "contract_number"),
            filter_workers_voy=fetch_distinct_values("voyages", "worker_name"),
            voyage_kinds=fetch_distinct_values("voyages", "voyage_cost_kind"),
            filter_contracts_ctr=fetch_distinct_values("contracters", "contract_number"),
            filter_contracters=fetch_distinct_values("contracters", "contracter_name"),
            # rows
            bonuses_rows=bonuses_rows,
            voyages_rows=voyages_rows,
            contracters_rows=contracters_rows,
        )

    @app.post("/data_input/bonuses/create")
    def data_input_bonuses_create():
        redir = require_login()
        if redir:
            return redir
        if not can_use_data_input(current_role()):
            flash("Нет доступа.", "error")
            return redirect(url_for("projects"))

        contract_number = (request.form.get("contract_number") or "").strip()
        etap_number = (request.form.get("etap_number") or "").strip()
        worker_name = (request.form.get("worker_name") or "").strip()
        task_date_ui = (request.form.get("task_date") or "").strip()
        hours_raw = (request.form.get("hours_number") or "").strip()
        bonus_raw = (request.form.get("bonus_sum") or "").strip()

        if not contract_number or not etap_number or not worker_name or not task_date_ui:
            flash("Заполните обязательные поля: Договор, Этап, Сотрудник, Дата.", "error")
            return redirect(url_for("data_input", tab="bonuses"))

        try:
            parse_date_from_ddmmyyyy(task_date_ui)
            task_date_db = normalize_sqlite_timestamp_date(task_date_ui)
            hours = float(hours_raw.replace(",", ".")) if hours_raw else None
            bonus_sum = float(bonus_raw.replace(",", ".")) if bonus_raw else None
        except Exception:
            flash("Неверный формат данных (дата: dd.mm.YYYY, числа: 123 или 123,5).", "error")
            return redirect(url_for("data_input", tab="bonuses"))

        if not project_stage_exists(contract_number, etap_number):
            flash("Проект (договор + этап) не найден в справочнике.", "error")
            return redirect(url_for("data_input", tab="bonuses"))

        insert_bonus(
            {
                "contract_number": contract_number,
                "etap_number": etap_number,
                "worker_name": worker_name,
                "task_date": task_date_db,
                "hours_number": hours,
                "bonus_sum": bonus_sum,
            }
        )
        flash("Запись добавлена.", "success")
        return redirect(url_for("data_input", tab="bonuses"))

    @app.post("/data_input/bonuses/delete")
    def data_input_bonuses_delete():
        redir = require_login()
        if redir:
            return redir
        if not can_use_data_input(current_role()):
            flash("Нет доступа.", "error")
            return redirect(url_for("projects"))
        rid = (request.form.get("rid") or "").strip()
        if not rid.isdigit():
            flash("Выберите строку для удаления.", "error")
            return redirect(url_for("data_input", tab="bonuses"))
        rid_int = int(rid)
        if not bonus_row_exists(rid_int):
            flash("Запись не найдена.", "error")
            return redirect(url_for("data_input", tab="bonuses"))
        delete_bonus_by_rid(rid_int)
        flash("Запись удалена.", "success")
        return redirect(url_for("data_input", tab="bonuses"))

    @app.post("/data_input/voyages/create")
    def data_input_voyages_create():
        redir = require_login()
        if redir:
            return redir
        if not can_use_data_input(current_role()):
            flash("Нет доступа.", "error")
            return redirect(url_for("projects"))

        contract_number = (request.form.get("contract_number") or "").strip()
        etap_number = (request.form.get("etap_number") or "").strip()
        worker_name = (request.form.get("worker_name") or "").strip()
        voyage_date_ui = (request.form.get("voyage_date") or "").strip()
        voyage_cost_kind = (request.form.get("voyage_cost_kind") or "").strip()
        cost_raw = (request.form.get("voyage_cost_sum") or "").strip()

        if not contract_number or not etap_number or not worker_name or not voyage_date_ui:
            flash("Заполните обязательные поля: Договор, Этап, Сотрудник, Дата.", "error")
            return redirect(url_for("data_input", tab="voyages"))

        try:
            parse_date_from_ddmmyyyy(voyage_date_ui)
            voyage_date_db = normalize_sqlite_timestamp_date(voyage_date_ui)
            cost_sum = float(cost_raw.replace(",", ".")) if cost_raw else None
        except Exception:
            flash("Неверный формат данных (дата: dd.mm.YYYY, сумма: 123 или 123,5).", "error")
            return redirect(url_for("data_input", tab="voyages"))

        if not project_stage_exists(contract_number, etap_number):
            flash("Проект (договор + этап) не найден в справочнике.", "error")
            return redirect(url_for("data_input", tab="voyages"))

        insert_voyage(
            {
                "contract_number": contract_number,
                "etap_number": etap_number,
                "worker_name": worker_name,
                "voyage_date": voyage_date_db,
                "voyage_cost_kind": voyage_cost_kind or None,
                "voyage_cost_sum": cost_sum,
            }
        )
        flash("Запись добавлена.", "success")
        return redirect(url_for("data_input", tab="voyages"))

    @app.post("/data_input/voyages/delete")
    def data_input_voyages_delete():
        redir = require_login()
        if redir:
            return redir
        if not can_use_data_input(current_role()):
            flash("Нет доступа.", "error")
            return redirect(url_for("projects"))
        rid = (request.form.get("rid") or "").strip()
        if not rid.isdigit():
            flash("Выберите строку для удаления.", "error")
            return redirect(url_for("data_input", tab="voyages"))
        rid_int = int(rid)
        if not voyage_row_exists(rid_int):
            flash("Запись не найдена.", "error")
            return redirect(url_for("data_input", tab="voyages"))
        delete_voyage_by_rid(rid_int)
        flash("Запись удалена.", "success")
        return redirect(url_for("data_input", tab="voyages"))

    @app.post("/data_input/contracters/create")
    def data_input_contracters_create():
        redir = require_login()
        if redir:
            return redir
        if not can_use_data_input(current_role()):
            flash("Нет доступа.", "error")
            return redirect(url_for("projects"))

        contract_number = (request.form.get("contract_number") or "").strip()
        etap_number = (request.form.get("etap_number") or "").strip()
        contracter_name = (request.form.get("contracter_name") or "").strip()
        start_ui = (request.form.get("task_start_date") or "").strip()
        end_ui = (request.form.get("task_end_date") or "").strip()
        hours_raw = (request.form.get("contracters_hours_number") or "").strip()
        cost_raw = (request.form.get("contracters_cost_sum") or "").strip()
        comment = (request.form.get("comment") or "").strip()

        if not contract_number or not etap_number or not contracter_name:
            flash("Заполните обязательные поля: Договор, Этап, Подрядчик.", "error")
            return redirect(url_for("data_input", tab="contracters"))

        try:
            start_db = normalize_sqlite_timestamp_date(start_ui) if start_ui else None
            end_db = normalize_sqlite_timestamp_date(end_ui) if end_ui else None
            hours = float(hours_raw.replace(",", ".")) if hours_raw else None
            cost_sum = float(cost_raw.replace(",", ".")) if cost_raw else None
        except Exception:
            flash("Неверный формат данных (даты: dd.mm.YYYY, числа: 123 или 123,5).", "error")
            return redirect(url_for("data_input", tab="contracters"))

        if not project_stage_exists(contract_number, etap_number):
            flash("Проект (договор + этап) не найден в справочнике.", "error")
            return redirect(url_for("data_input", tab="contracters"))

        insert_contracter(
            {
                "contract_number": contract_number,
                "etap_number": etap_number,
                "contracter_name": contracter_name,
                "task_start_date": start_db,
                "task_end_date": end_db,
                "contracters_hours_number": hours,
                "contracters_cost_sum": cost_sum,
                "comment": comment or None,
            }
        )
        flash("Запись добавлена.", "success")
        return redirect(url_for("data_input", tab="contracters"))

    @app.post("/data_input/contracters/delete")
    def data_input_contracters_delete():
        redir = require_login()
        if redir:
            return redir
        if not can_use_data_input(current_role()):
            flash("Нет доступа.", "error")
            return redirect(url_for("projects"))
        rid = (request.form.get("rid") or "").strip()
        if not rid.isdigit():
            flash("Выберите строку для удаления.", "error")
            return redirect(url_for("data_input", tab="contracters"))
        rid_int = int(rid)
        if not contracter_row_exists(rid_int):
            flash("Запись не найдена.", "error")
            return redirect(url_for("data_input", tab="contracters"))
        delete_contracter_by_rid(rid_int)
        flash("Запись удалена.", "success")
        return redirect(url_for("data_input", tab="contracters"))

    @app.post("/project/<path:contract_number>/<etap_number>/upload_tasks")
    def upload_tasks(contract_number: str, etap_number: str):
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        if not can_upload_tasks(role):
            flash("На этапе 1 редактирование задач доступно только Директору и Руководителю проекта.", "error")
            return redirect(url_for("project_card", contract_number=contract_number, etap_number=etap_number))

        file = request.files.get("file")
        if not file or not file.filename:
            flash("Файл не выбран.", "error")
            return redirect(url_for("project_card", contract_number=contract_number, etap_number=etap_number))

        file_bytes = file.read()
        try:
            parsed = parse_tasks_from_xlsx(
                file_bytes=file_bytes,
                expected_contract_number=contract_number,
                expected_etap_number=etap_number,
            )
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("project_card", contract_number=contract_number, etap_number=etap_number))

        # Normalize dates to sqlite-compatible timestamp strings.
        normalized: List[Dict[str, Any]] = []
        for t in parsed:
            normalized.append(
                {
                    **t,
                    "task_start_date": normalize_sqlite_timestamp_date(t.get("task_start_date")),
                    "task_end_date": normalize_sqlite_timestamp_date(t.get("task_end_date")),
                }
            )

        draft_key = f"draft::{contract_number}::{etap_number}"
        session[draft_key] = normalized
        flash("Файл загружен. Проверьте таблицу и нажмите \"Сохранить\".", "success")
        return redirect(url_for("project_card", contract_number=contract_number, etap_number=etap_number))

    @app.post("/project/<path:contract_number>/<etap_number>/save_tasks")
    def save_tasks(contract_number: str, etap_number: str):
        redir = require_login()
        if redir:
            return redir

        role = current_role()
        if not can_save_tasks(role):
            flash("На этапе 1 сохранение задач доступно для Директора/Руководителя проекта/Консультанта (частично).", "error")
            return redirect(url_for("project_card", contract_number=contract_number, etap_number=etap_number))

        try:
            count = int(request.form.get("tasks_count", "0"))
        except Exception:
            count = 0

        allowed_workers = set(fetch_worker_short_names())
        allowed_statuses = set(fetch_task_statuses())
        tasks: List[Dict[str, Any]] = []
        card_url = url_for("project_card", contract_number=contract_number, etap_number=etap_number)

        for i in range(count):
            start_raw = request.form.get(f"task_start_date_{i}", "").strip()
            end_raw = request.form.get(f"task_end_date_{i}", "").strip()
            t = {
                "contract_number": contract_number,
                "etap_number": etap_number,
                "task_name": request.form.get(f"task_name_{i}", "").strip(),
                "task_adenda": request.form.get(f"task_adenda_{i}", "").strip(),
                "worker_name": request.form.get(f"worker_name_{i}", "").strip(),
                "task_comment": request.form.get(f"task_comment_{i}", "").strip(),
                "working_file": request.form.get(f"working_file_{i}", "").strip(),
                "task_status": request.form.get(f"task_status_{i}", "").strip(),
            }
            has_data = any(
                [
                    t["task_name"],
                    t["task_adenda"],
                    t["worker_name"],
                    t["task_comment"],
                    t["working_file"],
                    t["task_status"],
                    start_raw,
                    end_raw,
                ]
            )
            if not has_data:
                continue

            if t["worker_name"] and t["worker_name"] not in allowed_workers:
                flash("Некорректный исполнитель задачи.", "error")
                return redirect(card_url)
            if t["task_status"] and t["task_status"] not in allowed_statuses:
                flash("Некорректный статус задачи.", "error")
                return redirect(card_url)

            try:
                if start_raw:
                    parse_date_from_ddmmyyyy(start_raw)
                if end_raw:
                    parse_date_from_ddmmyyyy(end_raw)
            except ValueError:
                flash("Неверный формат дат (ожидается dd.mm.YYYY).", "error")
                return redirect(card_url)

            t["task_start_date"] = normalize_sqlite_timestamp_date(start_raw) if start_raw else ""
            t["task_end_date"] = normalize_sqlite_timestamp_date(end_raw) if end_raw else ""
            tasks.append(t)

        replace_project_tasks(contract_number, etap_number, tasks)

        draft_key = f"draft::{contract_number}::{etap_number}"
        session.pop(draft_key, None)

        flash("Задачи сохранены.", "success")
        return redirect(url_for("project_card", contract_number=contract_number, etap_number=etap_number))

    @app.get("/download_template")
    def download_template():
        # For convenience. Not required in TЗ, but helps.
        # Implemented as a simple file response with correct content type.
        redir = require_login()
        if redir:
            return redir

        if not can_edit_tasks(current_role()):
            flash("Загрузка шаблона доступна только для Директора/Руководителя проекта.", "error")
            return redirect(url_for("projects"))
        from flask import send_file

        return send_file(EXCEL_TEMPLATE_PATH, as_attachment=True)

    @app.get("/users")
    def rights_user_panel():
        redir = require_login()
        if redir:
            return redir
        if not is_admin(current_role()):
            flash("Панель управления пользователями доступна только Администратору.", "error")
            return redirect(url_for("projects"))

        users = fetch_workers(enabled_only=True)
        roles = fetch_worker_roles()
        return render_template("rights_user_panel.html", users=users, roles=roles, arm=arm_for_role(current_role()))

    @app.post("/users/create")
    def create_user():
        redir = require_login()
        if redir:
            return redir
        if not is_admin(current_role()):
            flash("Панель управления пользователями доступна только Администратору.", "error")
            return redirect(url_for("projects"))

        full_name = request.form.get("full_name", "").strip()
        short_name = request.form.get("short_name", "").strip()
        worker_role = request.form.get("worker_role", "").strip()
        if not full_name or not short_name or not worker_role:
            flash("Заполните все поля для создания пользователя.", "error")
            return redirect(url_for("rights_user_panel"))

        create_worker(full_name=full_name, short_name=short_name, worker_role=worker_role)
        flash("Пользователь создан.", "success")
        return redirect(url_for("rights_user_panel"))

    @app.post("/users/disable")
    def disable_user():
        redir = require_login()
        if redir:
            return redir
        if not is_admin(current_role()):
            flash("Панель управления пользователями доступна только Администратору.", "error")
            return redirect(url_for("projects"))

        worker_id_raw = request.form.get("workers_id", "").strip()
        if not worker_id_raw.isdigit():
            flash("Выберите пользователя для удаления.", "error")
            return redirect(url_for("rights_user_panel"))

        worker_id = int(worker_id_raw)
        # Protect current admin session from self-disable in pilot.
        if worker_id == session["user"]["workers_id"]:
            flash("Нельзя удалить текущего пользователя.", "error")
            return redirect(url_for("rights_user_panel"))

        disable_worker(worker_id)
        flash("Пользователь отключен (enabled = 0).", "success")
        return redirect(url_for("rights_user_panel"))

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", message="Страница не найдена."), 404

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(host=HOST, port=PORT, debug=debug)

