"""Generate the data-driven knowledge-base documents from the live database.

    python scripts/generate_docs.py

Writes docs/generated/data_dictionary.md and docs/generated/analytical_findings.md.
Every figure is computed from PostgreSQL at generation time - nothing is typed by hand.
(docs/generated/model_report.md is written by the training script.)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from src.analytics.repository import AnalyticsRepository, Filters  # noqa: E402
from src.analytics.schema_info import QUALIFIED_VIEW, V_SALES_COLUMNS  # noqa: E402
from src.config import DOCS_DIR, get_settings  # noqa: E402
from src.db.session import Database, safe_error  # noqa: E402

OUT = DOCS_DIR / "generated"


def money(v: float) -> str:
    return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


def data_dictionary(db: Database) -> str:
    lines = [
        "# Data Dictionary",
        "",
        f"_Generated from PostgreSQL on {datetime.now(timezone.utc):%Y-%m-%d}. The analytics layer and the SQL agent read only the view `{QUALIFIED_VIEW}` (one row per order line)._",
        "",
        "| Column | Type | Meaning | Distinct values | Min | Max |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    with db.readonly_engine().connect() as conn:
        total = conn.execute(text(f"SELECT count(*) FROM {QUALIFIED_VIEW}")).scalar()
        for name, typ, desc in V_SALES_COLUMNS:
            if typ in ("integer", "numeric", "date"):
                d, lo, hi = conn.execute(text(f"SELECT count(DISTINCT {name}), min({name}), max({name}) FROM {QUALIFIED_VIEW}")).one()
            else:
                d = conn.execute(text(f"SELECT count(DISTINCT {name}) FROM {QUALIFIED_VIEW}")).scalar()
                lo = hi = ""
            fmt = (lambda v: f"{float(v):g}" if isinstance(v, (int, float)) or hasattr(v, "as_tuple") else str(v))
            lines.append(f"| `{name}` | {typ} | {desc} | {d:,} | {fmt(lo) if lo != '' else ''} | {fmt(hi) if hi != '' else ''} |")
        conn.rollback()
    lines += [
        "",
        f"The view contains {total:,} order lines. An order (`order_id`) can have several lines; "
        "`row_id` identifies a single line. `shipping_days` = `ship_date` - `order_date`.",
        "",
        "## Underlying tables (schema `retailiq`)",
        "- `fact_sales` - one row per order line (grain), keyed by `row_id`; foreign keys to the three dimensions.",
        "- `dim_customer` - customer id, name, segment.",
        "- `dim_product` - product id, name, category, sub-category. `product_id` is not unique in the source data, so the natural key is the full tuple.",
        "- `dim_location` - city, state, country, region, market, market2.",
        "- `etl_runs` - audit record of every ETL execution with row counts and a data-quality report.",
        "",
        "Money and discount columns keep the source precision; nothing is rounded during loading.",
        "",
    ]
    return "\n".join(lines)


def findings(repo: AnalyticsRepository, db: Database) -> str:
    f = Filters()
    kp = repo.summary(f)["kpis"]
    cat = repo.by_dimension("category", f)
    mkt = repo.by_dimension("market", f)
    reg = repo.by_dimension("region", f, order_by="profit")
    sub = repo.by_dimension("sub_category", f, order_by="profit")
    yearly = repo.trend(f, "year")
    disc = repo.discount_impact(f)
    ship = repo.shipping(f)
    seg = repo.by_dimension("segment", f)
    top_prod = repo.top_products(f, 3)

    L = [
        "# Verified Analytical Findings",
        "",
        f"_Computed from PostgreSQL on {datetime.now(timezone.utc):%Y-%m-%d}; each statement below is a direct SQL aggregation of `{QUALIFIED_VIEW}`. They describe what the data shows, not why._",
        "",
        "## Headline figures",
        f"- Period covered: {kp['first_date']} to {kp['last_date']}.",
        f"- Total sales {money(kp['total_sales'])}, total profit {money(kp['total_profit'])}, profit margin {kp['profit_margin']:.1%}.",
        f"- {kp['orders']:,} orders ({kp['order_lines']:,} order lines), {kp['customers']:,} customers, {kp['units']:,} units sold.",
        f"- Average order value {money(kp['avg_order_value'])}; average line discount {kp['avg_discount']:.1%}.",
        "",
        "## Sales and profit by category",
    ]
    for c in cat:
        L.append(f"- {c['name']}: sales {money(c['sales'])}, profit {money(c['profit'])}, margin {c['margin_pct']:.1f}%.")
    L += ["", "## Sales by year"]
    prev = None
    for y in yearly:
        growth = f" ({(y['sales'] / prev - 1):+.1%} vs previous year)" if prev else ""
        L.append(f"- {y['period']}: sales {money(y['sales'])}, profit {money(y['profit'])}{growth}.")
        prev = y["sales"]
    L += ["", "## Markets (by sales)"]
    for m in mkt:
        L.append(f"- {m['name']}: sales {money(m['sales'])}, profit {money(m['profit'])}, margin {m['margin_pct']:.1f}%.")
    best, worst = reg[0], reg[-1]
    top_sub = ", ".join("{} ({})".format(s["name"], money(s["profit"])) for s in sub[:3])
    L += [
        "", "## Regions (by profit)",
        f"- Most profitable region: {best['name']} (profit {money(best['profit'])} on sales {money(best['sales'])}).",
        f"- Least profitable region: {worst['name']} (profit {money(worst['profit'])} on sales {money(worst['sales'])}).",
        "", "## Sub-categories (by profit)",
        f"- Highest profit: {top_sub}.",
    ]
    losing = [s for s in sub if s["profit"] < 0]
    L.append("- Loss-making sub-categories: " + (", ".join(f"{s['name']} ({money(s['profit'])})" for s in losing) if losing else "none") + ".")
    L += ["", "## Customer segments"]
    for s in seg:
        L.append(f"- {s['name']}: sales {money(s['sales'])}, profit {money(s['profit'])}.")
    L += ["", "## Discounts and profitability", "Profit margin by line-discount band (profit / sales within the band):"]
    for d in disc:
        L.append(f"- {d['band'][2:]}: margin {d['margin_pct']:.1f}% over {d['order_lines']:,} order lines.")
    L += ["", "## Shipping"]
    for s in ship:
        L.append(f"- {s['ship_mode']}: {s['orders']:,} orders, average {s['avg_days']:.1f} days to ship, average shipping cost {s['avg_cost']:.2f}.")
    L += ["", "## Best-selling products", "- " + "; ".join(f"{p['name']} ({money(p['sales'])})" for p in top_prod) + ".", ""]
    return "\n".join(L)


def main() -> int:
    db = Database(get_settings())
    try:
        repo = AnalyticsRepository(db)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "data_dictionary.md").write_text(data_dictionary(db), encoding="utf-8")
        (OUT / "analytical_findings.md").write_text(findings(repo, db), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not generate docs (is the database loaded?): {safe_error(exc)}")
        return 1
    finally:
        db.dispose()
    print("Wrote docs/generated/data_dictionary.md and docs/generated/analytical_findings.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
