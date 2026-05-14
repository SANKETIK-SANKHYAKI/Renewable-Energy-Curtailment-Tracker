import pdfplumber

with pdfplumber.open("vre_reports/12.05.2026_NLDC_REMC_REPORT_144.pdf") as pdf:
    print("=== PAGE 1 TEXT ===")
    print(pdf.pages[0].extract_text())
    
    print("\n=== LAST PAGE TABLES ===")
    tables = pdf.pages[-1].extract_tables()
    for i, t in enumerate(tables):
        print(f"\n-- Table {i} --")
        for row in t:
            if row and any(c for c in row if c and str(c).strip()):
                print(row)