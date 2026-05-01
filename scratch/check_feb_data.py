
import os
import json
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

KEY_PATH = "vinita-key.json"
PROJECT_ID = "vinita-388203"
ARPU_TABLE = "vinita-388203.vinita_rc_new.daily_metrics_rc"

def get_bq_client():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(credentials=creds, project=PROJECT_ID)

def check_feb():
    client = get_bq_client()
    
    # Query for February 2026
    q = f"""
        WITH monthly_agg AS (
            SELECT
                platform,
                SUM(proceeds) AS total_proceeds,
                ARRAY_AGG(total_active_subscriptions ORDER BY date DESC LIMIT 1)[OFFSET(0)] AS active_end
            FROM `{ARPU_TABLE}`
            WHERE country = 'Total'
              AND DATE(date) BETWEEN '2026-02-01' AND '2026-02-28'
            GROUP BY platform
        )
        SELECT 
            platform, 
            total_proceeds, 
            active_end,
            SAFE_DIVIDE(total_proceeds, NULLIF(active_end, 0)) AS arpu
        FROM monthly_agg
    """
    
    print("--- February 2026 Data ---")
    try:
        df = client.query(q).to_dataframe()
        print(df.to_string(index=False))
    except Exception as e:
        print(f"Error: {e}")

    # Also check February 2025 just in case
    q2 = q.replace('2026-02', '2025-02')
    print("\n--- February 2025 Data ---")
    try:
        df2 = client.query(q2).to_dataframe()
        print(df2.to_string(index=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_feb()
