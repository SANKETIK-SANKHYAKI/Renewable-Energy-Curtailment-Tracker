import pandas as pd
import pdfplumber
import re
import os
import glob

# -----------------------------
# PDF FOLDER
# -----------------------------
pdf_folder = "vre_reports"

pdf_files = glob.glob(f"{pdf_folder}/*.pdf")

all_data = []

print(f"\nTOTAL PDFs FOUND: {len(pdf_files)}")

# -----------------------------
# LOOP THROUGH PDFs
# -----------------------------
for pdf_path in pdf_files:

    print(f"\nProcessing: {pdf_path}")

    report_date = ""
    wind_mw = 0
    wind_mu = 0
    solar_mw = 0
    solar_mu = 0

    try:

        with pdfplumber.open(pdf_path) as pdf:

            # PAGE 1
            page1 = pdf.pages[0].extract_text()

            date_match = re.search(
                r"Report for\s*[:\.]?\s*(\d{1,2}-[A-Za-z]+-\d{2,4})",
                page1
            )

            if date_match:
                report_date = date_match.group(1)

            # LAST PAGE
            last_page = pdf.pages[-1]

            tables = last_page.extract_tables()

            for table in tables:

                for row in table:

                    if not row:
                        continue

                    row_text = " ".join([str(x) for x in row if x])

                    if "Total Curtailment" in row_text:

                        wind_mw = float(row[3])
                        wind_mu = float(row[4])

                        solar_mw = float(row[5])
                        solar_mu = float(row[6])

        total_mu = round(wind_mu + solar_mu, 2)

        all_data.append({
            "report_date": report_date,
            "wind_mw": wind_mw,
            "wind_mu": wind_mu,
            "solar_mw": solar_mw,
            "solar_mu": solar_mu,
            "total_mu": total_mu
        })

        print(f"SUCCESS: {report_date}")

    except Exception as e:

        print(f"ERROR in {pdf_path}")
        print(e)

# -----------------------------
# FINAL DATAFRAME
# -----------------------------
df = pd.DataFrame(all_data)

# SORT BY DATE
df["report_date"] = pd.to_datetime(df["report_date"], format="%d-%b-%y")

df = df.sort_values("report_date")

# SAVE MASTER CSV
df.to_csv("curtailment_master.csv", index=False)

print("\n==========================")
print("MASTER CSV CREATED")
print("==========================")

print(df)

print("\nSaved as:")
print("curtailment_master.csv")