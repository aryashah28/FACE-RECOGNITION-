import sqlite3

def update_admin():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Check if admin exists
    cursor.execute("SELECT id FROM employees WHERE name='admin'")
    admin = cursor.fetchone()
    
    if admin:
        print("Updating existing admin...")
        cursor.execute("""
            UPDATE employees 
            SET employee_id='ADMIN-001', phone='9898989898' 
            WHERE name='admin'
        """)
        conn.commit()
        print("Admin updated successfully.")
    else:
        print("Admin not found in database.")
    
    conn.close()

if __name__ == "__main__":
    update_admin()
