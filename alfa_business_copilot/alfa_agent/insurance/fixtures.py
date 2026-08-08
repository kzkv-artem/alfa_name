from __future__ import annotations

from alfa_agent.insurance.features import ClientFeatures

# Тот же персонаж, что заведён в cashflow (seed_demo_beauty_client) и
# gov_support (seed_demo_beauty_client) — ИП, студия маникюра, 2 года работы,
# Казань. В отличие от 400 синтетических клиентов из insurance/synthetic.py,
# эти цифры не сгенерированы случайно, а подобраны вручную под ту же историю:
# студия с одной сотрудницей, недорогое оборудование, стабильный поток клиентов.
DEMO_BEAUTY_CLIENT_ID = "demo_beauty"


def demo_beauty_client_features() -> ClientFeatures:
    return ClientFeatures(
        client_id=DEMO_BEAUTY_CLIENT_ID,
        legal_form="ИП",
        okved="96.02",  # предоставление услуг парикмахерскими и салонами красоты
        business_age_months=24.0,
        history_months=12.0,
        has_rent=True,
        rent_amount_avg=32000.0,
        equipment_spend_12m=180000.0,
        equipment_spend_share=0.22,
        months_since_equipment=4.0,
        headcount=1.0,
        payroll_monthly=45000.0,
        offline_txn_per_day=6.0,
        avg_ticket=3500.0,
        online_acquiring_share=0.15,
        it_spend_monthly=2500.0,
        has_insurance_payments=False,
        months_since_insurance=None,
        monthly_revenue=430000.0,
        fixed_cost_ratio=0.32,
        revenue_volatility=0.28,
        gap_frequency_6m=0.0,
        gap_max_days=0.0,
        cash_buffer_days=25.0,
    )
