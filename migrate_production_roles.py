import sqlite3
import os

# Update this path if necessary to point to the production database
DB_PATH = os.path.join('instance', 'hem.db')

if not os.path.exists(DB_PATH):
    print(f"Error: Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Map old roles to new ones
role_mapping = {
    'chief_engineer': 'biomedical_engineer',
    'technician': 'biomedical_technician'
}

for old_role, new_role in role_mapping.items():
    cursor.execute("UPDATE users SET role = ? WHERE role = ?", (new_role, old_role))

conn.commit()
conn.close()
print("Production database updated successfully.")
