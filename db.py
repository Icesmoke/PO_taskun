import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import DB_PATH

CHIEF_ROLE = "Руководитель проекта"


def _worker_assigned_to_short_sql(task_alias: str) -> str:
    """Match tasks.worker_name to a worker by short_name or full_name. Binds short_name twice."""
    return (
        f"(TRIM({task_alias}.worker_name) = TRIM(?)"
        f" OR TRIM({task_alias}.worker_name) = ("
        f"SELECT TRIM(full_name) FROM workers w0"
        f" WHERE TRIM(w0.short_name) = TRIM(?) LIMIT 1"
        f"))"
    )


def _chief_visible_project_sql(projects_alias: str) -> str:
    """
    Project chief sees rows they lead and contracts where they have assigned tasks.
    Binds current_short_name three times.
    """
    return (
        f"("
        f"{projects_alias}.project_chief = ?"
        f" OR EXISTS ("
        f"SELECT 1 FROM tasks t_vis"
        f" WHERE t_vis.contract_number = {projects_alias}.contract_number"
        f" AND {_worker_assigned_to_short_sql('t_vis')}"
        f")"
        f")"
    )


def _bind_short_name_thrice(short_name: str) -> Tuple[str, str, str]:
    return (short_name, short_name, short_name)


def get_connection() -> sqlite3.Connection:
    # Use detect_types for better parsing, but still normalize in utils.
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def project_stage_exists(contract_number: str, etap_number: str) -> bool:
    with get_connection() as con:
        row = con.execute(
            "SELECT 1 FROM projects WHERE contract_number = ? AND etap_number = ? LIMIT 1",
            (contract_number, etap_number),
        ).fetchone()
        return row is not None


def bonus_row_exists(rid: int) -> bool:
    with get_connection() as con:
        row = con.execute("SELECT 1 FROM bonuses WHERE rowid = ? LIMIT 1", (rid,)).fetchone()
        return row is not None


def voyage_row_exists(rid: int) -> bool:
    with get_connection() as con:
        row = con.execute("SELECT 1 FROM voyages WHERE rowid = ? LIMIT 1", (rid,)).fetchone()
        return row is not None


def contracter_row_exists(rid: int) -> bool:
    with get_connection() as con:
        row = con.execute("SELECT 1 FROM contracters WHERE rowid = ? LIMIT 1", (rid,)).fetchone()
        return row is not None


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


def delete_bonus_by_rid(rid: int) -> bool:
    with get_connection() as con:
        cur = con.execute("DELETE FROM bonuses WHERE rowid = ?", (rid,))
        con.commit()
        return cur.rowcount > 0


def update_bonus_by_rid(rid: int, row: Dict[str, Any]) -> bool:
    with get_connection() as con:
        cur = con.execute(
            """
            UPDATE bonuses
            SET contract_number = ?, etap_number = ?, worker_name = ?,
                task_date = ?, hours_number = ?, bonus_sum = ?
            WHERE rowid = ?
            """,
            (
                row.get("contract_number"),
                row.get("etap_number"),
                row.get("worker_name"),
                row.get("task_date"),
                row.get("hours_number"),
                row.get("bonus_sum"),
                rid,
            ),
        )
        con.commit()
        return cur.rowcount > 0


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


def delete_voyage_by_rid(rid: int) -> bool:
    with get_connection() as con:
        cur = con.execute("DELETE FROM voyages WHERE rowid = ?", (rid,))
        con.commit()
        return cur.rowcount > 0


def update_voyage_by_rid(rid: int, row: Dict[str, Any]) -> bool:
    with get_connection() as con:
        cur = con.execute(
            """
            UPDATE voyages
            SET contract_number = ?, etap_number = ?, worker_name = ?,
                voyage_date = ?, voyage_cost_kind = ?, voyage_cost_sum = ?
            WHERE rowid = ?
            """,
            (
                row.get("contract_number"),
                row.get("etap_number"),
                row.get("worker_name"),
                row.get("voyage_date"),
                row.get("voyage_cost_kind"),
                row.get("voyage_cost_sum"),
                rid,
            ),
        )
        con.commit()
        return cur.rowcount > 0


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


def delete_contracter_by_rid(rid: int) -> bool:
    with get_connection() as con:
        cur = con.execute("DELETE FROM contracters WHERE rowid = ?", (rid,))
        con.commit()
        return cur.rowcount > 0


def update_contracter_by_rid(rid: int, row: Dict[str, Any]) -> bool:
    with get_connection() as con:
        cur = con.execute(
            """
            UPDATE contracters
            SET contract_number = ?, etap_number = ?, contracter_name = ?,
                task_start_date = ?, task_end_date = ?,
                contracters_hours_number = ?, contracters_cost_sum = ?, comment = ?
            WHERE rowid = ?
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
                rid,
            ),
        )
        con.commit()
        return cur.rowcount > 0


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
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
) -> List[Dict[str, Any]]:
    """
    Return projects list for project_panel.
    - Director: all rows
    - Project chief: projects they lead, plus contracts with tasks assigned to them
    - Consultant: where tasks exist for this worker (tasks table)
    """
    where: List[str] = []
    params: List[Any] = []

    # Visibility by role
    # (match worker_role stored in DB)
    if role == CHIEF_ROLE:
        where.append(_chief_visible_project_sql("projects"))
        params.extend(_bind_short_name_thrice(current_short_name))
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

    sort_columns = {
        "contract_number": "contract_number",
        "project_chief": "project_chief",
        "client_name": "client_name",
        "executant_name": "executant_name",
        "plan_start_date": "date(plan_start_date)",
        "plan_end_date": "date(plan_end_date)",
        "project_status": "project_status",
    }
    direction = "DESC" if sort_dir == "desc" else "ASC"
    if sort_by and sort_by in sort_columns:
        sql += f" ORDER BY {sort_columns[sort_by]} {direction}, contract_number, etap_number"
    else:
        sql += " ORDER BY date(plan_end_date) DESC, contract_number, etap_number"

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
    project: Dict[str, Any],
) -> bool:
    """
    Update editable project columns for (contract_number, etap_number).
    Keys of `project` match create_project (except identity keys used in WHERE).
    """
    cols = [
        "contract_kind",
        "client_name",
        "executant_name",
        "contract_start_date",
        "contract_end_date",
        "plan_start_date",
        "plan_end_date",
        "project_status",
        "period",
        "project_chief",
        "etap_sum",
        "contr_sum",
        "act_date",
    ]
    sets = ", ".join(f"{c} = ?" for c in cols)
    values = [project.get(c) for c in cols]
    values.extend([contract_number, etap_number])
    with get_connection() as con:
        cur = con.execute(
            f"""
            UPDATE projects
            SET {sets}
            WHERE contract_number = ? AND etap_number = ?
            """,
            values,
        )
        con.commit()
        return cur.rowcount > 0


def _iso_date_ymd(value: object) -> Optional[str]:
    s = str(value or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def _periods_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    return start_a <= end_b and start_b <= end_a


def _worker_canonical_map(con: sqlite3.Connection) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    rows = con.execute(
        "SELECT TRIM(short_name) AS short_name, TRIM(full_name) AS full_name FROM workers"
    ).fetchall()
    for row in rows:
        short_name = (row["short_name"] or "").strip()
        full_name = (row["full_name"] or "").strip()
        canonical = short_name or full_name
        if not canonical:
            continue
        if short_name:
            mapping[short_name] = canonical
        if full_name:
            mapping[full_name] = canonical
    return mapping


def _canonical_worker(mapping: Dict[str, str], worker_name: str) -> str:
    name = worker_name.strip()
    return mapping.get(name, name)


def _scheduled_task_periods(tasks: Sequence[Dict[str, Any]], mapping: Dict[str, str]) -> List[Tuple[str, str, str]]:
    periods: List[Tuple[str, str, str]] = []
    for t in tasks:
        worker_name = str(t.get("worker_name") or "").strip()
        start = _iso_date_ymd(t.get("task_start_date"))
        end = _iso_date_ymd(t.get("task_end_date"))
        if not worker_name or not start or not end:
            continue
        periods.append((_canonical_worker(mapping, worker_name), start, end))
    return periods


def executor_has_overlapping_assignment(
    *,
    contract_number: str,
    etap_number: str,
    tasks: Sequence[Dict[str, Any]],
) -> bool:
    """
    True if the executor already has a task whose dates overlap the given period,
    either among the tasks being saved or in another project/stage.
    """
    with get_connection() as con:
        mapping = _worker_canonical_map(con)
        incoming = _scheduled_task_periods(tasks, mapping)
        if not incoming:
            return False

        for i, (worker_a, start_a, end_a) in enumerate(incoming):
            for worker_b, start_b, end_b in incoming[i + 1 :]:
                if worker_a == worker_b and _periods_overlap(start_a, end_a, start_b, end_b):
                    return True

        worker_keys = {p[0] for p in incoming}
        name_list: List[str] = []
        for stored_name, canonical in mapping.items():
            if canonical in worker_keys:
                name_list.append(stored_name)
        for key in worker_keys:
            if key not in name_list:
                name_list.append(key)

        placeholders = ",".join(["?"] * len(name_list))
        rows = con.execute(
            f"""
            SELECT TRIM(worker_name) AS worker_name,
                   date(task_start_date) AS task_start_date,
                   date(task_end_date) AS task_end_date
            FROM tasks
            WHERE TRIM(COALESCE(worker_name, '')) IN ({placeholders})
              AND NOT (contract_number = ? AND etap_number = ?)
              AND COALESCE(task_start_date, '') != ''
              AND COALESCE(task_end_date, '') != ''
            """,
            [*name_list, contract_number, etap_number],
        ).fetchall()

        existing: List[Tuple[str, str, str]] = []
        for row in rows:
            start = row["task_start_date"]
            end = row["task_end_date"]
            worker_name = (row["worker_name"] or "").strip()
            if not worker_name or not start or not end:
                continue
            existing.append((_canonical_worker(mapping, worker_name), str(start), str(end)))

        for worker_a, start_a, end_a in incoming:
            for worker_b, start_b, end_b in existing:
                if worker_a == worker_b and _periods_overlap(start_a, end_a, start_b, end_b):
                    return True
        return False


def replace_project_tasks(contract_number: str, etap_number: str, tasks: List[Dict[str, Any]]) -> None:
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            "DELETE FROM tasks WHERE contract_number = ? AND etap_number = ?",
            (contract_number, etap_number),
        )
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
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


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


def fetch_report_contract_numbers(worker_role: str, current_short_name: str) -> List[str]:
    """Distinct contract numbers visible in reports (same scope as contract_kind filter)."""
    with get_connection() as con:
        if worker_role == CHIEF_ROLE:
            rows = con.execute(
                f"""
                SELECT DISTINCT contract_number
                FROM projects
                WHERE {_chief_visible_project_sql("projects")}
                  AND contract_number IS NOT NULL
                  AND TRIM(contract_number) <> ''
                ORDER BY contract_number
                """,
                _bind_short_name_thrice(current_short_name),
            ).fetchall()
        elif worker_role == "Консультант":
            rows = con.execute(
                """
                SELECT DISTINCT t.contract_number
                FROM tasks t
                WHERE t.contract_number IS NOT NULL
                  AND TRIM(t.contract_number) <> ''
                  AND (
                    TRIM(t.worker_name) = TRIM(?)
                    OR TRIM(t.worker_name) = (
                      SELECT TRIM(full_name) FROM workers w0
                      WHERE TRIM(w0.short_name) = TRIM(?)
                      LIMIT 1
                    )
                  )
                ORDER BY t.contract_number
                """,
                (current_short_name, current_short_name),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT DISTINCT contract_number
                FROM projects
                WHERE contract_number IS NOT NULL
                  AND TRIM(contract_number) <> ''
                ORDER BY contract_number
                """
            ).fetchall()
        return [r[0] for r in rows]


def fetch_report_contract_kinds(worker_role: str, current_short_name: str) -> List[str]:
    with get_connection() as con:
        if worker_role == CHIEF_ROLE:
            rows = con.execute(
                f"""
                SELECT DISTINCT contract_kind
                FROM projects
                WHERE {_chief_visible_project_sql("projects")}
                  AND contract_kind IS NOT NULL
                ORDER BY contract_kind
                """,
                _bind_short_name_thrice(current_short_name),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT DISTINCT contract_kind FROM projects WHERE contract_kind IS NOT NULL ORDER BY contract_kind"
            ).fetchall()
        return [r[0] for r in rows]


def fetch_report_project_chiefs(worker_role: str, current_short_name: str) -> List[str]:
    with get_connection() as con:
        if worker_role == CHIEF_ROLE:
            rows = con.execute(
                f"""
                SELECT DISTINCT project_chief
                FROM projects
                WHERE {_chief_visible_project_sql("projects")}
                  AND project_chief IS NOT NULL
                  AND TRIM(project_chief) <> ''
                ORDER BY project_chief
                """,
                _bind_short_name_thrice(current_short_name),
            ).fetchall()
            return [r[0] for r in rows]
        if worker_role == "Консультант":
            rows = con.execute(
                """
                SELECT DISTINCT p.project_chief
                FROM projects p
                JOIN tasks t
                  ON t.contract_number = p.contract_number
                 AND t.etap_number = p.etap_number
                WHERE p.project_chief IS NOT NULL
                  AND TRIM(p.project_chief) <> ''
                  AND (
                    TRIM(t.worker_name) = TRIM(?)
                    OR TRIM(t.worker_name) = (
                      SELECT TRIM(full_name) FROM workers w0
                      WHERE TRIM(w0.short_name) = TRIM(?)
                      LIMIT 1
                    )
                  )
                ORDER BY p.project_chief
                """,
                (current_short_name, current_short_name),
            ).fetchall()
            return [r[0] for r in rows]
        rows = con.execute(
            "SELECT DISTINCT project_chief FROM projects WHERE project_chief IS NOT NULL ORDER BY project_chief"
        ).fetchall()
        return [r[0] for r in rows]


def _execution_role_filters(
    *,
    worker_role: str,
    current_short_name: str,
    project_chief: Optional[str],
    contract_number: Optional[str],
) -> Tuple[List[str], List[Any]]:
    where: List[str] = []
    params: List[Any] = []
    if worker_role == CHIEF_ROLE:
        where.append(_chief_visible_project_sql("p"))
        params.extend(_bind_short_name_thrice(current_short_name))
    elif worker_role == "Консультант":
        where.append(
            "("
            "TRIM(t.worker_name) = TRIM(?)"
            " OR TRIM(t.worker_name) = ("
            "SELECT TRIM(full_name) FROM workers w0 WHERE TRIM(w0.short_name) = TRIM(?) LIMIT 1"
            ")"
            ")"
        )
        params.extend([current_short_name, current_short_name])
    if project_chief:
        where.append("p.project_chief = ?")
        params.append(project_chief)
    if contract_number:
        where.append("t.contract_number = ?")
        params.append(contract_number)
    return where, params


def fetch_tasks_for_execution_report(
    *,
    start_date_iso: str,
    end_date_iso: str,
    worker_role: str,
    current_short_name: str,
    project_chief: Optional[str] = None,
    contract_number: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Tasks for «Выполнение задач»: a task is included if its date interval
    overlaps [start, end] (same overlap rule as Gantt).
    Worker name is resolved to workers.short_name when possible.
    """
    where, params = _execution_role_filters(
        worker_role=worker_role,
        current_short_name=current_short_name,
        project_chief=project_chief,
        contract_number=contract_number,
    )
    where.append("date(t.task_start_date) <= date(?)")
    params.append(end_date_iso)
    where.append("date(t.task_end_date) >= date(?)")
    params.append(start_date_iso)
    sql = f"""
        SELECT
            COALESCE(w_sn.short_name, w_fn.short_name, TRIM(t.worker_name)) AS worker_name,
            COALESCE(w_sn.full_name, w_fn.full_name, '') AS worker_full_name,
            COALESCE(w_sn.enabled, w_fn.enabled, 1) AS worker_enabled,
            t.contract_number,
            t.etap_number,
            p.project_status,
            p.plan_start_date,
            p.plan_end_date,
            t.task_name,
            t.task_status,
            t.task_start_date,
            t.task_end_date
        FROM tasks t
        JOIN projects p
          ON p.contract_number = t.contract_number
         AND p.etap_number = t.etap_number
        LEFT JOIN workers w_sn
          ON TRIM(t.worker_name) = TRIM(w_sn.short_name)
        LEFT JOIN workers w_fn
          ON w_sn.workers_id IS NULL
         AND TRIM(t.worker_name) = TRIM(w_fn.full_name)
        WHERE {" AND ".join(where)}
        ORDER BY worker_name, t.contract_number, t.etap_number, date(t.task_start_date), t.task_name
    """
    with get_connection() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetch_tasks_intervals_for_reports(
    *,
    start_date_iso: str,  # YYYY-MM-DD
    end_date_iso: str,  # YYYY-MM-DD
    worker_role: str,
    current_short_name: str,
    contract_kind: Optional[str] = None,
    project_chief: Optional[str] = None,
    contract_number: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns task intervals clipped to [start_date_iso, end_date_iso] and filtered by:
    - role visibility (chief: led projects plus contracts with assigned tasks)
    - contract_kind (optional)
    - project_chief (optional)
    - contract_number (optional)
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
        if worker_role == CHIEF_ROLE:
            where.append(_chief_visible_project_sql("p"))
            params.extend(_bind_short_name_thrice(current_short_name))

        if contract_kind:
            where.append("p.contract_kind = ?")
            params.append(contract_kind)

        if project_chief:
            where.append("p.project_chief = ?")
            params.append(project_chief)

        if contract_number:
            where.append("t.contract_number = ?")
            params.append(contract_number)

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
    contract_number: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (min_date_iso, max_date_iso) in YYYY-MM-DD based on task_start/task_end overlap.
    """
    with get_connection() as con:
        where = []
        params: List[Any] = []

        # role visibility
        if worker_role == CHIEF_ROLE:
            where.append(_chief_visible_project_sql("p"))
            params.extend(_bind_short_name_thrice(current_short_name))
        elif worker_role == "Консультант":
            where.append(
                "("
                "TRIM(t.worker_name) = TRIM(?)"
                " OR TRIM(t.worker_name) = ("
                "SELECT TRIM(full_name) FROM workers w0 WHERE TRIM(w0.short_name) = TRIM(?) LIMIT 1"
                ")"
                ")"
            )
            params.extend([current_short_name, current_short_name])

        if contract_kind:
            where.append("p.contract_kind = ?")
            params.append(contract_kind)

        if project_chief:
            where.append("p.project_chief = ?")
            params.append(project_chief)

        if contract_number:
            where.append("t.contract_number = ?")
            params.append(contract_number)

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
        if worker_role == CHIEF_ROLE:
            where_scope.append(_chief_visible_project_sql("p"))
            params_scope.extend(_bind_short_name_thrice(current_short_name))

        if contract_kind:
            where_scope.append("p.contract_kind = ?")
            params_scope.append(contract_kind)

        if project_chief:
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

        if worker_role == CHIEF_ROLE:
            where_scope.append(_chief_visible_project_sql("p"))
            params_scope.extend(_bind_short_name_thrice(current_short_name))

        if contract_kind:
            where_scope.append("p.contract_kind = ?")
            params_scope.append(contract_kind)

        if project_chief:
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

        if worker_role == CHIEF_ROLE:
            where.append(_chief_visible_project_sql("p"))
            params.extend(_bind_short_name_thrice(current_short_name))

        if contract_kind:
            where.append("p.contract_kind = ?")
            params.append(contract_kind)

        if project_chief:
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

