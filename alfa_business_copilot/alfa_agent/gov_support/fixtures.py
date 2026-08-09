from __future__ import annotations

import sqlite3
from datetime import date, timedelta

DOCUMENT_TYPES = [
    "бизнес-план", "документ на помещение (аренда/собственность)",
    "справка об отсутствии задолженности", "выписка по счёту",
    "заявление по установленной форме", "финансовая отчётность",
]
REQUIRED_DOCS_BY_PROGRAM = {
    "agro-bakery": [
        "бизнес-план", "документ на помещение (аренда/собственность)",
        "справка об отсутствии задолженности", "выписка по счёту",
    ],
    "program-1764": [
        "заявление по установленной форме", "финансовая отчётность",
        "выписка по счёту", "справка об отсутствии задолженности",
    ],
    # Ниже — две программы из пяти, что проходят отраслевой фильтр для Алины
    # (otbor/mery-podderzhki-msp-2026.csv, колонки Ключевые_условия/Канал_подачи/
    # Стоп-факторы, без домысливания):
    # - social-contract: "защита бизнес-плана" в Ключевые_условия -> бизнес-план;
    #   канал — Госуслуги/соцзащита/МФЦ, формальная заявка в орган соцзащиты ->
    #   заявление по установленной форме.
    # - region-microloan: канал — региональная МФО, заём оформляется заявкой ->
    #   заявление по установленной форме; стоп-фактор "налоговая задолженность"
    #   подразумевает проверку -> справка об отсутствии задолженности.
    # Остальные три (umbrella-guarantee, my-business-centers, msp-platform)
    # оставлены без документов: текст явно говорит либо что заявка отдельно не
    # подаётся (umbrella-guarantee — "оформляется банком"), либо что документов
    # от клиента не требуется (msp-platform — "профиль подтягивается из
    # госреестров автоматически"; my-business-centers — бесплатная консультация).
    "social-contract": [
        "бизнес-план", "заявление по установленной форме",
    ],
    "region-microloan": [
        "заявление по установленной форме", "справка об отсутствии задолженности",
    ],
}
CLIENT_HAS_DOCS = ["выписка по счёту", "справка об отсутствии задолженности"]


def seed_demo_data(conn: sqlite3.Connection) -> tuple[int, dict[str, int]]:
    doc_type_ids = {}
    for name in DOCUMENT_TYPES:
        cur = conn.execute("INSERT INTO document_type (name) VALUES (?)", (name,))
        doc_type_ids[name] = cur.lastrowid

    for external_id, doc_names in REQUIRED_DOCS_BY_PROGRAM.items():
        row = conn.execute(
            """SELECT sp.program_id FROM support_program sp
               JOIN raw_program_source rps ON rps.source_row_id = sp.raw_source_id
               WHERE rps.external_id = ?""",
            (external_id,),
        ).fetchone()
        if row:
            for doc_name in doc_names:
                conn.execute(
                    "INSERT INTO required_document (program_id, document_type_id) VALUES (?,?)",
                    (row["program_id"], doc_type_ids[doc_name]),
                )

    cur = conn.execute(
        """INSERT INTO client (full_name, birth_date, entity_type, industry_code,
                                business_registered_at, region_code)
           VALUES (?,?,?,?,?,?)""",
        ("Дарья Кузнецова", "2001-05-14", "ИП", "производство хлебобулочных изделий",
         "2024-03-01", "Ленинградская область"),
    )
    client_id = cur.lastrowid
    for doc_name in CLIENT_HAS_DOCS:
        conn.execute(
            "INSERT INTO client_document (client_id, document_type_id, status) VALUES (?,?,'verified')",
            (client_id, doc_type_ids[doc_name]),
        )
    conn.commit()
    return client_id, doc_type_ids


# Тот же персонаж, что заведён в cashflow (seed_demo_beauty_client) и insurance
# (demo_beauty_client_features) — ИП, студия маникюра, 2 года работы, Казань.
# Комплект документов у неё беднее, чем у Дарьи, — только выписка по счёту,
# специально, чтобы показать другую ветку decide() (request_documents, а не
# сразу propose_draft) там, где документов не хватает больше двух.
CLIENT_HAS_DOCS_BEAUTY = ["выписка по счёту"]


def seed_demo_beauty_client(conn: sqlite3.Connection, doc_type_ids: dict[str, int]) -> int:
    cur = conn.execute(
        """INSERT INTO client (full_name, birth_date, entity_type, industry_code,
                                business_registered_at, region_code)
           VALUES (?,?,?,?,?,?)""",
        ("Алина Гарифуллина", "1997-06-15", "ИП", "услуги маникюра и педикюра",
         (date.today() - timedelta(days=730)).isoformat(), "Республика Татарстан"),
    )
    client_id = cur.lastrowid
    for doc_name in CLIENT_HAS_DOCS_BEAUTY:
        conn.execute(
            "INSERT INTO client_document (client_id, document_type_id, status) VALUES (?,?,'verified')",
            (client_id, doc_type_ids[doc_name]),
        )
    conn.commit()
    return client_id
