#!/bin/bash
# Script to run Streamlit with network access

cd /Users/L037187/Gemini
source myenv/bin/activate
streamlit run main.py --server.address 0.0.0.0 --server.port 8502 --server.headless true --browser.gatherUsageStats false
