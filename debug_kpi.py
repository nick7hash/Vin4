import sys
import os

# Add current dir to path to import data
sys.path.append(os.path.dirname(__file__))

from data import load_kpi_data, get_default_dates

start, end = get_default_dates()
print(f"Default dates: {start} to {end}")

res = load_kpi_data(start, end)
print(f"KPI data result: {res}")
