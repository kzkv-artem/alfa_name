from __future__ import annotations

import csv
import random
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from alfa_agent.acquisition.reference import (
    INDUSTRIES,
    REGIONS,
    Industry,
    Region,
    get_industry,
    get_region,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "market_signals.csv"

SNAPSHOT_DATE = "2026-07-01"
DEFAULT_SEED = 2026

CSV_DELIMITER = ";"
CSV_ENCODING = "utf-8-sig"
CSV_DECIMAL = ","


@dataclass(frozen=True)
class MarketSignal:
    industry_code: str
    industry_name: str
    region_code: str
    region_name: str
    population_k: int

    ip_count: int
    ip_growth_yoy_pct: float
    avg_monthly_revenue_rub: int
    revenue_p25_rub: int
    revenue_p90_rub: int
    closure_rate_12m_pct: float
    entry_ease_index: int
    seasonality_index: float

    snapshot_date: str = SNAPSHOT_DATE

    @property
    def revenue_gap_ratio(self) -> float:
        return round(self.revenue_p90_rub / max(self.revenue_p25_rub, 1), 2)


def _jitter(rnd: random.Random, spread: float) -> float:
    return 1.0 + rnd.uniform(-spread, spread)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _build_signal(industry: Industry, region: Region, rnd: random.Random) -> MarketSignal:

    expected_density = industry.density_per_100k * region.business_activity
    actual_density = expected_density * _jitter(rnd, 0.18)
    ip_count = max(12, round(region.population_k / 100 * actual_density))

    crowding = actual_density / industry.density_per_100k - 1.0

    growth = (
        industry.growth_yoy_pct
        + region.growth_delta_pct
        + rnd.uniform(-2.5, 2.5)
    )
    growth = _clamp(growth, -15.0, 35.0)

    avg_revenue = industry.avg_revenue_rub * region.purchasing_power * _jitter(rnd, 0.12)
    avg_revenue = round(avg_revenue / 1_000) * 1_000

    p25 = avg_revenue * (1.0 - 0.60 * industry.revenue_spread) * _jitter(rnd, 0.05)
    p90 = avg_revenue * (1.0 + 1.55 * industry.revenue_spread) * _jitter(rnd, 0.07)

    closure = (
        industry.closure_rate_pct
        + crowding * 12.0
        - growth * 0.35
        + rnd.uniform(-1.8, 1.8)
    )
    closure = _clamp(closure, 4.0, 46.0)

    entry_ease = industry.entry_ease + region.admin_ease_delta + rnd.uniform(-4, 4)
    entry_ease = _clamp(entry_ease, 5, 98)

    seasonality = industry.seasonality + region.seasonality_delta + rnd.uniform(-0.03, 0.03)
    seasonality = _clamp(seasonality, 0.05, 0.92)

    return MarketSignal(
        industry_code=industry.code,
        industry_name=industry.name,
        region_code=region.code,
        region_name=region.name,
        population_k=region.population_k,
        ip_count=ip_count,
        ip_growth_yoy_pct=round(growth, 1),
        avg_monthly_revenue_rub=int(avg_revenue),
        revenue_p25_rub=round(p25 / 1_000) * 1_000,
        revenue_p90_rub=round(p90 / 1_000) * 1_000,
        closure_rate_12m_pct=round(closure, 1),
        entry_ease_index=round(entry_ease),
        seasonality_index=round(seasonality, 2),
    )


def generate(seed: int = DEFAULT_SEED) -> list[MarketSignal]:
    rnd = random.Random(seed)
    return [
        _build_signal(industry, region, rnd)
        for industry in INDUSTRIES
        for region in REGIONS
    ]


_FIELD_NAMES = [f.name for f in fields(MarketSignal)]
_INT_FIELDS = {
    "population_k", "ip_count", "avg_monthly_revenue_rub",
    "revenue_p25_rub", "revenue_p90_rub", "entry_ease_index",
}
_FLOAT_FIELDS = {"ip_growth_yoy_pct", "closure_rate_12m_pct", "seasonality_index"}


def _to_row(signal: MarketSignal) -> dict[str, str]:
    row = asdict(signal)
    for key in _FLOAT_FIELDS:
        row[key] = str(row[key]).replace(".", CSV_DECIMAL)
    return row


def _to_float(value: str) -> float:
    return float(value.strip().replace(CSV_DECIMAL, "."))


def save_csv(signals: list[MarketSignal], path: Path = CSV_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=CSV_ENCODING, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELD_NAMES, delimiter=CSV_DELIMITER)
        writer.writeheader()
        writer.writerows(_to_row(s) for s in signals)
    return path


def load_csv(path: Path = CSV_PATH) -> list[MarketSignal]:
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла {path}. Сгенерируйте его: "
            f"python -m alfa_agent.acquisition.market_signals"
        )
    with path.open(encoding=CSV_ENCODING, newline="") as f:
        rows = list(csv.DictReader(f, delimiter=CSV_DELIMITER))

    signals = []
    for row in rows:
        typed = {
            key: int(value) if key in _INT_FIELDS
            else _to_float(value) if key in _FLOAT_FIELDS
            else value
            for key, value in row.items()
        }
        signals.append(MarketSignal(**typed))
    return signals


_cache: dict[tuple[str, str], MarketSignal] | None = None


def _index() -> dict[tuple[str, str], MarketSignal]:
    global _cache
    if _cache is None:
        _cache = {(s.industry_code, s.region_code): s for s in load_csv()}
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None


def find(industry_code: str, region_code: str) -> MarketSignal:
    get_industry(industry_code)
    get_region(region_code)
    try:
        return _index()[(industry_code, region_code)]
    except KeyError as exc:
        raise KeyError(
            f"В таблице нет пары {industry_code}×{region_code}. "
            f"Возможно, данные устарели — перегенерируйте их."
        ) from exc


def rows_for_industry(industry_code: str) -> list[MarketSignal]:
    get_industry(industry_code)
    return [s for s in _index().values() if s.industry_code == industry_code]


def rows_for_region(region_code: str) -> list[MarketSignal]:
    get_region(region_code)
    return [s for s in _index().values() if s.region_code == region_code]


def main() -> None:
    signals = generate()
    path = save_csv(signals)
    print(f"Готово: {len(signals)} строк -> {path}")
    print(f"Отраслей: {len(INDUSTRIES)}, регионов: {len(REGIONS)}\n")

    print("Пример — кафе в трёх регионах:")
    reset_cache()
    for region_code in ("msk", "spb", "primorye"):
        s = find("cafe", region_code)
        print(
            f"  {s.region_name:<24} ИП: {s.ip_count:>5}   "
            f"выручка: {s.avg_monthly_revenue_rub:>9,} ₽   "
            f"закрытий: {s.closure_rate_12m_pct:>4}%".replace(",", " ")
        )


if __name__ == "__main__":
    main()
