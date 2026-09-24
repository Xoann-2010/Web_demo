"""
database.py — Quản lý cơ sở dữ liệu SQLite cho Hệ Thống Đo Góc Cổ Lâm Sàng
Lưu trữ thông tin Bác sĩ, Bệnh nhân, và Lịch sử các phiên đo.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.db")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Bảng Bác sĩ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        title TEXT DEFAULT 'Bác sĩ CKI',
        department TEXT DEFAULT 'Khoa Phục Hồi Chức Năng',
        hospital TEXT DEFAULT 'Bệnh viện Đa khoa Trung ương',
        email TEXT DEFAULT 'bacsi@hospital.vn',
        phone TEXT DEFAULT '0912.345.678'
    )
    """)

    # Bảng Bệnh nhân
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        age INTEGER,
        gender TEXT,
        diagnosis TEXT,
        phone TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # Bảng Phiên đo
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        patient_name TEXT,
        doctor_name TEXT,
        start_time TEXT,
        duration_s REAL DEFAULT 0,
        csv_filename TEXT,
        max_flexion REAL DEFAULT 0,
        max_extension REAL DEFAULT 0,
        max_roll_left REAL DEFAULT 0,
        max_roll_right REAL DEFAULT 0,
        avg_pitch REAL DEFAULT 0,
        avg_roll REAL DEFAULT 0,
        total_samples INTEGER DEFAULT 0,
        doctor_notes TEXT DEFAULT '',
        status TEXT DEFAULT 'completed',
        events_json TEXT DEFAULT '[]',
        FOREIGN KEY (patient_id) REFERENCES patients(id)
    )
    """)

    # Khởi tạo bác sĩ mặc định nếu chưa có
    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO doctors (name, title, department, hospital, email, phone)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "BS. CKI Nguyễn Văn A",
            "Bác sĩ Chuyên khoa I",
            "Khoa Phục Hồi Chức Năng & Cơ Xương Khớp",
            "Bệnh viện Đại học Y Hà Nội",
            "dr.nguyenvana@hmu.edu.vn",
            "0988.123.456"
        ))

    # Khởi tạo bệnh nhân mẫu lâm sàng nếu chưa có
    cursor.execute("SELECT COUNT(*) FROM patients")
    if cursor.fetchone()[0] == 0:
        sample_patients = [
            ("BN-001", "Nguyễn Văn Bệnh Nhân", 45, "Nam", "Thoái hóa đốt sống cổ C5-C6 kèm hạn chế vận động cúi/ngửa", "0901.234.567", "Hà Nội", "Đau mỏi tăng khi ngồi máy tính lâu"),
            ("BN-002", "Trần Thị Mai", 38, "Nữ", "Hội chứng cổ vai cánh tay (Whiplash sau va chạm nhẹ)", "0912.987.654", "Hải Phòng", "Hạn chế nghiêng phải, co cứng cơ thang"),
            ("BN-003", "Lê Hoàng Nam", 52, "Nam", "Hẹp lỗ liên hợp đốt sống cổ, tê bì cánh tay phải", "0934.567.890", "Nam Định", "Đã điều trị bảo tồn 2 tuần"),
            ("BN-004", "Phạm Thu Hương", 29, "Nữ", "Hội chứng đau cân cơ vùng cổ (Myofascial pain syndrome)", "0977.112.233", "Hà Nội", "Nhân viên văn phòng, tư thế đầu đưa ra trước (Forward Head Posture)")
        ]
        cursor.executemany("""
            INSERT INTO patients (code, name, age, gender, diagnosis, phone, address, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_patients)

    conn.commit()
    conn.close()

def get_current_doctor():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_doctor(data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE doctors
        SET name = ?, title = ?, department = ?, hospital = ?, email = ?, phone = ?
        WHERE id = ?
    """, (
        data.get("name"),
        data.get("title"),
        data.get("department"),
        data.get("hospital"),
        data.get("email"),
        data.get("phone"),
        data.get("id", 1)
    ))
    conn.commit()
    conn.close()
    return True

def list_patients():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_patient(patient_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_patient(data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO patients (code, name, age, gender, diagnosis, phone, address, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("code"),
        data.get("name"),
        data.get("age"),
        data.get("gender"),
        data.get("diagnosis"),
        data.get("phone", ""),
        data.get("address", ""),
        data.get("notes", "")
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def list_sessions(patient_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if patient_id:
        cursor.execute("SELECT * FROM sessions WHERE patient_id = ? ORDER BY id DESC", (patient_id,))
    else:
        cursor.execute("SELECT * FROM sessions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_session(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_session(data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (
            patient_id, patient_name, doctor_name, start_time, duration_s,
            csv_filename, max_flexion, max_extension, max_roll_left, max_roll_right,
            avg_pitch, avg_roll, total_samples, doctor_notes, status, events_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("patient_id"),
        data.get("patient_name"),
        data.get("doctor_name"),
        data.get("start_time", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        data.get("duration_s", 0),
        data.get("csv_filename"),
        data.get("max_flexion", 0),
        data.get("max_extension", 0),
        data.get("max_roll_left", 0),
        data.get("max_roll_right", 0),
        data.get("avg_pitch", 0),
        data.get("avg_roll", 0),
        data.get("total_samples", 0),
        data.get("doctor_notes", ""),
        data.get("status", "completed"),
        json.dumps(data.get("events", []))
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def update_session_notes(session_id, notes):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET doctor_notes = ? WHERE id = ?", (notes, session_id))
    conn.commit()
    conn.close()
    return True
