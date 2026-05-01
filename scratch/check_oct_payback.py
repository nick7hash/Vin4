
import os
import json
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from decimal import Decimal

KEY_PATH = "vinita-key.json"
PROJECT_ID = "vinita-388203"
TABLE = "vinita-388203.dataform.mrt_final_vinita"

def get_bq_client():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return bigquery.Client(credentials=creds, project=PROJECT_ID)

def check_oct_payback():
    client = get_bq_client()
    
    # Query for October 2025 with Country Filter (the 4 core countries)
    q = f"""
        SELECT
            SUM(CASE WHEN rc_country IS NULL THEN spend ELSE 0 END) AS total_spend,
            SUM(CASE WHEN rc_country IN ('US', 'GB', 'CA', 'AU', 'United States', 'United Kingdom', 'Canada', 'Australia') THEN total_new_paid_subscriptions ELSE 0 END) AS total_new_subs,
            SUM(CASE WHEN rc_country IN ('US', 'GB', 'CA', 'AU', 'United States', 'United Kingdom', 'Canada', 'Australia') THEN proceeds ELSE 0 END) AS total_proceeds,
            SUM(CASE WHEN rc_country IN ('US', 'GB', 'CA', 'AU', 'United States', 'United Kingdom', 'Canada', 'Australia') AND DATE(date) = '2025-10-31' THEN active_subscriptions ELSE 0 END) AS active_subs_end
        FROM `{TABLE}`
        WHERE DATE(date) BETWEEN '2025-10-01' AND '2025-10-31'
    """
    
    print("--- October 2025 Data (Filtered for 4 Countries) ---")
    try:
        df = client.query(q).to_dataframe()
        print(df.to_string(index=False))
        
        row = df.iloc[0]
        spend = float(row['total_spend'])
        new_subs = float(row['total_new_subs'])
        proceeds = float(row['total_proceeds'])
        active_subs = float(row['active_subs_end'])
        
        cac = spend / new_subs if new_subs > 0 else 0
        arpu = proceeds / active_subs if active_subs > 0 else 0
        
        print(f"\nCalculated CAC: ${cac:.2f}")
        print(f"Calculated ARPU (Month 1): ${arpu:.2f}")
        
        if arpu > cac:
            print(f"Payback Period: Month 1 (Spend is covered in the first month)")
        else:
            print(f"Payback Period: > 1 Month")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_oct_payback()
