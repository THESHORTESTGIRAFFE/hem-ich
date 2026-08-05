import sqlite3
import os

# Configuration: Ensure we use the correct path to the database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'instance', 'hem.db'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

def reset_db():
    if not os.path.exists(DATABASE):
        print(f"Error: Database not found at {DATABASE}")
        return

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Tables to clear
    tables = [
        'maintenance_records', 
        'disposal_records', 
        'attachments', 
        'issue_flags', 
        'equipment', 
        'departments', 
        'locations', 
        'audit_log'
    ]
    
    print("Clearing database tables...")
    
    # 1. Clear tables
    for table in tables:
        cursor.execute(f'DELETE FROM {table}')
    
    # 2. Clear users except 'admin'
    print("Clearing users except admin...")
    cursor.execute("DELETE FROM users WHERE username != 'admin'")
    
    # 3. Reset sqlite_sequence to start IDs from 1
    print("Resetting ID sequences...")
    cursor.execute('DELETE FROM sqlite_sequence')
    
    conn.commit()
    conn.close()
    print("Database reset successfully. Only 'admin' user remains.")
    
    # 4. Clear uploads directory
    if os.path.exists(UPLOAD_FOLDER):
        print(f"Clearing uploads folder: {UPLOAD_FOLDER}...")
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        print("Uploads folder cleared.")

if __name__ == '__main__':
    reset_db()
