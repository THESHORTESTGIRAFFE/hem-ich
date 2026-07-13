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
    stats = {
        'total': query('SELECT COUNT(*) as count FROM equipment', one=True)['count'],
        'active': query('SELECT COUNT(*) as count FROM equipment WHERE state = "Active"', one=True)['count'],
        'maintenance': query('SELECT COUNT(*) as count FROM equipment WHERE state = "Under Maintenance"', one=True)['count'],
        'overdue': query('SELECT COUNT(*) as count FROM equipment WHERE next_maintenance < date("now") AND state = "Active"', one=True)['count'],
        'disposed': query('SELECT COUNT(*) as count FROM equipment WHERE state = "Disposed"', one=True)['count'],
        'pending_disposal': query('SELECT COUNT(*) as count FROM equipment WHERE state = "Pending Disposal"', one=True)['count'],
        'open_flags': query('SELECT COUNT(*) as count FROM issue_flags WHERE status = "Open"', one=True)['count']
    }
    return render_template('dashboard.html', stats=stats)

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

@app.route('/equipment/<int:eq_id>')
@login_required
def equipment_detail(eq_id):
    eq = query('SELECT * FROM equipment WHERE id = ?', (eq_id,), one=True)
    if not eq:
        flash('Equipment not found')
        return redirect(url_for('equipment_list'))
    
    maintenance = query('SELECT * FROM maintenance_records WHERE equipment_id = ? ORDER BY created_at DESC', (eq_id,))
    disposal = query('SELECT * FROM disposal_records WHERE equipment_id = ?', (eq_id,), one=True)
    attachments = query('SELECT * FROM attachments WHERE equipment_id = ? ORDER BY created_at DESC', (eq_id,))
    
    return render_template('equipment_detail.html', eq=eq, maintenance=maintenance, disposal=disposal, attachments=attachments)


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

@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_equipment():
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    
    # Placeholder implementation
    if request.method == 'POST':
        flash('Bulk import functionality needs implementation')
        return redirect(url_for('equipment_list'))
        
    return render_template('import_equipment.html')

@app.route('/maintenance')
@login_required
def maintenance_list():
    records = query('''SELECT m.*, e.name as eq_name, e.asset_tag 
                       FROM maintenance_records m 
                       JOIN equipment e ON m.equipment_id = e.id 
                       ORDER BY m.created_at DESC''')
    return render_template('maintenance_list.html', records=records)

@app.route('/maintenance/schedule')
@login_required
def maintenance_schedule():
    equipment = query('SELECT * FROM equipment WHERE next_maintenance IS NOT NULL ORDER BY next_maintenance')
    return render_template('maintenance_schedule.html', equipment=equipment)






@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/disposal')
@login_required
def disposal_list():
    disposals = query('''SELECT d.*, e.name as eq_name, e.asset_tag 
                         FROM disposal_records d 
                         JOIN equipment e ON d.equipment_id = e.id 
                         ORDER BY d.request_date DESC''')
    return render_template('disposal_list.html', disposals=disposals)

@app.route('/analytics')
@login_required
def analytics():
    # Placeholder for analytics logic
    return render_template('analytics.html')

@app.route('/audit')
@login_required
def audit_log():
    logs = query('SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100')
    return render_template('audit_log.html', logs=logs)

@app.route('/department')
@login_required
def department_overview():
    deps = query('SELECT DISTINCT department FROM equipment WHERE department IS NOT NULL')
    return render_template('department_overview.html', departments=deps)

@app.route('/flag', methods=['GET', 'POST'])
@login_required
def flag_issue():
    # Placeholder for flagging issue logic
    return render_template('flag_issue.html')

@app.route('/intern')
@login_required
def intern_dashboard():
    # Placeholder for intern dashboard
    return render_template('intern_dashboard.html')

@app.route('/issue')
@login_required
def issue_list():
    issues = query('SELECT * FROM issue_flags ORDER BY created_at DESC')
    return render_template('issue_list.html', issues=issues)

@app.route('/profile')
@login_required
def profile():
    user = query('SELECT * FROM users WHERE id = ?', (session['user_id'],), one=True)
    return render_template('profile.html', user=user)

@app.route('/users')
@login_required
def user_list():
    if session.get('role') != 'admin':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    users = query('SELECT * FROM users')
    return render_template('user_list.html', users=users)

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
