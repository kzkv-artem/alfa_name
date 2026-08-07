from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from alfa_agent.gov_support.db import PROJECT_ROOT

PROGRAMS_CSV_PATH = PROJECT_ROOT / "otbor" / "mery-podderzhki-msp-2026.csv"
SNAPSHOT_DATE = "2026-07-19"


def to_int(value) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def load_raw_programs(conn: sqlite3.Connection, path: Path = PROGRAMS_CSV_PATH) -> int:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = [
            (
                r["id"], "csv_manual", r["Мера"], r.get("Организатор"), r.get("Уровень"),
                r.get("Тип"), r.get("Аудитория"), r.get("Возраст"),
                to_int(r.get("Сумма_мин_руб")), to_int(r.get("Сумма_макс_руб")),
                r.get("Софинансирование"), r.get("Окно_2026"), r.get("Статус_на_19.07.2026"),
                r.get("Постоянный_прием"), r.get("Канал_подачи"), r.get("Ключевые_условия"),
                r.get("Стоп-факторы"), r.get("Источник"), r.get("Верифицировано"),
                r.get("Примечание"), SNAPSHOT_DATE,
            )
            for r in reader
        ]

    conn.executemany(
        """INSERT INTO raw_program_source (
            external_id, source_type, name_raw, organizer_raw, level_raw, type_raw,
            audience_text, age_text, amount_min_raw, amount_max_raw, cofinancing_text,
            window_text, status_text, is_permanent_intake_raw, submission_channel_raw,
            key_conditions_text, stop_factors_text, source_url, verified_label, note_text,
            snapshot_date
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    return len(rows)
