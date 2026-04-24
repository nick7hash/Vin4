"""
components.py — Reusable UI components for Vinita Analytics Dashboard.
"""

import plotly.graph_objects as go
from dash import html, dcc

# ── Palette ───────────────────────────────────────────────────────────────────
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

# ── Formatters ────────────────────────────────────────────────────────────────
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

# ── Delta badge ───────────────────────────────────────────────────────────────
def delta_badge(pct):
    if pct is None: return html.Span()
    cls  = "delta-badge positive" if pct >= 0 else "delta-badge negative"
    icon = "▲" if pct >= 0 else "▼"
    return html.Span(f"{icon} {abs(pct):.1f}%", className=cls)

# ── KPI Card ─────────────────────────────────────────────────────────────────
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
def chart_card(title, graph_id, controls=None):
    return html.Div(
        className="chart-card",
        children=[
            html.Div(className="chart-card__header", children=[
                html.Span(title, className="chart-card__title"),
                html.Div(controls or [], className="chart-card__controls"),
            ]),
            dcc.Graph(
                id=graph_id,
                config={"displayModeBar": False},
                className="chart-graph",
                style={"height": "320px"},
            ),
        ],
    )

# ── Proceeds line chart figure ────────────────────────────────────────────────
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
        line=dict(color="#A855F7", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(168,85,247,0.08)",
        name="Proceeds",
        hovertemplate="<b>$%{y:,.0f}</b><extra></extra>",
    ))
    layout = dict(CHART_LAYOUT)
    layout["title"] = dict(text="", x=0)
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# ── ARPU line chart figure ────────────────────────────────────────────────────
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
    layout["yaxis"]["tickprefix"] = "$"
    fig.update_layout(**layout)
    return fig

# ── ARPU by platform bar chart ────────────────────────────────────────────────
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
    layout["yaxis"]["tickprefix"] = "$"
    layout["xaxis"]["gridcolor"]  = "rgba(0,0,0,0)"
    fig.update_layout(**layout)
    return fig

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

# ── Granularity control ───────────────────────────────────────────────────────
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
