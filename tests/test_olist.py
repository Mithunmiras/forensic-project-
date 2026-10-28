"""Real-data (Olist) checks. Skipped when the dataset has not been imported."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from forensic.datasets import OLIST
from forensic.metrics import monthly_metrics

pytestmark = pytest.mark.skipif(not OLIST.is_available(), reason="Olist data not imported")


@pytest.fixture(scope="module")
def store():
    from forensic.store import get_store
    return get_store("olist")


def test_regions_and_months(store):
    assert set(store.sales["region"]) == {"North", "Northeast", "Center-West", "Southeast", "South"}
    assert store.months[0] == "2017-03" and store.months[-1] == "2018-08"


def test_anomalies_cluster_in_known_real_periods(store):
    df = monthly_metrics(store)
    flagged = df[df["is_anomaly"]]
    share = flagged["month"].isin(["2017-11", "2018-02", "2018-03"]).mean()
    assert 0 < len(flagged) < 0.1 * len(df)      # selective, not everything
    assert share > 0.5                           # Black Friday 2017 and the Feb-Mar 2018 delivery crisis


def test_text_and_timestamps_agree_on_delivery_crisis(store):
    from forensic.agents.rag_agent import classify
    months = [d.date[:7] for d in store.documents if classify(d)["cause"] == "logistics_disruption"]
    assert months and sum(m in ("2017-11", "2018-02", "2018-03") for m in months) / len(months) > 0.7


def test_portuguese_region_names_and_no_inventory_wording():
    from forensic.pipeline import get_investigator
    res = get_investigator("olist").investigate("O que aconteceu com telefonia no nordeste em 2018-03?",
                                                use_llm=False)
    assert (res["plan"]["product_id"], res["plan"]["region"]) == ("TELEPHONY", "Northeast")
    text = " ".join(res["answer"]["layers"].values())
    assert "stock" not in text.lower() and "warehouse" not in text.lower()
    assert "R$" in text


def test_api_dataset_switch():
    from forensic.api import app
    with TestClient(app) as c:
        meta = c.get("/api/meta", params={"dataset": "olist"}).json()
        assert meta["dataset"]["key"] == "olist" and len(meta["examples"]) >= 5
        assert c.get("/api/evaluation", params={"dataset": "olist"}).json()["available"] is False
        assert c.get("/api/meta", params={"dataset": "nope"}).status_code == 404
        r = c.post("/api/investigate", json={"question": "Why did bed bath sales change in the Southeast in 2017-11?",
                                              "dataset": "olist"}).json()
        assert r["plan"]["product_id"] == "BED_BATH_TABLE" and r["answer"]["case"] in ("full", "structured_only")
