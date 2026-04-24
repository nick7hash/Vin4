"""
app.py — Vinita Analytics Dashboard
Plotly Dash · BigQuery · Dark SaaS UI
"""

from datetime import date, timedelta

import dash
from dash import dcc, html, Input, Output, callback_context
import dash_bootstrap_components as dbc

from data import (
    get_default_dates, get_country_options,
    load_kpi_data, get_proceeds_trend,
    get_arpu_daily, get_arpu_by_platform,
)
from components import (
    kpi_card, chart_card, granularity_control,
    proceeds_figure, arpu_line_figure, arpu_platform_figure,
    fmt_currency, fmt_count,
)

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="Vinita Analytics",
    update_title=None,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "theme-color", "content": "#0B0F1A"},
    ],
)
server = app.server

# ── Loading screen injected via index_string ──────────────────────────────────
app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
  </head>
  <body>
    <!-- Full-screen loading overlay with blinking logo -->
    <div id="initial-loading">
      <img class="loading-logo" src="/assets/logo.png" alt="Vinita" />
      <div class="loading-label">Vinita Analytics</div>
    </div>

    {%app_entry%}

    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>

    <script>
      window.addEventListener('load', function () {
        setTimeout(function () {
          var el = document.getElementById('initial-loading');
          if (el) {
            el.classList.add('fade-out');
            setTimeout(function () { el.remove(); }, 700);
          }
        }, 1800);
      });
    </script>
  </body>
</html>"""

# ── Favicon ───────────────────────────────────────────────────────────────────
app.title = "Vinita Analytics"

# ── Default dates (fetched once at startup) ───────────────────────────────────
_default_start, _default_end = get_default_dates()
print(f"[app] Default date range: {_default_start} -> {_default_end}")

# ── Layout ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div(
        className="app-shell",
        children=[
            # ── Stores ──
            dcc.Store(id="store-dates",
                      data={"start": str(_default_start), "end": str(_default_end)}),

            # ── Auto-refresh every 5 min ──
            dcc.Interval(id="interval", interval=300_000, n_intervals=0),

            # ══════════════ HEADER ══════════════
            html.Header(className="app-header", children=[

                # Brand
                html.Div(className="header-brand", children=[
                    html.Div(
                        html.Img(src="/assets/logo.png", alt="Vinita"),
                        className="header-logo",
                    ),
                    html.Div([
                        html.Div("Vinita Analytics", className="header-title"),
                        html.Div("Revenue Intelligence", className="header-sub"),
                    ]),
                ]),

                # Controls
                html.Div(className="header-controls", children=[

                    # Country filter (no "All Countries" option)
                    dcc.Dropdown(
                        id="filter-country",
                        options=[],          # populated by callback
                        value=None,
                        clearable=True,
                        searchable=True,
                        placeholder="Filter by country…",
                        className="country-dropdown",
                        style={
                            "width": "190px", "fontSize": "12.5px",
                            "fontFamily": "Inter, sans-serif",
                        },
                    ),

                    # Date range picker
                    dcc.DatePickerRange(
                        id="filter-dates",
                        min_date_allowed=date(2020, 1, 1),
                        max_date_allowed=date.today(),
                        initial_visible_month=_default_start,
                        start_date=_default_start,
                        end_date=_default_end,
                        display_format="MMM D, YYYY",
                        style={"fontSize": "12.5px"},
                    ),
                ]),
            ]),

            # ══════════════ MAIN ══════════════
            html.Main(className="main-content", children=[

                dcc.Loading(type="default", color="#A855F7", children=[

                    # ── 3 KPI scorecards ──
                    html.Div("Key Metrics", className="section-label"),
                    html.Div(id="kpi-grid", className="kpi-grid"),

                    html.Div(className="divider"),

                    # ── Proceeds trend chart ──
                    html.Div("Trends", className="section-label"),
                    chart_card(
                        title="Proceeds Over Time",
                        graph_id="chart-proceeds",
                        controls=[granularity_control("gran-proceeds", "Day")],
                    ),

                    # ── ARPU charts row ──
                    html.Div("ARPU Analysis", className="section-label"),
                    html.Div(className="chart-row", children=[
                        chart_card(
                            title="ARPU Over Time",
                            graph_id="chart-arpu-line",
                            controls=[granularity_control("gran-arpu", "Day")],
                        ),
                        chart_card(
                            title="ARPU by Platform",
                            graph_id="chart-arpu-platform",
                        ),
                    ]),
                ]),
            ]),
        ],
    )


app.layout = layout

# ── Callback 1: Populate country dropdown ──────────────────────────────────────
@app.callback(
    Output("filter-country", "options"),
    Input("interval", "n_intervals"),
    prevent_initial_call=False,
)
def load_countries(_):
    try:
        return get_country_options()
    except Exception as e:
        print(f"[app] load_countries: {e}")
        return []


# ── Callback 2: KPI scorecards ─────────────────────────────────────────────────
@app.callback(
    Output("kpi-grid", "children"),
    Input("filter-dates",   "start_date"),
    Input("filter-dates",   "end_date"),
    Input("filter-country", "value"),
    Input("interval",       "n_intervals"),
    prevent_initial_call=False,
)
def update_kpis(start, end, country, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)

    try:
        m = load_kpi_data(start, end, country)
    except Exception as e:
        print(f"[app] update_kpis: {e}")
        m = {"gross_revenue": 0, "proceeds": 0, "spend": 0,
             "gr_delta": 0, "pr_delta": 0, "sp_delta": 0}

    return [
        kpi_card("gr",  "Gross Revenue", fmt_currency(m["gross_revenue"]),
                 subtitle=f"{start} → {end}", delta=m["gr_delta"],
                 icon="💰", featured=True),
        kpi_card("pr",  "Proceeds",      fmt_currency(m["proceeds"]),
                 subtitle=f"{start} → {end}", delta=m["pr_delta"],
                 icon="🏦", featured=True),
        kpi_card("sp",  "Spend",         fmt_currency(m["spend"]),
                 subtitle=f"{start} → {end}", delta=m["sp_delta"],
                 icon="📣", featured=True),
    ]


# ── Callback 3: Proceeds trend chart ──────────────────────────────────────────
@app.callback(
    Output("chart-proceeds", "figure"),
    Input("filter-dates",   "start_date"),
    Input("filter-dates",   "end_date"),
    Input("filter-country", "value"),
    Input("gran-proceeds",  "value"),
    Input("interval",       "n_intervals"),
    prevent_initial_call=False,
)
def update_proceeds(start, end, country, gran, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        df = get_proceeds_trend(start, end, country)
        return proceeds_figure(df, gran or "Day")
    except Exception as e:
        print(f"[app] update_proceeds: {e}")
        from components import _empty_figure
        return _empty_figure(f"Error: {e}")


# ── Callback 4: ARPU line + platform bar ──────────────────────────────────────
@app.callback(
    Output("chart-arpu-line",     "figure"),
    Output("chart-arpu-platform", "figure"),
    Input("filter-dates", "start_date"),
    Input("filter-dates", "end_date"),
    Input("gran-arpu",    "value"),
    Input("interval",     "n_intervals"),
    prevent_initial_call=False,
)
def update_arpu(start, end, gran, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        df_daily    = get_arpu_daily(start, end)
        df_platform = get_arpu_by_platform(start, end)
        return (
            arpu_line_figure(df_daily, gran or "Day"),
            arpu_platform_figure(df_platform),
        )
    except Exception as e:
        print(f"[app] update_arpu: {e}")
        from components import _empty_figure
        empty = _empty_figure(f"Error: {e}")
        return empty, empty


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
