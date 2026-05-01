"""
pages/breakeven_page.py — Break-Even Point page.

Visualises the point where cumulative cohort revenue per user crosses CAC.

  Line 1 (dashed): Flat horizontal = CAC (constant cost to acquire a user)
  Line 2 (solid):  Rising cumulative cohort net revenue per user
  Intersection:    Break-even month (annotated per country)

No visible filters. This page shows a simple per-country break-even view.
"""
from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS, _defaults


def breakeven_layout(default_start=None, default_end=None):
    _start, _end = _defaults()
    default_start = default_start or "2025-01-01"
    default_end   = default_end   or "2025-12-31"
    controls = []

    return html.Div(
        className="app-shell",
        children=[
            dcc.Interval(id="interval", interval=300_000, n_intervals=0),
            page_header(subtitle="Break-Even Point Analysis", controls=controls),
            # Keep shared filter IDs mounted (hidden) to avoid cross-page callback errors.
            html.Div(style={"display": "none"}, children=[
                dcc.Dropdown(id="filter-platform", options=[], value=None),
                dcc.Dropdown(id="filter-country", options=LTV_COUNTRY_OPTIONS, value=None),
                dcc.DatePickerRange(
                    id="filter-dates",
                    min_date_allowed="2020-01-01",
                    max_date_allowed="2026-12-31",
                    initial_visible_month=default_start,
                    start_date=default_start,
                    end_date=default_end,
                    display_format="MMM D, YYYY",
                ),
            ]),

            html.Main(className="main-content", children=[
                page_tab_nav("breakeven"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    html.Div("Break-Even Point", className="section-label"),
                    html.Div(
                        [
                            html.Strong("Simple view: "),
                            "Break-Even = first month where cumulative proceeds per user crosses CAC.",
                            html.Br(),
                            html.Span(
                                "CAC line is flat. Cumulative net proceeds per user rises month by month.  "
                                "Break-even is where the rising line crosses CAC.  "
                                "Chart is shown per country.",
                                style={"color": "#6B7280"},
                            ),
                        ],
                        style={"fontSize": "12px", "fontFamily": "Inter, sans-serif",
                               "color": "#9CA3AF", "marginBottom": "16px"},
                    ),
                    chart_card(
                        title="Break-Even Point — CAC vs Cumulative Net Proceeds/User",
                        graph_id="chart-breakeven",
                        height=420,
                    ),
                ]),
            ]),
            page_footer(),
        ],
    )
