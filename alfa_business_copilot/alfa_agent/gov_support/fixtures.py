from __future__ import annotations

import sqlite3

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
