import sqlite3
import os

DATABASE = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'hem.db'))

def migrate_locations_to_departments():
    if not os.path.exists(DATABASE):
        print(f"Error: Database not found at {DATABASE}")
        return

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    print("Starting migration: Merging Locations to Departments...")
    try:
        # 1. Get all locations
        cursor.execute('SELECT id, name FROM locations')
        locations = cursor.fetchall()
        
        # 2. Add locations to departments if they don't exist
        for loc_id, loc_name in locations:
            cursor.execute('INSERT OR IGNORE INTO departments (name) VALUES (?)', (loc_name,))
            # Get the new department ID for this location name
            cursor.execute('SELECT id FROM departments WHERE name = ?', (loc_name,))
            dept_id = cursor.fetchone()[0]
            
            # 3. Update equipment: If it has this location_id, update to the new department_id
            cursor.execute('UPDATE equipment SET department_id = ? WHERE location_id = ?', (dept_id, loc_id))
        
        print("Locations merged into Departments successfully.")
        
        # Note: We cannot easily drop the column in SQLite without recreating the table.
        # We will keep the column but it will be ignored by the application logic.
        conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_locations_to_departments()
