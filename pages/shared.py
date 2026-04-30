"""
pages/shared.py — Shared UI helpers used across all pages.

HOW IT WORKS (beginner-friendly):
  - `page_tab_nav(active)` builds the top navigation bar.
  - `page_header(...)` builds the top header bar.
  - `page_footer()` builds the bottom footer bar.
"""

from dash import html, dcc
from datetime import date
from data import get_default_dates as _get_default_dates


def _defaults():
    """Return (start_date, end_date) from the database, cached on first call."""
    return _get_default_dates()

# Standard list of countries used for filtering
LTV_COUNTRY_OPTIONS = [
    {"label": "🇦🇺 Australia",      "value": "AU"},
    {"label": "🇨🇦 Canada",         "value": "CA"},
    {"label": "🇬🇧 United Kingdom", "value": "GB"},
    {"label": "🇺🇸 United States",  "value": "US"},
]

# ── Tab definitions ────────────────────────────────────────────────────────────
TAB_DEFINITIONS = [
    ("Overview",       "/",              "overview"),
    ("CAC",            "/cac",           "cac"),
    ("LTV",            "/ltv",           "ltv"),
    ("ROAS",           "/roas",          "roas"),
    ("Break-Even",     "/breakeven",     "breakeven"),
    ("Payback Period", "/payback",       "payback"),
    ("ROI",            "/roi",           "roi"),
    ("Biz Break-Even", "/biz-breakeven", "biz-breakeven"),
]

def page_tab_nav(active: str) -> html.Div:
    tabs = []
    for label, href, key in TAB_DEFINITIONS:
        cls = "page-tab page-tab--active" if key == active else "page-tab"
        tabs.append(dcc.Link(label, href=href, className=cls))
    return html.Div(className="page-tab-nav", children=tabs)

def page_header(
    title: str = "Vinita Analytics",
    subtitle: str = "Revenue Intelligence",
    icon_src: str = "/assets/logo.png",
    controls: list | None = None,
) -> html.Header:
    return html.Header(
        className="app-header",
        children=[
            html.Div(className="header-brand", children=[
                html.Div(
                    html.Img(src=icon_src, alt="Vinita", style={"width": "32px", "height": "32px", "filter": "invert(1)" if "fb-icon" in icon_src else "none"}),
                    className="header-logo",
                ),
                html.Div([
                    html.Div(title,    className="header-title"),
                    html.Div(subtitle, className="header-sub"),
                ]),
            ]),
            html.Div(className="header-controls", children=controls or []),
        ],
    )

def page_footer() -> html.Footer:
    return html.Footer(
        "Powered by Razorlytics",
        className="app-footer",
        style={
            "textAlign": "center",
            "padding": "24px 0",
            "color": "#6B7280",
            "fontSize": "13px",
            "fontFamily": "Inter, sans-serif",
            "marginTop": "20px",
        },
    )
