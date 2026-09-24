# HỆ THỐNG ĐO GÓC CÚI / NGHIÊNG ĐẦU LÂM SÀNG (CROM)
### DÀNH CHO BÁC SĨ & KỸ THUẬT VIÊN PHỤC HỒI CHỨC NĂNG

> **Kết hợp hoàn chỉnh:**
> - Bộ giao diện y tế tiêu chuẩn từ thư mục `Giao_Dien_Template` (Inter typography, Medical Palette, Responsive Dashboard, Interactive Anatomical Visualizer).
> - Thuật toán đo lường cơ sinh học chính xác 100% từ file `head_angle_monitor_ble__final_fixed.py` (Adaptive Madgwick, ZUPT, Quaternions, Asynchronous Fast BLE Receiver, Batch CSV Logging).

---

## 📁 Cấu Trúc Thư Mục `web_bac_si`

```
web_bac_si/
├── Mo_Phan_Mem.bat            # Tệp khởi chạy 1 chạm cho Bác sĩ (Tự mở trình duyệt http://localhost:5000)
├── Huong_Dan_Su_Dung.txt      # Hướng dẫn chi tiết bằng Tiếng Việt
├── README.md                  # Tài liệu kỹ thuật hệ thống
├── app.py                     # Máy chủ Web Flask & Socket.IO
├── database.db                # Cơ sở dữ liệu SQLite (Hồ sơ Bác sĩ, Bệnh nhân, Lịch sử phiên đo)
├── core/
│   ├── ble_engine.py          # Bộ xử lý tín hiệu IMU Madgwick, BLE Reader & Simulator giả lập
│   └── database.py            # ORM & truy vấn cơ sở dữ liệu SQLite
├── static/
│   ├── css/
│   │   └── medical_theme.css  # Bộ phong cách Y Tế chuẩn (Thẻ glass-panel, huy hiệu cảnh báo)
│   └── js/
│       ├── app.js             # Điều phối giao diện, chuyển Tab & Modal
│       ├── head_avatar.js     # Mô hình 2D giải phẫu đầu & đốt sống cổ (Cúi/Ngửa & Nghiêng T/P)
│       ├── tracking.js        # Đồ thị sóng 25Hz thời gian thực & telemetry
│       └── history.js         # Tra cứu lịch sử, phát lại đồ thị & xuất báo cáo
├── templates/
│   ├── index.html             # Giao diện chính (Dashboard, Phòng Khám, Lịch Sử)
│   └── print_report.html      # Phiếu kết quả khám bệnh nhân A4 chuẩn y khoa (in hoặc lưu PDF)
└── recordings/                # Toàn bộ tệp CSV đo đạc gốc (tương thích 100% định dạng cũ)
```

---

## 🚀 Cách Bác Sĩ Sử Dụng

### 1. Khởi động nhanh
Nhấp đúp chuột vào file **`Mo_Phan_Mem.bat`**. Trình duyệt sẽ tự động mở tại `http://localhost:5000`.

### 2. Hai chế độ vận hành linh hoạt
- **Cảm biến thật (BLE MPU6050_HEAD)**: Kết nối không dây với ESP32 và 2 cảm biến MPU6050 (T1-T3 và Chỏm đầu) ở tần số 50Hz.
- **Giả lập lâm sàng (Demo Mode)**: Cho phép bác sĩ thử nghiệm hoặc hội chẩn ngay cả khi không có phần cứng gắn trên người.

### 3. Quy trình đo khám
1. **Chọn bệnh nhân** từ danh sách hoặc bấm **`+ Thêm BN`**.
2. Nhấn **`▶ Bắt Đầu Đo`**: Thiết bị tự động cân bằng tĩnh trong 3 giây.
3. Bệnh nhân thực hiện các động tác:
   - Cúi đầu tối đa (Cervical Flexion)
   - Ngửa đầu tối đa (Cervical Extension)
   - Nghiêng đầu trái/phải (Lateral Bending)
4. Nếu bệnh nhân cảm thấy đau mỏi, bấm **`⚠ Đánh Dấu Điểm Đau`** để ghi lại cột mốc.
5. Khi hoàn thành bài tập, bấm **`■ Dừng & Lưu Phiên`**:
   - Dữ liệu được lưu tự động vào `recordings/head_angle_YYYYMMDD_HHMMSS.csv`.
   - Các chỉ số biên độ vận động (ROM), góc trung bình được lưu vào cơ sở dữ liệu.
6. Chuyển sang thẻ **Lịch Sử & Báo Cáo** để:
   - Xem lại đồ thị dao động toàn phiên.
   - Nhập nhận xét chẩn đoán của Bác sĩ.
   - Bấm **`In Phiếu Khám (A4)`** để in trực tiếp hoặc xuất tệp PDF gửi cho bệnh nhân.
