// scripts.js – Full corrected version with video summary updates every 2 seconds
// and dynamic recent files table. Save button now properly enabled after analysis.

window.addEventListener('DOMContentLoaded', () => {
  const API_BASE = "http://localhost:8001";

  function getElement(id) {
    const el = document.getElementById(id);
    if (!el) console.warn(`Element with id '${id}' not found.`);
    return el;
  }

  // ---------- DOM elements ----------
  const video = getElement('video');
  const canvas = getElement('overlay');
  const ctx = canvas ? canvas.getContext('2d', { alpha: true }) : null;
  const fileInput = getElement('fileInput');
  const btnPlay = getElement('btnPlay');
  const btnPause = getElement('btnPause');
  const btnStop = getElement('btnStop');
  const btnAnalyze = getElement('btnAnalyze');
  const btnDownloadReport = getElement('btnDownloadReport');
  // Use let so we can reassign if needed (though we won't clone anymore)
  let btnSaveToDatabase = getElement('btnSaveToDatabase');
  const btnAuto = getElement('btnAuto');
  const backendStatus = getElement('backendStatus');
  const btnStageNone = getElement('btnStageNone');
  const btnStagePre = getElement('btnStagePre');
  const btnStagePost = getElement('btnStagePost');
  const stageLabel = getElement('stageLabel');
  const btnViewExterior = getElement('btnViewExterior');
  const btnViewInterior = getElement('btnViewInterior');
  const viewLabel = getElement('viewLabel');
  const summaryContainerId = getElement('summaryContainerId');
  const summaryContainerType = getElement('summaryContainerType');
  const summaryStatusBadge = getElement('summaryStatusBadge');
  const summaryStageBadge = getElement('summaryStageBadge');
  const summaryPeopleBadge = getElement('summaryPeopleBadge');
  const summaryDoorBadge = getElement('summaryDoorBadge');
  const summaryAnomBadge = getElement('summaryAnomBadge');
  const contScaleValueText = getElement('contScaleValueText');
  const contaminationScore = getElement('contaminationScore');
  const totalDefectsSpan = getElement('totalDefects');
  const cleanlinessSpan = getElement('cleanlinessScore');
  const structuralIssuesSpan = getElement('structuralIssues');
  const damageSensitivitySelect = getElement('damageSensitivity');
  const spotModeSelect = getElement('spotMode');

  if (!video || !canvas || !ctx) {
    console.error('Critical video/canvas elements missing. Aborting.');
    return;
  }

  // ---------- MJPEG stream element ----------
  const mjpegImg = document.createElement('img');
  mjpegImg.id = 'mjpegStream';
  mjpegImg.style.display = 'none';
  mjpegImg.style.width = '100%';
  mjpegImg.style.height = '100%';
  mjpegImg.style.objectFit = 'contain';
  document.querySelector('.video-container').appendChild(mjpegImg);

  // ---------- Defect classification ----------
  const REFINED_CONTAINER_CLASSES = [
    "Cracks", "Dents", "Rust & Corrosion", "Holes",
    "Dust & Powder", "Oil & Stains", "Nails & Fasteners",
    "Floor Structural Damage"
  ];

  const DEFECT_MAP = {
    "damagedent": "Dents",
    "damagescratch": "Dents",
    "damagehole": "Holes",
    "damagecrack": "Cracks",
    "rust": "Rust & Corrosion",
    "corrosion": "Rust & Corrosion",
    "dirt": "Dust & Powder",
    "dust": "Dust & Powder",
    "powder": "Dust & Powder",
    "oil": "Oil & Stains",
    "stain": "Oil & Stains",
    "grease": "Oil & Stains",
    "looseobject": "Nails & Fasteners",
    "nail": "Nails & Fasteners",
    "fastener": "Nails & Fasteners",
    "floorstructural": "Floor Structural Damage",
    "floordamage": "Floor Structural Damage",
    "mold": "Biological/Fungal",
    "fungal": "Biological/Fungal",
    "biological": "Biological/Fungal",
    "dark spot": "Biological/Fungal"
  };

  function mapToRefinedClass(originalLabel) {
    if (!originalLabel) return "Unknown";
    const key = originalLabel.toLowerCase().trim();
    for (let [pattern, mapped] of Object.entries(DEFECT_MAP)) {
      if (key.includes(pattern)) return mapped;
    }
    for (let refined of REFINED_CONTAINER_CLASSES) {
      if (key.includes(refined.toLowerCase())) return refined;
    }
    return originalLabel;
  }

  // ---------- Global state ----------
  let lastDetections = [];
  let lastAnalysisResult = null;
  let currentImageData = null;
  let currentImageObject = null;
  let autoAnalyze = false;
  let autoTimer = null;
  let analyzing = false;
  let currentStage = null;
  let currentView = null;
  let imageScale = 1;
  let imageOffsetX = 0, imageOffsetY = 0;
  let imageDrawWidth = 0, imageDrawHeight = 0;
  let currentSessionId = null;
  let pollingInterval = null;
  let currentVideoFile = null;

  // ---------- Helper functions ----------
  function updateBackendStatus(text, ok = false) {
    if (backendStatus) {
      backendStatus.textContent = text;
      backendStatus.style.color = ok ? "#22c55e" : "#f97373";
    }
  }

  function colorForCategory(cat, label) {
    const c = (cat || "").toLowerCase();
    const l = (label || "").toLowerCase();
    if (l.includes("dark spot") || l.includes("mold") || l.includes("mould") || l.includes("mögel")) return "#a855f7";
    if (c === "damage" || l.startsWith("damage")) return "#ef4444";
    if (l.includes("dirt") || l.includes("smuts") || l.includes("looseobject") || l.includes("loose object") || l.includes("löst föremål") || l.includes("discoloration") || l.includes("missfärgning")) return "#eab308";
    if (c === "lock") return "#22c55e";
    if (c === "door" || c === "door_open" || c === "door_closed") return "#e5e7eb";
    if (c === "human") return "#f9fafb";
    const defectColors = {
      "crack": "#ef4444", "dent": "#f97316", "rust": "#b91c1c", "corrosion": "#b91c1c",
      "hole": "#dc2626", "dust": "#eab308", "powder": "#eab308", "oil": "#facc15",
      "stain": "#facc15", "nail": "#84cc16", "fastener": "#84cc16", "floor": "#3b82f6"
    };
    for (let [keyword, col] of Object.entries(defectColors)) {
      if (l.includes(keyword)) return col;
    }
    return "#d1d5db";
  }

  function setStage(stage) {
    currentStage = stage;
    if (btnStageNone && btnStagePre && btnStagePost) {
      btnStageNone.classList.remove('btn-pill-active');
      btnStagePre.classList.remove('btn-pill-active');
      btnStagePost.classList.remove('btn-pill-active');
      if (stage === 'pre') {
        btnStagePre.classList.add('btn-pill-active');
        if (stageLabel) stageLabel.textContent = "Stage: Pre wash";
      } else if (stage === 'post') {
        btnStagePost.classList.add('btn-pill-active');
        if (stageLabel) stageLabel.textContent = "Stage: Post wash";
      } else {
        btnStageNone.classList.add('btn-pill-active');
        if (stageLabel) stageLabel.textContent = "Stage: none";
      }
    }
  }

  function setView(view) {
    currentView = view;
    if (btnViewExterior && btnViewInterior && viewLabel) {
      btnViewExterior.classList.remove('btn-pill-active');
      btnViewInterior.classList.remove('btn-pill-active');
      if (view === 'exterior') {
        btnViewExterior.classList.add('btn-pill-active');
        viewLabel.textContent = 'View: Exterior';
      } else if (view === 'interior') {
        btnViewInterior.classList.add('btn-pill-active');
        viewLabel.textContent = 'View: Interior';
      } else {
        viewLabel.textContent = 'View: none';
      }
    }
    if (currentSessionId && view) {
      sendSessionCommand('set-view-type', { view_type: view });
    }
  }

  function updateContaminationScale(level) {
    const n = Math.min(9, Math.max(1, level || 1));
    const boxes = document.querySelectorAll('.cont-box-vertical');
    const totalHeight = 180;
    const barHeight = totalHeight / 9;
    boxes.forEach((box) => {
      const lv = parseInt(box.getAttribute('data-level'), 10);
      box.style.height = barHeight + 'px';
      if (lv <= n) {
        box.classList.add('active');
        const hue = 120 * (1 - (lv - 1) / 8);
        box.style.backgroundColor = `hsl(${hue}, 100%, 40%)`;
      } else {
        box.classList.remove('active');
        box.style.backgroundColor = '#b9c2d0';
      }
    });
    if (contScaleValueText) contScaleValueText.textContent = n + ' / 9';
    if (contaminationScore) contaminationScore.textContent = n + '/9';
  }

  function updateInspectionTable(detections) {
    const classScores = {};
    REFINED_CONTAINER_CLASSES.forEach(cls => classScores[cls] = 0);
    detections.forEach(det => {
      const label = det.label || det.class_name || '';
      const refined = mapToRefinedClass(label);
      if (refined && classScores.hasOwnProperty(refined)) {
        if (det.confidence > classScores[refined]) {
          classScores[refined] = det.confidence;
        }
      }
    });
    const rows = document.querySelectorAll('#inspectionTableBody tr');
    rows.forEach(row => {
      const defectNameCell = row.querySelector('.defect-name');
      if (!defectNameCell) return;
      const defectName = defectNameCell.textContent.trim();
      const score = classScores[defectName] || 0;
      const severity = Math.round(score * 100);
      const hue = 120 * (1 - score);
      const color = `hsl(${hue}, 100%, 40%)`;
      const preCell = row.cells[1];
      if (preCell) {
        const bar = preCell.querySelector('.severity-slim-bar');
        if (bar) {
          bar.style.width = severity + '%';
          bar.style.backgroundColor = color;
        }
      }
      const afterCell = row.cells[2];
      if (afterCell) {
        const bar = afterCell.querySelector('.severity-slim-bar');
        if (bar) {
          bar.style.width = '0%';
          bar.style.backgroundColor = '#b9c2d0';
        }
      }
    });
  }

  function updateStatsAndPie(detections, contaminationIndex) {
    const classCounts = {};
    REFINED_CONTAINER_CLASSES.forEach(cls => classCounts[cls] = 0);
    let totalDefects = 0;
    let structuralIssues = 0;
    detections.forEach(det => {
      const label = det.label || det.class_name || '';
      const refined = mapToRefinedClass(label);
      if (refined && classCounts.hasOwnProperty(refined)) {
        classCounts[refined]++;
        totalDefects++;
        if (refined === "Floor Structural Damage") structuralIssues++;
      }
    });
    if (totalDefectsSpan) totalDefectsSpan.textContent = totalDefects;
    if (structuralIssuesSpan) structuralIssuesSpan.textContent = structuralIssues;
    let cleanliness = 100;
    if (contaminationIndex >= 1) {
      cleanliness = Math.max(0, 100 - contaminationIndex * 10);
    }
    if (cleanlinessSpan) cleanlinessSpan.textContent = cleanliness + '%';

    const piePlaceholder = document.querySelector('.pie-chart-placeholder');
    if (!piePlaceholder) return;
    const existingCanvas = piePlaceholder.querySelector('canvas');
    if (existingCanvas) existingCanvas.remove();
    const staticPie = piePlaceholder.querySelector('.pie');
    if (staticPie) staticPie.remove();
    const oldLegend = piePlaceholder.querySelector('.pie-legend');
    if (oldLegend) oldLegend.remove();

    const pieCanvas = document.createElement('canvas');
    pieCanvas.width = 120;
    pieCanvas.height = 120;
    pieCanvas.style.display = 'block';
    pieCanvas.style.margin = '0 auto';
    piePlaceholder.appendChild(pieCanvas);
    const pCtx = pieCanvas.getContext('2d');
    const centerX = 60, centerY = 60, radius = 50;
    const activeClasses = REFINED_CONTAINER_CLASSES.filter(cls => classCounts[cls] > 0);

    if (activeClasses.length === 0) {
      pCtx.beginPath();
      pCtx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
      pCtx.fillStyle = '#e0e0e0';
      pCtx.fill();
      pCtx.strokeStyle = '#aaa';
      pCtx.lineWidth = 1;
      pCtx.stroke();
    } else {
      let startAngle = 0;
      activeClasses.forEach(cls => {
        const count = classCounts[cls];
        const sliceAngle = (count / totalDefects) * 2 * Math.PI;
        pCtx.beginPath();
        pCtx.moveTo(centerX, centerY);
        pCtx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        pCtx.closePath();
        pCtx.fillStyle = colorForCategory(null, cls);
        pCtx.fill();
        startAngle += sliceAngle;
      });
      pCtx.beginPath();
      pCtx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
      pCtx.strokeStyle = '#aaa';
      pCtx.lineWidth = 1;
      pCtx.stroke();
    }

    const legendDiv = document.createElement('div');
    legendDiv.className = 'pie-legend';
    legendDiv.style.display = 'flex';
    legendDiv.style.flexWrap = 'wrap';
    legendDiv.style.justifyContent = 'center';
    legendDiv.style.marginTop = '10px';
    legendDiv.style.gap = '8px';
    legendDiv.style.fontSize = '11px';

    if (activeClasses.length === 0) {
      const noDefectsItem = document.createElement('span');
      noDefectsItem.textContent = 'No defects';
      noDefectsItem.style.color = '#666';
      legendDiv.appendChild(noDefectsItem);
    } else {
      activeClasses.forEach(cls => {
        const item = document.createElement('span');
        item.style.display = 'inline-flex';
        item.style.alignItems = 'center';
        item.style.gap = '4px';
        const colorBox = document.createElement('span');
        colorBox.style.width = '12px';
        colorBox.style.height = '12px';
        colorBox.style.backgroundColor = colorForCategory(null, cls);
        colorBox.style.borderRadius = '2px';
        const label = document.createElement('span');
        label.textContent = cls;
        item.appendChild(colorBox);
        item.appendChild(label);
        legendDiv.appendChild(item);
      });
    }
    piePlaceholder.appendChild(legendDiv);
  }

  function updateSummaryFromResponse(data) {
    if (!data) return;
    if (summaryContainerId) summaryContainerId.textContent = data.container_id || "—";
    if (summaryContainerType) summaryContainerType.textContent = data.container_type || "—";
    if (summaryStatusBadge) {
      summaryStatusBadge.className = "badge";
      if (data.status === "alert") {
        summaryStatusBadge.classList.add("badge-status-alert");
        summaryStatusBadge.innerHTML = '<i class="fas fa-exclamation-circle"></i> Status: ALERT';
      } else {
        summaryStatusBadge.classList.add("badge-status-ok");
        summaryStatusBadge.innerHTML = '<i class="fas fa-check-circle"></i> Status: OK';
      }
    }
    if (summaryStageBadge) {
      summaryStageBadge.className = "badge badge-stage";
      let stageText = "—";
      if (data.inspection_stage === "pre") stageText = "Pre wash";
      if (data.inspection_stage === "post") stageText = "Post wash";
      summaryStageBadge.innerHTML = `<i class="fas fa-tint"></i> Stage: ${stageText}`;
    }
    if (summaryPeopleBadge) {
      summaryPeopleBadge.className = "badge badge-muted";
      summaryPeopleBadge.innerHTML = `<i class="fas fa-user"></i> Person: ${data.people_nearby ? "Yes" : "No"}`;
    }
    if (summaryDoorBadge) {
      summaryDoorBadge.className = "badge badge-muted";
      let doorText = "Unknown";
      if (data.door_status === "open") doorText = "Open";
      else if (data.door_status === "closed") doorText = "Closed";
      summaryDoorBadge.innerHTML = `<i class="fas fa-door-open"></i> Doors: ${doorText}`;
    }
    if (summaryAnomBadge) {
      summaryAnomBadge.className = "badge badge-muted";
      summaryAnomBadge.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Anomalies: ${data.anomalies_present ? "Yes" : "No"}`;
    }
    updateContaminationScale(data.contamination_index || 1);
  }

  // ---------- Drawing functions (only for images) ----------
  function drawDetection(ctx, det, idx, options = {}) {
    if (!ctx) return;
    const { isImage } = options;
    let points = null;
    let box = null;
    if (det.corners && Array.isArray(det.corners) && det.corners.length >= 3) {
      points = det.corners.map(p => {
        let x = p[0];
        let y = p[1];
        if (isImage && currentImageObject) {
          const imgW = currentImageObject.width;
          const imgH = currentImageObject.height;
          const scaleX = imageDrawWidth / imgW;
          const scaleY = imageDrawHeight / imgH;
          x = imageOffsetX + x * scaleX;
          y = imageOffsetY + y * scaleY;
        }
        return { x, y };
      });
    } else if (det.bbox) {
      box = { ...det.bbox };
      if (isImage && currentImageObject) {
        const imgW = currentImageObject.width;
        const imgH = currentImageObject.height;
        const scaleX = imageDrawWidth / imgW;
        const scaleY = imageDrawHeight / imgH;
        box = {
          x: imageOffsetX + box.x * scaleX,
          y: imageOffsetY + box.y * scaleY,
          w: box.w * scaleX,
          h: box.h * scaleY
        };
      }
    } else {
      return;
    }

    const color = colorForCategory(det.category, det.label || det.class_name) || '#ffffff';
    if (points) {
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.closePath();
      const r = parseInt(color.slice(1, 3), 16);
      const g = parseInt(color.slice(3, 5), 16);
      const b = parseInt(color.slice(5, 7), 16);
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.4)`;
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.stroke();
      if (det.model_source === 'General') {
        const xs = points.map(p => p.x);
        const ys = points.map(p => p.y);
        const minX = Math.min(...xs);
        const minY = Math.min(...ys);
        const idPart = (det.container_id && det.container_id !== 'UNKNOWN') ? det.container_id : 'UNKNOWN';
        const isoPart = det.iso_type ? ` | ${det.iso_type}` : '';
        const idText = idPart + isoPart;
        ctx.font = "bold 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
        const tw = ctx.measureText(idText).width + 16;
        const th = 24;
        let tx = minX;
        let ty = minY - th - 4;
        if (ty < 0) ty = minY + 4;
        if (tx + tw > canvas.width) tx = canvas.width - tw - 4;
        ctx.fillStyle = "rgba(0, 0, 0, 0.8)";
        ctx.fillRect(tx, ty, tw, th);
        ctx.fillStyle = "#ffff00";
        ctx.fillText(idText, tx + 8, ty + th - 6);
      }
    } else if (box) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.strokeRect(box.x, box.y, box.w, box.h);
      const text = "#" + (idx + 1) + " " + (det.legend || det.label || det.class_name || "");
      ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      const tw = ctx.measureText(text).width + 8;
      const th = 18;
      let tx = box.x;
      let ty = box.y - th - 2;
      if (ty < 0) ty = box.y + box.h + 2;
      if (tx + tw > canvas.width) tx = canvas.width - tw - 2;
      ctx.fillStyle = "rgba(0,0,0,0.85)";
      ctx.fillRect(tx, ty, tw, th);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(text, tx + 4, ty + th - 5);
    }
  }

  function drawDetections(detList) {
    if (!ctx) return;
    const isImage = video.dataset.isImage === 'true';
    if (!isImage) return; // videos are drawn by backend stream
    if (!canvas.width || !canvas.height) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (isImage && currentImageObject) {
      ctx.drawImage(
        currentImageObject,
        0, 0, currentImageObject.width, currentImageObject.height,
        imageOffsetX, imageOffsetY, imageDrawWidth, imageDrawHeight
      );
    }
    ctx.lineWidth = 3;
    detList.forEach((det, idx) => {
      drawDetection(ctx, det, idx, { isImage: true });
    });
  }

  // ---------- Analysis for images ----------
  async function analyzeCurrentFrame() {
    if (analyzing) return;
    const isImage = video.dataset.isImage === 'true';
    if (!isImage) return;
    if (!currentImageObject) return;

    analyzing = true;
    if (btnAnalyze) btnAnalyze.disabled = true;
    updateBackendStatus("analyzing...", true);

    try {
      const snapCanvas = document.createElement("canvas");
      snapCanvas.width = currentImageObject.width;
      snapCanvas.height = currentImageObject.height;
      const sctx = snapCanvas.getContext("2d");
      sctx.drawImage(currentImageObject, 0, 0);
      const blob = await new Promise((resolve) => snapCanvas.toBlob(resolve, "image/jpeg", 0.9));
      if (!blob) throw new Error("Failed to create image blob");

      const fd = new FormData();
      fd.append("image", blob, "frame.jpg");
      const damageSensitivity = damageSensitivitySelect ? damageSensitivitySelect.value : "medium";
      const spotMode = spotModeSelect ? spotModeSelect.value : "auto";

      let url = `${API_BASE}/api/analyze/?auto_save=false&damage_sensitivity=${encodeURIComponent(damageSensitivity)}&spot_mode=${encodeURIComponent(spotMode)}`;
      if (currentStage) url += `&inspection_stage=${encodeURIComponent(currentStage)}`;
      if (currentView) url += `&view_type=${encodeURIComponent(currentView)}`;

      const resp = await fetch(url, { method: "POST", body: fd });
      if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
      const data = await resp.json();

      lastAnalysisResult = data;
      lastDetections = data.detections || [];

      // Enable both buttons
      if (btnSaveToDatabase) {
        btnSaveToDatabase.disabled = false;
        btnSaveToDatabase.removeAttribute('disabled');
        console.log("Save button enabled");
      }
      if (btnDownloadReport) {
        btnDownloadReport.disabled = false;
        btnDownloadReport.removeAttribute('disabled');
        console.log("Download button enabled");
      }

      drawDetections(lastDetections);
      updateSummaryFromResponse(data);
      updateInspectionTable(lastDetections);
      updateStatsAndPie(lastDetections, data.contamination_index || 1);
      updateBackendStatus("Analysis complete", true);
    } catch (err) {
      console.error('❌ Analysis failed:', err);
      updateBackendStatus("Analysis error", false);
    } finally {
      analyzing = false;
      if (btnAnalyze) btnAnalyze.disabled = false;
    }
  }

  // ---------- Video session management ----------
  async function startVideoSession() {
    if (!currentVideoFile) {
      alert('No video file selected.');
      return;
    }
    if (!currentStage || currentStage === 'none') {
      alert('Please select an inspection stage (Pre wash or Post wash).');
      return;
    }
    if (!currentView) {
      alert('Please select a view type (Exterior or Interior).');
      return;
    }

    const formData = new FormData();
    formData.append('video', currentVideoFile);
    const url = `${API_BASE}/video-session/start?detection_interval=3&use_fp16=true&initial_view_type=${encodeURIComponent(currentView)}&inspection_stage=${encodeURIComponent(currentStage)}`;

    try {
      updateBackendStatus('Starting video session...', true);
      const response = await fetch(url, { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Failed to start session');
      const data = await response.json();
      currentSessionId = data.session_id;

      mjpegImg.src = data.stream_url;
      mjpegImg.style.display = 'block';
      video.style.display = 'none';
      canvas.style.display = 'none';

      if (btnStop) btnStop.disabled = false;
      if (btnPause) btnPause.disabled = false;
      if (btnPlay) btnPlay.disabled = false;
      if (btnAnalyze) btnAnalyze.disabled = true;

      startPollingDetections();
      updateBackendStatus('Streaming', true);
    } catch (err) {
      console.error('Failed to start video session:', err);
      updateBackendStatus('Session failed', false);
      alert('Error starting video: ' + err.message);
      currentSessionId = null;
      if (btnAnalyze) btnAnalyze.disabled = false;
    }
  }

  function stopVideoSession() {
    if (currentSessionId) {
      fetch(`${API_BASE}/video-session/${currentSessionId}`, { method: 'DELETE', keepalive: true }).catch(() => {});
      currentSessionId = null;
    }
    stopPollingDetections();
    mjpegImg.src = '';
    mjpegImg.style.display = 'none';
    if (btnStop) btnStop.disabled = true;
    if (btnPause) btnPause.disabled = true;
    if (btnPlay) btnPlay.disabled = true;
    video.style.display = 'block';
    canvas.style.display = 'block';
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    setView(null);
    setStage(null);
    updateBackendStatus('Session stopped', false);
    if (btnDownloadReport) btnDownloadReport.disabled = true;
    if (btnSaveToDatabase) btnSaveToDatabase.disabled = true;
  }

  async function sendSessionCommand(command, payload = {}) {
    if (!currentSessionId) return;
    try {
      await fetch(`${API_BASE}/video-session/${currentSessionId}/${command}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (err) {
      console.error(`Command ${command} failed:`, err);
    }
  }

  // ---------- Polling for video detections ----------
  function startPollingDetections() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(async () => {
      if (!currentSessionId) return;
      try {
        const resp = await fetch(`${API_BASE}/video-session/${currentSessionId}/latest-detections`);
        if (!resp.ok) throw new Error('Failed to fetch detections');
        const data = await resp.json();
        const detections = data.detections || [];
        const summary = data.summary || {};
        lastDetections = detections;
        updateInspectionTable(detections);
        updateStatsAndPie(detections, summary.contamination_index || 1);
        updateSummaryFromResponse({
          container_id: summary.container_id,
          status: summary.status,
          contamination_index: summary.contamination_index,
          container_type: null,
          inspection_stage: currentStage,
          people_nearby: false,
          door_status: null,
          anomalies_present: summary.total_defects > 0
        });
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 2000);
  }

  function stopPollingDetections() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  // ---------- File input handler ----------
  if (fileInput) {
    fileInput.addEventListener('change', () => {
      const file = fileInput.files[0];
      if (!file) return;

      stopVideoSession();
      stopAutoAnalyze();

      const fileType = file.type;
      if (fileType.startsWith('image/')) {
        // Image mode
        video.pause();
        video.removeAttribute('src');
        video.load();
        video.style.display = 'none';
        canvas.style.display = 'block';
        mjpegImg.style.display = 'none';
        currentVideoFile = null;
        const url = URL.createObjectURL(file);
        currentImageData = file;
        const img = new Image();
        img.onload = () => {
          currentImageObject = img;
          const container = document.querySelector('.video-container');
          if (!container) return;
          const containerWidth = container.clientWidth;
          const containerHeight = container.clientHeight;
          const imgW = img.width;
          const imgH = img.height;
          const scale = Math.min(containerWidth / imgW, containerHeight / imgH);
          imageDrawWidth = imgW * scale;
          imageDrawHeight = imgH * scale;
          imageOffsetX = (containerWidth - imageDrawWidth) / 2;
          imageOffsetY = (containerHeight - imageDrawHeight) / 2;
          canvas.width = containerWidth;
          canvas.height = containerHeight;
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, imgW, imgH, imageOffsetX, imageOffsetY, imageDrawWidth, imageDrawHeight);
          if (btnAnalyze) btnAnalyze.disabled = false;
          video.dataset.imageUrl = url;
          video.dataset.isImage = 'true';
          URL.revokeObjectURL(url);
          setView(null);
        };
        img.src = url;
      } else if (fileType.startsWith('video/')) {
        // Video mode: show first frame on canvas
        video.style.display = 'none';
        canvas.style.display = 'block';
        mjpegImg.style.display = 'none';
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const tempVideo = document.createElement('video');
        tempVideo.preload = 'auto';
        tempVideo.muted = true;
        tempVideo.playsInline = true;
        tempVideo.src = URL.createObjectURL(file);
        tempVideo.addEventListener('loadeddata', () => {
          tempVideo.currentTime = 0;
        });
        tempVideo.addEventListener('seeked', () => {
          const container = document.querySelector('.video-container');
          if (container) {
            const containerWidth = container.clientWidth;
            const containerHeight = container.clientHeight;
            const videoWidth = tempVideo.videoWidth;
            const videoHeight = tempVideo.videoHeight;
            const scale = Math.min(containerWidth / videoWidth, containerHeight / videoHeight);
            const drawWidth = videoWidth * scale;
            const drawHeight = videoHeight * scale;
            const offsetX = (containerWidth - drawWidth) / 2;
            const offsetY = (containerHeight - drawHeight) / 2;
            canvas.width = containerWidth;
            canvas.height = containerHeight;
            ctx.drawImage(tempVideo, 0, 0, videoWidth, videoHeight, offsetX, offsetY, drawWidth, drawHeight);
          }
          URL.revokeObjectURL(tempVideo.src);
          tempVideo.remove();
        });

        currentVideoFile = file;
        currentImageData = null;
        currentImageObject = null;
        lastDetections = [];
        lastAnalysisResult = null;
        updateInspectionTable([]);
        updateStatsAndPie([], 1);
        updateSummaryFromResponse({});
        if (btnAnalyze) btnAnalyze.disabled = false;
        video.dataset.isImage = 'false';
        setView(null);
        updateBackendStatus('Video ready. Select options and click Analyze.', true);
      } else {
        alert('Unsupported file type. Please select an image or video.');
      }

      if (btnDownloadReport) btnDownloadReport.disabled = true;
      if (btnSaveToDatabase) btnSaveToDatabase.disabled = true;
    });
  }

  // ---------- Button listeners ----------
  if (btnPlay) {
    btnPlay.addEventListener('click', () => {
      if (currentSessionId) {
        sendSessionCommand('resume');
        startPollingDetections();
      }
    });
  }

  if (btnPause) {
    btnPause.addEventListener('click', () => {
      if (currentSessionId) {
        sendSessionCommand('pause');
        stopPollingDetections();
      }
    });
  }

  if (btnStop) {
    btnStop.addEventListener('click', () => {
      stopVideoSession();
      if (fileInput) fileInput.value = '';
      if (btnAnalyze) btnAnalyze.disabled = true;
    });
  }

  if (btnAnalyze) {
    btnAnalyze.addEventListener('click', () => {
      if (currentVideoFile) {
        startVideoSession();
      } else {
        analyzeCurrentFrame();
      }
    });
  }

  if (btnStageNone) btnStageNone.addEventListener('click', () => setStage(null));
  if (btnStagePre) btnStagePre.addEventListener('click', () => setStage('pre'));
  if (btnStagePost) btnStagePost.addEventListener('click', () => setStage('post'));
  if (btnViewExterior) btnViewExterior.addEventListener('click', () => setView('exterior'));
  if (btnViewInterior) btnViewInterior.addEventListener('click', () => setView('interior'));

  // Download report
  if (btnDownloadReport) {
    btnDownloadReport.addEventListener('click', async () => {
      if (!lastAnalysisResult) {
        alert('No analysis data available. Please analyze an image first.');
        return;
      }
      try {
        updateBackendStatus('Generating PDF report...', true);
        const formData = new FormData();
        formData.append('analysis_data', JSON.stringify(lastAnalysisResult));
        const isImage = video.dataset.isImage === 'true';
        if (isImage && canvas.width > 0) {
          const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.95));
          if (blob) formData.append('image', blob, 'analyzed_image.jpg');
        }
        const response = await fetch(`${API_BASE}/api/analyze/generate-report`, { method: 'POST', body: formData });
        if (!response.ok) throw new Error('Failed to generate report');
        const pdfBlob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(pdfBlob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `Live_Analysis_Report_${lastAnalysisResult.container_id || 'UNKNOWN'}_${Date.now()}.pdf`;
        if (contentDisposition) {
          const match = contentDisposition.match(/filename="?(.+)"?/i);
          if (match) filename = match[1];
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        updateBackendStatus('Report downloaded successfully', true);
      } catch (err) {
        console.error('Failed to generate report:', err);
        updateBackendStatus('Failed to generate report', false);
        alert('Failed to generate report: ' + err.message);
      }
    });
  }

  // Save to database (single, correct handler)
  if (btnSaveToDatabase) {
    btnSaveToDatabase.addEventListener('click', async () => {
      if (!lastAnalysisResult || !currentImageData) {
        alert("No analysis data or image available to save.");
        return;
      }

      btnSaveToDatabase.disabled = true;
      const originalText = btnSaveToDatabase.innerHTML;
      btnSaveToDatabase.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

      try {
        const fd = new FormData();
        fd.append("analysis_data", JSON.stringify(lastAnalysisResult));
        fd.append("image", currentImageData);

        const response = await fetch(`${API_BASE}/api/analyze/save-analysis`, {
          method: 'POST',
          body: fd
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);

        updateBackendStatus("Analysis saved to database!", true);
        btnSaveToDatabase.innerHTML = '<i class="fas fa-check"></i> Saved!';

        // Refresh recent inspections
        await loadRecentInspections();

        setTimeout(() => {
          btnSaveToDatabase.innerHTML = originalText;
          btnSaveToDatabase.disabled = false;
        }, 3000);
      } catch (err) {
        console.error('❌ Save failed:', err);
        updateBackendStatus("Save failed", false);
        btnSaveToDatabase.disabled = false;
        btnSaveToDatabase.innerHTML = originalText;
        alert("Error saving to database. Check console for details.");
      }
    });
  }

  // Auto analyze (images only)
  if (btnAuto) {
    btnAuto.addEventListener('click', () => {
      autoAnalyze = !autoAnalyze;
      if (autoAnalyze) {
        btnAuto.textContent = "Auto: on";
        btnAuto.classList.remove("secondary");
        startAutoAnalyze();
      } else {
        btnAuto.textContent = "Auto: off";
        btnAuto.classList.add("secondary");
        stopAutoAnalyze();
      }
    });
  }

  function startAutoAnalyze() {
    if (autoTimer) return;
    autoTimer = setInterval(() => {
      if (video && video.dataset.isImage === 'true' && !video.paused) {
        analyzeCurrentFrame();
      }
    }, 2000);
  }

  function stopAutoAnalyze() {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
  }

  // ========== Recent Inspections Table ==========
  async function loadRecentInspections() {
    const tbody = document.getElementById('recentFilesBody');
    if (!tbody) return;

    try {
      const response = await fetch(`${API_BASE}/api/history/?page=1&page_size=4`);
      if (!response.ok) throw new Error('Failed to fetch recent inspections');
      const data = await response.json();
      const inspections = data.items || [];

      tbody.innerHTML = '';

      if (inspections.length === 0) {
        for (let i = 0; i < 4; i++) {
          tbody.appendChild(createPlaceholderRow());
        }
      } else {
        inspections.forEach(insp => tbody.appendChild(createInspectionRow(insp)));
        for (let i = inspections.length; i < 4; i++) {
          tbody.appendChild(createPlaceholderRow());
        }
      }
    } catch (err) {
      console.error('Error loading recent inspections:', err);
      tbody.innerHTML = `<tr><td colspan="3" style="color:red;">Failed to load</td></tr>`;
    }
  }

  function createInspectionRow(insp) {
    const row = document.createElement('tr');
    const containerId = insp.container_id || '—';
    const timestamp = insp.timestamp ? new Date(insp.timestamp).toLocaleString() : '—';
    const status = insp.status || 'ok';
    const isAlert = status === 'alert';
    const badgeClass = isAlert ? 'badge-status-alert' : 'badge-status-ok';
    const icon = isAlert ? 'fa-exclamation-circle' : 'fa-check-circle';
    const statusText = isAlert ? 'ALERT' : 'OK';

    row.innerHTML = `
      <td>${containerId}</td>
      <td>${timestamp}</td>
      <td><span class="badge ${badgeClass}"><i class="fas ${icon}"></i> ${statusText}</span></td>
    `;
    return row;
  }

  function createPlaceholderRow() {
    const row = document.createElement('tr');
    row.innerHTML = `<td>—</td><td>—</td><td><span class="badge">—</span></td>`;
    return row;
  }

  // ---------- Initialization ----------
  fetch(API_BASE + "/api/analyze", { method: "OPTIONS" })
    .then(() => updateBackendStatus("reachable", true))
    .catch(() => updateBackendStatus("unreachable", false));

  updateContaminationScale(1);
  setStage(null);
  setView(null);
  if (btnDownloadReport) btnDownloadReport.disabled = true;
  if (btnSaveToDatabase) btnSaveToDatabase.disabled = true;

  loadRecentInspections();

  window.addEventListener('beforeunload', () => {
    if (currentSessionId) {
      fetch(`${API_BASE}/video-session/${currentSessionId}`, { method: 'DELETE', keepalive: true });
    }
  });
});