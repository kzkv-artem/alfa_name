from __future__ import annotations

import re
import sqlite3

LEVEL_MAP = {"федеральный": "federal", "региональный": "regional", "федерально-региональный": "mixed"}
TYPE_MAP = {
    "грант": "grant", "субсидия": "subsidy", "льготный кредит": "credit",
    "льготный заём": "credit", "гарантия": "guarantee", "лизинг": "leasing",
    "нефинансовая": "nonfinancial",
}
AGE_RANGE_RE = re.compile(r"(\d{1,2})\s*[–\-]\s*(\d{1,2})\s*лет")
AGE_FROM_RE = re.compile(r"с\s*(\d{1,2})\s*лет")


def parse_age(age_text: str | None) -> tuple[int | None, int | None, str]:
    if not age_text:
        return None, None, "unparsed"
    text = age_text.strip().lower()
    if text.startswith("без ограничения"):
        return None, None, "parsed"
    m = AGE_RANGE_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2)), "parsed"
    m = AGE_FROM_RE.search(text)
    if m:
        return int(m.group(1)), None, "parsed"
    return None, None, "unparsed"


def parse_is_open(status_text: str | None) -> int:
    if not status_text:
        return 0
    text = status_text.lower()
    if "закрыт" in text and "не закрыт" not in text:
        return 0
    if "открыт" in text or "действует" in text:
        return 1
    return 0


def parse_cofinancing(text: str | None) -> int:
    return 0 if not text or text.strip().lower() == "нет" else 1


def parse_submission_channel(text: str | None) -> str:
    if not text:
        return "other"
    t = text.lower()
    if "банк" in t:
        return "bank"
    if "госуслуги" in t:
        return "gosuslugi"
    if "фонд-м" in t or "fasie" in t or "мсп.рф" in t:
        return "fund_platform"
    if "мой бизнес" in t or "мфц" in t or "минсельхоз" in t or "региональный орган" in t:
        return "regional_office"
    return "other"


def normalize_programs(conn: sqlite3.Connection) -> int:
    raw_rows = conn.execute("SELECT * FROM raw_program_source").fetchall()
    for r in raw_rows:
        age_min, age_max, age_conf = parse_age(r["age_text"])
        conn.execute(
            """INSERT INTO support_program (
                raw_source_id, name, organizer, level, type, amount_min, amount_max,
                cofinancing_required, age_min, age_max, age_parse_confidence,
                is_open, status_checked_at, submission_channel, stop_factors_text,
                notes_text, last_verified_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["source_row_id"], r["name_raw"], r["organizer_raw"],
                LEVEL_MAP.get(r["level_raw"], "federal"), TYPE_MAP.get(r["type_raw"], "grant"),
                r["amount_min_raw"], r["amount_max_raw"], parse_cofinancing(r["cofinancing_text"]),
                age_min, age_max, age_conf,
                parse_is_open(r["status_text"]), r["snapshot_date"],
                parse_submission_channel(r["submission_channel_raw"]),
                r["stop_factors_text"], r["note_text"], r["snapshot_date"],
            ),
        )
    conn.commit()
    return len(raw_rows)
