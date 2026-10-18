"""Model loading and inference (used by the API and the ML agent tool)."""
from __future__ import annotations

import logging
import threading
from datetime import date
from typing import Any

import joblib
import pandas as pd

from src.config import ROOT, Settings, get_settings
from src.logging_setup import redact
from src.ml.features import INPUT_FIELDS, VARIANT_FULL, VARIANT_SAFE, build_frame

log = logging.getLogger("retailiq.ml.service")

TRAIN_HINT = "Train the model with: python scripts/train_model.py (or: python main.py train)"
DISCLAIMER = (
    "Estimate for a single order line from a statistical model trained on 2011-2014 Superstore data. "
    "It is not a guarantee of actual sales."
)


class ModelNotReady(RuntimeError):
    """No trained model artefact is loaded."""


class InvalidPrediction(ValueError):
    """The request cannot be scored; ``errors`` maps field -> message."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


class ModelService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._bundle: dict[str, Any] | None = None
        self.error: str | None = None
        self._lock = threading.Lock()

    # ---- lifecycle -----------------------------------------------------
    def load(self) -> bool:
        """Load the artefact. Never raises; records the reason when unavailable."""
        path = self.settings.model_path
        if not path.exists():
            self._bundle, self.error = None, f"Model file not found: {self._rel(path)}"
            return False
        try:
            bundle = joblib.load(path)
            if bundle.get("schema_version") != 2:
                raise ValueError("Unsupported model schema version - retrain the model.")
            with self._lock:
                self._bundle, self.error = bundle, None
            log.info("Loaded model %s (trained %s)", path.name, bundle["metadata"]["trained_at"])
            return True
        except Exception as exc:  # noqa: BLE001
            self._bundle, self.error = None, redact(f"Could not load model: {exc}")
            log.error(self.error)
            return False

    @staticmethod
    def _rel(path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return path.name

    @property
    def ready(self) -> bool:
        return self._bundle is not None

    def _require(self) -> dict[str, Any]:
        if self._bundle is None:
            raise ModelNotReady(self.error or "Model is not loaded.")
        return self._bundle

    # ---- info ----------------------------------------------------------
    def health(self) -> dict[str, Any]:
        if not self.ready:
            return {"ready": False, "error": self.error, "hint": TRAIN_HINT}
        meta = self._bundle["metadata"]  # type: ignore[index]
        return {
            "ready": True,
            "trained_at": meta["trained_at"],
            "variants": {n: v["best_model"] for n, v in meta["variants"].items()},
            "default_variant": meta["default_variant"],
            "error": None,
        }

    def metadata(self) -> dict[str, Any]:
        return self._require()["metadata"]

    def input_schema(self) -> dict[str, Any]:
        """Describe every accepted input (drives the dynamic frontend form)."""
        meta = self.metadata()
        opts = meta["options"]
        allowed = {
            "category": opts["categories"],
            "market": opts["markets"],
            "segment": opts["segments"],
            "ship_mode": opts["ship_modes"],
            "order_priority": opts["order_priorities"],
        }
        fields = []
        for f in INPUT_FIELDS:
            item = dict(f)
            if f["name"] in allowed:
                item["options"] = allowed[f["name"]]
            if f["name"] == "sub_category":
                item["options_by_category"] = opts["sub_categories"]
            if f["name"] in opts["ranges"]:
                item["training_range"] = opts["ranges"][f["name"]]
            if f["name"] == "shipping_days":
                item["default_by_ship_mode"] = opts["typical"]["shipping_days_by_ship_mode"]
            if f["name"] == "order_date":
                item["default"] = opts["ranges"]["order_date"][1]
            fields.append(item)
        return {"fields": fields, "variant_rule": "shipping_cost provided -> with_shipping_cost model, otherwise the leakage-safe model."}

    # ---- inference -----------------------------------------------------
    def predict(self, data: dict[str, Any]) -> dict[str, Any]:
        bundle = self._require()
        meta = bundle["metadata"]
        opts = meta["options"]
        errors: dict[str, str] = {}
        warnings: list[str] = []
        assumptions: list[str] = []

        def check(field: str, allowed: list[str]) -> None:
            if data.get(field) not in allowed:
                errors[field] = f"'{data.get(field)}' is not valid. Expected one of: {', '.join(allowed)}"

        check("category", opts["categories"])
        check("market", opts["markets"])
        for field, key in (("segment", "segments"), ("ship_mode", "ship_modes"), ("order_priority", "order_priorities")):
            if data.get(field) is None:
                default = {"segment": "Consumer", "ship_mode": "Standard Class", "order_priority": "Medium"}[field]
                data[field] = default
                assumptions.append(f"{field} not provided; assumed '{default}'.")
            check(field, opts[key])
        if "category" not in errors:
            subs = opts["sub_categories"][data["category"]]
            if data.get("sub_category") not in subs:
                errors["sub_category"] = (
                    f"'{data.get('sub_category')}' is not a sub-category of '{data['category']}'. Expected one of: {', '.join(subs)}"
                )
        if errors:
            raise InvalidPrediction(errors)

        if data.get("shipping_days") is None:
            days = opts["typical"]["shipping_days_by_ship_mode"][data["ship_mode"]]
            data["shipping_days"] = days
            assumptions.append(f"shipping_days not provided; used the typical {days} days for '{data['ship_mode']}'.")
        if data.get("order_date") is None:
            data["order_date"] = opts["ranges"]["order_date"][1]
            assumptions.append(f"order_date not provided; used {data['order_date']} (latest date in the training data).")
        order_date = data["order_date"]
        if isinstance(order_date, date):
            order_date = order_date.isoformat()

        for field in ("quantity", "discount", "shipping_cost", "shipping_days"):
            value = data.get(field)
            lo, hi = opts["ranges"].get(field, (None, None))
            if value is not None and lo is not None and not (lo <= value <= hi):
                warnings.append(f"{field}={value} is outside the training range ({lo} to {hi}); the estimate is an extrapolation.")
        d0, d1 = opts["ranges"]["order_date"]
        if not (d0 <= order_date <= d1):
            warnings.append(f"order_date {order_date} is outside the training period ({d0} to {d1}); calendar effects are extrapolated.")

        variant = VARIANT_FULL if data.get("shipping_cost") is not None else VARIANT_SAFE
        art = bundle["variants"][variant]
        row = {k: data.get(k) for k in ("category", "sub_category", "market", "segment", "ship_mode", "order_priority",
                                         "quantity", "discount", "shipping_cost", "shipping_days")}
        row["order_date"] = order_date
        frame = build_frame(pd.DataFrame([row]), art["features"])

        point = max(float(art["model"].predict(frame)[0]), 0.0)
        low = float(art["q_low"].predict(frame)[0])
        high = float(art["q_high"].predict(frame)[0])
        low, high = min(low, high), max(low, high)
        low, high = max(min(low, point), 0.0), max(high, point)

        vmeta = meta["variants"][variant]
        return {
            "predicted_sales": round(point, 2),
            "lower_bound": round(low, 2),
            "upper_bound": round(high, 2),
            "interval_nominal_coverage": vmeta["interval"]["nominal_coverage"],
            "interval_empirical_coverage": round(vmeta["interval"]["empirical_test_coverage"], 4),
            "variant": variant,
            "model": vmeta["best_model"],
            "test_metrics": {k: round(v, 4) for k, v in vmeta["test_metrics"].items()},
            "typical_sub_category_sales": opts["typical"]["sales_by_sub_category"][data["sub_category"]],
            "inputs_used": {**row},
            "assumptions": assumptions,
            "warnings": warnings,
            "disclaimer": DISCLAIMER,
        }

    def retrain(self, source: str = "csv") -> dict[str, Any]:
        from src.ml.train import train

        meta = train(source=source, verbose=False, settings=self.settings)
        self.load()
        return meta
