from __future__ import annotations

from dataclasses import dataclass

from alfa_agent.insurance.catalog import InsuranceProduct, get_product
from alfa_agent.insurance.features import ClientFeatures

THRESHOLD = 0.25
TOP_N = 3


def eligible(f: ClientFeatures) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}

    if f.legal_form == "самозанятый":
        return out

    beauty = f.okved.startswith("96.")

    if f.has_rent:
        out["TENANT"] = ["HAS_RENT"]

    if f.has_rent or f.equipment_spend_12m >= 200_000:
        codes = []
        if f.has_rent:
            codes.append("HAS_PREMISES")
        if f.equipment_spend_12m >= 200_000:
            codes.append("OWNS_EQUIPMENT")
        out["PROP_MSB"] = codes

    if f.equipment_spend_12m >= 300_000:
        codes = ["HIGH_EQUIPMENT_SPEND"]
        if f.equipment_spend_share >= 0.25:
            codes.append("EQUIPMENT_HEAVY")
        months_since = f.months_since_equipment if f.months_since_equipment is not None else 99
        if months_since <= 3:
            codes.append("RECENT_PURCHASE")
        out["EQUIP"] = codes

    if f.has_rent and f.offline_txn_per_day >= 8:
        out["GL"] = ["HAS_PREMISES", "FOOT_TRAFFIC"]

    if beauty and f.offline_txn_per_day >= 5:
        out["PRODQ"] = ["SERVICE_ON_CLIENT", "FOOT_TRAFFIC"]

    if f.legal_form == "ООО" and f.headcount >= 3:
        out["DMS"] = ["HAS_STAFF"]

    if f.it_spend_monthly >= 3_000 or f.online_acquiring_share >= 0.30:
        codes = []
        if f.it_spend_monthly >= 3_000:
            codes.append("IT_SPEND")
        if f.online_acquiring_share >= 0.30:
            codes.append("ONLINE_REVENUE")
        out["CYBER"] = codes

    return out


def risk_exposure(product_code: str, f: ClientFeatures) -> float:
    revenue = max(1.0, f.monthly_revenue)
    if product_code == "TENANT":
        return min(1.0, 0.45 + f.rent_amount_avg / revenue * 1.5)
    if product_code == "PROP_MSB":
        return min(1.0, 0.35 + f.equipment_spend_share * 1.2)
    if product_code == "EQUIP":
        return min(1.0, 0.30 + f.equipment_spend_12m / (revenue * 6))
    if product_code == "GL":
        return min(1.0, 0.25 + f.offline_txn_per_day / 40)
    if product_code == "PRODQ":
        return min(1.0, 0.40 + f.offline_txn_per_day / 30)
    if product_code == "DMS":
        return min(1.0, 0.20 + f.headcount / 15)
    if product_code == "CYBER":
        return min(1.0, 0.25 + f.online_acquiring_share * 0.6)
    return 0.3


def vulnerability(f: ClientFeatures) -> float:
    v = 0.5
    if f.cash_buffer_days < 7:
        v += 0.30
    elif f.cash_buffer_days < 21:
        v += 0.15
    v += min(0.25, f.fixed_cost_ratio * 0.5)
    v += min(0.20, f.gap_frequency_6m * 0.07)
    return min(1.35, v)


def urgency(f: ClientFeatures) -> str:
    if f.cash_buffer_days < 7 or f.gap_frequency_6m >= 2:
        return "high"
    return "normal"


def coverage_config(f: ClientFeatures) -> str:
    if f.cash_buffer_days < 21 or f.gap_frequency_6m >= 1:
        return "высокая франшиза + рассрочка"
    return "стандартное покрытие"


@dataclass(frozen=True)
class InsuranceRecommendation:

    product: InsuranceProduct
    need_score: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class InsuranceAssessment:

    features: ClientFeatures
    recommendations: tuple[InsuranceRecommendation, ...]
    urgency: str
    coverage_config: str
    no_offer_reason: str | None


def recommend(f: ClientFeatures) -> InsuranceAssessment:
    el = eligible(f)

    if not el:
        reason = (
            "самозанятый: корпоративные продукты недоступны"
            if f.legal_form == "самозанятый"
            else "нет применимых продуктов"
        )
        return InsuranceAssessment(
            features=f, recommendations=(), urgency="normal",
            coverage_config="", no_offer_reason=reason,
        )

    insured = f.has_insurance_payments
    since = f.months_since_insurance if f.months_since_insurance is not None else 99

    v = vulnerability(f)
    scored = []
    for code, codes in el.items():
        score = risk_exposure(code, f) * v
        if insured and since < 10:
            score *= 0.35
            codes = codes + ["ALREADY_INSURED"]
        elif insured and since >= 10:
            codes = codes + ["RENEWAL_WINDOW"]
            score *= 1.2
        if score >= THRESHOLD:
            scored.append((code, round(min(score, 1.0), 3), codes))

    scored.sort(key=lambda x: -x[1])
    top = scored[:TOP_N]

    if not top:
        return InsuranceAssessment(
            features=f, recommendations=(), urgency="normal",
            coverage_config="", no_offer_reason="ни один продукт не набрал порог нужды",
        )

    recommendations = tuple(
        InsuranceRecommendation(
            product=get_product(code), need_score=score, reason_codes=tuple(codes),
        )
        for code, score, codes in top
    )

    return InsuranceAssessment(
        features=f, recommendations=recommendations,
        urgency=urgency(f), coverage_config=coverage_config(f), no_offer_reason=None,
    )
