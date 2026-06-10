@echo off
cd /d C:\AIRESBELLA
start http://localhost:8501
streamlit run app.py --server.address 0.0.0.0