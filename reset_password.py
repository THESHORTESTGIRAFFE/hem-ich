import sqlite3
from werkzeug.security import generate_password_hash
import os

# 1. Configuration
# Ensure we use the correct path to the database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'instance', 'hem.db'))
NEW_PASSWORD = 'admin'  # Set to 'admin' as a default recovery password
USERNAME = 'admin'

# 2. Update the hash
if os.path.exists(DATABASE):
    conn = sqlite3.connect(DATABASE)
    new_hash = generate_password_hash(NEW_PASSWORD)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, USERNAME))
    conn.commit()
    conn.close()
    print(f"Password for user '{USERNAME}' has been reset to '{NEW_PASSWORD}'")
else:
    print(f"Error: Database not found at {DATABASE}")
