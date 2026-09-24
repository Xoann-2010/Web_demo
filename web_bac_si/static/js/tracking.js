/**
 * tracking.js — Quản lý phòng khám và đo đạc thời gian thực (Real-time Telemetry & Charts)
 */

class TrackingManager {
  constructor(socket) {
    this.socket = socket;
    this.chart = null;
    this.visualizer = null;
    this.isMeasuring = false;
    this.maxPoints = 15 * 25; // 15 giây ở tần số 25Hz = 375 điểm

    this.dataPitch = [];
    this.dataRoll  = [];
    this.labels    = [];
    this.eventMarkers = [];

    this.initChart();
    this.initVisualizer();
    this.bindEvents();
    this.setupSocketListeners();
  }

  initVisualizer() {
    this.visualizer = new BiomechanicalHeadVisualizer('canvas-pitch-model', 'canvas-roll-model');
  }

  initChart() {
    const ctx = document.getElementById('realtime-chart');
    if (!ctx) return;

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.labels,
        datasets: [
          {
            label: 'Pitch (Cúi / Ngửa)',
            data: this.dataPitch,
            borderColor: '#0ea5e9',
            backgroundColor: 'rgba(14, 165, 233, 0.08)',
            borderWidth: 2.2,
            pointRadius: 0,
            pointHoverRadius: 5,
            tension: 0.25,
            fill: false
          },
          {
            label: 'Roll (Nghiêng T / P)',
            data: this.dataRoll,
            borderColor: '#8b5cf6',
            backgroundColor: 'rgba(139, 92, 246, 0.08)',
            borderWidth: 2.0,
            pointRadius: 0,
            pointHoverRadius: 5,
            tension: 0.25,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false, // tắt animation để vẽ 25Hz mượt mà
        interaction: {
          mode: 'index',
          intersect: false
        },
        scales: {
          x: {
            display: true,
            title: {
              display: true,
              text: 'Thời gian tương đối (giây)',
              color: '#94a3b8',
              font: { size: 11, family: 'Inter' }
            },
            grid: { color: 'rgba(226, 232, 240, 0.6)' },
            ticks: { maxTicksLimit: 8, color: '#94a3b8', font: { size: 10 } }
          },
          y: {
            display: true,
            min: -35,
            max: 35,
            title: {
              display: true,
              text: 'Góc nghiêng (°)',
              color: '#94a3b8',
              font: { size: 11, family: 'Inter' }
            },
            grid: {
              color: (context) => {
                if (context.tick.value === 0) return '#64748b'; // Đường 0°
                if (Math.abs(context.tick.value) === 15) return 'rgba(16, 185, 129, 0.4)'; // Ngưỡng CROM 15°
                return 'rgba(226, 232, 240, 0.5)';
              },
              lineWidth: (context) => (context.tick.value === 0 ? 1.5 : 1)
            },
            ticks: {
              stepSize: 10,
              color: '#64748b',
              font: { size: 10, family: 'JetBrains Mono' }
            }
          }
        },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              boxWidth: 14,
              font: { family: 'Inter', size: 12, weight: 600 }
            }
          },
          tooltip: {
            backgroundColor: '#1e293b',
            titleFont: { family: 'Inter', size: 12 },
            bodyFont: { family: 'JetBrains Mono', size: 12 },
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y > 0 ? '+' : ''}${ctx.parsed.y.toFixed(1)}°`
            }
          }
        }
      }
    });
  }

  setupSocketListeners() {
    this.socket.on('telemetry_update', (data) => {
      this.handleTelemetry(data);
    });

    this.socket.on('status_change', (data) => {
      this.handleStatusChange(data);
    });

    this.socket.on('error_notification', (data) => {
      this.showToast(data.message || 'Lỗi hệ thống', 'error');
      // Nếu có lỗi, kiểm tra đưa trạng thái về idle nếu không đo
      if (!this.isMeasuring) {
        this.currentState = 'idle';
        this.updateButtonStates();
      }
    });

    this.socket.on('calibration_progress', (data) => {
      const pBar = document.getElementById('calib-progress-bar');
      const pText = document.getElementById('calib-progress-text');
      if (pBar) pBar.style.width = `${data.percent}%`;
      if (pText) pText.innerText = `Đang hiệu chỉnh tĩnh: ${data.percent}% (${data.current}/${data.total} mẫu)`;
    });

    this.socket.on('tare_acknowledged', (data) => {
      this.showToast(data.message, 'success');
    });

    this.socket.on('event_marked', (data) => {
      this.showToast(`Đã đánh dấu sự kiện lúc ${data.time_s}s: ${data.label}`, 'warning');
      this.addEventToTimeline(data);
    });

    this.socket.on('session_finished', (data) => {
      this.isMeasuring = false;
      this.currentState = 'idle';
      this.updateButtonStates();
      this.showSessionSummaryModal(data);
    });
  }

  handleTelemetry(data) {
    // 1. Cập nhật Avatar Giải Phẫu
    if (this.visualizer) {
      this.visualizer.update(data.pitch, data.roll);
    }

    // 2. Cập nhật Đồng hồ số to & Huy hiệu cảnh báo
    const pitchValEl = document.getElementById('live-pitch-deg');
    const rollValEl  = document.getElementById('live-roll-deg');
    const pitchBadgeEl = document.getElementById('pitch-status-badge');
    const rollBadgeEl  = document.getElementById('roll-status-badge');

    if (pitchValEl) {
      pitchValEl.innerText = `${data.pitch > 0 ? '+' : ''}${data.pitch.toFixed(1)}°`;
      pitchValEl.className = data.pitch_warn ? 'text-3xl font-mono font-bold text-red-600 animate-pulse' : 'text-3xl font-mono font-bold text-sky-600';
    }

    if (rollValEl) {
      rollValEl.innerText = `${data.roll > 0 ? '+' : ''}${data.roll.toFixed(1)}°`;
      rollValEl.className = data.roll_warn ? 'text-3xl font-mono font-bold text-red-600 animate-pulse' : 'text-3xl font-mono font-bold text-purple-600';
    }

    if (pitchBadgeEl) {
      if (data.pitch_warn) {
        pitchBadgeEl.innerText = data.pitch > 0 ? 'Cúi quá mức ⚠' : 'Ngửa quá mức ⚠';
        pitchBadgeEl.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-red-100 text-red-700';
      } else {
        pitchBadgeEl.innerText = 'Dải an toàn ✓';
        pitchBadgeEl.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-700';
      }
    }

    if (rollBadgeEl) {
      if (data.roll_warn) {
        rollBadgeEl.innerText = 'Nghiêng quá mức ⚠';
        rollBadgeEl.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-red-100 text-red-700';
      } else {
        rollBadgeEl.innerText = 'Dải an toàn ✓';
        rollBadgeEl.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-700';
      }
    }

    // 3. Cập nhật Thẻ thông số sinh cơ học (ROM)
    const elMaxFlex = document.getElementById('metric-max-flexion');
    const elMaxExt  = document.getElementById('metric-max-extension');
    const elMaxRollL = document.getElementById('metric-max-roll-left');
    const elMaxRollR = document.getElementById('metric-max-roll-right');
    const elAvgPitch = document.getElementById('metric-avg-pitch');
    const elAvgRoll  = document.getElementById('metric-avg-roll');
    const elTimer    = document.getElementById('session-timer-text');

    if (elMaxFlex) elMaxFlex.innerText = `+${data.max_flexion.toFixed(1)}°`;
    if (elMaxExt)  elMaxExt.innerText  = `-${data.max_extension.toFixed(1)}°`;
    if (elMaxRollL) elMaxRollL.innerText = `-${data.max_roll_left.toFixed(1)}°`;
    if (elMaxRollR) elMaxRollR.innerText = `+${data.max_roll_right.toFixed(1)}°`;
    if (elAvgPitch) elAvgPitch.innerText = `${data.avg_pitch > 0 ? '+' : ''}${data.avg_pitch.toFixed(1)}°`;
    if (elAvgRoll)  elAvgRoll.innerText  = `${data.avg_roll > 0 ? '+' : ''}${data.avg_roll.toFixed(1)}°`;
    if (elTimer)    elTimer.innerText    = `${data.elapsed_s.toFixed(1)}s`;

    // 4. Cập nhật Chỉ số kết nối phần cứng
    const elRate = document.getElementById('hw-sample-rate');
    const elDrop = document.getElementById('hw-dropped');
    const elCrc  = document.getElementById('hw-crc-err');
    const elTemp = document.getElementById('hw-temp');

    if (elRate) elRate.innerText = `${data.sample_rate} Hz`;
    if (elDrop) elDrop.innerText = data.dropped;
    if (elCrc)  elCrc.innerText  = data.crc_errors;
    if (elTemp) elTemp.innerText = `${data.temp_head}°C (Head) / ${data.temp_t13}°C (T13)`;

    // 5. Cập nhật Biểu đồ Rolling Waveform
    this.labels.push(data.elapsed_s.toFixed(1));
    this.dataPitch.push(data.pitch);
    this.dataRoll.push(data.roll);

    if (this.labels.length > this.maxPoints) {
      this.labels.shift();
      this.dataPitch.shift();
      this.dataRoll.shift();
    }

    if (this.chart) {
      this.chart.update('none'); // Update không animation để đạt 25fps mượt mà
    }
  }

  handleStatusChange(data) {
    this.currentState = data.state;
    const statusMsgEl = document.getElementById('engine-status-msg');
    const statusPillEl = document.getElementById('engine-status-pill');
    const calibBox = document.getElementById('calib-progress-box');

    if (statusMsgEl) statusMsgEl.innerText = data.message || '';
    if (statusPillEl) {
      statusPillEl.className = `status-pill ${data.state}`;
      const stateLabels = {
        idle: '● Chờ đo',
        connecting: '● Đang kết nối',
        calibrating: '● Hiệu chỉnh 0°',
        measuring: '● Đang đo',
        error: '● Lỗi'
      };
      statusPillEl.innerText = stateLabels[data.state] || data.state;
    }

    if (calibBox) {
      calibBox.style.display = data.state === 'calibrating' ? 'block' : 'none';
    }

    this.isMeasuring = data.state === 'measuring';
    this.updateButtonStates();
  }

  updateButtonStates() {
    const btnStart = document.getElementById('btn-start-session');
    const btnStop  = document.getElementById('btn-stop-session');
    const btnTare  = document.getElementById('btn-tare-zero');
    const btnMark  = document.getElementById('btn-mark-event');

    const isBusy = (this.currentState === 'connecting' || this.currentState === 'calibrating' || this.currentState === 'measuring');

    if (btnStart) btnStart.disabled = isBusy;
    if (btnStop)  btnStop.disabled  = !isBusy;
    if (btnTare)  btnTare.disabled  = !this.isMeasuring;
    if (btnMark)  btnMark.disabled  = !this.isMeasuring;
  }

  bindEvents() {
    // Nút Bắt đầu đo
    document.getElementById('btn-start-session')?.addEventListener('click', () => {
      const patientSelect = document.getElementById('tracking-patient-select');
      const patientId = patientSelect ? parseInt(patientSelect.value) : null;
      const durationSelect = document.getElementById('tracking-duration-select');
      const durationLimit = durationSelect ? parseInt(durationSelect.value) : 0;

      // Xóa sạch dữ liệu biểu đồ trước đó
      this.labels.length = 0;
      this.dataPitch.length = 0;
      this.dataRoll.length = 0;
      if (this.chart) this.chart.update();

      const timelineEl = document.getElementById('event-timeline-list');
      if (timelineEl) timelineEl.innerHTML = '<div class="text-xs text-gray-400 italic py-1">Chưa có sự kiện nào được ghi nhận.</div>';

      // Phản hồi giao diện tức thì
      const statusPillEl = document.getElementById('engine-status-pill');
      const statusMsgEl = document.getElementById('engine-status-msg');
      if (statusPillEl) {
        statusPillEl.className = 'status-pill connecting';
        statusPillEl.innerText = '● Đang kết nối...';
      }
      if (statusMsgEl) {
        statusMsgEl.innerText = 'Đang khởi động phiên đo...';
      }

      this.currentState = 'connecting';
      this.updateButtonStates();

      this.socket.emit('start_measurement', {
        patient_id: isNaN(patientId) ? null : patientId,
        duration_limit: isNaN(durationLimit) ? 0 : durationLimit
      });
    });

    // Nút Dừng đo
    document.getElementById('btn-stop-session')?.addEventListener('click', () => {
      const statusPillEl = document.getElementById('engine-status-pill');
      const statusMsgEl = document.getElementById('engine-status-msg');
      if (statusPillEl) {
        statusPillEl.className = 'status-pill idle';
        statusPillEl.innerText = '● Đang lưu & dừng...';
      }
      if (statusMsgEl) {
        statusMsgEl.innerText = 'Đang dừng phiên đo và lưu dữ liệu...';
      }
      this.isMeasuring = false;
      this.currentState = 'idle';
      this.updateButtonStates();
      this.socket.emit('stop_measurement');
    });

    // Nút Cân bằng 0° (Tare)
    document.getElementById('btn-tare-zero')?.addEventListener('click', () => {
      this.socket.emit('tare');
    });

    // Nút Đánh dấu sự kiện đau / Cột mốc
    document.getElementById('btn-mark-event')?.addEventListener('click', () => {
      document.getElementById('modal-mark-event')?.classList.remove('hidden');
    });

    // Chuyển đổi Cảm biến Thật (BLE) / Giả lập (Demo)
    document.getElementById('switch-mode-select')?.addEventListener('change', (e) => {
      const mode = e.target.value;
      this.socket.emit('set_mode', { mode });
    });
  }

  addEventToTimeline(evt) {
    const list = document.getElementById('event-timeline-list');
    if (!list) return;
    if (list.querySelector('.italic')) list.innerHTML = '';

    const item = document.createElement('div');
    item.className = 'flex items-center justify-between p-2 bg-amber-50 border border-amber-200 rounded-md text-xs font-medium text-amber-900 mb-1';
    item.innerHTML = `
      <div class="flex items-center gap-1.5">
        <span class="w-2 h-2 rounded-full bg-amber-500"></span>
        <span>⏱ ${evt.time_s}s: <strong>${evt.label}</strong></span>
      </div>
      <div class="font-mono text-gray-600">
        P: ${evt.pitch}° | R: ${evt.roll}°
      </div>
    `;
    list.prepend(item);
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const color = type === 'success' ? 'bg-emerald-600' : type === 'warning' ? 'bg-amber-600' : 'bg-sky-600';
    toast.className = `fixed bottom-6 right-6 ${color} text-white text-xs font-semibold px-4 py-3 rounded-lg shadow-lg z-50 flex items-center gap-2 transition-all transform duration-300`;
    toast.innerHTML = `<span>✓</span> <span>${message}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  showSessionSummaryModal(data) {
    const modal = document.getElementById('modal-session-summary');
    if (!modal) return;

    document.getElementById('summary-session-time').innerText = `${data.duration_s}s`;
    document.getElementById('summary-max-flex').innerText = `+${data.max_flexion}°`;
    document.getElementById('summary-max-ext').innerText  = `-${data.max_extension}°`;
    document.getElementById('summary-max-roll-l').innerText = `-${data.max_roll_left}°`;
    document.getElementById('summary-max-roll-r').innerText = `+${data.max_roll_right}°`;
    document.getElementById('summary-samples-count').innerText = `${data.total_samples} mẫu`;

    const btnViewHistory = document.getElementById('btn-summary-go-history');
    if (btnViewHistory) {
      btnViewHistory.onclick = () => {
        modal.classList.add('hidden');
        window.App.switchTab('history');
        if (data.session_id && window.HistoryManager) {
          window.HistoryManager.loadSessionDetail(data.session_id);
        }
      };
    }

    const btnDownload = document.getElementById('btn-summary-download-csv');
    if (btnDownload && data.csv_filename) {
      btnDownload.href = `/api/download_csv/${data.csv_filename}`;
    }

    modal.classList.remove('hidden');
  }

  submitEventTag(tag) {
    this.socket.emit('mark_event', { label: tag });
    document.getElementById('modal-mark-event')?.classList.add('hidden');
  }

  submitCustomEvent() {
    const input = document.getElementById('custom-event-input');
    const val = input ? input.value.trim() : '';
    if (val) {
      this.socket.emit('mark_event', { label: val });
      input.value = '';
    }
    document.getElementById('modal-mark-event')?.classList.add('hidden');
  }
}

window.TrackingManager = TrackingManager;
