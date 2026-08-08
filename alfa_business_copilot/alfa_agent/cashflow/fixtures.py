from __future__ import annotations

import random
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


def seed_demo_beauty_client(conn: sqlite3.Connection) -> None:
    """Третий демо-клиент — ИП, студия маникюра, 2 года работы, Казань
    (тот же персонаж, что заведён в gov_support и insurance — см.
    alfa_agent/gov_support/fixtures.py::seed_demo_beauty_client и
    alfa_agent/insurance/fixtures.py::demo_beauty_client_features).

    Профиль сделан правдоподобным, а не подогнанным под вердикт: ежедневная
    выручка с реальным провалом в начале каждого календарного месяца (в эти
    дни у клиентов студии меньше свободных денег — типичный паттерн для
    бьюти-услуг), аренда и закупка материалов — крупные ежемесячные списания.

    Даты аренды/закупки считаются от date.today() при каждом запуске (как в
    seed_demo_alert_client), а не от фиксированного числа месяца: первая
    версия сида привязывала их к 5-му/8-му числу и в день, когда оба уже
    прошли в текущем месяце, оба платежа улетали за пределы 21-дневного окна
    прогноза — эффект зависел от того, какое сегодня число. days_ago-привязка
    устраняет эту зависимость: следующий ожидаемый платёж всегда попадает в
    окно прогноза независимо от даты запуска. Какой именно вердикт выдаст
    модель — не выбирается заранее; random.Random-seed фиксирован только ради
    воспроизводимости прогона, а не ради конкретного результата."""
    conn.execute(
        "INSERT OR REPLACE INTO client VALUES (?, ?, ?, ?, ?)",
        ("client_beauty", "Алина Гарифуллина", "1997-06-15", "Beauty", _days_ago_iso(730)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO account VALUES (?, ?, ?, ?)",
        ("account_beauty", "client_beauty", _days_ago_iso(700), 35000),
    )

    rows = []

    def add(days_ago: int, amount: float, direction: str, counterparty: str, category_id: int) -> None:
        rows.append((
            f"tx3_{len(rows) + 1}", "account_beauty", category_id, _days_ago(days_ago),
            amount, direction, counterparty, "transfer",
        ))

    rnd = random.Random(20260808)  # только для воспроизводимости, не для нужного исхода

    # Аренда студии — ~раз в 30 дней, последняя была 22 дня назад ->
    # next_expected_date патттерна = today+8, надёжно внутри 21-дневного окна.
    for i, days_ago in enumerate([22, 52, 82, 112]):
        add(days_ago, round(36000 * rnd.uniform(0.97, 1.03)), "outbound", "ИП Хозяин (аренда студии)", 1)
    # Закупка материалов — ~раз в 30 дней, последняя 15 дней назад ->
    # next_expected_date = today+15, тоже внутри окна.
    for i, days_ago in enumerate([15, 45, 75, 105]):
        add(days_ago, round(22000 * rnd.uniform(0.95, 1.05)), "outbound", "OOO Beauty-Snab", 2)

    # Ежедневная выручка за последние 65 дней: 1-5 число месяца — провал
    # (после аренды и закупок у клиентов меньше свободных денег на маникюр).
    for days_ago in range(65):
        d = date.today() - timedelta(days=days_ago)
        is_dip = d.day <= 5
        visits = rnd.randint(2, 3) if is_dip else rnd.randint(5, 8)
        avg_ticket = rnd.uniform(2600, 3400)
        add(days_ago, round(visits * avg_ticket, 2), "inbound", "acquiring", 4)

    conn.executemany(
        "INSERT INTO payment_transaction VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
