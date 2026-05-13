import sqlite3
import datetime

def fix_dates():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, date FROM attendance WHERE date IS NOT NULL')
    rows = cursor.fetchall()
    
    for row_id, date_str in rows:
        if len(date_str) == 8 and date_str.count('/') == 2:
            # 10/04/26 -> 10/04/2026
            parts = date_str.split('/')
            if len(parts[2]) == 2:
                new_date = f"{parts[0]}/{parts[1]}/20{parts[2]}"
                cursor.execute('UPDATE attendance SET date=? WHERE id=?', (new_date, row_id))
    
    conn.commit()
    conn.close()
    print("Dates updated to DD/MM/YYYY successfully!")

if __name__ == "__main__":
    fix_dates()
