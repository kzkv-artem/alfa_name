from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Industry:
    code: str
    name: str
    aliases: tuple[str, ...]
    density_per_100k: float
    growth_yoy_pct: float
    avg_revenue_rub: int
    revenue_spread: float
    closure_rate_pct: float
    entry_ease: int
    seasonality: float


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    aliases: tuple[str, ...]
    population_k: int
    purchasing_power: float
    business_activity: float
    growth_delta_pct: float
    admin_ease_delta: int
    seasonality_delta: float


INDUSTRIES: tuple[Industry, ...] = (
    Industry(
        code="cafe",
        name="Кафе и кофейни",
        aliases=("кафе", "кофейня", "кофе с собой", "общепит", "ресторан", "бар"),
        density_per_100k=18.0,
        growth_yoy_pct=6.0,
        avg_revenue_rub=850_000,
        revenue_spread=0.70,
        closure_rate_pct=22.0,
        entry_ease=45,
        seasonality=0.35,
    ),
    Industry(
        code="grocery",
        name="Продуктовый магазин у дома",
        aliases=("продуктовый", "магазин продуктов", "минимаркет", "продукты"),
        density_per_100k=26.0,
        growth_yoy_pct=-2.0,
        avg_revenue_rub=1_400_000,
        revenue_spread=0.35,
        closure_rate_pct=17.0,
        entry_ease=40,
        seasonality=0.12,
    ),
    Industry(
        code="beauty",
        name="Барбершоп и салон красоты",
        aliases=("барбершоп", "салон красоты", "парикмахерская", "маникюр", "бьюти"),
        density_per_100k=22.0,
        growth_yoy_pct=9.0,
        avg_revenue_rub=480_000,
        revenue_spread=0.55,
        closure_rate_pct=24.0,
        entry_ease=60,
        seasonality=0.20,
    ),
    Industry(
        code="bakery",
        name="Пекарня и кондитерская",
        aliases=("пекарня", "кондитерская", "выпечка", "булочная", "торты"),
        density_per_100k=9.0,
        growth_yoy_pct=7.0,
        avg_revenue_rub=620_000,
        revenue_spread=0.50,
        closure_rate_pct=20.0,
        entry_ease=38,
        seasonality=0.25,
    ),
    Industry(
        code="fitness",
        name="Фитнес-студия",
        aliases=("фитнес", "спортзал", "тренажёрный зал", "йога", "студия растяжки"),
        density_per_100k=5.0,
        growth_yoy_pct=11.0,
        avg_revenue_rub=900_000,
        revenue_spread=0.65,
        closure_rate_pct=26.0,
        entry_ease=28,
        seasonality=0.40,
    ),
    Industry(
        code="autoservice",
        name="Автосервис",
        aliases=("автосервис", "сто", "шиномонтаж", "ремонт авто", "автомастерская"),
        density_per_100k=14.0,
        growth_yoy_pct=3.0,
        avg_revenue_rub=780_000,
        revenue_spread=0.45,
        closure_rate_pct=14.0,
        entry_ease=35,
        seasonality=0.22,
    ),
    Industry(
        code="ecommerce",
        name="Интернет-магазин",
        aliases=("интернет-магазин", "онлайн-магазин", "маркетплейс",
                 "торговля на wildberries", "селлер", "ozon"),
        density_per_100k=31.0,
        growth_yoy_pct=18.0,
        avg_revenue_rub=540_000,
        revenue_spread=0.80,
        closure_rate_pct=31.0,
        entry_ease=85,
        seasonality=0.45,
    ),
    Industry(
        code="it_services",
        name="IT-услуги и веб-студия",
        aliases=("it", "айти", "веб-студия", "разработка", "программирование",
                 "digital-агентство", "сайты"),
        density_per_100k=12.0,
        growth_yoy_pct=14.0,
        avg_revenue_rub=720_000,
        revenue_spread=0.75,
        closure_rate_pct=19.0,
        entry_ease=90,
        seasonality=0.15,
    ),
    Industry(
        code="cleaning",
        name="Клининговые услуги",
        aliases=("клининг", "уборка", "химчистка", "мойка окон"),
        density_per_100k=7.0,
        growth_yoy_pct=12.0,
        avg_revenue_rub=390_000,
        revenue_spread=0.50,
        closure_rate_pct=23.0,
        entry_ease=78,
        seasonality=0.18,
    ),
    Industry(
        code="food_delivery",
        name="Доставка еды и dark kitchen",
        aliases=("доставка еды", "дарк китчен", "dark kitchen", "готовая еда",
                 "доставка обедов"),
        density_per_100k=4.0,
        growth_yoy_pct=21.0,
        avg_revenue_rub=1_100_000,
        revenue_spread=0.75,
        closure_rate_pct=34.0,
        entry_ease=50,
        seasonality=0.28,
    ),
    Industry(
        code="kids_center",
        name="Детский центр и дополнительное образование",
        aliases=("детский центр", "развивашка", "репетиторство", "кружки",
                 "частный детский сад", "школа развития"),
        density_per_100k=6.0,
        growth_yoy_pct=8.0,
        avg_revenue_rub=560_000,
        revenue_spread=0.55,
        closure_rate_pct=21.0,
        entry_ease=32,
        seasonality=0.55,
    ),
    Industry(
        code="flowers",
        name="Цветочный магазин",
        aliases=("цветы", "цветочный", "флористика", "букеты"),
        density_per_100k=8.0,
        growth_yoy_pct=1.0,
        avg_revenue_rub=430_000,
        revenue_spread=0.60,
        closure_rate_pct=25.0,
        entry_ease=62,
        seasonality=0.70,
    ),
)


REGIONS: tuple[Region, ...] = (
    Region("msk", "Москва", ("москва", "мск", "столица"),
           13_000, 1.75, 1.60, 3.0, 8, 0.00),
    Region("spb", "Санкт-Петербург", ("санкт-петербург", "спб", "питер", "петербург"),
           5_600, 1.40, 1.45, 2.0, 6, 0.03),
    Region("mo", "Московская область", ("московская область", "подмосковье", "мо"),
           8_500, 1.25, 1.30, 3.0, 2, 0.00),
    Region("krd", "Краснодарский край", ("краснодарский край", "краснодар", "кубань", "сочи"),
           5_800, 1.05, 1.15, 4.0, 0, 0.08),
    Region("sverdlovsk", "Свердловская область", ("свердловская область", "екатеринбург", "екб"),
           4_200, 1.00, 1.00, 0.0, 0, 0.02),
    Region("tatarstan", "Республика Татарстан", ("татарстан", "казань"),
           3_900, 1.08, 1.10, 2.0, 5, 0.00),
    Region("nsk", "Новосибирская область", ("новосибирская область", "новосибирск", "нск"),
           2_800, 0.95, 1.00, 0.0, 0, 0.03),
    Region("rostov", "Ростовская область", ("ростовская область", "ростов", "ростов-на-дону"),
           4_100, 0.92, 0.95, 0.0, -2, 0.04),
    Region("chelyabinsk", "Челябинская область", ("челябинская область", "челябинск"),
           3_400, 0.88, 0.90, -1.0, -1, 0.02),
    Region("nnov", "Нижегородская область", ("нижегородская область", "нижний новгород", "нижний"),
           3_100, 0.94, 0.95, 0.0, 0, 0.02),
    Region("samara", "Самарская область", ("самарская область", "самара", "тольятти"),
           3_100, 0.90, 0.92, -1.0, -1, 0.02),
    Region("lenobl", "Ленинградская область", ("ленинградская область", "ленобласть"),
           2_000, 0.98, 0.88, 2.0, 1, 0.06),
    Region("bashkortostan", "Республика Башкортостан", ("башкортостан", "башкирия", "уфа"),
           4_000, 0.90, 0.92, 0.0, 0, 0.02),
    Region("primorye", "Приморский край", ("приморский край", "приморье", "владивосток"),
           1_850, 0.95, 0.90, -1.0, -3, 0.05),
    Region("kaliningrad", "Калининградская область", ("калининградская область", "калининград"),
           1_030, 0.97, 1.05, 3.0, 2, 0.12),
)


INDUSTRY_BY_CODE: dict[str, Industry] = {i.code: i for i in INDUSTRIES}
REGION_BY_CODE: dict[str, Region] = {r.code: r for r in REGIONS}


def get_industry(code: str) -> Industry:
    try:
        return INDUSTRY_BY_CODE[code]
    except KeyError as exc:
        raise KeyError(
            f"Нет отрасли {code!r}. Доступные: {', '.join(sorted(INDUSTRY_BY_CODE))}"
        ) from exc


def get_region(code: str) -> Region:
    try:
        return REGION_BY_CODE[code]
    except KeyError as exc:
        raise KeyError(
            f"Нет региона {code!r}. Доступные: {', '.join(sorted(REGION_BY_CODE))}"
        ) from exc


def industry_choices() -> list[tuple[str, str]]:
    return [(i.code, i.name) for i in INDUSTRIES]


def region_choices() -> list[tuple[str, str]]:
    return [(r.code, r.name) for r in REGIONS]


def industries_for_prompt() -> str:
    return "\n".join(
        f"{i.code} — {i.name} (как могут назвать: {', '.join(i.aliases)})"
        for i in INDUSTRIES
    )


def regions_for_prompt() -> str:
    return "\n".join(
        f"{r.code} — {r.name} (как могут назвать: {', '.join(r.aliases)})"
        for r in REGIONS
    )
