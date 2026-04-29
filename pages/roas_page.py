"""
pages/roas_page.py — ROAS page (renamed from Facebook).

Shows ROAS = Revenue / Ad Spend, with Country → Campaign → Ad drill-down.
KPI cards removed per user request.
"""
from datetime import date
from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer


def roas_layout():
    fb_start = date(2025, 1, 1)
    fb_end   = date(2025, 12, 31)

    controls = [
        dcc.Dropdown(
            id="fb-filter-platform",
            options=[
                {"label": "iOS",     "value": "ios"},
                {"label": "Android", "value": "android"},
            ],
            value=None, clearable=True, searchable=False,
            placeholder="Platform…", className="platform-dropdown",
            style={"width": "160px", "fontSize": "12.5px", "fontFamily": "Inter, sans-serif"},
        ),
        dcc.DatePickerRange(
            id="fb-filter-dates",
            min_date_allowed=date(2020, 1, 1), max_date_allowed=date.today(),
            initial_visible_month=fb_end,
            start_date=fb_start, end_date=fb_end,
            display_format="MMM D, YYYY", style={"fontSize": "12.5px"},
        ),
    ]

    return html.Div(
        className="app-shell",
        children=[
            dcc.Store(id="store-roas-drill",
                      data={"level": "country", "filter_country": None, "filter_campaign": None}),
            dcc.Interval(id="fb-interval", interval=300_000, n_intervals=0),

            page_header(subtitle="ROAS — Return on Ad Spend", controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("roas"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    # ── ROAS type toggle + summary ──
                    html.Div(
                        className="section-label",
                        children=[
                            html.Span("ROAS Breakdown "),
                            html.Span(
                                "ⓘ",
                                title="True ROAS uses net proceeds (revenue halved, fee applied). "
                                      "Meta-Reported uses raw purchase value.",
                                style={"cursor": "help", "fontSize": "13px", "color": "#A855F7"},
                            ),
                        ],
                    ),
                    html.Div(className="true-roas-header", children=[
                        dcc.RadioItems(
                            id="toggle-roas-type",
                            options=[
                                {"label": " True ROAS",      "value": "true"},
                                {"label": " Meta-Reported",  "value": "meta"},
                            ],
                            value="true", inline=True,
                            className="ios-fee-radio",
                            inputClassName="ios-fee-input",
                            labelClassName="ios-fee-radio-label",
                        ),
                        html.Div(id="roas-summary", className="roas-summary"),
                    ]),

                    # ── Drill-down chart ──
                    chart_card(
                        title="ROAS by Country / Campaign / Ad",
                        graph_id="chart-true-roas",
                        height=550,
                        controls=[
                            html.Div(className="drill-buttons", children=[
                                html.Button("Country",  id="drill-country",  className="drill-btn drill-btn--active", n_clicks=0),
                                html.Button("Campaign", id="drill-campaign", className="drill-btn", n_clicks=0),
                                html.Button("Ad",       id="drill-ad",       className="drill-btn", n_clicks=0),
                            ]),
                        ],
                    ),
                ]),
            ]),
            page_footer(),
        ],
    )
