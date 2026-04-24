"""
app.py — Vinita Analytics Dashboard
Plotly Dash · BigQuery · Dark SaaS UI
"""

from datetime import date, timedelta

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

from data import (
    get_default_dates, get_country_options, get_platform_options,
    load_kpi_data, get_proceeds_trend,
    get_arpu_daily, get_arpu_by_platform,
    get_monthly_churn, get_cohort_ltv_data,
    get_roas_data, get_cac_data,
    get_cac_ltv_thresholds,
)
from components import (
    kpi_card, chart_card, granularity_control, drilldown_control,
    proceeds_figure, arpu_line_figure, arpu_platform_figure,
    churn_figure, ltv_cohort_figure, roas_figure, cac_figure,
    cac_ltv_threshold_figure,
    fmt_currency, fmt_count,
)

# ── App ───────────────────────────────────────────────────────────────────────
dash_app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="Vinita Analytics",
    update_title=None,
    external_stylesheets=[dbc.themes.BOOTSTRAP, "/assets/style.css"],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "theme-color", "content": "#0B0F1A"},
    ],
)
app = dash_app.server

# ── Loading screen injected via index_string ──────────────────────────────────
dash_app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <!-- Dark-mode overrides for react-dates (Dash DatePickerRange) -->
    <style>
      .DateRangePickerInput,.DateRangePickerInput__withBorder{
        background:#111827!important;border:1px solid #374151!important;
        border-radius:8px!important;display:flex!important;align-items:center!important;
      }
      .DateInput{background:transparent!important;width:110px!important;}
      .DateInput_input{
        background:transparent!important;color:#E5E7EB!important;
        font-family:'Inter',sans-serif!important;font-size:12.5px!important;
        border-bottom:2px solid transparent!important;padding:6px 8px!important;
        caret-color:#A855F7!important;
      }
      .DateInput_input::placeholder{color:#6B7280!important;}
      .DateInput_input__focused{border-bottom:2px solid #A855F7!important;}
      .DateRangePickerInput_arrow{color:#6B7280!important;padding:0 4px!important;}
      .DateRangePicker_picker{
        background:#1F2937!important;border:1px solid #374151!important;
        border-radius:12px!important;z-index:9999!important;
      }
      .DayPicker,.CalendarMonthGrid,.CalendarMonth{
        background:#1F2937!important;
      }
      .DayPicker__withBorder{
        box-shadow:0 8px 32px rgba(0,0,0,.6)!important;
        border-radius:12px!important;border:none!important;
      }
      .CalendarMonth_caption{color:#E5E7EB!important;font-family:'Inter',sans-serif!important;font-weight:600!important;}
      .DayPicker_weekHeader_li small{color:#6B7280!important;}
      .CalendarDay__default{
        background:transparent!important;color:#D1D5DB!important;
        border:1px solid transparent!important;
      }
      .CalendarDay__default:hover{
        background:rgba(124,58,237,.2)!important;color:#fff!important;
        border-color:#7C3AED!important;border-radius:4px!important;
      }
      .CalendarDay__selected,.CalendarDay__selected:hover,.CalendarDay__selected:active{
        background:#7C3AED!important;color:#fff!important;border-color:#7C3AED!important;
        border-radius:4px!important;
      }
      .CalendarDay__selected_span{
        background:rgba(124,58,237,.25)!important;color:#E5E7EB!important;
        border-color:rgba(124,58,237,.3)!important;
      }
      .CalendarDay__hovered_span,.CalendarDay__hovered_span:hover{
        background:rgba(124,58,237,.15)!important;color:#E5E7EB!important;
        border-color:rgba(124,58,237,.2)!important;
      }
      .CalendarDay__blocked_out_of_range,.CalendarDay__blocked_out_of_range:hover{
        color:#374151!important;background:transparent!important;
      }
      .DayPickerNavigation_button{
        background:transparent!important;border:1px solid #374151!important;
        border-radius:6px!important;
      }
      .DayPickerNavigation_button:hover{border-color:#A855F7!important;}
      .DayPickerNavigation_svg__horizontal{fill:#9CA3AF!important;}
    </style>
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

dash_app.title = "Vinita Analytics"

# ── Default dates (fetched once at startup) ───────────────────────────────────
_default_start, _default_end = get_default_dates()
print(f"[app] Default date range: {_default_start} -> {_default_end}")

# ── LTV country options (fixed: AU, CA, GB, US) ───────────────────────────────
LTV_COUNTRY_OPTIONS = [
    {"label": "🇦🇺 Australia",      "value": "AU"},
    {"label": "🇨🇦 Canada",         "value": "CA"},
    {"label": "🇬🇧 United Kingdom", "value": "GB"},
    {"label": "🇺🇸 United States",  "value": "US"},
]

# ── Layout ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div(
        className="app-shell",
        children=[
            # ── Stores ──
            # Granularity state stored client-side; survives callbacks without BQ re-query
            dcc.Store(id="store-dates",
                      data={"start": str(_default_start), "end": str(_default_end)}),
            dcc.Store(id="store-granularity", data={"proceeds": "Day", "arpu": "Day"}),

            # Auto-refresh every 5 min
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

                    # Platform filter
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

                    # Country filter
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

                dcc.Loading(type="default", color="#4B5563", children=[

                    # ── KPI scorecards ──
                    html.Div("Key Metrics", className="section-label"),
                    html.Div(id="kpi-grid", className="kpi-grid"),

                    html.Div(className="divider"),

                    # ── Proceeds trend chart ──
                    html.Div("Trends", className="section-label"),
                    chart_card(
                        title="Proceeds Over Time",
                        graph_id="chart-proceeds",
                        controls=[drilldown_control("gran-proceeds", "Day")],
                    ),

                    # ── ARPU charts row ──
                    html.Div("ARPU Analysis", className="section-label"),
                    html.Div(className="chart-row", children=[
                        chart_card(
                            title="ARPU Over Time",
                            graph_id="chart-arpu-line",
                            controls=[drilldown_control("gran-arpu", "Day")],
                        ),
                        chart_card(
                            title="ARPU by Platform",
                            graph_id="chart-arpu-platform",
                        ),
                    ]),

                    html.Div(className="divider"),

                    # ── Customer Metrics ──
                    html.Div("Customer Metrics", className="section-label"),
                    html.Div(className="chart-row", children=[
                        chart_card(
                            title="Monthly Churn Rate",
                            graph_id="chart-churn",
                        ),
                        chart_card(
                            title="Customer Acquisition Cost (CAC)",
                            graph_id="chart-cac",
                        ),
                    ]),

                    # ── Revenue Metrics ──
                    html.Div("Revenue Metrics", className="section-label"),
                    html.Div(className="chart-row", children=[
                        chart_card(
                            title="Return on Ad Spend (ROAS)",
                            graph_id="chart-roas",
                        ),
                        chart_card(
                            title="CAC vs LTV Thresholds",
                            graph_id="chart-cac-ltv",
                        ),
                    ]),

                    # ── LTV by Cohort (full-width, with country filter) ──
                    html.Div("LTV Dashboard", className="section-label"),

                    # Change 5: LTV country filter strip above the chart
                    html.Div(className="ltv-country-filter", children=[
                        html.Span("LTV by Country:", className="ltv-country-label"),
                        dcc.Dropdown(
                            id="filter-ltv-country",
                            options=LTV_COUNTRY_OPTIONS,
                            value=None,
                            clearable=True,
                            searchable=False,
                            placeholder="All countries…",
                            className="country-dropdown",
                            style={
                                "width": "220px", "fontSize": "12.5px",
                                "fontFamily": "Inter, sans-serif",
                            },
                        ),
                    ]),

                    chart_card(
                        title="Lifetime Value by Cohort (click legend to show/hide 180d & 365d)",
                        graph_id="chart-ltv",
                        height=380,
                    ),
                ]),
            ]),
        ],
    )


dash_app.layout = layout

# ── Callback 1: Populate dropdowns ──────────────────────────────────────────────
@dash_app.callback(
    Output("filter-platform", "options"),
    Input("interval", "n_intervals"),
    prevent_initial_call=False,
)
def load_dropdowns(_):
    try:
        platforms = get_platform_options()
        return platforms
    except Exception as e:
        print(f"[app] load_dropdowns: {e}")
        return []


# ── Callback 2: KPI scorecards ───────────────────────────────────────────────
@dash_app.callback(
    Output("kpi-grid", "children"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_kpis(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)

    try:
        m = load_kpi_data(start, end, country, platform)
    except Exception as e:
        print(f"[app] update_kpis: {e}")
        m = {"gross_revenue": 0, "proceeds": 0, "spend": 0, "active_subs": 0,
             "gr_delta": 0, "pr_delta": 0, "sp_delta": 0, "subs_delta": 0}

    return [
        kpi_card("subs", "Active Subscriptions", fmt_count(m.get("active_subs", 0)),
                 subtitle=f"As of {end}", delta=m.get("subs_delta", 0),
                 icon="", featured=True),
        kpi_card("gr",  "Gross Revenue", fmt_currency(m.get("gross_revenue", 0)),
                 subtitle=f"{start} → {end}", delta=m.get("gr_delta", 0),
                 icon="", featured=True),
        kpi_card("pr",  "Proceeds",      fmt_currency(m.get("proceeds", 0)),
                 subtitle=f"{start} → {end}", delta=m.get("pr_delta", 0),
                 icon="", featured=True),
        kpi_card("sp",  "Spend",         fmt_currency(m.get("spend", 0)),
                 subtitle=f"{start} → {end}", delta=m.get("sp_delta", 0),
                 icon="", featured=True),
    ]


# ── Callback 3: Proceeds trend chart ────────────────────────────────────────
@dash_app.callback(
    Output("chart-proceeds", "figure"),
    Input("filter-dates",      "start_date"),
    Input("filter-dates",      "end_date"),
    Input("filter-country",    "value"),
    Input("filter-platform",   "value"),
    Input("store-granularity", "data"),
    Input("interval",          "n_intervals"),
    prevent_initial_call=False,
)
def update_proceeds(start, end, country, platform, gran_data, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    gran = gran_data.get("proceeds", "Day") if gran_data else "Day"
    try:
        df = get_proceeds_trend(start, end, country, platform)
        return proceeds_figure(df, gran)
    except Exception as e:
        print(f"[app] update_proceeds: {e}")
        from components import _empty_figure
        return _empty_figure(f"Error: {e}")


# ── Callback 4: ARPU line + platform bar ────────────────────────────────────
@dash_app.callback(
    Output("chart-arpu-line",     "figure"),
    Output("chart-arpu-platform", "figure"),
    Input("filter-dates",      "start_date"),
    Input("filter-dates",      "end_date"),
    Input("filter-platform",   "value"),
    Input("store-granularity", "data"),
    Input("interval",          "n_intervals"),
    prevent_initial_call=False,
)
def update_arpu(start, end, platform, gran_data, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    gran = gran_data.get("arpu", "Day") if gran_data else "Day"
    try:
        df_daily    = get_arpu_daily(start, end)
        df_platform = get_arpu_by_platform(start, end)
        return (
            arpu_line_figure(df_daily, gran),
            arpu_platform_figure(df_platform),
        )
    except Exception as e:
        print(f"[app] update_arpu: {e}")
        from components import _empty_figure
        empty = _empty_figure(f"Error: {e}")
        return empty, empty


# ── Callback 5: Drill-down controls ─────────────────────────────────────────
# Change 8: also output the level span text so the label updates reactively
@dash_app.callback(
    Output("store-granularity",   "data"),
    Output("gran-proceeds-level", "children"),   # ← new: update level label
    Output("gran-arpu-level",     "children"),   # ← new: update level label
    Input("gran-proceeds-up",     "n_clicks"),
    Input("gran-proceeds-down",   "n_clicks"),
    Input("gran-arpu-up",         "n_clicks"),
    Input("gran-arpu-down",       "n_clicks"),
    State("store-granularity",    "data"),
    prevent_initial_call=True,
)
def handle_drilldown(proc_up, proc_down, arpu_up, arpu_down, current_gran):
    ctx = callback_context
    gran = (current_gran or {"proceeds": "Day", "arpu": "Day"}).copy()

    if not ctx.triggered:
        return gran, gran.get("proceeds", "Day"), gran.get("arpu", "Day")

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    # levels ordered coarse→fine: Year > Month > Day
    # ▲ (up) = aggregate more = go coarser (Day→Month→Year)
    # ▼ (down) = drill deeper = go finer  (Year→Month→Day)
    levels = ["Day", "Month", "Year"]

    if button_id == "gran-proceeds-up":
        idx = levels.index(gran.get("proceeds", "Day"))
        if idx < len(levels) - 1:          # Day→Month, Month→Year
            gran["proceeds"] = levels[idx + 1]
    elif button_id == "gran-proceeds-down":
        idx = levels.index(gran.get("proceeds", "Day"))
        if idx > 0:                         # Year→Month, Month→Day
            gran["proceeds"] = levels[idx - 1]
    elif button_id == "gran-arpu-up":
        idx = levels.index(gran.get("arpu", "Day"))
        if idx < len(levels) - 1:
            gran["arpu"] = levels[idx + 1]
    elif button_id == "gran-arpu-down":
        idx = levels.index(gran.get("arpu", "Day"))
        if idx > 0:
            gran["arpu"] = levels[idx - 1]

    return gran, gran.get("proceeds", "Day"), gran.get("arpu", "Day")


# ── Callback 6: Churn + CAC + ROAS + CAC-LTV Thresholds ────────────────────
@dash_app.callback(
    Output("chart-churn",   "figure"),
    Output("chart-cac",     "figure"),
    Output("chart-roas",    "figure"),
    Output("chart-cac-ltv", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_customer_charts(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)

    from components import _empty_figure

    try:
        churn_df = get_monthly_churn(start, end, country, platform)
    except Exception as e:
        print(f"[app] churn: {e}")
        churn_df = None

    try:
        cac_df = get_cac_data(start, end, country, platform)
    except Exception as e:
        print(f"[app] cac: {e}")
        cac_df = None

    try:
        roas_df = get_roas_data(start, end, country, platform)
    except Exception as e:
        print(f"[app] roas: {e}")
        roas_df = None

    try:
        cac_ltv_df = get_cac_ltv_thresholds(start, end, country, platform)
    except Exception as e:
        print(f"[app] cac_ltv: {e}")
        cac_ltv_df = None

    import pandas as pd

    churn_fig   = churn_figure(churn_df) if churn_df is not None else _empty_figure("Churn error")
    cac_fig_out = cac_figure(cac_df)     if cac_df is not None   else _empty_figure("CAC error")
    roas_fig    = roas_figure(roas_df)   if roas_df is not None  else _empty_figure("ROAS error")
    clt_fig     = cac_ltv_threshold_figure(cac_ltv_df) if cac_ltv_df is not None else _empty_figure("Threshold error")

    return churn_fig, cac_fig_out, roas_fig, clt_fig


# ── Callback 7: LTV cohort chart (with dedicated country filter) ─────────────
# Change 5: uses filter-ltv-country instead of the global filter-country
@dash_app.callback(
    Output("chart-ltv", "figure"),
    Input("filter-dates",       "start_date"),
    Input("filter-dates",       "end_date"),
    Input("filter-ltv-country", "value"),        # ← dedicated LTV country filter
    Input("filter-platform",    "value"),
    Input("interval",           "n_intervals"),
    prevent_initial_call=False,
)
def update_ltv(start, end, ltv_country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)

    try:
        ltv_df = get_cohort_ltv_data(start, end, ltv_country, platform)
        return ltv_cohort_figure(ltv_df)
    except Exception as e:
        print(f"[app] update_ltv: {e}")
        from components import _empty_figure
        return _empty_figure(f"Error: {e}")


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    dash_app.run(debug=True, host="127.0.0.1", port=8050)
