"""
data.py — BigQuery data layer for the Vinita Analytics Dashboard.
"""

import os
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import date, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID   = "vinita-388203"
TABLE        = "vinita-388203.dataform.mrt_final_vinita"
ARPU_TABLE   = "vinita-388203.vinita_rc_new.daily_metrics_rc"
KEY_PATH     = os.path.join(os.path.dirname(__file__), "vinita-key.json")

# ── Client ────────────────────────────────────────────────────────────────────
def get_bq_client() -> bigquery.Client:
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(credentials=creds, project=PROJECT_ID)


# ── Smart default date range (reads max date from BQ) ────────────────────────
def get_default_dates():
    """Return (start, end) based on the latest date in the main table."""
    try:
        client = get_bq_client()
        q = f"SELECT MAX(CAST(date AS DATE)) AS mx FROM `{TABLE}`"
        df = client.query(q).to_dataframe()
        mx = df["mx"].iloc[0]
        if mx is not None:
            return mx - timedelta(days=89), mx
    except Exception as e:
        print(f"[data] get_default_dates: {e}")
    return date.today() - timedelta(days=89), date.today()


# ── Country options ───────────────────────────────────────────────────────────
def get_country_options() -> list[dict]:
    try:
        client = get_bq_client()
        q = f"""
            SELECT DISTINCT rc_country
            FROM `{TABLE}`
            WHERE rc_country IS NOT NULL AND rc_country != ''
            ORDER BY rc_country LIMIT 200
        """
        df = client.query(q).to_dataframe()
        return [{"label": c, "value": c} for c in df["rc_country"].tolist()]
    except Exception as e:
        print(f"[data] get_country_options: {e}")
        return []


# ── Main KPI data (3 scorecards) ──────────────────────────────────────────────
def load_kpi_data(start_date, end_date, country=None) -> dict:
    """Returns aggregated KPIs for the selected period + prior period for delta."""
    client = get_bq_client()

    def _where(s, e, c):
        conds = [f"CAST(date AS DATE) BETWEEN '{s}' AND '{e}'"]
        if c and c not in ("", "All"):
            conds.append(f"rc_country = '{c}'")
        return " AND ".join(conds)

    days = (end_date - start_date).days if hasattr(end_date, "days") else 28
    try:
        days = (
            pd.Timestamp(end_date) - pd.Timestamp(start_date)
        ).days
    except Exception:
        days = 28

    prior_end   = pd.Timestamp(start_date) - pd.Timedelta(days=1)
    prior_start = prior_end - pd.Timedelta(days=days)

    def _run(s, e):
        q = f"""
            SELECT
                SUM(gross_revenue) AS gross_revenue,
                SUM(proceeds)      AS proceeds,
                SUM(spend)         AS spend
            FROM `{TABLE}` WHERE {_where(s, e, country)}
        """
        return client.query(q).to_dataframe().iloc[0]

    try:
        cur  = _run(start_date, end_date)
        prev = _run(str(prior_start.date()), str(prior_end.date()))

        def pct(c, p):
            return ((c - p) / p * 100) if p and p != 0 else 0.0

        return {
            "gross_revenue": float(cur["gross_revenue"] or 0),
            "proceeds":      float(cur["proceeds"]      or 0),
            "spend":         float(cur["spend"]         or 0),
            "gr_delta":      pct(cur["gross_revenue"], prev["gross_revenue"]),
            "pr_delta":      pct(cur["proceeds"],      prev["proceeds"]),
            "sp_delta":      pct(cur["spend"],         prev["spend"]),
        }
    except Exception as e:
        print(f"[data] load_kpi_data: {e}")
        return {"gross_revenue": 0, "proceeds": 0, "spend": 0,
                "gr_delta": 0, "pr_delta": 0, "sp_delta": 0}


# ── Proceeds trend (line chart) ───────────────────────────────────────────────
def get_proceeds_trend(start_date, end_date, country=None) -> pd.DataFrame:
    client = get_bq_client()
    conds  = [f"CAST(date AS DATE) BETWEEN '{start_date}' AND '{end_date}'"]
    if country and country not in ("", "All"):
        conds.append(f"rc_country = '{country}'")
    where = " AND ".join(conds)

    q = f"""
        SELECT
            CAST(date AS DATE) AS date,
            SUM(proceeds)      AS proceeds
        FROM `{TABLE}` WHERE {where}
        GROUP BY date ORDER BY date
    """
    try:
        df = client.query(q).to_dataframe()
        df["date"]     = pd.to_datetime(df["date"])
        df["proceeds"] = pd.to_numeric(df["proceeds"], errors="coerce").fillna(0)
        return df
    except Exception as e:
        print(f"[data] get_proceeds_trend: {e}")
        return pd.DataFrame(columns=["date", "proceeds"])


# ── ARPU daily by platform ────────────────────────────────────────────────────
def get_arpu_daily(start_date, end_date) -> pd.DataFrame:
    client = get_bq_client()
    q = f"""
        SELECT
            DATE(date)      AS date,
            platform,
            SUM(proceeds)   AS proceeds,
            MAX(total_active_subscriptions) AS active_subs,
            SAFE_DIVIDE(SUM(proceeds),
                NULLIF(MAX(total_active_subscriptions), 0)) AS arpu
        FROM `{ARPU_TABLE}`
        WHERE country = 'Total'
          AND DATE(date) BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY date, platform
        ORDER BY date, platform
    """
    try:
        df = client.query(q).to_dataframe()
        df["date"] = pd.to_datetime(df["date"])
        for col in ["proceeds", "active_subs", "arpu"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except Exception as e:
        print(f"[data] get_arpu_daily: {e}")
        return pd.DataFrame(columns=["date", "platform", "proceeds", "active_subs", "arpu"])


# ── ARPU by platform aggregate ────────────────────────────────────────────────
def get_arpu_by_platform(start_date, end_date) -> pd.DataFrame:
    client = get_bq_client()
    q = f"""
        WITH monthly AS (
            SELECT
                DATE_TRUNC(DATE(date), MONTH) AS month,
                platform,
                SUM(proceeds) AS monthly_proceeds,
                ARRAY_AGG(total_active_subscriptions
                    ORDER BY date DESC LIMIT 1)[OFFSET(0)] AS active_end
            FROM `{ARPU_TABLE}`
            WHERE country = 'Total'
              AND DATE(date) BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY month, platform
        )
        SELECT
            platform,
            SUM(monthly_proceeds) AS total_proceeds,
            AVG(SAFE_DIVIDE(monthly_proceeds, NULLIF(active_end, 0))) AS avg_arpu
        FROM monthly
        GROUP BY platform
        ORDER BY avg_arpu DESC
    """
    try:
        df = client.query(q).to_dataframe()
        for col in ["total_proceeds", "avg_arpu"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except Exception as e:
        print(f"[data] get_arpu_by_platform: {e}")
        return pd.DataFrame(columns=["platform", "total_proceeds", "avg_arpu"])
