import json

import joblib
import pytest

from src.config import Settings
from src.ml.features import FEATURES, VARIANT_FEATURES
from src.ml.service import InvalidPrediction, ModelNotReady, ModelService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def svc(trained_model):
    s = ModelService(trained_model)
    assert s.load()
    return s


@pytest.fixture
def base(order):
    return dict(order)


# ----------------------------------------------------------------------------- training results
def test_metadata_is_complete(svc, trained_model):
    m = svc.metadata()
    assert m["target"]["name"] == "sales" and m["split"] == {"strategy": "random", "test_size": 0.2, "random_state": 42, "cv_folds": 5}
    assert set(m["variants"]) == {"with_shipping_cost", "without_shipping_cost"}
    assert m["dataset"]["rows"] == 51290 and m["limitations"] and m["trained_at"]
    assert json.loads(trained_model.metrics_path.read_text()) == m  # metrics.json mirrors the artefact


def test_models_beat_the_baseline_and_baseline_is_never_selected(svc):
    for name, v in svc.metadata()["variants"].items():
        cands = {c["name"]: c for c in v["candidates"]}
        baseline = cands["Baseline (mean)"]
        assert abs(baseline["test_r2"]) < 0.01 and baseline["is_baseline"] and not baseline["selected"]
        assert sum(c["selected"] for c in v["candidates"]) == 1 and not v["best_model"].startswith("Baseline")
        assert v["test_metrics"]["mae"] < baseline["test_mae"] and v["test_metrics"]["rmse"] < baseline["test_rmse"]
        assert v["test_metrics"]["r2"] > cands["Linear Regression (Ridge)"]["test_r2"] - 0.01


def test_accuracy_floors_are_recorded_honestly(svc):
    v = svc.metadata()["variants"]
    assert v["with_shipping_cost"]["test_metrics"]["r2"] > 0.60
    assert 0.35 < v["without_shipping_cost"]["test_metrics"]["r2"] < v["with_shipping_cost"]["test_metrics"]["r2"]
    for variant in v.values():
        cov = variant["interval"]["empirical_test_coverage"]
        assert 0.70 < cov < 0.90 and variant["interval"]["nominal_coverage"] == pytest.approx(0.8)


def test_no_leakage_columns_in_either_variant(svc):
    v = svc.metadata()["variants"]
    assert "shipping_cost" not in v["without_shipping_cost"]["features"]
    assert "shipping_cost" in v["with_shipping_cost"]["features"]
    for variant in v.values():
        assert not {"sales", "profit", "row_id", "order_id", "customer_id", "product_id"} & set(variant["features"])
        # permutation importance is reported for exactly the features used
        assert {f["feature"] for f in variant["feature_importance"]} == set(variant["features"])
    assert v["with_shipping_cost"]["feature_importance"][0]["feature"] == "shipping_cost"  # the proxy dominates (documented)


def test_default_variant_is_the_leakage_safe_one(svc):
    assert svc.metadata()["default_variant"] == "without_shipping_cost"
    assert svc.health()["default_variant"] == "without_shipping_cost"


# ----------------------------------------------------------------------------- inference
def test_prediction_shape_and_interval(svc, base):
    r = svc.predict(base)
    assert r["variant"] == "without_shipping_cost"
    assert 0 <= r["lower_bound"] <= r["predicted_sales"] <= r["upper_bound"]
    assert r["interval_nominal_coverage"] == pytest.approx(0.8) and 0.7 < r["interval_empirical_coverage"] < 0.9
    assert r["typical_sub_category_sales"] > 0 and r["disclaimer"] and set(r["test_metrics"]) >= {"mae", "rmse", "r2"}
    json.dumps(r)


def test_shipping_cost_selects_the_more_accurate_variant(svc, base):
    cheap = svc.predict({**base, "shipping_cost": 5.0})
    pricey = svc.predict({**base, "shipping_cost": 200.0})
    assert cheap["variant"] == pricey["variant"] == "with_shipping_cost"
    assert pricey["predicted_sales"] > 3 * cheap["predicted_sales"]  # the proxy effect is large and monotone


def test_prediction_is_deterministic(svc, base):
    assert svc.predict(dict(base)) == svc.predict(dict(base))


def test_defaults_are_disclosed_as_assumptions(svc, base):
    r = svc.predict(dict(base))
    text = " ".join(r["assumptions"])
    for field in ("segment", "ship_mode", "order_priority", "shipping_days", "order_date"):
        assert field in text
    full = svc.predict({**base, "segment": "Corporate", "ship_mode": "Same Day", "order_priority": "High",
                        "shipping_days": 0, "order_date": "2013-05-05"})
    assert full["assumptions"] == [] and full["inputs_used"]["segment"] == "Corporate"


def test_inputs_change_the_estimate(svc, base):
    phones = svc.predict(dict(base))["predicted_sales"]
    binders = svc.predict({**base, "category": "Office Supplies", "sub_category": "Binders"})["predicted_sales"]
    assert phones > binders


def test_extrapolation_warnings(svc, base):
    r = svc.predict({**base, "quantity": 40, "order_date": "2026-01-01", "discount": 0.0})
    assert any("quantity=40" in w for w in r["warnings"]) and any("order_date" in w for w in r["warnings"])
    assert svc.predict(dict(base))["warnings"] == []


@pytest.mark.parametrize(
    "patch,field",
    [
        ({"category": "Toys"}, "category"),
        ({"market": "Mars"}, "market"),
        ({"sub_category": "Chairs"}, "sub_category"),     # exists, but not under Technology
        ({"sub_category": "Nope"}, "sub_category"),
        ({"segment": "VIP"}, "segment"),
        ({"ship_mode": "Teleport"}, "ship_mode"),
        ({"order_priority": "Urgent"}, "order_priority"),
    ],
)
def test_invalid_categorical_input_is_rejected_with_a_helpful_message(svc, base, patch, field):
    with pytest.raises(InvalidPrediction) as exc:
        svc.predict({**base, **patch})
    assert field in exc.value.errors and "Expected one of" in exc.value.errors[field]


def test_all_errors_are_reported_together(svc, base):
    with pytest.raises(InvalidPrediction) as exc:
        svc.predict({**base, "category": "Toys", "market": "Mars"})
    assert {"category", "market"} <= set(exc.value.errors)


def test_input_schema_describes_the_real_model(svc):
    schema = svc.input_schema()
    names = [f["name"] for f in schema["fields"]]
    assert names == ["category", "sub_category", "market", "segment", "ship_mode", "order_priority", "quantity", "discount",
                     "shipping_days", "shipping_cost", "order_date"]
    by = {f["name"]: f for f in schema["fields"]}
    assert by["category"]["required"] and not by["shipping_cost"]["required"]
    assert set(by["category"]["options"]) == {"Furniture", "Office Supplies", "Technology"}
    assert "Phones" in by["sub_category"]["options_by_category"]["Technology"]
    assert by["quantity"]["training_range"] == [1, 14] and by["order_date"]["default"] == "2014-12-31"
    # every model input maps to a declared field (nothing arbitrary in the form)
    model_inputs = set(VARIANT_FEATURES["with_shipping_cost"]) - {"year", "weeknum", "month", "quarter", "day_of_week"}
    assert model_inputs <= set(names)


# ----------------------------------------------------------------------------- not ready
def test_service_without_artifact_reports_and_refuses(tmp_path):
    s = ModelService(Settings(model_path=tmp_path / "missing.joblib", metrics_path=tmp_path / "m.json", _env_file=None))
    assert s.load() is False and not s.ready
    h = s.health()
    assert h["ready"] is False and "train_model.py" in h["hint"] and "not found" in h["error"]
    with pytest.raises(ModelNotReady):
        s.predict({"category": "Technology"})
    with pytest.raises(ModelNotReady):
        s.metadata()


def test_corrupt_artifact_is_reported_not_raised(tmp_path):
    bad = tmp_path / "bad.joblib"
    bad.write_bytes(b"this is not a joblib file")
    s = ModelService(Settings(model_path=bad, metrics_path=tmp_path / "m.json", _env_file=None))
    assert s.load() is False and "Could not load model" in s.error


def test_old_artifact_schema_requires_retraining(tmp_path):
    old = tmp_path / "old.joblib"
    joblib.dump({"schema_version": 1}, old)
    s = ModelService(Settings(model_path=old, metrics_path=tmp_path / "m.json", _env_file=None))
    assert s.load() is False and "retrain" in s.error.lower()
