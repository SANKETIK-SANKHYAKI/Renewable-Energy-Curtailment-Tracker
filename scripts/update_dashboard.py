import requests
import pandas as pd
import pdfplumber
import re
import os
import glob
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.makedirs("vre_reports", exist_ok=True)

BASE_URL = "https://grid-india.in/en/reports/daily-vre-report"

headers = {
    "User-Agent": "Mozilla/5.0"
}

print("Fetching GRID-INDIA page...")

html = requests.get(BASE_URL, headers=headers, verify=False).text

pdf_links = re.findall(r'https://grid-india\.in/sites/default/files/inline-files/.*?\.pdf', html)

if len(pdf_links) == 0:
    raise Exception("No PDF links found")

latest_pdf = pdf_links[0]

pdf_name = latest_pdf.split("/")[-1]

pdf_path = f"vre_reports/{pdf_name}"

print(f"Latest PDF found:\n{latest_pdf}")

# -----------------------------
# DOWNLOAD IF NOT EXISTS
# -----------------------------
if not os.path.exists(pdf_path):

    print("Downloading latest PDF...")

    pdf_data = requests.get(latest_pdf, headers=headers, verify=False).content

    with open(pdf_path, "wb") as f:
        f.write(pdf_data)

    print("PDF Downloaded")

else:
    print("PDF already exists")

# -----------------------------
# PROCESS ALL PDFs
# -----------------------------
all_data = []

pdf_files = glob.glob("vre_reports/*.pdf")

print(f"\nTOTAL PDFs FOUND: {len(pdf_files)}")

for pdf_file in pdf_files:

    try:

        report_date = ""
        wind_mw = 0
        wind_mu = 0
        solar_mw = 0
        solar_mu = 0

        with pdfplumber.open(pdf_file) as pdf:
print("\nMASTER CSV UPDATED")