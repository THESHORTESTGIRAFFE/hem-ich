from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
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

# ── Jinja2 Filters ────────────────────────────────────────────────────────────
@app.template_filter('fmtdate')
def fmtdate(value, format='%Y-%m-%d'):
    if not value: return '—'
    try:
        if isinstance(value, str):
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

@app.template_filter('currency')
def currency(value):
    try:
        return f"${float(value):,.2f}"
    except:
        return value

@app.template_filter('dateiso')
def dateiso(value):
    """Normalize a stored date/datetime string to YYYY-MM-DD for <input type=date>."""
    if not value:
        return ''
    try:
        return str(value).split(' ')[0].split('T')[0]
    except:
        return ''

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
    kpis = {'uptime': '99.2%', 'maintenance_compliance': '85%'}
    return render_template('dashboard.html', stats=stats, kpis=kpis)

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

@app.route('/equipment/<int:eq_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_equipment(eq_id):
    if session.get('role') not in ['chief_engineer', 'technician']:
        flash('Unauthorized')
        return redirect(url_for('equipment_detail', eq_id=eq_id))

    eq = query('SELECT * FROM equipment WHERE id = ?', (eq_id,), one=True)
    if not eq:
        flash('Equipment not found')
        return redirect(url_for('equipment_list'))

    if request.method == 'POST':
        data = request.form
        execute('''UPDATE equipment SET
                       name=?, manufacturer=?, model=?, category=?, department=?, location=?,
                       country_of_origin=?, donor_name=?, state=?, condition=?,
                       warranty_expiry=?, next_maintenance=?, notes=?, updated_at=datetime('now')
                   WHERE id=?''',
                (data.get('name'), data.get('manufacturer'), data.get('model'), data.get('category'),
                 data.get('department'), data.get('location'), data.get('country_of_origin'),
                 data.get('donor_name'), data.get('state'), data.get('condition'),
                 data.get('warranty_expiry') or None, data.get('next_maintenance') or None,
                 data.get('notes'), eq_id))
        flash('Equipment updated')
        return redirect(url_for('equipment_detail', eq_id=eq_id))

    return render_template('edit_equipment.html', eq=eq)

@app.route('/equipment/<int:eq_id>/inline-edit', methods=['POST'])
@login_required
def inline_edit_equipment(eq_id):
    if session.get('role') not in ['chief_engineer', 'technician']:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403
    field = request.form.get('field')
    value = request.form.get('value')
    if field not in ('state', 'condition'):
        return jsonify({'ok': False, 'error': 'Invalid field'}), 400
    execute(f"UPDATE equipment SET {field}=?, updated_at=datetime('now') WHERE id=?", (value, eq_id))
    return jsonify({'ok': True})

@app.route('/equipment/<int:eq_id>/export')
@login_required
def export_equipment(eq_id):
    eq = query('SELECT * FROM equipment WHERE id = ?', (eq_id,), one=True)
    if not eq:
        flash('Equipment not found')
        return redirect(url_for('equipment_list'))
    maintenance = query('SELECT * FROM maintenance_records WHERE equipment_id = ? ORDER BY created_at DESC', (eq_id,))
    disposal = query('SELECT * FROM disposal_records WHERE equipment_id = ?', (eq_id,), one=True)
    attachments = query('SELECT * FROM attachments WHERE equipment_id = ? ORDER BY created_at DESC', (eq_id,))
    return render_template('export_equipment.html', eq=eq, maintenance=maintenance, disposal=disposal,
                            attachments=attachments, now=datetime.now())

@app.route('/equipment/<int:eq_id>/qr')
@login_required
def equipment_qr(eq_id):
    eq = query('SELECT * FROM equipment WHERE id = ?', (eq_id,), one=True)
    if not eq:
        flash('Equipment not found')
        return redirect(url_for('equipment_list'))
    return render_template('equipment_qr.html', eq=eq)

@app.route('/disposal/<int:rec_id>/approve', methods=['POST'])
@login_required
def approve_disposal(rec_id):
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    rec = query('SELECT * FROM disposal_records WHERE id = ?', (rec_id,), one=True)
    if not rec:
        flash('Disposal request not found')
        return redirect(url_for('disposal_list'))

    action = request.form.get('action')
    if action == 'approve':
        execute('''UPDATE disposal_records SET status='Approved', approved_by_id=?, approval_date=date('now') WHERE id=?''',
                (session['user_id'], rec_id))
        execute("UPDATE equipment SET state='Pending Disposal', updated_at=datetime('now') WHERE id=?", (rec['equipment_id'],))
        flash('Disposal approved')
    elif action == 'reject':
        execute('''UPDATE disposal_records SET status='Rejected', approved_by_id=?, approval_date=date('now') WHERE id=?''',
                (session['user_id'], rec_id))
        flash('Disposal rejected')

    return redirect(url_for('equipment_detail', eq_id=rec['equipment_id']))

@app.route('/equipment/<int:eq_id>/attachments/upload', methods=['POST'])
@login_required
def upload_attachment(eq_id):
    if session.get('role') not in ['chief_engineer', 'technician']:
        flash('Unauthorized')
        return redirect(url_for('equipment_detail', eq_id=eq_id))

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected')
        return redirect(url_for('equipment_detail', eq_id=eq_id))

    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    original_name = file.filename
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
    safe_name = f"{eq_id}_{secrets.token_hex(8)}_{secure_filename(original_name)}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
    file_size = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))

    execute('''INSERT INTO attachments (equipment_id, uploaded_by_id, filename, original_name, file_type, file_size, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (eq_id, session['user_id'], safe_name, original_name, ext, file_size, request.form.get('description')))
    flash('Attachment uploaded')
    return redirect(url_for('equipment_detail', eq_id=eq_id))

@app.route('/attachments/<int:att_id>/download')
@login_required
def download_attachment(att_id):
    att = query('SELECT * FROM attachments WHERE id = ?', (att_id,), one=True)
    if not att:
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], att['filename'], as_attachment=True,
                                download_name=att['original_name'])

@app.route('/attachments/<int:att_id>/delete', methods=['POST'])
@login_required
def delete_attachment(att_id):
    if session.get('role') not in ['chief_engineer', 'technician']:
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    att = query('SELECT * FROM attachments WHERE id = ?', (att_id,), one=True)
    if not att:
        flash('Attachment not found')
        return redirect(url_for('dashboard'))
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], att['filename']))
    except OSError:
        pass
    eq_id = att['equipment_id']
    execute('DELETE FROM attachments WHERE id = ?', (att_id,))
    flash('Attachment deleted')
    return redirect(url_for('equipment_detail', eq_id=eq_id))

@app.route('/equipment/<int:eq_id>/request-disposal', methods=['GET', 'POST'])
@login_required
def request_disposal(eq_id):
    eq = query('SELECT * FROM equipment WHERE id = ?', (eq_id,), one=True)
    if not eq:
        flash('Equipment not found')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        data = request.form
        execute('''INSERT INTO disposal_records (equipment_id, requested_by_id, reason, method, status)
                   VALUES (?, ?, ?, ?, 'Pending')''',
                (eq_id, session['user_id'], data.get('reason'), data.get('method')))
        flash('Disposal request submitted')
        return redirect(url_for('equipment_detail', eq_id=eq_id))
    
    return render_template('request_disposal.html', eq=eq)



@app.route('/receive', methods=['GET', 'POST'])
@login_required
def receive_equipment():
    if session.get('role') not in ['chief_engineer', 'technician']:
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.form
        if not data.get('name'):
            flash('Equipment name is required')
            return render_template('receive_equipment.html')

        # Asset tags aren't collected on the form — generate the next one for this year.
        year = datetime.now().year
        count = query(
            "SELECT COUNT(*) as count FROM equipment WHERE asset_tag LIKE ?",
            (f'HEM-{year}-%',), one=True
        )['count']
        asset_tag = f"HEM-{year}-{count + 1:04d}"
        # Guard against a rare collision (e.g. a manually-entered tag using the same pattern).
        while query('SELECT id FROM equipment WHERE asset_tag = ?', (asset_tag,), one=True):
            count += 1
            asset_tag = f"HEM-{year}-{count + 1:04d}"

        execute('''INSERT INTO equipment (asset_tag, name, model, manufacturer, serial_number, category,
                       department, location, country_of_origin, donor_name, state, condition,
                       purchase_date, purchase_cost, received_by_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (asset_tag, data['name'], data.get('model'), data.get('manufacturer'), data.get('serial_number'),
                 data.get('category'), data.get('department'), data.get('location'),
                 data.get('country_of_origin'), data.get('donor_name'), 'Active', data.get('condition', 'Good'),
                 data.get('purchase_date') or None, data.get('purchase_cost') or None, session['user_id']))
        eq_id = query('SELECT id FROM equipment WHERE asset_tag = ?', (asset_tag,), one=True)['id']
        flash(f'Equipment received successfully — tagged {asset_tag}')
        return redirect(url_for('equipment_detail', eq_id=eq_id))

    return render_template('receive_equipment.html')

@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_equipment():
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        flash('Bulk import processed')
        return redirect(url_for('equipment_list'))
        
    return render_template('import_equipment.html')

@app.route('/qr-batch')
@login_required
def qr_batch():
    return render_template('qr_batch.html')

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

@app.route('/maintenance/add/<int:eq_id>', methods=['GET', 'POST'])
@login_required
def add_maintenance(eq_id):
    eq = query('SELECT * FROM equipment WHERE id = ?', (eq_id,), one=True)
    if not eq:
        flash('Equipment not found')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        # Simple implementation
        data = request.form
        execute('''INSERT INTO maintenance_records (equipment_id, performed_by_id, maintenance_type, description, findings, outcome, cost, scheduled_date, completed_date, next_due)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (eq_id, session['user_id'], data.get('maintenance_type'), data.get('description'), 
                 data.get('findings'), data.get('outcome'), data.get('cost'), 
                 data.get('scheduled_date'), data.get('completed_date'), data.get('next_due')))
        
        if data.get('update_state'):
            execute('UPDATE equipment SET state = ? WHERE id = ?', (data.get('update_state'), eq_id))
            
        flash('Maintenance record added')
        return redirect(url_for('equipment_detail', eq_id=eq_id))
    
    return render_template('add_maintenance.html', eq=eq, today=date.today().isoformat())



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
    kpis = query('SELECT SUM(purchase_cost) as total_asset_value, COUNT(*) as total_assets, AVG(purchase_cost) as avg_asset_value FROM equipment WHERE state = \"Active\"', one=True)
    total_maint_cost = query('SELECT SUM(cost) as total FROM maintenance_records', one=True)
    by_dept = query('SELECT department, SUM(purchase_cost) as total_value FROM equipment GROUP BY department')
    by_cat = query('SELECT category, SUM(purchase_cost) as total_value FROM equipment GROUP BY category')
    maint_by_month = query('SELECT strftime(\"%Y-%m\", completed_date) as month, SUM(cost) as total_cost FROM maintenance_records GROUP BY month ORDER BY month')
    maint_by_type = query('SELECT maintenance_type, SUM(cost) as total_cost FROM maintenance_records GROUP BY maintenance_type')
    top_equipment = query('SELECT id, name, department, asset_tag, purchase_cost FROM equipment ORDER BY purchase_cost DESC LIMIT 10')
    by_condition = query('SELECT condition, COUNT(*) as count, SUM(purchase_cost) as total_value FROM equipment GROUP BY condition')
    
    return render_template('analytics.html', kpis=kpis, total_maint_cost=total_maint_cost, by_dept=by_dept, by_cat=by_cat, maint_by_month=maint_by_month, maint_by_type=maint_by_type, top_equipment=top_equipment, by_condition=by_condition, cond_badge=lambda x: 'badge-green')


@app.route('/audit')
@login_required
def audit_log():
    page = int(request.args.get('page', 1))
    per_page = 20
    logs = query('SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ? OFFSET ?', (per_page, (page-1)*per_page))
    total_count = query('SELECT COUNT(*) as count FROM audit_log', one=True)['count']
    total_pages = (total_count + per_page - 1) // per_page
    return render_template('audit_log.html', logs=logs, total_pages=total_pages, page=page)

@app.route('/department')
@login_required
def department_overview():
    unassigned = query('SELECT COUNT(*) as count FROM equipment WHERE (department IS NULL OR department = \"\") AND state = \"Active\"', one=True)['count']
    departments = query('''SELECT department, 
                            COUNT(*) as total, 
                            SUM(CASE WHEN state=\"Active\" THEN 1 ELSE 0 END) as active, 
                            SUM(CASE WHEN state=\"Under Maintenance\" THEN 1 ELSE 0 END) as under_maint, 
                            SUM(CASE WHEN next_maintenance < date(\"now\") THEN 1 ELSE 0 END) as overdue,
                            0 as critical_count,
                            SUM(purchase_cost) as total_value
                          FROM equipment WHERE department IS NOT NULL GROUP BY department''')
    return render_template('department_overview.html', departments=departments, unassigned=unassigned)

@app.route('/department/<dept>')
@login_required
def department_detail(dept):
    equipment = query('SELECT * FROM equipment WHERE department = ?', (dept,))
    
    # Calculate stats
    stats_data = query('''SELECT COUNT(*) as total, 
                                 SUM(CASE WHEN state=\"Active\" THEN 1 ELSE 0 END) as active, 
                                 SUM(CASE WHEN next_maintenance < date(\"now\") THEN 1 ELSE 0 END) as overdue, 
                                 SUM(purchase_cost) as value 
                          FROM equipment WHERE department = ?''', (dept,), one=True)
    open_flags_count = query('''SELECT COUNT(*) as count FROM issue_flags i 
                                JOIN equipment e ON i.equipment_id=e.id 
                                WHERE e.department = ? AND i.status=\"Open\"''', (dept,), one=True)['count']
    
    stats = {
        'total': stats_data['total'],
        'active': stats_data['active'],
        'overdue': stats_data['overdue'],
        'value': stats_data['value'] or 0,
        'open_flags': open_flags_count
    }
    
    maint_due = query('SELECT * FROM equipment WHERE department = ? AND next_maintenance IS NOT NULL AND next_maintenance <= date(\"now\", \"+30 days\")', (dept,))
    flags = query('''SELECT i.*, e.name as eq_name FROM issue_flags i 
                     JOIN equipment e ON i.equipment_id=e.id 
                     WHERE e.department = ? AND i.status=\"Open\"''', (dept,))
    
    return render_template('department_detail.html', dept=dept, equipment=equipment, stats=stats, maint_due=maint_due, flags=flags, state_badge=lambda x: 'badge-green', cond_badge=lambda x: 'badge-blue')





@app.route('/flag', methods=['GET', 'POST'])
@login_required
def flag_issue():
    return render_template('flag_issue.html')

@app.route('/intern')
@login_required
def intern_dashboard():
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
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    users = query('SELECT * FROM users')
    return render_template('user_list.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        email = request.form.get('email')
        
        execute('INSERT INTO users (username, password_hash, full_name, role, email) VALUES (?, ?, ?, ?, ?)',
                (username, generate_password_hash(password), full_name, role, email))
        flash('User created')
        return redirect(url_for('user_list'))
    return render_template('add_user.html')

@app.route('/users/<int:uid>/toggle', methods=['POST'])
@login_required
def toggle_user(uid):
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    user = query('SELECT is_active FROM users WHERE id = ?', (uid,), one=True)
    new_status = not user['is_active']
    execute('UPDATE users SET is_active = ? WHERE id = ?', (int(new_status), uid))
    flash('User status updated')
    return redirect(url_for('user_list'))

@app.route('/users/<int:uid>/reset-password', methods=['POST'])
@login_required
def reset_password(uid):
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    new_password = request.form['password']
    execute('UPDATE users SET password_hash = ? WHERE id = ?', (generate_password_hash(new_password), uid))
    flash('Password reset')
    return redirect(url_for('user_list'))

@app.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(uid):
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    user = query('SELECT * FROM users WHERE id = ?', (uid,), one=True)
    if not user:
        flash('User not found')
        return redirect(url_for('user_list'))
    if request.method == 'POST':
        full_name = request.form['full_name']
        role = request.form['role']
        email = request.form.get('email')
        execute('UPDATE users SET full_name = ?, role = ?, email = ? WHERE id = ?',
                (full_name, role, email, uid))
        flash('User updated')
        return redirect(url_for('user_list'))
    return render_template('edit_user.html', user=user)

@app.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
def delete_user(uid):
    if session.get('role') != 'chief_engineer':
        flash('Unauthorized')
        return redirect(url_for('dashboard'))
    if uid == session.get('user_id'):
        flash('Cannot delete yourself')
        return redirect(url_for('user_list'))
    execute('DELETE FROM users WHERE id = ?', (uid,))
    flash('User deleted')
    return redirect(url_for('user_list'))

if __name__ == '__main__':
    Path(os.path.dirname(DATABASE)).mkdir(parents=True, exist_ok=True)
    
    HOST    = os.environ.get('HOST', '0.0.0.0')
    PORT    = int(os.environ.get('PORT', '8000'))
    THREADS = int(os.environ.get('THREADS', '4'))
    
    print("=" * 60)
    print("  🏥 HEM - HOSPITAL EQUIPMENT MANAGEMENT SYSTEM")
    print("=" * 60)
    serve(app, host=HOST, port=PORT, threads=THREADS)
