"""
ble_engine.py — Động cơ xử lý tín hiệu IMU & BLE lâm sàng
Tích hợp 100% thuật toán từ file head_angle_monitor_ble__final_fixed.py:
  - CRC8 verification & Fast parsing
  - Adaptive Madgwick filter với Zero Velocity Update (ZUPT)
  - Quaternions & Relative Euler angles (Pitch: Cúi/Ngửa, Roll: Nghiêng T/P)
  - BLEReader tối ưu hàng đợi RAM bất đồng bộ
  - Cân chỉnh tĩnh (Calibration) & Bù trôi Zero (Tare on-the-fly)
  - Bộ ghi CSV đa luồng không nghẽn giao diện (Batch CSV Writing)
  - Bộ giả lập cơ sinh học cổ (Biomechanical Simulator) khi chưa bật cảm biến
"""

import asyncio
import threading
import time
import math
import os
import queue
import numpy as np
import pandas as pd
from datetime import datetime
from collections import deque

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH LÂM SÀNG & KỸ THUẬT
# ══════════════════════════════════════════════════════════════
BLE_DEVICE_NAME     = "MPU6050_HEAD"
SERVICE_UUID        = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
CHAR_UUID_TX        = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify: ESP32 → PC
CHAR_UUID_RX        = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write:  PC → ESP32

SAMPLE_RATE_HZ      = 50
CALIB_SECONDS       = 3
BATCH_SIZE          = 50
LERP_ALPHA          = 0.25

# Ngưỡng lâm sàng CROM (Cervical Range of Motion)
CLINICAL_PITCH_MAX  =  15.0  # Ngưỡng an toàn cúi đầu
CLINICAL_PITCH_MIN  = -15.0  # Ngưỡng an toàn ngửa đầu
CLINICAL_ROLL_MAX   =  10.0  # Ngưỡng nghiêng phải
CLINICAL_ROLL_MIN   = -10.0  # Ngưỡng nghiêng trái

# Adaptive Madgwick
BETA_MIN            = 0.02
BETA_MAX            = 0.08
ACCEL_THR           = 0.08
ZERO_VEL_THR        = 0.002


# ══════════════════════════════════════════════════════════════
# CRC8 & PARSING
# ══════════════════════════════════════════════════════════════
def crc8(data: str) -> int:
    crc = 0x00
    for b in data.encode("ascii"):
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) if (crc & 0x80) else (crc << 1)
        crc &= 0xFF
    return crc


def validate_and_parse(line: str):
    parts = line.split(",")
    if len(parts) != 17:
        return None
    try:
        payload      = ",".join(parts[:16])
        expected_crc = int(parts[16])
        actual_crc   = crc8(payload)
        if expected_crc != actual_crc:
            return None
        return list(map(float, parts[1:16])) + [float(parts[0])]
    except (ValueError, IndexError):
        return None


# ══════════════════════════════════════════════════════════════
# ADAPTIVE MADGWICK FILTER
# ══════════════════════════════════════════════════════════════
class AdaptiveMadgwick:
    def __init__(self, freq=50.0, beta_min=BETA_MIN, beta_max=BETA_MAX,
                 accel_thr=ACCEL_THR, zupt_thr=ZERO_VEL_THR):
        self.freq     = freq
        self.bmin     = beta_min
        self.bmax     = beta_max
        self.athr     = accel_thr
        self.zupt_thr = zupt_thr
        self.q        = [1.0, 0.0, 0.0, 0.0]
        self.beta     = beta_max

    def _adapt_beta(self, ax, ay, az):
        dev       = abs(math.sqrt(ax*ax + ay*ay + az*az) - 1.0)
        alpha     = min(dev / self.athr, 1.0)
        self.beta = self.bmin + (1.0 - alpha) * (self.bmax - self.bmin)

    def update(self, gx, gy, gz, ax, ay, az, dt=None):
        if dt is None:
            dt = 1.0 / self.freq
        self._adapt_beta(ax, ay, az)
        beta = self.beta
        q0, q1, q2, q3 = self.q

        gyro_mag = math.sqrt(gx*gx + gy*gy + gz*gz)
        if gyro_mag < self.zupt_thr:
            gx = gy = gz = 0.0

        n = math.sqrt(ax*ax + ay*ay + az*az)
        if n < 1e-6:
            q0 += 0.5 * (-q1*gx - q2*gy - q3*gz) * dt
            q1 += 0.5 * ( q0*gx + q2*gz - q3*gy) * dt
            q2 += 0.5 * ( q0*gy - q1*gz + q3*gx) * dt
            q3 += 0.5 * ( q0*gz + q1*gy - q2*gx) * dt
        else:
            ax /= n; ay /= n; az /= n
            q0q0 = q0*q0; q1q1 = q1*q1; q2q2 = q2*q2; q3q3 = q3*q3
            s0 = 4*q0*q2q2 + 2*q2*ax + 4*q0*q1q1 - 2*q1*ay
            s1 = (4*q1*q3q3 - 2*q3*ax + 4*q0q0*q1 - 2*q0*ay
                  - 4*q1 + 8*q1*q1q1 + 8*q1*q2q2 + 4*q1*az)
            s2 = (4*q0q0*q2 + 2*q0*ax + 4*q2*q3q3 - 2*q3*ay
                  - 4*q2 + 8*q2*q1q1 + 8*q2*q2q2 + 4*q2*az)
            s3 = 4*q1q1*q3 - 2*q1*ax + 4*q2q2*q3 - 2*q2*ay
            sn = math.sqrt(s0*s0 + s1*s1 + s2*s2 + s3*s3)
            if sn > 1e-6:
                s0 /= sn; s1 /= sn; s2 /= sn; s3 /= sn
            q0 += (0.5*(-q1*gx - q2*gy - q3*gz) - beta*s0) * dt
            q1 += (0.5*( q0*gx + q2*gz - q3*gy) - beta*s1) * dt
            q2 += (0.5*( q0*gy - q1*gz + q3*gx) - beta*s2) * dt
            q3 += (0.5*( q0*gz + q1*gy - q2*gx) - beta*s3) * dt

        qn = math.sqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3)
        self.q = [q0/qn, q1/qn, q2/qn, q3/qn]
        return self.q[:]

    def get_q(self):   return self.q[:]
    def reset(self):   self.q = [1.0, 0.0, 0.0, 0.0]


# ══════════════════════════════════════════════════════════════
# QUATERNION & EULER UTILITIES
# ══════════════════════════════════════════════════════════════
def q_inv(q):
    return (q[0], -q[1], -q[2], -q[3])

def q_mul(q, r):
    q0,q1,q2,q3 = q; r0,r1,r2,r3 = r
    return (
        q0*r0 - q1*r1 - q2*r2 - q3*r3,
        q0*r1 + q1*r0 + q2*r3 - q3*r2,
        q0*r2 - q1*r3 + q2*r0 + q3*r1,
        q0*r3 + q1*r2 - q2*r1 + q3*r0,
    )

def q_to_euler(q):
    q0,q1,q2,q3 = q
    pitch = math.asin(max(-1.0, min(1.0, 2*(q0*q2 - q3*q1)))) * 180.0/math.pi
    roll  = math.atan2(2*(q0*q1 + q2*q3), 1 - 2*(q1*q1 + q2*q2)) * 180.0/math.pi
    return pitch, roll

def relative_pitch_roll(q_base, q_head):
    q_rel = q_mul(q_inv(q_base), q_head)
    if q_rel[0] < 0:
        q_rel = (-q_rel[0], -q_rel[1], -q_rel[2], -q_rel[3])
    return q_to_euler(q_rel)


# ══════════════════════════════════════════════════════════════
# SENSOR PIPELINE
# ══════════════════════════════════════════════════════════════
class SensorPipeline:
    BIAS_ALPHA = 2e-4

    def __init__(self, freq=50.0):
        self.madgwick   = AdaptiveMadgwick(freq=freq)
        self.gyro_bias  = [0.0, 0.0, 0.0]
        self.last_ts_us = None

    def process(self, gx, gy, gz, ax, ay, az, ts_us: float):
        gx -= self.gyro_bias[0]
        gy -= self.gyro_bias[1]
        gz -= self.gyro_bias[2]

        gyro_mag = math.sqrt(gx*gx + gy*gy + gz*gz)
        if gyro_mag < ZERO_VEL_THR:
            a = self.BIAS_ALPHA
            self.gyro_bias[0] += a * gx
            self.gyro_bias[1] += a * gy
            self.gyro_bias[2] += a * gz

        dt = None
        if self.last_ts_us is not None:
            raw_dt = (ts_us - self.last_ts_us) * 1e-6
            if 0.005 <= raw_dt <= 0.1:
                dt = raw_dt
        self.last_ts_us = ts_us
        return self.madgwick.update(gx, gy, gz, ax, ay, az, dt)

    def get_q(self):   return self.madgwick.get_q()
    def reset(self):
        self.madgwick.reset()
        self.last_ts_us = None


# ══════════════════════════════════════════════════════════════
# CALIBRATION
# ══════════════════════════════════════════════════════════════
def calibrate_sensors(p1: SensorPipeline, p2: SensorPipeline,
                      dq: queue.Queue, calib_s: float, progress_callback=None, stop_event=None):
    n = int(calib_s * SAMPLE_RATE_HZ)
    samples = []
    timeout_per_sample = 5.0  # Tối đa 5 giây chờ mẫu từ cảm biến
    for i in range(n):
        t0 = time.time()
        while dq.empty():
            if stop_event and stop_event.is_set():
                return None, None
            if time.time() - t0 > timeout_per_sample:
                raise TimeoutError("Quá thời gian chờ dữ liệu từ cảm biến trong quá trình hiệu chuẩn (5s).")
            time.sleep(0.002)
        samples.append(dq.get())
        if progress_callback and (i % 10 == 0 or i == n - 1):
            pct = int((i + 1) / n * 100)
            progress_callback(pct, i + 1, n)

    if len(samples) < n:
        return None, None

    arr = np.array(samples)
    p1.gyro_bias = np.mean(arr[:, 4:7], axis=0)
    p2.gyro_bias = np.mean(arr[:, 10:13], axis=0)

    p1.reset(); p2.reset()

    CONVERGE_TOL = 0.0005
    MAX_ROUNDS   = 15
    for rnd in range(MAX_ROUNDS):
        q1_prev = p1.get_q().copy()
        q2_prev = p2.get_q().copy()
        for v in samples:
            p1.process(v[4],v[5],v[6], v[1],v[2],v[3], v[0])
            p2.process(v[10],v[11],v[12], v[7],v[8],v[9], v[0])
        d1 = np.linalg.norm(np.array(p1.get_q()) - np.array(q1_prev))
        d2 = np.linalg.norm(np.array(p2.get_q()) - np.array(q2_prev))
        if d1 < CONVERGE_TOL and d2 < CONVERGE_TOL:
            break

    return p1.get_q(), p2.get_q()


# ══════════════════════════════════════════════════════════════
# BATCH CSV RECORDER (ASYNCHRONOUS THREAD)
# ══════════════════════════════════════════════════════════════
CSV_HEADER = [
    "real_time", "timestamp_s", "seq",
    "rel_pitch_deg", "rel_roll_deg", "avg_pitch_deg", "avg_roll_deg",
    "accel_x_1", "accel_y_1", "accel_z_1", "gyro_x_1", "gyro_y_1", "gyro_z_1",
    "accel_x_2", "accel_y_2", "accel_z_2", "gyro_x_2", "gyro_y_2", "gyro_z_2",
    "q1w", "q1x", "q1y", "q1z", "q2w", "q2x", "q2y", "q2z",
    "temp1_C", "temp2_C", "madgwick_beta1", "madgwick_beta2"
]

class AsyncCSVWriter:
    def __init__(self, filepath):
        self.filepath = filepath
        self.buffer = []
        self.write_queue = queue.Queue()
        self.total_saved = 0
        self._thread = None
        self._init_file()
        self._start()

    def _init_file(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        pd.DataFrame(columns=CSV_HEADER).to_csv(self.filepath, index=False)

    def _start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            batch = self.write_queue.get()
            if batch is None:
                self.write_queue.task_done()
                break
            try:
                df = pd.DataFrame(batch)
                df.to_csv(self.filepath, mode='a', header=False, index=False)
            except Exception as e:
                print(f"[AsyncCSVWriter Error] {e}")
            finally:
                self.write_queue.task_done()

    def add_row(self, row_dict):
        self.buffer.append(row_dict)
        if len(self.buffer) >= BATCH_SIZE:
            batch = self.buffer
            self.buffer = []
            self.total_saved += len(batch)
            self.write_queue.put(batch)

    def close(self):
        if self.buffer:
            batch = self.buffer
            self.buffer = []
            self.total_saved += len(batch)
            self.write_queue.put(batch)
        self.write_queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


# ══════════════════════════════════════════════════════════════
# BLE HARDWARE READER
# ══════════════════════════════════════════════════════════════
class BLEReader:
    def __init__(self, data_queue: queue.Queue):
        self.dq         = data_queue
        self.ready      = threading.Event()
        self.error      = None
        self.dropped    = 0
        self.crc_errors = 0
        self.last_seq   = None
        self.seq_gaps   = 0
        self._running   = False
        self._thread    = None
        self._loop      = None
        self._client    = None
        self._buf       = ""

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ble_main())
        finally:
            self._loop.close()

    async def _scan_device(self) -> str | None:
        try:
            device = await BleakScanner.find_device_by_name(BLE_DEVICE_NAME, timeout=8.0)
            if device:
                return device.address
            return None
        except Exception as e:
            self.error = str(e)
            return None

    def _notify_handler(self, sender, data: bytearray):
        self._buf += data.decode("utf-8", "ignore")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if not line or line.startswith(("READY:", "HEADER:", "WARN:")):
                if line.startswith("READY:"):
                    self.ready.set()
                continue

            parsed = validate_and_parse(line)
            if parsed is None:
                self.crc_errors += 1
                continue

            seq = int(parsed[15])
            if self.last_seq is not None:
                if seq > self.last_seq:
                    gap = seq - self.last_seq - 1
                    if gap > 0:
                        self.seq_gaps += gap
            self.last_seq = seq

            if self.dq.full():
                self.dropped += 1
                try:
                    self.dq.get_nowait()
                except queue.Empty:
                    pass
            try:
                self.dq.put_nowait(parsed)
            except queue.Full:
                self.dropped += 1

    async def _ble_main(self):
        address = await self._scan_device()
        if not address:
            self.error = f"Không tìm thấy thiết bị BLE '{BLE_DEVICE_NAME}'"
            self.ready.set()
            return

        try:
            client = BleakClient(address)
            self._client = client
            await client.connect()
            await client.start_notify(CHAR_UUID_TX, self._notify_handler)
            self.ready.set()

            while self._running and client.is_connected:
                await asyncio.sleep(0.1)

        except Exception as e:
            self.error = str(e)
            self.ready.set()
        finally:
            try:
                if self._client and self._client.is_connected:
                    await self._client.stop_notify(CHAR_UUID_TX)
                    await self._client.disconnect()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════
# BIOMECHANICAL SIMULATION GENERATOR (DEMO MODE)
# ══════════════════════════════════════════════════════════════
class BiomechanicalSimulator:
    """
    Tạo tín hiệu giả lập cơ sinh học đốt sống cổ có độ chân thực cao:
    - Mô phỏng chu kỳ Cúi / Ngửa (Flexion / Extension: -18° đến +25°)
    - Mô phỏng chu kỳ Nghiêng Trái / Phải (Lateral Bending: -12° đến +14°)
    - Nhiễu rung cơ sinh học thực tế (micro-tremor 8-12Hz)
    - Tương thích 100% định dạng mảng 16 phần tử của ESP32 MPU6050
    """
    def __init__(self, data_queue: queue.Queue):
        self.dq = data_queue
        self._running = False
        self._thread = None
        self.ready = threading.Event()
        self.error = None
        self.dropped = 0
        self.crc_errors = 0
        self.seq_gaps = 0

    def start(self):
        self._running = True
        self.ready.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        seq = 0
        t0 = time.time()
        while self._running:
            now = time.time()
            t = now - t0
            ts_us = int(now * 1e6)

            # Mô phỏng góc cổ thay đổi theo chu kỳ bài tập lâm sàng
            # Giai đoạn 1: Giữ thẳng đầu (0s - 4s)
            # Giai đoạn 2: Cúi đầu dần (+22°) rồi về 0
            # Giai đoạn 3: Ngửa đầu dần (-16°) rồi về 0
            # Giai đoạn 4: Nghiêng phải (+12°) rồi sang trái (-10°)
            cycle = t % 24.0
            if cycle < 4.0:
                target_pitch = 0.0
                target_roll  = 0.0
            elif cycle < 9.0:
                p = (cycle - 4.0) / 5.0
                target_pitch = 22.0 * math.sin(p * math.pi)
                target_roll  = 1.0 * math.sin(p * math.pi * 2)
            elif cycle < 14.0:
                p = (cycle - 9.0) / 5.0
                target_pitch = -16.0 * math.sin(p * math.pi)
                target_roll  = -1.5 * math.sin(p * math.pi)
            elif cycle < 19.0:
                p = (cycle - 14.0) / 5.0
                target_pitch = 2.0 * math.sin(p * math.pi)
                target_roll  = 12.0 * math.sin(p * math.pi)
            else:
                p = (cycle - 19.0) / 5.0
                target_pitch = -1.0 * math.sin(p * math.pi)
                target_roll  = -10.0 * math.sin(p * math.pi)

            # Thêm nhiễu sinh lý
            noise_pitch = 0.25 * math.sin(t * 18.0) + np.random.normal(0, 0.05)
            noise_roll  = 0.20 * math.sin(t * 22.0) + np.random.normal(0, 0.05)
            pitch_deg = target_pitch + noise_pitch
            roll_deg  = target_roll + noise_roll

            # Giả lập gia tốc trọng trường khi nghiêng
            pr = math.radians(pitch_deg)
            rr = math.radians(roll_deg)
            
            # Cảm biến 1 (T1-T3 cố định trên lưng): dao động rất ít
            ax1 = 0.05 * math.sin(pr) + np.random.normal(0, 0.01)
            ay1 = 0.05 * math.sin(rr) + np.random.normal(0, 0.01)
            az1 = 0.99 + np.random.normal(0, 0.01)
            gx1 = np.random.normal(0, 0.002)
            gy1 = np.random.normal(0, 0.002)
            gz1 = np.random.normal(0, 0.002)

            # Cảm biến 2 (Chỏm đầu): nghiêng theo target_pitch và target_roll
            ax2 = math.sin(pr) + np.random.normal(0, 0.01)
            ay2 = math.sin(rr) + np.random.normal(0, 0.01)
            az2 = math.cos(pr) * math.cos(rr) + np.random.normal(0, 0.01)
            
            # Vận tốc góc xấp xỉ đạo hàm
            gx2 = 0.15 * math.cos(t * 1.2) + np.random.normal(0, 0.005)
            gy2 = 0.12 * math.cos(t * 1.5) + np.random.normal(0, 0.005)
            gz2 = np.random.normal(0, 0.003)

            T1 = 33.2 + 0.1 * math.sin(t * 0.1)
            T2 = 34.5 + 0.1 * math.cos(t * 0.1)

            # Khung 16 phần tử theo định dạng validate_and_parse
            # [ts_us, ax1, ay1, az1, gx1, gy1, gz1, ax2, ay2, az2, gx2, gy2, gz2, T1, T2, seq]
            sample = [ts_us, ax1, ay1, az1, gx1, gy1, gz1, ax2, ay2, az2, gx2, gy2, gz2, T1, T2, float(seq)]
            
            if not self.dq.full():
                self.dq.put(sample)
            seq = (seq + 1) % 65536
            time.sleep(1.0 / SAMPLE_RATE_HZ)


# ══════════════════════════════════════════════════════════════
# MAIN CLINICAL MEASUREMENT SESSION CONTROLLER
# ══════════════════════════════════════════════════════════════
class ClinicalSessionEngine:
    def __init__(self, socketio, recordings_dir):
        self.socketio = socketio
        self.recordings_dir = recordings_dir
        self.mode = "sim"             # "ble" hoặc "sim"
        self.state = "idle"           # "idle", "connecting", "calibrating", "measuring", "error"
        self.status_msg = "Sẵn sàng — Nhấn 'Bắt đầu đo' để tiến hành thăm khám."
        self.stop_event = threading.Event()
        self.active_thread = None
        self.current_session_info = {}
        
        # Tare reference quaternions (có thể reset giữa phiên)
        self.qr1 = [1.0, 0.0, 0.0, 0.0]
        self.qr2 = [1.0, 0.0, 0.0, 0.0]
        self.pipe_t13 = None
        self.pipe_head = None
        self.events_log = []

    def set_mode(self, mode):
        if mode in ("ble", "sim"):
            self.mode = mode

    def emit_state(self, state, message):
        self.state = state
        self.status_msg = message
        self.socketio.emit("status_change", {
            "state": state,
            "message": message,
            "mode": self.mode
        })

    def tare(self):
        """Đặt lại góc 0° ngay tức thì theo vị trí đầu hiện tại."""
        if self.pipe_t13 and self.pipe_head:
            self.qr1 = self.pipe_t13.get_q()
            self.qr2 = self.pipe_head.get_q()
            self.socketio.emit("tare_acknowledged", {"message": "Đã cân bằng lại góc 0° (Tare)."})
            return True
        return False

    def mark_event(self, label="Đau / Cột mốc lâm sàng"):
        timestamp_s = round(time.time() - self.current_session_info.get("start_ts", time.time()), 2)
        event_item = {
            "time_s": timestamp_s,
            "label": label,
            "pitch": self.current_session_info.get("last_pitch", 0.0),
            "roll": self.current_session_info.get("last_roll", 0.0)
        }
        self.events_log.append(event_item)
        self.socketio.emit("event_marked", event_item)

    def start_session(self, patient_data, duration_limit=0):
        # Nếu luồng trước đang chạy, ngắt và chờ tối đa 1 giây để dọn dẹp
        if self.active_thread and self.active_thread.is_alive():
            self.stop_event.set()
            self.active_thread.join(timeout=1.0)

        self.state = "idle"
        self.stop_event.clear()
        self.events_log = []
        self.active_thread = threading.Thread(
            target=self._session_worker,
            args=(patient_data, duration_limit),
            daemon=True
        )
        self.active_thread.start()
        return True

    def stop_session(self):
        self.stop_event.set()
        # Đưa trạng thái về idle ngay lập tức để mở khóa nút bấm trên giao diện
        self.emit_state("idle", "Đã dừng phiên đo.")

    def _session_worker(self, patient_data, duration_limit):
        from .database import create_session

        sid = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"head_angle_{sid}.csv"
        csv_filepath = os.path.join(self.recordings_dir, csv_filename)
        
        csv_writer = AsyncCSVWriter(csv_filepath)
        dq = queue.Queue(maxsize=1000)
        reader = None

        self.pipe_t13  = SensorPipeline(freq=SAMPLE_RATE_HZ)
        self.pipe_head = SensorPipeline(freq=SAMPLE_RATE_HZ)

        # Thống kê lâm sàng
        max_flexion    = 0.0  # Pitch dương lớn nhất
        max_extension  = 0.0  # Pitch âm lớn nhất (tuyệt đối)
        max_roll_left  = 0.0  # Roll âm lớn nhất (tuyệt đối)
        max_roll_right = 0.0  # Roll dương lớn nhất
        pitch_sum      = 0.0
        roll_sum       = 0.0
        n_samples      = 0

        self.current_session_info = {
            "start_ts": time.time(),
            "patient": patient_data,
            "csv_filename": csv_filename,
            "last_pitch": 0.0,
            "last_roll": 0.0
        }

        try:
            # 1. KẾT NỐI
            if self.mode == "ble":
                self.emit_state("connecting", f"Đang quét & kết nối cảm biến BLE '{BLE_DEVICE_NAME}'...")
                reader = BLEReader(dq)
                reader.start()
                connected = reader.ready.wait(timeout=12.0)
                if not connected or reader.error:
                    err = reader.error or "Không tìm thấy thiết bị BLE trong 12 giây."
                    self.emit_state("error", f"Lỗi BLE: {err}. Bạn có thể chuyển sang Chế độ Giả lập (Demo) để trải nghiệm.")
                    return
            else:
                self.emit_state("connecting", "Đang khởi động Chế độ Giả Lập Cơ Sinh Học Cổ (Demo Mode)...")
                reader = BiomechanicalSimulator(dq)
                reader.start()
                time.sleep(0.5)

            if self.stop_event.is_set():
                return

            # 2. HIỆU CHUẨN (CALIBRATION)
            self.emit_state("calibrating", f"Đã kết nối. Bệnh nhân giữ thẳng đầu trong {CALIB_SECONDS} giây để hiệu chỉnh 0°...")
            def calib_cb(pct, cur, total):
                self.socketio.emit("calibration_progress", {"percent": int(pct), "current": int(cur), "total": int(total)})

            self.qr1, self.qr2 = calibrate_sensors(
                self.pipe_t13, self.pipe_head, dq, CALIB_SECONDS, calib_cb, self.stop_event
            )

            if self.stop_event.is_set() or self.qr1 is None or self.qr2 is None:
                return

            # 3. VÒNG ĐO THỜI GIAN THỰC (REALTIME MEASUREMENT)
            self.emit_state("measuring", "Đang ghi nhận tín hiệu thời gian thực.")
            ui_pitch = [0.0]
            ui_roll  = [0.0]
            t_start  = None
            last_emit = 0.0
            EMIT_INTERVAL = 1.0 / 25   # Cập nhật 25Hz mượt mà cho giao diện

            start_clock = time.time()

            while not self.stop_event.is_set():
                if duration_limit > 0 and (time.time() - start_clock >= duration_limit):
                    break

                try:
                    v = dq.get(timeout=0.2)
                except queue.Empty:
                    continue

                ts_us = v[0]
                ax1, ay1, az1 = v[1], v[2], v[3]
                gx1, gy1, gz1 = v[4], v[5], v[6]
                ax2, ay2, az2 = v[7], v[8], v[9]
                gx2, gy2, gz2 = v[10], v[11], v[12]
                T1, T2        = v[13], v[14]
                seq           = int(v[15])

                q1 = self.pipe_t13.process(gx1, gy1, gz1, ax1, ay1, az1, ts_us)
                q2 = self.pipe_head.process(gx2, gy2, gz2, ax2, ay2, az2, ts_us)

                q1_adj = q_mul(q_inv(self.qr1), q1)
                q2_adj = q_mul(q_inv(self.qr2), q2)
                rp, rr = relative_pitch_roll(q1_adj, q2_adj)

                tn = ts_us * 1e-6
                if t_start is None:
                    t_start = tn

                ui_pitch[0] += LERP_ALPHA * (rp - ui_pitch[0])
                ui_roll[0]  += LERP_ALPHA * (rr - ui_roll[0])

                p_cur = ui_pitch[0]
                r_cur = ui_roll[0]
                self.current_session_info["last_pitch"] = round(p_cur, 2)
                self.current_session_info["last_roll"]  = round(r_cur, 2)

                # Cập nhật biên độ ROM
                if p_cur > max_flexion:
                    max_flexion = p_cur
                if p_cur < -max_extension:
                    max_extension = abs(p_cur)

                if r_cur > max_roll_right:
                    max_roll_right = r_cur
                if r_cur < -max_roll_left:
                    max_roll_left = abs(r_cur)

                pitch_sum += rp
                roll_sum  += rr
                n_samples += 1
                avg_p = pitch_sum / n_samples
                avg_r = roll_sum  / n_samples

                # Lưu vào CSV batch
                csv_writer.add_row({
                    "real_time"     : datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "timestamp_s"   : round(tn, 4),
                    "seq"           : seq,
                    "rel_pitch_deg" : round(rp, 3),
                    "rel_roll_deg"  : round(rr, 3),
                    "avg_pitch_deg" : round(avg_p, 3),
                    "avg_roll_deg"  : round(avg_r, 3),
                    "accel_x_1": round(ax1, 5), "accel_y_1": round(ay1, 5), "accel_z_1": round(az1, 5),
                    "gyro_x_1" : round(gx1, 5), "gyro_y_1" : round(gy1, 5), "gyro_z_1" : round(gz1, 5),
                    "accel_x_2": round(ax2, 5), "accel_y_2": round(ay2, 5), "accel_z_2": round(az2, 5),
                    "gyro_x_2" : round(gx2, 5), "gyro_y_2" : round(gy2, 5), "gyro_z_2" : round(gz2, 5),
                    "q1w": round(q1[0],5), "q1x": round(q1[1],5),
                    "q1y": round(q1[2],5), "q1z": round(q1[3],5),
                    "q2w": round(q2[0],5), "q2x": round(q2[1],5),
                    "q2y": round(q2[2],5), "q2z": round(q2[3],5),
                    "temp1_C"       : round(T1, 2),
                    "temp2_C"       : round(T2, 2),
                    "madgwick_beta1": round(self.pipe_t13.madgwick.beta, 4),
                    "madgwick_beta2": round(self.pipe_head.madgwick.beta, 4),
                })

                now_m = time.monotonic()
                if now_m - last_emit >= EMIT_INTERVAL:
                    last_emit = now_m
                    elapsed_s = round(time.time() - start_clock, 1)

                    # Trạng thái cảnh báo CROM (ép kiểu bool chuẩn của Python để tránh lỗi JSON serializable từ np.bool_)
                    pitch_warn = bool(abs(p_cur) > CLINICAL_PITCH_MAX)
                    roll_warn  = bool(abs(r_cur) > CLINICAL_ROLL_MAX)

                    self.socketio.emit("telemetry_update", {
                        "elapsed_s"     : float(elapsed_s),
                        "pitch"         : float(round(p_cur, 2)),
                        "roll"          : float(round(r_cur, 2)),
                        "avg_pitch"     : float(round(avg_p, 2)),
                        "avg_roll"      : float(round(avg_r, 2)),
                        "max_flexion"   : float(round(max_flexion, 1)),
                        "max_extension" : float(round(max_extension, 1)),
                        "max_roll_left" : float(round(max_roll_left, 1)),
                        "max_roll_right": float(round(max_roll_right, 1)),
                        "pitch_warn"    : pitch_warn,
                        "roll_warn"     : roll_warn,
                        "dropped"       : int(reader.dropped) if reader else 0,
                        "crc_errors"    : int(reader.crc_errors) if reader else 0,
                        "seq_gaps"      : int(reader.seq_gaps) if reader else 0,
                        "temp_head"     : float(round(T2, 1)),
                        "temp_t13"      : float(round(T1, 1)),
                        "sample_rate"   : int(SAMPLE_RATE_HZ)
                    })

        except Exception as e:
            print(f"[ClinicalSessionEngine Lỗi Worker] {e}")
            self.emit_state("error", f"Đã dừng phiên đo do phát sinh lỗi: {e}")

        finally:
            if reader:
                try:
                    reader.stop()
                except Exception as e:
                    print(f"[Reader stop error] {e}")
            try:
                csv_writer.close()
            except Exception as e:
                print(f"[CSVWriter close error] {e}")

            # 4. TỔNG KẾT VÀ GHI VÀO DATABASE
            duration_s = round(time.time() - self.current_session_info.get("start_ts", time.time()), 1)
            session_id = None
            try:
                if n_samples > 10:
                    final_avg_pitch = float(round(pitch_sum / n_samples, 2))
                    final_avg_roll  = float(round(roll_sum / n_samples, 2))
                    patient = self.current_session_info.get("patient", {})
                    session_id = create_session({
                        "patient_id": patient.get("id"),
                        "patient_name": patient.get("name", "Bệnh nhân"),
                        "doctor_name": "BS. CKI Nguyễn Văn A",
                        "start_time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "duration_s": float(duration_s),
                        "csv_filename": csv_filename,
                        "max_flexion": float(round(max_flexion, 1)),
                        "max_extension": float(round(max_extension, 1)),
                        "max_roll_left": float(round(max_roll_left, 1)),
                        "max_roll_right": float(round(max_roll_right, 1)),
                        "avg_pitch": final_avg_pitch,
                        "avg_roll": final_avg_roll,
                        "total_samples": int(n_samples),
                        "doctor_notes": "Biên độ vận động khớp cổ cần được đối chiếu thêm với triệu chứng lâm sàng.",
                        "status": "completed",
                        "events": self.events_log
                    })
            except Exception as e:
                print(f"[DB Create Session Error] {e}")

            # Luôn luôn đưa trạng thái về idle sau khi dọn dẹp xong
            self.emit_state("idle", f"Phiên đo hoàn tất ({duration_s}s). Dữ liệu đã lưu vào {csv_filename}")
            try:
                self.socketio.emit("session_finished", {
                    "session_id": session_id,
                    "csv_filename": csv_filename,
                    "duration_s": float(duration_s),
                    "max_flexion": float(round(max_flexion, 1)),
                    "max_extension": float(round(max_extension, 1)),
                    "max_roll_left": float(round(max_roll_left, 1)),
                    "max_roll_right": float(round(max_roll_right, 1)),
                    "total_samples": int(n_samples)
                })
            except Exception as e:
                print(f"[Session Finished Emit Error] {e}")
