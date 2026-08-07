from __future__ import annotations

from dataclasses import dataclass, field

from alfa_agent.acquisition.market_signals import MarketSignal, find
from alfa_agent.acquisition.reference import Industry, Region, get_industry, get_region

WEIGHTS = {
    "survival": 30,
    "competition": 20,
    "market_trend": 15,
    "entry_cost": 15,
    "income_spread": 10,
    "seasonality": 10,
}

BUDGET_WEIGHT = 20
LEVEL_THRESHOLDS = ((30, "низкий"), (50, "умеренный"), (70, "высокий"))

def normalize(value: float, best: float, worst: float) -> float:

    if best == worst:
        return 0.0
    share = (value - best) / (worst - best)
    return round(max(0.0, min(1.0, share)) * 100, 1)

ANCHORS = {
    "survival":      (8.0, 36.0),
    "competition":   (0.75, 1.45),
    "market_trend":  (20.0, -5.0),
    "entry_cost":    (90.0, 25.0),
    "income_spread": (1.5, 5.0),
    "seasonality":   (0.10, 0.75),
    "budget":        (1.5, 0.4),
}

@dataclass(frozen=True)
class RiskFactor:

    code: str
    name: str
    raw_value: float
    display: str
    risk_points: float
    weight: int
    contribution: float
    comment: str


@dataclass(frozen=True)
class RiskAssessment:

    industry: Industry
    region: Region
    signal: MarketSignal
    score: float
    level: str
    factors: tuple[RiskFactor, ...]
    estimated_capital_rub: int
    budget_rub: int | None = None

    @property
    def top_risks(self) -> list[RiskFactor]:
        return [f for f in self.factors if f.risk_points >= 55][:3]

    @property
    def strengths(self) -> list[RiskFactor]:
        return [f for f in self.factors if f.risk_points <= 30]

def estimate_capital(signal: MarketSignal) -> int:

    months = 0.8 + (100 - signal.entry_ease_index) / 100 * 3.5
    capital = signal.avg_monthly_revenue_rub * months
    return int(round(capital / 50_000) * 50_000)

def _make_factor(
    code: str,
    name: str,
    raw_value: float,
    display: str,
    total_weight: int,
    comments: tuple[str, str, str],
    weight: int | None = None,
) -> RiskFactor:

    best, worst = ANCHORS[code]
    points = normalize(raw_value, best, worst)
    weight = WEIGHTS.get(code, BUDGET_WEIGHT) if weight is None else weight

    comment = comments[0] if points < 35 else comments[1] if points < 65 else comments[2]

    return RiskFactor(
        code=code,
        name=name,
        raw_value=raw_value,
        display=display,
        risk_points=points,
        weight=weight,
        contribution=round(points * weight / total_weight, 1),
        comment=comment,
    )

def assess(
    industry_code: str,
    region_code: str,
    budget_rub: int | None = None,
) -> RiskAssessment:

    industry = get_industry(industry_code)
    region = get_region(region_code)
    signal = find(industry_code, region_code)

    capital = estimate_capital(signal)
    total_weight = sum(WEIGHTS.values()) + (BUDGET_WEIGHT if budget_rub else 0)

    density = signal.ip_count / signal.population_k * 100
    density_ratio = density / industry.density_per_100k

    factors = [
        _make_factor(
            "survival", "Выживаемость",
            signal.closure_rate_12m_pct, f"{signal.closure_rate_12m_pct}% закрытий за год",
            total_weight,
            ("закрываются реже, чем в среднем по малому бизнесу",
             "закрывается примерно каждый пятый — обычная картина",
             "закрывается очень много, отрасль не прощает ошибок"),
        ),
        _make_factor(
            "competition", "Конкуренция",
            density_ratio, f"{signal.ip_count} ИП в регионе",
            total_weight,
            ("рынок свободнее обычного, место есть",
             "рынок занят примерно как везде",
             "рынок переполнен, придётся отбивать клиентов у существующих"),
        ),
        _make_factor(
            "market_trend", "Динамика рынка",
            signal.ip_growth_yoy_pct, f"{signal.ip_growth_yoy_pct:+}% за год",
            total_weight,
            ("рынок растёт, новых игроков ждут",
             "рынок стоит на месте",
             "число таких бизнесов сокращается — спрос уходит"),
        ),
        _make_factor(
            "entry_cost", "Порог входа",
            signal.entry_ease_index, f"около {capital:,} ₽ на старт".replace(",", " "),
            total_weight,
            ("начать можно почти без вложений",
             "нужны заметные вложения до первой выручки",
             "высокий порог: помещение, оборудование, разрешения"),
        ),
        _make_factor(
            "income_spread", "Расслоение доходов",
            signal.revenue_gap_ratio, f"сильные зарабатывают в {signal.revenue_gap_ratio} раза больше слабых",
            total_weight,
            ("зарабатывают примерно одинаково, результат предсказуем",
             "разброс заметный, многое решает исполнение",
             "рынок-лотерея: либо очень хорошо, либо никак"),
        ),
        _make_factor(
            "seasonality", "Сезонность",
            signal.seasonality_index, f"размах выручки по месяцам {signal.seasonality_index}",
            total_weight,
            ("выручка ровная весь год",
             "есть сезонные спады, их надо закладывать в план",
             "сильные сезонные провалы — почти гарантированные кассовые разрывы"),
        ),
    ]

    if budget_rub:
        ratio = budget_rub / capital
        factors.append(
            _make_factor(
                "budget", "Бюджет",
                ratio, f"{budget_rub:,} ₽ при оценке {capital:,} ₽".replace(",", " "),
                total_weight,
                ("бюджета хватает с запасом",
                 "бюджет впритык, подушки почти нет",
                 "бюджета не хватает, стартовать не на что"),
                weight=BUDGET_WEIGHT,
            )
        )

    factors.sort(key=lambda f: f.contribution, reverse=True)
    score = round(sum(f.contribution for f in factors), 1)

    level = "очень высокий"
    for threshold, label in LEVEL_THRESHOLDS:
        if score < threshold:
            level = label
            break

    return RiskAssessment(
        industry=industry, region=region, signal=signal,
        score=score, level=level, factors=tuple(factors),
        estimated_capital_rub=capital, budget_rub=budget_rub,
    )