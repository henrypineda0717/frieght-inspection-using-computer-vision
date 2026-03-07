// history.js – Full integration with original UI and backend
const API_BASE = "http://localhost:8001";
let currentPage = 1;
let totalPages = 1;
let currentInspectionId = null;
let currentInspectionData = null;
let deleteTargetId = null;
let deleteTargetContainerId = null;

// ----- Helper: safe element access -----
function safeGetElement(id) {
    const el = document.getElementById(id);
    if (!el) console.warn(`Element #${id} not found`);
    return el;
}

async function loadStats() {
    try {
        // Use same pagination as loadHistory but with a large page_size to get all items
        // If backend limits page_size, we can request multiple pages, but for now use a safe value
        const resp = await fetch(`${API_BASE}/api/history/?page=1&page_size=100`);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        const data = await resp.json();
        
        // Extract items (handle both paginated response and plain array)
        const items = data.items || data || [];
        
        // Compute statistics
        const totalInspections = items.length;
        const uniqueContainers = new Set(items.map(i => i.container_id).filter(Boolean)).size;
        const totalFrames = items.reduce((sum, i) => sum + (i.frame_count || i.frameCount || 0), 0);
        const totalDetections = items.reduce((sum, i) => sum + (i.detection_count || i.detectionCount || 0), 0);
        const alertCount = items.filter(i => i.status === 'alert').length;

        // Update DOM elements
        const setText = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        };

        setText('statInspections', totalInspections);
        setText('statContainers', uniqueContainers);
        setText('statFrames', totalFrames);
        setText('statDetections', totalDetections);
        setText('statAlerts', alertCount);
        
        console.log('Stats updated:', { totalInspections, uniqueContainers, totalFrames, totalDetections, alertCount });
    } catch (e) {
        console.error('loadStats error:', e);
        // Display dashes on error
        ['statInspections','statContainers','statFrames','statDetections','statAlerts'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '—';
        });
    }
}
// ----- Load history list (with filters & pagination) -----
async function loadHistory() {
    const historyTable = safeGetElement('historyTable');
    if (!historyTable) return;

    const search = safeGetElement('searchInput')?.value || '';
    const status = safeGetElement('statusFilter')?.value || '';
    const stage = safeGetElement('stageFilter')?.value || '';

    let url = `${API_BASE}/api/history/?page=${currentPage}&page_size=20`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (status) url += `&status=${status}`;
    if (stage) url += `&stage=${stage}`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();

        totalPages = Math.ceil(data.total / data.page_size);
        renderHistoryTable(data.items);
        updatePagination();
        loadStats();  // refresh stats after list loads
    } catch (e) {
        console.error('Failed to load history:', e);
        historyTable.innerHTML = '<tr><td colspan="11" style="text-align:center;color:#f87171;">Failed to load history</td></tr>';
    }
}

function renderHistoryTable(items) {
    const tbody = safeGetElement('historyTable');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--gray-soft);">No inspections found</td></tr>';
        return;
    }

    items.forEach(item => {
        const tr = document.createElement('tr');

        const statusBadge = item.status === 'alert'
            ? '<span class="badge badge-alert">Alert</span>'
            : '<span class="badge badge-ok">OK</span>';

        const stageBadge = item.stage
            ? `<span class="badge badge-stage">${item.stage}</span>`
            : '-';

        const timestamp = new Date(item.timestamp).toLocaleString();

        tr.innerHTML = `
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${item.id}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;"><strong>${item.container_id}</strong></td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${item.iso_type || '-'}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${timestamp}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${stageBadge}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${statusBadge}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${item.risk_score}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${item.contamination_index} / 9 (${item.contamination_label})</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${item.frame_count}</td>
            <td onclick="loadDetail(${item.id})" style="cursor:pointer;">${item.detection_count}</td>
            <td>
                <button class="download-btn" onclick="event.stopPropagation(); downloadReport(${item.id}, '${item.container_id}')" title="Download PDF Report">
                    <i class="fas fa-file-pdf"></i>
                </button>
                <button class="delete-btn" onclick="event.stopPropagation(); showDeleteModal(${item.id}, '${item.container_id}')" title="Delete Entry">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function updatePagination() {
    const pageInfo = safeGetElement('pageInfo');
    const btnPrev = safeGetElement('btnPrevPage');
    const btnNext = safeGetElement('btnNextPage');
    if (!pageInfo || !btnPrev || !btnNext) return;

    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    btnPrev.disabled = currentPage <= 1;
    btnNext.disabled = currentPage >= totalPages;
}

function prevPage() { if (currentPage > 1) { currentPage--; loadHistory(); } }
function nextPage() { if (currentPage < totalPages) { currentPage++; loadHistory(); } }

function clearFilters() {
    safeGetElement('searchInput') && (safeGetElement('searchInput').value = '');
    safeGetElement('statusFilter') && (safeGetElement('statusFilter').value = '');
    safeGetElement('stageFilter') && (safeGetElement('stageFilter').value = '');
    currentPage = 1;
    loadHistory();
}

// ----- Cleanup orphaned containers -----
async function cleanupOrphanedContainers() {
    if (!confirm('Remove all containers that have no inspections?')) return;
    try {
        const resp = await fetch(`${API_BASE}/api/history/cleanup/orphaned-containers`, { method: 'POST' });
        if (resp.ok) {
            const data = await resp.json();
            showNotification(data.message, 'success');
            await loadStats();
            await loadHistory();
        } else {
            throw new Error((await resp.json()).detail || 'Cleanup failed');
        }
    } catch (e) {
        console.error('Cleanup failed:', e);
        showNotification('Cleanup failed: ' + e.message, 'error');
    }
}

// ----- Load inspection detail -----
async function loadDetail(inspectionId) {
    currentInspectionId = inspectionId;

    try {
        const resp = await fetch(`${API_BASE}/api/history/${inspectionId}`);
        const data = await resp.json();
        currentInspectionData = data;
        renderDetail(data);

        safeGetElement('listView').style.display = 'none';
        safeGetElement('detailView').style.display = 'block';
    } catch (e) {
        console.error('Failed to load detail:', e);
        alert('Failed to load inspection details');
    }
}

// ----- Render detail view (adapted to original UI) -----
function renderDetail(data) {
    // Helper to set text content
    const setText = (id, text) => {
        const el = safeGetElement(id);
        if (el) el.textContent = text ?? '-';
    };

    // Header
    setText('detailId', data.id);
    setText('detailContainerIdHeader', data.container_id);
    setText('detailTitle', `Inspection #${data.id} — ${data.container_id}`); // fallback

    // Editable fields
    const containerInput = safeGetElement('editContainerId');
    const isoInput = safeGetElement('editIsoType');
    if (containerInput) containerInput.value = data.container_id || '';
    if (isoInput) isoInput.value = data.iso_type || '';

    // Risk & contamination
    setText('summaryRisk', data.risk_score);
    const riskBar = safeGetElement('riskBarFill');
    if (riskBar) {
        const riskPercent = Math.min(data.risk_score, 100);
        riskBar.style.width = riskPercent + '%';
        if (riskPercent < 30) riskBar.style.backgroundColor = '#10b981';
        else if (riskPercent < 70) riskBar.style.backgroundColor = '#f59e0b';
        else riskBar.style.backgroundColor = '#ef4444';
    }

    setText('summaryContamination', `${data.contamination_index} / 9 (${data.contamination_label})`);
    const contScale = document.querySelector('.contamination-scale');
    if (contScale) {
        contScale.innerHTML = '';
        for (let i = 1; i <= 9; i++) {
            const box = document.createElement('div');
            box.style.cssText = `flex:1; height:8px; border-radius:4px; background: ${i <= data.contamination_index ? '#f59e0b' : 'var(--border-light)'};`;
            contScale.appendChild(box);
        }
    }

    setText('summaryPeople', data.people_nearby ? 'Yes' : 'No');
    setText('summaryDoor', data.door_status || 'Unknown');

    // Anomaly summary
    const anomalyContainer = safeGetElement('anomalySummaryContainer');
    const anomalyText = safeGetElement('anomalySummaryText');
    if (anomalyContainer && anomalyText) {
        if (data.anomaly_summary) {
            anomalyText.textContent = data.anomaly_summary;
            anomalyContainer.style.display = 'flex';
        } else {
            anomalyContainer.style.display = 'none';
        }
    }

    // Frame thumbnails
    const frameList = data.frames.map(frame => ({
        ...frame,
        overlayUrl: frame.overlay_path ? `${API_BASE}/api/images/${frame.overlay_path}` : null,
        imageUrl: frame.image_path ? `${API_BASE}/api/images/${frame.image_path}` : null
    }));

    const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
    const thumbnailsContainer = document.querySelector('.frame-thumbnails');
    if (!thumbnailsContainer) return;
    thumbnailsContainer.innerHTML = '';

    frameList.forEach((frame, idx) => {
        const thumb = document.createElement('div');
        thumb.className = 'frame-thumb';
        thumb.setAttribute('role', 'button');
        thumb.setAttribute('aria-label', `Show frame ${idx + 1}`);
        thumb.setAttribute('data-frame-idx', idx);

        const thumbImg = document.createElement('img');
        const thumbUrl = frame.overlayUrl || frame.imageUrl || transparentPixel;
        thumbImg.src = thumbUrl;
        if (frame.imageUrl) {
            thumbImg.onerror = () => {
                if (thumbImg.dataset.fallback) return;
                thumbImg.dataset.fallback = '1';
                thumbImg.src = frame.imageUrl;
            };
        }
        thumb.appendChild(thumbImg);
        thumb.addEventListener('click', () => showFrame(idx));
        thumbnailsContainer.appendChild(thumb);
    });

    // Show first frame
    let currentFrameIndex = 0;
    const mainImage = safeGetElement('currentFrameImage');
    if (!mainImage) return;

    function showFrame(idx) {
        currentFrameIndex = idx;
        const frame = frameList[idx];
        if (!frame) return;

        mainImage.dataset.fallback = '0';
        mainImage.onerror = () => {
            if (mainImage.dataset.fallback === '1' || !frame.imageUrl) return;
            mainImage.dataset.fallback = '1';
            mainImage.src = frame.imageUrl;
        };

        const targetUrl = frame.overlayUrl || frame.imageUrl;
        if (targetUrl) {
            mainImage.src = targetUrl;
        } else {
            mainImage.removeAttribute('src');
        }

        // Highlight active thumbnail
        document.querySelectorAll('.frame-thumb').forEach((el, i) => {
            el.style.borderColor = i === idx ? 'var(--accent-blue)' : 'transparent';
        });

        // Update defect table for this frame
        renderDetectionsForFrame(frame);
    }

    showFrame(0);
}

// ----- Populate defect table (original table format) -----
function renderDetectionsForFrame(frame) {
    const tbody = safeGetElement('defectTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!frame.detections || frame.detections.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--text-secondary);">No detections in this frame</td></tr>';
        return;
    }

    frame.detections.forEach(det => {
        const tr = document.createElement('tr');
        const severityClass = det.severity === 'high' ? 'badge badge-status-alert' : 'badge badge-muted';
        tr.innerHTML = `
            <td>${det.label}</td>
            <td><span class="${severityClass}" style="border-radius:0;">${det.severity || 'N/A'}</span></td>
            <td>${(det.confidence * 100).toFixed(1)}%</td>
        `;
        tbody.appendChild(tr);
    });
}

function backToList() {
    safeGetElement('listView').style.display = 'block';
    safeGetElement('detailView').style.display = 'none';
    currentInspectionId = null;
    currentInspectionData = null;
}

// ----- Delete modal functions -----
function showDeleteModal(inspectionId, containerId) {
    deleteTargetId = inspectionId;
    deleteTargetContainerId = containerId;
    safeGetElement('deleteInspectionId').textContent = inspectionId;
    safeGetElement('deleteContainerId').textContent = containerId;
    safeGetElement('deleteModal').style.display = 'flex';
    safeGetElement('confirmDeleteBtn').disabled = false;
}

function closeDeleteModal() {
    safeGetElement('deleteModal').style.display = 'none';
    deleteTargetId = null;
    deleteTargetContainerId = null;
}

async function confirmDelete() {
    if (!deleteTargetId) return;
    const deleteBtn = safeGetElement('confirmDeleteBtn');
    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting...';

    try {
        const resp = await fetch(`${API_BASE}/api/history/${deleteTargetId}`, { method: 'DELETE' });
        if (resp.ok) {
            closeDeleteModal();
            if (currentInspectionId === deleteTargetId) backToList();
            await loadHistory();
            await loadStats();
            showNotification('Inspection deleted successfully', 'success');
        } else {
            throw new Error((await resp.json()).detail || 'Failed to delete');
        }
    } catch (e) {
        console.error('Delete failed:', e);
        showNotification('Delete failed: ' + e.message, 'error');
        deleteBtn.disabled = false;
        deleteBtn.textContent = 'Delete Permanently';
    }
}

async function saveMetadata() {
    if (!currentInspectionId) return;

    const containerId = safeGetElement('editContainerId')?.value.trim();
    const isoType = safeGetElement('editIsoType')?.value.trim();

    if (!containerId) {
        showNotification('Container ID is required', 'error');
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/history/${currentInspectionId}/metadata`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ container_id: containerId, iso_type: isoType || null })
        });

        if (resp.ok) {
            showNotification('Metadata updated successfully', 'success');
            await loadDetail(currentInspectionId);
            await loadHistory();
            await loadStats();
        } else {
            const error = await resp.json();
            showNotification('Failed to update: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (e) {
        console.error('Failed to save metadata:', e);
        showNotification('Failed to save metadata', 'error');
    }
}

// ----- Download PDF report -----
async function downloadReport(inspectionId, containerId) {
    if (!inspectionId) {
        showNotification('No inspection selected', 'error');
        return;
    }

    try {
        showNotification('Generating PDF report...', 'info');
        const url = `${API_BASE}/api/history/${inspectionId}/download-report`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to generate report');

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `Inspection_Report_${containerId}_${inspectionId}.pdf`;
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?(.+)"?/i);
            if (match) filename = match[1];
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        showNotification('Report downloaded successfully', 'success');
    } catch (e) {
        console.error('Download failed:', e);
        showNotification('Download failed: ' + e.message, 'error');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    // Trigger reflow to enable animation
    notification.style.animation = 'slideIn 0.3s ease';

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ----- Initialization -----
function initHistoryPage() {
    console.log('Initializing History page...');
    // Ensure list view visible, detail hidden
    safeGetElement('listView') && (safeGetElement('listView').style.display = 'block');
    safeGetElement('detailView') && (safeGetElement('detailView').style.display = 'none');

    // Modal click‑out close
    const deleteModal = safeGetElement('deleteModal');
    if (deleteModal) deleteModal.onclick = (e) => { if (e.target.id === 'deleteModal') closeDeleteModal(); };

    // Load initial data
    loadHistory();
}

// Make function globally available
window.initHistoryPage = initHistoryPage;
