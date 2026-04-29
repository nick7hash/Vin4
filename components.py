"""
components.py — Reusable UI components for Vinita Analytics Dashboard.
"""

import plotly.graph_objects as go
from dash import html, dcc

# =============================================================================
# ── Color Palette & Universal Chart Layout ──
# These settings define the "Dark Mode" aesthetic for all Plotly charts.
# =============================================================================
ACCENT_COLORS = ["#6C7CFF", "#A855F7", "#EC4899", "#34D399", "#F59E0B", "#22D3EE"]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#9CA3AF", size=12),
    margin=dict(l=16, r=16, t=44, b=16),
    # Use simple hover without a vertical spike line
    hovermode="closest",
    xaxis=dict(
        gridcolor="#1F2937",
        linecolor="#1F2937",
        tickcolor="#4B5563",
        tickfont=dict(color="#9CA3AF"),
        showspikes=False,
    ),
    yaxis=dict(
        gridcolor="#1F2937",
        linecolor="#1F2937",
        tickcolor="#4B5563",
        tickfont=dict(color="#9CA3AF"),
        showspikes=False,
    ),
    legend=dict(bgcolor="rgba(17,24,39,0.85)", bordercolor="#1F2937",
                borderwidth=1, font=dict(color="#E5E7EB")),
)

# =============================================================================
# ── Text Formatters ──
# Helper functions to convert large numbers into readable text (e.g. 1500 -> 1.5K)
# =============================================================================
def fmt_currency(v, prefix="$"):
    if v is None: return f"{prefix}0"
    v = float(v)
    if abs(v) >= 1_000_000: return f"{prefix}{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:     return f"{prefix}{v/1_000:.1f}K"
    return f"{prefix}{v:,.0f}"

def fmt_count(v):
    if v is None: return "0"
    v = int(v)
    if abs(v) >= 1_000_000: return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:     return f"{v/1_000:.1f}K"
    return f"{v:,}"

# =============================================================================
# ── HTML Components (Cards & Controls) ──
# These functions generate the raw HTML for the boxes on the screen.
# =============================================================================
def delta_badge(pct):
    if pct is None: return html.Span()
    cls  = "delta-badge positive" if pct >= 0 else "delta-badge negative"
    icon = "▲" if pct >= 0 else "▼"
    return html.Span(f"{icon} {abs(pct):.1f}%", className=cls)

def kpi_card(card_id, title, value, subtitle="", delta=None, icon="◈", featured=False):
    return html.Div(
        id=f"kpi-card-{card_id}",
        className=f"kpi-card {'kpi-card--featured' if featured else ''}",
        children=[
            html.Div(className="kpi-card__header", children=[
                html.Span(icon, className="kpi-card__icon"),
                delta_badge(delta),
            ]),
            html.Div(value, id=f"kpi-val-{card_id}", className="kpi-card__value"),
            html.Div(title,    className="kpi-card__title"),
            html.Div(subtitle, className="kpi-card__subtitle") if subtitle else html.Span(),
        ],
    )

# ── Chart card wrapper ────────────────────────────────────────────────────────
def chart_card(title, graph_id, controls=None, height=320):
    return html.Div(
        className="chart-card",
        children=[
            html.Div(className="chart-card__header", children=[
                html.Span(title, className="chart-card__title"),
                html.Div(controls or [], className="chart-card__controls"),
            ]),
            dcc.Graph(
                id=graph_id,
                config={"displayModeBar": True, "displaylogo": False,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]},
                className="chart-graph",
                style={"height": f"{height}px"},
            ),
        ],
    )

# ── Empty figure placeholder ──────────────────────────────────────────────────
def _empty_figure(msg="No data"):
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            text=msg, x=0.5, y=0.5, showarrow=False,
            font=dict(color="#4B5563", size=14, family="Inter, sans-serif"),
        )],
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig

# ── Proceeds line chart figure ────────────────────────────────────────────────
# Change 2: fill color → dark purple, opacity 0.06, line → #7C3AED
def proceeds_figure(df, granularity="Day"):
    if df.empty:
        return _empty_figure("No proceeds data for this period")

    df = df.copy().sort_values("date")
    if granularity == "Month":
        df = df.set_index("date").resample("ME")["proceeds"].sum().reset_index()
    elif granularity == "Year":
        df = df.set_index("date").resample("YE")["proceeds"].sum().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["proceeds"],
        mode="lines",
        line=dict(color="#7C3AED", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(124,58,237,0.06)",
        name="Proceeds",
        hovertemplate="<b>$%{y:,.0f}</b><extra></extra>",
    ))
    layout = dict(CHART_LAYOUT)
    layout["title"] = dict(text="", x=0)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# =============================================================================
# ── ARPU Line Chart Figure ──
# Generates the multi-line chart comparing ARPU across different platforms.
# =============================================================================
def arpu_line_figure(df, granularity="Day"):
    if df.empty:
        return _empty_figure("No ARPU data for this period")

    df = df.copy().sort_values("date")
    fig = go.Figure()

    for i, platform in enumerate(sorted(df["platform"].unique())):
        pdf = df[df["platform"] == platform].copy()
        if granularity == "Month":
            pdf = (pdf.set_index("date")
                      .resample("ME").agg({
                          "proceeds": "sum",
                          "active_subs": "last"
                      }).reset_index())
            pdf["arpu"] = pdf.apply(lambda row: row["proceeds"] / row["active_subs"] if row["active_subs"] else 0, axis=1)
        elif granularity == "Year":
            pdf = (pdf.set_index("date")
                      .resample("YE").agg({
                          "proceeds": "sum",
                          "active_subs": "last"
                      }).reset_index())
            pdf["arpu"] = pdf.apply(lambda row: row["proceeds"] / row["active_subs"] if row["active_subs"] else 0, axis=1)
        fig.add_trace(go.Scatter(
            x=pdf["date"], y=pdf["arpu"],
            mode="lines+markers",
            name=platform,
            line=dict(color=ACCENT_COLORS[i % len(ACCENT_COLORS)], width=2),
            marker=dict(size=4),
            hovertemplate=f"<b>{platform}</b>: $%{{y:.2f}}<extra></extra>",
        ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# =============================================================================
# ── Conversion Rate Line Chart ──
# Generates a line chart for Installs to Paid Conversion Rate.
# =============================================================================
def conversion_rate_figure(df, granularity="Day"):
    if df.empty:
        return _empty_figure("No conversion data for this period")

    df = df.copy().sort_values("date")
    if granularity == "Month":
        df = df.set_index("date").resample("ME").sum().reset_index()
        df["conversion_rate"] = df.apply(lambda x: (x['total_new_paid_subscriptions'] / x['installs'] * 100) if x['installs'] > 0 else 0, axis=1)
    elif granularity == "Year":
        df = df.set_index("date").resample("YE").sum().reset_index()
        df["conversion_rate"] = df.apply(lambda x: (x['total_new_paid_subscriptions'] / x['installs'] * 100) if x['installs'] > 0 else 0, axis=1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["conversion_rate"],
        mode="lines+markers",
        line=dict(color="#22D3EE", width=2.5),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(34,211,238,0.1)",
        name="Conversion Rate",
        hovertemplate="<b>%{x|%b %Y}</b><br>Conversion: %{y:.2f}%<extra></extra>",
    ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["ticksuffix"] = "%"
    layout["yaxis"]["tickformat"] = ".2f"
    fig.update_layout(**layout)
    return fig

# ── Monthly Churn Chart ────────────────────────────────────────────────────────
def churn_figure(df):
    if df.empty:
        return _empty_figure("No churn data for this period")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["churn_rate_pct"],
        mode="lines+markers",
        line=dict(color="#EF4444", width=2.5),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.1)",
        name="Churn Rate",
        hovertemplate="<b>%{x|%b %Y}</b><br>Churn: %{y:.2f}%<extra></extra>",
    ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["ticksuffix"] = "%"
    layout["yaxis"]["tickformat"] = ".1f"
    fig.update_layout(**layout)
    return fig

# ── LTV (net) Chart ────────────────────────────────────────────────────────────
def ltv_net_figure(df):
    if df.empty:
        return _empty_figure("No LTV (net) data for this period")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["ltv_net"],
        mode="lines+markers",
        line=dict(color="#A855F7", width=2.5),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(168,85,247,0.1)",
        name="LTV (net)",
        hovertemplate="<b>%{x|%b %Y}</b><br>LTV (net): $%{y:.2f}<extra></extra>",
    ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# ── LTV by Cohort Chart ────────────────────────────────────────────────────────
# Change 7: 7d/30d/90d visible by default; 180d/365d set to legendonly
def ltv_cohort_figure(df):
    if df.empty:
        return _empty_figure("No LTV data for this period")

    fig = go.Figure()

    # Group by date and calculate average LTV
    agg_cols = {}
    for period in ['7d', '30d', '90d', '180d', '365d']:
        col = f'realized_ltv_{period}'
        if col in df.columns:
            agg_cols[col] = 'mean'

    if not agg_cols:
        return _empty_figure("No LTV columns found")

    ltv_summary = df.groupby('date').agg(agg_cols).reset_index()

    periods = ['7d', '30d', '90d', '180d', '365d']
    colors  = ['#6C7CFF', '#A855F7', '#34D399', '#F59E0B', '#EC4899']
    # 180d and 365d are hidden by default but togglable via legend
    visibility = {
        '7d':   True,
        '30d':  True,
        '90d':  True,
        '180d': 'legendonly',
        '365d': 'legendonly',
    }

    for i, period in enumerate(periods):
        col = f'realized_ltv_{period}'
        if col in ltv_summary.columns:
            fig.add_trace(go.Scatter(
                x=ltv_summary['date'],
                y=ltv_summary[col],
                mode="lines+markers",
                name=f'LTV {period}',
                line=dict(color=colors[i], width=2),
                marker=dict(size=3),
                visible=visibility.get(period, True),
                hovertemplate=f"<b>LTV {period}</b>: $%{{y:.2f}}<extra></extra>",
            ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# ── ROAS Chart ────────────────────────────────────────────────────────────────
def roas_figure(df):
    if df.empty:
        return _empty_figure("No ROAS data for this period")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["roas"],
        mode="lines+markers",
        line=dict(color="#10B981", width=2.5),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(16,185,129,0.1)",
        name="ROAS",
        hovertemplate="<b>%{x|%b %Y}</b><br>ROAS: %{y:.2f}x<extra></extra>",
    ))

    # Reference line at ROAS = 1
    fig.add_hline(y=1, line_dash="dash", line_color="#6B7280", opacity=0.5,
                  annotation_text="Break-even", annotation_font_color="#6B7280")

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickformat"] = ".1f"
    layout["yaxis"]["ticksuffix"] = "x"
    fig.update_layout(**layout)
    return fig

# ── CAC Chart ────────────────────────────────────────────────────────────────
def cac_figure(df):
    if df.empty:
        return _empty_figure("No CAC data for this period")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cac"],
        mode="lines+markers",
        line=dict(color="#F59E0B", width=2.5),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.1)",
        name="CAC",
        hovertemplate="<b>%{x|%b %Y}</b><br>CAC: $%{y:.2f}<extra></extra>",
    ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# ── CAC vs LTV Thresholds Chart ───────────────────────────────────────────────
# Change 6: multi-line chart with CAC, LTV30d, Healthy (LTV/3), Aggressive (LTV/2)
def cac_ltv_threshold_figure(df):
    if df.empty:
        return _empty_figure("No data available for CAC vs LTV Thresholds")

    fig = go.Figure()

    # LTV 30d line
    if "ltv_30d" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["ltv_30d"],
            mode="lines+markers",
            name="LTV 30d",
            line=dict(color="#6C7CFF", width=2),
            marker=dict(size=3),
            hovertemplate="<b>LTV 30d</b>: $%{y:.2f}<extra></extra>",
        ))

    # Healthy CAC threshold (LTV/3) — dashed green
    if "healthy_cac_threshold" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["healthy_cac_threshold"],
            mode="lines",
            name="Healthy CAC (LTV÷3)",
            line=dict(color="#34D399", width=1.5, dash="dash"),
            hovertemplate="<b>Healthy Threshold</b>: $%{y:.2f}<extra></extra>",
        ))

    # Aggressive CAC threshold (LTV/2) — dashed orange
    if "aggressive_cac_threshold" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["aggressive_cac_threshold"],
            mode="lines",
            name="Aggressive CAC (LTV÷2)",
            line=dict(color="#F59E0B", width=1.5, dash="dot"),
            hovertemplate="<b>Aggressive Threshold</b>: $%{y:.2f}<extra></extra>",
        ))

    # Actual CAC line — solid red-orange
    if "cac" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["cac"],
            mode="lines+markers",
            name="Actual CAC",
            line=dict(color="#EC4899", width=2.5),
            marker=dict(size=4),
            hovertemplate="<b>Actual CAC</b>: $%{y:.2f}<extra></extra>",
        ))

    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    layout["legend"] = dict(
        bgcolor="rgba(17,24,39,0.85)", bordercolor="#1F2937",
        borderwidth=1, font=dict(color="#E5E7EB"),
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
    )
    fig.update_layout(**layout)
    return fig

# ── Drill-down control ────────────────────────────────────────────────────────
# Change 8: give the level span an id so it can be updated by callback
def drilldown_control(ctrl_id, current_level="Day"):
    """Drill-down up/down arrows with an updateable level label."""
    return html.Div([
        html.Button(
            "▲",
            id=f"{ctrl_id}-up",
            className="drilldown-btn drilldown-up",
            title="Drill up (coarser)",
            n_clicks=0,
        ),
        html.Span(
            current_level,
            id=f"{ctrl_id}-level",   # ← now has an ID for callback updates
            className="drilldown-level",
        ),
        html.Button(
            "▼",
            id=f"{ctrl_id}-down",
            className="drilldown-btn drilldown-down",
            title="Drill down (finer)",
            n_clicks=0,
        ),
    ], className="drilldown-control")

# ── Granularity control (legacy, kept for reference) ─────────────────────────
def granularity_control(ctrl_id, value="Day"):
    return dcc.RadioItems(
        id=ctrl_id,
        options=[
            {"label": "Day",   "value": "Day"},
            {"label": "Month", "value": "Month"},
            {"label": "Year",  "value": "Year"},
        ],
        value=value,
        inline=True,
        className="granularity-radio",
        inputClassName="granularity-input",
        labelClassName="granularity-label",
    )

# ── iOS Fee Toggle ───────────────────────────────────────────────────────────
def ios_fee_toggle(toggle_id="ios-fee-toggle", default_val=15):
    """A styled pill toggle for the iOS fee percentage."""
    return html.Div(
        className="ios-fee-toggle-container",
        children=[
            html.Span("iOS Fee:", className="ios-fee-label"),
            dcc.RadioItems(
                id=toggle_id,
                options=[
                    {"label": " 15%", "value": 15},
                    {"label": " 30%", "value": 30},
                ],
                value=default_val,
                inline=True,
                className="ios-fee-radio",
                inputClassName="ios-fee-input",
                labelClassName="ios-fee-radio-label",
            )
        ]
    )

# ── True ROAS Figure ──────────────────────────────────────────────────────────
def true_roas_figure(df, drill_level="campaign", roas_type="true"):
    """
    Bar chart for True ROAS broken down by Country, Campaign, or Ad.
    drill_level options: 'country', 'campaign', 'ad'
    roas_type options: 'true', 'meta'
    """
    if df.empty:
        return _empty_figure("No True ROAS data available for these filters")

    # Determine the grouping column based on drill_level
    if drill_level == "country":
        group_col = "country"
    elif drill_level == "ad":
        group_col = "ad_name"
    else:
        group_col = "campaign_name" # default

    # Handle missing values to prevent Plotly from crashing (white chart issue)
    df = df.copy()
    df[group_col] = df[group_col].fillna("Unknown").astype(str)

    # Group the dataframe by the selected level
    # We sum net_proceeds and spend, then recalculate roas
    grouped = df.groupby(group_col, as_index=False)[['net_proceeds', 'spend']].sum()
    
    # Filter out 0 spend rows to prevent clutter/organic campaigns showing up as 0 ROAS
    grouped = grouped[grouped['spend'] > 0]
    
    grouped['roas'] = grouped.apply(lambda x: x['net_proceeds'] / x['spend'] if x['spend'] > 0 else 0, axis=1)
    
    # Sort by spend (ascending for horizontal bar chart layout)
    grouped = grouped.sort_values('spend', ascending=True).tail(100) # top 100 by spend

    if grouped.empty:
        return _empty_figure(f"No {drill_level} data with valid spend")

    # Color logic: Green if >= 1, Red if < 1 for True ROAS. Always green for Meta ROAS.
    if roas_type == 'meta':
        colors = ['#10B981'] * len(grouped)
        hover_proceeds_label = "Purchase"
    else:
        colors = ['#10B981' if r >= 1 else '#EF4444' for r in grouped['roas']]
        hover_proceeds_label = "Net Proceeds"

    # Ensure minimum bar width so 0 ROAS campaigns are still clickable
    grouped['display_roas'] = grouped['roas'].apply(lambda r: max(r, 0.05))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=grouped[group_col],
        x=grouped['display_roas'],
        orientation='h',
        marker_color=colors,
        text=[f"{r:.2f}x" for r in grouped['roas']],
        textposition='outside',
        textfont=dict(color="#E5E7EB"),
        customdata=grouped[['net_proceeds', 'spend', 'roas']].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "ROAS: %{customdata[2]:.2f}x<br>"
            f"{hover_proceeds_label}: $%{{customdata[0]:,.2f}}<br>"
            "Spend: $%{customdata[1]:,.2f}"
            "<extra></extra>"
        )
    ))

    # Reference line at break-even (ROAS = 1)
    fig.add_vline(x=1, line_dash="dash", line_color="#6B7280", opacity=0.5,
                  annotation_text="Break-even", annotation_font_color="#6B7280")

    layout = dict(CHART_LAYOUT)
    layout["margin"] = dict(l=16, r=40, t=20, b=16) # adjust margins for horizontal bars
    layout["xaxis"] = dict(CHART_LAYOUT["xaxis"])
    layout["xaxis"]["ticksuffix"] = "x"
    layout["xaxis"]["title"] = "ROAS"
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickmode"] = "linear" # show all labels
    layout["yaxis"]["automargin"] = True # ensure long labels fit without cutting off or blanking chart
    layout["clickmode"] = "event+select" # Enable clicking
    
    fig.update_layout(**layout)
    return fig


# =============================================================================
# -- Break-Even Point Figure --
# Multi-country: flat CAC line (dashed) + rising cumulative ARPU (solid).
# =============================================================================
def breakeven_figure(df):
    if df is None or df.empty:
        return _empty_figure("No data available — try a wider date range")
    fig = go.Figure()
    for i, ctry in enumerate(df["country"].unique()):
        c_df   = df[df["country"] == ctry].sort_values("month_num")
        color  = ACCENT_COLORS[i % len(ACCENT_COLORS)]
        cac    = c_df["avg_cac"].iloc[0]
        x_nums = c_df["month_num"].tolist()
        x_labs = c_df["month_label"].tolist()
        fig.add_trace(go.Scatter(
            x=x_nums, y=c_df["cumulative_arpu_net"],
            mode="lines+markers", name=f"{ctry} — Cum. ARPU",
            line=dict(color=color, width=2.5), marker=dict(size=5),
            customdata=x_labs,
            hovertemplate="<b>%{customdata}</b><br>Cum. ARPU: $%{y:.2f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=[x_nums[0], x_nums[-1]], y=[cac, cac],
            mode="lines", name=f"{ctry} — CAC (${cac:.0f})",
            line=dict(color=color, width=1.5, dash="dash"),
            hovertemplate=f"<b>{ctry} CAC</b>: ${cac:.2f}<extra></extra>",
        ))
        cross = c_df[c_df["cumulative_arpu_net"] >= cac]
        if not cross.empty:
            mx, my = cross.iloc[0]["month_num"], cross.iloc[0]["cumulative_arpu_net"]
            fig.add_annotation(
                x=mx, y=my, text=f"Break-even: {ctry} M{mx}",
                showarrow=True, arrowhead=2, arrowcolor=color,
                font=dict(color=color, size=11),
                bgcolor="rgba(11,15,26,0.8)", bordercolor=color, borderwidth=1,
            )
    layout = dict(CHART_LAYOUT)
    layout["xaxis"] = dict(CHART_LAYOUT["xaxis"], title="Month Number", tickmode="linear", dtick=1)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"], tickprefix="$")
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return fig


# =============================================================================
# -- Payback Period Figure --
# Same data as break-even; filled area + vertical marker at crossover.
# =============================================================================
def payback_figure(df):
    if df is None or df.empty:
        return _empty_figure("No data available — try a wider date range")
    fig = go.Figure()
    for i, ctry in enumerate(df["country"].unique()):
        c_df   = df[df["country"] == ctry].sort_values("month_num")
        color  = ACCENT_COLORS[i % len(ACCENT_COLORS)]
        cac    = c_df["avg_cac"].iloc[0]
        x_nums = c_df["month_num"].tolist()
        x_labs = c_df["month_label"].tolist()
        try:
            r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            fill_c  = f"rgba({r},{g},{b},0.08)"
        except Exception:
            fill_c  = "rgba(108,124,255,0.08)"
        fig.add_trace(go.Scatter(
            x=x_nums, y=c_df["cumulative_arpu_net"],
            mode="lines+markers", name=ctry,
            fill="tozeroy", fillcolor=fill_c,
            line=dict(color=color, width=2.5), marker=dict(size=5),
            customdata=list(zip(x_labs, [cac]*len(x_nums))),
            hovertemplate="<b>%{customdata[0]}</b><br>Recovered: $%{y:.2f}<br>CAC: $%{customdata[1]:.2f}<extra></extra>",
        ))
        fig.add_hline(y=cac, line_dash="dot", line_color=color, opacity=0.6,
                      annotation_text=f"{ctry} CAC ${cac:.0f}", annotation_font_color=color)
        cross = c_df[c_df["cumulative_arpu_net"] >= cac]
        if not cross.empty:
            mx = cross.iloc[0]["month_num"]
            fig.add_vline(x=mx, line_dash="dash", line_color=color, opacity=0.5,
                          annotation_text=f"{ctry}: Payback M{mx}", annotation_font_color=color)
    layout = dict(CHART_LAYOUT)
    layout["xaxis"] = dict(CHART_LAYOUT["xaxis"], title="Month Number", tickmode="linear", dtick=1)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"], tickprefix="$")
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return fig


# =============================================================================
# -- ROI Summary Cards --
# Four KPI-style divs: 3m / 6m / 12m / Full LTV ROI.
# =============================================================================
def roi_summary_cards(roi_data: dict):
    def _card(card_id, horizon, roi_val, ltv_val, cac_val):
        positive = roi_val >= 0
        color    = "#34D399" if positive else "#EF4444"
        arrow    = "\u25b2" if positive else "\u25bc"
        return html.Div(
            id=f"roi-card-{card_id}",
            className="kpi-card kpi-card--featured",
            children=[
                html.Div(className="kpi-card__header", children=[
                    html.Span("\U0001f4c8" if positive else "\U0001f4c9", className="kpi-card__icon"),
                    html.Span(f"{arrow} {abs(roi_val):.1f}%",
                              className="delta-badge positive" if positive else "delta-badge negative"),
                ]),
                html.Div(f"{roi_val:+.1f}%", className="kpi-card__value", style={"color": color}),
                html.Div(f"ROI — {horizon}", className="kpi-card__title"),
                html.Div(f"LTV ${ltv_val:,.2f}  \xb7  CAC ${cac_val:,.2f}", className="kpi-card__subtitle"),
            ],
        )
    cac = roi_data.get("avg_cac", 0)
    return [
        _card("3m",   "3 Months",  roi_data.get("roi_3m",   0), roi_data.get("ltv_3m",   0), cac),
        _card("6m",   "6 Months",  roi_data.get("roi_6m",   0), roi_data.get("ltv_6m",   0), cac),
        _card("12m",  "12 Months", roi_data.get("roi_12m",  0), roi_data.get("ltv_12m",  0), cac),
        _card("full", "Full LTV",  roi_data.get("roi_full", 0), roi_data.get("ltv_full", 0), cac),
    ]


# =============================================================================
# -- ROI Trend Figure --
# Monthly line chart: 3m / 6m / 12m ROI over time.
# =============================================================================
def roi_trend_figure(trend_df):
    if trend_df is None or trend_df.empty:
        return _empty_figure("No monthly ROI trend data — try a wider date range")
    fig = go.Figure()
    for col, label, color in [
        ("roi_3m",  "3-Month ROI",  "#6C7CFF"),
        ("roi_6m",  "6-Month ROI",  "#A855F7"),
        ("roi_12m", "12-Month ROI", "#34D399"),
    ]:
        if col not in trend_df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=trend_df["month"], y=trend_df[col],
            mode="lines+markers", name=label,
            line=dict(color=color, width=2), marker=dict(size=4),
            hovertemplate=f"<b>{label}</b>: %{{y:+.1f}}%<extra></extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="#6B7280", opacity=0.5,
                  annotation_text="Break-even (0%)", annotation_font_color="#6B7280")
    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"], ticksuffix="%")
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return fig


# =============================================================================
# -- Business Break-Even Figure --
# Cumulative proceeds vs. cumulative ad spend with intersection highlight.
# =============================================================================
def biz_breakeven_figure(df):
    if df is None or df.empty:
        return _empty_figure("No data available — try a wider date range")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["cumulative_proceeds"],
        mode="lines+markers", name="Cumulative Proceeds",
        line=dict(color="#34D399", width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(52,211,153,0.07)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Cum. Proceeds: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["cumulative_spend"],
        mode="lines+markers", name="Cumulative Ad Spend",
        line=dict(color="#EF4444", width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.07)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Cum. Spend: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["net_position"],
        mode="lines", name="Net Position (Proceeds \u2212 Spend)",
        line=dict(color="#A855F7", width=1.5, dash="dot"),
        hovertemplate="<b>%{x|%b %Y}</b><br>Net: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#6B7280", opacity=0.4)
    crossed = df[df["net_position"] >= 0]
    if not crossed.empty:
        bx = crossed.iloc[0]["month"]
        fig.add_vline(
            x=bx.timestamp() * 1000,
            line_dash="dash", line_color="#A855F7", opacity=0.6,
            annotation_text=f"Biz Break-Even: {bx.strftime('%b %Y')}",
            annotation_font_color="#A855F7",
        )
    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"], tickprefix="$")
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return fig
