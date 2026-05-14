import pandas as pd
import json

# -----------------------------
# LOAD CSV
# -----------------------------
df = pd.read_csv("curtailment_master.csv")

# -----------------------------
# FORMAT DATES
# -----------------------------
df["report_date"] = pd.to_datetime(df["report_date"])

df = df.sort_values("report_date")

dates = df["report_date"].dt.strftime("%d-%b").tolist()

solar = df["solar_mu"].tolist()

wind = df["wind_mu"].tolist()

total = df["total_mu"].tolist()

# -----------------------------
# BUILD JS
# -----------------------------
js_code = f"""
const dates = {json.dumps(dates)};
const solar = {json.dumps(solar)};
const wind = {json.dumps(wind)};
const total = {json.dumps(total)};
"""

# -----------------------------
# LOAD HTML
# -----------------------------
with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

# -----------------------------
# REPLACE EXISTING JS ARRAYS
# -----------------------------
import re

html = re.sub(
    r'const dates = .*?;',
    f'const dates = {json.dumps(dates)};',
    html
)

html = re.sub(
    r'const solar = .*?;',
    f'const solar = {json.dumps(solar)};',
    html
)

html = re.sub(
    r'const wind  = .*?;',
    f'const wind  = {json.dumps(wind)};',
    html
)

# -----------------------------
# SAVE UPDATED HTML
# -----------------------------
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("\nDashboard Updated Successfully")