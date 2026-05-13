import sqlite3
import random

def setup_salaries():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM employees")
    employees = cursor.fetchall()

    for emp in employees:
        name = emp[0]
        if name == 'admin':
            salary = 0 # Admin salary is private or not relevant
            reimbursement = 0
        else:   
            salary = random.randint(20000, 50000)
            reimbursement = random.randint(500, 5000)
            
        cursor.execute("UPDATE employees SET salary=?, reimbursement=? WHERE name=?", (salary, reimbursement, name))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_salaries()
    print("Salaries and reimbursements initialized!")
