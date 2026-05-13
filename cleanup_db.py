import sqlite3

def final_cleanup():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Delete 'ADMIN' and keep only 'admin'
    cursor.execute("DELETE FROM employees WHERE name='ADMIN'")
    
    # Ensure 'admin' has the right ID and phone
    cursor.execute("""
        UPDATE employees 
        SET employee_id='ADMIN-001', phone='9898989898' 
        WHERE name='admin'
    """)
    
    conn.commit()
    print("Cleanup complete.")
    conn.close()

if __name__ == "__main__":
    final_cleanup()
