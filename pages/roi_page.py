"""
pages/roi_page.py — Return on Investment (ROI) page.

Formula: ROI = ((LTV - CAC) / CAC) * 100

LTV is net-proceeds-based (realized_ltv from cohort table).
Shows ROI across 4 horizons: 3m, 6m, 12m, Full LTV.
  - 4 KPI summary cards (top row)
  - Monthly ROI trend line chart (bottom)
"""
from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS, _defaults


def roi_layout(default_start=None, default_end=None):
    _start, _end = _defaults()
    default_start = default_start or "2025-01-01"
    default_end   = default_end   or "2025-12-31"
    controls = [
        dcc.Dropdown(
            id="filter-platform",
            options=[], value=None, clearable=True, searchable=True,
            placeholder="Platform…", className="platform-dropdown",
            style={"width": "160px", "fontSize": "12.5px", "fontFamily": "Inter, sans-serif"},
        ),
        dcc.Dropdown(
            id="filter-country",
            options=LTV_COUNTRY_OPTIONS,
            value=None, clearable=True, searchable=True,
            placeholder="Country…", className="country-dropdown",
            style={"width": "200px", "fontSize": "12.5px", "fontFamily": "Inter, sans-serif"},
        ),
        dcc.DatePickerRange(
            id="filter-dates",
            min_date_allowed="2020-01-01", max_date_allowed="2026-12-31",
            initial_visible_month=default_start,
            start_date=default_start, end_date=default_end,
            display_format="MMM D, YYYY", style={"fontSize": "12.5px"},
        ),
    ]

    return html.Div(
        className="app-shell",
        children=[
            dcc.Interval(id="interval", interval=300_000, n_intervals=0),
            page_header(subtitle="ROI — Return on Investment", controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("roi"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    # ── ROI formula note ──
                    html.Div("ROI by Horizon", className="section-label"),
                    html.Div(
                        [
                            html.Strong("Formula: "),
                            "ROI = ((LTV − CAC) ÷ CAC) × 100",
                            html.Br(),
                            html.Span(
                                "LTV is net-proceeds-based (not gross revenue).  "
                                "Positive ROI = profitable cohort at that horizon.",
                                style={"color": "#6B7280"},
                            ),
                        ],
                        style={"fontSize": "12px", "fontFamily": "Inter, sans-serif",
                               "color": "#9CA3AF", "marginBottom": "16px"},
                    ),

                    # ── 4 ROI summary cards ──
                    html.Div(id="roi-kpi-grid", className="kpi-grid"),

                    html.Div(className="divider"),

                    # ── Monthly ROI trend ──
                    html.Div("ROI Trend Over Time", className="section-label"),
                    html.Div(
                        "Shows how the 3m / 6m / 12m ROI ratio has changed month-over-month.",
                        style={"fontSize": "12px", "fontFamily": "Inter, sans-serif",
                               "color": "#6B7280", "marginBottom": "12px"},
                    ),
                    chart_card(
                        title="Monthly ROI by Horizon (3m / 6m / 12m)",
                        graph_id="chart-roi-trend",
                        height=360,
                    ),
                ]),
            ]),
            page_footer(),
        ],
    )
