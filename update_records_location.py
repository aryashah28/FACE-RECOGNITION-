import sqlite3
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def update_locations():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    local_ip = get_local_ip()
    new_location = "Ahmedabad Office (Local Network)"

    print(f"Updating all employees to use: {new_location} and IP {local_ip}")
    
    # Update all employees in the records
    cursor.execute("""
        UPDATE employees 
        SET base_location = 'AHMEDABAD', 
            current_location = ?,
            last_ip = ?
    """, (new_location, local_ip))
    
    # Also update attendance records to be consistent
    cursor.execute("""
        UPDATE attendance
        SET location = ?
    """, (new_location,))
    
    conn.commit()
    print(f"Successfully updated all employee and attendance records.")
    
    conn.close()

if __name__ == "__main__":
    update_locations()
