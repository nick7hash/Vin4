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
    hovermode="x unified",
    xaxis=dict(gridcolor="#1F2937", linecolor="#1F2937", tickcolor="#4B5563",
               tickfont=dict(color="#9CA3AF")),
    yaxis=dict(gridcolor="#1F2937", linecolor="#1F2937", tickcolor="#4B5563",
               tickfont=dict(color="#9CA3AF")),
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
                      .resample("ME")["arpu"]
                      .mean()
                      .reset_index())
        elif granularity == "Year":
            pdf = (pdf.set_index("date")
                      .resample("YE")["arpu"]
                      .mean()
                      .reset_index())
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
# ── ARPU by Platform Bar Chart ──
# Generates the vertical bar chart summarizing ARPU by platform.
# =============================================================================
def arpu_platform_figure(df):
    if df.empty:
        return _empty_figure("No platform data for this period")

    colors = [ACCENT_COLORS[i % len(ACCENT_COLORS)] for i in range(len(df))]
    fig = go.Figure(go.Bar(
        x=df["platform"],
        y=df["avg_arpu"],
        marker=dict(color=colors, opacity=0.9),
        text=[f"${v:.2f}" for v in df["avg_arpu"]],
        textposition="outside",
        textfont=dict(color="#E5E7EB", size=11),
        hovertemplate="<b>%{x}</b><br>Avg ARPU: $%{y:.2f}<extra></extra>",
    ))
    layout = dict(CHART_LAYOUT)
    layout["yaxis"] = dict(CHART_LAYOUT["yaxis"])
    layout["yaxis"]["tickprefix"] = "$"
    layout["xaxis"] = dict(CHART_LAYOUT["xaxis"])
    layout["xaxis"]["gridcolor"] = "rgba(0,0,0,0)"
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
