import pandas as pd
import pytest

from src.config import CLEAN_CSV, RAW_CSV
from src.data import load_sales
from src.etl.clean_data import clean, clean_frame
from src.etl.pipeline import EtlError, extract, validate
from src.ml.features import FEATURES, VARIANT_FEATURES, add_date_features, build_frame, tableau_week


def good_row(**over) -> dict:
    row = dict(
        row_id=1, order_id="CA-1", customer_id="C1", customer_name="Ann", segment="Consumer", product_id="P1",
        product_name="Phone", category="Technology", sub_category="Phones", city="LA", state="CA", country="US",
        region="West", market="US", market2="North America", order_date="2013-05-01", ship_date="2013-05-04",
        ship_mode="Standard Class", order_priority="High", quantity=2, discount=0.1, sales=100.0, profit=10.0,
        shipping_cost=5.0, year=2013,
    )
    row.update(over)
    return row


def frame(*rows) -> pd.DataFrame:
    return clean_frame(pd.DataFrame(list(rows)))


# ---------------------------------------------------------------- ETL validation
def test_valid_rows_pass():
    r = validate(frame(good_row(), good_row(row_id=2)))
    assert r.report["valid_rows"] == 2 and r.report["rejected_rows"] == 0
    assert r.valid["shipping_days"].tolist() == [3, 3]


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"ship_date": "2013-04-01"}, "ship_before_order"),
        ({"order_date": "not-a-date"}, "invalid_order_date"),
        ({"quantity": 0}, "invalid_quantity"),
        ({"quantity": 1.5}, "invalid_quantity"),
        ({"discount": 1.5}, "invalid_discount"),
        ({"discount": -0.1}, "invalid_discount"),
        ({"sales": -5}, "invalid_sales"),
        ({"shipping_cost": -1}, "invalid_shipping_cost"),
        ({"profit": None}, "invalid_profit"),
        ({"category": None}, "missing_category"),
        ({"customer_id": "  "}, "missing_customer_id"),
        ({"row_id": None}, "invalid_row_id"),
    ],
)
def test_bad_rows_are_rejected_with_reason(override, reason):
    r = validate(frame(good_row(), good_row(**{"row_id": 2, **override})))
    assert r.report["valid_rows"] == 1 and r.report["rejected_rows"] == 1
    assert reason in r.rejected["reject_reason"].iloc[0]
    assert r.report["rejected_by_reason"][reason] == 1


def test_duplicate_row_id_keeps_first():
    r = validate(frame(good_row(), good_row(sales=999.0)))
    assert len(r.valid) == 1 and r.valid["sales"].iloc[0] == 100.0
    assert "duplicate_row_id" in r.rejected["reject_reason"].iloc[0]


def test_exact_duplicate_rows_are_counted():
    r = validate(frame(good_row(), good_row()))
    assert r.report["duplicate_rows"] == 1


def test_missing_required_column_is_an_error():
    df = frame(good_row()).drop(columns=["segment"])
    with pytest.raises(EtlError, match="segment"):
        validate(df)


def test_clean_frame_drops_non_ascii_and_normalises_names():
    raw = pd.DataFrame([{**{k.replace("_", "."): v for k, v in good_row().items()}, "记录数": 1}])
    out = clean_frame(raw)
    assert "记录数" not in out.columns and "order_date" in out.columns and "shipping_days" in out.columns


def test_clean_rejects_missing_core_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="missing expected columns"):
        clean(bad, tmp_path / "out.csv")


def test_real_dataset_is_fully_valid():
    df, path = extract("raw")
    assert path == RAW_CSV
    r = validate(df)
    assert r.report["raw_rows"] == 51290 and r.report["rejected_rows"] == 0
    assert r.report["order_date_range"] == ["2011-01-01", "2014-12-31"]
    assert r.report["year_column_mismatches"] == 0


def test_clean_is_reproducible(tmp_path):
    out = tmp_path / "clean.csv"
    cleaned = clean(RAW_CSV, out)
    assert cleaned.shape[0] == 51290
    pd.testing.assert_frame_equal(pd.read_csv(out), pd.read_csv(CLEAN_CSV), check_dtype=False)


def test_extract_unknown_source_and_missing_file(tmp_path):
    with pytest.raises(EtlError):
        extract("bogus")
    with pytest.raises(EtlError, match="not found"):
        extract("raw", tmp_path / "nope.csv")


# ---------------------------------------------------------------- features
def test_week_number_matches_export_for_every_row():
    df = load_sales()
    assert (tableau_week(df["order_date"]) == df["weeknum"]).all()


def test_date_features():
    out = add_date_features(pd.DataFrame({"order_date": ["2012-01-01", "2014-12-31"]}))
    assert out["year"].tolist() == [2012, 2014]
    assert out["weeknum"].tolist() == [1, 53]
    assert out["quarter"].tolist() == [1, 4]
    assert out["day_of_week"].tolist() == [6, 2]


def test_build_frame_columns_and_variants():
    row = {**good_row(), "shipping_days": 3}
    assert list(build_frame(pd.DataFrame([row])).columns) == FEATURES
    safe = VARIANT_FEATURES["without_shipping_cost"]
    assert "shipping_cost" not in safe and "shipping_cost" in VARIANT_FEATURES["with_shipping_cost"]
    assert list(build_frame(pd.DataFrame([row]), safe).columns) == safe


def test_target_and_identifiers_are_never_features():
    for banned in ("sales", "profit", "row_id", "order_id", "customer_id", "product_id"):
        assert banned not in FEATURES
