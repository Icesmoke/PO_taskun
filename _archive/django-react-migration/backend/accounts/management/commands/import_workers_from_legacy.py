import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Импорт пользователей из taskun.sqlite (по умолчанию: <PO_taskun>/taskun.sqlite)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--db",
            type=str,
            default="",
            help="Путь к taskun.sqlite",
        )

    def handle(self, *args, **options):
        legacy_path = options["db"].strip()
        if legacy_path:
            p = Path(legacy_path)
        else:
            p = settings.BASE_DIR.parent / "taskun.sqlite"
        if not p.is_file():
            self.stderr.write(self.style.ERROR(f"Файл не найден: {p}"))
            return

        con = sqlite3.connect(str(p))
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT full_name, short_name, worker_role, tarif_per_hour, enabled, password
                FROM workers
                """
            ).fetchall()
        finally:
            con.close()

        created = 0
        updated = 0
        for row in rows:
            short_name = (row["short_name"] or "").strip()
            if not short_name:
                continue
            pwd = row["password"]
            legacy = "" if pwd is None else str(pwd)

            full_name = (row["full_name"] or "").strip()
            worker_role = (row["worker_role"] or "").strip()
            tarif = row["tarif_per_hour"]
            enabled = bool(row["enabled"]) if row["enabled"] is not None else True

            existing = CustomUser.objects.filter(username=short_name).first()
            if existing is None:
                u = CustomUser(
                    username=short_name,
                    full_name=full_name,
                    worker_role=worker_role,
                    tarif_per_hour=tarif,
                    enabled=enabled,
                    legacy_password_hash=legacy,
                    is_active=True,
                )
                u.set_unusable_password()
                u.save()
                created += 1
            else:
                CustomUser.objects.filter(pk=existing.pk).update(
                    full_name=full_name,
                    worker_role=worker_role,
                    tarif_per_hour=tarif,
                    enabled=enabled,
                    legacy_password_hash=legacy,
                )
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Готово: создано {created}, обновлено {updated} (источник {p})")
        )
