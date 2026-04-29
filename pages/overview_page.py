from dash import html, dcc
from components import chart_card, drilldown_control
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS

def overview_layout(default_start, default_end):
    # Standard Controls for the Header
    controls = [
        dcc.Dropdown(
            id="filter-platform",
            options=[],
            value=None,
            clearable=True,
            searchable=True,
            placeholder="Platform…",
            className="platform-dropdown",
            style={
                "width": "160px", "fontSize": "12.5px",
                "fontFamily": "Inter, sans-serif",
            },
        ),
        dcc.Dropdown(
            id="filter-country",
            options=LTV_COUNTRY_OPTIONS,
            value=None,
            clearable=True,
            searchable=True,
            placeholder="Country…",
            className="country-dropdown",
            style={
                "width": "200px", "fontSize": "12.5px",
                "fontFamily": "Inter, sans-serif",
            },
        ),
        dcc.DatePickerRange(
            id="filter-dates",
            min_date_allowed="2020-01-01",
            max_date_allowed="2026-12-31",  # Placeholder
            initial_visible_month=default_start,
            start_date=default_start,
            end_date=default_end,
            display_format="MMM D, YYYY",
            style={"fontSize": "12.5px"},
        ),
    ]

    return html.Div(
        className="app-shell",
        children=[
            # Stores (Hidden Memory)
            dcc.Store(id="store-dates", data={"start": str(default_start), "end": str(default_end)}),
            dcc.Store(id="store-granularity", data={"proceeds": "Day", "arpu": "Day", "conversion": "Day"}),
            dcc.Interval(id="interval", interval=300_000, n_intervals=0),

            page_header(controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("overview"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    # KPI Scorecards
                    html.Div("Key Metrics", className="section-label"),
                    html.Div(id="kpi-grid", className="kpi-grid"),

                    html.Div(className="divider"),

                    # Trends
                    html.Div("Trends", className="section-label"),
                    chart_card(
                        title="Proceeds Over Time",
                        graph_id="chart-proceeds",
                        controls=[drilldown_control("gran-proceeds", "Day")],
                    ),

                    # ARPU Analysis
                    html.Div("ARPU Analysis", className="section-label"),
                    html.Div(className="chart-row", children=[
                        chart_card(
                            title="ARPU Over Time",
                            graph_id="chart-arpu-line",
                            controls=[drilldown_control("gran-arpu", "Day")],
                        ),
                        chart_card(
                            title="Installs to Paid Conversion Rate",
                            graph_id="chart-conversion",
                            controls=[drilldown_control("gran-conversion", "Day")],
                        ),
                    ]),

                    html.Div(className="divider"),

                    # Customer & Revenue Metrics (Minus CAC and LTV which are moved)
                    html.Div("Customer & Revenue Metrics", className="section-label"),
                    html.Div(className="chart-row", children=[
                        chart_card(title="Monthly Churn Rate", graph_id="chart-churn"),
                        chart_card(title="Return on Ad Spend (ROAS)", graph_id="chart-roas"),
                    ]),
                ]),
            ]),
            page_footer()
        ],
    )
