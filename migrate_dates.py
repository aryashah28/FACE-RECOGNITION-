import sqlite3
import datetime

def migrate_dates():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, date FROM attendance WHERE date IS NOT NULL')
    rows = cursor.fetchall()
    
    updated = 0
    for row_id, date_str in rows:
        new_date = None
        try:
            # Handle YYYY-MM-DD  →  DD-MM-YYYY
            if len(date_str) == 10 and date_str[4] == '-' and date_str.count('-') == 2:
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                new_date = dt.strftime("%d-%m-%Y")
            # Handle DD/MM/YY   →  DD-MM-YYYY
            elif '/' in date_str and len(date_str) in (8, 10):
                parts = date_str.split('/')
                year = parts[2] if len(parts[2]) == 4 else f"20{parts[2]}"
                new_date = f"{parts[0]}-{parts[1]}-{year}"
            # Handle DD/MM/YYYY →  DD-MM-YYYY
        except Exception as e:
            print(f"  Could not convert '{date_str}': {e}")
            continue

        if new_date and new_date != date_str:
            cursor.execute('UPDATE attendance SET date=? WHERE id=?', (new_date, row_id))
            updated += 1

    conn.commit()
    conn.close()
    print(f"Migration complete. {updated} records updated to DD-MM-YYYY format.")

if __name__ == "__main__":
    migrate_dates()
