/**
 * app.js — Điều phối giao diện người dùng, Điều hướng Tab & Quản lý Modal
 */

window.App = {
  socket: null,
  trackingManager: null,
  historyManager: null,

  init() {
    // 1. Khởi tạo Socket.IO
    this.socket = io(window.location.origin);

    // 2. Khởi tạo các module con
    this.trackingManager = new TrackingManager(this.socket);
    this.historyManager  = new HistoryManager();

    // 3. Lắng nghe cấu hình ban đầu
    this.socket.on('config', (cfg) => {
      if (this.trackingManager) {
        if (this.trackingManager.visualizer) {
          this.trackingManager.visualizer.setThresholds(
            cfg.clinical_pitch_min,
            cfg.clinical_pitch_max,
            cfg.clinical_roll_min,
            cfg.clinical_roll_max
          );
        }
        if (cfg.state) {
          this.trackingManager.handleStatusChange({
            state: cfg.state,
            message: cfg.message || '',
            mode: cfg.mode
          });
        }
        const modeSelect = document.getElementById('switch-mode-select');
        if (modeSelect && cfg.mode) {
          modeSelect.value = cfg.mode;
        }
      }
      if (cfg.doctor) {
        this.updateDoctorHeader(cfg.doctor);
      }
    });

    // 4. Gắn sự kiện giao diện
    this.bindEvents();
    this.startClock();
  },

  switchTab(tabId) {
    document.querySelectorAll('.view-tab').forEach((el) => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach((btn) => btn.classList.remove('active'));

    const targetView = document.getElementById(`view-${tabId}`);
    const targetNav  = document.getElementById(`tab-nav-${tabId}`);

    if (targetView) targetView.classList.remove('hidden');
    if (targetNav) targetNav.classList.add('active');

    // Nếu vào tab history, tải lại danh sách phiên mới nhất
    if (tabId === 'history' && this.historyManager) {
      this.historyManager.loadPatientsList();
    }
  },

  bindEvents() {
    // Tab switching
    document.getElementById('tab-nav-dashboard')?.addEventListener('click', () => this.switchTab('dashboard'));
    document.getElementById('tab-nav-tracking')?.addEventListener('click', () => this.switchTab('tracking'));
    document.getElementById('tab-nav-history')?.addEventListener('click', () => this.switchTab('history'));

    // Dashboard quick cards
    document.getElementById('card-quick-tracking')?.addEventListener('click', () => this.switchTab('tracking'));
    document.getElementById('card-quick-history')?.addEventListener('click', () => this.switchTab('history'));

    // Modal: Thêm bệnh nhân mới
    const modalPatient = document.getElementById('modal-add-patient');
    document.getElementById('btn-open-add-patient')?.addEventListener('click', () => {
      modalPatient?.classList.remove('hidden');
    });
    document.getElementById('btn-close-patient-modal')?.addEventListener('click', () => {
      modalPatient?.classList.add('hidden');
    });

    document.getElementById('form-add-patient')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        code: document.getElementById('new-patient-code').value.trim(),
        name: document.getElementById('new-patient-name').value.trim(),
        age: parseInt(document.getElementById('new-patient-age').value) || 0,
        gender: document.getElementById('new-patient-gender').value,
        diagnosis: document.getElementById('new-patient-diagnosis').value.trim(),
        phone: document.getElementById('new-patient-phone').value.trim(),
        notes: document.getElementById('new-patient-notes').value.trim()
      };

      try {
        const res = await fetch('/api/patients', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
          alert('✓ Đã thêm hồ sơ bệnh nhân thành công!');
          modalPatient?.classList.add('hidden');
          // Reload trang hoặc cập nhật danh sách chọn
          location.reload();
        } else {
          alert('Lỗi: ' + (result.error || 'Không thể tạo bệnh nhân'));
        }
      } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
      }
    });

    // Modal: Đổi thông tin Bác sĩ
    const modalDoctor = document.getElementById('modal-doctor-profile');
    document.getElementById('btn-open-doctor-modal')?.addEventListener('click', () => {
      modalDoctor?.classList.remove('hidden');
    });
    document.getElementById('btn-close-doctor-modal')?.addEventListener('click', () => {
      modalDoctor?.classList.add('hidden');
    });

    document.getElementById('form-doctor-profile')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById('doc-name').value.trim(),
        title: document.getElementById('doc-title').value.trim(),
        department: document.getElementById('doc-department').value.trim(),
        hospital: document.getElementById('doc-hospital').value.trim(),
        email: document.getElementById('doc-email').value.trim(),
        phone: document.getElementById('doc-phone').value.trim()
      };

      try {
        const res = await fetch('/api/doctor', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
          alert('✓ Đã cập nhật thông tin Bác sĩ!');
          this.updateDoctorHeader(result.doctor);
          modalDoctor?.classList.add('hidden');
        }
      } catch (err) {
        alert('Lỗi: ' + err.message);
      }
    });

    // Đóng modal tóm tắt phiên
    document.getElementById('btn-close-summary-modal')?.addEventListener('click', () => {
      document.getElementById('modal-session-summary')?.classList.add('hidden');
    });
  },

  updateDoctorHeader(doctor) {
    const elName = document.getElementById('header-doctor-name');
    const elDept = document.getElementById('header-doctor-dept');
    if (elName) elName.innerText = doctor.name || 'BS. Nguyễn Văn A';
    if (elDept) elDept.innerText = `${doctor.title || ''} • ${doctor.department || ''}`;
  },

  startClock() {
    const clockEl = document.getElementById('realtime-clock');
    if (!clockEl) return;
    const update = () => {
      const now = new Date();
      clockEl.innerText = now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
        '  ' + now.toLocaleDateString('vi-VN');
    };
    update();
    setInterval(update, 1000);
  }
};

document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
