"""Ground-truth incident scenarios.

Every scenario is a cause injected on purpose. The generator derives BOTH its structured
signature (sales / inventory numbers) and its unstructured artefact (the document a person
would have written about it) from the same entry, using the shared keys product_id, region
and month. The evaluator later replays each scenario's question and checks that the agents
found this cause - not just a plausible-sounding one.

Coverage:
  * full evidence (numbers + document)            SC01-SC11, SC15-SC17
  * structured only (anomaly, no document)        SC12, SC18
  * unstructured only (document, no anomaly)      SC13, SC14 (SC14 has no sales data at all)
  * controls (no scenario: noise only)            CT01-CT06
"""
from __future__ import annotations

SCENARIOS = [
    {
        "id": "SC01", "product_id": "IPHONE15", "region": "North", "month": "2026-03",
        "cause": "supplier_delay",
        "structured_effect": {"units_sold_pct_change": -18, "stockout_days": 9, "stockout_start_day": 4},
        "doc": {
            "doc_type": "supplier_report", "date": "2026-03-02", "author": "Foxconn Assembly - Account Operations",
            "title": "Supplier Update: iPhone 15 shipments to North region",
            "paragraphs": [
                "This note confirms that the component shipment scheduled for dispatch to the North region "
                "distribution centre (WH_NORTH_01) on 1 March has been delayed by 12 days due to port congestion at Chennai.",
                "Container vessels are waiting an average of nine days for a berth. Our consolidated shipment of display "
                "and camera modules is in the queue, which pushes final assembly and dispatch of iPhone 15 units for North "
                "region retailers to the week of 13 March.",
                "Other regions are served from a different consolidation hub and are not affected. Normal shipment cadence "
                "will resume once the backlog clears; we will confirm a revised schedule in our next update.",
            ],
        },
        "question": "Why did iPhone 15 sales drop in the North region in March 2026?",
        "expected": {"cause": "supplier_delay", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC02", "product_id": "IPHONE15", "region": "West", "month": "2026-04",
        "cause": "quality_issue",
        "structured_effect": {"units_sold_pct_change": -9, "returns_pct_change": 240},
        "doc": {
            "doc_type": "quality_report", "date": "2026-04-06", "author": "Quality Engineering",
            "title": "Quality Control Report: iPhone 15 West region batches",
            "paragraphs": [
                "Batch QC flagged an elevated screen defect rate of 2.1% against a 0.3% baseline in units shipped to "
                "West region stores in early April (batches W-2604-11 to W-2604-19).",
                "Most failures are display flicker and dead-pixel clusters appearing within the first week of use. Field "
                "returns citing a faulty screen have risen sharply at West region stores.",
                "Recommended action: hold the affected batches pending root-cause analysis with the display panel vendor "
                "and prioritise replacement units for affected customers.",
            ],
        },
        "question": "What is going on with iPhone 15 in the West region in April 2026?",
        "expected": {"cause": "quality_issue", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC03", "product_id": "MACBOOKAIR", "region": "South", "month": "2026-03",
        "cause": "promotion",
        "structured_effect": {"units_sold_pct_change": 22, "discount_pct_change": 15},
        "doc": {
            "doc_type": "internal_memo", "date": "2026-02-27", "author": "Regional Manager, South",
            "title": "Internal Memo: South region pre-refresh clearance",
            "paragraphs": [
                "The South regional manager has approved a 15% promotional discount on MacBook Air for the whole of March "
                "to clear pre-refresh inventory ahead of the next model introduction.",
                "Finance notes that the deeper markdown should lift unit volume substantially, but most of the gain will be "
                "offset by the lower realised price, so revenue should rise only slightly. Margin per unit will fall.",
                "The promotion applies to South region retail and online channels only.",
            ],
        },
        "question": "Why did MacBook Air sales jump in the South in March 2026?",
        "expected": {"cause": "promotion", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC04", "product_id": "IPADPRO", "region": "East", "month": "2026-01",
        "cause": "competitor_launch",
        "structured_effect": {"units_sold_pct_change": -14},
        "doc": {
            "doc_type": "market_intel", "date": "2026-01-08", "author": "Market Intelligence Team",
            "title": "Market Intelligence Brief: Tablets, East region",
            "paragraphs": [
                "Competitor A launched its new flagship tablet in the East region on 5 January, bundled with a free keyboard "
                "and a carrier data plan at major electronics chains.",
                "Store walk-throughs and partner feedback indicate that customers in the premium tablet segment are switching "
                "to the rival bundle; sales associates report more comparison shopping than usual.",
                "No comparable launch has happened in North, South or West yet. Expect pressure on iPad Pro volumes in the "
                "East while the rival bundle is available.",
            ],
        },
        "question": "Why are iPad Pro sales down in the East region in January 2026?",
        "expected": {"cause": "competitor_launch", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC05", "product_id": "APPLEWATCH", "region": "North", "month": "2025-12",
        "cause": "marketing_campaign",
        "structured_effect": {"units_sold_pct_change": 30},
        "doc": {
            "doc_type": "internal_memo", "date": "2025-11-25", "author": "Marketing, North region",
            "title": "Internal Memo: North region holiday campaign",
            "paragraphs": [
                "Marketing will run a four-week holiday gifting campaign for Apple Watch across North region TV, outdoor and "
                "social channels from 1 December.",
                "The campaign has no price component: list prices and the standard discount stay unchanged. Store teams should "
                "plan for a demand surge and keep display stock replenished.",
                "Additional inventory has been pre-positioned at WH_NORTH_01 so that the campaign does not cause stock-outs.",
            ],
        },
        "question": "Why did Apple Watch sales spike in the North in December 2025?",
        "expected": {"cause": "marketing_campaign", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC06", "product_id": "AIRPODSPRO", "region": "South", "month": "2026-02",
        "cause": "logistics_disruption",
        "structured_effect": {"units_sold_pct_change": -25, "stockout_days": 11, "stockout_start_day": 9},
        "doc": {
            "doc_type": "logistics_notice", "date": "2026-02-08", "author": "Distribution Operations, South",
            "title": "Logistics Notice: South region transport strike",
            "paragraphs": [
                "A regional trucking strike began on 8 February, halting road transport from the port terminal to WH_SOUTH_01. "
                "Carrier partners have suspended all scheduled deliveries into the South region.",
                "Warehouse stock of AirPods Pro is expected to run out within a day. Inbound pallets are held at the terminal "
                "until the strike is resolved.",
                "Union talks are ongoing; carriers estimate 10 to 12 days before normal delivery schedules resume.",
            ],
        },
        "question": "Why did AirPods Pro sales fall in the South in February 2026?",
        "expected": {"cause": "logistics_disruption", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC07", "product_id": "IPHONE15", "region": "East", "month": "2026-05",
        "cause": "price_increase",
        "structured_effect": {"units_sold_pct_change": -8, "price_pct_change": 6},
        "doc": {
            "doc_type": "internal_memo", "date": "2026-04-28", "author": "Commercial Finance, East",
            "title": "Internal Memo: East region price revision",
            "paragraphs": [
                "Following the new state levy on imported electronics, the East region will apply a 6% price increase to "
                "iPhone 15 from 1 May. Standard discount levels are unchanged.",
                "Commercial expects some price-sensitive customers to defer purchases; a single-digit decline in unit volume "
                "is acceptable given the margin protection.",
            ],
        },
        "question": "Explain the iPhone 15 sales decline in East in May 2026",
        "expected": {"cause": "price_increase", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC08", "product_id": "MACBOOKAIR", "region": "West", "month": "2026-01",
        "cause": "return_policy_change",
        "structured_effect": {"units_sold_pct_change": 4, "returns_pct_change": 90},
        "doc": {
            "doc_type": "policy_update", "date": "2026-01-02", "author": "Customer Experience, West",
            "title": "Policy Update: West region extended return window",
            "paragraphs": [
                "Effective 1 January, the return window for MacBook Air purchased in West region stores is extended from 14 "
                "to 30 days as a pilot of the new customer-satisfaction programme.",
                "Customers may return opened units for a full refund within the extended window, no questions asked. Store "
                "teams should expect a higher volume of returns, most of them in resaleable condition.",
                "The pilot will be reviewed at the end of the quarter.",
            ],
        },
        "question": "Why are MacBook Air returns so high in the West in January 2026?",
        "expected": {"cause": "return_policy_change", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC09", "product_id": "APPLEWATCH", "region": "East", "month": "2026-04",
        "cause": "quality_issue",
        "structured_effect": {"units_sold_pct_change": -6, "returns_pct_change": 180},
        "doc": {
            "doc_type": "quality_report", "date": "2026-04-09", "author": "Quality Engineering",
            "title": "Quality Control Report: Apple Watch heart-rate sensor",
            "paragraphs": [
                "Incoming QC and early field data show a heart-rate sensor failure rate of 1.6% versus a 0.4% baseline in "
                "units shipped to the East region since late March.",
                "Affected units give intermittent readings after a firmware sync, and customers are returning them as faulty. "
                "The defect has been traced to a single sensor lot (HR-0322).",
                "Recommended action: quarantine remaining stock from lot HR-0322 and expedite replacement modules.",
            ],
        },
        "question": "Why did Apple Watch returns rise in the East region in April 2026?",
        "expected": {"cause": "quality_issue", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC10", "product_id": "IPADPRO", "region": "North", "month": "2026-05",
        "cause": "supplier_delay",
        "structured_effect": {"units_sold_pct_change": -15, "stockout_days": 7, "stockout_start_day": 12},
        "doc": {
            "doc_type": "supplier_report", "date": "2026-05-10", "author": "Compal Electronics - Customer Programs",
            "title": "Supplier Update: iPad Pro shipments",
            "paragraphs": [
                "Because of a component shortage of mini-LED backlight units at our panel sub-supplier, iPad Pro shipments to "
                "the North region are delayed by about one week.",
                "We are prioritising open orders by contract date. Distribution centre WH_NORTH_01 will receive its next "
                "shipment around 19 May instead of 12 May.",
                "We will share a recovery schedule once the sub-supplier confirms volumes.",
            ],
        },
        "question": "Why did iPad Pro sales drop in North in May 2026?",
        "expected": {"cause": "supplier_delay", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC11", "product_id": "AIRPODSPRO", "region": "West", "month": "2025-11",
        "cause": "promotion",
        "structured_effect": {"units_sold_pct_change": 28, "discount_pct_change": 10},
        "doc": {
            "doc_type": "internal_memo", "date": "2025-10-30", "author": "Regional Manager, West",
            "title": "Internal Memo: West region Black Friday promotion",
            "paragraphs": [
                "The West region will run a month-long Black Friday promotion on AirPods Pro throughout November, with an "
                "additional 10% discount on top of the standard 5%.",
                "The promotion is funded from the regional budget. Stores should expect a significant volume uplift and plan "
                "staffing accordingly.",
            ],
        },
        "question": "Why were AirPods Pro sales so high in the West in November 2025?",
        "expected": {"cause": "promotion", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC12", "product_id": "IPHONE15", "region": "South", "month": "2026-01",
        "cause": "unexplained_demand_drop",
        "structured_effect": {"units_sold_pct_change": -12},
        "doc": None,  # structured-only: nobody wrote anything down about it
        "question": "Why did iPhone 15 sales drop in the South in January 2026?",
        "expected": {"cause": "demand_decline", "case": "structured_only", "confidence": "medium"},
    },
    {
        "id": "SC13", "product_id": "MACBOOKAIR", "region": "North", "month": "2026-06",
        "cause": "supplier_delay",
        "structured_effect": None,  # document-only: an early warning that has not hit sales yet
        "doc": {
            "doc_type": "supplier_report", "date": "2026-06-12", "author": "Quanta Computer - Account Management",
            "title": "Supplier Advisory: MacBook Air display panels",
            "paragraphs": [
                "We are flagging a potential shortage of display panels for MacBook Air in July, following reduced output at a "
                "panel sub-supplier.",
                "Current shipments to the North region distribution centre are unaffected; the risk applies to orders placed "
                "after 1 July. A shipment delay of up to two weeks is possible.",
                "We will confirm by the end of June whether the delay will materialise.",
            ],
        },
        "question": "Is there any problem with MacBook Air in the North region in June 2026?",
        "expected": {"cause": "supplier_delay", "case": "unstructured_only", "confidence": "medium"},
    },
    {
        "id": "SC14", "product_id": "VISIONPRO", "region": "West", "month": "2026-04",
        "cause": "quality_issue",
        "structured_effect": None,  # Vision Pro has no sales or inventory records at all
        "doc": {
            "doc_type": "customer_feedback", "date": "2026-04-20", "author": "Customer Support Analytics",
            "title": "Customer Feedback Summary: Vision Pro, West region",
            "paragraphs": [
                "Customer feedback in the West region during April is dominated by complaints about display calibration "
                "faults: users report colour drift in one eye after a few days of use.",
                "Store technicians confirm the defect on returned units, and the QC team has opened an investigation into the "
                "affected batch.",
                "Overall satisfaction for Vision Pro in the West fell from 4.5 to 3.6 out of 5.",
            ],
        },
        "question": "Why are Vision Pro sales slowing in the West in April 2026?",
        "expected": {"cause": "quality_issue", "case": "unstructured_only", "confidence": "medium"},
    },
    {
        "id": "SC15", "product_id": "APPLEWATCH", "region": "West", "month": "2026-02",
        "cause": "logistics_disruption",
        "structured_effect": {"units_sold_pct_change": -16, "stockout_days": 6, "stockout_start_day": 15},
        "doc": {
            "doc_type": "logistics_notice", "date": "2026-02-14", "author": "Distribution Operations, West",
            "title": "Logistics Notice: WH_WEST_01 flood closure",
            "paragraphs": [
                "Heavy rain flooded the loading bays at WH_WEST_01 on 14 February. The warehouse is closed while the site is "
                "cleaned and inspected, and inbound transport has been redirected.",
                "Apple Watch stock held on the ground floor was damaged and written off; remaining stock cannot be dispatched "
                "until the warehouse reopens, expected in about six days.",
            ],
        },
        "question": "What happened to Apple Watch sales in the West in February 2026?",
        "expected": {"cause": "logistics_disruption", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC16", "product_id": "AIRPODSPRO", "region": "North", "month": "2026-04",
        "cause": "competitor_launch",
        "structured_effect": {"units_sold_pct_change": -11},
        "doc": {
            "doc_type": "market_intel", "date": "2026-04-03", "author": "Market Intelligence Team",
            "title": "Market Intelligence Brief: Earbuds, North region",
            "paragraphs": [
                "Competitor B launched noise-cancelling earbuds at a much lower price point in the North region in early "
                "April, backed by a heavy in-store presence at telecom retailers.",
                "Partner surveys show a measurable share of premium-earbud shoppers switching to the rival product, "
                "especially in the under-30 segment.",
            ],
        },
        "question": "Why did AirPods Pro sales decline in the North in April 2026?",
        "expected": {"cause": "competitor_launch", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC17", "product_id": "IPADPRO", "region": "South", "month": "2026-03",
        "cause": "promotion",
        "structured_effect": {"units_sold_pct_change": 18, "discount_pct_change": 8},
        "doc": {
            "doc_type": "internal_memo", "date": "2026-02-25", "author": "Regional Manager, South",
            "title": "Internal Memo: South region education promotion",
            "paragraphs": [
                "For the March admissions season the South region will give students and teachers an extra 8% education "
                "discount on iPad Pro.",
                "This promotion runs in all South stores and online. Expect higher unit volume with a modest revenue gain.",
            ],
        },
        "question": "Why did iPad Pro sales go up in the South region in March 2026?",
        "expected": {"cause": "promotion", "case": "full", "confidence": "high"},
    },
    {
        "id": "SC18", "product_id": "HOMEPOD", "region": "East", "month": "2026-03",
        "cause": "unexplained_stockout",
        "structured_effect": {"units_sold_pct_change": -20, "stockout_days": 7, "stockout_start_day": 10},
        "doc": None,  # HomePod has no unstructured documents at all
        "question": "Why did HomePod mini sales fall in the East in March 2026?",
        "expected": {"cause": "supply_disruption", "case": "structured_only", "confidence": "medium"},
    },
]

# Product / region / months with no injected cause. The system must NOT invent one.
CONTROLS = [
    {"id": "CT01", "product_id": "IPHONE15", "region": "North", "month": "2026-01",
     "question": "Why did iPhone 15 sales change in the North region in January 2026?"},
    {"id": "CT02", "product_id": "MACBOOKAIR", "region": "East", "month": "2026-02",
     "question": "What happened to MacBook Air sales in the East in February 2026?"},
    {"id": "CT03", "product_id": "IPADPRO", "region": "West", "month": "2026-04",
     "question": "Why did iPad Pro sales drop in the West in April 2026?"},
    {"id": "CT04", "product_id": "AIRPODSPRO", "region": "East", "month": "2026-03",
     "question": "Explain AirPods Pro performance in the East in March 2026"},
    {"id": "CT05", "product_id": "APPLEWATCH", "region": "South", "month": "2026-05",
     "question": "Why did Apple Watch sales change in the South in May 2026?"},
    {"id": "CT06", "product_id": "HOMEPOD", "region": "South", "month": "2026-02",
     "question": "Why did HomePod mini sales drop in the South in February 2026?"},
]
for _c in CONTROLS:
    _c["expected"] = {"cause": "none", "case": "none", "confidence": "high"}


def structured_scenarios():
    return [s for s in SCENARIOS if s.get("structured_effect")]


def scenario_for(product_id: str, region: str, month: str):
    for s in SCENARIOS:
        if (s["product_id"], s["region"], s["month"]) == (product_id, region, month):
            return s
    return None
