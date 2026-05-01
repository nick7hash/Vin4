"""
pages/payback_page.py — Payback Period page.

Monthly performance tracking view:
  - Bars: CAC
  - Line: Monthly ARPU (net)
  - Optional line: Payback period in days

Formula:
  Payback Days = (CAC / Monthly ARPU) * 30
"""
from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS, _defaults


def payback_layout(default_start=None, default_end=None):
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
            page_header(subtitle="Payback Period Analysis", controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("payback"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    html.Div("Payback Period", className="section-label"),
                    html.Div(
                        [
                            html.Strong("Formula: "),
                            "Payback Days = (CAC ÷ Monthly Net ARPU) × 30",
                            html.Br(),
                            html.Span(
                                "Uses net proceeds (after platform fees).  "
                                "Bars = CAC.  "
                                "Solid line = Monthly ARPU.  "
                                "Optional dotted line (legend toggle) = Payback Days.",
                                style={"color": "#6B7280"},
                            ),
                        ],
                        style={"fontSize": "12px", "fontFamily": "Inter, sans-serif",
                               "color": "#9CA3AF", "marginBottom": "16px"},
                    ),
                    chart_card(
                        title="Payback Period — Monthly CAC vs ARPU",
                        graph_id="chart-payback",
                        height=420,
                    ),
                ]),
            ]),
            page_footer(),
        ],
    )
