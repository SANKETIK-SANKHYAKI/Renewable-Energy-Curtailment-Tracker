"""
auto_push.py — RE Curtailment Tracker Auto Publisher
=====================================================
Run by Windows Task Scheduler every 30 minutes.
- Checks if any PDF in vre_reports/ is newer than index.html
- If yes: runs updater.py → git add → git commit → git push
- Logs everything to auto_push.log

Setup: See SETUP_INSTRUCTIONS.txt in this folder.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# ── CONFIG — edit these two lines ───────────────────────────────────────────
PROJECT_DIR = r"C:\Users\Lenovo\Desktop\Renewable-Energy-Curtailment-Tracker"
PYTHON_EXE  = r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\python.exe"
# ────────────────────────────────────────────────────────────────────────────

LOG_FILE = os.path.join(PROJECT_DIR, "auto_push.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def log(msg):
    logging.info(msg)
    print(msg)


def find_new_pdfs(project_dir):
    """Return True if any PDF in vre_reports/ is newer than index.html."""
    pdf_dir    = Path(project_dir) / "vre_reports"
    index_html = Path(project_dir) / "index.html"

    pdfs = list(pdf_dir.glob("*.pdf"))
    if not pdfs:
        log("No PDFs found in vre_reports/ — nothing to do.")
        return False

    # If index.html doesn't exist yet, always run
    if not index_html.exists():
        log("index.html missing — will generate fresh.")
        return True

    index_mtime = index_html.stat().st_mtime
    new_pdfs = [p for p in pdfs if p.stat().st_mtime > index_mtime]

    if new_pdfs:
        log(f"New PDF(s) detected: {[p.name for p in new_pdfs]}")
        return True

    log("No new PDFs since last run — skipping.")
    return False


def run(cmd, cwd):
    """Run a shell command; return (success, output)."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, shell=True
    )
    out = (result.stdout + result.stderr).strip()
    return result.returncode == 0, out


def setup_git_credentials(project_dir):
    """
    Configure git to store credentials permanently so no password prompt.
    This runs once; after the first successful push credentials are cached.
    """
    run('git config credential.helper store', cwd=project_dir)


def main():
    log("=" * 50)
    log("auto_push.py started")

    project_dir = PROJECT_DIR

    if not Path(project_dir).exists():
        log(f"ERROR: PROJECT_DIR not found: {project_dir}")
        log("Edit PROJECT_DIR in auto_push.py to your actual folder path.")
        sys.exit(1)

    # Step 1: Check if there's anything new to process
    if not find_new_pdfs(project_dir):
        log("Done — no action needed.")
        return

    # Step 2: Run updater.py
    log("Running updater.py ...")
    updater = str(Path(project_dir) / "updater.py")
    ok, out = run(f'"{PYTHON_EXE}" "{updater}"', cwd=project_dir)
    log(out)
    if not ok:
        log("ERROR: updater.py failed. Check above output.")
        sys.exit(1)

    # Step 3: Git — configure credential store (safe to run repeatedly)
    setup_git_credentials(project_dir)

    # Step 4: Git add
    log("Git add ...")
    ok, out = run("git add -A", cwd=project_dir)
    log(out or "  (nothing printed)")
    if not ok:
        log("ERROR: git add failed.")
        sys.exit(1)

    # Step 5: Git commit
    today = datetime.now().strftime("%d-%b-%Y %H:%M")
    commit_msg = f"auto-update: curtailment data {today}"
    log(f"Git commit: {commit_msg}")
    ok, out = run(f'git commit -m "{commit_msg}"', cwd=project_dir)
    log(out or "  (nothing to commit)")

    # If nothing to commit, still try push (in case previous push failed)
    # Step 6: Git push
    log("Git push ...")
    ok, out = run("git push", cwd=project_dir)
    log(out)
    if not ok:
        log("ERROR: git push failed. Check credentials (see SETUP_INSTRUCTIONS.txt).")
        sys.exit(1)

    log("✅ SUCCESS — Dashboard updated and pushed to GitHub!")
    log("=" * 50)


if __name__ == "__main__":
    main()
