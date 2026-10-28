"""Static reference data: products, suppliers, regions and warehouses.

The company is Apple for the demo; swapping these lists is all it takes to demo another
company - the schema and the agents do not change.
"""
from __future__ import annotations

REGIONS = ["North", "South", "East", "West"]
REGION_WEIGHT = {"North": 1.0, "South": 0.85, "East": 0.9, "West": 1.1}
WAREHOUSE = {r: f"WH_{r.upper()}_01" for r in REGIONS}

# base_daily_units: average units per day in a region of weight 1.0.
# HOMEPOD has sales data but no documents; VISIONPRO has documents but no sales data -
# together they exercise the "one side missing" rules.
PRODUCTS = [
    {"product_id": "IPHONE15", "product_name": "iPhone 15", "category": "Smartphones",
     "launch_date": "2025-09-20", "unit_price": 799.0, "supplier_id": "SUP_FOXCONN",
     "base_daily_units": 1400, "aliases": ["iphone 15", "iphone15", "iphone"]},
    {"product_id": "MACBOOKAIR", "product_name": "MacBook Air", "category": "Laptops",
     "launch_date": "2025-03-10", "unit_price": 1099.0, "supplier_id": "SUP_QUANTA",
     "base_daily_units": 500, "aliases": ["macbook air", "macbookair", "macbook", "mba"]},
    {"product_id": "IPADPRO", "product_name": "iPad Pro", "category": "Tablets",
     "launch_date": "2025-05-15", "unit_price": 999.0, "supplier_id": "SUP_COMPAL",
     "base_daily_units": 600, "aliases": ["ipad pro", "ipadpro", "ipad"]},
    {"product_id": "APPLEWATCH", "product_name": "Apple Watch", "category": "Wearables",
     "launch_date": "2025-09-20", "unit_price": 399.0, "supplier_id": "SUP_LUXSHARE",
     "base_daily_units": 800, "aliases": ["apple watch", "applewatch", "watch"]},
    {"product_id": "AIRPODSPRO", "product_name": "AirPods Pro", "category": "Audio",
     "launch_date": "2025-09-20", "unit_price": 249.0, "supplier_id": "SUP_LUXSHARE",
     "base_daily_units": 1100, "aliases": ["airpods pro", "airpodspro", "airpods", "air pods"]},
    {"product_id": "HOMEPOD", "product_name": "HomePod mini", "category": "Smart Home",
     "launch_date": "2024-11-01", "unit_price": 99.0, "supplier_id": "SUP_INVENTEC",
     "base_daily_units": 300, "aliases": ["homepod mini", "homepod", "home pod"]},
    {"product_id": "VISIONPRO", "product_name": "Vision Pro", "category": "Spatial Computing",
     "launch_date": "2026-02-02", "unit_price": 3499.0, "supplier_id": "SUP_LUXSHARE",
     "base_daily_units": 0, "aliases": ["vision pro", "visionpro", "vision"]},
]

SUPPLIERS = [
    {"supplier_id": "SUP_FOXCONN", "supplier_name": "Foxconn Assembly", "region_served": "All",
     "avg_lead_time_days": 14, "reliability_score": 0.91, "role": "primary", "product_ids": "IPHONE15"},
    {"supplier_id": "SUP_PEGATRON", "supplier_name": "Pegatron", "region_served": "All",
     "avg_lead_time_days": 18, "reliability_score": 0.87, "role": "backup", "product_ids": "IPHONE15"},
    {"supplier_id": "SUP_QUANTA", "supplier_name": "Quanta Computer", "region_served": "All",
     "avg_lead_time_days": 21, "reliability_score": 0.89, "role": "primary", "product_ids": "MACBOOKAIR"},
    {"supplier_id": "SUP_COMPAL", "supplier_name": "Compal Electronics", "region_served": "All",
     "avg_lead_time_days": 18, "reliability_score": 0.88, "role": "primary", "product_ids": "IPADPRO"},
    {"supplier_id": "SUP_WISTRON", "supplier_name": "Wistron", "region_served": "All",
     "avg_lead_time_days": 20, "reliability_score": 0.84, "role": "backup", "product_ids": "MACBOOKAIR;IPADPRO"},
    {"supplier_id": "SUP_LUXSHARE", "supplier_name": "Luxshare Precision", "region_served": "All",
     "avg_lead_time_days": 12, "reliability_score": 0.93, "role": "primary",
     "product_ids": "APPLEWATCH;AIRPODSPRO;VISIONPRO"},
    {"supplier_id": "SUP_GOERTEK", "supplier_name": "Goertek", "region_served": "All",
     "avg_lead_time_days": 16, "reliability_score": 0.85, "role": "backup", "product_ids": "APPLEWATCH;AIRPODSPRO"},
    {"supplier_id": "SUP_INVENTEC", "supplier_name": "Inventec Appliances", "region_served": "All",
     "avg_lead_time_days": 15, "reliability_score": 0.90, "role": "primary", "product_ids": "HOMEPOD"},
]

PRODUCT_BY_ID = {p["product_id"]: p for p in PRODUCTS}
SUPPLIER_BY_ID = {s["supplier_id"]: s for s in SUPPLIERS}

# Cause taxonomy. "family" is the structured signature each cause leaves in the tables.
CAUSES = {
    "supplier_delay": {"label": "Supplier delay", "families": ["supply"]},
    "logistics_disruption": {"label": "Logistics disruption", "families": ["supply"]},
    "quality_issue": {"label": "Product quality issue", "families": ["returns", "demand_down"]},
    "return_policy_change": {"label": "Return-policy change", "families": ["returns", "demand_up"]},
    "promotion": {"label": "Promotional discount", "families": ["discount", "demand_up"]},
    "price_increase": {"label": "Price increase", "families": ["price", "demand_down"]},
    "competitor_launch": {"label": "Competitor launch", "families": ["demand_down"]},
    "marketing_campaign": {"label": "Marketing campaign", "families": ["demand_up"]},
}

# What we can say from the tables alone, when no document explains the anomaly.
STRUCTURED_HYPOTHESES = {
    "supply": ("supply_disruption", "Supply disruption (stock-out)"),
    "returns": ("quality_or_returns_issue", "Quality or returns issue"),
    "discount": ("promotion", "Promotional discount"),
    "price": ("price_increase", "Price increase"),
    "demand_up": ("demand_surge", "Unexplained demand surge"),
    "demand_down": ("demand_decline", "Unexplained demand decline"),
}
