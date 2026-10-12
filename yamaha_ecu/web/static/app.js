/**
 * YAMAHA ECU STUDIO - FULL ECU DIAGNOSTIC, TELEMETRY & TUNING ENGINE
 * Interactive map cell editing, presets, actuator tests, hex packet terminal,
 * telemetry recording sessions manager, and zero-glow minimalist canvas rendering.
 */

// =====================================================================
// GLOBAL STATE
// =====================================================================
const state = {
  connected: false,
  mode: 'mock',
  port: 'COM3',
  baudrate: 10400,
  sseSource: null,
  packetCount: 0,
  fpsCounter: 0,
  lastFpsTimestamp: performance.now(),
  currentFps: 0,
  isRecording: false,

  // Live telemetry snapshot
  telemetry: {
    rpm: 0,
    rps: 0,
    tps: 0,
    tpsVolt: 0.65,
    tpsDeg: 0,
    engTemp: 0,
    iatTemp: 0,
    mapKpa: 0,
    baroKpa: 101.3,
    vbat: 0,
    o2Volt: 0.5,
    o2Lambda: 1.0,
    injMs: 0,
    ignDeg: 0,
    iscSteps: 0,
    neutral: true,
    kickstand: false,
    tipOverVolt: 1.4,
    fuelConsumption: 0,
    timestamp: 0,
  },

  // Oscilloscope ring buffer
  osc: {
    paused: false,
    maxPoints: 180,
    buffer: [],
  },

  // Map profile & cell selection
  mapping: {
    currentView: 'fuel', // 'fuel' or 'ign'
    profile: null,
    coTrim: 0,
    selectedCell: null, // { row, col, mapType, val }
  },
};

// =====================================================================
// RADIAL GAUGE ENGINE (MINIMALIST, NO GLOW)
// =====================================================================
class RadialGauge {
  constructor(canvasId, options) {
    this.canvas = document.getElementById(canvasId);
    this.options = Object.assign({
      min: 0,
      max: 100,
      startAngle: Math.PI * 0.75,
      endAngle: Math.PI * 2.25,
      ticks: 5,
      zones: [],
      colorArc: '#38bdf8',
      needleColor: '#38bdf8',
      valueFormat: (v) => v.toFixed(0),
    }, options);

    this.currentValue = this.options.min;
    this.targetValue = this.options.min;
  }

  setValue(val) {
    this.targetValue = Math.max(this.options.min, Math.min(this.options.max, val));
  }

  update() {
    this.currentValue += (this.targetValue - this.currentValue) * 0.25;
    this.draw();
  }

  draw() {
    if (!this.canvas) return;
    const ctx = this.canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth || this.canvas.width / dpr;
    const height = this.canvas.clientHeight || this.canvas.height / dpr;

    ctx.clearRect(0, 0, width, height);

    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) / 2 - 20;

    const span = this.options.endAngle - this.options.startAngle;
    const pct = (this.currentValue - this.options.min) / (this.options.max - this.options.min);
    const valueAngle = this.options.startAngle + span * pct;

    // 1. Background Track Arc
    ctx.beginPath();
    ctx.arc(cx, cy, radius, this.options.startAngle, this.options.endAngle, false);
    ctx.lineWidth = 6;
    ctx.strokeStyle = '#232736';
    ctx.lineCap = 'round';
    ctx.stroke();

    // 2. Colored Range Zones
    for (const zone of this.options.zones) {
      const zFromPct = (zone.from - this.options.min) / (this.options.max - this.options.min);
      const zToPct = (zone.to - this.options.min) / (this.options.max - this.options.min);
      const a1 = this.options.startAngle + span * zFromPct;
      const a2 = this.options.startAngle + span * zToPct;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, a1, a2, false);
      ctx.lineWidth = 6;
      ctx.strokeStyle = zone.color;
      ctx.lineCap = 'butt';
      ctx.stroke();
    }

    // 3. Active Value Line (No Glow)
    if (pct > 0.005) {
      ctx.beginPath();
      ctx.arc(cx, cy, radius, this.options.startAngle, valueAngle, false);
      ctx.lineWidth = 6;
      ctx.strokeStyle = this.options.colorArc;
      ctx.lineCap = 'round';
      ctx.stroke();
    }

    // 4. Tick Marks & Numbers
    const numTicks = this.options.ticks;
    for (let i = 0; i <= numTicks; i++) {
      const tPct = i / numTicks;
      const angle = this.options.startAngle + span * tPct;
      const tickVal = this.options.min + (this.options.max - this.options.min) * tPct;

      const cos = Math.cos(angle);
      const sin = Math.sin(angle);

      const rOuter = radius - 7;
      const rInner = radius - 13;

      ctx.beginPath();
      ctx.moveTo(cx + cos * rOuter, cy + sin * rOuter);
      ctx.lineTo(cx + cos * rInner, cy + sin * rInner);
      ctx.lineWidth = 1;
      ctx.strokeStyle = '#374151';
      ctx.stroke();

      const rText = radius - 24;
      ctx.fillStyle = '#6b7280';
      ctx.font = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(this.options.valueFormat(tickVal), cx + cos * rText, cy + sin * rText);
    }

    // 5. Needle Indicator (Sharp line, no glow)
    const needleLen = radius - 12;
    const nCos = Math.cos(valueAngle);
    const nSin = Math.sin(valueAngle);

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + nCos * needleLen, cy + nSin * needleLen);
    ctx.lineWidth = 2;
    ctx.strokeStyle = this.options.needleColor;
    ctx.stroke();

    // Pivot hub
    ctx.beginPath();
    ctx.arc(cx, cy, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, Math.PI * 2);
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

let rpmGauge, tpsGauge, tempGauge, vbatGauge;

function initGauges() {
  const dpr = window.devicePixelRatio || 1;

  const cvsRpm = document.getElementById('gauge-rpm');
  cvsRpm.width = 320 * dpr;
  cvsRpm.height = 320 * dpr;
  cvsRpm.getContext('2d').scale(dpr, dpr);
  rpmGauge = new RadialGauge('gauge-rpm', {
    min: 0,
    max: 10000,
    ticks: 10,
    zones: [
      { from: 8500, to: 9500, color: 'rgba(245, 158, 11, 0.4)' },
      { from: 9500, to: 10000, color: 'rgba(239, 68, 68, 0.6)' },
    ],
    colorArc: '#38bdf8',
    needleColor: '#38bdf8',
    valueFormat: (v) => (v / 1000).toFixed(0) + 'k',
  });

  const cvsTps = document.getElementById('gauge-tps');
  cvsTps.width = 240 * dpr;
  cvsTps.height = 240 * dpr;
  cvsTps.getContext('2d').scale(dpr, dpr);
  tpsGauge = new RadialGauge('gauge-tps', {
    min: 0,
    max: 100,
    ticks: 5,
    zones: [{ from: 80, to: 100, color: 'rgba(245, 158, 11, 0.4)' }],
    colorArc: '#f59e0b',
    needleColor: '#f59e0b',
    valueFormat: (v) => v.toFixed(0),
  });

  const cvsTemp = document.getElementById('gauge-temp');
  cvsTemp.width = 240 * dpr;
  cvsTemp.height = 240 * dpr;
  cvsTemp.getContext('2d').scale(dpr, dpr);
  tempGauge = new RadialGauge('gauge-temp', {
    min: 0,
    max: 130,
    ticks: 6,
    zones: [
      { from: 0, to: 55, color: '#3b82f6' },
      { from: 55, to: 95, color: '#10b981' },
      { from: 105, to: 130, color: '#ef4444' },
    ],
    colorArc: '#60a5fa',
    needleColor: '#60a5fa',
    valueFormat: (v) => v.toFixed(0),
  });

  const cvsVbat = document.getElementById('gauge-vbat');
  cvsVbat.width = 240 * dpr;
  cvsVbat.height = 240 * dpr;
  cvsVbat.getContext('2d').scale(dpr, dpr);
  vbatGauge = new RadialGauge('gauge-vbat', {
    min: 8,
    max: 16,
    ticks: 8,
    zones: [
      { from: 8, to: 11.5, color: '#ef4444' },
      { from: 11.5, to: 14.8, color: '#10b981' },
      { from: 15.0, to: 16.0, color: '#f59e0b' },
    ],
    colorArc: '#10b981',
    needleColor: '#10b981',
    valueFormat: (v) => v.toFixed(0),
  });
}

// =====================================================================
// OSCILLOSCOPE ENGINE (MINIMALIST, NO GLOW)
// =====================================================================
function renderOscilloscope() {
  const canvas = document.getElementById('osc-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 1000;
  const height = canvas.clientHeight || 420;

  if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
  }

  ctx.clearRect(0, 0, width, height);

  // Background Grid (Clean hairline)
  ctx.strokeStyle = '#1b202c';
  ctx.lineWidth = 1;

  for (let y = 0; y <= height; y += height / 10) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  for (let x = 0; x <= width; x += width / 16) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }

  const buf = state.osc.buffer;
  if (buf.length < 2) return;

  const dx = width / (state.osc.maxPoints - 1);
  const startX = width - (buf.length - 1) * dx;

  const channels = [
    { id: 'chk-trace-rpm', color: '#38bdf8', scale: (d) => height - (d.rpm / 10000) * (height - 20) - 10 },
    { id: 'chk-trace-tps', color: '#f59e0b', scale: (d) => height - (d.tps / 100) * (height - 20) - 10 },
    { id: 'chk-trace-map', color: '#a78bfa', scale: (d) => height - (d.map / 110) * (height - 20) - 10 },
    { id: 'chk-trace-inj', color: '#10b981', scale: (d) => height - (d.inj / 12) * (height - 20) - 10 },
  ];

  channels.forEach((ch) => {
    const chk = document.getElementById(ch.id);
    if (chk && !chk.checked) return;

    ctx.beginPath();
    ctx.strokeStyle = ch.color;
    ctx.lineWidth = 1.5;

    for (let i = 0; i < buf.length; i++) {
      const x = startX + i * dx;
      const y = ch.scale(buf[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  });
}

// =====================================================================
// TELEMETRY RECEPTION & UI UPDATE
// =====================================================================
function handleTelemetryData(data) {
  state.packetCount++;
  state.fpsCounter++;
  state.telemetry = Object.assign(state.telemetry, {
    rpm: data.engine_speed_rpm || 0,
    rps: data.engine_speed_rps || 0,
    tps: data.throttle_position_pct || 0,
    tpsVolt: data.throttle_voltage_v || 0.65,
    tpsDeg: data.throttle_angle_deg || 0,
    engTemp: data.engine_temp_c || 0,
    iatTemp: data.intake_air_temp_c || 0,
    mapKpa: data.manifold_pressure_kpa || 0,
    baroKpa: data.atmospheric_pressure_kpa || 101.3,
    vbat: data.battery_voltage_v || 0,
    o2Volt: data.o2_sensor_voltage_v || 0.5,
    o2Lambda: data.o2_lambda || 1.0,
    injMs: data.injector_pulse_width_ms || 0,
    ignDeg: data.ignition_advance_deg || 0,
    iscSteps: data.isc_valve_steps || 0,
    neutral: !!data.gear_neutral,
    kickstand: !!data.kickstand_down,
    tipOverVolt: data.tip_over_sensor_v || 1.4,
    fuelConsumption: data.fuel_consumption_l_per_h || 0,
    timestamp: data.timestamp || Date.now() / 1000,
  });

  if (!state.osc.paused) {
    state.osc.buffer.push({
      time: state.telemetry.timestamp,
      rpm: state.telemetry.rpm,
      tps: state.telemetry.tps,
      map: state.telemetry.mapKpa,
      inj: state.telemetry.injMs,
    });
    if (state.osc.buffer.length > state.osc.maxPoints) {
      state.osc.buffer.shift();
    }
  }

  // Update gauges
  if (rpmGauge) rpmGauge.setValue(state.telemetry.rpm);
  if (tpsGauge) tpsGauge.setValue(state.telemetry.tps);
  if (tempGauge) tempGauge.setValue(state.telemetry.engTemp);
  if (vbatGauge) vbatGauge.setValue(state.telemetry.vbat);

  // Digital metrics
  document.getElementById('readout-rpm').textContent = state.telemetry.rpm.toLocaleString();
  document.getElementById('readout-rps').textContent = state.telemetry.rps.toFixed(1);
  document.getElementById('readout-tps').textContent = state.telemetry.tps.toFixed(1);
  document.getElementById('readout-tps-volt').textContent = state.telemetry.tpsVolt.toFixed(2);
  document.getElementById('readout-tps-deg').textContent = state.telemetry.tpsDeg.toFixed(1);
  document.getElementById('tps-linear-bar').style.width = Math.min(100, state.telemetry.tps) + '%';

  document.getElementById('readout-temp').textContent = Math.round(state.telemetry.engTemp);
  document.getElementById('readout-iat').textContent = Math.round(state.telemetry.iatTemp);

  const tempStatus = document.getElementById('temp-status');
  if (state.telemetry.engTemp > 105) {
    tempStatus.textContent = 'OVERHEAT!';
    tempStatus.style.color = 'var(--danger)';
  } else if (state.telemetry.engTemp < 55) {
    tempStatus.textContent = 'WARMUP DINGIN';
    tempStatus.style.color = '#38bdf8';
  } else {
    tempStatus.textContent = 'OPTIMAL';
    tempStatus.style.color = 'var(--success)';
  }

  document.getElementById('readout-vbat').textContent = state.telemetry.vbat.toFixed(1);
  const vbatStatus = document.getElementById('vbat-status');
  if (state.telemetry.vbat < 11.8) {
    vbatStatus.textContent = 'AKI LEMAH';
    vbatStatus.style.color = 'var(--danger)';
  } else if (state.telemetry.vbat > 13.5) {
    vbatStatus.textContent = 'MENGISI (CHARGING)';
    vbatStatus.style.color = 'var(--success)';
  } else {
    vbatStatus.textContent = 'NORMAL';
    vbatStatus.style.color = 'var(--text-muted)';
  }

  document.getElementById('readout-lambda').textContent = state.telemetry.o2Lambda.toFixed(2) + ' λ';
  const lambdaPct = Math.max(0, Math.min(100, ((state.telemetry.o2Lambda - 0.7) / (1.3 - 0.7)) * 100));
  document.getElementById('lambda-cursor').style.left = lambdaPct + '%';

  // Telemetry grid
  document.getElementById('val-map').innerHTML = `${state.telemetry.mapKpa.toFixed(1)} <span class="tele-unit">kPa</span>`;
  document.getElementById('bar-map').style.width = Math.min(100, (state.telemetry.mapKpa / 110) * 100) + '%';
  document.getElementById('val-inj').innerHTML = `${state.telemetry.injMs.toFixed(2)} <span class="tele-unit">ms</span>`;
  document.getElementById('bar-inj').style.width = Math.min(100, (state.telemetry.injMs / 10) * 100) + '%';
  document.getElementById('val-ign').innerHTML = `${state.telemetry.ignDeg.toFixed(1)} <span class="tele-unit">°BTDC</span>`;
  document.getElementById('bar-ign').style.width = Math.min(100, (state.telemetry.ignDeg / 40) * 100) + '%';
  document.getElementById('val-isc').innerHTML = `${state.telemetry.iscSteps} <span class="tele-unit">steps</span>`;
  document.getElementById('bar-isc').style.width = Math.min(100, (state.telemetry.iscSteps / 100) * 100) + '%';
  document.getElementById('val-fuel').innerHTML = `${state.telemetry.fuelConsumption.toFixed(2)} <span class="tele-unit">L/Jam</span>`;
  document.getElementById('bar-fuel').style.width = Math.min(100, (state.telemetry.fuelConsumption / 6) * 100) + '%';
  document.getElementById('val-baro').innerHTML = `${state.telemetry.baroKpa.toFixed(1)} <span class="tele-unit">kPa</span>`;

  // Status pills
  const flagNeutral = document.getElementById('flag-neutral');
  document.getElementById('neutral-val').textContent = state.telemetry.neutral ? 'AKTIF' : 'MASUK GIGI';
  flagNeutral.classList.toggle('flag-alert', !state.telemetry.neutral);

  const flagKickstand = document.getElementById('flag-kickstand');
  document.getElementById('kickstand-val').textContent = state.telemetry.kickstand ? 'TURUN (CUT)' : 'NAIK';
  flagKickstand.classList.toggle('flag-alert', state.telemetry.kickstand);

  document.getElementById('lean-val').textContent = `${state.telemetry.tipOverVolt.toFixed(2)} V (${state.telemetry.tipOverVolt > 3.0 ? 'TERJATUH' : 'AMAN'})`;

  // Oscilloscope values
  document.getElementById('cur-trace-rpm').textContent = state.telemetry.rpm;
  document.getElementById('cur-trace-tps').textContent = state.telemetry.tps.toFixed(1) + '%';
  document.getElementById('cur-trace-map').textContent = state.telemetry.mapKpa.toFixed(1) + ' kPa';
  document.getElementById('cur-trace-inj').textContent = state.telemetry.injMs.toFixed(2) + ' ms';

  // Live Map active operating cell
  document.getElementById('live-map-rpm').textContent = state.telemetry.rpm;
  document.getElementById('live-map-tps').textContent = state.telemetry.tps.toFixed(1) + '%';
  highlightActiveMapCell(state.telemetry.rpm, state.telemetry.tps);

  // Footer
  document.getElementById('footer-packet-info').textContent = `Paket: ${state.packetCount.toLocaleString()} diterima`;
  document.getElementById('footer-time-info').textContent = `Waktu: ${new Date().toLocaleTimeString()}`;
}

// =====================================================================
// ECU MAP MATRIX & INTERACTIVE CELL EDITING
// =====================================================================
async function loadECUMappingProfile() {
  try {
    const res = await fetch('/api/mapping');
    const data = await res.json();
    state.mapping.profile = data;
    state.mapping.coTrim = data.co_adjustment_trim || 0;

    document.getElementById('co-slider').value = state.mapping.coTrim;
    document.getElementById('co-current-val').textContent = (state.mapping.coTrim > 0 ? '+' : '') + state.mapping.coTrim;
    document.getElementById('spec-rpm-limiter').textContent = `${data.rpm_limiter_rpm || 9500} RPM`;

    renderMapMatrixTable();
  } catch (err) {
    console.error('Gagal memuat mapping profile:', err);
  }
}

async function loadPresetsList() {
  try {
    const res = await fetch('/api/mapping/presets');
    const presets = await res.json();
    const sel = document.getElementById('sel-preset');
    sel.innerHTML = '';
    presets.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.filename;
      opt.textContent = `${p.name} (CO: ${p.co > 0 ? '+' : ''}${p.co})`;
      sel.appendChild(opt);
    });
  } catch (err) {
    console.error('Gagal memuat preset:', err);
  }
}

async function loadSelectedPreset() {
  const sel = document.getElementById('sel-preset');
  const filename = sel.value;
  if (!filename) return;

  try {
    const res = await fetch('/api/mapping/load_preset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    const data = await res.json();
    if (data.success) {
      state.mapping.profile = data.profile;
      renderMapMatrixTable();
      alert(`Berhasil memuat preset: ${filename}!`);
    } else {
      alert('Gagal memuat preset: ' + data.error);
    }
  } catch (err) {
    alert('Kesalahan saat memuat preset: ' + err.message);
  }
}

function renderMapMatrixTable() {
  if (!state.mapping.profile) return;
  const isFuel = state.mapping.currentView === 'fuel';
  const mapData = isFuel ? state.mapping.profile.fuel_map : state.mapping.profile.ignition_map;
  if (!mapData) return;

  const table = document.getElementById('ecu-matrix-table');
  table.innerHTML = '';

  const headerRow = document.createElement('tr');
  const cornerTh = document.createElement('th');
  cornerTh.className = 'th-corner';
  cornerTh.textContent = isFuel ? 'TPS \\ RPM' : 'TPS \\ RPM';
  headerRow.appendChild(cornerTh);

  mapData.rpm_axis.forEach((rpm) => {
    const th = document.createElement('th');
    th.textContent = rpm;
    headerRow.appendChild(th);
  });
  table.appendChild(headerRow);

  mapData.load_axis.forEach((tps, rowIdx) => {
    const tr = document.createElement('tr');
    const rowTh = document.createElement('th');
    rowTh.textContent = tps.toFixed(1) + '%';
    tr.appendChild(rowTh);

    mapData.matrix[rowIdx].forEach((val, colIdx) => {
      const td = document.createElement('td');
      td.textContent = val.toFixed(1);
      td.id = `map-cell-${rowIdx}-${colIdx}`;
      td.dataset.row = rowIdx;
      td.dataset.col = colIdx;
      td.dataset.rpm = mapData.rpm_axis[colIdx];
      td.dataset.tps = tps;
      td.dataset.val = val;

      const minVal = isFuel ? 1.0 : 7.0;
      const maxVal = isFuel ? 9.7 : 36.0;
      const ratio = Math.max(0, Math.min(1, (val - minVal) / (maxVal - minVal)));
      const hue = (1.0 - ratio) * 210;
      td.style.backgroundColor = `hsla(${hue}, 85%, 35%, 0.3)`;

      td.addEventListener('click', () => selectMapCell(rowIdx, colIdx, val, tps, mapData.rpm_axis[colIdx], isFuel ? 'fuel' : 'ign'));

      tr.appendChild(td);
    });
    table.appendChild(tr);
  });

  render3DSurface();
}

function selectMapCell(row, col, val, tps, rpm, mapType) {
  state.mapping.selectedCell = { row, col, val, tps, rpm, mapType };

  document.querySelectorAll('.ecu-matrix-table td').forEach((el) => el.classList.remove('cell-selected'));
  const cellEl = document.getElementById(`map-cell-${row}-${col}`);
  if (cellEl) cellEl.classList.add('cell-selected');

  const unit = mapType === 'fuel' ? 'ms' : '°BTDC';
  document.getElementById('cell-editor-label').textContent = `Sel Aktif [TPS: ${tps}%, RPM: ${rpm}]:`;

  const inputVal = document.getElementById('cell-editor-val');
  inputVal.value = val;
  inputVal.disabled = false;
  document.getElementById('btn-cell-minus').disabled = false;
  document.getElementById('btn-cell-plus').disabled = false;
  document.getElementById('btn-cell-save').disabled = false;
}

async function saveSelectedCell() {
  if (!state.mapping.selectedCell) return;
  const { row, col, mapType } = state.mapping.selectedCell;
  const newVal = parseFloat(document.getElementById('cell-editor-val').value);

  try {
    const res = await fetch('/api/mapping/cell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ map_type: mapType, row, col, value: newVal }),
    });
    const data = await res.json();
    if (data.success) {
      const table = mapType === 'fuel' ? state.mapping.profile.fuel_map : state.mapping.profile.ignition_map;
      table.matrix[row][col] = newVal;
      const cellEl = document.getElementById(`map-cell-${row}-${col}`);
      if (cellEl) {
        cellEl.textContent = newVal.toFixed(1);
        cellEl.dataset.val = newVal;
      }
      render3DSurface();
    }
  } catch (err) {
    alert('Gagal menyimpan sel: ' + err.message);
  }
}

async function applyFuelTrim(percentage) {
  try {
    const res = await fetch('/api/mapping/trim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'fuel', delta: percentage }),
    });
    const data = await res.json();
    if (data.success) {
      await loadECUMappingProfile();
      alert(`Berhasil menerapkan trim bahan bakar ${percentage > 0 ? '+' : ''}${percentage}%!`);
    }
  } catch (err) {
    alert('Gagal menerapkan trim: ' + err.message);
  }
}

async function applyIgnitionTrim(degOffset) {
  try {
    const res = await fetch('/api/mapping/trim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'ign', delta: degOffset }),
    });
    const data = await res.json();
    if (data.success) {
      await loadECUMappingProfile();
      alert(`Berhasil menerapkan offset pengapian ${degOffset > 0 ? '+' : ''}${degOffset}°!`);
    }
  } catch (err) {
    alert('Gagal menerapkan trim: ' + err.message);
  }
}

let activeCellEl = null;

function highlightActiveMapCell(rpm, tps) {
  if (!state.mapping.profile) return;
  const isFuel = state.mapping.currentView === 'fuel';
  const mapData = isFuel ? state.mapping.profile.fuel_map : state.mapping.profile.ignition_map;
  if (!mapData) return;

  let bestCol = 0;
  let minRpmDiff = Infinity;
  mapData.rpm_axis.forEach((r, idx) => {
    const diff = Math.abs(r - rpm);
    if (diff < minRpmDiff) {
      minRpmDiff = diff;
      bestCol = idx;
    }
  });

  let bestRow = 0;
  let minTpsDiff = Infinity;
  mapData.load_axis.forEach((t, idx) => {
    const diff = Math.abs(t - tps);
    if (diff < minTpsDiff) {
      minTpsDiff = diff;
      bestRow = idx;
    }
  });

  const cellId = `map-cell-${bestRow}-${bestCol}`;
  const targetEl = document.getElementById(cellId);

  if (activeCellEl && activeCellEl !== targetEl) {
    activeCellEl.classList.remove('cell-active');
  }

  if (targetEl) {
    targetEl.classList.add('cell-active');
    activeCellEl = targetEl;
    const val = targetEl.dataset.val;
    const unit = isFuel ? 'ms' : '°BTDC';
    document.getElementById('live-map-val').textContent = `${val} ${unit}`;
  }
}

function render3DSurface() {
  const canvas = document.getElementById('canvas-3d-surface');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 800;
  const height = canvas.clientHeight || 420;

  if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
  }

  ctx.clearRect(0, 0, width, height);

  const isFuel = state.mapping.currentView === 'fuel';
  const mapData = isFuel ? state.mapping.profile.fuel_map : state.mapping.profile.ignition_map;
  if (!mapData) return;

  const rows = mapData.load_axis.length;
  const cols = mapData.rpm_axis.length;
  const matrix = mapData.matrix;

  const minVal = isFuel ? 1.0 : 7.0;
  const maxVal = isFuel ? 9.7 : 36.0;

  const originX = width / 2;
  const originY = height * 0.72;
  const cellW = (width * 0.38) / cols;
  const cellH = (height * 0.28) / rows;
  const scaleZ = 120 / (maxVal - minVal);

  function project(r, c, val) {
    const x = originX + (c - cols / 2) * cellW - (r - rows / 2) * (cellW * 0.7);
    const y = originY + (r - rows / 2) * cellH + (c - cols / 2) * (cellH * 0.5) - (val - minVal) * scaleZ;
    return { x, y };
  }

  ctx.lineWidth = 1.2;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const p1 = project(r, c, matrix[r][c]);

      if (c < cols - 1) {
        const p2 = project(r, c + 1, matrix[r][c + 1]);
        const ratio = (matrix[r][c] - minVal) / (maxVal - minVal);
        const hue = (1.0 - ratio) * 210;
        ctx.strokeStyle = `hsla(${hue}, 85%, 50%, 0.8)`;
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      }

      if (r < rows - 1) {
        const p3 = project(r + 1, c, matrix[r + 1][c]);
        const ratio = (matrix[r][c] - minVal) / (maxVal - minVal);
        const hue = (1.0 - ratio) * 210;
        ctx.strokeStyle = `hsla(${hue}, 85%, 50%, 0.8)`;
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p3.x, p3.y);
        ctx.stroke();
      }
    }
  }
}

// =====================================================================
// DIAGNOSTIC DTC & ACTUATOR TESTS
// =====================================================================
async function loadDTC() {
  try {
    const res = await fetch('/api/dtc');
    const data = await res.json();

    const activeList = document.getElementById('active-dtc-list');
    const historyList = document.getElementById('history-dtc-list');
    const activeCount = document.getElementById('active-dtc-count');
    const historyCount = document.getElementById('history-dtc-count');
    const dtcBadge = document.getElementById('dtc-badge');
    const milFlag = document.getElementById('flag-mil');
    const milVal = document.getElementById('mil-val');

    activeList.innerHTML = '';
    historyList.innerHTML = '';

    const activeCodes = data.active || [];
    const historyCodes = data.history || [];

    activeCount.textContent = activeCodes.length;
    historyCount.textContent = historyCodes.length;

    if (activeCodes.length > 0) {
      milVal.textContent = `ON (${activeCodes.length} DTC)`;
      milFlag.classList.add('flag-alert');
      dtcBadge.style.display = 'inline-block';
      dtcBadge.textContent = activeCodes.length;
    } else {
      milVal.textContent = 'OFF';
      milFlag.classList.remove('flag-alert');
      dtcBadge.style.display = 'none';
    }

    if (activeCodes.length === 0) {
      activeList.innerHTML = '<div class="empty-state">✅ Tidak ada kode kerusakan aktif. Sistem FI normal.</div>';
    } else {
      activeCodes.forEach((d) => {
        activeList.innerHTML += `
          <div class="dtc-item-card">
            <div class="dtc-item-top">
              <span class="dtc-code-badge">KODE ${d.code}</span>
              <span class="dtc-sensor-name">${d.name}</span>
            </div>
            <div class="dtc-desc">${d.description}</div>
            <div class="dtc-meta">
              <div><strong>Gejala:</strong> ${d.symptoms}</div>
              <div><strong>Penyebab:</strong> ${d.probable_cause}</div>
            </div>
          </div>
        `;
      });
    }

    if (historyCodes.length === 0) {
      historyList.innerHTML = '<div class="empty-state">✅ Memori EEPROM bersih. Tidak ada riwayat kerusakan.</div>';
    } else {
      historyCodes.forEach((d) => {
        historyList.innerHTML += `
          <div class="dtc-item-card history">
            <div class="dtc-item-top">
              <span class="dtc-code-badge history">KODE ${d.code}</span>
              <span class="dtc-sensor-name">${d.name}</span>
            </div>
            <div class="dtc-desc">${d.description}</div>
          </div>
        `;
      });
    }
  } catch (err) {
    console.error('Gagal memuat DTC:', err);
  }
}

async function clearDTC() {
  if (!confirm('Apakah Anda yakin ingin menghapus seluruh memori kode kerusakan (DTC) di ECU?')) return;
  try {
    const res = await fetch('/api/dtc/clear', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      alert('Berhasil! Seluruh kode kerusakan pada EEPROM ECU berhasil di-reset.');
      loadDTC();
    } else {
      alert('Gagal mereset DTC: ' + (data.error || 'Pastikan kontak ON dan mesin mati.'));
    }
  } catch (err) {
    alert('Kesalahan saat mereset DTC: ' + err.message);
  }
}

async function triggerActuator(code) {
  const name = code === 30 ? 'Uji Koil Busi / Pengapian (d30)' : 'Uji Semprotan Injektor (d36)';
  try {
    const res = await fetch('/api/actuator/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_code: code }),
    });
    const data = await res.json();
    if (data.success) {
      alert(`[BERHASIL] ${name} berhasil dieksekusi 5 kali oleh ECU.`);
    } else {
      alert(`[GAGAL] ${name}: ${data.error}`);
    }
  } catch (err) {
    alert('Kesalahan saat memicu uji aktuator: ' + err.message);
  }
}

// =====================================================================
// DIAG MODE (d01-d70)
// =====================================================================
async function loadDiagItems() {
  try {
    const grid = document.getElementById('diag-items-grid');
    grid.innerHTML = '<div class="empty-state">Membaca parameter sensor DIAG mode...</div>';
    const res = await fetch('/api/diag');
    const items = await res.json();

    if (!items || items.length === 0) {
      grid.innerHTML = '<div class="empty-state">Tidak ada data diagnostik yang diterima.</div>';
      return;
    }

    grid.innerHTML = '';
    items.forEach((item) => {
      const isOk = item.in_range;
      grid.innerHTML += `
        <div class="diag-card ${isOk ? 'in-range' : 'out-of-range'}">
          <div class="diag-code-title">
            <span>${item.name}</span>
            <span class="card-tag ${isOk ? 'tag-green' : 'tag-amber'}">d${String(item.code).padStart(2, '0')}</span>
          </div>
          <div class="diag-val-large">${item.value} <span class="diag-unit">${item.unit}</span></div>
          <div class="diag-status-badge ${isOk ? 'ok' : 'warn'}">
            ${isOk ? 'NORMAL / DALAM RANGE' : 'DILUAR AMBANG BATAS'}
          </div>
        </div>
      `;
    });
  } catch (err) {
    console.error('Gagal memuat DIAG mode:', err);
  }
}

// =====================================================================
// TELEMETRY RECORDINGS & SESSIONS MANAGER
// =====================================================================
async function loadRecordings() {
  try {
    const res = await fetch('/api/recordings');
    const list = await res.json();
    const tbody = document.getElementById('recordings-tbody');

    if (!list || list.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Belum ada file log telemetri yang direkam. Klik "🔴 Rekam ke CSV" di tab osiloskop untuk mulai merekam.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    list.forEach((item) => {
      tbody.innerHTML += `
        <tr>
          <td><strong>${item.filename}</strong></td>
          <td>${item.formatted_date}</td>
          <td>${item.samples.toLocaleString()} sampel</td>
          <td>${item.size_kb} KB</td>
          <td>
            <a href="/api/recordings/download?file=${encodeURIComponent(item.filename)}" class="btn btn-sm btn-outline">⬇️ Unduh CSV</a>
            <button class="btn btn-sm btn-primary" onclick="generatePlotAnalysis('${item.filename}')">📊 Buat Grafik</button>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    console.error('Gagal memuat log telemetri:', err);
  }
}

async function generatePlotAnalysis(filename) {
  try {
    const res = await fetch('/api/recordings/plot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    const data = await res.json();
    if (data.success) {
      const container = document.getElementById('plot-preview-container');
      const img = document.getElementById('plot-preview-img');
      const title = document.getElementById('plot-preview-title');
      img.src = `/${data.image}?t=${Date.now()}`;
      title.textContent = `Grafik Analisis Telemetri: ${filename}`;
      container.style.display = 'block';
    } else {
      alert('Gagal membuat grafik analisis: ' + data.error);
    }
  } catch (err) {
    alert('Kesalahan saat membuat plot analisis: ' + err.message);
  }
}

function closePlotPreview() {
  document.getElementById('plot-preview-container').style.display = 'none';
}

// =====================================================================
// RAW Y-DIS HEX TERMINAL
// =====================================================================
async function sendRawHex(hexStr) {
  const logBox = document.getElementById('terminal-log-box');
  const now = new Date().toLocaleTimeString();

  logBox.innerHTML += `<div class="terminal-log-entry tx">[${now}] TX &gt;&gt; ${hexStr}</div>`;

  try {
    const res = await fetch('/api/raw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hex_command: hexStr }),
    });
    const data = await res.json();
    if (data.success) {
      logBox.innerHTML += `<div class="terminal-log-entry rx">[${now}] RX &lt;&lt; ${data.response_hex} (${data.resp_cmd || ''})</div>`;
    } else {
      logBox.innerHTML += `<div class="terminal-log-entry error">[${now}] ERR &lt;&lt; ${data.error}</div>`;
    }
    logBox.scrollTop = logBox.scrollHeight;
  } catch (err) {
    logBox.innerHTML += `<div class="terminal-log-entry error">[${now}] NETWORK ERROR: ${err.message}</div>`;
  }
}

function sendQuickHex(code) {
  document.getElementById('raw-hex-input').value = code;
  sendRawHex(code);
}

// =====================================================================
// SSE REAL-TIME CONNECTION STREAM
// =====================================================================
function connectSSE() {
  if (state.sseSource) state.sseSource.close();

  const pill = document.getElementById('connection-pill');
  const statusText = document.getElementById('connection-status-text');
  const dot = pill.querySelector('.status-dot');

  state.sseSource = new EventSource('/api/stream');

  state.sseSource.onopen = () => {
    state.connected = true;
    dot.className = 'status-dot connected';
    statusText.textContent = 'TERHUBUNG';
    document.getElementById('btn-toggle-connect').textContent = 'Putuskan';
    document.getElementById('btn-toggle-connect').classList.add('connected');
  };

  state.sseSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      handleTelemetryData(data);
    } catch (err) {}
  };

  state.sseSource.onerror = () => {
    state.connected = false;
    dot.className = 'status-dot disconnected';
    statusText.textContent = 'RECONNECTING...';
    document.getElementById('btn-toggle-connect').textContent = 'Hubungkan';
    document.getElementById('btn-toggle-connect').classList.remove('connected');
  };
}

// =====================================================================
// SERVER STATUS & HARDWARE CONTROL
// =====================================================================
async function checkServerStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.connected = data.connected;
    state.mode = data.mode;
    state.port = data.port;
    state.baudrate = data.baudrate;
    state.isRecording = data.is_recording;

    document.getElementById('mode-text').textContent = data.mode === 'mock' ? 'MOCK SIMULATOR' : `K-LINE (${data.port})`;
    document.getElementById('sel-connection-mode').value = data.mode;
    document.getElementById('sel-baudrate').value = String(data.baudrate);

    updateRecordingUI(data.is_recording, data.recorded_samples || 0);

    if (data.connected && !state.sseSource) connectSSE();
  } catch (err) {
    console.warn('Gagal membaca status server:', err);
  }
}

async function scanPorts() {
  try {
    const res = await fetch('/api/ports');
    const ports = await res.json();
    const sel = document.getElementById('sel-serial-port');
    sel.innerHTML = '';
    ports.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p;
      if (p === state.port) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (err) {
    console.error('Gagal memindai port serial:', err);
  }
}

async function applyConnection() {
  const mode = document.getElementById('sel-connection-mode').value;
  const port = document.getElementById('sel-serial-port').value || 'COM3';
  const baudrate = parseInt(document.getElementById('sel-baudrate').value, 10) || 10400;

  const res = await fetch('/api/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mock: mode === 'mock', port, baudrate }),
  });
  const data = await res.json();
  if (data.status === 'ok') {
    state.mode = mode;
    state.port = port;
    state.baudrate = baudrate;
    document.getElementById('mode-text').textContent = mode === 'mock' ? 'MOCK SIMULATOR' : `K-LINE (${port})`;
    connectSSE();
    alert(`Berhasil terhubung ke ${mode === 'mock' ? 'Simulator Mock' : port}!`);
  } else {
    alert('Gagal menghubungkan: ' + data.message);
  }
}

function updateRecordingUI(recording, samples = 0) {
  state.isRecording = recording;
  const btn = document.getElementById('btn-record-csv');
  const chip = document.getElementById('rec-info-chip');
  const recVal = document.getElementById('rec-val');

  if (recording) {
    btn.textContent = '⏹️ Hentikan Rekam';
    btn.classList.add('recording');
    chip.style.display = 'flex';
    document.getElementById('rec-samples-count').textContent = samples;
    recVal.textContent = 'RECORDING';
    document.getElementById('flag-recording').classList.add('flag-alert');
  } else {
    btn.textContent = '🔴 Rekam ke CSV';
    btn.classList.remove('recording');
    chip.style.display = 'none';
    recVal.textContent = 'STANDBY';
    document.getElementById('flag-recording').classList.remove('flag-alert');
  }
}

async function toggleRecording() {
  if (state.isRecording) {
    const res = await fetch('/api/recording/stop', { method: 'POST' });
    const data = await res.json();
    updateRecordingUI(false);
    alert(`Perekaman CSV selesai!\nFile tersimpan di: ${data.path}\nTotal sampel: ${data.samples}`);
    loadRecordings();
  } else {
    const res = await fetch('/api/recording/start', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'recording_started') {
      updateRecordingUI(true, 0);
    }
  }
}

// =====================================================================
// ANIMATION LOOP
// =====================================================================
function animationLoop(timestamp) {
  if (rpmGauge) rpmGauge.update();
  if (tpsGauge) tpsGauge.update();
  if (tempGauge) tempGauge.update();
  if (vbatGauge) vbatGauge.update();

  const oscPane = document.getElementById('tab-oscilloscope');
  if (oscPane && oscPane.classList.contains('active')) {
    renderOscilloscope();
  }

  if (timestamp - state.lastFpsTimestamp >= 1000) {
    state.currentFps = state.fpsCounter;
    state.fpsCounter = 0;
    state.lastFpsTimestamp = timestamp;
    document.getElementById('telemetry-fps').textContent = state.currentFps.toFixed(1);
  }

  requestAnimationFrame(animationLoop);
}

// =====================================================================
// INITIALIZATION
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
  initGauges();
  connectSSE();
  checkServerStatus();
  scanPorts();
  loadECUMappingProfile();
  loadPresetsList();
  loadDTC();

  // Tab switcher
  document.querySelectorAll('.nav-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPane = document.getElementById(tab.dataset.tab);
      if (targetPane) targetPane.classList.add('active');

      if (tab.dataset.tab === 'tab-dtc') loadDTC();
      if (tab.dataset.tab === 'tab-diag') loadDiagItems();
      if (tab.dataset.tab === 'tab-maps') renderMapMatrixTable();
      if (tab.dataset.tab === 'tab-recordings') loadRecordings();
    });
  });

  // Oscilloscope controls
  document.getElementById('btn-pause-osc').addEventListener('click', (e) => {
    state.osc.paused = !state.osc.paused;
    e.target.textContent = state.osc.paused ? 'Resume' : 'Pause';
    e.target.classList.toggle('active', state.osc.paused);
  });

  document.getElementById('btn-clear-osc').addEventListener('click', () => {
    state.osc.buffer = [];
  });

  document.getElementById('btn-record-csv').addEventListener('click', toggleRecording);

  // Map view toggle
  document.getElementById('btn-view-fuel').addEventListener('click', (e) => {
    document.querySelectorAll('.btn-tab-map').forEach((b) => b.classList.remove('active'));
    e.target.classList.add('active');
    state.mapping.currentView = 'fuel';
    renderMapMatrixTable();
  });

  document.getElementById('btn-view-ign').addEventListener('click', (e) => {
    document.querySelectorAll('.btn-tab-map').forEach((b) => b.classList.remove('active'));
    e.target.classList.add('active');
    state.mapping.currentView = 'ign';
    renderMapMatrixTable();
  });

  document.getElementById('btn-mode-2d').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('btn-mode-3d').classList.remove('active');
    document.getElementById('map-table-view').style.display = 'block';
    document.getElementById('map-3d-view').style.display = 'none';
  });

  document.getElementById('btn-mode-3d').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('btn-mode-2d').classList.remove('active');
    document.getElementById('map-table-view').style.display = 'none';
    document.getElementById('map-3d-view').style.display = 'block';
    render3DSurface();
  });

  // Preset loader
  document.getElementById('btn-load-preset').addEventListener('click', loadSelectedPreset);

  // Cell editor controls
  document.getElementById('btn-cell-minus').addEventListener('click', () => {
    const input = document.getElementById('cell-editor-val');
    input.value = (parseFloat(input.value) - 0.1).toFixed(1);
  });

  document.getElementById('btn-cell-plus').addEventListener('click', () => {
    const input = document.getElementById('cell-editor-val');
    input.value = (parseFloat(input.value) + 0.1).toFixed(1);
  });

  document.getElementById('btn-cell-save').addEventListener('click', saveSelectedCell);

  // CO Slider
  const coSlider = document.getElementById('co-slider');
  coSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    document.getElementById('co-current-val').textContent = (val > 0 ? '+' : '') + val;
  });

  document.getElementById('btn-apply-co').addEventListener('click', async () => {
    const val = parseInt(coSlider.value, 10);
    try {
      const res = await fetch('/api/mapping/co', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ co_trim: val }),
      });
      const data = await res.json();
      if (data.success) {
        alert(`Berhasil menyimpan CO Adjustment Trim: ${val} ke ECU!`);
      } else {
        alert('Gagal mengatur CO Trim: ' + (data.error || 'Pastikan kontak motor ON.'));
      }
    } catch (err) {
      alert('Kesalahan saat mengirim CO trim: ' + err.message);
    }
  });

  // DTC Buttons
  document.getElementById('btn-refresh-dtc').addEventListener('click', loadDTC);
  document.getElementById('btn-clear-dtc').addEventListener('click', clearDTC);

  // DIAG Buttons
  document.getElementById('btn-refresh-diag').addEventListener('click', loadDiagItems);

  // Recordings
  document.getElementById('btn-refresh-recordings').addEventListener('click', loadRecordings);

  // Raw Hex Terminal
  document.getElementById('btn-send-raw-hex').addEventListener('click', () => {
    const val = document.getElementById('raw-hex-input').value.trim();
    if (val) sendRawHex(val);
  });

  document.getElementById('raw-hex-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const val = e.target.value.trim();
      if (val) sendRawHex(val);
    }
  });

  // Settings
  document.getElementById('btn-scan-ports').addEventListener('click', scanPorts);
  document.getElementById('btn-apply-connection').addEventListener('click', applyConnection);
  document.getElementById('btn-toggle-connect').addEventListener('click', async () => {
    if (state.connected) {
      await fetch('/api/disconnect', { method: 'POST' });
      if (state.sseSource) state.sseSource.close();
      state.connected = false;
      document.getElementById('connection-status-text').textContent = 'TERPUTUS';
      document.querySelector('.status-dot').className = 'status-dot disconnected';
      document.getElementById('btn-toggle-connect').textContent = 'Hubungkan';
      document.getElementById('btn-toggle-connect').classList.remove('connected');
    } else {
      applyConnection();
    }
  });

  window.addEventListener('resize', () => {
    initGauges();
    render3DSurface();
  });

  requestAnimationFrame(animationLoop);
});
