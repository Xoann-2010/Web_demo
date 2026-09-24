"""
app.py — Máy chủ Web Flask & SocketIO cho Hệ Thống Đo Góc Cổ Lâm Sàng (Dành Cho Bác Sĩ)
"""

import os
import sys

# Configure UTF-8 for console output on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

import json
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_socketio import SocketIO

# Đảm bảo đường dẫn import thư mục cục bộ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import (
    init_db, get_current_doctor, update_doctor,
    list_patients, get_patient, add_patient,
    list_sessions, get_session, update_session_notes
)
from core.ble_engine import (
    ClinicalSessionEngine, CLINICAL_PITCH_MIN, CLINICAL_PITCH_MAX,
    CLINICAL_ROLL_MIN, CLINICAL_ROLL_MAX
)

RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = 'cervical-spine-doctor-portal-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Khởi tạo SQLite DB
init_db()

# Khởi tạo Động cơ đo đạc lâm sàng
engine = ClinicalSessionEngine(socketio, RECORDINGS_DIR)


# ══════════════════════════════════════════════════════════════
# HTTP ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/')
def index():
    import time
    doctor = get_current_doctor()
    patients = list_patients()
    return render_template('index.html', doctor=doctor, patients=patients, v=int(time.time()))

@app.route('/api/status')
def api_status():
    doctor = get_current_doctor()
    return jsonify({
        "state": engine.state,
        "message": engine.status_msg,
        "mode": engine.mode,
        "doctor": doctor,
        "config": {
            "clinical_pitch_min": CLINICAL_PITCH_MIN,
            "clinical_pitch_max": CLINICAL_PITCH_MAX,
            "clinical_roll_min": CLINICAL_ROLL_MIN,
            "clinical_roll_max": CLINICAL_ROLL_MAX
        }
    })

@app.route('/api/doctor', methods=['GET', 'POST'])
def api_doctor():
    if request.method == 'POST':
        data = request.json or {}
        update_doctor(data)
        return jsonify({"success": True, "doctor": get_current_doctor()})
    return jsonify(get_current_doctor())

@app.route('/api/patients', methods=['GET', 'POST'])
def api_patients():
    if request.method == 'POST':
        data = request.json or {}
        if not data.get("name"):
            return jsonify({"error": "Tên bệnh nhân không được để trống"}), 400
        if not data.get("code"):
            # Tự sinh mã bệnh nhân
            count = len(list_patients()) + 1
            data["code"] = f"BN-{count:03d}"
        new_id = add_patient(data)
        return jsonify({"success": True, "id": new_id, "patient": get_patient(new_id)})
    return jsonify(list_patients())

@app.route('/api/patients/<int:patient_id>')
def api_patient_detail(patient_id):
    p = get_patient(patient_id)
    if not p:
        return jsonify({"error": "Không tìm thấy bệnh nhân"}), 404
    sessions = list_sessions(patient_id)
    return jsonify({"patient": p, "sessions": sessions})

@app.route('/api/sessions')
def api_sessions():
    patient_id = request.args.get('patient_id', type=int)
    sessions = list_sessions(patient_id)
    return jsonify(sessions)

@app.route('/api/sessions/<int:session_id>')
def api_session_detail(session_id):
    s = get_session(session_id)
    if not s:
        return jsonify({"error": "Không tìm thấy phiên đo"}), 404
    return jsonify(s)

@app.route('/api/sessions/<int:session_id>/data')
def api_session_data(session_id):
    s = get_session(session_id)
    if not s or not s.get("csv_filename"):
        return jsonify({"error": "Không tìm thấy dữ liệu phiên"}), 404

    csv_path = os.path.join(RECORDINGS_DIR, s["csv_filename"])
    if not os.path.exists(csv_path):
        return jsonify({"error": f"Không tìm thấy file: {s['csv_filename']}"}), 404

    try:
        df = pd.read_csv(csv_path)
        # Giảm tải dữ liệu nếu file quá lớn (>1500 dòng) để trình duyệt vẽ mượt
        total_rows = len(df)
        step = 1
        if total_rows > 1200:
            step = max(1, total_rows // 800)
            df = df.iloc[::step]

        # Kiểm tra cột có sẵn
        t_col = "timestamp_s" if "timestamp_s" in df.columns else df.columns[1]
        p_col = "rel_pitch_deg" if "rel_pitch_deg" in df.columns else df.columns[3]
        r_col = "rel_roll_deg" if "rel_roll_deg" in df.columns else df.columns[4]

        # Thời gian tương đối bắt đầu từ 0
        t_vals = (df[t_col] - df[t_col].iloc[0]).round(2).tolist()
        p_vals = df[p_col].round(2).tolist()
        r_vals = df[r_col].round(2).tolist()

        return jsonify({
            "times": t_vals,
            "pitch": p_vals,
            "roll": r_vals,
            "total_points": total_rows,
            "sampled_points": len(df)
        })
    except Exception as e:
        return jsonify({"error": f"Lỗi đọc dữ liệu CSV: {e}"}), 500

@app.route('/api/sessions/<int:session_id>/notes', methods=['POST'])
def api_update_notes(session_id):
    data = request.json or {}
    notes = data.get("doctor_notes", "")
    update_session_notes(session_id, notes)
    return jsonify({"success": True})

@app.route('/api/download_csv/<filename>')
def download_csv(filename):
    # Bảo mật: không cho directory traversal
    filename = os.path.basename(filename)
    path = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(path):
        return "Không tìm thấy file", 404
    return send_file(path, as_attachment=True, download_name=filename)

@app.route('/print_report/<int:session_id>')
def print_report(session_id):
    session = get_session(session_id)
    if not session:
        return "Không tìm thấy phiên đo", 404
    patient = get_patient(session["patient_id"]) if session.get("patient_id") else {}
    doctor = get_current_doctor()
    events = json.loads(session.get("events_json") or "[]")
    return render_template('print_report.html', session=session, patient=patient, doctor=doctor, events=events)


@app.route('/api/start_measurement', methods=['POST'])
def api_start_measurement():
    data = request.json or {}
    patient_id = data.get("patient_id")
    duration_limit = data.get("duration_limit", 0)
    patient = get_patient(patient_id) if patient_id else {
        "id": None, "name": data.get("patient_name", "Bệnh nhân thăm khám"), "code": "BN-TEMP"
    }
    success = engine.start_session(patient, duration_limit)
    return jsonify({"success": success, "state": engine.state, "message": engine.status_msg})

@app.route('/api/stop_measurement', methods=['POST'])
def api_stop_measurement():
    engine.stop_session()
    return jsonify({"success": True, "state": engine.state, "message": engine.status_msg})

@app.route('/api/reset_engine', methods=['POST'])
def api_reset_engine():
    engine.stop_session()
    engine.state = "idle"
    engine.status_msg = "Sẵn sàng — Nhấn 'Bắt đầu đo' để tiến hành thăm khám."
    engine.emit_state("idle", engine.status_msg)
    return jsonify({"success": True, "state": engine.state})


# ══════════════════════════════════════════════════════════════
# WEBSOCKET SOCKET.IO EVENTS
# ══════════════════════════════════════════════════════════════
@socketio.on('connect')
def handle_connect():
    doctor = get_current_doctor()
    if engine.active_thread and not engine.active_thread.is_alive():
        engine.state = "idle"
        engine.status_msg = "Sẵn sàng — Nhấn 'Bắt đầu đo' để tiến hành thăm khám."
    socketio.emit('config', {
        'clinical_pitch_min': CLINICAL_PITCH_MIN,
        'clinical_pitch_max': CLINICAL_PITCH_MAX,
        'clinical_roll_min':  CLINICAL_ROLL_MIN,
        'clinical_roll_max':  CLINICAL_ROLL_MAX,
        'mode': engine.mode,
        'state': engine.state,
        'message': engine.status_msg,
        'doctor': doctor
    })

@socketio.on('set_mode')
def handle_set_mode(data):
    mode = data.get("mode", "sim")
    engine.set_mode(mode)
    if engine.state not in ("calibrating", "measuring") or (engine.active_thread and not engine.active_thread.is_alive()):
        new_state = "idle"
    else:
        new_state = engine.state
    mode_name = "Cảm biến BLE Thật (MPU6050_HEAD)" if mode == "ble" else "Chế độ Giả Lập Lâm Sàng (Demo)"
    engine.emit_state(new_state, f"Đã chuyển sang: {mode_name}. Sẵn sàng thăm khám.")

@socketio.on('start_measurement')
def handle_start(data):
    data = data or {}
    patient_id = data.get("patient_id")
    duration_limit = data.get("duration_limit", 0)
    try:
        duration_limit = int(duration_limit)
    except (TypeError, ValueError):
        duration_limit = 0

    patient = get_patient(patient_id) if patient_id else {
        "id": None, "name": data.get("patient_name", "Bệnh nhân thăm khám"), "code": "BN-TEMP"
    }
    print(f"[SocketIO] Bắt đầu đo cho bệnh nhân: {patient.get('name')} (Mode: {engine.mode})")
    success = engine.start_session(patient, duration_limit)
    if not success:
        print(f"[SocketIO Cảnh báo] Không thể bắt đầu đo, trạng thái hiện tại: {engine.state}")
        socketio.emit("error_notification", {"message": f"Hệ thống đang ở trạng thái '{engine.state}', vui lòng dừng phiên trước hoặc đợi kết thúc."})

@socketio.on('stop_measurement')
def handle_stop():
    print("[SocketIO] Dừng phiên đo.")
    engine.stop_session()

@socketio.on('tare')
def handle_tare():
    engine.tare()

@socketio.on('mark_event')
def handle_mark_event(data):
    label = data.get("label", "Điểm đau / Cột mốc")
    engine.mark_event(label)


# ══════════════════════════════════════════════════════════════
# KHỞI CHẠY SERVER
# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("\n" + "="*60)
    print("  HE THONG DO GOC CO LAM SANG - DANH CHO BAC SI")
    print("  Giao_Dien_Template + head_angle_monitor_ble")
    print("  Dia chi Web: http://localhost:5000")
    print("="*60 + "\n")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
