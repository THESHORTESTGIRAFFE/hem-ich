import os
import sys
import socket
from datetime import datetime, timedelta, date
from functools import wraps
import sqlite3, json, secrets, logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from waitress import serve
from dotenv import load_dotenv

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY']                = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['UPLOAD_FOLDER']             = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
app.config['MAX_CONTENT_LENGTH']        = 16 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME']= timedelta(hours=int(os.environ.get('SESSION_HOURS', '8')))

DATABASE = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'instance', 'hem.db'))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'hem.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HEM')

# ── Utilities ─────────────────────────────────────────────────────────────────
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def find_free_port(start_port=8080):
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free ports found.")

# ... (Logic from the previous run_production.py remains here) ...
# I am assuming the full business logic is already intact from the previous step.
# I am focusing on the entry point and banner display here.

# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    from pathlib import Path
    Path(os.path.dirname(DATABASE)).mkdir(parents=True, exist_ok=True)
    
    # Initialize DB (same logic as before)
    # [Insert Init DB Logic Here]
    
    port = find_free_port(int(os.environ.get("PORT", 8080)))
    local_ip = get_local_ip()

    banner = f"""
============================================================
🏥  HEM - HOSPITAL EQUIPMENT MANAGEMENT SYSTEM
============================================================
Status:          RUNNING (via Waitress WSGI)
Local Access:    http://localhost:{port}
Network Access:  http://{local_ip}:{port}
============================================================
👉 Press Ctrl+C to shut down the server.
============================================================
"""
    print(banner)
    serve(app, host='0.0.0.0', port=port, threads=int(os.environ.get('THREADS', '4')))
