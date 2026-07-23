import sqlite3
import os

DATABASE = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'hem.db'))

def run_migration():
    if not os.path.exists(DATABASE):
        print(f"Error: Database not found at {DATABASE}")
        return

    conn = sqlite3.connect(DATABASE)
    try:
        print("Starting migration...")
        # 1. Create Tables
        conn.execute('CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)')
        
        # 2. Migrate existing departments
        # Get unique departments from equipment
        cursor = conn.execute('SELECT DISTINCT department FROM equipment WHERE department IS NOT NULL')
        depts = [row[0] for row in cursor.fetchall() if row[0]]
        
        for dept_name in depts:
            conn.execute('INSERT OR IGNORE INTO departments (name) VALUES (?)', (dept_name,))
        
        # 3. Alter Equipment table
        # Check if department_id exists to avoid error if already migrated
        cursor = conn.execute('PRAGMA table_info(equipment)')
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'department_id' not in columns:
            conn.execute('ALTER TABLE equipment ADD COLUMN department_id INTEGER')
            print("Added department_id column.")
        
        # Populate department_id
        for dept_name in depts:
            result = conn.execute('SELECT id FROM departments WHERE name = ?', (dept_name,)).fetchone()
            if result:
                dept_id = result[0]
                conn.execute('UPDATE equipment SET department_id = ? WHERE department = ?', (dept_id, dept_name))
        
        print("Migration successful! Departments table created and data linked.")
        conn.commit()
        
    except sqlite3.OperationalError as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()
