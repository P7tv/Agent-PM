#!/usr/bin/env python3
"""
Virtual AI Office PM Dashboard Launcher
Unified runner for the Antigravity Multi-Agent Orchestrator & Virtual Office Dashboard.
"""

import sys
import os
import uvicorn
import subprocess
import webbrowser
import time
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    print("\n" + "="*60)
    print("🏢 ANTIGRAVITY VIRTUAL AI OFFICE - PM COMMAND CENTER 🏢")
    print("="*60)
    
    # Check if frontend is built
    dist_dir = os.path.join(ROOT_DIR, "frontend", "dist")
    if not os.path.exists(dist_dir):
        print("📦 Building frontend production bundle...")
        subprocess.run(["npm", "run", "build"], cwd=os.path.join(ROOT_DIR, "frontend"), check=True, shell=os.name == "nt")

    print("\n🚀 Starting FastAPI Orchestrator on http://127.0.0.1:8000 ...")
    print("✨ Features: Office Floor View, Dual Split View, Focus Room, Self-Healing Loop")
    print("Press Ctrl+C to shutdown.\n")

    from app.main import app
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()
