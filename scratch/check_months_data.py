
import os
import json
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

KEY_PATH = "vinita-key.json"
PROJECT_ID = "vinita-388203"
TABLE = "vinita-388203.dataform.mrt_final_vinita"

def get_bq_client():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(credentials=creds, project=PROJECT_ID)

def check_months_data():
    client = get_bq_client()
    
    # Query for Sep, Oct, Nov 2025
    # Filtered for the 4 core countries to match user expectations
    q = f"""
        SELECT
            FORMAT_DATE('%Y-%m', date) AS month,
            SUM(CASE WHEN rc_country IS NULL THEN spend ELSE 0 END) AS total_spend,
            SUM(CASE WHEN rc_country IN ('US', 'GB', 'CA', 'AU', 'United States', 'United Kingdom', 'Canada', 'Australia') THEN total_new_paid_subscriptions ELSE 0 END) AS total_new_subs,
            SUM(CASE WHEN rc_country IN ('US', 'GB', 'CA', 'AU', 'United States', 'United Kingdom', 'Canada', 'Australia') THEN proceeds ELSE 0 END) AS total_proceeds,
            -- For active subs, we take the last day of the month
            SUM(CASE WHEN rc_country IN ('US', 'GB', 'CA', 'AU', 'United States', 'United Kingdom', 'Canada', 'Australia') AND date = LAST_DAY(date) THEN active_subscriptions ELSE 0 END) AS active_subs_end
        FROM `{TABLE}`
        WHERE DATE(date) BETWEEN '2025-09-01' AND '2025-11-30'
        GROUP BY 1
        ORDER BY 1
    """
    
    print("--- Monthly Raw Data (Sep-Nov 2025) ---")
    try:
        df = client.query(q).to_dataframe()
        df['total_spend'] = df['total_spend'].astype(float)
        df['total_new_subs'] = df['total_new_subs'].astype(float)
        df['total_proceeds'] = df['total_proceeds'].astype(float)
        df['active_subs_end'] = df['active_subs_end'].astype(float)
        
        df['cac'] = df['total_spend'] / df['total_new_subs']
        df['arpu_net'] = df['total_proceeds'] / df['active_subs_end']
        df['net_biz_position'] = df['total_proceeds'] - df['total_spend']
        
        print(df.to_string(index=False))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_months_data()
