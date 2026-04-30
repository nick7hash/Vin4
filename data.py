"""
data.py — BigQuery data layer for the Vinita Analytics Dashboard.
(Optimized: Fetch Once, Filter Often)
"""

import os
import time
import hashlib
import json
import threading
import pickle
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import date, timedelta

# Try to initialize Redis for Vercel serverless persistence
try:
    import redis
    # Vercel KV provides KV_URL, Upstash provides UPSTASH_REDIS_REST_URL or REDIS_URL
    redis_url = os.getenv("KV_URL") or os.getenv("REDIS_URL")
    if redis_url:
        REDIS_CLIENT = redis.Redis.from_url(redis_url)
    else:
        REDIS_CLIENT = None
except ImportError:
    REDIS_CLIENT = None

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID   = "vinita-388203"
TABLE        = "vinita-388203.dataform.mrt_final_vinita"
ARPU_TABLE   = "vinita-388203.vinita_rc_new.daily_metrics_rc"
COHORT_TABLE = "vinita-388203.dataform.mrt_cohort_vinita"
KEY_PATH     = os.path.join(os.path.dirname(__file__), "vinita-key.json")

# =============================================================================
# ── Caching System ──
# To make the dashboard lightning fast, we use this dictionary as memory.
# When BigQuery returns data, we save it here for 10 minutes (`CACHE_TTL`).
# If you change a dropdown before 10 minutes, it uses this memory instead of querying again.
# =============================================================================
CACHE: dict = {}
CACHE_TTL   = 600  # 10 minutes (600 seconds)

# Threading locks to prevent cache stampedes (i.e. multiple callbacks requesting the same data simultaneously)
CACHE_LOCK = threading.Lock()
KEY_LOCKS = {}
KEY_LOCKS_LOCK = threading.Lock()

COUNTRY_MAP = {
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia"
}

# =============================================================================
# ── Database Authentication ──
# Connects to Google BigQuery. It tries to use environment variables first (for Vercel),
# and falls back to `vinita-key.json` if you're running it locally.
# =============================================================================
def get_bq_client() -> bigquery.Client:
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        try:
            creds_info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(
                creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            return bigquery.Client(credentials=creds, project=PROJECT_ID)
        except Exception as e:
            print(f"[data] Failed to parse GOOGLE_CREDENTIALS: {e}")

    try:
        creds = service_account.Credentials.from_service_account_file(
            KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return bigquery.Client(credentials=creds, project=PROJECT_ID)
    except FileNotFoundError:
        return bigquery.Client(project=PROJECT_ID)


def _cache_key(tag: str, params: dict) -> str:
    raw = f"{tag}|{json.dumps(params, sort_keys=True, default=str)}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cached(key: str, query_fn):
    """
    Retrieves data from the cache. If the data is missing or expired, it runs the query_fn.
    Uses locks to prevent multiple threads from querying BigQuery for the same data simultaneously.
    If REDIS is configured (Vercel KV), it uses Redis to share cache across serverless instances.
    """
    now = time.time()
    
    # 0. Try Redis first (Shared across Vercel serverless instances)
    if REDIS_CLIENT:
        try:
            cached_data = REDIS_CLIENT.get(key)
            if cached_data:
                return pickle.loads(cached_data)
        except Exception as e:
            print(f"[Cache] Redis GET error: {e}")
            
    # 1. Fast path: check if valid data exists in local memory (Fallback)
    with CACHE_LOCK:
        if key in CACHE:
            value, ts = CACHE[key]
            if now - ts < CACHE_TTL:
                return value

    # 2. Get or create a lock specific to this query key
    with KEY_LOCKS_LOCK:
        if key not in KEY_LOCKS:
            KEY_LOCKS[key] = threading.Lock()
        lock = KEY_LOCKS[key]

    # 3. Acquire the lock and query
    with lock:
        # Check local cache one more time in case another thread just finished querying
        now = time.time()
        with CACHE_LOCK:
            if key in CACHE:
                value, ts = CACHE[key]
                if now - ts < CACHE_TTL:
                    return value
        
        # Check Redis one more time
        if REDIS_CLIENT:
            try:
                cached_data = REDIS_CLIENT.get(key)
                if cached_data:
                    result = pickle.loads(cached_data)
                    # Sync local memory cache with Redis
                    with CACHE_LOCK:
                        CACHE[key] = (result, now)
                    return result
            except Exception:
                pass
        
        # 4. Actually run the expensive query
        result = query_fn()
        
        # 5. Save back to local cache
        with CACHE_LOCK:
            CACHE[key] = (result, time.time())
            
        # 6. Save back to Redis (Vercel)
        if REDIS_CLIENT:
            try:
                REDIS_CLIENT.setex(key, CACHE_TTL, pickle.dumps(result))
            except Exception as e:
                print(f"[Cache] Redis SET error: {e}")
            
        return result

# ── Smart default date range ──────────────────────────────────────────────────
def get_default_dates():
    try:
        client = get_bq_client()
        q = f"SELECT MAX(CAST(date AS DATE)) AS mx FROM `{TABLE}`"
        df = client.query(q).to_dataframe()
        mx = df["mx"].iloc[0]
        if mx is not None:
            end_d = pd.to_datetime(mx).date()
            start_d = date(2026, 1, 1)  # Default start date set to Jan 1, 2026
            return start_d, end_d
    except:
        pass
    end_d = date.today()
    return date(2026, 1, 1), end_d

def get_country_options() -> list[dict]:
    # Hardcoded to avoid BQ query, as requested by user
    return [
        {"label": "🇦🇺 Australia",      "value": "AU"},
        {"label": "🇨🇦 Canada",         "value": "CA"},
        {"label": "🇬🇧 United Kingdom", "value": "GB"},
        {"label": "🇺🇸 United States",  "value": "US"},
    ]

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
            return []
    return _get_cached(_cache_key('platform_options', {}), _query)


# =============================================================================
# ── BASE DATAFRAME FETCHERS (The "Fetch Once" Part) ──
# Instead of querying BigQuery every time a user clicks a filter, these functions 
# fetch ALL data for a selected date range at once. This huge chunk of data 
# is then saved in `CACHE`.
# =============================================================================

def _get_base_final_df(start_date, end_date) -> pd.DataFrame:
    """Fetches the main KPI table for the date range (ignoring country/platform filters)."""
    # Need to fetch slightly earlier data for prior period calculations
    try:
        days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
    except:
        days = 28
    
    # We fetch an extra 'days + 1' back so we can calculate previous period deltas
    extended_start = (pd.Timestamp(start_date) - pd.Timedelta(days=days+1)).date()

    def _query():
        client = get_bq_client()
        q = f"""
            SELECT
                CAST(date AS DATE) AS date,
                rc_country,
                rc_platform,
                SUM(gross_revenue) AS gross_revenue,
                SUM(proceeds) AS proceeds,
                SUM(spend) AS spend,
                SUM(active_subscriptions) AS active_subscriptions,
                SUM(churned_active) AS churned_active,
                SUM(total_new_paid_subscriptions) AS total_new_paid_subscriptions,
                SUM(installs) AS installs
            FROM `{TABLE}`
            WHERE CAST(date AS DATE) BETWEEN '{extended_start}' AND '{end_date}'
              AND (rc_country != 'Total' OR rc_country IS NULL)
            GROUP BY date, rc_country, rc_platform
        """
        try:
            df = client.query(q).to_dataframe()
            df['date'] = pd.to_datetime(df['date'])
            for col in ['gross_revenue', 'proceeds', 'spend', 'active_subscriptions', 'churned_active', 'total_new_paid_subscriptions', 'installs']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] _get_base_final_df ERROR: {e}")
            return pd.DataFrame()

    return _get_cached(_cache_key('base_final', {'s': str(extended_start), 'e': str(end_date)}), _query)

def _get_base_cohort_df(start_date, end_date) -> pd.DataFrame:
    def _query():
        client = get_bq_client()
        q = f"""
            SELECT
                DATE(date) AS date,
                country,
                platform,
                realized_ltv_0d, realized_ltv_7d, realized_ltv_30d, realized_ltv_90d, realized_ltv_180d, realized_ltv_365d,
                proceeds_0d, proceeds_7d, proceeds_30d, proceeds_90d, proceeds_180d, proceeds_365d,
                spend
            FROM `{COHORT_TABLE}`
            WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
              AND country != 'Total'
        """
        try:
            df = client.query(q).to_dataframe()
            df['date'] = pd.to_datetime(df['date'])
            numeric_cols = [
                'realized_ltv_0d', 'realized_ltv_7d', 'realized_ltv_30d', 'realized_ltv_90d', 'realized_ltv_180d', 'realized_ltv_365d',
                'proceeds_0d', 'proceeds_7d', 'proceeds_30d', 'proceeds_90d', 'proceeds_180d', 'proceeds_365d', 'spend'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] _get_base_cohort_df ERROR: {e}")
            return pd.DataFrame()
    return _get_cached(_cache_key('base_cohort', {'s': str(start_date), 'e': str(end_date)}), _query)


# =============================================================================
# ── FILTERING HELPERS (The "Filter Often" Part) ──
# This function takes the huge chunk of cached data and slices it instantly 
# using Pandas based on whatever country/platform the user clicked.
# =============================================================================

def _filter_df(df, country_col, platform_col, country=None, platform=None, map_country=False):
    if df.empty: return df
    res = df.copy()
    if country and country not in ("", "All", "Total"):
        c = COUNTRY_MAP.get(country, country) if map_country else country
        res = res[res[country_col] == c]
    if platform and platform not in ("", "All"):
        res = res[res[platform_col] == platform]
    return res


# =============================================================================
# ── DATA ACCESS FUNCTIONS ──
# These are the actual functions called by `app.py`. 
# They grab the cached data, filter it, do the math (sums, averages), 
# and return the final numbers to be displayed on the screen.
# =============================================================================

def load_kpi_data(start_date, end_date, country=None, platform=None) -> dict:
    df = _get_base_final_df(start_date, end_date)
    if df.empty:
        return {"gross_revenue": 0, "proceeds": 0, "spend": 0, "active_subs": 0, "gr_delta": 0, "pr_delta": 0, "sp_delta": 0, "subs_delta": 0}

    # Filter
    df_f = _filter_df(df, 'rc_country', 'rc_platform', country, platform, map_country=True)
    
    # Time periods
    s_dt = pd.to_datetime(start_date)
    e_dt = pd.to_datetime(end_date)
    try: days = (e_dt - s_dt).days
    except: days = 28
    p_end = s_dt - pd.Timedelta(days=1)
    p_start = p_end - pd.Timedelta(days=days)

    cur_df = df_f[(df_f['date'] >= s_dt) & (df_f['date'] <= e_dt)]
    prev_df = df_f[(df_f['date'] >= p_start) & (df_f['date'] <= p_end)]

    cur = cur_df[['gross_revenue', 'proceeds', 'spend']].sum()
    prev = prev_df[['gross_revenue', 'proceeds', 'spend']].sum()

    # Active Subs logic
    cur_subs = 0.0
    if not cur_df.empty:
        max_dt = cur_df['date'].max()
        cur_subs = cur_df[cur_df['date'] == max_dt]['active_subscriptions'].sum()

    prev_subs = 0.0
    if not prev_df.empty:
        max_dt_p = prev_df['date'].max()
        prev_subs = prev_df[prev_df['date'] == max_dt_p]['active_subscriptions'].sum()

    def pct(c, p):
        return ((c - p) / p * 100) if p and p != 0 else 0.0

    return {
        "gross_revenue": float(cur.get("gross_revenue", 0)),
        "proceeds":      float(cur.get("proceeds", 0)),
        "spend":         float(cur.get("spend", 0)),
        "active_subs":   float(cur_subs),
        "gr_delta":      pct(cur.get("gross_revenue",0), prev.get("gross_revenue",0)),
        "pr_delta":      pct(cur.get("proceeds",0), prev.get("proceeds",0)),
        "sp_delta":      pct(cur.get("spend",0), prev.get("spend",0)),
        "subs_delta":    pct(cur_subs, prev_subs),
    }

def get_proceeds_trend(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_final_df(start_date, end_date)
    if df.empty: return pd.DataFrame(columns=["date", "proceeds"])
    
    # Filter strictly for the current period (base df has extended start)
    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]
    
    df_f = _filter_df(df, 'rc_country', 'rc_platform', country, platform, map_country=True)
    res = df_f.groupby('date', as_index=False)['proceeds'].sum().sort_values('date')
    return res

def get_monthly_churn(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_final_df(start_date, end_date)
    if df.empty: return pd.DataFrame(columns=['month', 'active_subscription_end', 'total_churned', 'churn_rate_pct'])
    
    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]
    df_f = _filter_df(df, 'rc_country', 'rc_platform', country, platform, map_country=True)
    
    if df_f.empty: return pd.DataFrame(columns=['month', 'active_subscription_end', 'total_churned', 'churn_rate_pct'])

    df_f['month'] = df_f['date'].dt.to_period('M')
    
    # Group by exact date first to sum across countries/platforms for that day
    daily_agg = df_f.groupby(['date', 'month'], as_index=False)[['active_subscriptions', 'churned_active']].sum()
    
    # Then group by month
    monthly = []
    for m, m_df in daily_agg.groupby('month'):
        m_df = m_df.sort_values('date')
        end_subs = m_df.iloc[-1]['active_subscriptions']
        tot_churn = m_df['churned_active'].sum()
        rate = (tot_churn / end_subs * 100) if end_subs else 0
        monthly.append({
            'month': m.to_timestamp(),
            'active_subscription_end': end_subs,
            'total_churned': tot_churn,
            'churn_rate_pct': rate
        })
        
    return pd.DataFrame(monthly).sort_values('month')

def get_ltv_net_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_final_df(start_date, end_date)
    if df.empty: return pd.DataFrame(columns=['month', 'ltv_net'])
    
    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]
    df_f = _filter_df(df, 'rc_country', 'rc_platform', country, platform, map_country=True)
    
    if df_f.empty: return pd.DataFrame(columns=['month', 'ltv_net'])

    df_f['month'] = df_f['date'].dt.to_period('M')
    
    # Group by exact date first to sum across countries/platforms for that day
    daily_agg = df_f.groupby(['date', 'month'], as_index=False)[['active_subscriptions', 'churned_active', 'proceeds']].sum()
    
    monthly = []
    for m, m_df in daily_agg.groupby('month'):
        m_df = m_df.sort_values('date')
        end_subs = m_df.iloc[-1]['active_subscriptions']
        tot_churn = m_df['churned_active'].sum()
        monthly_proceeds = m_df['proceeds'].sum()
        
        churn_rate_decimal = (tot_churn / end_subs) if end_subs else 0
        arpu_net = (monthly_proceeds / end_subs) if end_subs else 0
        
        ltv_net = (arpu_net / churn_rate_decimal) if churn_rate_decimal > 0 else 0
        
        monthly.append({
            'month': m.to_timestamp(),
            'ltv_net': ltv_net
        })
        
    return pd.DataFrame(monthly).sort_values('month')

def get_cac_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_final_df(start_date, end_date)
    if df.empty: return pd.DataFrame(columns=['date', 'total_spend', 'total_new_paid_subscriptions', 'cac'])
    
    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]
    df_f = _filter_df(df, 'rc_country', 'rc_platform', country, platform, map_country=True)
    
    res = df_f.groupby('date', as_index=False)[['spend', 'total_new_paid_subscriptions']].sum()
    res = res.rename(columns={'spend': 'total_spend'})
    
    # Calculate CAC
    res['cac'] = res.apply(lambda x: x['total_spend'] / x['total_new_paid_subscriptions'] if x['total_new_paid_subscriptions'] > 0 else 0, axis=1)
    
    # Meaningful CAC
    res = res[res['cac'] >= 0].copy()
    return res

def get_conversion_rate_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    # Installs are only tracked globally (rc_country/rc_platform are NULL),
    # so we must run a dedicated query ignoring those filters to get correct numbers.
    def _query():
        client = get_bq_client()
        q = f"""
            SELECT
                CAST(date AS DATE) AS date,
                SUM(installs) AS installs,
                SUM(total_new_paid_subscriptions) AS total_new_paid_subscriptions
            FROM `{TABLE}`
            WHERE CAST(date AS DATE) BETWEEN '{start_date}' AND '{end_date}'
              AND (rc_country != 'Total' OR rc_country IS NULL)
            GROUP BY date
            ORDER BY date
        """
        try:
            df = client.query(q).to_dataframe()
            df['date'] = pd.to_datetime(df['date'])
            for col in ['installs', 'total_new_paid_subscriptions']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df['conversion_rate'] = df.apply(
                lambda x: (x['total_new_paid_subscriptions'] / x['installs'] * 100) if x['installs'] > 0 else 0, 
                axis=1
            )
            return df
        except Exception as e:
            print(f"[data] get_conversion_rate_data ERROR: {e}")
            return pd.DataFrame(columns=['date', 'installs', 'total_new_paid_subscriptions', 'conversion_rate'])

    return _get_cached(_cache_key('conversion_rate', {'start': start_date, 'end': end_date}), _query)

def get_cohort_ltv_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_cohort_df(start_date, end_date)
    if df.empty: return pd.DataFrame()
    return _filter_df(df, 'country', 'platform', country, platform, map_country=False)

def get_roas_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_cohort_df(start_date, end_date)
    if df.empty: return pd.DataFrame(columns=['date', 'total_proceeds', 'total_spend', 'roas'])
    
    df_f = _filter_df(df, 'country', 'platform', country, platform, map_country=False)
    
    # Sum proceeds columns
    proceeds_cols = ['proceeds_7d', 'proceeds_30d', 'proceeds_90d', 'proceeds_180d', 'proceeds_365d']
    existing_cols = [c for c in proceeds_cols if c in df_f.columns]
    
    if not existing_cols:
        return pd.DataFrame(columns=['date', 'total_proceeds', 'total_spend', 'roas'])
        
    df_f['total_proceeds_row'] = df_f[existing_cols].sum(axis=1)
    
    res = df_f.groupby('date', as_index=False)[['total_proceeds_row', 'spend']].sum()
    res = res.rename(columns={'total_proceeds_row': 'total_proceeds', 'spend': 'total_spend'})
    
    res['roas'] = res.apply(lambda x: x['total_proceeds'] / x['total_spend'] if x['total_spend'] > 0 else 0, axis=1)
    return res

def get_cac_ltv_thresholds(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df_final = _get_base_final_df(start_date, end_date)
    df_cohort = _get_base_cohort_df(start_date, end_date)
    
    if df_final.empty or df_cohort.empty:
        return pd.DataFrame(columns=['date', 'cac', 'ltv_30d', 'healthy_cac_threshold', 'aggressive_cac_threshold'])
        
    # Filter strictly for current period
    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df_final = df_final[(df_final['date'] >= s_dt) & (df_final['date'] <= e_dt)]
    
    f_final = _filter_df(df_final, 'rc_country', 'rc_platform', country, platform, map_country=True)
    f_cohort = _filter_df(df_cohort, 'country', 'platform', country, platform, map_country=False)
    
    # Calculate daily CAC
    cac_agg = f_final.groupby('date', as_index=False)[['spend', 'total_new_paid_subscriptions']].sum()
    cac_agg['cac'] = cac_agg.apply(lambda x: x['spend'] / x['total_new_paid_subscriptions'] if x['total_new_paid_subscriptions'] > 0 else 0, axis=1)
    
    # Calculate daily LTV 30d (Average)
    if 'realized_ltv_30d' not in f_cohort.columns:
        return pd.DataFrame(columns=['date', 'cac', 'ltv_30d', 'healthy_cac_threshold', 'aggressive_cac_threshold'])
        
    ltv_agg = f_cohort.groupby('date', as_index=False)['realized_ltv_30d'].mean()
    ltv_agg = ltv_agg.rename(columns={'realized_ltv_30d': 'ltv_30d'})
    
    # Merge
    merged = pd.merge(cac_agg[['date', 'cac']], ltv_agg[['date', 'ltv_30d']], on='date', how='inner')
    merged = merged[(merged['cac'] >= 0) & (merged['ltv_30d'] > 0)].copy()
    
    merged['healthy_cac_threshold'] = merged['ltv_30d'] / 3
    merged['aggressive_cac_threshold'] = merged['ltv_30d'] / 2
    
    return merged.sort_values('date')

# ── TRUE ROAS / META ROAS ───────────────────────────────────────────────────────
def get_true_roas_data(start_date, end_date, country=None, platform=None, roas_type='true') -> pd.DataFrame:
    """
    Fetches True ROAS data broken down by Country, Campaign, and Ad.
    
    Data Source: mrt_final_vinita (Adjust data)
    
    Logic applied for True ROAS (as requested by user):
    1. Filter for platform IN ('ios', 'android')
    2. all_revenue is halved due to a known double-counting issue in Adjust data.
    3. Net Proceeds are calculated based on the fee structure:
       - Android: 15% fee (multiplier 0.85)
       - iOS: Variable fee based on toggle (15% or 30%, multiplier 0.85 or 0.70)
    4. ROAS = Net Proceeds / Spend
    """
    def _query():
        client = get_bq_client()
        # Fetching raw data from BigQuery, math is done in Pandas for fast toggle switching
        q = f"""
            SELECT
                country,
                platform,
                campaign_name,
                ad_name,
                SUM(all_revenue) AS total_all_revenue,
                SUM(purchase) AS total_purchase,
                SUM(spend) AS total_spend
            FROM `{TABLE}`
            WHERE CAST(date AS DATE) BETWEEN '{start_date}' AND '{end_date}'
              AND LOWER(platform) IN ('ios', 'android')
            GROUP BY country, platform, campaign_name, ad_name
        """
        try:
            df = client.query(q).to_dataframe()
            for col in ['total_all_revenue', 'total_purchase', 'total_spend']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] get_true_roas_data ERROR: {e}")
            return pd.DataFrame(columns=['country', 'platform', 'campaign_name', 'ad_name', 'total_all_revenue', 'total_purchase', 'total_spend'])

    # Cache the raw query result (doesn't include the math so we can toggle iOS fee instantly)
    df = _get_cached(_cache_key('true_roas', {'start': start_date, 'end': end_date}), _query)

    if df.empty:
        return pd.DataFrame(columns=['country', 'platform', 'campaign_name', 'ad_name', 'net_proceeds', 'spend', 'roas'])

    df_f = df.copy()

    # Restrict to only the 4 target countries (US, Canada, UK, Australia)
    target_countries = ['us', 'gb', 'ca', 'au', 'united states', 'united kingdom', 'canada', 'australia']
    df_f = df_f[df_f['country'].str.lower().isin(target_countries)]

    # Filter by platform
    if platform and platform not in ("", "All"):
        # We lowercase both sides to be safe
        df_f = df_f[df_f['platform'].str.lower() == platform.lower()]

    # Filter by country
    if country and country not in ("", "All", "Total"):
        c_mapped = COUNTRY_MAP.get(country, country)
        # Check against both the exact 2-letter code or the mapped full name, since Adjust format can vary
        df_f = df_f[(df_f['country'].str.upper() == country) | (df_f['country'].str.lower() == country.lower()) | (df_f['country'] == c_mapped)]

    if roas_type == 'meta':
        df_f['net_proceeds'] = df_f['total_purchase']
    else:
        # 1. Halve the all_revenue
        df_f['revenue_adj'] = df_f['total_all_revenue'] / 2.0

        # 2. Apply platform fees
        # Both iOS and Android apply a default 15% fee (multiplier 0.85)
        df_f['net_proceeds'] = df_f['revenue_adj'] * 0.85

    df_f['spend'] = df_f['total_spend']
    
    # 3. Calculate ROAS
    df_f['roas'] = df_f.apply(lambda x: x['net_proceeds'] / x['spend'] if x['spend'] > 0 else 0, axis=1)

    return df_f[['country', 'platform', 'campaign_name', 'ad_name', 'net_proceeds', 'spend', 'roas']]


# ── ARPU Queries (Unchanged as they are very specific to Total) ───────────────
def get_arpu_daily(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    def _query():
        client = get_bq_client()
        
        c_filter = "country = 'Total'"
        if country and country not in ("All", "Total"):
            c_name = COUNTRY_MAP.get(country, country)
            c_filter = f"country = '{c_name}'"
            
        p_filter = ""
        if platform and platform not in ("All", ""):
            p_filter = f" AND platform = '{platform}'"

        q = f"""
            SELECT
                DATE(date)      AS date,
                platform,
                SUM(proceeds)   AS proceeds,
                MAX(total_active_subscriptions) AS active_subs,
                SAFE_DIVIDE(SUM(proceeds), NULLIF(MAX(total_active_subscriptions), 0)) AS arpu
            FROM `{ARPU_TABLE}`
            WHERE {c_filter}{p_filter}
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
        except:
            return pd.DataFrame(columns=["date", "platform", "proceeds", "active_subs", "arpu"])
    return _get_cached(_cache_key('arpu_daily', {'start': start_date, 'end': end_date, 'c': country, 'p': platform}), _query)


def get_arpu_by_platform(start_date, end_date) -> pd.DataFrame:
    def _query():
        client = get_bq_client()
        q = f"""
            WITH monthly AS (
                SELECT
                    DATE_TRUNC(DATE(date), MONTH) AS month,
                    platform,
                    SUM(proceeds) AS monthly_proceeds,
                    ARRAY_AGG(total_active_subscriptions ORDER BY date DESC LIMIT 1)[OFFSET(0)] AS active_end
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
        except:
            return pd.DataFrame(columns=["platform", "total_proceeds", "avg_arpu"])
    return _get_cached(_cache_key('arpu_by_platform', {'start': start_date, 'end': end_date}), _query)

# ── FACEBOOK ANALYTICS ────────────────────────────────────────────────────────
def get_facebook_kpi_data(start_date, end_date, platform=None) -> dict:
    def _query():
        client = get_bq_client()
        p_filter = ""
        if platform and platform not in ("All", ""):
            p_filter = f" AND LOWER(platform) = '{platform.lower()}'"
        q = f"""
            SELECT
                SUM(spend) AS spend,
                SUM(clicks) AS clicks,
                SUM(impressions) AS impressions,
                SUM(reach) AS reach
            FROM `{TABLE}`
            WHERE CAST(date AS DATE) BETWEEN '{start_date}' AND '{end_date}'
              AND adplatform = 'Facebook'{p_filter}
        """
        try:
            df = client.query(q).to_dataframe()
            for col in ['spend', 'clicks', 'impressions', 'reach']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            print(f"[data] get_facebook_kpi_data ERROR: {e}")
            return pd.DataFrame(columns=['spend', 'clicks', 'impressions', 'reach'])
            
    df = _get_cached(_cache_key('facebook_kpi', {'start': start_date, 'end': end_date, 'p': platform}), _query)
    
    if df.empty or len(df) == 0:
        return {"spend": 0, "ctr": 0, "cpm": 0, "cost_per_reach": 0}
        
    row = df.iloc[0]
    spend = float(row.get('spend', 0))
    clicks = float(row.get('clicks', 0))
    impressions = float(row.get('impressions', 0))
    reach = float(row.get('reach', 0))
    
    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    cpm = (spend / impressions * 1000) if impressions > 0 else 0
    cost_per_reach = (spend / reach) if reach > 0 else 0
    
    return {
        "spend": spend,
        "ctr": ctr,
        "cpm": cpm,
        "cost_per_reach": cost_per_reach
    }

def get_meta_roas_data(start_date, end_date) -> pd.DataFrame:
    def _query():
        client = get_bq_client()
        q = f"""
            SELECT
                CAST(date AS DATE) AS date,
                SUM(purchase) AS total_purchase,
                SUM(spend) AS total_spend
            FROM `{TABLE}`
            WHERE CAST(date AS DATE) BETWEEN '{start_date}' AND '{end_date}'
              AND adplatform = 'Facebook'
            GROUP BY date
            ORDER BY date
        """
        try:
            df = client.query(q).to_dataframe()
            df['date'] = pd.to_datetime(df['date'])
            for col in ['total_purchase', 'total_spend']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df['roas'] = df.apply(
                lambda x: (x['total_purchase'] / x['total_spend']) if x['total_spend'] > 0 else 0, 
                axis=1
            )
            return df
        except Exception as e:
            print(f"[data] get_meta_roas_data ERROR: {e}")
            return pd.DataFrame(columns=['date', 'total_purchase', 'total_spend', 'roas'])

    return _get_cached(_cache_key('meta_roas', {'start': start_date, 'end': end_date}), _query)


# =============================================================================
# ── Break-Even & Payback Period Data ──
# Calculates monthly cumulative net ARPU per user vs the average CAC.
# Used by BOTH the Break-Even Point page and the Payback Period page.
#
# Data source architecture (mrt_final_vinita table):
#   ┌─────────────────────────────────────────────────────────────────┐
#   │ Row type         │ rc_country │ spend>0 │ proceeds>0 │ subs>0  │
#   ├──────────────────┼────────────┼─────────┼────────────┼─────────┤
#   │ Adjust / Ads     │ NULL       │  YES    │    no      │  no     │
#   │ RevenueCat (RC)  │ 'US'/'GB'  │  no     │   YES      │ YES     │
#   └─────────────────────────────────────────────────────────────────┘
#
# Formula:
#   avg_cac           = SUM(spend) [Adjust rows] / SUM(new_paid_subs) [RC rows]
#   monthly_arpu_net  = monthly_proceeds / end_of_month_active_subs  [RC rows, per country]
#   cumulative_arpu   = running cumsum of monthly_arpu_net
#   Break-even month  = first month where cumulative_arpu >= avg_cac
# =============================================================================
def get_breakeven_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_final_df(start_date, end_date)
    if df.empty:
        return pd.DataFrame()

    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]

    # ─────────────────────────────────────────────────────────────────────────
    # The mrt_final_vinita table has two distinct row types:
    #   Adjust/Ads rows → rc_country IS NULL  → spend > 0,  proceeds = 0, subs = 0
    #   RevenueCat rows → rc_country IS SET   → spend = 0,  proceeds > 0, subs > 0
    # We must NOT filter spend by rc_country; split first, then work per-source.
    # ─────────────────────────────────────────────────────────────────────────
    adjust_df = df[df['rc_country'].isna()].copy()   # Ads/Adjust → spend lives here
    rc_df     = df[df['rc_country'].notna()].copy()  # RevenueCat → RC metrics live here

    # Platform filter: only applied to RC rows (rc_platform).
    # Adjust rows have rc_platform=NULL; spend is tracked globally, not per platform.
    if platform and platform not in ('', 'All'):
        rc_df = rc_df[rc_df['rc_platform'] == platform]

    # ── Global CAC ────────────────────────────────────────────────────────────
    # spend     = Adjust (ads) rows — not tagged per rc_country
    # new_subs  = RevenueCat rows  — sum across all countries
    # → CAC is a single global number applied equally to every country series.
    total_spend    = adjust_df['spend'].sum()
    total_new_subs = rc_df['total_new_paid_subscriptions'].sum()
    global_avg_cac = total_spend / total_new_subs if total_new_subs > 0 else 0

    if global_avg_cac <= 0:
        print(f"[data] get_breakeven_data: no CAC "
              f"(spend={total_spend:.2f}, new_subs={total_new_subs:.0f})")
        return pd.DataFrame()

    # ── Country resolution (rc_country may be code 'US' or full 'United States') ──
    code_to_name = COUNTRY_MAP                              # {'US': 'United States', ...}
    name_to_code = {v: k for k, v in COUNTRY_MAP.items()}  # {'United States': 'US', ...}
    all_rc_vals  = rc_df['rc_country'].unique().tolist()

    def _resolve(requested):
        if not requested or requested in ('', 'All', 'Total'):
            return [v for v in all_rc_vals if v in code_to_name or v in name_to_code]
        hits = set()
        if requested in all_rc_vals:
            hits.add(requested)
        mapped = code_to_name.get(requested) or name_to_code.get(requested)
        if mapped and mapped in all_rc_vals:
            hits.add(mapped)
        return list(hits)

    rc_countries = _resolve(country)
    if not rc_countries:
        print(f"[data] get_breakeven_data: no RC rows for country={country!r}")
        return pd.DataFrame()

    # Canonical display label → always use full country name in charts
    rc_df = rc_df[rc_df['rc_country'].isin(rc_countries)].copy()
    rc_df['country_label'] = rc_df['rc_country'].map(
        lambda rc: code_to_name.get(rc, rc)
    )

    # ── Monthly ARPU per country (RC data only) ───────────────────────────────
    results = []
    for ctry_label, ctry_df in rc_df.groupby('country_label'):
        ctry_df = ctry_df.copy()
        if ctry_df.empty:
            continue

        ctry_df['month'] = ctry_df['date'].dt.to_period('M')
        monthly_rows = []
        for m, m_df in ctry_df.groupby('month'):
            m_df_s     = m_df.sort_values('date')
            last_day   = m_df_s['date'].max()
            end_subs   = m_df_s[m_df_s['date'] == last_day]['active_subscriptions'].sum()
            m_proceeds = m_df_s['proceeds'].sum()
            arpu_net   = (m_proceeds / end_subs) if end_subs > 0 else 0
            monthly_rows.append({
                'month':            m,
                'month_label':      str(m),
                'monthly_arpu_net': arpu_net,
            })

        if not monthly_rows:
            continue

        monthly = pd.DataFrame(monthly_rows).sort_values('month')
        monthly['cumulative_arpu_net'] = monthly['monthly_arpu_net'].cumsum()
        monthly['month_num'] = range(1, len(monthly) + 1)
        monthly['country']   = ctry_label
        monthly['avg_cac']   = global_avg_cac   # same global CAC applied to all countries

        results.append(monthly[['country', 'month_label', 'month_num',
                                 'monthly_arpu_net', 'cumulative_arpu_net', 'avg_cac']])

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


# =============================================================================
# ── ROI Data ──
# Returns both a scalar summary dict AND a monthly trend DataFrame.
#
# ROI = ((LTV_horizon - CAC) / CAC) * 100
#   LTV_90d  → 3-month ROI proxy  (realized_ltv_90d  from cohort table)
#   LTV_180d → 6-month ROI proxy
#   LTV_365d → 12-month ROI proxy
#   Full LTV → calculated via ARPU / churn rate  (same formula as get_ltv_net_data)
#
# avg_cac = total_spend / total_new_paid_subscriptions
# =============================================================================
def get_roi_data(start_date, end_date, country=None, platform=None) -> dict:
    df_cohort = _get_base_cohort_df(start_date, end_date)
    df_final  = _get_base_final_df(start_date, end_date)

    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df_final = df_final[(df_final['date'] >= s_dt) & (df_final['date'] <= e_dt)]

    f_final  = _filter_df(df_final,  'rc_country', 'rc_platform', country, platform, map_country=True)
    f_cohort = _filter_df(df_cohort, 'country',    'platform',    country, platform, map_country=False)

    # ── CAC (overall average) ──
    total_spend    = f_final['spend'].sum()
    total_new_subs = f_final['total_new_paid_subscriptions'].sum()
    avg_cac = total_spend / total_new_subs if total_new_subs > 0 else 0

    # ── Horizon LTVs (average per-user from cohort table) ──
    def _mean(col):
        return float(f_cohort[col].mean()) if col in f_cohort.columns and not f_cohort.empty else 0.0

    ltv_90d  = _mean('realized_ltv_90d')
    ltv_180d = _mean('realized_ltv_180d')
    ltv_365d = _mean('realized_ltv_365d')

    # ── Full LTV via ARPU / churn (mirrors get_ltv_net_data logic) ──
    ltv_full = 0.0
    if not f_final.empty:
        f_final_copy = f_final.copy()
        f_final_copy['month'] = f_final_copy['date'].dt.to_period('M')
        monthly_ltvs = []
        for m, m_df in f_final_copy.groupby('month'):
            m_df_s = m_df.sort_values('date')
            end_subs   = m_df_s.iloc[-1]['active_subscriptions']
            tot_churn  = m_df_s['churned_active'].sum()
            m_proceeds = m_df_s['proceeds'].sum()
            churn_rate = (tot_churn / end_subs) if end_subs else 0
            arpu_net   = (m_proceeds / end_subs) if end_subs else 0
            ltv_m      = (arpu_net / churn_rate) if churn_rate > 0 else 0
            monthly_ltvs.append(ltv_m)
        ltv_full = float(pd.Series(monthly_ltvs).mean()) if monthly_ltvs else 0.0

    def _roi(ltv, cac):
        if cac <= 0:
            return 0.0
        return round(((ltv - cac) / cac) * 100, 2)

    # ── Monthly trend: ROI per month ──
    trend_rows = []
    if not f_cohort.empty and not f_final.empty:
        f_cohort_copy = f_cohort.copy()
        f_cohort_copy['month'] = f_cohort_copy['date'].dt.to_period('M')
        f_final_copy  = f_final.copy()
        f_final_copy['month']  = f_final_copy['date'].dt.to_period('M')

        cac_monthly = f_final_copy.groupby('month').apply(
            lambda x: x['spend'].sum() / x['total_new_paid_subscriptions'].sum()
            if x['total_new_paid_subscriptions'].sum() > 0 else 0
        ).rename('cac')

        ltv_monthly = f_cohort_copy.groupby('month').agg(
            ltv_90d  =('realized_ltv_90d',  'mean'),
            ltv_180d =('realized_ltv_180d', 'mean'),
            ltv_365d =('realized_ltv_365d', 'mean'),
        )

        merged = pd.merge(cac_monthly, ltv_monthly, on='month', how='inner')
        for _, row in merged.iterrows():
            cac = row['cac']
            trend_rows.append({
                'month': row.name.to_timestamp(),
                'roi_3m':  _roi(row['ltv_90d'],  cac),
                'roi_6m':  _roi(row['ltv_180d'], cac),
                'roi_12m': _roi(row['ltv_365d'], cac),
            })

    trend_df = pd.DataFrame(trend_rows).sort_values('month') if trend_rows else pd.DataFrame()

    return {
        'avg_cac':  round(avg_cac,  2),
        'ltv_3m':   round(ltv_90d,  2),
        'ltv_6m':   round(ltv_180d, 2),
        'ltv_12m':  round(ltv_365d, 2),
        'ltv_full': round(ltv_full, 2),
        'roi_3m':   _roi(ltv_90d,  avg_cac),
        'roi_6m':   _roi(ltv_180d, avg_cac),
        'roi_12m':  _roi(ltv_365d, avg_cac),
        'roi_full': _roi(ltv_full, avg_cac),
        'trend_df': trend_df,
    }


# =============================================================================
# ── Business Break-Even Data ──
# First month where cumulative net proceeds >= cumulative ad spend.
#
# Returns a monthly DataFrame with:
#   month | monthly_proceeds | monthly_spend | cumulative_proceeds | cumulative_spend | net_position
# =============================================================================
def get_biz_breakeven_data(start_date, end_date, country=None, platform=None) -> pd.DataFrame:
    df = _get_base_final_df(start_date, end_date)
    if df.empty:
        return pd.DataFrame()

    s_dt, e_dt = pd.to_datetime(start_date), pd.to_datetime(end_date)
    df = df[(df['date'] >= s_dt) & (df['date'] <= e_dt)]

    df_f = _filter_df(df, 'rc_country', 'rc_platform', country, platform, map_country=True)
    if df_f.empty:
        return pd.DataFrame()

    df_f = df_f.copy()
    df_f['month'] = df_f['date'].dt.to_period('M')
    monthly = df_f.groupby('month')[['proceeds', 'spend']].sum().reset_index()
    monthly = monthly.rename(columns={'proceeds': 'monthly_proceeds', 'spend': 'monthly_spend'})
    monthly['month'] = monthly['month'].dt.to_timestamp()
    monthly = monthly.sort_values('month')
    monthly['cumulative_proceeds'] = monthly['monthly_proceeds'].cumsum()
    monthly['cumulative_spend']    = monthly['monthly_spend'].cumsum()
    monthly['net_position']        = monthly['cumulative_proceeds'] - monthly['cumulative_spend']
    return monthly
