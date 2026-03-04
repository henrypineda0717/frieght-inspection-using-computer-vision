const API_BASE = "http://localhost:8001";
let currentPage = 1;
let totalPages = 1;
let currentInspectionId = null;
let currentInspectionData = null;
let deleteTargetId = null;
let deleteTargetContainerId = null;

// Load statistics
async function loadStats() {
    try {
        const resp = await fetch(`${API_BASE}/api/history/stats/summary`);
        const data = await resp.json();
        
        document.getElementById('statInspections').textContent = data.total_inspections;
        document.getElementById('statContainers').textContent = data.total_containers;
        document.getElementById('statFrames').textContent = data.total_frames;
        document.getElementById('statDetections').textContent = data.total_detections;
        document.getElementById('statAlerts').textContent = data.alert_inspections;
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

// Load history list
async function loadHistory() {
    const search = document.getElementById('searchInput').value;
    const status = document.getElementById('statusFilter').value;
    const stage = document.getElementById('stageFilter').value;

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
    } catch (e) {
        console.error('Failed to load history:', e);
        document.getElementById('historyTable').innerHTML = 
            '<tr><td colspan="10" style="text-align:center;color:#f87171;">Failed to load history</td></tr>';
    }
}

function renderHistoryTable(items) {
    const tbody = document.getElementById('historyTable');
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
                <button class="download-btn" onclick="event.stopPropagation(); downloadReport(${item.id}, '${item.container_id}')" title="Download PDF Report">📄</button>
                <button class="delete-btn" onclick="event.stopPropagation(); showDeleteModal(${item.id}, '${item.container_id}')">🗑️</button>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

function updatePagination() {
    document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
    document.getElementById('btnPrevPage').disabled = currentPage <= 1;
    document.getElementById('btnNextPage').disabled = currentPage >= totalPages;
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        loadHistory();
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        loadHistory();
    }
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('stageFilter').value = '';
    currentPage = 1;
    loadHistory();
}

// Cleanup orphaned containers
async function cleanupOrphanedContainers() {
    if (!confirm('Remove all containers that have no inspections?')) {
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/history/cleanup/orphaned-containers`, {
            method: 'POST'
        });

        if (resp.ok) {
            const data = await resp.json();
            showNotification(data.message, 'success');
            await loadStats();
            await loadHistory();
        } else {
            const error = await resp.json();
            throw new Error(error.detail || 'Cleanup failed');
        }
    } catch (e) {
        console.error('Cleanup failed:', e);
        showNotification('Cleanup failed: ' + e.message, 'error');
    }
}

// Load inspection detail
async function loadDetail(inspectionId) {
    currentInspectionId = inspectionId;

    try {
        const resp = await fetch(`${API_BASE}/api/history/${inspectionId}`);
        const data = await resp.json();

        currentInspectionData = data;
        renderDetail(data);
        document.getElementById('listView').style.display = 'none';
        document.getElementById('detailView').classList.add('active');
    } catch (e) {
        console.error('Failed to load detail:', e);
        alert('Failed to load inspection details');
    }
}

function renderDetail(data) {
    document.getElementById('detailTitle').textContent = 
        `Inspection #${data.id} - ${data.container_id}`;

    // Populate edit form
    document.getElementById('editContainerId').value = data.container_id;
    document.getElementById('editIsoType').value = data.iso_type || '';

    // Metadata grid
    const metadataGrid = document.getElementById('metadataGrid');
    metadataGrid.innerHTML = `
        <div class="metadata-item">
            <div class="metadata-label">Container ID</div>
            <div class="metadata-value">${data.container_id}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">ISO Type</div>
            <div class="metadata-value">${data.iso_type || 'Unknown'}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Timestamp</div>
            <div class="metadata-value">${new Date(data.timestamp).toLocaleString()}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Stage</div>
            <div class="metadata-value">${data.stage || 'None'}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Status</div>
            <div class="metadata-value">
                ${data.status === 'alert' 
                    ? '<span class="badge badge-alert">Alert</span>' 
                    : '<span class="badge badge-ok">OK</span>'}
            </div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Risk Score</div>
            <div class="metadata-value">${data.risk_score}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Contamination</div>
            <div class="metadata-value">${data.contamination_index} / 9 (${data.contamination_label})</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">People Nearby</div>
            <div class="metadata-value">${data.people_nearby ? 'Yes' : 'No'}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Door Status</div>
            <div class="metadata-value">${data.door_status || 'Unknown'}</div>
        </div>
        <div class="metadata-item">
            <div class="metadata-label">Anomalies</div>
            <div class="metadata-value">${data.anomalies_present ? 'Yes' : 'No'}</div>
        </div>
    `;

    if (data.scene_caption) {
        metadataGrid.innerHTML += `
            <div class="metadata-item" style="grid-column: 1 / -1;">
                <div class="metadata-label">Scene Caption</div>
                <div class="metadata-value">${data.scene_caption}</div>
            </div>
        `;
    }

    if (data.anomaly_summary) {
        metadataGrid.innerHTML += `
            <div class="metadata-item" style="grid-column: 1 / -1;">
                <div class="metadata-label">Anomaly Summary</div>
                <div class="metadata-value">${data.anomaly_summary}</div>
            </div>
        `;
    }

    // Frames grid
    const framesGrid = document.getElementById('framesGrid');
    framesGrid.innerHTML = '';

    data.frames.forEach((frame, idx) => {
        const frameCard = document.createElement('div');
        frameCard.className = 'frame-card';

        // Use overlay image if available, otherwise original
        const imgPath = frame.overlay_path || frame.image_path;
        const imgUrl = `${API_BASE}/api/images/${imgPath}`;

        let detectionsHtml = '';
        if (frame.detections.length > 0) {
            detectionsHtml = '<div class="detection-list">';
            frame.detections.forEach(det => {
                const conf = det.confidence ? ` (${(det.confidence * 100).toFixed(1)}%)` : '';
                detectionsHtml += `<div class="detection-item">${det.label}${conf}</div>`;
            });
            detectionsHtml += '</div>';
        } else {
            detectionsHtml = '<div class="detection-list" style="color:var(--gray-soft);">No detections</div>';
        }

        frameCard.innerHTML = `
            <img src="${imgUrl}" alt="Frame ${idx + 1}" />
            <div class="frame-info">
                <h4>Frame #${frame.id} - Contamination: ${frame.contamination_index}/9</h4>
                <div style="margin-bottom: 6px;">
                    ${frame.status === 'alert' 
                        ? '<span class="badge badge-alert">Alert</span>' 
                        : '<span class="badge badge-ok">OK</span>'}
                </div>
                ${detectionsHtml}
            </div>
        `;

        framesGrid.appendChild(frameCard);
    });
}

function backToList() {
    document.getElementById('detailView').classList.remove('active');
    document.getElementById('listView').style.display = 'block';
    currentInspectionId = null;
    currentInspectionData = null;
}

// Delete functionality
function showDeleteModal(inspectionId, containerId) {
    deleteTargetId = inspectionId;
    deleteTargetContainerId = containerId;
    
    document.getElementById('deleteInspectionId').textContent = inspectionId;
    document.getElementById('deleteContainerId').textContent = containerId;
    document.getElementById('deleteModal').classList.add('active');
    document.getElementById('confirmDeleteBtn').disabled = false;
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteTargetId = null;
    deleteTargetContainerId = null;
}

async function confirmDelete() {
    if (!deleteTargetId) return;

    const deleteBtn = document.getElementById('confirmDeleteBtn');
    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting...';

    try {
        const resp = await fetch(`${API_BASE}/api/history/${deleteTargetId}`, {
            method: 'DELETE'
        });

        if (resp.ok) {
            closeDeleteModal();
            
            // If we're in detail view, go back to list
            if (currentInspectionId === deleteTargetId) {
                backToList();
            }
            
            // Reload data
            await loadHistory();
            await loadStats();
            
            // Show success message
            showNotification('Inspection deleted successfully', 'success');
        } else {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to delete inspection');
        }
    } catch (e) {
        console.error('Failed to delete inspection:', e);
        showNotification('Failed to delete inspection: ' + e.message, 'error');
        deleteBtn.disabled = false;
        deleteBtn.textContent = 'Delete Permanently';
    }
}

// Simple notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        z-index: 2000;
        animation: slideIn 0.3s ease;
        ${type === 'success' ? 'background: #10b981; color: white;' : ''}
        ${type === 'error' ? 'background: #ef4444; color: white;' : ''}
        ${type === 'info' ? 'background: #3b82f6; color: white;' : ''}
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('deleteModal').addEventListener('click', (e) => {
        if (e.target.id === 'deleteModal') {
            closeDeleteModal();
        }
    });
});

// Download PDF report
async function downloadReport(inspectionId, containerId) {
    if (!inspectionId) {
        showNotification('No inspection selected', 'error');
        return;
    }

    try {
        showNotification('Generating PDF report...', 'info');
        
        const url = `${API_BASE}/api/history/${inspectionId}/download-report`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('Failed to generate report');
        }
        
        // Get the blob
        const blob = await response.blob();
        
        // Create download link
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        
        // Get filename from Content-Disposition header or create one
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `Inspection_Report_${containerId}_${inspectionId}.pdf`;
        
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        
        showNotification('Report downloaded successfully', 'success');
    } catch (e) {
        console.error('Failed to download report:', e);
        showNotification('Failed to download report: ' + e.message, 'error');
    }
}

// Metadata editing
async function saveMetadata() {
    if (!currentInspectionId) return;

    const containerId = document.getElementById('editContainerId').value.trim();
    const isoType = document.getElementById('editIsoType').value.trim();

    if (!containerId) {
        alert('Container ID is required');
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/history/${currentInspectionId}/metadata`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                container_id: containerId,
                iso_type: isoType || null
            })
        });

        if (resp.ok) {
            alert('Metadata updated successfully');
            loadDetail(currentInspectionId); // Reload
            loadStats(); // Refresh stats
        } else {
            const error = await resp.json();
            alert('Failed to update: ' + (error.detail || 'Unknown error'));
        }
    } catch (e) {
        console.error('Failed to save metadata:', e);
        alert('Failed to save metadata');
    }
}

function cancelEdit() {
    if (currentInspectionId) {
        loadDetail(currentInspectionId); // Reload to reset form
    }
}

// Initialize
window.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadHistory();
});