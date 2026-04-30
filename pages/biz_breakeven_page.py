"""
pages/biz_breakeven_page.py — Business Break-Even page.

Definition: first month where:
  Cumulative Net Proceeds >= Cumulative Ad Spend

Tracks:
  - Running total net proceeds (green)
  - Running total ad spend (red)
  - Net position = proceeds − spend (purple dotted)

Highlights the exact intersection month.
"""
from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS, _defaults


def biz_breakeven_layout(default_start=None, default_end=None):
    _start, _end = _defaults()
    default_start = default_start or _start
    default_end   = default_end   or _end
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
            page_header(subtitle="Business Break-Even Analysis", controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("biz-breakeven"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    html.Div("Business Break-Even", className="section-label"),
                    html.Div(
                        [
                            html.Strong("Definition: "),
                            "First month where Cumulative Net Proceeds ≥ Cumulative Ad Spend",
                            html.Br(),
                            html.Span(
                                "Green = cumulative proceeds.  "
                                "Red = cumulative ad spend.  "
                                "Purple dotted = net position (proceeds − spend).",
                                style={"color": "#6B7280"},
                            ),
                        ],
                        style={"fontSize": "12px", "fontFamily": "Inter, sans-serif",
                               "color": "#9CA3AF", "marginBottom": "16px"},
                    ),
                    chart_card(
                        title="Business Break-Even — Cumulative Proceeds vs Ad Spend",
                        graph_id="chart-biz-breakeven",
                        height=420,
                    ),
                ]),
            ]),
            page_footer(),
        ],
    )
