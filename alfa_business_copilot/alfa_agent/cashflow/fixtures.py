from __future__ import annotations

import sqlite3
from datetime import date, timedelta


def seed_demo_client(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO client VALUES (?, ?, ?, ?, ?)",
        ("client_1", "Дарья Соколова", "2002-04-12", "HoReCa", "2026-03-15"),
    )
    conn.execute(
        "INSERT OR REPLACE INTO account VALUES (?, ?, ?, ?)",
        ("account_1", "client_1", "2026-03-15", 18000),
    )
    conn.commit()


def _days_ago(n: int) -> str:
    """Дата в формате ДД.ММ.ГГГГ — как хранятся даты в payment_transaction."""
    return (date.today() - timedelta(days=n)).strftime("%d.%m.%Y")


def _days_ago_iso(n: int) -> str:
    """Дата в ISO — как хранятся client.registration_date / account.opening_date."""
    return (date.today() - timedelta(days=n)).isoformat()


def seed_demo_alert_client(conn: sqlite3.Connection) -> None:
    """Второй демо-клиент, специально сконструированный так, чтобы прогноз
    гарантированно поймал разрыв (client_1 из seed_demo_client() его никогда
    не покажет — три его повторяющихся платежа привязаны к статичным датам
    из otbor/alfa.csv и с течением времени неизбежно уезжают в прошлое
    относительно date.today(), выпадая из 21-дневного окна прогноза).
    Даты здесь считаются от date.today() при каждом запуске — три
    повторяющихся списания стабильно проецируются на ближайшие 5-19 дней,
    независимо от того, в какой день идёт демонстрация."""
    conn.execute(
        "INSERT OR REPLACE INTO client VALUES (?, ?, ?, ?, ?)",
        ("client_2", "ИП Сергей Волков", "1990-02-20", "Retail", _days_ago_iso(600)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO account VALUES (?, ?, ?, ?)",
        ("account_2", "client_2", _days_ago_iso(580), 5000),
    )

    rows = []

    def add(days_ago: int, amount: float, direction: str, counterparty: str, category_id: int) -> None:
        rows.append((
            f"tx2_{len(rows) + 1}", "account_2", category_id, _days_ago(days_ago),
            amount, direction, counterparty, "transfer",
        ))

    # 3 регулярных списания ~раз в 30 дней — суммарно ~107к/мес, надёжно
    # проверено против реальной обученной модели (confidence 0.996, gap ~-33.5к).
    for i, days_ago in enumerate([25, 55, 85, 115]):
        add(days_ago, 50000 + i * 100, "outbound", "OOO Romashka (rent)", 1)
    for i, days_ago in enumerate([20, 50, 80, 110]):
        add(days_ago, 35000 + i * 50, "outbound", "salary", 3)
    for i, days_ago in enumerate([18, 48, 78, 108]):
        add(days_ago, 22000 - i * 80, "outbound", "OOO Snab", 2)

    # скромный ежедневный приход за последние 35 дней
    for days_ago in range(35):
        add(days_ago, 2200 + (days_ago % 5) * 60, "inbound", "acquiring", 4)

    conn.executemany(
        "INSERT INTO payment_transaction VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
