@echo off
cd "C:\Users\Lenovo\Desktop\Renewable-Energy-Curtailment-Tracker"
python updater.py
git add -A
git commit -m "update: daily"
git push
pause
