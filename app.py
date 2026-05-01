"""
app.py — Vinita Analytics Dashboard
Routing + Callbacks only. All layouts live in pages/.
"""
from datetime import date
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

from data import (
    get_default_dates, get_country_options, get_platform_options,
    load_kpi_data, get_proceeds_trend, get_arpu_daily,
    get_conversion_rate_data, get_monthly_churn, get_cohort_ltv_data,
    get_roas_data, get_cac_data, get_cac_ltv_thresholds, get_ltv_net_data,
    get_true_roas_data, get_facebook_kpi_data, get_meta_roas_data,
    get_breakeven_data, get_roi_data, get_biz_breakeven_data,
)
from components import (
    kpi_card, chart_card, granularity_control, drilldown_control,
    proceeds_figure, arpu_line_figure, conversion_rate_figure,
    churn_figure, ltv_cohort_figure, roas_figure, cac_figure,
    cac_ltv_threshold_figure, ltv_net_figure,
    fmt_currency, fmt_count, ios_fee_toggle, true_roas_figure,
    breakeven_figure, payback_figure,
    roi_summary_cards, roi_trend_figure, biz_breakeven_figure,
    _empty_figure,
)
from pages.overview_page    import overview_layout
from pages.cac_page         import cac_layout
from pages.ltv_page         import ltv_layout
from pages.roas_page        import roas_layout
from pages.breakeven_page   import breakeven_layout
from pages.payback_page     import payback_layout
from pages.roi_page         import roi_layout
from pages.biz_breakeven_page import biz_breakeven_layout

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

dash_app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
      .DateRangePickerInput,.DateRangePickerInput__withBorder{background:#111827!important;border:1px solid #374151!important;border-radius:8px!important;display:flex!important;align-items:center!important;}
      .DateInput{background:transparent!important;width:110px!important;}
      .DateInput_input{background:transparent!important;color:#E5E7EB!important;font-family:'Inter',sans-serif!important;font-size:12.5px!important;border-bottom:2px solid transparent!important;padding:6px 8px!important;caret-color:#A855F7!important;}
      .DateInput_input::placeholder{color:#6B7280!important;}
      .DateInput_input__focused{border-bottom:2px solid #A855F7!important;}
      .DateRangePickerInput_arrow{color:#6B7280!important;padding:0 4px!important;}
      .DateRangePicker_picker{background:#1F2937!important;border:1px solid #374151!important;border-radius:12px!important;z-index:9999!important;}
      .DayPicker,.CalendarMonthGrid,.CalendarMonth{background:#1F2937!important;}
      .DayPicker__withBorder{box-shadow:0 8px 32px rgba(0,0,0,.6)!important;border-radius:12px!important;border:none!important;}
      .CalendarMonth_caption{color:#E5E7EB!important;font-family:'Inter',sans-serif!important;font-weight:600!important;}
      .DayPicker_weekHeader_li small{color:#6B7280!important;}
      .CalendarDay__default{background:transparent!important;color:#D1D5DB!important;border:1px solid transparent!important;}
      .CalendarDay__default:hover{background:rgba(124,58,237,.2)!important;color:#fff!important;border-color:#7C3AED!important;border-radius:4px!important;}
      .CalendarDay__selected,.CalendarDay__selected:hover,.CalendarDay__selected:active{background:#7C3AED!important;color:#fff!important;border-color:#7C3AED!important;border-radius:4px!important;}
      .CalendarDay__selected_span{background:rgba(124,58,237,.25)!important;color:#E5E7EB!important;border-color:rgba(124,58,237,.3)!important;}
      .CalendarDay__hovered_span,.CalendarDay__hovered_span:hover{background:rgba(124,58,237,.15)!important;color:#E5E7EB!important;border-color:rgba(124,58,237,.2)!important;}
      .CalendarDay__blocked_out_of_range,.CalendarDay__blocked_out_of_range:hover{color:#374151!important;background:transparent!important;}
      .DayPickerNavigation_button{background:transparent!important;border:1px solid #374151!important;border-radius:6px!important;}
      .DayPickerNavigation_button:hover{border-color:#A855F7!important;}
      .DayPickerNavigation_svg__horizontal{fill:#9CA3AF!important;}
    </style>
  </head>
  <body>
    <div id="initial-loading">
      <img class="loading-logo" src="/assets/logo.png" alt="Vinita" />
      <div class="loading-label">Vinita Analytics</div>
    </div>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
    <script>
      window.addEventListener('load', function () {
        setTimeout(function () {
          var el = document.getElementById('initial-loading');
          if (el) { el.classList.add('fade-out'); setTimeout(function () { el.remove(); }, 700); }
        }, 1800);
      });
    </script>
  </body>
</html>"""

_default_start, _default_end = get_default_dates()
print(f"[app] Default date range: {_default_start} -> {_default_end}")

# ── Root layout ───────────────────────────────────────────────────────────────
dash_app.layout = html.Div(
    className="app-container",
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(id="page-content", className="page-content-wrapper"),
    ],
)

# ── Page routing ──────────────────────────────────────────────────────────────
@dash_app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    routes = {
        "/cac":          cac_layout,
        "/ltv":          ltv_layout,
        "/roas":         roas_layout,
        "/facebook":     roas_layout,   # legacy redirect
        "/breakeven":    breakeven_layout,
        "/payback":      payback_layout,
        "/roi":          roi_layout,
        "/biz-breakeven":biz_breakeven_layout,
    }
    layout_fn = routes.get(pathname, overview_layout)
    return layout_fn()

# =============================================================================
# SHARED CALLBACKS
# These IDs exist on every page (in the header), so these callbacks fire
# on all pages. suppress_callback_exceptions=True handles missing outputs.
# =============================================================================

@dash_app.callback(
    Output("filter-platform", "options"),
    Input("interval", "n_intervals"),
    prevent_initial_call=False,
)
def load_dropdowns(_):
    try:
        return get_platform_options()
    except Exception as e:
        print(f"[app] load_dropdowns: {e}")
        return []

# =============================================================================
# OVERVIEW PAGE CALLBACKS
# =============================================================================

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
        m = {"gross_revenue":0,"proceeds":0,"spend":0,"active_subs":0,
             "gr_delta":0,"pr_delta":0,"sp_delta":0,"subs_delta":0}
    return [
        kpi_card("subs","Active Subscriptions", fmt_count(m.get("active_subs",0)),
                 subtitle=f"As of {end}", delta=m.get("subs_delta",0), icon="", featured=True),
        kpi_card("gr",  "Gross Revenue",  fmt_currency(m.get("gross_revenue",0)),
                 subtitle=f"{start} → {end}", delta=m.get("gr_delta",0), icon="", featured=True),
        kpi_card("pr",  "Proceeds",       fmt_currency(m.get("proceeds",0)),
                 subtitle=f"{start} → {end}", delta=m.get("pr_delta",0), icon="", featured=True),
        kpi_card("sp",  "Spend",          fmt_currency(m.get("spend",0)),
                 subtitle=f"{start} → {end}", delta=m.get("sp_delta",0), icon="", featured=True),
    ]


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
        return proceeds_figure(get_proceeds_trend(start, end, country, platform), gran)
    except Exception as e:
        print(f"[app] update_proceeds: {e}")
        return _empty_figure(f"Error: {e}")


@dash_app.callback(
    Output("chart-arpu-line", "figure"),
    Input("filter-dates",      "start_date"),
    Input("filter-dates",      "end_date"),
    Input("filter-country",    "value"),
    Input("filter-platform",   "value"),
    Input("store-granularity", "data"),
    Input("interval",          "n_intervals"),
    prevent_initial_call=False,
)
def update_arpu(start, end, country, platform, gran_data, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    gran = gran_data.get("arpu", "Day") if gran_data else "Day"
    try:
        return arpu_line_figure(get_arpu_daily(start, end, country, platform), gran)
    except Exception as e:
        print(f"[app] update_arpu: {e}")
        return _empty_figure(f"Error: {e}")


@dash_app.callback(
    Output("store-granularity",    "data"),
    Output("gran-proceeds-level",  "children"),
    Output("gran-arpu-level",      "children"),
    Output("gran-conversion-level","children"),
    Input("gran-proceeds-up",      "n_clicks"),
    Input("gran-proceeds-down",    "n_clicks"),
    Input("gran-arpu-up",          "n_clicks"),
    Input("gran-arpu-down",        "n_clicks"),
    Input("gran-conversion-up",    "n_clicks"),
    Input("gran-conversion-down",  "n_clicks"),
    State("store-granularity",     "data"),
    prevent_initial_call=True,
)
def handle_drilldown(pu, pd_, au, ad_, cu, cd_, current_gran):
    ctx    = callback_context
    levels = ["Day", "Month", "Year"]
    gran   = (current_gran or {"proceeds":"Day","arpu":"Day","conversion":"Day"}).copy()
    if not ctx.triggered:
        return gran, gran.get("proceeds","Day"), gran.get("arpu","Day"), gran.get("conversion","Day")
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    def _shift(key, delta):
        idx = levels.index(gran.get(key,"Day"))
        gran[key] = levels[max(0, min(len(levels)-1, idx+delta))]
    if btn=="gran-proceeds-up":    _shift("proceeds",+1)
    elif btn=="gran-proceeds-down":_shift("proceeds",-1)
    elif btn=="gran-arpu-up":      _shift("arpu",+1)
    elif btn=="gran-arpu-down":    _shift("arpu",-1)
    elif btn=="gran-conversion-up":_shift("conversion",+1)
    elif btn=="gran-conversion-down":_shift("conversion",-1)
    return gran, gran.get("proceeds","Day"), gran.get("arpu","Day"), gran.get("conversion","Day")


@dash_app.callback(
    Output("chart-conversion", "figure"),
    Input("filter-dates",      "start_date"),
    Input("filter-dates",      "end_date"),
    Input("filter-country",    "value"),
    Input("filter-platform",   "value"),
    Input("store-granularity", "data"),
    Input("interval",          "n_intervals"),
    prevent_initial_call=False,
)
def update_conversion(start, end, country, platform, gran_data, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    gran = gran_data.get("conversion","Day") if gran_data else "Day"
    try:
        return conversion_rate_figure(get_conversion_rate_data(start, end, country, platform), gran)
    except Exception as e:
        print(f"[app] update_conversion: {e}")
        return _empty_figure(f"Error: {e}")


@dash_app.callback(
    Output("chart-churn", "figure"),
    Output("chart-roas",  "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_overview_charts(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        churn_df = get_monthly_churn(start, end, country, platform)
        ch_fig   = churn_figure(churn_df)
    except Exception as e:
        print(f"[app] churn: {e}"); ch_fig = _empty_figure("Churn error")
    try:
        roas_df  = get_roas_data(start, end, country, platform)
        ro_fig   = roas_figure(roas_df)
    except Exception as e:
        print(f"[app] roas: {e}"); ro_fig = _empty_figure("ROAS error")
    return ch_fig, ro_fig

# =============================================================================
# CAC PAGE CALLBACKS
# =============================================================================

@dash_app.callback(
    Output("chart-cac",     "figure"),
    Output("chart-cac-ltv", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("store-gran-cac",  "data"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_cac_charts(start, end, country, platform, gran_data, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    gran = gran_data.get("cac", "Day") if gran_data else "Day"
    try:
        cac_fig = cac_figure(get_cac_data(start, end, country, platform), gran)
    except Exception as e:
        print(f"[app] cac: {e}"); cac_fig = _empty_figure("CAC error")
    try:
        clt_fig = cac_ltv_threshold_figure(get_cac_ltv_thresholds(start, end, country, platform), gran)
    except Exception as e:
        print(f"[app] cac_ltv: {e}"); clt_fig = _empty_figure("Threshold error")
    return cac_fig, clt_fig

@dash_app.callback(
    Output("store-gran-cac", "data"),
    Output("gran-cac-level", "children"),
    Input("gran-cac-up", "n_clicks"),
    Input("gran-cac-down", "n_clicks"),
    State("store-gran-cac", "data"),
    prevent_initial_call=True,
)
def handle_cac_drilldown(up, down, current_gran):
    ctx = callback_context
    levels = ["Day", "Month", "Year"]
    gran = (current_gran or {"cac": "Day"}).copy()
    if not ctx.triggered:
        return gran, gran.get("cac", "Day")
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    idx = levels.index(gran.get("cac", "Day"))
    if btn == "gran-cac-up":
        idx = min(len(levels)-1, idx+1)
    elif btn == "gran-cac-down":
        idx = max(0, idx-1)
    gran["cac"] = levels[idx]
    return gran, gran["cac"]

# =============================================================================
# LTV PAGE CALLBACKS
# =============================================================================

@dash_app.callback(
    Output("chart-ltv-net", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_ltv_net(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        return ltv_net_figure(get_ltv_net_data(start, end, country, platform))
    except Exception as e:
        print(f"[app] ltv_net: {e}"); return _empty_figure("LTV (net) error")


@dash_app.callback(
    Output("chart-ltv", "figure"),
    Input("filter-dates",       "start_date"),
    Input("filter-dates",       "end_date"),
    Input("filter-ltv-country", "value"),
    Input("filter-platform",    "value"),
    Input("interval",           "n_intervals"),
    prevent_initial_call=False,
)
def update_ltv(start, end, ltv_country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        return ltv_cohort_figure(get_cohort_ltv_data(start, end, ltv_country, platform))
    except Exception as e:
        print(f"[app] update_ltv: {e}"); return _empty_figure(f"Error: {e}")

# =============================================================================
# ROAS PAGE CALLBACKS
# =============================================================================

@dash_app.callback(
    Output("store-roas-drill", "data"),
    Output("drill-country",    "className"),
    Output("drill-campaign",   "className"),
    Output("drill-ad",         "className"),
    Input("drill-country",     "n_clicks"),
    Input("drill-campaign",    "n_clicks"),
    Input("drill-ad",          "n_clicks"),
    Input("chart-true-roas",   "clickData"),
    State("store-roas-drill",  "data"),
    prevent_initial_call=True,
)
def handle_roas_drilldown(c_clicks, camp_clicks, ad_clicks, click_data, current_state):
    ctx   = callback_context
    state = current_state or {"level":"country","filter_country":None,"filter_campaign":None}
    if not ctx.triggered:
        return state,"drill-btn drill-btn--active","drill-btn","drill-btn"
    tid   = ctx.triggered[0]["prop_id"].split(".")[0]
    level = state.get("level","country")
    if tid == "chart-true-roas":
        if click_data and "points" in click_data:
            clicked = click_data["points"][0]["y"]
            if level == "country":
                state["filter_country"]  = clicked
                state["level"]           = "campaign"
            elif level == "campaign":
                state["filter_campaign"] = clicked
                state["level"]           = "ad"
    else:
        if   tid=="drill-country":  state.update({"level":"country","filter_country":None,"filter_campaign":None})
        elif tid=="drill-campaign": state.update({"level":"campaign","filter_campaign":None})
        elif tid=="drill-ad":       state["level"] = "ad"
    lv   = state["level"]
    cls  = lambda k: "drill-btn" + (" drill-btn--active" if lv==k else "")
    return state, cls("country"), cls("campaign"), cls("ad")


@dash_app.callback(
    Output("chart-true-roas", "figure"),
    Output("roas-summary",    "children"),
    Input("fb-filter-dates",   "start_date"),
    Input("fb-filter-dates",   "end_date"),
    Input("fb-filter-platform","value"),
    Input("store-roas-drill",  "data"),
    Input("toggle-roas-type",  "value"),
    Input("fb-interval",       "n_intervals"),
    prevent_initial_call=False,
)
def update_true_roas(start, end, platform, drill_store, roas_type, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    drill = drill_store or {"level":"country","filter_country":None,"filter_campaign":None}
    level           = drill.get("level","country")
    filter_country  = drill.get("filter_country")
    filter_campaign = drill.get("filter_campaign")
    try:
        df = get_true_roas_data(start, end, None, platform, roas_type=roas_type)
        if not df.empty:
            if filter_country:
                df = df[df["country"].fillna("Unknown").astype(str) == filter_country]
            if filter_campaign:
                df = df[df["campaign_name"].fillna("Unknown").astype(str) == filter_campaign]
        if df.empty:
            return true_roas_figure(df, drill_level=level, roas_type=roas_type), html.Span("No ROAS data")
        tot_net   = df["net_proceeds"].sum()
        tot_spend = df["spend"].sum()
        avg_roas  = (tot_net/tot_spend) if tot_spend > 0 else 0
        cls       = "roas-val positive" if avg_roas >= 1 else "roas-val negative"
        breadcrumb= ""
        if filter_campaign: breadcrumb = f" ({filter_country} > {filter_campaign})"
        elif filter_country: breadcrumb = f" ({filter_country})"
        net_lbl = "Purchase" if roas_type=="meta" else "Net"
        summary = html.Div([
            html.Span("Avg ROAS: ", className="roas-lbl"),
            html.Span(f"{avg_roas:.2f}x", className=cls),
            html.Span(f" ({net_lbl}: ${tot_net:,.0f} | Spend: ${tot_spend:,.0f}){breadcrumb}", className="roas-sublbl"),
        ])
        return true_roas_figure(df, drill_level=level, roas_type=roas_type), summary
    except Exception as e:
        print(f"[app] update_true_roas: {e}")
        return _empty_figure(f"Error: {e}"), html.Span("Error loading ROAS")

# =============================================================================
# BREAK-EVEN PAGE CALLBACK
# =============================================================================

@dash_app.callback(
    Output("chart-breakeven", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_breakeven(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        return breakeven_figure(get_breakeven_data(start, end, country, platform))
    except Exception as e:
        print(f"[app] breakeven: {e}"); return _empty_figure(f"Error: {e}")

# =============================================================================
# PAYBACK PERIOD PAGE CALLBACK
# =============================================================================

@dash_app.callback(
    Output("chart-payback", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_payback(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        return payback_figure(get_breakeven_data(start, end, country, platform))
    except Exception as e:
        print(f"[app] payback: {e}"); return _empty_figure(f"Error: {e}")

# =============================================================================
# ROI PAGE CALLBACKS
# =============================================================================

@dash_app.callback(
    Output("roi-kpi-grid",    "children"),
    Output("chart-roi-trend", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_roi(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        roi_data = get_roi_data(start, end, country, platform)
        cards    = roi_summary_cards(roi_data)
        trend    = roi_trend_figure(roi_data.get("trend_df"))
        return cards, trend
    except Exception as e:
        print(f"[app] roi: {e}")
        return [], _empty_figure(f"Error: {e}")

# =============================================================================
# BUSINESS BREAK-EVEN PAGE CALLBACK
# =============================================================================

@dash_app.callback(
    Output("chart-biz-breakeven", "figure"),
    Input("filter-dates",    "start_date"),
    Input("filter-dates",    "end_date"),
    Input("filter-country",  "value"),
    Input("filter-platform", "value"),
    Input("interval",        "n_intervals"),
    prevent_initial_call=False,
)
def update_biz_breakeven(start, end, country, platform, _):
    if not start or not end:
        start, end = str(_default_start), str(_default_end)
    try:
        return biz_breakeven_figure(get_biz_breakeven_data(start, end, country, platform))
    except Exception as e:
        print(f"[app] biz_breakeven: {e}"); return _empty_figure(f"Error: {e}")

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    dash_app.run(debug=True, host="127.0.0.1", port=8050)
