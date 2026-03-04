/**
 * UI.js - DOM Manipulation and Visual Updates
 * Handles all visual updates to the dashboard
 */

class UI {
  constructor() {
    this.canvas = document.getElementById('overlay');
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.video = document.getElementById('video');
    this.lastDetections = [];
  }

  /**
   * Initialize UI components
   */
  init() {
    // Set up canvas resize observer
    if (this.video && this.canvas) {
      const resizeCanvas = () => {
        if (this.video.videoWidth && this.video.videoHeight) {
          this.canvas.width = this.video.videoWidth;
          this.canvas.height = this.video.videoHeight;
          this.redrawDetections();
        }
      };

      this.video.addEventListener('loadedmetadata', resizeCanvas);
      window.addEventListener('resize', resizeCanvas);
    }
  }

  /**
   * Update backend status indicator
   */
  updateBackendStatus(online, message = '') {
    const statusEl = document.getElementById('backendStatus');
    if (!statusEl) return;

    statusEl.textContent = message || (online ? 'online' : 'offline');
    statusEl.className = online ? 'online' : 'offline';
  }

  /**
   * Update learning mode badge
   */
  updateLearningBadge(enabled) {
    const badge = document.getElementById('learningBadge');
    if (!badge) return;

    if (enabled) {
      badge.textContent = 'LEARNING MODE ON';
      badge.className = 'badge-learning badge-learning-on';
    } else {
      badge.textContent = 'LEARNING MODE OFF';
      badge.className = 'badge-learning badge-learning-off';
    }
  }

  /**
   * Update container summary section
   */
  updateSummary(data) {
    // Container ID
    const containerIdEl = document.getElementById('summaryContainerId');
    if (containerIdEl) {
      containerIdEl.textContent = `Container ID: ${data.container_id || 'UNKNOWN'}`;
    }

    // Container Type
    const containerTypeEl = document.getElementById('summaryContainerType');
    if (containerTypeEl) {
      containerTypeEl.textContent = `Type: ${data.container_type || 'Unknown type'}`;
    }

    // Status Badge
    const statusBadge = document.getElementById('summaryStatusBadge');
    if (statusBadge) {
      statusBadge.className = 'badge';
      if (data.status === 'alert') {
        statusBadge.classList.add('badge-status-alert');
        statusBadge.textContent = 'Status: ALERT';
      } else {
        statusBadge.classList.add('badge-status-ok');
        statusBadge.textContent = 'Status: OK';
      }
    }

    // Stage Badge
    const stageBadge = document.getElementById('summaryStageBadge');
    if (stageBadge) {
      stageBadge.className = 'badge badge-stage';
      let stageText = '–';
      if (data.inspection_stage === 'pre') stageText = 'Pre wash';
      if (data.inspection_stage === 'post') stageText = 'Post wash';
      stageBadge.textContent = `Stage: ${stageText}`;
    }

    // People Badge
    const peopleBadge = document.getElementById('summaryPeopleBadge');
    if (peopleBadge) {
      peopleBadge.className = 'badge badge-muted';
      peopleBadge.textContent = data.people_nearby
        ? 'Person nearby: Yes'
        : 'Person nearby: No';
    }

    // Door Badge
    const doorBadge = document.getElementById('summaryDoorBadge');
    if (doorBadge) {
      doorBadge.className = 'badge badge-muted';
      if (data.door_status === 'open') {
        doorBadge.textContent = 'Doors: Open';
      } else if (data.door_status === 'closed') {
        doorBadge.textContent = 'Doors: Closed';
      } else {
        doorBadge.textContent = 'Doors: Unknown';
      }
    }

    // Anomalies Badge
    const anomBadge = document.getElementById('summaryAnomBadge');
    if (anomBadge) {
      anomBadge.className = 'badge badge-muted';
      anomBadge.textContent = data.anomalies_present
        ? 'Anomalies: Yes'
        : 'Anomalies: No';
    }
  }

  /**
   * Update contamination scale (1-9)
   */
  updateContaminationScale(level) {
    const n = Math.min(9, Math.max(1, level || 1));
    const contScaleBar = document.getElementById('contScaleBar');
    const contScaleValueText = document.getElementById('contScaleValueText');

    if (contScaleValueText) {
      contScaleValueText.textContent = `${n} / 9`;
    }

    if (!contScaleBar) return;

    const boxes = contScaleBar.querySelectorAll('.cont-box');
    boxes.forEach((box) => {
      const lv = parseInt(box.getAttribute('data-level'), 10);
      if (lv <= n) {
        box.classList.add('active');
        const color = this.getLevelColor(lv);
        box.style.background = color;
        box.style.borderColor = color;
      } else {
        box.classList.remove('active');
        box.style.background = 'var(--bg-dark)';
        box.style.borderColor = 'var(--gray-border)';
      }
    });
  }

  /**
   * Get color for contamination level (1=green, 9=red)
   */
  getLevelColor(level) {
    const hue = ((9 - level) / 8) * 120; // 120=green, 0=red
    return `hsl(${hue}, 80%, 55%)`;
  }

  /**
   * Update prewash and resolved lists
   */
  updatePrewashResolved(prewashItems, resolvedItems) {
    const prewashList = document.getElementById('prewashList');
    const prewashInfo = document.getElementById('prewashInfo');
    const resolvedList = document.getElementById('resolvedList');
    const resolvedInfo = document.getElementById('resolvedInfo');

    this.buildWashList(prewashList, prewashInfo, prewashItems, 'No PreWash inspection yet.');
    this.buildWashList(resolvedList, resolvedInfo, resolvedItems, 'Nothing resolved yet.');
  }

  /**
   * Build wash list (prewash or resolved)
   */
  buildWashList(listEl, infoEl, items, emptyText) {
    if (!listEl || !infoEl) return;

    listEl.innerHTML = '';
    
    if (!items || items.length === 0) {
      infoEl.textContent = emptyText;
      return;
    }

    infoEl.textContent = '';

    // Group by type
    const damageItems = [];
    const dirtItems = [];
    const otherItems = [];

    items.forEach((item) => {
      const { group, severity } = this.classifyDiffItem(item);
      if (group === 'damage') damageItems.push({ item, severity });
      else if (group === 'dirt') dirtItems.push({ item, severity });
      else otherItems.push({ item, severity });
    });

    // Render groups
    this.renderWashGroup(listEl, 'Damage', damageItems);
    this.renderWashGroup(listEl, 'Dirt / loose objects / discoloration', dirtItems);
    this.renderWashGroup(listEl, 'Other', otherItems);
  }

  /**
   * Render a wash group
   */
  renderWashGroup(listEl, label, bucket) {
    if (!bucket.length) return;

    const header = document.createElement('div');
    header.className = 'wash-category-label';
    header.textContent = label;
    listEl.appendChild(header);

    bucket.forEach(({ item, severity }) => {
      const li = document.createElement('li');
      const row = document.createElement('div');
      row.className = 'wash-item';

      const dot = document.createElement('div');
      dot.className = `severity-dot severity-${severity}`;

      const textBox = document.createElement('div');
      const main = document.createElement('div');
      main.className = 'wash-item-text-main';
      main.textContent = item.label || 'Unknown';

      const sub = document.createElement('div');
      sub.className = 'wash-item-text-sub';
      const catText = item.category ? `Category: ${item.category}` : '';
      const sevText = `Severity: ${this.getSeverityLabel(severity)}`;
      sub.textContent = catText ? `${catText} | ${sevText}` : sevText;

      textBox.appendChild(main);
      textBox.appendChild(sub);

      row.appendChild(dot);
      row.appendChild(textBox);
      li.appendChild(row);
      listEl.appendChild(li);
    });
  }

  /**
   * Classify diff item
   */
  classifyDiffItem(item) {
    const cat = (item.category || '').toLowerCase();
    const label = (item.label || '').toLowerCase();
    let group = 'other';
    let severity = 'low';

    if (cat === 'damage' || label.startsWith('damage')) {
      group = 'damage';
      severity = 'high';
    } else if (
      label.includes('dirt') ||
      label.includes('smuts') ||
      label.includes('loose object') ||
      label.includes('looseobject') ||
      label.includes('löst föremål') ||
      label.includes('discoloration') ||
      label.includes('missfärgning') ||
      label.includes('dark spot') ||
      label.includes('mold') ||
      label.includes('mould')
    ) {
      group = 'dirt';
      severity = 'medium';
    }

    return { group, severity };
  }

  /**
   * Get severity label
   */
  getSeverityLabel(sev) {
    if (sev === 'high') return 'High (damage)';
    if (sev === 'medium') return 'Medium (dirt/object)';
    return 'Low';
  }

  /**
   * Update detections table
   */
  updateDetectionsTable(detections, onDeleteCallback) {
    const tbody = document.getElementById('detectionsBody');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (!detections || detections.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="color:var(--gray-soft);">No detections</td></tr>';
      return;
    }

    detections.forEach((det, idx) => {
      const tr = document.createElement('tr');
      tr.onclick = () => this.highlightDetection(idx);

      const confText = det.confidence != null
        ? `${(det.confidence * 100).toFixed(1)}%`
        : '-';

      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td>${det.legend || det.label || ''}</td>
        <td>${det.label || ''}</td>
        <td>${det.category || ''}</td>
        <td>${confText}</td>
        <td>
          <button 
            data-del="${idx}" 
            style="color:#f87171;background:none;border:none;cursor:pointer;padding:2px 6px;font-size:14px;"
            title="Mark as ignore">
            ✕
          </button>
        </td>
      `;

      // Add delete handler
      const delBtn = tr.querySelector('[data-del]');
      if (delBtn && onDeleteCallback) {
        delBtn.onclick = (e) => {
          e.stopPropagation();
          onDeleteCallback(idx);
        };
      }

      tbody.appendChild(tr);
    });
  }

  /**
   * Draw detections on canvas overlay
   */
  drawDetections(detections) {
    if (!this.ctx || !this.video || !this.video.videoWidth) return;

    this.lastDetections = detections || [];

    this.canvas.width = this.video.videoWidth;
    this.canvas.height = this.video.videoHeight;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    if (!detections || detections.length === 0) return;

    this.ctx.lineWidth = 2;

    detections.forEach((det, idx) => {
      if (!det.bbox) return;

      const box = det.bbox;
      const color = this.getColorForCategory(det.category, det.label);

      // Draw rectangle
      this.ctx.strokeStyle = color;
      this.ctx.strokeRect(box.x, box.y, box.w, box.h);

      // Draw label
      const text = `#${idx + 1} ${det.legend || det.label || ''}`;
      this.ctx.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      const tw = this.ctx.measureText(text).width + 6;
      const th = 16;

      let tx = box.x;
      let ty = box.y - th - 2;
      if (ty < 0) ty = box.y + box.h + 2;
      if (tx + tw > this.canvas.width) tx = this.canvas.width - tw - 2;

      this.ctx.fillStyle = 'rgba(0,0,0,0.75)';
      this.ctx.fillRect(tx, ty, tw, th);
      this.ctx.fillStyle = '#f9fafb';
      this.ctx.fillText(text, tx + 3, ty + th - 4);
    });
  }

  /**
   * Redraw last detections (for resize)
   */
  redrawDetections() {
    this.drawDetections(this.lastDetections);
  }

  /**
   * Highlight a specific detection
   */
  highlightDetection(index) {
    if (!this.lastDetections || !this.lastDetections[index]) return;

    // Redraw all with highlighted one
    this.drawDetections(this.lastDetections);

    const det = this.lastDetections[index];
    if (!det.bbox) return;

    const box = det.bbox;
    this.ctx.strokeStyle = '#ffffff';
    this.ctx.lineWidth = 4;
    this.ctx.strokeRect(box.x, box.y, box.w, box.h);
  }

  /**
   * Get color for detection category
   */
  getColorForCategory(cat, label) {
    const c = (cat || '').toLowerCase();
    const l = (label || '').toLowerCase();

    // Special: dark spots / mold
    if (l.includes('dark spot') || l.includes('mold') || l.includes('mould') || l.includes('mögel')) {
      return '#a855f7'; // purple
    }

    if (c === 'damage' || l.startsWith('damage')) return '#ef4444'; // red
    if (
      l.includes('dirt') || l.includes('smuts') ||
      l.includes('looseobject') || l.includes('loose object') ||
      l.includes('löst föremål') ||
      l.includes('discoloration') || l.includes('missfärgning')
    ) return '#eab308'; // yellow
    if (c === 'lock') return '#22c55e'; // green
    if (c === 'door' || c === 'door_open' || c === 'door_closed') return '#e5e7eb'; // light gray
    if (c === 'human') return '#f9fafb'; // white
    return '#d1d5db'; // gray
  }

  /**
   * Show toast notification
   */
  showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠'
    };

    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || '•'}</span>
      <span class="toast-message">${message}</span>
      <button class="toast-close">×</button>
    `;

    container.appendChild(toast);

    // Auto remove
    const timeout = setTimeout(() => {
      toast.style.animation = 'slideIn 0.3s ease reverse';
      setTimeout(() => toast.remove(), 300);
    }, duration);

    // Manual close
    toast.querySelector('.toast-close').onclick = () => {
      clearTimeout(timeout);
      toast.style.animation = 'slideIn 0.3s ease reverse';
      setTimeout(() => toast.remove(), 300);
    };
  }

  /**
   * Show/hide loading overlay
   */
  setLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;

    if (show) {
      overlay.classList.add('active');
    } else {
      overlay.classList.remove('active');
    }
  }

  /**
   * Set button loading state
   */
  setButtonLoading(button, loading) {
    if (!button) return;

    if (loading) {
      button.disabled = true;
      button.classList.add('loading');
    } else {
      button.disabled = false;
      button.classList.remove('loading');
    }
  }
}

// Export singleton instance
const ui = new UI();
