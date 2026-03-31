import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    # Use detect_types for better parsing, but still normalize in utils.
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def fetch_distinct_values(table: str, column: str) -> List[str]:
    """
    Safe helper for simple DISTINCT lists from known tables/columns.
    """
    allowed = {
        ("bonuses", "contract_number"),
        ("bonuses", "worker_name"),
        ("voyages", "contract_number"),
        ("voyages", "worker_name"),
        ("voyages", "voyage_cost_kind"),
        ("contracters", "contract_number"),
        ("contracters", "contracter_name"),
    }
    if (table, column) not in allowed:
        raise ValueError("Unsupported table/column for DISTINCT list")
    with get_connection() as con:
        rows = con.execute(
            f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND TRIM({column})<>'' ORDER BY {column}"
        ).fetchall()
        return [r[0] for r in rows]


def fetch_bonuses(
    *,
    contract_numbers: Optional[Sequence[str]] = None,
    worker_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    params: List[Any] = []
    if contract_numbers:
        where.append("contract_number IN ({})".format(",".join(["?"] * len(contract_numbers))))
        params.extend(contract_numbers)
    if worker_names:
        where.append("worker_name IN ({})".format(",".join(["?"] * len(worker_names))))
        params.extend(worker_names)
    sql = """
        SELECT
          rowid AS rid,
          contract_number, etap_number, worker_name,
          task_date, hours_number, bonus_sum
        FROM bonuses
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date(task_date) DESC, contract_number, etap_number, worker_name"
    with get_connection() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def insert_bonus(row: Dict[str, Any]) -> None:
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO bonuses (contract_number, etap_number, worker_name, task_date, hours_number, bonus_sum)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("contract_number"),
                row.get("etap_number"),
                row.get("worker_name"),
                row.get("task_date"),
                row.get("hours_number"),
                row.get("bonus_sum"),
            ),
        )
        con.commit()


def delete_bonus_by_rid(rid: int) -> None:
    with get_connection() as con:
        con.execute("DELETE FROM bonuses WHERE rowid = ?", (rid,))
        con.commit()


def fetch_voyages(
    *,
    contract_numbers: Optional[Sequence[str]] = None,
    worker_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    params: List[Any] = []
    if contract_numbers:
        where.append("contract_number IN ({})".format(",".join(["?"] * len(contract_numbers))))
        params.extend(contract_numbers)
    if worker_names:
        where.append("worker_name IN ({})".format(",".join(["?"] * len(worker_names))))
        params.extend(worker_names)
    sql = """
        SELECT
          rowid AS rid,
          contract_number, etap_number, worker_name,
          voyage_date, voyage_cost_kind, voyage_cost_sum
        FROM voyages
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date(voyage_date) DESC, contract_number, etap_number, worker_name"
    with get_connection() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def insert_voyage(row: Dict[str, Any]) -> None:
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO voyages (contract_number, etap_number, worker_name, voyage_date, voyage_cost_kind, voyage_cost_sum)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("contract_number"),
                row.get("etap_number"),
                row.get("worker_name"),
                row.get("voyage_date"),
                row.get("voyage_cost_kind"),
                row.get("voyage_cost_sum"),
            ),
        )
        con.commit()


def delete_voyage_by_rid(rid: int) -> None:
    with get_connection() as con:
        con.execute("DELETE FROM voyages WHERE rowid = ?", (rid,))
        con.commit()


def fetch_contracters_rows(
    *,
    contract_numbers: Optional[Sequence[str]] = None,
    contracter_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    params: List[Any] = []
    if contract_numbers:
        where.append("contract_number IN ({})".format(",".join(["?"] * len(contract_numbers))))
        params.extend(contract_numbers)
    if contracter_names:
        where.append("contracter_name IN ({})".format(",".join(["?"] * len(contracter_names))))
        params.extend(contracter_names)
    sql = """
        SELECT
          rowid AS rid,
          contract_number, etap_number, contracter_name,
          task_start_date, task_end_date,
          contracters_hours_number, contracters_cost_sum, comment
        FROM contracters
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date(task_start_date) DESC, contract_number, etap_number, contracter_name"
    with get_connection() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def insert_contracter(row: Dict[str, Any]) -> None:
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO contracters (
              contract_number, etap_number, contracter_name,
              task_start_date, task_end_date,
              contracters_hours_number, contracters_cost_sum, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("contract_number"),
                row.get("etap_number"),
                row.get("contracter_name"),
                row.get("task_start_date"),
                row.get("task_end_date"),
                row.get("contracters_hours_number"),
                row.get("contracters_cost_sum"),
                row.get("comment"),
            ),
        )
        con.commit()


def delete_contracter_by_rid(rid: int) -> None:
    with get_connection() as con:
        con.execute("DELETE FROM contracters WHERE rowid = ?", (rid,))
        con.commit()


def fetch_workers(*, enabled_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as con:
        sql = "SELECT workers_id, full_name, short_name, worker_role, tarif_per_hour, enabled FROM workers"
        params: List[Any] = []
        if enabled_only:
            sql += " WHERE COALESCE(enabled, 1) = 1"
        sql += " ORDER BY short_name"
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetch_worker_by_short_name(
    short_name: str, *, enabled_only: bool = True, for_auth: bool = False
) -> Optional[Dict[str, Any]]:
    with get_connection() as con:
        fields = "workers_id, full_name, short_name, worker_role, tarif_per_hour, enabled"
        if for_auth:
            fields += ", password"
        sql = f"SELECT {fields} FROM workers WHERE short_name = ?"
        params: List[Any] = [short_name]
        if enabled_only:
            sql += " AND COALESCE(enabled, 1) = 1"
        row = con.execute(sql, params).fetchone()
        return dict(row) if row else None


def fetch_project_statuses() -> List[str]:
    # We do not have status_id stored in projects, so best-effort: show distinct values from projects.
    with get_connection() as con:
        rows = con.execute("SELECT DISTINCT project_status FROM projects WHERE project_status IS NOT NULL ORDER BY project_status").fetchall()
        return [r[0] for r in rows if r[0] is not None]


def fetch_project_status_catalog() -> List[str]:
    with get_connection() as con:
        rows = con.execute(
            "SELECT status_name FROM project_statuses WHERE status_name IS NOT NULL ORDER BY status_id"
        ).fetchall()
        return [r[0] for r in rows if r[0] is not None]


def fetch_projects(
    *,
    role: str,
    current_short_name: str,
    contract_kinds: Optional[Sequence[str]] = None,
    executant_names: Optional[Sequence[str]] = None,
    project_chiefs: Optional[Sequence[str]] = None,
    statuses: Optional[Sequence[str]] = None,
    period_start: Optional[str] = None,  # dd.mm.YYYY
    period_end: Optional[str] = None,  # dd.mm.YYYY
) -> List[Dict[str, Any]]:
    """
    Return projects list for project_panel.
    - Director: all rows
    - Project chief: where project_chief == short_name
    - Consultant: where tasks exist for this worker (tasks table)
    """
    where: List[str] = []
    params: List[Any] = []

    # Visibility by role
    # (match worker_role stored in DB)
    if role == "Руководитель проекта":
        where.append("project_chief = ?")
        params.append(current_short_name)
    elif role == "Консультант":
        where.append(
            "EXISTS (SELECT 1 FROM tasks t WHERE t.contract_number = projects.contract_number AND t.worker_name = ?)"
        )
        params.append(current_short_name)

    if contract_kinds:
        where.append(
            "contract_kind IN ({})".format(",".join(["?"] * len(contract_kinds)))
        )
        params.extend(contract_kinds)

    if executant_names:
        where.append(
            "executant_name IN ({})".format(",".join(["?"] * len(executant_names)))
        )
        params.extend(executant_names)

    # Additional filter for Director only (project_panel -> projects_sheet -> column project_chief).
    if project_chiefs and role == "Директор":
        where.append(
            "project_chief IN ({})".format(",".join(["?"] * len(project_chiefs)))
        )
        params.extend(project_chiefs)

    if statuses:
        where.append(
            "project_status IN ({})".format(",".join(["?"] * len(statuses)))
        )
        params.extend(statuses)

    # Period filter: variant b (start/end inside range)
    # We compare `date(plan_start_date)` and `date(plan_end_date)` with range boundaries.
    # Caller should pass dd.mm.YYYY (or dd-mm-YYYY) which we convert in SQL via substr.
    if period_start and period_end:
        # Convert dd.mm.YYYY -> YYYY-MM-DD in SQL using substr.
        # start_date_ymd = substr(:start,7,4)||'-'||substr(:start,4,2)||'-'||substr(:start,1,2)
        period_start = period_start.replace(".", "-")
        period_end = period_end.replace(".", "-")
        where.append(
            "("
            "date(plan_start_date) >= (substr(? ,7,4)||'-'||substr(? ,4,2)||'-'||substr(? ,1,2))"
            " AND date(plan_end_date) <= (substr(? ,7,4)||'-'||substr(? ,4,2)||'-'||substr(? ,1,2))"
            ")"
        )
        params.extend([period_start, period_start, period_start, period_end, period_end, period_end])

    sql = """
        SELECT
            contract_number,
            contract_kind,
            client_name,
            executant_name,
            contract_start_date,
            contract_end_date,
            plan_start_date,
            plan_end_date,
            project_status,
            etap_number,
            period,
            project_chief,
            etap_sum,
            contr_sum,
            act_date
        FROM projects
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY contract_number, etap_number"

    with get_connection() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def create_project(project: Dict[str, Any]) -> None:
    """
    Insert new row into `projects`.
    Expected keys match columns used in project_panel (projects_sheet).
    """
    cols = [
        "contract_number",
        "contract_kind",
        "client_name",
        "executant_name",
        "contract_start_date",
        "contract_end_date",
        "plan_start_date",
        "plan_end_date",
        "project_status",
        "etap_number",
        "period",
        "project_chief",
        "etap_sum",
        "contr_sum",
        "act_date",
    ]
    values = [project.get(c) for c in cols]

    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders})"

    with get_connection() as con:
        con.execute(sql, values)
        con.commit()

def fetch_project_tasks(contract_number: str, etap_number: str) -> List[Dict[str, Any]]:
    with get_connection() as con:
        rows = con.execute(
            "SELECT contract_number, etap_number, task_name, task_adenda, worker_name, task_start_date, task_end_date, task_comment, working_file, task_status "
            "FROM tasks WHERE contract_number = ? AND etap_number = ? ORDER BY task_name",
            (contract_number, etap_number),
        ).fetchall()
        return [dict(r) for r in rows]


def update_project_fields(
    *,
    contract_number: str,
    etap_number: str,
    plan_start_date: str,
    plan_end_date: str,
    project_status: str,
    act_date: Optional[str],
) -> None:
    with get_connection() as con:
        con.execute(
            """
            UPDATE projects
            SET plan_start_date = ?, plan_end_date = ?, project_status = ?, act_date = ?
            WHERE contract_number = ? AND etap_number = ?
            """,
            (plan_start_date, plan_end_date, project_status, act_date, contract_number, etap_number),
        )
        con.commit()


def replace_project_tasks(contract_number: str, etap_number: str, tasks: List[Dict[str, Any]]) -> None:
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM tasks WHERE contract_number = ? AND etap_number = ?", (contract_number, etap_number))
        for t in tasks:
            cur.execute(
                """
                INSERT INTO tasks (
                    contract_number, etap_number, task_name, task_adenda,
                    worker_name, task_start_date, task_end_date, task_comment,
                    working_file, task_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_number,
                    etap_number,
                    t.get("task_name", ""),
                    t.get("task_adenda", ""),
                    t.get("worker_name", ""),
                    t.get("task_start_date", ""),
                    t.get("task_end_date", ""),
                    t.get("task_comment", ""),
                    t.get("working_file", ""),
                    t.get("task_status", ""),
                ),
            )
        con.commit()


def fetch_worker_short_names() -> List[str]:
    with get_connection() as con:
        rows = con.execute("SELECT short_name FROM workers WHERE COALESCE(enabled, 1) = 1 ORDER BY short_name").fetchall()
        return [r[0] for r in rows]


def fetch_task_statuses() -> List[str]:
    with get_connection() as con:
        rows = con.execute("SELECT status_name FROM task_statuses ORDER BY status_id").fetchall()
        return [r[0] for r in rows]

def fetch_done_task_status_name() -> Optional[str]:
    """
    Task status name representing "Выполнено".
    In current DB we treat status_id=3 as 'done' (per prefilled catalog).
    """
    with get_connection() as con:
        row = con.execute("SELECT status_name FROM task_statuses WHERE status_id = 3").fetchone()
        if row and row[0]:
            return row[0]
        # Fallback: best-effort by name
        row2 = con.execute(
            "SELECT status_name FROM task_statuses WHERE lower(status_name) LIKE '%выполн%' LIMIT 1"
        ).fetchone()
        return row2[0] if row2 and row2[0] else None


def fetch_worker_roles() -> List[str]:
    with get_connection() as con:
        rows = con.execute(
            "SELECT DISTINCT worker_role FROM workers WHERE worker_role IS NOT NULL AND TRIM(worker_role)<>'' ORDER BY worker_role"
        ).fetchall()
        return [r[0] for r in rows]


def create_worker(full_name: str, short_name: str, worker_role: str) -> None:
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO workers (full_name, short_name, worker_role, tarif_per_hour, enabled)
            VALUES (?, ?, ?, 0, 1)
            """,
            (full_name, short_name, worker_role),
        )
        con.commit()


def disable_worker(workers_id: int) -> None:
    with get_connection() as con:
        con.execute("UPDATE workers SET enabled = 0 WHERE workers_id = ?", (workers_id,))
        con.commit()


def fetch_report_contract_kinds(worker_role: str, current_short_name: str) -> List[str]:
    with get_connection() as con:
        if worker_role == "Руководитель проекта":
            rows = con.execute(
                "SELECT DISTINCT contract_kind FROM projects WHERE project_chief = ? AND contract_kind IS NOT NULL ORDER BY contract_kind",
                (current_short_name,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT DISTINCT contract_kind FROM projects WHERE contract_kind IS NOT NULL ORDER BY contract_kind"
            ).fetchall()
        return [r[0] for r in rows]


def fetch_report_project_chiefs(worker_role: str, current_short_name: str) -> List[str]:
    with get_connection() as con:
        if worker_role == "Руководитель проекта":
            return [current_short_name]
        rows = con.execute(
            "SELECT DISTINCT project_chief FROM projects WHERE project_chief IS NOT NULL ORDER BY project_chief"
        ).fetchall()
        return [r[0] for r in rows]


def fetch_tasks_intervals_for_reports(
    *,
    start_date_iso: str,  # YYYY-MM-DD
    end_date_iso: str,  # YYYY-MM-DD
    worker_role: str,
    current_short_name: str,
    contract_kind: Optional[str] = None,
    project_chief: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns task intervals clipped to [start_date_iso, end_date_iso] and filtered by:
    - role visibility (chief sees only their projects)
    - contract_kind (optional)
    - project_chief (optional, but for chief it's forced by role)
    """
    with get_connection() as con:
        where = []
        params: List[Any] = []

        # overlap with [start,end]
        where.append("date(t.task_start_date) <= date(?)")
        params.append(end_date_iso)
        where.append("date(t.task_end_date) >= date(?)")
        params.append(start_date_iso)

        # role visibility
        if worker_role == "Руководитель проекта":
            where.append("p.project_chief = ?")
            params.append(current_short_name)

        if contract_kind:
            where.append("p.contract_kind = ?")
            params.append(contract_kind)

        # director can filter by project chief
        if project_chief and worker_role != "Руководитель проекта":
            where.append("p.project_chief = ?")
            params.append(project_chief)

        sql = f"""
            SELECT
                COALESCE(w_sn.short_name, w_fn.short_name, TRIM(t.worker_name)) AS worker_name,
                t.contract_number,
                date(t.task_start_date) AS task_start_date,
                date(t.task_end_date) AS task_end_date
            FROM tasks t
            JOIN projects p
              ON p.contract_number = t.contract_number
             AND p.etap_number = t.etap_number
            LEFT JOIN workers w_sn
              ON TRIM(t.worker_name) = TRIM(w_sn.short_name)
            LEFT JOIN workers w_fn
              ON w_sn.workers_id IS NULL
             AND TRIM(t.worker_name) = TRIM(w_fn.full_name)
            WHERE {' AND '.join(where)}
        """
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetch_tasks_date_bounds_for_reports(
    *,
    worker_role: str,
    current_short_name: str,
    contract_kind: Optional[str] = None,
    project_chief: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (min_date_iso, max_date_iso) in YYYY-MM-DD based on task_start/task_end overlap.
    """
    with get_connection() as con:
        where = []
        params: List[Any] = []

        # role visibility
        if worker_role == "Руководитель проекта":
            where.append("p.project_chief = ?")
            params.append(current_short_name)

        if contract_kind:
            where.append("p.contract_kind = ?")
            params.append(contract_kind)

        if project_chief and worker_role != "Руководитель проекта":
            where.append("p.project_chief = ?")
            params.append(project_chief)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        row = con.execute(
            f"""
            SELECT
                MIN(date(t.task_start_date)) AS min_d,
                MAX(date(t.task_end_date)) AS max_d
            FROM tasks t
            JOIN projects p
              ON p.contract_number = t.contract_number
             AND p.etap_number = t.etap_number
            {where_sql}
            """,
            params,
        ).fetchone()

        min_d = row[0]
        max_d = row[1]
        return (min_d, max_d)


def fetch_economy_report_rows(
    *,
    start_date_iso: str,  # YYYY-MM-DD
    end_date_iso: str,  # YYYY-MM-DD
    worker_role: str,
    current_short_name: str,
    contract_kind: Optional[str] = None,
    project_chief: Optional[str] = None,
    done_status_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Project unit economics:
    - revenue: SUM(projects.etap_sum) for stages that have tasks overlapping period (scope)
    - cost: SUM(days(task) * (workers.tarif_per_hour * 8)) only for tasks with status "Выполнено"
    - income: revenue - cost
    - margin: income / revenue
    """
    done_status_name = done_status_name or fetch_done_task_status_name() or ""

    with get_connection() as con:
        where_scope: List[str] = []
        params_scope: List[Any] = []

        # overlap with [start,end]
        where_scope.append("date(t.task_start_date) <= date(?)")
        params_scope.append(end_date_iso)
        where_scope.append("date(t.task_end_date) >= date(?)")
        params_scope.append(start_date_iso)

        # role visibility by projects
        if worker_role == "Руководитель проекта":
            where_scope.append("p.project_chief = ?")
            params_scope.append(current_short_name)

        if contract_kind:
            where_scope.append("p.contract_kind = ?")
            params_scope.append(contract_kind)

        if project_chief and worker_role != "Руководитель проекта":
            where_scope.append("p.project_chief = ?")
            params_scope.append(project_chief)

        where_scope_sql = " AND ".join(where_scope) if where_scope else "1=1"

        # We clip each task to the selected period in cost calculation.
        # CTE uses the same WHERE twice (scope + cost), so we pass scope params twice.
        sql = f"""
        WITH scope AS (
          SELECT DISTINCT p.contract_number, p.etap_number
          FROM tasks t
          JOIN projects p
            ON p.contract_number = t.contract_number
           AND p.etap_number = t.etap_number
          WHERE {where_scope_sql}
        ),
        revenue AS (
          SELECT
            p.contract_number AS contract_number,
            MAX(p.client_name) AS client_name,
            SUM(COALESCE(p.etap_sum, 0)) AS project_revenue
          FROM projects p
          JOIN scope s
            ON s.contract_number = p.contract_number
           AND s.etap_number = p.etap_number
          GROUP BY p.contract_number
        ),
        cost AS (
          SELECT
            t.contract_number AS contract_number,
            SUM(
              (
                julianday(MIN(date(t.task_end_date), date(?))) -
                julianday(MAX(date(t.task_start_date), date(?))) + 1
              )
              * COALESCE(w.tarif_per_hour, 0) * 8
            ) AS cost_revenue
          FROM tasks t
          JOIN projects p
            ON p.contract_number = t.contract_number
           AND p.etap_number = t.etap_number
          JOIN scope s
            ON s.contract_number = t.contract_number
           AND s.etap_number = t.etap_number
          LEFT JOIN workers w
            ON w.short_name = t.worker_name
          WHERE {where_scope_sql}
            AND COALESCE(t.task_status, '') = ?
          GROUP BY t.contract_number
        )
        SELECT
          r.contract_number AS contract_number,
          r.client_name AS client_name,
          r.project_revenue AS project_revenue,
          COALESCE(c.cost_revenue, 0) AS cost_revenue,
          (r.project_revenue - COALESCE(c.cost_revenue, 0)) AS project_income,
          CASE WHEN r.project_revenue = 0 THEN NULL
               ELSE (r.project_revenue - COALESCE(c.cost_revenue, 0)) * 1.0 / r.project_revenue
          END AS margin_rate
        FROM revenue r
        LEFT JOIN cost c
          ON c.contract_number = r.contract_number
        ORDER BY r.contract_number
        """

        # Params: scope params duplicated for cost WHERE + clip dates + done_status
        params: List[Any] = []
        params.extend(params_scope)  # scope
        # cost clip dates:
        params.append(end_date_iso)
        params.append(start_date_iso)
        # repeat same scope filters for cost WHERE:
        params.extend(params_scope)
        # done status
        params.append(done_status_name)

        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetch_economy_revenue_rows(
    *,
    start_date_iso: str,  # YYYY-MM-DD
    end_date_iso: str,  # YYYY-MM-DD
    worker_role: str,
    current_short_name: str,
    contract_kind: Optional[str] = None,
    project_chief: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Revenue base for economy report:
    SUM(projects.etap_sum) per contract_number for stages that have tasks overlapping period.
    """
    with get_connection() as con:
        where_scope: List[str] = []
        params_scope: List[Any] = []

        where_scope.append("date(t.task_start_date) <= date(?)")
        params_scope.append(end_date_iso)
        where_scope.append("date(t.task_end_date) >= date(?)")
        params_scope.append(start_date_iso)

        if worker_role == "Руководитель проекта":
            where_scope.append("p.project_chief = ?")
            params_scope.append(current_short_name)

        if contract_kind:
            where_scope.append("p.contract_kind = ?")
            params_scope.append(contract_kind)

        if project_chief and worker_role != "Руководитель проекта":
            where_scope.append("p.project_chief = ?")
            params_scope.append(project_chief)

        where_scope_sql = " AND ".join(where_scope) if where_scope else "1=1"

        sql = f"""
        WITH scope AS (
          SELECT DISTINCT p.contract_number, p.etap_number
          FROM tasks t
          JOIN projects p
            ON p.contract_number = t.contract_number
           AND p.etap_number = t.etap_number
          WHERE {where_scope_sql}
        )
        SELECT
          p.contract_number AS contract_number,
          p.etap_number AS etap_number,
          MAX(p.client_name) AS client_name,
          SUM(COALESCE(p.etap_sum, 0)) AS project_revenue
        FROM projects p
        JOIN scope s
          ON s.contract_number = p.contract_number
         AND s.etap_number = p.etap_number
        GROUP BY p.contract_number, p.etap_number
        ORDER BY p.contract_number, p.etap_number
        """

        rows = con.execute(sql, params_scope).fetchall()
        return [dict(r) for r in rows]


def fetch_done_tasks_for_economy(
    *,
    start_date_iso: str,  # YYYY-MM-DD
    end_date_iso: str,  # YYYY-MM-DD
    worker_role: str,
    current_short_name: str,
    contract_kind: Optional[str] = None,
    project_chief: Optional[str] = None,
    done_status_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Tasks used in economy cost calculation:
    - only tasks with status == done_status_name
    - only tasks overlapping [start,end]
    - filtered by contract_kind / project_chief and role visibility
    """
    done_status_name = done_status_name or fetch_done_task_status_name() or ""

    with get_connection() as con:
        where: List[str] = []
        params: List[Any] = []

        where.append("date(t.task_start_date) <= date(?)")
        params.append(end_date_iso)
        where.append("date(t.task_end_date) >= date(?)")
        params.append(start_date_iso)

        if worker_role == "Руководитель проекта":
            where.append("p.project_chief = ?")
            params.append(current_short_name)

        if contract_kind:
            where.append("p.contract_kind = ?")
            params.append(contract_kind)

        if project_chief and worker_role != "Руководитель проекта":
            where.append("p.project_chief = ?")
            params.append(project_chief)

        where.append("COALESCE(t.task_status, '') = ?")
        params.append(done_status_name)

        sql = f"""
        SELECT
          t.worker_name AS worker_name,
          t.contract_number AS contract_number,
          t.etap_number AS etap_number,
          date(t.task_start_date) AS task_start_date,
          date(t.task_end_date) AS task_end_date,
          COALESCE(w.tarif_per_hour, 0) AS tarif_per_hour
        FROM tasks t
        JOIN projects p
          ON p.contract_number = t.contract_number
         AND p.etap_number = t.etap_number
        LEFT JOIN workers w
          ON w.short_name = t.worker_name
        WHERE {' AND '.join(where)}
        """

        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetch_economy_addon_sums_by_stage(
    pairs: Sequence[Tuple[str, str]],
) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], float], Dict[Tuple[str, str], float]]:
    """
    Суммы по (contract_number, etap_number) из bonuses / voyages / contracters.
    """
    bonus_map: Dict[Tuple[str, str], float] = {}
    voyage_map: Dict[Tuple[str, str], float] = {}
    contracter_map: Dict[Tuple[str, str], float] = {}
    plist = list(pairs)
    if not plist:
        return bonus_map, voyage_map, contracter_map

    placeholders = ",".join(["(?,?)"] * len(plist))
    flat = [x for pair in plist for x in pair]

    with get_connection() as con:
        q_bonus = f"""
            SELECT contract_number, etap_number, SUM(COALESCE(bonus_sum, 0))
            FROM bonuses
            WHERE (contract_number, etap_number) IN ({placeholders})
            GROUP BY contract_number, etap_number
        """
        for row in con.execute(q_bonus, flat).fetchall():
            k = (str(row[0]), str(row[1]) if row[1] is not None else "")
            bonus_map[k] = float(row[2] or 0)

        q_voy = f"""
            SELECT contract_number, etap_number, SUM(COALESCE(voyage_cost_sum, 0))
            FROM voyages
            WHERE (contract_number, etap_number) IN ({placeholders})
            GROUP BY contract_number, etap_number
        """
        for row in con.execute(q_voy, flat).fetchall():
            k = (str(row[0]), str(row[1]) if row[1] is not None else "")
            voyage_map[k] = float(row[2] or 0)

        q_ctr = f"""
            SELECT contract_number, etap_number, SUM(COALESCE(contracters_cost_sum, 0))
            FROM contracters
            WHERE (contract_number, etap_number) IN ({placeholders})
            GROUP BY contract_number, etap_number
        """
        for row in con.execute(q_ctr, flat).fetchall():
            k = (str(row[0]), str(row[1]) if row[1] is not None else "")
            contracter_map[k] = float(row[2] or 0)

    return bonus_map, voyage_map, contracter_map

