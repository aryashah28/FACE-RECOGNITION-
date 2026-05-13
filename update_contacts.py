import sqlite3

def update_contact_numbers():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # --- Setup HR (YADAV JI) ---
    cursor.execute("""
        UPDATE employees 
        SET department='HR', 
            employee_id='HR-YAD-1001', 
            phone='0987654321', 
            designation='HR Manager',
            email='yadavji@visionid.com'
        WHERE name='YADAV JI'
    """)

    # --- Setup Finance (Riya) ---
    cursor.execute("""
        UPDATE employees 
        SET department='FINANCE', 
            employee_id='FIN-RIY-2001', 
            phone='9876543210', 
            designation='Finance Manager',
            email='riya@visionid.com'
        WHERE name='Riya'
    """)

    # --- Setup Operations (Dhrumi) ---
    cursor.execute("""
        UPDATE employees 
        SET department='OPERATIONS', 
            employee_id='OPS-DHR-3001', 
            phone='1234567890', 
            designation='Operations Head',
            email='dhrumi@visionid.com'
        WHERE name='Dhrumi'
    """)

    # --- Setup Technical (Ishika) ---
    cursor.execute("""
        UPDATE employees 
        SET department='TECHNICAL', 
            employee_id='TECH-ISH-4001', 
            phone='2345678901', 
            designation='Technical Lead',
            email='ishika@visionid.com'
        WHERE name='Ishika'
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_contact_numbers()
    print("Contact numbers updated successfully!")
