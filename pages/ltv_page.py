"""
pages/ltv_page.py — Lifetime Value (LTV) page.

Shows:
  1. LTV (Net) monthly trend chart
  2. LTV by Cohort (heatmap/line chart) — moved here from Overview
"""
from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS, _defaults


def ltv_layout(default_start=None, default_end=None):
    _start, _end = _defaults()
    default_start = default_start or _start
    default_end   = default_end   or _end
    controls = [
        dcc.Dropdown(
            id="filter-platform",
            options=[],
            value=None, clearable=True, searchable=True,
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
            page_header(subtitle="Lifetime Value Analysis", controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("ltv"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    # ── LTV (Net) monthly trend ──
                    html.Div("LTV (Net) — Monthly Trend", className="section-label"),
                    html.Div(
                        "Formula: LTV (Net) = (Monthly Net ARPU) ÷ (Monthly Churn Rate)",
                        className="section-description",
                        style={"color": "#6B7280", "fontSize": "12px",
                               "fontFamily": "Inter, sans-serif", "marginBottom": "12px"},
                    ),
                    chart_card(title="LTV (Net) Over Time", graph_id="chart-ltv-net"),

                    html.Div(className="divider"),

                    # ── LTV by Cohort ──
                    html.Div("LTV by Cohort", className="section-label"),
                    html.Div(className="ltv-country-filter", children=[
                        html.Span("Filter by Country:", className="ltv-country-label"),
                        dcc.Dropdown(
                            id="filter-ltv-country",
                            options=LTV_COUNTRY_OPTIONS,
                            value=None, clearable=True, searchable=False,
                            placeholder="All countries…", className="country-dropdown",
                            style={"width": "220px", "fontSize": "12.5px",
                                   "fontFamily": "Inter, sans-serif"},
                        ),
                    ]),
                    chart_card(
                        title="Lifetime Value by Cohort (click legend to show/hide 180d & 365d)",
                        graph_id="chart-ltv",
                        height=400,
                    ),
                ]),
            ]),
            page_footer(),
        ],
    )
