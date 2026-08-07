from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientFeatures:

    client_id: str
    legal_form: str
    okved: str
    business_age_months: float
    history_months: float
    has_rent: bool
    rent_amount_avg: float
    equipment_spend_12m: float
    equipment_spend_share: float
    months_since_equipment: float | None
    headcount: float
    payroll_monthly: float
    offline_txn_per_day: float
    avg_ticket: float
    online_acquiring_share: float
    it_spend_monthly: float
    has_insurance_payments: bool
    months_since_insurance: float | None
    monthly_revenue: float
    fixed_cost_ratio: float
    revenue_volatility: float
    gap_frequency_6m: float
    gap_max_days: float
    cash_buffer_days: float


def _num(row: dict, key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _opt_num(row: dict, key: str) -> float | None:
    value = row.get(key, "")
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def features_from_row(row: dict) -> ClientFeatures:
    return ClientFeatures(
        client_id=str(row.get("client_id", "")),
        legal_form=str(row.get("legal_form", "")),
        okved=str(row.get("okved", "")),
        business_age_months=_num(row, "business_age_months"),
        history_months=_num(row, "history_months", 12.0),
        has_rent=_num(row, "has_rent") == 1,
        rent_amount_avg=_num(row, "rent_amount_avg"),
        equipment_spend_12m=_num(row, "equipment_spend_12m"),
        equipment_spend_share=_num(row, "equipment_spend_share"),
        months_since_equipment=_opt_num(row, "months_since_equipment"),
        headcount=_num(row, "headcount"),
        payroll_monthly=_num(row, "payroll_monthly"),
        offline_txn_per_day=_num(row, "offline_txn_per_day"),
        avg_ticket=_num(row, "avg_ticket"),
        online_acquiring_share=_num(row, "online_acquiring_share"),
        it_spend_monthly=_num(row, "it_spend_monthly"),
        has_insurance_payments=_num(row, "has_insurance_payments") == 1,
        months_since_insurance=_opt_num(row, "months_since_insurance"),
        monthly_revenue=_num(row, "monthly_revenue"),
        fixed_cost_ratio=_num(row, "fixed_cost_ratio"),
        revenue_volatility=_num(row, "revenue_volatility"),
        gap_frequency_6m=_num(row, "gap_frequency_6m"),
        gap_max_days=_num(row, "gap_max_days"),
        cash_buffer_days=_num(row, "cash_buffer_days", 30.0),
    )
