from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from dataclasses import asdict, fields
from datetime import date, timedelta
from pathlib import Path

from alfa_agent.insurance.features import ClientFeatures, features_from_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
FEATURES_CSV_PATH = DATA_DIR / "insurance_features.csv"
LABELS_CSV_PATH = DATA_DIR / "insurance_labels.csv"

DEFAULT_N = 400
DEFAULT_SEED = 20260805
END_DATE = date(2026, 7, 31)
START_DATE = END_DATE - timedelta(days=364)

ARCHETYPES = (
    ("beauty_home_selfemp", 0.14, "самозанятый", "beauty"),
    ("beauty_studio_ip", 0.18, "ИП", "beauty"),
    ("beauty_salon_ooo", 0.14, "ООО", "beauty"),
    ("creative_freelance_se", 0.14, "самозанятый", "creative"),
    ("creative_studio_ip", 0.16, "ИП", "creative"),
    ("creative_agency_ooo", 0.14, "ООО", "creative"),
    ("retail_small_ip", 0.10, "ИП", "retail"),
)

OKVED_BY_INDUSTRY = {"beauty": "96.02", "creative": "74.20", "retail": "47.19"}


def _pick_archetype(rnd: random.Random) -> tuple[str, float, str, str]:
    r = rnd.random()
    acc = 0.0
    for archetype in ARCHETYPES:
        acc += archetype[1]
        if r <= acc:
            return archetype
    return ARCHETYPES[-1]


def _month_index(d: date) -> int:
    return (d.year - START_DATE.year) * 12 + (d.month - START_DATE.month) + 1


def _make_latent(client_id: int, rnd: random.Random) -> dict:
    code, _, legal_form, industry = _pick_archetype(rnd)
    L = {
        "client_id": client_id, "archetype": code, "legal_form": legal_form,
        "industry": industry, "okved": OKVED_BY_INDUSTRY[industry],
    }

    L["business_age_months"] = rnd.randint(4, 96)

    if code in ("beauty_home_selfemp", "creative_freelance_se"):
        L["has_premises"] = False
        L["rent_amount"] = 0
    elif code == "creative_studio_ip":
        L["has_premises"] = rnd.random() < 0.75
        L["rent_amount"] = rnd.choice([35_000, 50_000, 70_000, 95_000]) if L["has_premises"] else 0
    else:
        L["has_premises"] = rnd.random() < 0.92
        L["rent_amount"] = rnd.choice([45_000, 60_000, 80_000, 110_000, 150_000]) if L["has_premises"] else 0

    if legal_form == "самозанятый":
        L["headcount"] = 0
    elif code in ("beauty_studio_ip", "creative_studio_ip", "retail_small_ip"):
        L["headcount"] = rnd.randint(0, 3)
    else:
        L["headcount"] = rnd.randint(3, 12)
    L["salary_per_head"] = rnd.choice([45_000, 55_000, 65_000, 80_000])

    if industry == "beauty":
        val = rnd.choice([0, 0, 250_000, 500_000, 900_000, 1_400_000])
    elif industry == "creative":
        val = rnd.choice([0, 180_000, 350_000, 700_000, 1_100_000])
    else:
        val = rnd.choice([0, 200_000, 400_000])
    personal = legal_form == "самозанятый" or (code == "creative_studio_ip" and rnd.random() < 0.45)
    L["equipment_value_company"] = 0 if personal else val
    L["equipment_value_personal"] = val if personal else 0
    L["equipment_purchase_month"] = rnd.randint(1, 12) if val else None

    base_flow = {"beauty": 12, "creative": 2, "retail": 30}[industry]
    if not L["has_premises"]:
        base_flow = max(1, base_flow // 3)
    L["clients_per_day"] = max(1, int(rnd.gauss(base_flow, base_flow * 0.3)))

    L["it_spend_monthly"] = {
        "beauty": rnd.choice([0, 0, 2_000, 4_500]),
        "creative": rnd.choice([3_000, 8_000, 15_000, 25_000]),
        "retail": rnd.choice([0, 5_000, 12_000]),
    }[industry]
    L["online_share"] = {
        "beauty": rnd.uniform(0.0, 0.15),
        "creative": rnd.uniform(0.3, 0.95),
        "retail": rnd.uniform(0.1, 0.7),
    }[industry]

    avg_check = {
        "beauty": rnd.choice([2500, 3500, 5000]),
        "creative": rnd.choice([40_000, 80_000, 150_000]),
        "retail": rnd.choice([900, 1500, 2500]),
    }[industry]
    L["avg_check"] = avg_check
    L["monthly_revenue"] = int(avg_check * L["clients_per_day"] * (22 if industry != "creative" else 3.5))

    L["seasonality_amp"] = rnd.uniform(0.05, 0.55)
    L["low_month"] = rnd.choice([1, 1, 2, 7, 8])
    L["client_concentration"] = (
        rnd.uniform(0.35, 0.85) if industry == "creative" else rnd.uniform(0.02, 0.12)
    )
    L["cash_share"] = rnd.uniform(0.0, 0.35) if industry != "creative" else 0.0

    L["has_policy"] = rnd.random() < 0.18
    L["policy_month"] = rnd.randint(1, 12) if L["has_policy"] else None

    L["history_months"] = 12 if rnd.random() > 0.12 else rnd.randint(2, 5)
    return L


def _gen_transactions(L: dict, rnd: random.Random) -> list[list]:
    rows = []
    cid = L["client_id"]
    first_month = 12 - L["history_months"] + 1

    d = START_DATE
    while d <= END_DATE:
        mi = _month_index(d)
        if mi < first_month:
            d += timedelta(days=1)
            continue

        season = 1.0 - L["seasonality_amp"] * (1.0 if d.month == L["low_month"] else 0.0)
        season *= rnd.uniform(0.9, 1.1)

        if d.weekday() < 6 or L["industry"] == "retail":
            visits = max(0, int(rnd.gauss(L["clients_per_day"] * season, L["clients_per_day"] * 0.35)))
            card_visits = int(visits * (1 - L["cash_share"]))
            if card_visits > 0:
                amt = card_visits * L["avg_check"] * rnd.uniform(0.85, 1.15)
                online = L["online_share"]
                if online > 0.01:
                    rows.append([cid, d, "in", "acquiring_online",
                                 round(amt * online, 2), int(card_visits * online)])
                if online < 0.99:
                    rows.append([cid, d, "in", "acquiring_offline",
                                 round(amt * (1 - online), 2), int(card_visits * (1 - online))])

        if L["rent_amount"] and d.day == min(28, 3 + (cid % 7) + rnd.randint(-1, 2)):
            rows.append([cid, d, "out", "rent", L["rent_amount"], 1])

        if L["headcount"] and d.day in (10, 25):
            rows.append([cid, d, "out", "payroll", round(L["headcount"] * L["salary_per_head"] / 2), L["headcount"]])
            rows.append([cid, d, "out", "taxes", round(L["headcount"] * L["salary_per_head"] / 2 * 0.43), 1])

        if d.day == 15 and L["it_spend_monthly"]:
            rows.append([cid, d, "out", "it_services", round(L["it_spend_monthly"] * rnd.uniform(0.8, 1.2)), 1])

        if d.day in (5, 20):
            supplies = L["monthly_revenue"] * rnd.uniform(0.10, 0.28) / 2
            rows.append([cid, d, "out", "supplies", round(supplies), 1])

        if L["equipment_purchase_month"] and mi == L["equipment_purchase_month"] and d.day == 12:
            val = L["equipment_value_company"] or L["equipment_value_personal"]
            rows.append([cid, d, "out", "equipment", val, 1])

        if L["policy_month"] and mi == L["policy_month"] and d.day == 8:
            rows.append([cid, d, "out", "insurance", rnd.choice([4_000, 9_000, 18_000]), 1])

        if d.day == 28:
            fixed = (L["rent_amount"] + L["headcount"] * L["salary_per_head"] * 1.43
                     + L["monthly_revenue"] * 0.19 + L["it_spend_monthly"])
            surplus = max(0.0, L["monthly_revenue"] * season - fixed)
            take = surplus * rnd.uniform(0.40, 0.85)
            rows.append([cid, d, "out", "drawings", round(take), 1])

        if rnd.random() < 0.004:
            rows.append([cid, d, "out", "other", round(L["monthly_revenue"] * rnd.uniform(0.05, 0.2)), 1])

        d += timedelta(days=1)
    return rows


def _volatility(rows: list[list]) -> float:
    m: dict = defaultdict(float)
    for _, d, direction, _cat, amt, _n in rows:
        if direction == "in":
            m[(d.year, d.month)] += amt
    values = list(m.values())
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))
    return sd / mean if mean else 0.0


def _build_feature_row(L: dict, rows: list[list]) -> dict:
    by_cat: dict = defaultdict(float)
    cnt_cat: dict = defaultdict(int)
    days_with_offline: dict = defaultdict(int)
    offline_txn = 0
    rent_months, ins_dates, eq_dates = set(), [], []
    daily: dict = defaultdict(float)

    for _, d, direction, cat, amt, n in rows:
        by_cat[cat] += amt
        cnt_cat[cat] += 1
        daily[d] += amt if direction == "in" else -amt
        if cat == "acquiring_offline":
            days_with_offline[d] += 1
            offline_txn += n
        if cat == "rent":
            rent_months.add((d.year, d.month))
        if cat == "insurance":
            ins_dates.append(d)
        if cat == "equipment":
            eq_dates.append(d)

    months = max(1, L["history_months"])
    revenue = by_cat["acquiring_online"] + by_cat["acquiring_offline"]
    expenses = sum(v for k, v in by_cat.items() if k not in ("acquiring_online", "acquiring_offline"))

    bal, series = 0.0, []
    d = START_DATE
    while d <= END_DATE:
        bal += daily.get(d, 0.0)
        series.append(bal)
        d += timedelta(days=1)

    peak, cur, gaps = 0.0, 0, []
    for b in series:
        peak = max(peak, b)
        if b < peak * 0.05:
            cur += 1
        elif cur:
            gaps.append(cur)
            cur = 0
    if cur:
        gaps.append(cur)

    monthly_rev = revenue / months if months else 0
    active_days = max(1, len(days_with_offline))

    return {
        "client_id": L["client_id"],
        "legal_form": L["legal_form"],
        "okved": L["okved"],
        "business_age_months": L["business_age_months"],
        "history_months": months,
        "has_rent": int(len(rent_months) >= 3),
        "rent_amount_avg": round(by_cat["rent"] / max(1, len(rent_months))),
        "equipment_spend_12m": round(by_cat["equipment"]),
        "equipment_spend_share": round(by_cat["equipment"] / max(1, expenses), 3),
        "months_since_equipment": (round((END_DATE - max(eq_dates)).days / 30) if eq_dates else ""),
        "headcount": (max(n for _, _, _, c, _, n in rows if c == "payroll") if cnt_cat["payroll"] else 0),
        "payroll_monthly": round(by_cat["payroll"] / months),
        "offline_txn_per_day": round(offline_txn / active_days, 1),
        "avg_ticket": round(by_cat["acquiring_offline"] / max(1, offline_txn)),
        "online_acquiring_share": round(by_cat["acquiring_online"] / max(1.0, revenue), 3),
        "it_spend_monthly": round(by_cat["it_services"] / months),
        "has_insurance_payments": int(bool(ins_dates)),
        "months_since_insurance": (round((END_DATE - max(ins_dates)).days / 30) if ins_dates else ""),
        "monthly_revenue": round(monthly_rev),
        "fixed_cost_ratio": round((by_cat["rent"] + by_cat["payroll"]) / max(1.0, revenue), 3),
        "revenue_volatility": round(_volatility(rows), 3),
        "gap_frequency_6m": len([g for g in gaps if g >= 3]),
        "gap_max_days": max(gaps) if gaps else 0,
        "cash_buffer_days": round(max(0.0, series[-1]) / max(1.0, expenses / max(1, months * 30)), 1),
    }


def _true_labels(L: dict) -> tuple[str, ...]:
    if L["legal_form"] == "самозанятый":
        return ()
    P = []
    if L["has_premises"]:
        P.append("TENANT")
    if L["has_premises"] or L["equipment_value_company"] >= 200_000:
        P.append("PROP_MSB")
    if L["equipment_value_company"] >= 300_000:
        P.append("EQUIP")
    if L["has_premises"] and L["clients_per_day"] >= 8:
        P.append("GL")
    if L["industry"] == "beauty" and L["clients_per_day"] >= 5:
        P.append("PRODQ")
    if L["legal_form"] == "ООО" and L["headcount"] >= 3:
        P.append("DMS")
    if L["it_spend_monthly"] >= 3_000 or L["online_share"] >= 0.30:
        P.append("CYBER")
    return tuple(P)


def generate(n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> tuple[list[ClientFeatures], dict[str, tuple[str, ...]]]:
    rnd = random.Random(seed)
    features: list[ClientFeatures] = []
    labels: dict[str, tuple[str, ...]] = {}

    for cid in range(1, n + 1):
        latent = _make_latent(cid, rnd)
        tx_rows = _gen_transactions(latent, rnd)
        row = _build_feature_row(latent, tx_rows)
        features.append(features_from_row(row))
        labels[str(cid)] = _true_labels(latent)

    return features, labels


_FIELD_NAMES = [f.name for f in fields(ClientFeatures)]
_BOOL_FIELDS = {"has_rent", "has_insurance_payments"}


def _to_row(feat: ClientFeatures) -> dict:
    row = asdict(feat)
    for key in _BOOL_FIELDS:
        row[key] = int(row[key])
    for key, value in row.items():
        if value is None:
            row[key] = ""
    return row


def save_features_csv(features: list[ClientFeatures], path: Path = FEATURES_CSV_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELD_NAMES)
        writer.writeheader()
        writer.writerows(_to_row(feat) for feat in features)
    return path


def save_labels_csv(labels: dict[str, tuple[str, ...]], path: Path = LABELS_CSV_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["client_id", "applicable"])
        for client_id, codes in labels.items():
            writer.writerow([client_id, "|".join(codes)])
    return path


def load_features_csv(path: Path = FEATURES_CSV_PATH) -> list[ClientFeatures]:
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла {path}. Сгенерируйте его: python -m alfa_agent.insurance.synthetic"
        )
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [features_from_row(row) for row in rows]


def main() -> None:
    features, labels = generate()
    features_path = save_features_csv(features)
    labels_path = save_labels_csv(labels)
    empty = sum(1 for codes in labels.values() if not codes)
    print(f"клиентов: {len(features)} -> {features_path}")
    print(f"эталонные метки -> {labels_path}")
    print(f"без применимых продуктов: {empty} ({empty / len(features):.0%})")


if __name__ == "__main__":
    main()
