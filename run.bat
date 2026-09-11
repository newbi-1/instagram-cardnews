@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
call .venv\Scripts\activate.bat
streamlit run app.py --server.headless true
