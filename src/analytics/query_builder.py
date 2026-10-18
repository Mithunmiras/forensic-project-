"""Deterministic natural-language -> SQL for common analytical questions.

No LLM is involved. A question is parsed into a ``QuerySpec`` (metric, optional
dimension, filters, ordering, limit) and rendered into SQL from whitelisted
metric/dimension fragments. Filter values are always bind parameters. The
resulting SQL still goes through the same AST validator as LLM-written SQL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.analytics.schema_info import QUALIFIED_VIEW

# metric -> (SQL expression, output alias, human label)
METRICS: dict[str, tuple[str, str, str]] = {
    "sales": ("SUM(sales)", "total_sales", "total sales"),
    "profit": ("SUM(profit)", "total_profit", "total profit"),
    "orders": ("COUNT(DISTINCT order_id)", "orders", "number of orders"),
    "quantity": ("SUM(quantity)", "units_sold", "units sold"),
    "customers": ("COUNT(DISTINCT customer_id)", "customers", "number of customers"),
    "avg_discount": ("AVG(discount) * 100", "avg_discount_pct", "average discount (%)"),
    "avg_order_value": ("SUM(sales) / NULLIF(COUNT(DISTINCT order_id), 0)", "avg_order_value", "average order value"),
    "profit_margin": ("100 * SUM(profit) / NULLIF(SUM(sales), 0)", "profit_margin_pct", "profit margin (%)"),
    "avg_shipping_days": ("AVG(shipping_days)", "avg_shipping_days", "average shipping days"),
    "avg_shipping_cost": ("AVG(shipping_cost)", "avg_shipping_cost", "average shipping cost"),
}

# dimension -> (SQL expression, alias, label, is_time)
DIMS: dict[str, tuple[str, str, str, bool]] = {
    "category": ("category", "category", "category", False),
    "sub_category": ("sub_category", "sub_category", "sub-category", False),
    "region": ("region", "region", "region", False),
    "market": ("market", "market", "market", False),
    "country": ("country", "country", "country", False),
    "state": ("state", "state", "state", False),
    "city": ("city", "city", "city", False),
    "segment": ("segment", "segment", "customer segment", False),
    "ship_mode": ("ship_mode", "ship_mode", "ship mode", False),
    "order_priority": ("order_priority", "order_priority", "order priority", False),
    "product": ("product_name", "product", "product", False),
    "customer": ("customer_name", "customer", "customer", False),
    "month": ("year_month", "month", "month", True),
    "quarter": ("CAST(year AS TEXT) || '-Q' || CAST(quarter AS TEXT)", "quarter", "quarter", True),
    "year": ("year", "year", "year", True),
}

# Regexes in priority order (most specific first).
_METRIC_PATTERNS: list[tuple[str, str]] = [
    ("avg_discount", r"(average|avg|mean)\s+discount|discount\s+(rate|level|percentage)|\bdiscounts?\b"),
    ("profit_margin", r"\bmargins?\b"),
    ("avg_order_value", r"average\s+order\s+(value|size)|\baov\b|avg\s+order"),
    ("avg_shipping_days", r"shipping\s+(days|duration|time)|delivery\s+(time|days|duration)|days\s+to\s+ship|ship(ping)?\s+speed|shipping\s+length|time\s+to\s+ship"),
    ("avg_shipping_cost", r"shipping\s+cost|freight|shipping\s+charge"),
    ("customers", r"how\s+many\s+(unique\s+)?customers|(number|count)\s+of\s+(unique\s+)?customers|customer\s+count|unique\s+customers"),
    ("orders", r"how\s+many\s+orders|(number|count|total)\s+of\s+orders|orders?\s+count|\bnumber\s+of\s+orders|most\s+orders|\borders\b"),
    ("quantity", r"\bquantit(y|ies)\b|\bunits\b|items\s+sold"),
    ("profit", r"\bprofit(s|able|ability)?\b|\bearn"),
    ("sales", r"\bsales\b|\brevenue\b|\bsold\b|\bturnover\b|\bsell"),
]

_DIM_PATTERNS: list[tuple[str, str]] = [
    ("sub_category", r"sub[\s-]?categor(y|ies)"),
    ("category", r"\bcategor(y|ies)\b"),
    ("region", r"\bregions?\b"),
    ("market", r"\bmarkets?\b"),
    ("country", r"\bcountr(y|ies)\b"),
    ("state", r"\b(states?|provinces?)\b"),
    ("city", r"\bcit(y|ies)\b"),
    ("segment", r"\bsegments?\b"),
    ("ship_mode", r"ship(ping)?[\s-]*(modes?|methods?)|\bship\s+modes?\b"),
    ("order_priority", r"\bpriorit(y|ies)\b"),
    ("customer", r"\bcustomers?\b"),
    ("product", r"\bproducts?\b|\bitems?\b"),
]
_TIME_PATTERNS: list[tuple[str, str]] = [
    ("quarter", r"\bquarter(ly|s)?\b"),
    ("year", r"\byearly\b|\bannual(ly)?\b|per\s+year|by\s+year|each\s+year|year[\s-]over[\s-]year|\byoy\b"),
    ("month", r"\bmonthly\b|per\s+month|by\s+month|each\s+month|\bmonths\b|\btrends?\b|over\s+time|time\s+series"),
]
_DIM_LEADERS = r"(?:by|per|each|every|across|which|what|compare|comparing|among|between|for\s+each|of\s+each)"

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                 "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20}
_ASC = r"\b(lowest|least|worst|bottom|fewest|smallest|shortest|minimum|weakest)\b"
_DESC = r"\b(highest|most|best|top|largest|longest|biggest|maximum|leading|strongest)\b"

HIGH_CARDINALITY = {"product", "customer", "city", "state", "country"}
FILTER_COLUMNS = ["category", "sub_category", "region", "market", "segment", "ship_mode", "country", "order_priority"]
_OPTION_KEYS = {
    "category": "categories", "sub_category": "sub_categories", "region": "regions", "market": "markets",
    "segment": "segments", "ship_mode": "ship_modes", "country": "countries",
}
_ORDER_PRIORITIES = ["Low", "Medium", "High", "Critical"]


@dataclass
class QuerySpec:
    metric: str
    dimension: str | None = None
    descending: bool = True
    limit: int | None = None
    years: list[int] = field(default_factory=list)
    year_range: bool = False
    filters: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def is_time(self) -> bool:
        return bool(self.dimension and DIMS[self.dimension][3])


def _parse_limit(q: str) -> int | None:
    m = re.search(r"\b(?:top|bottom|best|worst|highest|lowest|first)\s+(\d+|" + "|".join(_NUMBER_WORDS) + r")\b", q)
    if not m:
        m = re.search(r"\b(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+(?:best|top|highest|lowest|worst|most|least)\b", q)
    if not m:
        m = re.search(r"\b(?:which|what|show|list|give\s+me|find|name)\s+(?:the\s+)?(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+[a-z-]+", q)
    if not m:
        return None
    token = m.group(1)
    n = int(token) if token.isdigit() else _NUMBER_WORDS[token]
    return max(1, min(n, 100))


def _find_metric(q: str) -> str | None:
    for name, pattern in _METRIC_PATTERNS:
        if re.search(pattern, q):
            return name
    return None


def _find_dimension(q: str) -> str | None:
    for name, pattern in _TIME_PATTERNS:
        if re.search(pattern, q):
            return name
    matched = [name for name, pattern in _DIM_PATTERNS if re.search(pattern, q)]
    if not matched:
        return None
    # An explicit "by X" / "per X" wins; otherwise the most specific match.
    for name, pattern in _DIM_PATTERNS:
        if name in matched and re.search(_DIM_LEADERS + r"\s+(?:the\s+)?(?:\w+\s+){0,2}?(?:" + pattern + ")", q):
            return name
    return matched[0]


def _find_filters(question: str, q: str, known: dict[str, list[str]], dimension: str | None) -> dict[str, str]:
    found: dict[str, str] = {}
    for col in FILTER_COLUMNS:
        if col == dimension or col in found:
            continue
        values = list(known.get(_OPTION_KEYS.get(col, ""), [])) if col != "order_priority" else _ORDER_PRIORITIES
        for value in sorted(values, key=len, reverse=True):
            if col == "order_priority":
                # Only when written as "<priority> priority" to avoid matching ordinary words.
                if re.search(rf"\b{value.lower()}\s+priority\b", q):
                    found[col] = value
                    break
                continue
            short = len(value) <= 3
            if short:
                hit = re.search(rf"\b{re.escape(value)}\b", question)  # case-sensitive: "US", "EU"
            else:
                hit = re.search(rf"\b{re.escape(value.lower())}\b", q)
            if hit:
                found[col] = value
                break
    return found


def parse_question(question: str, known_values: dict[str, list[str]]) -> QuerySpec | None:
    """Return a ``QuerySpec`` for a recognisable analytical question, else None."""
    q = question.lower().strip()
    if not q:
        return None
    dimension = _find_dimension(q)
    metric = _find_metric(q)
    if metric is None and dimension is None:
        return None
    if metric is None:
        metric = "sales"
    # "how many customers" etc. are counts, not groupings by customer.
    if metric == "customers" and dimension == "customer":
        dimension = None
    # Metrics that already imply a dimension collision.
    if metric == "avg_shipping_days" and dimension == "ship_mode" and not re.search(r"ship(ping)?[\s-]*(modes?|methods?)", q):
        dimension = None

    spec = QuerySpec(metric=metric, dimension=dimension)
    spec.filters = _find_filters(question, q, known_values, dimension)

    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", q)]
    if years:
        spec.years = sorted(set(years))
        spec.year_range = len(spec.years) == 2 and bool(re.search(r"between|from|through|to\b|-", q))
        if len(spec.years) > 6:
            spec.years = spec.years[:6]

    asc = re.search(_ASC, q)
    desc = re.search(_DESC, q)
    spec.descending = not (asc and not desc)
    if spec.is_time:
        spec.descending = False
    spec.limit = _parse_limit(q)
    if spec.limit is None and dimension in HIGH_CARDINALITY:
        spec.limit = 10
        spec.notes.append("Showing the top 10 by default.")
    if dimension and re.search(r"\b(bottom|worst|lowest|least)\s+\d+", q):
        spec.descending = False
    return spec


def describe(spec: QuerySpec) -> str:
    label = METRICS[spec.metric][2].capitalize()
    text = label
    if spec.dimension:
        text += f" by {DIMS[spec.dimension][2]}"
    cond = []
    if spec.years:
        cond.append(f"years {spec.years[0]} to {spec.years[1]}" if spec.year_range else f"year {', '.join(map(str, spec.years))}")
    cond += [f"{k.replace('_', ' ')} = {v}" for k, v in spec.filters.items()]
    if cond:
        text += " (" + ", ".join(cond) + ")"
    if spec.dimension and not spec.is_time:
        text += f", sorted {'highest' if spec.descending else 'lowest'} first"
        if spec.limit:
            text += f", limited to {spec.limit}"
    return text + "."


def build_sql(spec: QuerySpec) -> tuple[str, dict[str, object]]:
    """Render the spec into SQL (named ``:param`` placeholders) and its parameters."""
    expr, alias, _ = METRICS[spec.metric]
    metric_sql = f"ROUND(CAST({expr} AS NUMERIC), 2) AS {alias}"
    params: dict[str, object] = {}
    where: list[str] = []
    if spec.years:
        if spec.year_range:
            params["y0"], params["y1"] = spec.years[0], spec.years[1]
            where.append("year BETWEEN :y0 AND :y1")
        else:
            names = []
            for i, y in enumerate(spec.years):
                params[f"y{i}"] = y
                names.append(f":y{i}")
            where.append(f"year IN ({', '.join(names)})")
    for i, (col, value) in enumerate(spec.filters.items()):
        params[f"f{i}"] = value
        where.append(f"{col} = :f{i}")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    if spec.dimension is None:
        return f"SELECT {metric_sql} FROM {QUALIFIED_VIEW}{where_sql}", params

    dim_expr, dim_alias, _, is_time = DIMS[spec.dimension]
    columns = [f"{dim_expr} AS {dim_alias}", metric_sql]
    if spec.metric == "sales":
        columns.append("ROUND(CAST(SUM(profit) AS NUMERIC), 2) AS total_profit")
    elif spec.metric == "profit":
        columns.append("ROUND(CAST(SUM(sales) AS NUMERIC), 2) AS total_sales")
    order = "ORDER BY 1 ASC" if is_time else f"ORDER BY 2 {'DESC' if spec.descending else 'ASC'}, 1"
    limit = f" LIMIT {int(spec.limit)}" if spec.limit else ""
    sql = f"SELECT {', '.join(columns)} FROM {QUALIFIED_VIEW}{where_sql} GROUP BY 1 {order}{limit}"
    return sql, params


SUPPORTED_EXAMPLES = [
    "What is the total sales amount?",
    "Which product categories generate the most sales?",
    "What are the top 10 products by sales?",
    "Compare sales by region",
    "What is the monthly sales trend?",
    "Which sub-categories have the highest profit?",
    "What is the average discount by category?",
    "Which shipping modes have the longest shipping duration?",
    "Top 5 customers by profit in 2014",
    "What is the profit margin by market?",
]
