import sqlite3
conn = sqlite3.connect('database.db')
print("---Employees---")
print(conn.execute('SELECT name, employee_id FROM employees').fetchall())
print("---Attendance---")
print(conn.execute('SELECT name, date, time, status FROM attendance').fetchall())
conn.close()
