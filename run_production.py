from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from functools import wraps
import sqlite3, os, json, secrets, logging
from waitress import serve
from dotenv import load_dotenv
from pathlib import Path

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

# ── Database Utilities ────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db = get_db()
    db.execute(sql, args)
    db.commit()

# ── Authentication ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ── Routes ───────────────────────────────────────────────────────────────────

# ── Template Helpers ─────────────────────────────────────────────────────────
@app.context_processor
def utility_processor():
    def is_overdue(date_str):
        if not date_str: return False
        try:
            due_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            return due_date < date.today()
        except: return False
    
    def state_badge(state):
        return {
            'Active': 'badge-green',
            'Under Maintenance': 'badge-yellow',
            'Pending Disposal': 'badge-red',
            'Disposed': 'badge-gray',
            'In Storage': 'badge-blue'
        }.get(state, 'badge-gray')
        
    def cond_badge(condition):
        return {
            'Good': 'badge-green',
            'Fair': 'badge-yellow',
            'Poor': 'badge-red'
        }.get(condition, 'badge-gray')
        
    return dict(is_overdue=is_overdue, state_badge=state_badge, cond_badge=cond_badge)

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            logger.info(f"User {username} logged in")
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/equipment')
@login_required
def equipment_list():
    q = request.args.get('q', '')
    state = request.args.get('state', '')
    category = request.args.get('category', '')
    
    sql = 'SELECT * FROM equipment WHERE 1=1'
    params = []
    if q:
        sql += ' AND (name LIKE ? OR asset_tag LIKE ? OR serial_number LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])
    if state:
        sql += ' AND state = ?'
        params.append(state)
    if category:
        sql += ' AND category = ?'
        params.append(category)
        
    equipment = query(sql, params)
    categories = [r['category'] for r in query('SELECT DISTINCT category FROM equipment WHERE category IS NOT NULL')]
    
    return render_template('equipment_list.html', equipment=equipment, q=q, state=state, cat=category, categories=categories)

@app.route('/receive', methods=['GET', 'POST'])
@login_required
def receive_equipment():
    if session.get('role') not in ['chief_engineer', 'technician']:
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Simple implementation for now, assuming form fields match DB columns
        data = request.form
        execute('''INSERT INTO equipment (asset_tag, name, model, manufacturer, serial_number, category, department, location, state, condition, purchase_date, purchase_cost, received_by_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (data['asset_tag'], data['name'], data.get('model'), data.get('manufacturer'), data.get('serial_number'),
                 data.get('category'), data.get('department'), data.get('location'), 'Active', data.get('condition', 'Good'),
                 data.get('purchase_date'), data.get('purchase_cost'), session['user_id']))
        flash('Equipment received successfully')
        return redirect(url_for('equipment_list'))
    
    return render_template('receive_equipment.html')



# ── Jinja2 Filters ────────────────────────────────────────────────────────────
@app.template_filter('fmtdate')
def fmtdate(value, format='%Y-%m-%d'):
    if not value: return '—'
    try:
        # Handle string inputs (like '2026-07-09')
        if isinstance(value, str):
            # Simple check if it's already in a recognizable format
            dt = datetime.strptime(value.split(' ')[0], '%Y-%m-%d')
        else:
            dt = value
        return dt.strftime(format)
    except:
        return value

@app.template_filter('fmtdatetime')
def fmtdatetime(value, format='%Y-%m-%d %H:%M'):
    if not value: return '—'
    try:
        if isinstance(value, str):
            dt = datetime.strptime(value.split('.')[0], '%Y-%m-%d %H:%M:%S')
        else:
            dt = value
        return dt.strftime(format)
    except:
        return value

# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    Path(os.path.dirname(DATABASE)).mkdir(parents=True, exist_ok=True)
    
    # Simple check to ensure DB exists, if not, it would require init code, 
    # but the current DB already exists based on our findings.
    
    HOST    = os.environ.get('HOST', '0.0.0.0')
    PORT    = int(os.environ.get('PORT', '8000'))
    THREADS = int(os.environ.get('THREADS', '4'))
    
    print("=" * 60)
    print("  🏥 HEM - HOSPITAL EQUIPMENT MANAGEMENT SYSTEM")
    print("=" * 60)
    serve(app, host=HOST, port=PORT, threads=THREADS)
