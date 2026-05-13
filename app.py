from flask import Flask, render_template, request, jsonify, redirect, session
import sqlite3
import cv2
import os
import face_recognition
import base64
import numpy as np
import datetime
import time
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_weak_key_do_not_use")
csrf = CSRFProtect(app)

# Security Headers (VAPT Compliance)
talisman = Talisman(
    app,
    content_security_policy={
        'default-src': '\'self\'',
        'script-src': [
            '\'self\'',
            'https://cdn.jsdelivr.net',
            'https://code.jquery.com',
            'https://cdnjs.cloudflare.com',
            'https://unpkg.com',
            '\'unsafe-inline\'' # Required for many dynamic components
        ],
        'style-src': [
            '\'self\'',
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net',
            '\'unsafe-inline\''
        ],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com'],
        'img-src': ['\'self\'', 'data:']
    },
    force_https=False # Set to True in production with SSL
)

# Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Session Security
app.config.update(
    SESSION_COOKIE_SECURE=False, # Set to True in production with SSL
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        date TEXT,
        time TEXT,
        status TEXT,      
        location TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        employee_id TEXT UNIQUE,
        password TEXT,
        birthdate TEXT,
        phone TEXT,
        email TEXT,
        position TEXT,
        occupation TEXT,
        designation TEXT,
        department TEXT,
        gender TEXT,
        base_location TEXT,
        current_location TEXT,
        last_ip TEXT,
        salary INTEGER DEFAULT 25000,
        reimbursement INTEGER DEFAULT 0
    )
    """)

    # --- Schema Migration: Add columns if table already exists ---
    try: cursor.execute("ALTER TABLE employees ADD COLUMN birthdate TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN phone TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN email TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN position TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN occupation TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN designation TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN department TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN gender TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN base_location TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN current_location TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN last_ip TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN salary INTEGER DEFAULT 25000")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN reimbursement INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE attendance ADD COLUMN location TEXT")
    except sqlite3.OperationalError: pass

    # --- Ensure Admin exists ---
    cursor.execute("SELECT id FROM employees WHERE name='admin' OR name='ADMIN'")
    admins = cursor.fetchall()
    if not admins:
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin")
        cursor.execute("""
            INSERT INTO employees (name, employee_id, password, gender, base_location, occupation, designation, department, current_location, salary, reimbursement, phone) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("admin", "ADMIN-001", generate_password_hash(admin_pass), "Female", "AHMEDABAD", "Admin", "System Admin", "IT", "Ahmedabad Office", 50000, 0, "9898989898"))
    elif len(admins) > 1:
        # Cleanup redundant admin
        cursor.execute("DELETE FROM employees WHERE name='ADMIN'")
        cursor.execute("UPDATE employees SET name='admin', employee_id='ADMIN-001', phone='9898989898' WHERE name='admin'")

    conn.commit()
    conn.close()


init_db()

# ---------------- HELPERS ---------------- #

import urllib.request
import json
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

def get_client_ip():
    ip = request.remote_addr
    if ip == "127.0.0.1" or ip == "::1":
        return get_local_ip()
    return ip

def get_location_from_ip(ip):
    # For local/private IPs, try to get the public IP to provide a real location
    target_ip = ip
    if ip == "127.0.0.1" or ip == "::1" or ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
        try:
            # Fetch public IP of the server/environment if the client is local
            with urllib.request.urlopen("https://api.ipify.org") as response:
                target_ip = response.read().decode('utf8')
        except:
            pass

    try:
        url = f"http://ip-api.com/json/{target_ip}"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                city = data.get('city')
                region = data.get('regionName')
                # Common ISP routing issue: Ahmedabad users often show as Surat due to ISP gateways
                if city == "Surat" and region == "Gujarat":
                    city = "Ahmedabad"
                return f"{city}, {region}, {data.get('country')}"
    except:
        pass
    
    return "Ahmedabad, Gujarat, India" if target_ip == ip else "Unknown Location"

# ---------------- DATASET ---------------- #

known_encodings = []
known_names = []
known_dataset_files = set()
dataset_path = "dataset"

def load_dataset():
    global known_encodings, known_names, known_dataset_files

    known_encodings = []
    known_names = []
    known_dataset_files = set()

    if os.path.exists(dataset_path):
        for file in os.listdir(dataset_path):
            if file.endswith((".jpg", ".png", ".jpeg")):
                known_dataset_files.add(file)

                path = os.path.join(dataset_path, file)
                image = face_recognition.load_image_file(path)
                encodings = face_recognition.face_encodings(image)

                if encodings:
                    known_encodings.append(encodings[0])
                    name = os.path.splitext(file)[0].split("_")[0]
                    known_names.append(name)

    print("Dataset loaded:", known_names)

load_dataset()

# ---------------- ATTENDANCE ---------------- #

def mark_attendance(name, status="Login"):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    now = datetime.datetime.now()
    date = now.strftime("%d-%m-%Y")
    time_str = now.strftime("%H:%M:%S")
    
    # Get IP and Location
    ip = get_client_ip()
    location = get_location_from_ip(ip)

    cursor.execute(
        "INSERT INTO attendance (name,date,time,status,location) VALUES (?,?,?,?,?)",
        (name, date, time_str, status, location)
    )
    
    # Also update employee's last known location
    cursor.execute("UPDATE employees SET current_location=?, last_ip=? WHERE name=?", (location, ip, name))

    conn.commit()
    conn.close()

# ---------------- GLOBALS ---------------- #

last_name = None
last_time = 0

# ---------------- ROUTES ---------------- #

@app.route('/')
def login():
    return render_template("login.html")

@app.route('/home')
def home():
    if "user" not in session:
        return redirect("/")
    
    username = session["user"]
    
    # Refresh current location if it's an employee
    if username.lower() != "admin":
        ip = get_client_ip()
        location = get_location_from_ip(ip)
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE employees SET current_location=?, last_ip=? WHERE name=?", (location, ip, username))
        conn.commit()
        conn.close()

    profile_pic = None
    if os.path.exists(dataset_path):
        for file in os.listdir(dataset_path):
            if file.lower().startswith(f"{username.lower()}_") and file.lower().endswith((".jpg", ".png", ".jpeg")):
                profile_pic = file
                break
                
    return render_template("home.html", profile_pic=profile_pic)

@app.route('/how_it_works')
def how_it_works():
    return render_template("how_it_works.html")

@app.route('/admin')
def admin():
    if "user" not in session or session["user"].lower() != "admin":
        return redirect("/")
    
    # Get current admin info
    ip = get_client_ip()
    location = get_location_from_ip(ip)
    
    admin_info = {
        "ip": ip,
        "current_location": location,
        "base_location": "AHMEDABAD", # Default for Admin
        "employee_id": "ADMIN-001"
    }
    
    return render_template("admin.html", admin_info=admin_info)

@app.route('/vapt')
def vapt_dashboard():
    if "user" not in session or session["user"].lower() != "admin":
        return redirect("/")
    return render_template("vapt.html")

@app.route('/services')
def services():
    return render_template("services.html")

@app.route('/logout')
def logout():
    if "user" in session:
        mark_attendance(session["user"], status="Logout")
    session.clear()
    return redirect('/')

@app.route('/department')
def department_portal():
    if "user" not in session:
        return redirect("/")
    return render_template("department.html")

@app.route('/employee_dashboard')
def employee_dashboard():
    if "user" not in session:
        return redirect("/")
    
    username = session["user"]
    
    if username.lower() == "admin":
        ip = get_client_ip()
        location = get_location_from_ip(ip)
        
        # Load admin details from DB
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT salary, reimbursement, employee_id, email, department, designation, phone, base_location FROM employees WHERE LOWER(name)='admin'", )
        admin_db = cursor.fetchone()
        conn.close()

        # Look for admin's profile picture
        profile_pic = None
        if os.path.exists(dataset_path):
            for file in os.listdir(dataset_path):
                if file.startswith("admin_") and file.endswith((".jpg", ".png", ".jpeg")):
                    profile_pic = file
                    break

        return render_template("employee_dashboard.html", user_data={
            "name": "Administrator",
            "employee_id": admin_db[2] if admin_db else "ADMIN-001",
            "email": admin_db[3] if admin_db else "admin@visionid.com",
            "department": admin_db[4] if admin_db else "All",
            "designation": admin_db[5] if admin_db else "System Administrator",
            "phone": admin_db[6] if admin_db else "9898989898",
            "profile_pic": profile_pic,
            "base_location": admin_db[7] if admin_db else "AHMEDABAD",
            "current_location": location,
            "live_ip": ip,
            "salary": admin_db[0] if admin_db else 50000,
            "reimbursement": admin_db[1] if admin_db else 0
        })

    # Get live info
    ip = get_client_ip()
    live_location = get_location_from_ip(ip)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, employee_id, email, department, designation, phone, base_location, salary, reimbursement FROM employees WHERE LOWER(name)=LOWER(?)", (username,))
    user = cursor.fetchone()

    # Update latest location in DB
    cursor.execute("UPDATE employees SET current_location=?, last_ip=? WHERE LOWER(name)=LOWER(?)", (live_location, ip, username))
    conn.commit()
    conn.close()

    if not user:
        return redirect("/home")

    # Look for profile picture in dataset
    profile_pic = None
    if os.path.exists(dataset_path):
        for file in os.listdir(dataset_path):
            if file.lower().startswith(f"{username.lower()}_") and file.lower().endswith((".jpg", ".png", ".jpeg")):
                profile_pic = file
                break

    user_data = {
        "name": user[0],
        "employee_id": user[1],
        "email": user[2],
        "department": user[3],
        "designation": user[4],
        "phone": user[5],
        "base_location": user[6] if user[6] else "AHMEDABAD",
        "current_location": live_location, 
        "live_ip": ip,
        "profile_pic": profile_pic,
        "salary": user[7],
        "reimbursement": user[8]
    }

    return render_template("employee_dashboard.html", user_data=user_data)

from flask import send_from_directory
@app.route('/dataset/<path:filename>')
def serve_dataset(filename):
    if "user" not in session:
        return "Unauthorized", 401
    return send_from_directory(dataset_path, filename)

# ---------------- ATTENDANCE APIs ---------------- #

@app.route('/get_analytics')
def get_analytics():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # --- 📈 Attendance Trend (Last 7 Days) ---
    trend_data = {}
    for i in range(6, -1, -1):
        date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%d-%m-%Y")
        cursor.execute("SELECT COUNT(DISTINCT name) FROM attendance WHERE date=?", (date,))
        count = cursor.fetchone()[0]
        trend_data[date] = count

    # --- 📅 Monthly Attendance % ---
    current_month_prefix = datetime.datetime.now().strftime("%m-%Y")
    cursor.execute("SELECT COUNT(DISTINCT name || date) FROM attendance WHERE date LIKE ?", (f"%-{current_month_prefix}",))
    present_total = cursor.fetchone()[0]
    
    # Total possible: Employees * Days in current month passed so far
    employee_count = 0
    if os.path.exists(dataset_path):
        employee_count = len([f for f in os.listdir(dataset_path) if f.endswith((".jpg", ".png", ".jpeg"))])
    
    day_of_month = datetime.datetime.now().day
    total_possible = max(1, employee_count * day_of_month)
    monthly_percentage = round((present_total / total_possible) * 100, 1)

    # --- 🕔 Peak Check-in Times (Hourly Distribution) ---
    cursor.execute("SELECT SUBSTR(time, 1, 2) as hour, COUNT(*) FROM attendance GROUP BY hour")
    hour_records = cursor.fetchall()
    peak_times = {f"{h}:00": count for h, count in hour_records}

    conn.close()
    
    return jsonify({
        "trend": trend_data,
        "monthly_stat": monthly_percentage,
        "peaks": peak_times
    })

@app.route('/get_attendance')
def get_attendance():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.name, e.employee_id, e.department, e.gender, e.base_location, e.current_location, e.last_ip, 
               e.occupation, e.designation, e.phone, e.email, a.date, a.time, a.status
        FROM employees e
        LEFT JOIN attendance a ON a.id = (
            SELECT MAX(id) FROM attendance WHERE LOWER(name) = LOWER(e.name)
        )
        ORDER BY e.id DESC
    """)
    
    results = cursor.fetchall()
    employees_list = []
    
    for idx, row in enumerate(results, 1):
        name, emp_id, dept, gender, base_loc, cur_loc, last_ip, occ, des, phone, email, date, time, status = row
        
        display_name = name if name else "Unknown"
        loc_display = cur_loc if cur_loc else "Detecting..."
        if last_ip and last_ip != "N/A":
            loc_display = f"{loc_display} (IP: {last_ip})"

        employees_list.append({
            "id": idx,
            "name": display_name,
            "occupation": occ or "-",
            "designation": des or "-",
            "gender": gender or "N/A",
            "base_location": base_loc or "AHMEDABAD",
            "current_location": loc_display,
            "current_ip": last_ip or "N/A",
            "employee_id": emp_id or "-",
            "phone": phone or "-",
            "email": email or "-",
            "department": dept or "-",
            "date": date or "N/A",
            "time": time or "-",
            "status": status or "Not Logged"
        })
  
    conn.close()
    return jsonify(employees_list)


@app.route('/search_attendance', methods=['POST'])
def search_attendance():
    data = request.json
    search_name = data.get("name", "").strip()
    search_date_raw = data.get("date", "").strip()
    
    search_date = ""
    if search_date_raw:
        # Convert YYYY-MM-DD from input[type=date] to DD-MM-YYYY
        try:
            search_date = datetime.datetime.strptime(search_date_raw, "%Y-%m-%d").strftime("%d-%m-%Y")
        except:
            search_date = search_date_raw

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    employees_list = []
    
    # 🛡️ CASE A & B: Search records by name and/or date
    query = """
        SELECT e.name, e.employee_id, e.department, e.gender, e.base_location, e.current_location, e.last_ip, 
               e.occupation, e.designation, e.phone, e.email, a.date, a.time, a.status
        FROM employees e
        LEFT JOIN attendance a ON a.id = (
            SELECT MAX(id) FROM attendance WHERE LOWER(name) = LOWER(e.name)
    """
    params = []
    
    if search_date:
        query += " AND date = ?"
        params.append(search_date)
        
    query += ")"
    
    if search_name:
        query += " AND (e.name LIKE ? OR e.employee_id LIKE ?)"
        params.append(f"%{search_name}%")
        params.append(f"%{search_name}%")
        
    query += " ORDER BY e.id DESC"
    
    cursor.execute(query, tuple(params))
    results = cursor.fetchall()
    
    for idx, row in enumerate(results, 1):
        name, emp_id, dept, gender, base_loc, cur_loc, last_ip, occ, des, phone, email, date, time, status = row
        display_name = name if name else "Unknown"
        
        loc_display = cur_loc if cur_loc else "Records Log"
        if last_ip and last_ip != "N/A":
            loc_display = f"{loc_display} (IP: {last_ip})"
            
        employees_list.append({
            "id": idx,
            "name": display_name,
            "occupation": occ or "-",
            "designation": des or "-",
            "gender": gender or "N/A",
            "base_location": base_loc or "AHMEDABAD",
            "current_location": loc_display,
            "current_ip": last_ip or "N/A",
            "employee_id": emp_id or "-",
            "phone": phone or "-",
            "email": email or "-",
            "department": dept or "-",
            "date": date or "N/A",
            "time": time or "-",
            "status": status or "Not Logged"
        })

    # 🛡️ CASE C: Default (No name, No date) - Return today's summary (Same as get_attendance)
    if not search_name and not search_date:
        conn.close()
        return get_attendance()
    
    conn.close()
    return jsonify(employees_list)


# ---------------- REGISTER ---------------- #

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    if "user" not in session or session["user"].lower() != "admin":
        return redirect("/")

    if request.method == 'GET':
        return render_template('register.html')

    name = request.form.get('name')
    birthdate = request.form.get('birthdate')
    phone = request.form.get('phone')
    email = request.form.get('email')
    occupation = request.form.get('occupation')
    designation = request.form.get('designation')
    department = request.form.get('department')
    gender = request.form.get('gender')
    base_location = request.form.get('base_location', 'AHMEDABAD')
    password = request.form.get('password')

    if not name or not password or not birthdate or not phone or not email or not occupation or not designation or not department or not gender:
        return "All required fields are missing", 400

    # Validate birthdate (must not be futuristic, max 2026)
    try:
        birth_year = int(birthdate.split('-')[0])
        if birth_year > 2026:
            return "Invalid birthdate (Future years not allowed)", 400
    except:
        pass

    # Auto-generate Employee ID
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM employees")
    emp_count = cursor.fetchone()[0]
    employee_id = f"EMP-{101 + emp_count}"
 
    # Get IP and Location
    ip = get_client_ip()
    location = get_location_from_ip(ip)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    # Unique employee_id and password for new user
    hashed_password = generate_password_hash(password)
    try:
        cursor.execute("""
            INSERT INTO employees (name, employee_id, password, birthdate, phone, email, occupation, designation, department, gender, base_location, current_location, last_ip) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, employee_id, hashed_password, birthdate, phone, email, occupation, designation, department, gender, base_location, location, ip))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "This Employee ID or Email is already registered", 400
    conn.close()

    if not os.path.exists(dataset_path):
        os.makedirs(dataset_path)

    cap = cv2.VideoCapture(0)
    count = 1

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.resize(frame, (640, 480))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb)

        for (top, right, bottom, left) in face_locations:
            face_img = frame[top:bottom, left:right]

            file_name = f"{name}_{count}.jpg"
            file_path = os.path.join(dataset_path, file_name)

            cv2.imwrite(file_path, face_img)
            count += 1

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        cv2.imshow("Register Face", frame)

        if count >= 2:
            break

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    load_dataset()

    return jsonify({
        "status": "success",
        "message": f"{name} registered successfully"
    })

@app.route('/edit_employee', methods=['POST'])
def edit_employee():
    if "user" not in session or session["user"].lower() != "admin":
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401
    
    data = request.json
    old_name = data.get("old_name")
    new_gender = data.get("gender")
    new_base_loc = data.get("base_location")
    new_occ = data.get("occupation")
    new_des = data.get("designation")
    new_id = data.get("employee_id")
    new_phone = data.get("phone")
    new_email = data.get("email")
    new_dept = data.get("department")
    new_password = data.get("password")
    
    if not old_name:
        return jsonify({"status": "fail", "message": "Missing name"}), 400
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE employees 
        SET gender=?, base_location=?, occupation=?, designation=?, employee_id=?, phone=?, email=?, department=?
        WHERE name=?
    """, (new_gender, new_base_loc, new_occ, new_des, new_id, new_phone, new_email, new_dept, old_name))
    
    if new_password and new_password.strip():
        cursor.execute("UPDATE employees SET password=? WHERE name=?", (generate_password_hash(new_password), old_name))
    
    # Also update attendance records if name changed (but we are only editing other fields for now to keep it safe)
    
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Employee updated successfully"})

# ---------------- ID LOGIN ---------------- #

@app.route('/login_id', methods=['POST'])
@limiter.limit("5 per minute")
def login_id():
    data = request.json
    emp_id = data.get("employee_id", "").strip()
    password = data.get("password")

    if not emp_id or not password:
        return jsonify({"status": "fail", "message": "ID and Password are required"})

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Handle both Admin and Employee via DB (Case-Insensitive)
    if emp_id.lower() == "admin" or emp_id.upper() == "ADMIN-001":
        cursor.execute("SELECT name, password FROM employees WHERE employee_id='ADMIN-001' OR name='admin' OR name='ADMIN'")
    else:
        # Use COLLATE NOCASE for case-insensitive matching in SQLite
        cursor.execute("SELECT name, password FROM employees WHERE employee_id=? COLLATE NOCASE", (emp_id,))
    
    user = cursor.fetchone()
    conn.close()

    # Check for password in .env first
    env_key = f"PASS_{emp_id.upper().replace('-', '_')}"
    env_password = os.getenv(env_key)

    if user:
        # 1. Match against .env password (if exists)
        # 2. Match against DB hash
        is_match = (env_password and password == env_password) or check_password_hash(user[1], password)
        
        if is_match:
            name = user[0]
            # Record login time
            mark_attendance(name, status="Login")
            
            # Update session trackers
            global last_name, last_time
            last_name = name
            last_time = time.time()
                
            session["user"] = name
            
            # Dynamic redirect based on name/role
            redirect_url = "/admin" if name.lower() == "admin" else "/home"
            return jsonify({"status": "success", "name": name, "redirect": redirect_url})
        else:
            return jsonify({"status": "fail", "message": "Incorrect password. Please try again."})
    
    return jsonify({"status": "fail", "message": "Employee ID not found. Contact Admin."})

# ---------------- RESET PASSWORD ---------------- #

@app.route('/reset_password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def reset_password():
    if request.method == 'GET':
        return render_template('reset_password.html')

    data = request.json
    employee_id = data.get('employee_id')
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not employee_id or not current_password or not new_password:
        return jsonify({"status": "fail", "message": "All fields are required"})

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Check if the person attempting reset is the admin
    cursor.execute("SELECT password FROM employees WHERE employee_id='ADMIN-001' OR LOWER(name)='admin'")
    admin_data = cursor.fetchone()
    
    # Allow reset if current_password matches admin password (admin intervention)
    # OR if current_password matches the user's own password
    is_admin_reset = admin_data and check_password_hash(admin_data[0], current_password)

    if is_admin_reset:
        cursor.execute("SELECT id FROM employees WHERE employee_id=?", (employee_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE employees SET password=? WHERE employee_id=?", (generate_password_hash(new_password), employee_id))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "message": "Password reset via Admin successfully!", "redirect": "/login"})
        else:
            conn.close()
            return jsonify({"status": "fail", "message": "Employee ID not found"})

    cursor.execute("SELECT password FROM employees WHERE employee_id=?", (employee_id,))
    user = cursor.fetchone()

    if user and check_password_hash(user[0], current_password):
        cursor.execute("UPDATE employees SET password=? WHERE employee_id=?", (generate_password_hash(new_password), employee_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Password reset successfully!", "redirect": "/login"})

    conn.close()
    return jsonify({"status": "fail", "message": "Invalid Employee ID or Current Password"})                                    


# ---------------- FACE LOGIN ---------------- #

@app.route('/face_login', methods=['POST'])
def face_login():

    global last_name, last_time

    # Performance: Skipped dataset check on every request (only updated on registration)

    if not known_encodings:
        # Emergency reload if empty
        if os.listdir(dataset_path): load_dataset()
        if not known_encodings: return jsonify({"status": "fail", "message": "No registered users"})

    if not request.json or 'image' not in request.json:
        return jsonify({"status": "fail", "message": "Missing image data"}), 400

    data = request.json['image']
    image_data = data.split(",")[1]
    decoded = base64.b64decode(image_data)

    np_img = np.frombuffer(decoded, np.uint8)
    frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    # Optimization: 480x360 is much faster than 640x480 while maintaining eye visibility
    frame = cv2.resize(frame, (480, 360))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb)

    if not face_locations:
        return jsonify({"status": "fail", "message": "No face detected"})

    encodings = face_recognition.face_encodings(rgb, face_locations)

    if not encodings:
        return jsonify({"status": "fail", "message": "Encoding failed"})

    # ---------------- MATCH FACE ---------------- #

    face_encoding = encodings[0]
    distances = face_recognition.face_distance(known_encodings, face_encoding)
    best_index = np.argmin(distances)
    recognized_name = known_names[best_index] if distances[best_index] <= 0.6 else None

    if not recognized_name: 
        return jsonify({"status": "fail", "message": "Face not recognized", "liveness_progress": 0})

    name = recognized_name

    # ---------------- LOGIN SUCCESS ---------------- #

    if name.lower() == "admin":
        mark_attendance(name, status="Login")
        session["user"] = name
        return jsonify({
            "status": "success",
            "name": name,
            "redirect": "/admin",
            "liveness_progress": 100
        })

    # Employee Login
    mark_attendance(name, status="Login")
    last_name = name
    last_time = time.time()
    session["user"] = name

    return jsonify({
        "status": "success",
        "name": name,
        "redirect": "/home",
        "liveness_progress": 100
    })

# ---------------- DEPARTMENT API ---------------- #

@app.route('/get_dept_info', methods=['POST'])
def get_dept_info():
    if "user" not in session:
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401
    
    data = request.json
    requested_dept = data.get("department")
    username = session["user"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get information about the current logged-in user
    cursor.execute("SELECT name, department FROM employees WHERE name=?", (username,))
    current_user_data = cursor.fetchone()
    current_user_dept = current_user_data[1] if current_user_data else None

    # Role check: Admin or HR
    is_privileged = (username.lower() == "admin" or (current_user_dept and current_user_dept.upper() == "HR"))

    if requested_dept.upper() == "FINANCE" and is_privileged:
        # Admin and HR see EVERYONE'S salary in Finance
        cursor.execute("SELECT name, employee_id, department, designation, salary FROM employees")
        all_emps = cursor.fetchall()
        conn.close()
        
        records = []
        for emp in all_emps:
            records.append({
                "name": emp[0],
                "employee_id": emp[1],
                "department": emp[2],
                "designation": emp[3],
                "salary": emp[4]
            })
        
        return jsonify({
            "status": "success",
            "type": "all_records",
            "data": records
        })

    if username.lower() == "admin":
        # For other departments, Admin still sees the head of that department
        cursor.execute("""
            SELECT name, employee_id, department, designation, email, phone 
            FROM employees 
            WHERE department=? LIMIT 1
        """, (requested_dept,))
        user_info = cursor.fetchone()
        
        if not user_info:
            conn.close()
            return jsonify({"status": "fail", "message": f"No person allotted to {requested_dept} yet."})
            
        data_payload = {
            "name": user_info[0],
            "employee_id": user_info[1],
            "department": user_info[2],
            "designation": user_info[3],
            "email": user_info[4],
            "phone": user_info[5]
        }
    else:
        # Regular user can only see their own info (including salary if requested FINANCE)
        if requested_dept.upper() == "FINANCE":
            cursor.execute("SELECT name, employee_id, department, designation, email, phone, salary FROM employees WHERE name=?", (username,))
        else:
            cursor.execute("SELECT name, employee_id, department, designation, email, phone FROM employees WHERE name=?", (username,))
        
        user_info = cursor.fetchone()
        
        if not user_info:
            conn.close()
            return jsonify({"status": "fail", "message": "User not found"})

        # Check if user's department matches requested department (except handled finance logic)
        if user_info[2].upper() != requested_dept.upper():
            conn.close()
            return jsonify({
                "status": "fail", 
                "message": f"Access Denied. You are in {user_info[2]} department. You can only view details for your allocated department."
            })
            
        data_payload = {
            "name": user_info[0],
            "employee_id": user_info[1],
            "department": user_info[2],
            "designation": user_info[3],
            "email": user_info[4],
            "phone": user_info[5]
        }
        
        if requested_dept.upper() == "FINANCE":
            data_payload["salary"] = user_info[6]

    conn.close()
    return jsonify({
        "status": "success",
        "type": "single_record",
        "data": data_payload
    })

# ---------------- PHOTO UPLOAD API ---------------- #

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if "user" not in session:
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401
    
    if 'photo' not in request.files:
        return jsonify({"status": "fail", "message": "No file part"})
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"status": "fail", "message": "No selected file"})
    
    if file and file.filename.lower().endswith(('.jpg', '.png', '.jpeg')):
        username = session["user"]
        
        # Save consistently as {username}_1.jpg for main display
        filename = f"{username}_1.jpg"
        filepath = os.path.join(dataset_path, filename)
        
        # Delete existing ones to avoid confusion
        if os.path.exists(filepath):
            os.remove(filepath)
            
        file.save(filepath)
        
        # Reload dataset so face recognition works with new photo if applicable
        load_dataset()
        
        return jsonify({"status": "success", "message": "Profile photo updated!"})
    
    return jsonify({"status": "fail", "message": "Invalid file type. Only JPG, PNG, JPEG allowed."})

import subprocess
@app.route('/run_vapt_scan', methods=['POST'])
def run_vapt_scan():
    if "user" not in session or session["user"].lower() != "admin":
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401
    
    try:
        # Run Bandit (Actual VAPT audit tool)
        # Using sys.executable to ensure we run in the same environment
        import sys
        result = subprocess.run([sys.executable, "-m", "bandit", "-r", "app.py"], capture_output=True, text=True)
        
        # We also check dependencies (Safety)
        # result_safety = subprocess.run([sys.executable, "-m", "safety", "check"], capture_output=True, text=True)
        
        return jsonify({
            "status": "success",
            "audit_output": result.stdout if result.stdout else "No issues found.",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

# ---------------- DEMO ---------------- #

@app.route('/start_demo')
def start_demo():

    camera = cv2.VideoCapture(0)

    while True:
        ret, frame = camera.read()
        if not ret:
            continue

        frame = cv2.resize(frame, (320, 240))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb)

        for top, right, bottom, left in face_locations:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        cv2.imshow("Face Detection Demo", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()

    return redirect('/')


# ---------------- CONFIG MANAGEMENT ---------------- #

@app.route('/get_env_config')
def get_env_config():
    if "user" not in session or session["user"].lower() != "admin":
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401
    
    try:
        with open(".env", "r") as f:
            content = f.read()
        return jsonify({"status": "success", "content": content})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/update_env_config', methods=['POST'])
def update_env_config():
    if "user" not in session or session["user"].lower() != "admin":
        return jsonify({"status": "fail", "message": "Unauthorized"}), 401
    
    content = request.json.get("content")
    if not content:
        return jsonify({"status": "fail", "message": "No content provided"})
    
    try:
        # Manage file attributes to allow update
        import subprocess
        subprocess.run(["attrib", "-h", ".env"])
        
        with open(".env", "w") as f:
            f.write(content)
            
        subprocess.run(["attrib", "+h", ".env"])
        
        # Reload environment
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        return jsonify({"status": "success", "message": "Configuration (.env) updated successfully!"})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

# ---------------- RUN APP ---------------- #

if __name__ == "__main__":
    app.run(debug=os.getenv("DEBUG", "False").lower() == "true", port=int(os.getenv("PORT", 5000)))