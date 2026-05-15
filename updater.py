"""
RE Curtailment Tracker — updater.py v3
========================================
Usage:
  1. vre_reports/ folder mein naya PDF daalo  (filename: DD.MM.YYYY_*.pdf)
  2. python updater.py
  3. git add -A && git commit -m "update" && git push

GitHub Pages will auto-serve index.html as your public dashboard.
"""

import os, re, csv, json, sys
from pathlib import Path
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    print("ERROR: pip install pdfplumber")
    sys.exit(1)

PDF_FOLDER = "vre_reports"
CSV_FILE   = "curtailment_history.csv"
HTML_FILE  = "index.html"

CSV_FIELDS = [
    "date",
    "solar_hrs_demand_mw", "non_solar_hrs_demand_mw",
    "wind_contribution_mw", "wind_contribution_pct",
    "solar_contribution_mw", "solar_contribution_pct",
    "vre_total_mw", "vre_total_pct",
    "max_wind_gen_mw", "max_solar_gen_mw", "max_vre_gen_mw",
    "max_wind_penetration_pct", "max_solar_penetration_pct", "max_vre_penetration_pct",
    "wind_curtail_mw", "wind_curtail_mu",
    "solar_curtail_mw", "solar_curtail_mu",
    "total_curtail_mu",
    "tras_wind_mw", "tras_wind_mu", "tras_solar_mw", "tras_solar_mu",
    "curtail_reasons",
]

# ─── manual overrides ───────────────────────────────────────────────────────
# Use this for any PDF whose Page 1 regex fails to parse correctly.
# Key   = ISO date string  "YYYY-MM-DD"
# Value = dict of any CSV_FIELDS you want to force-set for that date.
# These are applied AFTER PDF extraction, so they always win.
# Add new entries here whenever a PDF produces wrong/zero values.
#
# How to find the correct values:
#   Open the PDF, look at Page 1 "Solar Hours" row:
#     demand_mw | time | wind_mw | wind% | solar_mw | solar% | vre_mw | vre%
#
MANUAL_OVERRIDES = {
    "2026-05-04": {
        "vre_total_pct":        28.11,   # from Page 1 Solar hrs row → VRE %
        "solar_hrs_demand_mw":  221648,  # from Page 1 Solar hrs row → Demand MW
        # add more fields below if also wrong, e.g.:
        # "wind_contribution_pct":  3.25,
        # "solar_contribution_pct": 22.68,
        # "vre_total_mw":           62345,
        # "solar_curtail_mu":       34.97,
        # "wind_curtail_mu":        3.59,
        # "total_curtail_mu":       38.56,
    },
    # "2026-05-XX": { "vre_total_pct": 0.0, ... },  # template for future fixes
}

# ─── helpers ────────────────────────────────────────────────────────────────

def date_from_filename(fname):
    """Parse DD.MM.YYYY or DDMMYYYY from filename."""
    m = re.search(r'(\d{2})[._-](\d{2})[._-](\d{4})', Path(fname).name)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None

def friendly(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%b-%y")
    except:
        return iso

def safe_int(val):
    try:
        return int(float(str(val).strip()))
    except:
        return 0

def safe_float(val):
    try:
        return round(float(str(val).strip()), 2)
    except:
        return 0.0

# ─── page 1 extraction ──────────────────────────────────────────────────────

def extract_page1(page):
    text = page.extract_text() or ""
    d = {
        "solar_hrs_demand_mw": 0, "non_solar_hrs_demand_mw": 0,
        "wind_contribution_mw": 0, "wind_contribution_pct": 0.0,
        "solar_contribution_mw": 0, "solar_contribution_pct": 0.0,
        "vre_total_mw": 0, "vre_total_pct": 0.0,
        "max_wind_gen_mw": 0, "max_solar_gen_mw": 0, "max_vre_gen_mw": 0,
        "max_wind_penetration_pct": 0.0, "max_solar_penetration_pct": 0.0,
        "max_vre_penetration_pct": 0.0,
    }

    # Solar hrs row: 247881 15:37 8067 3.25% 56209 22.68% 64277 25.93%
    solar_row = re.search(
        r'Solar hrs.*?(\d{5,6})\s+\d{1,2}:\d{2}\s+'   # demand MW
        r'(\d{3,6})\s+([\d.]+)%\s+'                    # wind MW, wind%
        r'(\d{3,6})\s+([\d.]+)%\s+'                    # solar MW, solar%
        r'(\d{3,6})\s+([\d.]+)%',                      # VRE MW, VRE%
        text
    )
    if solar_row:
        d["solar_hrs_demand_mw"]    = int(solar_row.group(1))
        d["wind_contribution_mw"]   = int(solar_row.group(2))
        d["wind_contribution_pct"]  = float(solar_row.group(3))
        d["solar_contribution_mw"]  = int(solar_row.group(4))
        d["solar_contribution_pct"] = float(solar_row.group(5))
        d["vre_total_mw"]           = int(solar_row.group(6))
        d["vre_total_pct"]          = float(solar_row.group(7))

    non_solar = re.search(r'Non Solar hrs\s+(\d{5,6})', text)
    if non_solar:
        d["non_solar_hrs_demand_mw"] = int(non_solar.group(1))

    # Max gen row: 11497 0:23 81220 12:09 85930 12:40 5.06% 0:35 34.96% 12:07 36.94% 12:09
    max_gen = re.search(
        r'(\d{4,6})\s+\d{1,2}:\d{2}\s+'               # max wind MW
        r'(\d{4,6})\s+\d{1,2}:\d{2}\s+'               # max solar MW
        r'(\d{4,6})\s+\d{1,2}:\d{2}\s+'               # max VRE MW
        r'([\d.]+)%\s+\d{1,2}:\d{2}\s+'               # max wind %
        r'([\d.]+)%\s+\d{1,2}:\d{2}\s+'               # max solar %
        r'([\d.]+)%',                                   # max VRE %
        text
    )
    if max_gen:
        d["max_wind_gen_mw"]           = int(max_gen.group(1))
        d["max_solar_gen_mw"]          = int(max_gen.group(2))
        d["max_vre_gen_mw"]            = int(max_gen.group(3))
        d["max_wind_penetration_pct"]  = float(max_gen.group(4))
        d["max_solar_penetration_pct"] = float(max_gen.group(5))
        d["max_vre_penetration_pct"]   = float(max_gen.group(6))

    return d

# ─── page 4 (last page) extraction ─────────────────────────────────────────
#
# CONFIRMED COLUMN LAYOUT (from pdfplumber diagnostic on real PDF):
#
# Section 8 table (one big table on last page):
#   row[0] = Region (NR/WR/SR or "Total Curtailment")
#   row[1] = Sub-type (RE State / ISTS RE Station)
#   row[2] = Station / State name
#   row[3] = Wind Max MW
#   row[4] = Wind MUs
#   row[5] = Solar Max MW
#   row[6] = Solar MUs
#   row[7] = Reason for Curtailment
#
# "Total Curtailment" row: row[0]="Total Curtailment", cols 3-6 = totals
#
# Section 9 (continues in same table after sec-9 header row):
#   row[0] = Region (NR ISTS / WR ISTS / SR ISTS)
#   row[1] = Pooling station name
#   row[2] = TRAS Wind Max MW
#   row[3] = TRAS Wind MUs
#   row[4] = TRAS Solar Max MW
#   row[5] = TRAS Solar MUs
#   row[6] = Reason
#   "SUM" row: row[1]="SUM", cols 2-5 = totals

def extract_last_page(page):
    d = {
        "wind_curtail_mw": 0, "wind_curtail_mu": 0.0,
        "solar_curtail_mw": 0, "solar_curtail_mu": 0.0,
        "total_curtail_mu": 0.0,
        "tras_wind_mw": 0, "tras_wind_mu": 0.0,
        "tras_solar_mw": 0, "tras_solar_mu": 0.0,
        "curtail_reasons": [],
    }

    tables = page.extract_tables()
    if not tables:
        return d

    # There is ONE big table on page 4 containing both Section 8 & 9
    table = tables[0]

    in_sec9 = False  # flag: have we crossed the Section 9 header?

    for row in table:
        if not row:
            continue
        rc = [str(c).strip() if c else "" for c in row]

        # ── Detect Section 9 header ──────────────────────────────────────
        if rc[0] and "Emergency TRAS" in rc[0]:
            in_sec9 = True
            continue

        # ── Section 8 — Total Curtailment row ────────────────────────────
        if not in_sec9 and rc[0] and "Total Curtailment" in rc[0]:
            d["wind_curtail_mw"]  = safe_int(rc[3])
            d["wind_curtail_mu"]  = safe_float(rc[4])
            d["solar_curtail_mw"] = safe_int(rc[5])
            d["solar_curtail_mu"] = safe_float(rc[6])
            d["total_curtail_mu"] = round(d["wind_curtail_mu"] + d["solar_curtail_mu"], 2)
            continue

        # ── Section 8 — station rows with actual curtailment ─────────────
        if not in_sec9 and len(rc) >= 8:
            reason = rc[7].strip()
            # skip header rows and rows with no real data
            skip_phrases = {"--", "-", "", "No Curtailment", "Reason For Curtailnment",
                            "MUs", "ब धित ऊर् ि क क रण"}
            if reason in skip_phrases:
                continue
            try:
                w_mw = safe_float(rc[3])
                s_mw = safe_float(rc[5])
                if w_mw > 0 or s_mw > 0:
                    station = rc[2] if rc[2] else (rc[1] if rc[1] else rc[0])
                    entry = {
                        "station":   station[:80],
                        "reason":    reason[:120],
                        "wind_mw":   w_mw,
                        "solar_mw":  s_mw,
                        "wind_mu":   safe_float(rc[4]),
                        "solar_mu":  safe_float(rc[6]),
                    }
                    # avoid exact duplicates
                    if entry not in d["curtail_reasons"]:
                        d["curtail_reasons"].append(entry)
            except:
                pass

        # ── Section 9 — SUM row ──────────────────────────────────────────
        if in_sec9 and len(rc) >= 6 and rc[1] == "SUM":
            d["tras_wind_mw"]  = safe_int(rc[2])
            d["tras_wind_mu"]  = safe_float(rc[3])
            d["tras_solar_mw"] = safe_int(rc[4])
            d["tras_solar_mu"] = safe_float(rc[5])

    return d

# ─── process all PDFs ───────────────────────────────────────────────────────

def process_all_pdfs():
    pdfs = sorted(Path(PDF_FOLDER).glob("*.pdf"))
    if not pdfs:
        print(f"ERROR: '{PDF_FOLDER}/' mein koi PDF nahi!")
        sys.exit(1)

    print(f"\n  {len(pdfs)} PDF(s) mile\n")
    all_data = []

    for pdf_path in pdfs:
        iso_date = date_from_filename(pdf_path.name)
        if not iso_date:
            print(f"  SKIP (date parse failed): {pdf_path.name}")
            continue

        print(f"  Processing: {pdf_path.name}")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                p1   = extract_page1(pdf.pages[0])
                last = extract_last_page(pdf.pages[-1])

            row = {"date": iso_date}
            row.update(p1)
            row.update(last)
            all_data.append(row)

            print(f"    Wind curtail : {last['wind_curtail_mw']} MW | {last['wind_curtail_mu']} MU")
            print(f"    Solar curtail: {last['solar_curtail_mw']} MW | {last['solar_curtail_mu']} MU")
            print(f"    Total curtail: {last['total_curtail_mu']} MU")
            print(f"    TRAS         : Wind {last['tras_wind_mu']} MU | Solar {last['tras_solar_mu']} MU")
            print(f"    VRE          : {p1['vre_total_pct']}% | Demand: {p1['solar_hrs_demand_mw']:,} MW\n")

        except Exception as e:
            print(f"    ERROR processing {pdf_path.name}: {e}\n")

    # sort by date ascending
    all_data.sort(key=lambda x: x["date"])
    return all_data

# ─── write CSV ──────────────────────────────────────────────────────────────

def write_csv(all_data):
    print(f"[2/3] Writing {CSV_FILE}...")
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for d in all_data:
            row = dict(d)
            reasons = d.get("curtail_reasons", [])
            row["curtail_reasons"] = " | ".join(
                f"{r['station']}: {r['reason'][:60]}" for r in reasons
            ) if reasons else "No curtailment"
            writer.writerow(row)
    print(f"    Saved — {len(all_data)} records")

# ─── generate HTML ──────────────────────────────────────────────────────────

def generate_html(all_data):
    print(f"[3/3] Generating {HTML_FILE}...")
    if not all_data:
        return

    latest = all_data[-1]
    rows   = all_data
    n      = len(rows)

    # ── JS arrays for charts ──
    dates_js     = json.dumps([friendly(d["date"]) for d in rows])
    wind_mu_js   = json.dumps([d["wind_curtail_mu"]  for d in rows])
    solar_mu_js  = json.dumps([d["solar_curtail_mu"] for d in rows])
    total_mu_js  = json.dumps([d["total_curtail_mu"] for d in rows])
    vre_pct_js   = json.dumps([d["vre_total_pct"]    for d in rows])

    # ── latest-day values ──
    date_str     = friendly(latest["date"])
    wind_mu      = latest["wind_curtail_mu"]
    solar_mu     = latest["solar_curtail_mu"]
    wind_mw      = latest["wind_curtail_mw"]
    solar_mw     = latest["solar_curtail_mw"]
    total_mu     = latest["total_curtail_mu"]
    tras_w_mu    = latest["tras_wind_mu"]
    tras_s_mu    = latest["tras_solar_mu"]
    tras_w_mw    = latest["tras_wind_mw"]
    tras_s_mw    = latest["tras_solar_mw"]
    tras_total   = round(tras_w_mu + tras_s_mu, 2)
    vre_pct      = latest["vre_total_pct"]
    wind_pct_d   = latest["wind_contribution_pct"]
    solar_pct_d  = latest["solar_contribution_pct"]
    wind_con_mw  = latest["wind_contribution_mw"]
    solar_con_mw = latest["solar_contribution_mw"]
    vre_tot_mw   = latest["vre_total_mw"]
    max_wind     = latest["max_wind_gen_mw"]
    max_solar    = latest["max_solar_gen_mw"]
    max_vre      = latest["max_vre_gen_mw"]
    max_wp       = latest["max_wind_penetration_pct"]
    max_sp       = latest["max_solar_penetration_pct"]
    max_vrep     = latest["max_vre_penetration_pct"]
    demand_mw    = latest["solar_hrs_demand_mw"]
    demand_gw    = round(demand_mw / 1000, 1) if demand_mw > 1000 else demand_mw

    solar_share  = round(solar_mu / total_mu * 100) if total_mu > 0 else 0
    wind_share   = 100 - solar_share

    # ── summary stats ──
    total_lost   = round(sum(d["total_curtail_mu"] for d in rows), 2)
    avg_curtail  = round(total_lost / n, 2)
    max_day_val  = max(d["total_curtail_mu"] for d in rows)
    max_day_d    = friendly([d for d in rows if d["total_curtail_mu"] == max_day_val][0]["date"])
    date_from    = friendly(rows[0]["date"])
    date_to      = friendly(rows[-1]["date"])

    # ── reason cards ──
    reasons_list = latest.get("curtail_reasons", [])
    reason_cards = ""
    if reasons_list:
        for r in reasons_list[:6]:
            ww = f'<span class="rv wind">💨 {r["wind_mw"]} MW wind</span>'  if r["wind_mw"]  > 0 else ""
            ss = f'<span class="rv solar">☀️ {r["solar_mw"]} MW solar</span>' if r["solar_mw"] > 0 else ""
            reason_cards += f"""
        <div class="reason-card">
          <div class="rc-station">{r['station']}</div>
          <div class="rc-reason">{r['reason']}</div>
          <div class="rc-vals">{ww}{ss}</div>
        </div>"""
    else:
        reason_cards = '<div class="reason-card"><div class="rc-reason">✅ No curtailment reported today</div></div>'

    # ── daily table rows (last 15 days) ──
    table_rows = ""
    for d in reversed(rows[-15:]):
        tc = d["total_curtail_mu"]
        cls = "row-high" if tc > 5 else ("row-med" if tc > 1 else "row-low")
        table_rows += f"""
        <tr class="{cls}">
          <td>{friendly(d['date'])}</td>
          <td>{d['solar_hrs_demand_mw']:,}</td>
          <td>{d['vre_total_pct']:.2f}%</td>
          <td>{d['wind_curtail_mu']:.2f}</td>
          <td>{d['solar_curtail_mu']:.2f}</td>
          <td><strong>{tc:.2f}</strong></td>
          <td>{d['tras_wind_mu'] + d['tras_solar_mu']:.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>India RE Curtailment Tracker</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root{{
      --navy:#0f2744; --blue:#2563eb; --solar:#f59e0b; --wind:#10b981;
      --purple:#8b5cf6; --red:#ef4444; --bg:#f8fafc; --card:#fff;
      --border:#e2e8f0; --text:#0f172a; --t2:#64748b; --t3:#94a3b8;
    }}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text)}}

    /* ── Header ── */
    .header{{background:var(--navy);padding:0 32px;display:flex;align-items:center;
      justify-content:space-between;height:60px;border-bottom:1px solid rgba(255,255,255,.07)}}
    .hl{{display:flex;align-items:center;gap:12px}}
    .logo{{width:36px;height:36px;border-radius:9px;
      background:linear-gradient(135deg,#f59e0b,#10b981);
      display:flex;align-items:center;justify-content:center;font-size:18px}}
    .h-title{{color:#fff;font-size:16px;font-weight:600}}
    .h-sub{{color:rgba(255,255,255,.4);font-size:11px;margin-top:1px}}
    .live-pill{{display:flex;align-items:center;gap:6px;
      background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);
      color:#34d399;font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px}}
    .live-dot{{width:6px;height:6px;border-radius:50%;background:#34d399;animation:pulse 2s infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
    .date-b{{color:rgba(255,255,255,.45);font-size:12px;font-family:'DM Mono',monospace}}

    /* ── Alert banner ── */
    .alert{{background:linear-gradient(90deg,#fffbeb,#fff7ed);
      border-bottom:1px solid #fde68a;padding:10px 32px;font-size:13px;
      color:#92400e;display:flex;align-items:center;gap:10px}}
    .alert strong{{color:#b45309}}

    /* ── Stats bar ── */
    .stats-bar{{background:var(--navy);display:grid;grid-template-columns:repeat(4,1fr)}}
    .stat-item{{padding:14px 24px;border-right:1px solid rgba(255,255,255,.08)}}
    .stat-item:last-child{{border-right:none}}
    .stat-label{{font-size:10px;color:rgba(255,255,255,.4);text-transform:uppercase;
      letter-spacing:1px;margin-bottom:4px}}
    .stat-val{{font-size:20px;font-weight:700;color:#fff}}
    .stat-sub{{font-size:11px;color:rgba(255,255,255,.3);margin-top:2px}}

    /* ── Page container ── */
    .page{{padding:24px 32px;max-width:1440px;margin:0 auto}}
    .sec-label{{font-size:10px;font-weight:700;color:var(--t3);
      text-transform:uppercase;letter-spacing:1.5px;margin:24px 0 12px}}

    /* ── Metric cards ── */
    .metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}}
    .mcard{{background:var(--card);border:1px solid var(--border);border-radius:16px;
      padding:18px 20px;position:relative;overflow:hidden;
      transition:transform .2s,box-shadow .2s}}
    .mcard:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.08)}}
    .mbar{{position:absolute;top:0;left:0;right:0;height:3px;border-radius:16px 16px 0 0}}
    .micon{{width:34px;height:34px;border-radius:9px;
      display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:10px}}
    .mlbl{{font-size:10px;color:var(--t3);font-weight:500;
      text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
    .mval{{font-size:26px;font-weight:700;letter-spacing:-1px;line-height:1}}
    .munit{{font-size:12px;font-weight:500;color:var(--t3);margin-left:2px}}
    .msub{{font-size:11px;color:var(--t3);margin-top:5px}}

    .m-red  .mbar{{background:linear-gradient(90deg,#ef4444,#f97316)}}
    .m-red  .micon{{background:#fef2f2}} .m-red  .mval{{color:#dc2626}}
    .m-amb  .mbar{{background:linear-gradient(90deg,#f59e0b,#fcd34d)}}
    .m-amb  .micon{{background:#fffbeb}} .m-amb  .mval{{color:#d97706}}
    .m-grn  .mbar{{background:linear-gradient(90deg,#10b981,#34d399)}}
    .m-grn  .micon{{background:#ecfdf5}} .m-grn  .mval{{color:#059669}}
    .m-pur  .mbar{{background:linear-gradient(90deg,#8b5cf6,#a78bfa)}}
    .m-pur  .micon{{background:#f5f3ff}} .m-pur  .mval{{color:#7c3aed}}
    .m-blu  .mbar{{background:linear-gradient(90deg,#2563eb,#60a5fa)}}
    .m-blu  .micon{{background:#eff6ff}} .m-blu  .mval{{color:#1d4ed8}}

    /* ── Charts grid ── */
    .charts-grid{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:14px}}
    .ccard{{background:var(--card);border:1px solid var(--border);
      border-radius:16px;padding:20px 22px}}
    .ctitle{{font-size:13px;font-weight:600;color:var(--text);margin-bottom:2px}}
    .csub{{font-size:11px;color:var(--t3);margin-bottom:14px}}

    /* ── Info cards ── */
    .info-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
    .icard{{background:var(--card);border:1px solid var(--border);
      border-radius:16px;padding:18px 20px}}
    .ititle{{font-size:11px;font-weight:700;color:var(--t3);
      text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;
      padding-bottom:8px;border-bottom:1px solid var(--border)}}
    .irow{{display:flex;justify-content:space-between;align-items:center;
      padding:7px 0;border-bottom:1px solid #f8fafc}}
    .irow:last-child{{border:none}}
    .ik{{font-size:12px;color:var(--t2)}}
    .iv{{font-size:12px;font-weight:600;color:var(--text);font-family:'DM Mono',monospace}}
    .badge{{display:inline-flex;font-size:10px;font-weight:600;
      padding:2px 8px;border-radius:20px}}
    .b-solar{{background:#fffbeb;color:#d97706;border:1px solid #fde68a}}
    .b-wind {{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}}
    .b-blue {{background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe}}

    /* ── Two-col ── */
    .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}

    /* ── Reasons ── */
    .bigcard{{background:var(--card);border:1px solid var(--border);
      border-radius:16px;padding:20px 22px}}
    .bigtitle{{font-size:11px;font-weight:700;color:var(--t3);
      text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px;
      padding-bottom:8px;border-bottom:1px solid var(--border)}}
    .reasons-wrap{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
    .reason-card{{background:#f8fafc;border:1px solid var(--border);
      border-radius:10px;padding:12px 14px}}
    .rc-station{{font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px}}
    .rc-reason{{font-size:12px;color:var(--t2);line-height:1.5;margin-bottom:6px}}
    .rc-vals{{display:flex;gap:8px;flex-wrap:wrap}}
    .rv{{font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px}}
    .rv.wind{{background:#ecfdf5;color:#059669}}
    .rv.solar{{background:#fffbeb;color:#d97706}}

    /* ── History table ── */
    .table-wrap{{overflow-x:auto}}
    table{{width:100%;border-collapse:collapse;font-size:12px}}
    th{{background:#f1f5f9;color:var(--t2);font-weight:600;
      text-align:left;padding:8px 12px;border-bottom:2px solid var(--border);
      font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
    td{{padding:8px 12px;border-bottom:1px solid #f1f5f9;
      font-family:'DM Mono',monospace}}
    tr:hover td{{background:#f8fafc}}
    .row-high td{{border-left:3px solid #ef4444}}
    .row-med  td{{border-left:3px solid #f59e0b}}
    .row-low  td{{border-left:3px solid #10b981}}

    /* ── Footer ── */
    .footer{{background:var(--navy);color:rgba(255,255,255,.4);
      text-align:center;padding:14px 32px;font-size:12px;
      display:flex;align-items:center;justify-content:center;
      gap:16px;flex-wrap:wrap;border-top:1px solid rgba(255,255,255,.07)}}
    .footer a{{color:rgba(255,255,255,.55);text-decoration:none}}
    .footer a:hover{{color:#fff}}

    /* ── Responsive ── */
    @media(max-width:1100px){{
      .metrics{{grid-template-columns:repeat(3,1fr)}}
      .charts-grid,.info-grid,.two-col{{grid-template-columns:1fr}}
      .reasons-wrap{{grid-template-columns:1fr}}
      .stats-bar{{grid-template-columns:repeat(2,1fr)}}
    }}
    @media(max-width:600px){{
      .metrics{{grid-template-columns:repeat(2,1fr)}}
      .stats-bar{{grid-template-columns:1fr}}
      .header{{flex-direction:column;height:auto;padding:12px 16px;gap:8px}}
      .page{{padding:16px}}
    }}
  </style>
</head>
<body>

<!-- ── Header ── -->
<div class="header">
  <div class="hl">
    <div class="logo">🌱</div>
    <div>
      <div class="h-title">India RE Curtailment Tracker</div>
      <div class="h-sub">NLDC-REMC Daily VRE Report · Grid India</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span class="date-b">Latest: {date_str}</span>
    <div class="live-pill"><span class="live-dot"></span>AUTO-UPDATED</div>
  </div>
</div>

<!-- ── Alert banner ── -->
<div class="alert">
  ⚡&nbsp;
  <span>
    <strong>{date_str}:</strong>
    Total curtailment <strong>{total_mu:.2f} MU</strong> —
    Solar {solar_mu:.2f} MU ({solar_share}%) + Wind {wind_mu:.2f} MU ({wind_share}%).
    VRE met <strong>{vre_pct:.2f}%</strong> of demand
    (Solar {solar_pct_d:.2f}% + Wind {wind_pct_d:.2f}%).
  </span>
</div>

<!-- ── Stats bar ── -->
<div class="stats-bar">
  <div class="stat-item">
    <div class="stat-label">Tracking Period</div>
    <div class="stat-val">{n} Days</div>
    <div class="stat-sub">{date_from} → {date_to}</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">Total Energy Lost</div>
    <div class="stat-val">{total_lost} MU</div>
    <div class="stat-sub">Cumulative curtailment</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">Daily Average</div>
    <div class="stat-val">{avg_curtail} MU</div>
    <div class="stat-sub">Per day average</div>
  </div>
  <div class="stat-item">
    <div class="stat-label">Highest Day</div>
    <div class="stat-val">{max_day_val} MU</div>
    <div class="stat-sub">{max_day_d}</div>
  </div>
</div>

<div class="page">

  <!-- ── Today's curtailment metrics ── -->
  <div class="sec-label">Today's Curtailment — {date_str}</div>
  <div class="metrics">
    <div class="mcard m-red"><div class="mbar"></div>
      <div class="micon">⚡</div>
      <div class="mlbl">Total Curtailed</div>
      <div class="mval">{total_mu:.2f}<span class="munit">MU</span></div>
      <div class="msub">Wind + Solar combined</div>
    </div>
    <div class="mcard m-amb"><div class="mbar"></div>
      <div class="micon">☀️</div>
      <div class="mlbl">Solar Curtailed</div>
      <div class="mval">{solar_mu:.2f}<span class="munit">MU</span></div>
      <div class="msub">{solar_mw:,} MW peak · {solar_share}% share</div>
    </div>
    <div class="mcard m-grn"><div class="mbar"></div>
      <div class="micon">💨</div>
      <div class="mlbl">Wind Curtailed</div>
      <div class="mval">{wind_mu:.2f}<span class="munit">MU</span></div>
      <div class="msub">{wind_mw:,} MW peak · {wind_share}% share</div>
    </div>
    <div class="mcard m-pur"><div class="mbar"></div>
      <div class="micon">⚠️</div>
      <div class="mlbl">TRAS Down (Sec 9)</div>
      <div class="mval">{tras_total:.2f}<span class="munit">MU</span></div>
      <div class="msub">Emergency TRAS curtailment</div>
    </div>
    <div class="mcard m-blu"><div class="mbar"></div>
      <div class="micon">🏭</div>
      <div class="mlbl">Peak Demand</div>
      <div class="mval">{demand_gw}<span class="munit">GW</span></div>
      <div class="msub">{demand_mw:,} MW · Solar hours</div>
    </div>
  </div>

  <!-- ── Trend charts ── -->
  <div class="sec-label">Trends — {n} Days</div>
  <div class="charts-grid">
    <div class="ccard">
      <div class="ctitle">Daily Curtailment — Solar + Wind Stacked (MU)</div>
      <div class="csub">Drops to zero = no curtailment that day</div>
      <canvas id="trendChart" height="110"></canvas>
    </div>
    <div class="ccard">
      <div class="ctitle">Today's Solar vs Wind Split</div>
      <div class="csub">Share of {total_mu:.2f} MU curtailed</div>
      <canvas id="splitChart" height="110"></canvas>
    </div>
    <div class="ccard">
      <div class="ctitle">VRE Penetration % Trend</div>
      <div class="csub">Daily renewable share of demand met</div>
      <canvas id="vreChart" height="110"></canvas>
    </div>
  </div>

  <!-- ── VRE generation insights ── -->
  <div class="sec-label">VRE Generation Insights (Page 1 Data)</div>
  <div class="info-grid">
    <div class="icard">
      <div class="ititle">☀️ Solar in Demand Mix</div>
      <div class="irow"><span class="ik">Contribution to Demand</span><span class="iv">{solar_con_mw:,} MW</span></div>
      <div class="irow"><span class="ik">Solar Penetration %</span><span class="iv">{solar_pct_d:.2f}%</span></div>
      <div class="irow"><span class="ik">Max Solar Generation</span><span class="iv">{max_solar:,} MW</span></div>
      <div class="irow"><span class="ik">Max Solar Penetration</span><span class="iv">{max_sp:.2f}%</span></div>
      <div class="irow"><span class="ik">Type</span><span class="iv"><span class="badge b-solar">Ground Mounted</span></span></div>
    </div>
    <div class="icard">
      <div class="ititle">💨 Wind in Demand Mix</div>
      <div class="irow"><span class="ik">Contribution to Demand</span><span class="iv">{wind_con_mw:,} MW</span></div>
      <div class="irow"><span class="ik">Wind Penetration %</span><span class="iv">{wind_pct_d:.2f}%</span></div>
      <div class="irow"><span class="ik">Max Wind Generation</span><span class="iv">{max_wind:,} MW</span></div>
      <div class="irow"><span class="ik">Max Wind Penetration</span><span class="iv">{max_wp:.2f}%</span></div>
      <div class="irow"><span class="ik">Type</span><span class="iv"><span class="badge b-wind">Onshore Wind</span></span></div>
    </div>
    <div class="icard">
      <div class="ititle">⚡ VRE Combined</div>
      <div class="irow"><span class="ik">Total VRE in Demand</span><span class="iv">{vre_tot_mw:,} MW</span></div>
      <div class="irow"><span class="ik">VRE Penetration %</span><span class="iv">{vre_pct:.2f}%</span></div>
      <div class="irow"><span class="ik">Max VRE Generation</span><span class="iv">{max_vre:,} MW</span></div>
      <div class="irow"><span class="ik">Max VRE Penetration</span><span class="iv">{max_vrep:.2f}%</span></div>
      <div class="irow"><span class="ik">Source</span><span class="iv"><span class="badge b-blue">Grid India</span></span></div>
    </div>
  </div>

  <!-- ── Section 8 & 9 detail ── -->
  <div class="sec-label">Section 8 & 9 Detail</div>
  <div class="two-col">
    <div class="icard">
      <div class="ititle">📊 Section 8 — Real Time System Constraints</div>
      <div class="irow"><span class="ik">Wind Curtailed (Max MW)</span><span class="iv">{wind_mw:,} MW</span></div>
      <div class="irow"><span class="ik">Wind Curtailed (MU)</span><span class="iv">{wind_mu:.2f} MU</span></div>
      <div class="irow"><span class="ik">Solar Curtailed (Max MW)</span><span class="iv">{solar_mw:,} MW</span></div>
      <div class="irow"><span class="ik">Solar Curtailed (MU)</span><span class="iv">{solar_mu:.2f} MU</span></div>
      <div class="irow"><span class="ik">Total Curtailed (MU)</span><span class="iv">{total_mu:.2f} MU</span></div>
    </div>
    <div class="icard">
      <div class="ititle">🔴 Section 9 — Emergency TRAS Down</div>
      <div class="irow"><span class="ik">TRAS Wind (Max MW)</span><span class="iv">{tras_w_mw:,} MW</span></div>
      <div class="irow"><span class="ik">TRAS Wind (MU)</span><span class="iv">{tras_w_mu:.2f} MU</span></div>
      <div class="irow"><span class="ik">TRAS Solar (Max MW)</span><span class="iv">{tras_s_mw:,} MW</span></div>
      <div class="irow"><span class="ik">TRAS Solar (MU)</span><span class="iv">{tras_s_mu:.2f} MU</span></div>
      <div class="irow"><span class="ik">TRAS Total (MU)</span><span class="iv">{tras_total:.2f} MU</span></div>
    </div>
  </div>

  <!-- ── Curtailment reasons ── -->
  <div class="sec-label">Curtailment Reasons — Station-wise ({date_str})</div>
  <div class="bigcard">
    <div class="bigtitle">⚠️ Active Reasons (Section 8)</div>
    <div class="reasons-wrap">
      {reason_cards}
    </div>
  </div>

  <!-- ── History table ── -->
  <div class="sec-label">Daily History — Last 15 Days</div>
  <div class="bigcard">
    <div class="bigtitle">📅 Day-by-Day Summary
      <a href="{CSV_FILE}" style="float:right;font-size:11px;color:var(--blue);
        text-decoration:none;font-weight:400">⬇ Download Full CSV</a>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Demand (MW)</th>
            <th>VRE %</th>
            <th>Wind Curtail (MU)</th>
            <th>Solar Curtail (MU)</th>
            <th>Total (MU)</th>
            <th>TRAS (MU)</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>
    <div style="font-size:11px;color:var(--t3);margin-top:10px">
      🟥 &gt;5 MU high &nbsp;|&nbsp; 🟧 1–5 MU medium &nbsp;|&nbsp; 🟩 &lt;1 MU low
    </div>
  </div>

</div>

<!-- ── Footer ── -->
<div class="footer">
  <span>🌱 <strong style="color:rgba(255,255,255,.7)">India RE Curtailment Tracker</strong> by Sanket</span>
  <span style="opacity:.3">|</span>
  <span>Data: <a href="https://grid-india.in/en/reports/daily-vre-report" target="_blank">Grid India NLDC-REMC</a></span>
  <span style="opacity:.3">|</span>
  <a href="{CSV_FILE}">⬇ Download CSV</a>
  <span style="opacity:.3">|</span>
  <span style="opacity:.5">Add PDF → python updater.py → git push</span>
</div>

<script>
const dates   = {dates_js};
const windMu  = {wind_mu_js};
const solarMu = {solar_mu_js};
const vrePct  = {vre_pct_js};
const gc = 'rgba(0,0,0,0.05)';
const f  = {{family:'DM Sans',size:12}};
const m  = {{family:'DM Mono',size:11}};

// ── Stacked bar: curtailment trend ──
new Chart(document.getElementById('trendChart'), {{
  type: 'bar',
  data: {{
    labels: dates,
    datasets: [
      {{label:'Solar MU', data:solarMu, backgroundColor:'#f59e0b', borderRadius:3, stack:'a'}},
      {{label:'Wind MU',  data:windMu,  backgroundColor:'#10b981', borderRadius:3, stack:'a'}}
    ]
  }},
  options: {{
    responsive:true,
    plugins:{{ legend:{{ position:'top', labels:{{ font:f, boxWidth:12 }} }} }},
    scales:{{
      x:{{ stacked:true, grid:{{color:gc}}, ticks:{{font:m, maxRotation:45}} }},
      y:{{ stacked:true, beginAtZero:true, grid:{{color:gc}}, ticks:{{font:m}},
           title:{{display:true, text:'MU', font:f, color:'#94a3b8'}} }}
    }}
  }}
}});

// ── Doughnut: solar vs wind split ──
new Chart(document.getElementById('splitChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['Solar ({solar_mu:.2f} MU)', 'Wind ({wind_mu:.2f} MU)'],
    datasets: [{{
      data: [{solar_mu}, {wind_mu}],
      backgroundColor: ['#f59e0b', '#10b981'],
      borderWidth: 3, borderColor: '#fff', hoverOffset: 6
    }}]
  }},
  options: {{
    responsive:true, cutout:'62%',
    plugins:{{ legend:{{ position:'bottom', labels:{{font:f, boxWidth:12}} }} }}
  }}
}});

// ── Line: VRE penetration ──
new Chart(document.getElementById('vreChart'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [{{
      label:'VRE %', data:vrePct,
      borderColor:'#8b5cf6', backgroundColor:'rgba(139,92,246,0.1)',
      fill:true, tension:0.4,
      pointBackgroundColor:'#8b5cf6', pointRadius:4, borderWidth:2.5
    }}]
  }},
  options: {{
    responsive:true,
    plugins:{{ legend:{{display:false}} }},
    scales:{{
      x:{{ grid:{{color:gc}}, ticks:{{font:m, maxRotation:45}} }},
      y:{{ beginAtZero:false, grid:{{color:gc}},
           ticks:{{font:m, callback:v=>v+'%'}},
           title:{{display:true, text:'VRE %', font:f, color:'#94a3b8'}} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"    HTML saved — {HTML_FILE}")

# ─── main ───────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*54)
    print("  India RE Curtailment Tracker — Updater v3")
    print("="*54)
    print("\n[1/3] PDFs process ho rahe hain...")
    all_data = process_all_pdfs()
    if not all_data:
        sys.exit(1)

    # ── apply manual overrides ──────────────────────────────────────────────
    if MANUAL_OVERRIDES:
        for row in all_data:
            if row["date"] in MANUAL_OVERRIDES:
                fixes = MANUAL_OVERRIDES[row["date"]]
                row.update(fixes)
                print(f"  [OVERRIDE] {row['date']} → {list(fixes.keys())}")
    # ───────────────────────────────────────────────────────────────────────

    write_csv(all_data)
    generate_html(all_data)
    latest = all_data[-1]
    print(f"\n{'='*54}")
    print(f"  Done · {len(all_data)} records")
    print(f"  Wind  : {latest['wind_curtail_mw']} MW / {latest['wind_curtail_mu']} MU")
    print(f"  Solar : {latest['solar_curtail_mw']} MW / {latest['solar_curtail_mu']} MU")
    print(f"  Total : {latest['total_curtail_mu']} MU")
    print(f"  VRE   : {latest['vre_total_pct']}%")
    print(f"\n  Ab push karo: git add -A && git commit -m 'update' && git push")
    print("="*54 + "\n")

if __name__ == "__main__":
    main()