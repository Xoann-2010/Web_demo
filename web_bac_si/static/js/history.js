/**
 * history.js — Quản lý Lịch sử Thăm khám & Phân tích Đồ thị Phiên đo
 */

class HistoryManager {
  constructor() {
    this.historyChart = null;
    this.selectedPatientId = null;
    this.selectedSessionId = null;

    this.initChart();
    this.bindEvents();
    this.loadPatientsList();
  }

  initChart() {
    const ctx = document.getElementById('history-full-chart');
    if (!ctx) return;

    this.historyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Pitch (Cúi / Ngửa)',
            data: [],
            borderColor: '#0ea5e9',
            backgroundColor: 'rgba(14, 165, 233, 0.08)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.2
          },
          {
            label: 'Roll (Nghiêng T / P)',
            data: [],
            borderColor: '#8b5cf6',
            backgroundColor: 'rgba(139, 92, 246, 0.08)',
            borderWidth: 1.8,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: {
            title: { display: true, text: 'Thời gian (giây)', color: '#94a3b8', font: { size: 11 } },
            grid: { color: 'rgba(226, 232, 240, 0.5)' },
            ticks: { maxTicksLimit: 12, color: '#94a3b8' }
          },
          y: {
            title: { display: true, text: 'Góc nghiêng (°)', color: '#94a3b8', font: { size: 11 } },
            grid: {
              color: (c) => (c.tick.value === 0 ? '#64748b' : 'rgba(226, 232, 240, 0.5)')
            },
            ticks: { color: '#64748b', font: { family: 'JetBrains Mono' } }
          }
        },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 14 } },
          tooltip: {
            backgroundColor: '#1e293b',
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y > 0 ? '+' : ''}${ctx.parsed.y.toFixed(1)}°`
            }
          }
        }
      }
    });
  }

  bindEvents() {
    // Tìm kiếm bệnh nhân
    document.getElementById('history-search-patient')?.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('.patient-item-btn').forEach((btn) => {
        const name = btn.dataset.name.toLowerCase();
        const code = btn.dataset.code.toLowerCase();
        btn.style.display = (name.includes(q) || code.includes(q)) ? 'block' : 'none';
      });
    });

    // Lưu ghi chú Bác sĩ
    document.getElementById('btn-save-doctor-notes')?.addEventListener('click', async () => {
      if (!this.selectedSessionId) return;
      const notes = document.getElementById('history-doctor-notes-input').value;
      try {
        const res = await fetch(`/api/sessions/${this.selectedSessionId}/notes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doctor_notes: notes })
        });
        if (res.ok) {
          alert('✓ Đã lưu nhận xét và chẩn đoán của Bác sĩ thành công!');
        }
      } catch (err) {
        alert('Lỗi lưu ghi chú: ' + err.message);
      }
    });
  }

  async loadPatientsList() {
    const container = document.getElementById('history-patient-list');
    if (!container) return;

    try {
      const res = await fetch('/api/patients');
      const patients = await res.json();
      container.innerHTML = '';

      if (patients.length === 0) {
        container.innerHTML = '<div class="text-xs text-gray-400 p-3 italic">Chưa có bệnh nhân nào.</div>';
        return;
      }

      patients.forEach((p, index) => {
        const btn = document.createElement('button');
        btn.className = 'patient-item-btn w-full p-2.5 text-left rounded-lg border text-sm font-medium transition-all mb-1.5 flex flex-col gap-0.5 ' +
          (index === 0 ? 'bg-sky-50 border-sky-300 text-sky-900 font-semibold' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50');
        btn.dataset.id = p.id;
        btn.dataset.name = p.name;
        btn.dataset.code = p.code;
        btn.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-bold text-gray-800">${p.name}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-mono">${p.code}</span>
          </div>
          <div class="text-[11px] text-gray-500 truncate">${p.age} tuổi | ${p.gender} | ${p.diagnosis || 'Chưa có chẩn đoán'}</div>
        `;

        btn.onclick = () => {
          document.querySelectorAll('.patient-item-btn').forEach(b => {
            b.className = 'patient-item-btn w-full p-2.5 text-left rounded-lg border text-sm font-medium transition-all mb-1.5 flex flex-col gap-0.5 bg-white border-gray-200 text-gray-700 hover:bg-gray-50';
          });
          btn.className = 'patient-item-btn w-full p-2.5 text-left rounded-lg border text-sm font-semibold transition-all mb-1.5 flex flex-col gap-0.5 bg-sky-50 border-sky-400 text-sky-900 shadow-sm';
          this.selectPatient(p.id);
        };

        container.appendChild(btn);
      });

      // Tự động chọn bệnh nhân đầu tiên
      this.selectPatient(patients[0].id);

    } catch (err) {
      console.error('Lỗi nạp bệnh nhân:', err);
    }
  }

  async selectPatient(patientId) {
    this.selectedPatientId = patientId;
    const sessionListContainer = document.getElementById('history-session-list');
    if (!sessionListContainer) return;

    sessionListContainer.innerHTML = '<div class="text-xs text-gray-400 p-3">Đang tải các phiên đo...</div>';

    try {
      const res = await fetch(`/api/sessions?patient_id=${patientId}`);
      const sessions = await res.json();
      sessionListContainer.innerHTML = '';

      if (sessions.length === 0) {
        sessionListContainer.innerHTML = '<div class="text-xs text-gray-400 p-3 italic">Bệnh nhân này chưa có phiên đo nào.</div>';
        this.clearSessionDetail();
        return;
      }

      sessions.forEach((s, index) => {
        const btn = document.createElement('button');
        btn.className = 'session-item-btn w-full p-3 text-left rounded-lg border text-xs transition-all mb-2 flex flex-col gap-1 ' +
          (index === 0 ? 'bg-emerald-50 border-emerald-400 text-emerald-950 font-semibold shadow-sm' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50');
        btn.dataset.id = s.id;
        btn.innerHTML = `
          <div class="flex items-center justify-between font-mono font-bold text-gray-800">
            <span>📅 ${s.start_time}</span>
            <span class="text-sky-600">${s.duration_s}s</span>
          </div>
          <div class="flex items-center gap-2 text-[11px] text-gray-600">
            <span>Cúi: <strong>+${s.max_flexion}°</strong></span>
            <span>Ngửa: <strong>-${s.max_extension}°</strong></span>
          </div>
        `;

        btn.onclick = () => {
          document.querySelectorAll('.session-item-btn').forEach(b => {
            b.className = 'session-item-btn w-full p-3 text-left rounded-lg border text-xs transition-all mb-2 flex flex-col gap-1 bg-white border-gray-200 text-gray-700 hover:bg-gray-50';
          });
          btn.className = 'session-item-btn w-full p-3 text-left rounded-lg border text-xs font-semibold transition-all mb-2 flex flex-col gap-1 bg-emerald-50 border-emerald-400 text-emerald-950 shadow-sm';
          this.loadSessionDetail(s.id);
        };

        sessionListContainer.appendChild(btn);
      });

      // Tự động nạp chi tiết phiên đầu tiên
      this.loadSessionDetail(sessions[0].id);

    } catch (err) {
      console.error('Lỗi nạp phiên đo:', err);
    }
  }

  async loadSessionDetail(sessionId) {
    this.selectedSessionId = sessionId;

    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      const s = await res.json();

      // Cập nhật thông tin tiêu đề
      document.getElementById('hist-detail-patient-name').innerText = s.patient_name || 'Bệnh nhân';
      document.getElementById('hist-detail-time').innerText = `${s.start_time} (Thời lượng: ${s.duration_s}s)`;

      // Cập nhật Thẻ ROM Thống kê
      document.getElementById('hist-max-flex').innerText   = `+${s.max_flexion.toFixed(1)}°`;
      document.getElementById('hist-max-ext').innerText    = `-${s.max_extension.toFixed(1)}°`;
      document.getElementById('hist-max-roll-l').innerText = `-${s.max_roll_left.toFixed(1)}°`;
      document.getElementById('hist-max-roll-r').innerText = `+${s.max_roll_right.toFixed(1)}°`;
      document.getElementById('hist-avg-pitch').innerText  = `${s.avg_pitch > 0 ? '+' : ''}${s.avg_pitch.toFixed(1)}°`;
      document.getElementById('hist-avg-roll').innerText   = `${s.avg_roll > 0 ? '+' : ''}${s.avg_roll.toFixed(1)}°`;

      // Cập nhật Ghi chú Bác sĩ
      document.getElementById('history-doctor-notes-input').value = s.doctor_notes || '';

      // Cập nhật Nút Tải CSV & In Báo Cáo
      const btnDownload = document.getElementById('btn-download-history-csv');
      if (btnDownload) {
        btnDownload.href = `/api/download_csv/${s.csv_filename}`;
      }

      const btnPrint = document.getElementById('btn-print-report');
      if (btnPrint) {
        btnPrint.onclick = () => {
          window.open(`/print_report/${s.id}`, '_blank');
        };
      }

      // Danh sách sự kiện
      const eventsBox = document.getElementById('hist-events-list');
      if (eventsBox) {
        const events = JSON.parse(s.events_json || '[]');
        if (events.length === 0) {
          eventsBox.innerHTML = '<div class="text-xs text-gray-400 italic">Không có điểm đau hoặc bất thường nào được đánh dấu.</div>';
        } else {
          eventsBox.innerHTML = events.map(e => `
            <div class="p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900 mb-1 flex justify-between">
              <span>⏱ ${e.time_s}s: <strong>${e.label}</strong></span>
              <span class="font-mono text-gray-600">Pitch: ${e.pitch}° | Roll: ${e.roll}°</span>
            </div>
          `).join('');
        }
      }

      // Tải Dữ liệu Đồ thị toàn phiên
      this.loadSessionChartData(sessionId);

    } catch (err) {
      console.error('Lỗi tải chi tiết phiên:', err);
    }
  }

  async loadSessionChartData(sessionId) {
    if (!this.historyChart) return;

    try {
      const res = await fetch(`/api/sessions/${sessionId}/data`);
      const d = await res.json();
      if (d.error) {
        console.warn(d.error);
        return;
      }

      this.historyChart.data.labels = d.times;
      this.historyChart.data.datasets[0].data = d.pitch;
      this.historyChart.data.datasets[1].data = d.roll;
      this.historyChart.update();

    } catch (err) {
      console.error('Lỗi tải dữ liệu đồ thị:', err);
    }
  }

  clearSessionDetail() {
    if (this.historyChart) {
      this.historyChart.data.labels = [];
      this.historyChart.data.datasets[0].data = [];
      this.historyChart.data.datasets[1].data = [];
      this.historyChart.update();
    }
    document.getElementById('hist-detail-patient-name').innerText = 'Chưa chọn phiên đo';
    document.getElementById('hist-detail-time').innerText = '--';
  }
}

window.HistoryManager = HistoryManager;
