from dash import html, dcc
from components import chart_card
from .shared import page_header, page_tab_nav, page_footer, LTV_COUNTRY_OPTIONS

def cac_layout(default_start, default_end):
    # Standard Controls for the Header (same as Overview to retain global filter context)
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
            max_date_allowed="2026-12-31",
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
            dcc.Interval(id="interval", interval=300_000, n_intervals=0),

            page_header(controls=controls),

            html.Main(className="main-content", children=[
                page_tab_nav("cac"),

                dcc.Loading(type="default", color="#4B5563", children=[
                    html.Div("Customer Acquisition Cost (CAC)", className="section-label"),
                    
                    html.Div(className="chart-row", children=[
                        chart_card(
                            title="CAC Over Time",
                            graph_id="chart-cac",
                        ),
                        chart_card(
                            title="CAC vs LTV Thresholds",
                            graph_id="chart-cac-ltv",
                        ),
                    ]),
                ]),
            ]),
            page_footer()
        ],
    )
