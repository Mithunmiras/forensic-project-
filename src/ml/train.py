"""Train, compare, evaluate and persist the sales-prediction models.

    python scripts/train_model.py            # or: python main.py train

Two variants are trained (see ``features.py`` for the leakage rationale):

* ``with_shipping_cost``    - uses the shipping cost the customer is quoted.
* ``without_shipping_cost`` - leakage-safe: order attributes only.

For each variant, a mean-predictor baseline plus Ridge, Decision Tree, Random
Forest and Gradient Boosting are compared by 5-fold cross-validation on the
training split. The best model by CV R^2 is refit and scored once on the held-out
20% test split (``random_state=42``). Two quantile models give an 80% prediction
interval whose empirical coverage on the test split is measured and reported.
"""
from __future__ import annotations

import json
import logging
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

from src.config import DOCS_DIR, Settings, get_settings
from src.data import load_sales
from src.ml.features import (
    CATEGORICAL,
    INPUT_FIELDS,
    TARGET,
    VARIANT_FEATURES,
    VARIANT_LABELS,
    VARIANT_SAFE,
    build_frame,
)

log = logging.getLogger("retailiq.ml.train")

RANDOM_STATE = 42
TEST_SIZE = 0.20
INTERVAL = (0.10, 0.90)
SCHEMA_VERSION = 2


def _ordinal(features: list[str]) -> ColumnTransformer:
    cats = [c for c in CATEGORICAL if c in features]
    return ColumnTransformer(
        [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cats)],
        remainder="passthrough",
    )


def _onehot_scaled(features: list[str]) -> ColumnTransformer:
    cats = [c for c in CATEGORICAL if c in features]
    nums = [f for f in features if f not in cats]
    return ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), cats), ("num", StandardScaler(), nums)]
    )


def candidate_models(features: list[str]) -> dict[str, Pipeline]:
    return {
        "Baseline (mean)": Pipeline([("prep", _ordinal(features)), ("model", DummyRegressor(strategy="mean"))]),
        "Linear Regression (Ridge)": Pipeline([("prep", _onehot_scaled(features)), ("model", Ridge(alpha=1.0))]),
        "Decision Tree": Pipeline(
            [
                ("prep", _ordinal(features)),
                ("model", DecisionTreeRegressor(max_depth=10, min_samples_leaf=5, random_state=RANDOM_STATE)),
            ]
        ),
        "Random Forest": Pipeline(
            [
                ("prep", _ordinal(features)),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=200, max_depth=14, min_samples_leaf=5, max_features=0.6,
                        random_state=RANDOM_STATE, n_jobs=-1,
                    ),
                ),
            ]
        ),
        "Gradient Boosting": Pipeline(
            [
                ("prep", _ordinal(features)),
                ("model", HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=RANDOM_STATE)),
            ]
        ),
    }


def _quantile_model(features: list[str], q: float) -> Pipeline:
    return Pipeline(
        [
            ("prep", _ordinal(features)),
            (
                "model",
                HistGradientBoostingRegressor(
                    loss="quantile", quantile=q, max_iter=250, learning_rate=0.06, random_state=RANDOM_STATE
                ),
            ),
        ]
    )


def _scores(y_true, y_pred) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "median_abs_error": float(median_absolute_error(y_true, y_pred)),
    }


def category_options(df: pd.DataFrame) -> dict[str, Any]:
    """Valid values for each categorical input, plus ranges seen in training."""
    sub_by_cat = {cat: sorted(subs) for cat, subs in df.groupby("category")["sub_category"].unique().items()}
    days_by_mode = df.groupby("ship_mode")["shipping_days"].median().round().astype(int)
    return {
        "categories": sorted(df["category"].unique()),
        "sub_categories": sub_by_cat,
        "markets": sorted(df["market"].unique()),
        "segments": sorted(df["segment"].unique()),
        "ship_modes": sorted(df["ship_mode"].unique()),
        "order_priorities": ["Low", "Medium", "High", "Critical"],
        "ranges": {
            "quantity": [int(df["quantity"].min()), int(df["quantity"].max())],
            "discount": [float(df["discount"].min()), float(df["discount"].max())],
            "shipping_cost": [float(df["shipping_cost"].min()), float(df["shipping_cost"].max())],
            "shipping_days": [int(df["shipping_days"].min()), int(df["shipping_days"].max())],
            "order_date": [df["order_date"].min().strftime("%Y-%m-%d"), df["order_date"].max().strftime("%Y-%m-%d")],
        },
        "typical": {
            "sales_by_sub_category": {k: round(float(v), 2) for k, v in df.groupby("sub_category")["sales"].median().items()},
            "shipping_days_by_ship_mode": {k: int(v) for k, v in days_by_mode.items()},
        },
    }


def load_training_frame(source: str, settings: Settings) -> pd.DataFrame:
    """Raw orders with every column the model needs. ``source``: csv | postgres."""
    if source == "csv":
        return load_sales("csv")
    if source == "postgres":
        from sqlalchemy import text

        from src.db.session import Database

        db = Database(settings)
        try:
            with db.readonly_engine().connect() as conn:
                df = pd.read_sql(
                    text(
                        "SELECT order_date, category, sub_category, market, segment, ship_mode, order_priority, "
                        "quantity, discount, shipping_cost, shipping_days, sales FROM retailiq.v_sales"
                    ),
                    conn,
                )
        finally:
            db.dispose()
        for col in ("discount", "shipping_cost", "sales"):
            df[col] = df[col].astype(float)
        df["order_date"] = pd.to_datetime(df["order_date"])
        return df
    raise ValueError("source must be 'csv' or 'postgres'")


def _train_variant(name: str, raw: pd.DataFrame, log_fn) -> tuple[dict[str, Any], dict[str, Any]]:
    """Train one variant. Returns (artifacts-for-joblib, metadata-for-json)."""
    features = VARIANT_FEATURES[name]
    X, y = build_frame(raw, features), raw[TARGET].astype(float)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    log_fn(f"\n[{name}] {len(X_train):,} train / {len(X_test):,} test rows, {len(features)} features")
    log_fn(f"{'Model':<28}{'CV R2':>9}{'Test R2':>9}{'MAE':>9}{'RMSE':>10}{'Fit s':>8}")

    results, fitted = [], {}
    for model_name, pipe in candidate_models(features).items():
        cv = cross_val_score(pipe, X_train, y_train, cv=5, scoring="r2", n_jobs=1)
        t0 = time.perf_counter()
        pipe.fit(X_train, y_train)
        fit_s = time.perf_counter() - t0
        test = _scores(y_test, pipe.predict(X_test))
        fitted[model_name] = pipe
        results.append(
            {
                "name": model_name,
                "is_baseline": model_name.startswith("Baseline"),
                "cv_r2_mean": float(cv.mean()),
                "cv_r2_std": float(cv.std()),
                "fit_seconds": round(fit_s, 2),
                **{f"test_{k}": v for k, v in test.items()},
            }
        )
        log_fn(f"{model_name:<28}{cv.mean():>9.4f}{test['r2']:>9.4f}{test['mae']:>9.2f}{test['rmse']:>10.2f}{fit_s:>8.1f}")

    best = max((r for r in results if not r["is_baseline"]), key=lambda r: r["cv_r2_mean"])
    for r in results:
        r["selected"] = r["name"] == best["name"]
    model = fitted[best["name"]]
    log_fn(f"Selected: {best['name']} (best cross-validated R2)")

    q_low = _quantile_model(features, INTERVAL[0]).fit(X_train, y_train)
    q_high = _quantile_model(features, INTERVAL[1]).fit(X_train, y_train)
    lo, hi = q_low.predict(X_test), q_high.predict(X_test)
    low, high = np.minimum(lo, hi), np.maximum(lo, hi)
    coverage = float(np.mean((y_test >= low) & (y_test <= high)))
    log_fn(f"80% interval empirical coverage on test: {coverage:.1%}")

    sample = X_test.sample(min(4000, len(X_test)), random_state=RANDOM_STATE)
    perm = permutation_importance(
        model, sample, y_test.loc[sample.index], n_repeats=5, random_state=RANDOM_STATE, scoring="r2", n_jobs=1
    )
    importance = sorted(
        ({"feature": f, "importance": float(m)} for f, m in zip(features, perm.importances_mean)),
        key=lambda d: d["importance"], reverse=True,
    )
    point = model.predict(X_test)
    scatter = pd.DataFrame({"actual": y_test.to_numpy(), "predicted": point}).sample(400, random_state=RANDOM_STATE)

    artifacts = {"model": model, "q_low": q_low, "q_high": q_high, "features": features}
    meta = {
        "label": VARIANT_LABELS[name],
        "features": features,
        "best_model": best["name"],
        "candidates": results,
        "test_metrics": {k.removeprefix("test_"): v for k, v in best.items() if k.startswith("test_")},
        "baseline_test_metrics": {
            k.removeprefix("test_"): v
            for k, v in next(r for r in results if r["is_baseline"]).items()
            if k.startswith("test_")
        },
        "interval": {
            "method": "quantile gradient boosting (10th and 90th percentile)",
            "nominal_coverage": INTERVAL[1] - INTERVAL[0],
            "empirical_test_coverage": coverage,
        },
        "feature_importance": importance,
        "scatter": [
            {"actual": round(float(a), 2), "predicted": round(float(p), 2)}
            for a, p in zip(scatter["actual"], scatter["predicted"])
        ],
        "split": {"train_rows": int(len(X_train)), "test_rows": int(len(X_test))},
    }
    return artifacts, meta


def train(source: str = "csv", verbose: bool = True, settings: Settings | None = None,
          write_report: bool = True) -> dict[str, Any]:
    settings = settings or get_settings()
    log_fn = print if verbose else (lambda *a, **k: None)
    raw = load_training_frame(source, settings)
    raw = raw.dropna(subset=[TARGET]).reset_index(drop=True)
    log_fn(f"Dataset: {len(raw):,} order lines (source: {source})")

    artifacts, variants = {}, {}
    for name in VARIANT_FEATURES:
        artifacts[name], variants[name] = _train_variant(name, raw, log_fn)

    options = category_options(raw)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "target": {
            "name": TARGET,
            "definition": "Sales value of a single order line, in the dataset's currency units.",
        },
        "dataset": {"rows": int(len(raw)), "source": source, "order_date_range": options["ranges"]["order_date"]},
        "split": {"strategy": "random", "test_size": TEST_SIZE, "random_state": RANDOM_STATE, "cv_folds": 5},
        "default_variant": VARIANT_SAFE,
        "variants": variants,
        "input_fields": INPUT_FIELDS,
        "options": options,
        "limitations": [
            "Predictions are statistical estimates for one order line, not guarantees of future sales.",
            "Only 2011-2014 data was used; dates outside that range are extrapolations.",
            "Sales is heavy-tailed: a few very large orders dominate RMSE, so typical error is lower than RMSE suggests.",
            "The with_shipping_cost variant relies on shipping cost, which scales with order value in this dataset (a proxy of the target).",
            "The model uses order attributes only; it has no knowledge of customers, products or promotions beyond the listed fields.",
        ],
    }
    bundle = {"schema_version": SCHEMA_VERSION, "variants": artifacts, "metadata": metadata}

    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, settings.model_path, compress=3)
    settings.metrics_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    log_fn(f"\nSaved {settings.model_path.name} ({settings.model_path.stat().st_size / 1024**2:.1f} MiB) "
           f"and {settings.metrics_path.name}")
    if write_report:
        write_model_report(metadata)
        log_fn("Wrote docs/generated/model_report.md")
    return metadata


def write_model_report(meta: dict[str, Any], out_dir: Path | None = None) -> Path:
    """Markdown evaluation report (also indexed by the RAG knowledge base)."""
    out_dir = out_dir or (DOCS_DIR / "generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "model_report.md"
    lines = [
        "# Sales Prediction Model Report",
        "",
        f"_Generated by `src/ml/train.py` on {meta['trained_at']} (scikit-learn {meta['sklearn_version']}, Python {meta['python_version']}). "
        "Every number below was computed from an actual training run._",
        "",
        "## Target and data",
        f"- Target: `{meta['target']['name']}` - {meta['target']['definition']}",
        f"- Rows: {meta['dataset']['rows']:,} order lines (source: {meta['dataset']['source']}); "
        f"order dates {meta['dataset']['order_date_range'][0]} to {meta['dataset']['order_date_range'][1]}.",
        f"- Split: random {int((1 - meta['split']['test_size']) * 100)}/{int(meta['split']['test_size'] * 100)} train/test, "
        f"random_state={meta['split']['random_state']}; model selection by {meta['split']['cv_folds']}-fold cross-validation on the training split only.",
        "",
        "## Two variants and target leakage",
        "`shipping_cost` in the Superstore data scales with the order's value, so it works as a proxy for the target "
        "(Spearman correlation about 0.91 with sales). The project therefore trains two models:",
        "- **with_shipping_cost**: highest accuracy, but relies on that proxy.",
        "- **without_shipping_cost** (default): leakage-safe - uses only order attributes (category, sub-category, market, segment, "
        "ship mode, priority, quantity, discount, shipping days and calendar features).",
        "`profit` and all identifiers are never used as features.",
        "",
    ]
    for name, v in meta["variants"].items():
        lines += [f"## Variant: {name}", f"{v['label']}", "", f"Selected model: **{v['best_model']}**", "",
                  "| Model | CV R2 (mean +/- sd) | Test R2 | Test MAE | Test RMSE |", "| --- | --- | --- | --- | --- |"]
        for r in sorted(v["candidates"], key=lambda r: -r["cv_r2_mean"]):
            mark = " (selected)" if r["selected"] else (" (baseline)" if r["is_baseline"] else "")
            lines.append(
                f"| {r['name']}{mark} | {r['cv_r2_mean']:.3f} +/- {r['cv_r2_std']:.3f} | {r['test_r2']:.3f} | "
                f"{r['test_mae']:.2f} | {r['test_rmse']:.2f} |"
            )
        m, b = v["test_metrics"], v["baseline_test_metrics"]
        top = ", ".join(f"{f['feature']} ({f['importance']:.3f})" for f in v["feature_importance"][:5])
        lines += [
            "",
            f"Held-out test: MAE {m['mae']:.2f}, RMSE {m['rmse']:.2f}, R2 {m['r2']:.3f}, median absolute error {m['median_abs_error']:.2f}. "
            f"The mean-predictor baseline scores MAE {b['mae']:.2f}, RMSE {b['rmse']:.2f}, R2 {b['r2']:.3f}.",
            f"80% prediction interval (quantile regression): empirical coverage on the test split = {v['interval']['empirical_test_coverage']:.1%}.",
            f"Top permutation importances (drop in R2): {top}.",
            "",
        ]
    lines += ["## Limitations", *[f"- {x}" for x in meta["limitations"]], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    train()
