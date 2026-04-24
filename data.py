"""
data.py — BigQuery data layer for the Vinita Analytics Dashboard.
"""

import os
import time
import hashlib
import json
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import date, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID   = "vinita-388203"
TABLE        = "vinita-388203.dataform.mrt_final_vinita"
ARPU_TABLE   = "vinita-388203.vinita_rc_new.daily_metrics_rc"
COHORT_TABLE = "vinita-388203.dataform.mrt_cohort_vinita"
KEY_PATH     = os.path.join(os.path.dirname(__file__), "vinita-key.json")

# ── Simple In-Process Cache ───────────────────────────────────────────────────
# dcc.Store handles UI state (granularity); this handles BQ query results.
# TTL = 5 minutes. Shared across all callbacks in this process.
CACHE: dict = {}
CACHE_TTL   = 300  # seconds

# ── Client ────────────────────────────────────────────────────────────────────
def get_bq_client() -> bigquery.Client:
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(credentials=creds, project=PROJECT_ID)


# ── Cache Helpers ─────────────────────────────────────────────────────────────
def _cache_key(tag: str, params: dict) -> str:
    raw = f"{tag}|{json.dumps(params, sort_keys=True, default=str)}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cached(key: str, query_fn):
    """Return cached value if fresh, else call query_fn() and store result."""
    now = time.time()
    if key in CACHE:
        value, ts = CACHE[key]
        if now - ts < CACHE_TTL:
            return value
    result = query_fn()
    CACHE[key] = (result, now)
    return result


# ── Smart default date range ──────────────────────────────────────────────────
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
    def _query():
        try:
            client = get_bq_client()
            q = f"""
                SELECT DISTINCT rc_country
                FROM `{TABLE}`
                WHERE rc_country IS NOT NULL AND rc_country != ''
                  AND rc_country != 'Total' /* Filter out 'Total' to avoid double counting */
                ORDER BY rc_country LIMIT 200
            """
            df = client.query(q).to_dataframe()
            return [{"label": c, "value": c} for c in df["rc_country"].tolist()]
        except Exception as e:
            print(f"[data] get_country_options: {e}")
            return []
    
    key = _cache_key('country_options', {})
    return _get_cached(key, _query)


# ── Platform Options ──────────────────────────────────────────────────────────
def get_platform_options() -> list[dict]:
    def _query():
        try:
            client = get_bq_client()
            q = f"""
                SELECT DISTINCT rc_platform
                FROM `{TABLE}`
                WHERE rc_platform IS NOT NULL AND rc_platform != ''
                ORDER BY rc_platform LIMIT 50
            """
            df = client.query(q).to_dataframe()
            return [{"label": p, "value": p} for p in df["rc_platform"].tolist()]
        except Exception as e:
            print(f"[data] get_platform_options: {e}")
            return []
    
    key = _cache_key('platform_options', {})
    return _get_cached(key, _query)


# ── Main KPI data (3 scorecards) ──────────────────────────────────────────────
def load_kpi_data(start_date, end_date, country=None) -> dict:
    """Returns aggregated KPIs for the selected period + prior period for delta."""
    def _query():
        client = get_bq_client()

        def _where(s, e, c):
            # Filter out 'Total' to avoid double counting across all countries
            conds = [f"CAST(date AS DATE) BETWEEN '{s}' AND '{e}'", "rc_country != 'Total'"]
            if c and c not in ("", "All"):
                conds.append(f"rc_country = '{c}'")
            return " AND ".join(conds)

        try:
            days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
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

        def _run_subs(s, e):
            q = f"""
                SELECT SUM(active_subscriptions) AS active_subs
                FROM `{TABLE}`
                WHERE {_where(s, e, country)}
                  AND CAST(date AS DATE) = (
                      SELECT MAX(CAST(date AS DATE))
                      FROM `{TABLE}`
                      WHERE {_where(s, e, country)}
                  )
            """
            try:
                res = client.query(q).to_dataframe()
                if not res.empty and pd.notna(res.iloc[0]["active_subs"]):
                    return float(res.iloc[0]["active_subs"])
            except Exception as ex:
                print(f"[data] _run_subs: {ex}")
            return 0.0

        try:
            cur  = _run(start_date, end_date)
            prev = _run(str(prior_start.date()), str(prior_end.date()))
            
            cur_subs = _run_subs(start_date, end_date)
            prev_subs = _run_subs(str(prior_start.date()), str(prior_end.date()))

            def pct(c, p):
                return ((c - p) / p * 100) if p and p != 0 else 0.0

            def _sf(val):
                try:
                    return float(val) if pd.notna(val) else 0.0
                except (ValueError, TypeError):
                    return 0.0

            return {
                "gross_revenue": _sf(cur["gross_revenue"]),
                "proceeds":      _sf(cur["proceeds"]),
                "spend":         _sf(cur["spend"]),
                "active_subs":   cur_subs,
                "gr_delta":      pct(_sf(cur["gross_revenue"]), _sf(prev["gross_revenue"])),
                "pr_delta":      pct(_sf(cur["proceeds"]),      _sf(prev["proceeds"])),
                "sp_delta":      pct(_sf(cur["spend"]),         _sf(prev["spend"])),
                "subs_delta":    pct(cur_subs, prev_subs),
            }
        except Exception as e:
            print(f"[data] load_kpi_data: {e}")
            return {"gross_revenue": 0, "proceeds": 0, "spend": 0, "active_subs": 0,
                    "gr_delta": 0, "pr_delta": 0, "sp_delta": 0, "subs_delta": 0}

    key = _cache_key('kpi_data', {'start': start_date, 'end': end_date, 'country': country})
    return _get_cached(key, _query)


# ── Proceeds trend (line chart) ───────────────────────────────────────────────
def get_proceeds_trend(start_date, end_date, country=None) -> pd.DataFrame:
    def _query():
        client = get_bq_client()
        # Filter out 'Total' to avoid double counting
        conds  = [f"CAST(date AS DATE) BETWEEN '{start_date}' AND '{end_date}'", "rc_country != 'Total'"]
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

    key = _cache_key('proceeds_trend', {'start': start_date, 'end': end_date, 'country': country})
    return _get_cached(key, _query)


# ── ARPU daily by platform ────────────────────────────────────────────────────
def get_arpu_daily(start_date, end_date) -> pd.DataFrame:
    def _query():
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

    key = _cache_key('arpu_daily', {'start': start_date, 'end': end_date})
    return _get_cached(key, _query)


# ── ARPU by platform aggregate ────────────────────────────────────────────────
def get_arpu_by_platform(start_date, end_date) -> pd.DataFrame:
    def _query():
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

    key = _cache_key('arpu_by_platform', {'start': start_date, 'end': end_date})
    return _get_cached(key, _query)


# ── Monthly Churn ─────────────────────────────────────────────────────────────
def get_monthly_churn(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    client = get_bq_client()

    # Filter out 'Total' to avoid double counting
    conds = [f"DATE(date) BETWEEN '{start_date}' AND '{end_date}'", "rc_country != 'Total'"]
    if country and country not in ("", "All", "Total"):
        conds.append(f"rc_country = '{country}'")
    if platform and platform not in ("", "All"):
        conds.append(f"rc_platform = '{platform}'")

    where_clause = " AND ".join(conds)

    q = f"""
    WITH daily_agg AS (
        SELECT
            DATE(date) AS dt,
            FORMAT_DATE('%Y-%m', DATE(date)) AS month,
            SUM(active_subscriptions) AS active_subscriptions,
            SUM(churned_active) AS churned_active
        FROM `{TABLE}`
        WHERE {where_clause}
        GROUP BY dt, month
    ),
    monthly_calc AS (
        SELECT
            month,
            ARRAY_AGG(active_subscriptions ORDER BY dt DESC LIMIT 1)[OFFSET(0)]
              AS active_subscription_end,
            SUM(churned_active) AS total_churned
        FROM daily_agg
        GROUP BY month
    )
    SELECT
        month,
        active_subscription_end,
        total_churned,
        SAFE_DIVIDE(total_churned, active_subscription_end) * 100 AS churn_rate_pct
    FROM monthly_calc
    ORDER BY month
    """

    def _query():
        try:
            df = client.query(q).to_dataframe()
            df['month'] = pd.to_datetime(df['month'])
            for col in ['active_subscription_end', 'total_churned', 'churn_rate_pct']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] get_monthly_churn: {e}")
            return pd.DataFrame(columns=['month', 'active_subscription_end',
                                         'total_churned', 'churn_rate_pct'])

    key = _cache_key('monthly_churn', {'start': start_date, 'end': end_date,
                                        'country': country, 'platform': platform})
    return _get_cached(key, _query)


# ── Cohort LTV Data ───────────────────────────────────────────────────────────
def get_cohort_ltv_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    """
    Pulls LTV data from the cohort table.
    Change 5: country filter supports AU/CA/GB/US (passed directly).
    """
    client = get_bq_client()

    conds = [f"DATE(date) BETWEEN '{start_date}' AND '{end_date}'"]
    if country and country not in ("", "All", "Total"):
        conds.append(f"country = '{country}'")
    if platform and platform not in ("", "All"):
        conds.append(f"platform = '{platform}'")

    where_clause = " AND ".join(conds)

    q = f"""
    SELECT
        date,
        country,
        country_name,
        platform,
        realized_ltv_0d,
        realized_ltv_7d,
        realized_ltv_30d,
        realized_ltv_90d,
        realized_ltv_180d,
        realized_ltv_365d,
        proceeds_0d,
        proceeds_7d,
        proceeds_30d,
        proceeds_90d,
        proceeds_180d,
        proceeds_365d,
        campaign_name,
        impressions,
        reach,
        clicks,
        spend,
        campaign_id,
        campaign_objective,
        campaign_status
    FROM `{COHORT_TABLE}`
    WHERE {where_clause}
    ORDER BY date DESC
    """

    def _query():
        try:
            df = client.query(q).to_dataframe()
            df['date'] = pd.to_datetime(df['date'])
            numeric_cols = [
                'realized_ltv_0d', 'realized_ltv_7d', 'realized_ltv_30d',
                'realized_ltv_90d', 'realized_ltv_180d', 'realized_ltv_365d',
                'proceeds_0d', 'proceeds_7d', 'proceeds_30d', 'proceeds_90d',
                'proceeds_180d', 'proceeds_365d',
                'impressions', 'reach', 'clicks', 'spend'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] get_cohort_ltv_data: {e}")
            return pd.DataFrame()

    key = _cache_key('cohort_ltv', {'start': start_date, 'end': end_date,
                                     'country': country, 'platform': platform})
    return _get_cached(key, _query)


# ── ROAS Calculation ──────────────────────────────────────────────────────────
# Change 4: COALESCE each nullable proceeds column so SUM doesn't return NULL
def get_roas_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    client = get_bq_client()

    conds = [f"DATE(date) BETWEEN '{start_date}' AND '{end_date}'"]
    if country and country not in ("", "All", "Total"):
        conds.append(f"country = '{country}'")
    if platform and platform not in ("", "All"):
        conds.append(f"platform = '{platform}'")

    where_clause = " AND ".join(conds)

    q = f"""
    WITH proceeds_data AS (
        SELECT
            DATE(date) AS date,
            SUM(
                COALESCE(proceeds_7d,   0) +
                COALESCE(proceeds_30d,  0) +
                COALESCE(proceeds_90d,  0) +
                COALESCE(proceeds_180d, 0) +
                COALESCE(proceeds_365d, 0)
            ) AS total_proceeds,
            SUM(COALESCE(spend, 0)) AS total_spend
        FROM `{COHORT_TABLE}`
        WHERE {where_clause}
        GROUP BY DATE(date)
    )
    SELECT
        date,
        total_proceeds,
        total_spend,
        SAFE_DIVIDE(total_proceeds, NULLIF(total_spend, 0)) AS roas
    FROM proceeds_data
    ORDER BY date
    """

    def _query():
        try:
            df = client.query(q).to_dataframe()
            print(f"[data] get_roas_data: {len(df)} rows returned")
            if df.empty:
                print("[data] get_roas_data: query returned 0 rows — check date/country filters")
                return pd.DataFrame(columns=['date', 'total_proceeds', 'total_spend', 'roas'])
            df['date'] = pd.to_datetime(df['date'])
            for col in ['total_proceeds', 'total_spend', 'roas']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] get_roas_data ERROR: {e}")
            return pd.DataFrame(columns=['date', 'total_proceeds', 'total_spend', 'roas'])

    key = _cache_key('roas', {'start': start_date, 'end': end_date,
                               'country': country, 'platform': platform})
    return _get_cached(key, _query)


# ── CAC Calculation ───────────────────────────────────────────────────────────
# Change 4: remove strict WHERE filter so 0-new-subscription days are included;
#           roas stays as SAFE_DIVIDE which returns NULL → 0 for those days.
def get_cac_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    client = get_bq_client()

    # Filter out 'Total' to avoid double counting
    conds = [f"DATE(date) BETWEEN '{start_date}' AND '{end_date}'", "rc_country != 'Total'"]
    if country and country not in ("", "All", "Total"):
        conds.append(f"rc_country = '{country}'")
    if platform and platform not in ("", "All"):
        conds.append(f"rc_platform = '{platform}'")

    where_clause = " AND ".join(conds)

    q = f"""
    WITH cac_calc AS (
        SELECT
            DATE(date) AS date,
            SUM(COALESCE(spend, 0))                        AS total_spend,
            SUM(COALESCE(total_new_paid_subscriptions, 0))  AS total_new_paid_subscriptions
        FROM `{TABLE}`
        WHERE {where_clause}
        GROUP BY DATE(date)
    )
    SELECT
        date,
        total_spend,
        total_new_paid_subscriptions,
        SAFE_DIVIDE(total_spend, NULLIF(total_new_paid_subscriptions, 0)) AS cac
    FROM cac_calc
    WHERE total_spend > 0 OR total_new_paid_subscriptions > 0
    ORDER BY date
    """

    def _query():
        try:
            df = client.query(q).to_dataframe()
            print(f"[data] get_cac_data: {len(df)} rows returned")
            if df.empty:
                print("[data] get_cac_data: query returned 0 rows — check date/country filters")
                return pd.DataFrame(columns=['date', 'total_spend',
                                             'total_new_paid_subscriptions', 'cac'])
            df['date'] = pd.to_datetime(df['date'])
            for col in ['total_spend', 'total_new_paid_subscriptions', 'cac']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            # Filter rows where CAC is meaningful (>0)
            df = df[df['cac'] > 0].copy()
            return df
        except Exception as e:
            print(f"[data] get_cac_data ERROR: {e}")
            return pd.DataFrame(columns=['date', 'total_spend',
                                         'total_new_paid_subscriptions', 'cac'])

    key = _cache_key('cac', {'start': start_date, 'end': end_date,
                              'country': country, 'platform': platform})
    return _get_cached(key, _query)


# ── CAC vs LTV Thresholds (Change 6) ─────────────────────────────────────────
# Joins mrt_final_vinita (CAC) with mrt_cohort_vinita (LTV 30d) on date.
def get_cac_ltv_thresholds(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    """
    Returns daily rows with columns:
        date, cac, ltv_30d, healthy_cac_threshold (ltv/3), aggressive_cac_threshold (ltv/2)

    CAC comes from mrt_final_vinita (rc_country / rc_platform).
    LTV 30d comes from mrt_cohort_vinita (country / platform).
    They are joined on date.
    """
    client = get_bq_client()

    # Build WHERE clauses for each table separately (different column names)
    # Filter out 'Total' from CAC (mrt_final_vinita) to avoid double counting
    cac_conds = [f"DATE(date) BETWEEN '{start_date}' AND '{end_date}'", "rc_country != 'Total'"]
    ltv_conds = [f"DATE(date) BETWEEN '{start_date}' AND '{end_date}'"]

    if country and country not in ("", "All", "Total"):
        cac_conds.append(f"rc_country = '{country}'")
        ltv_conds.append(f"country = '{country}'")
    if platform and platform not in ("", "All"):
        cac_conds.append(f"rc_platform = '{platform}'")
        ltv_conds.append(f"platform = '{platform}'")

    cac_where = " AND ".join(cac_conds)
    ltv_where = " AND ".join(ltv_conds)

    q = f"""
    WITH cac_data AS (
        SELECT
            DATE(date) AS date,
            SUM(COALESCE(spend, 0))                       AS total_spend,
            SUM(COALESCE(total_new_paid_subscriptions, 0)) AS total_new_subs,
            SAFE_DIVIDE(
                SUM(COALESCE(spend, 0)),
                NULLIF(SUM(COALESCE(total_new_paid_subscriptions, 0)), 0)
            ) AS cac
        FROM `{TABLE}`
        WHERE {cac_where}
        GROUP BY DATE(date)
    ),
    ltv_data AS (
        SELECT
            DATE(date) AS date,
            AVG(COALESCE(realized_ltv_30d, 0)) AS ltv_30d
        FROM `{COHORT_TABLE}`
        WHERE {ltv_where}
        GROUP BY DATE(date)
    )
    SELECT
        c.date,
        c.cac,
        l.ltv_30d,
        SAFE_DIVIDE(l.ltv_30d, 3) AS healthy_cac_threshold,
        SAFE_DIVIDE(l.ltv_30d, 2) AS aggressive_cac_threshold
    FROM cac_data c
    INNER JOIN ltv_data l ON c.date = l.date
    WHERE c.cac IS NOT NULL AND c.cac > 0 AND l.ltv_30d > 0
    ORDER BY c.date
    """

    def _query():
        try:
            df = client.query(q).to_dataframe()
            print(f"[data] get_cac_ltv_thresholds: {len(df)} rows returned")
            if df.empty:
                print("[data] get_cac_ltv_thresholds: 0 rows — may need wider date range or no country filter")
                return pd.DataFrame(columns=['date', 'cac', 'ltv_30d',
                                             'healthy_cac_threshold', 'aggressive_cac_threshold'])
            df['date'] = pd.to_datetime(df['date'])
            for col in ['cac', 'ltv_30d', 'healthy_cac_threshold', 'aggressive_cac_threshold']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] get_cac_ltv_thresholds ERROR: {e}")
            return pd.DataFrame(columns=['date', 'cac', 'ltv_30d',
                                         'healthy_cac_threshold', 'aggressive_cac_threshold'])

    key = _cache_key('cac_ltv_thresh', {'start': start_date, 'end': end_date,
                                         'country': country, 'platform': platform})
    return _get_cached(key, _query)
