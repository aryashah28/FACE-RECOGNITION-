import sqlite3

def revert_dates():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, date FROM attendance WHERE date IS NOT NULL')
    rows = cursor.fetchall()
    
    for row_id, date_str in rows:
        # e.g., 10/04/2026 -> 10/04/26
        if len(date_str) == 10 and date_str.count('/') == 2:
            parts = date_str.split('/')
            if len(parts[2]) == 4:
                # take last 2 digits of the year
                new_date = f"{parts[0]}/{parts[1]}/{parts[2][2:]}"
                cursor.execute('UPDATE attendance SET date=? WHERE id=?', (new_date, row_id))
    
    conn.commit()
    conn.close()
    print("Dates reverted to DD/MM/YY successfully!")

if __name__ == "__main__":
    revert_dates()
