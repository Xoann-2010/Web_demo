/**
 * head_avatar.js — Trực quan hóa Giải phẫu Đốt Sống Cổ & Chỏm Đầu (2D Biomechanical Model)
 * Vẽ trên Canvas:
 *   1. Canvas Pitch: Góc nhìn nghiêng (Sagittal View) — Cúi (Flexion) / Ngửa (Extension)
 *   2. Canvas Roll:  Góc nhìn thẳng (Coronal View)  — Nghiêng Trái (Left) / Nghiêng Phải (Right)
 */

class BiomechanicalHeadVisualizer {
  constructor(canvasPitchId, canvasRollId) {
    this.canvasP = document.getElementById(canvasPitchId);
    this.canvasR = document.getElementById(canvasRollId);
    this.ctxP = this.canvasP ? this.canvasP.getContext('2d') : null;
    this.ctxR = this.canvasR ? this.canvasR.getContext('2d') : null;

    this.pitch = 0.0;
    this.roll = 0.0;

    this.normalPitchMin = -15.0;
    this.normalPitchMax =  15.0;
    this.normalRollMin  = -10.0;
    this.normalRollMax  =  10.0;

    this.render();
  }

  update(pitchDeg, rollDeg) {
    this.pitch = pitchDeg;
    this.roll = rollDeg;
    this.render();
  }

  setThresholds(pMin, pMax, rMin, rMax) {
    this.normalPitchMin = pMin;
    this.normalPitchMax = pMax;
    this.normalRollMin  = rMin;
    this.normalRollMax  = rMax;
    this.render();
  }

  render() {
    if (this.ctxP) this.drawPitch(this.ctxP, this.canvasP.width, this.canvasP.height, this.pitch);
    if (this.ctxR) this.drawRoll(this.ctxR, this.canvasR.width, this.canvasR.height, this.roll);
  }

  /**
   * VẼ GÓC CÚI / NGỬA (PITCH - SAGITTAL VIEW)
   */
  drawPitch(ctx, w, h, angle) {
    ctx.clearRect(0, 0, w, h);
    const cx = w * 0.5;
    const cy = h * 0.72; // Gốc xoay tại khớp C7-T1
    const rHead = 38;
    const neckLen = 42;

    // Trục chuẩn thẳng đứng (0°)
    ctx.save();
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx, cy - neckLen - rHead * 1.5);
    ctx.stroke();
    ctx.restore();

    // Vùng dải an toàn [-15°, +15°]
    ctx.save();
    const radMin = (this.normalPitchMin - 90) * Math.PI / 180;
    const radMax = (this.normalPitchMax - 90) * Math.PI / 180;
    ctx.fillStyle = 'rgba(16, 185, 129, 0.12)';
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, neckLen + rHead + 10, radMin, radMax);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // Đế cố định: Đốt sống ngực T1-T3 (Sensor 1)
    ctx.fillStyle = '#64748b';
    ctx.beginPath();
    ctx.roundRect(cx - 30, cy, 60, 20, 6);
    ctx.fill();

    // Cảm biến 1 (T1-T3)
    ctx.fillStyle = '#0ea5e9';
    ctx.beginPath();
    ctx.roundRect(cx - 10, cy + 2, 20, 8, 3);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 8px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('IMU 1', cx, cy + 8);

    // Xoay cổ và đầu theo Pitch
    ctx.save();
    ctx.translate(cx, cy);
    // Lưu ý: pitch > 0 là cúi (nghiêng về phía trước / bên phải màn hình), pitch < 0 là ngửa
    const radPitch = (angle * Math.PI) / 180;
    ctx.rotate(radPitch);

    const isWarning = angle > this.normalPitchMax || angle < this.normalPitchMin;
    const headColor = isWarning ? '#ef4444' : '#0ea5e9';

    // Cột sống cổ C1-C7 (Neck)
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -neckLen);
    ctx.stroke();

    // Đốt sống cổ chi tiết
    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 2;
    for (let dy = -8; dy >= -neckLen + 8; dy -= 8) {
      ctx.beginPath();
      ctx.moveTo(-6, dy);
      ctx.lineTo(6, dy);
      ctx.stroke();
    }

    // Tâm chỏm đầu
    const hx = 0;
    const hy = -neckLen - rHead * 0.65;

    // Hộp sọ nhìn nghiêng (Skull profile)
    ctx.fillStyle = isWarning ? '#fee2e2' : '#e0f2fe';
    ctx.strokeStyle = headColor;
    ctx.lineWidth = 3;
    ctx.beginPath();
    // Vòm sọ
    ctx.arc(hx, hy, rHead, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Mũi và cằm (chỉ hướng nhìn về bên phải)
    ctx.fillStyle = isWarning ? '#fee2e2' : '#e0f2fe';
    ctx.beginPath();
    ctx.moveTo(hx + rHead * 0.85, hy - 4);
    ctx.lineTo(hx + rHead + 12, hy + 4); // Chóp mũi
    ctx.lineTo(hx + rHead * 0.8, hy + 12);
    ctx.lineTo(hx + rHead * 0.9, hy + 24); // Cằm
    ctx.lineTo(hx + rHead * 0.4, hy + rHead * 0.95);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Mắt
    ctx.fillStyle = headColor;
    ctx.beginPath();
    ctx.arc(hx + rHead * 0.55, hy - 2, 3, 0, Math.PI * 2);
    ctx.fill();

    // Cảm biến 2 (Chỏm đầu)
    ctx.fillStyle = '#10b981';
    ctx.beginPath();
    ctx.roundRect(hx - 12, hy - rHead - 8, 24, 8, 3);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 8px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('IMU 2', hx, hy - rHead - 2);

    ctx.restore();

    // Nhãn góc & phân loại
    ctx.fillStyle = isWarning ? '#ef4444' : '#0ea5e9';
    ctx.font = 'bold 15px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    const sign = angle > 0 ? '+' : '';
    ctx.fillText(`Pitch: ${sign}${angle.toFixed(1)}°`, cx, h - 8);
  }

  /**
   * VẼ GÓC NGHIÊNG TRÁI / PHẢI (ROLL - CORONAL VIEW)
   */
  drawRoll(ctx, w, h, angle) {
    ctx.clearRect(0, 0, w, h);
    const cx = w * 0.5;
    const cy = h * 0.72;
    const rHead = 36;
    const neckLen = 42;

    // Trục thẳng đứng chuẩn
    ctx.save();
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx, cy - neckLen - rHead * 1.5);
    ctx.stroke();
    ctx.restore();

    // Vùng dải an toàn [-10°, +10°]
    ctx.save();
    const radMin = (this.normalRollMin - 90) * Math.PI / 180;
    const radMax = (this.normalRollMax - 90) * Math.PI / 180;
    ctx.fillStyle = 'rgba(16, 185, 129, 0.12)';
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, neckLen + rHead + 10, radMin, radMax);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // Hai bờ vai cố định (Clavicle base)
    ctx.fillStyle = '#64748b';
    ctx.beginPath();
    ctx.roundRect(cx - 50, cy, 100, 16, 6);
    ctx.fill();

    // Cảm biến 1
    ctx.fillStyle = '#8b5cf6';
    ctx.beginPath();
    ctx.roundRect(cx - 10, cy + 2, 20, 8, 3);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 8px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('IMU 1', cx, cy + 8);

    // Xoay theo Roll
    ctx.save();
    ctx.translate(cx, cy);
    const radRoll = (angle * Math.PI) / 180;
    ctx.rotate(radRoll);

    const isWarning = angle > this.normalRollMax || angle < this.normalRollMin;
    const headColor = isWarning ? '#ef4444' : '#8b5cf6';

    // Cột sống cổ
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -neckLen);
    ctx.stroke();

    const hx = 0;
    const hy = -neckLen - rHead * 0.7;

    // Đầu nhìn chính diện (Front view skull oval)
    ctx.fillStyle = isWarning ? '#fee2e2' : '#f5f3ff';
    ctx.strokeStyle = headColor;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(hx, hy, rHead * 0.85, rHead, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Tai hai bên
    ctx.fillStyle = isWarning ? '#fee2e2' : '#f5f3ff';
    ctx.beginPath();
    ctx.ellipse(hx - rHead * 0.85, hy, 4, 10, 0, 0, Math.PI * 2);
    ctx.ellipse(hx + rHead * 0.85, hy, 4, 10, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Hai mắt
    ctx.fillStyle = headColor;
    ctx.beginPath();
    ctx.arc(hx - 10, hy - 4, 3, 0, Math.PI * 2);
    ctx.arc(hx + 10, hy - 4, 3, 0, Math.PI * 2);
    ctx.fill();

    // Mũi và miệng
    ctx.strokeStyle = headColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(hx, hy - 1);
    ctx.lineTo(hx - 2, hy + 6);
    ctx.lineTo(hx + 2, hy + 6);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(hx, hy + 14, 5, 0, Math.PI);
    ctx.stroke();

    // Cảm biến 2 (Chỏm đầu)
    ctx.fillStyle = '#10b981';
    ctx.beginPath();
    ctx.roundRect(hx - 12, hy - rHead - 8, 24, 8, 3);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 8px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('IMU 2', hx, hy - rHead - 2);

    ctx.restore();

    // Nhãn Roll
    ctx.fillStyle = isWarning ? '#ef4444' : '#8b5cf6';
    ctx.font = 'bold 15px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    const sign = angle > 0 ? '+' : '';
    ctx.fillText(`Roll: ${sign}${angle.toFixed(1)}°`, cx, h - 8);
  }
}

window.BiomechanicalHeadVisualizer = BiomechanicalHeadVisualizer;
