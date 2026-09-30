/**
 * Admin Dashboard Interactive JavaScript
 * Handles tabs, live search/filtering, modals, AJAX user actions, audio playback, and lightboxes.
 */

document.addEventListener('DOMContentLoaded', () => {
    initAdminTabs();
    initUserSearchAndFilters();
    initGenerationsSearch();
    initAdminClock();
});

// Toast notification helper
function showAdminToast(message, type = 'success') {
    const container = document.getElementById('global-alert-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `glass-alert alert-${type}`;
    
    let iconClass = 'fa-circle-check';
    if (type === 'danger') iconClass = 'fa-circle-exclamation';
    if (type === 'warning') iconClass = 'fa-triangle-exclamation';
    if (type === 'info') iconClass = 'fa-circle-info';

    toast.innerHTML = `
        <i class="fa-solid ${iconClass} alert-icon"></i>
        <span class="alert-text">${message}</span>
        <button class="alert-close-btn" onclick="this.parentElement.remove();">&times;</button>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 350);
    }, 4500);
}

// === TABS NAVIGATION ===
function initAdminTabs() {
    const tabButtons = document.querySelectorAll('.admin-tab-btn');
    const tabPanels = document.querySelectorAll('.admin-tab-panel');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');

            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPanel = document.getElementById(targetId);
            if (targetPanel) {
                targetPanel.classList.add('active');
            }
        });
    });
}

// === USER SEARCH & FILTERING ===
function initUserSearchAndFilters() {
    const searchInput = document.getElementById('user-search-input');
    const filterButtons = document.querySelectorAll('.user-filter-btn');
    const userRows = document.querySelectorAll('#users-table-body tr.user-row');

    let activeFilter = 'all';

    function applyUserFilter() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

        userRows.forEach(row => {
            const username = (row.getAttribute('data-username') || '').toLowerCase();
            const userId = (row.getAttribute('data-userid') || '').toLowerCase();
            const role = (row.getAttribute('data-role') || '').toLowerCase(); // 'admin' or 'user'
            const gens = parseInt(row.getAttribute('data-gens') || '0', 10);

            // Filter match
            let matchesFilter = true;
            if (activeFilter === 'admins') matchesFilter = (role === 'admin');
            if (activeFilter === 'members') matchesFilter = (role === 'user');
            if (activeFilter === 'creators') matchesFilter = (gens > 0);

            // Search match
            let matchesSearch = true;
            if (query) {
                matchesSearch = username.includes(query) || userId.includes(query) || role.includes(query);
            }

            if (matchesFilter && matchesSearch) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', applyUserFilter);
    }

    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter');
            applyUserFilter();
        });
    });
}

// === GENERATIONS SEARCH ===
function initGenerationsSearch() {
    const genSearchInput = document.getElementById('gen-search-input');
    const genRows = document.querySelectorAll('#generations-table-body tr.gen-row');

    if (genSearchInput) {
        genSearchInput.addEventListener('input', () => {
            const query = genSearchInput.value.toLowerCase().trim();
            genRows.forEach(row => {
                const user = (row.getAttribute('data-gen-user') || '').toLowerCase();
                const caption = (row.getAttribute('data-gen-caption') || '').toLowerCase();
                const voice = (row.getAttribute('data-gen-voice') || '').toLowerCase();

                if (!query || user.includes(query) || caption.includes(query) || voice.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
}

// === MODAL CONTROLS ===
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
        // Stop any audio playing inside the modal
        const audios = modal.querySelectorAll('audio');
        audios.forEach(a => a.pause());
    }
}

// Close modal when clicking on backdrop
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('admin-modal-overlay') || e.target.classList.contains('lightbox-modal')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
        const audios = e.target.querySelectorAll('audio');
        audios.forEach(a => a.pause());
    }
});

// === USER DETAILS DEEP DIVE MODAL ===
async function viewUserDetails(userId) {
    openModal('userDetailModal');
    const contentBox = document.getElementById('user-detail-modal-content');
    contentBox.innerHTML = `
        <div style="text-align: center; padding: 2.5rem 1rem;">
            <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: var(--primary);"></i>
            <p style="margin-top: 1rem; color: var(--text-muted);">Loading user profile & generation history...</p>
        </div>
    `;

    try {
        const res = await fetch(`/admin/api/user/${userId}`);
        if (!res.ok) throw new Error('Failed to load user data');
        const data = await res.json();
        const user = data.user;
        const gens = data.generations;

        const roleBadgeHtml = user.is_admin 
            ? `<span class="badge-role role-admin"><i class="fa-solid fa-shield-halved"></i> Administrator</span>`
            : `<span class="badge-role role-user"><i class="fa-solid fa-user"></i> Standard User</span>`;

        let gensHtml = '';
        if (gens.length === 0) {
            gensHtml = `
                <div style="text-align: center; padding: 2rem 1rem; color: var(--text-muted); background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px dashed var(--card-border);">
                    <i class="fa-regular fa-folder-open" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                    This user has not generated any captions or voiceovers yet.
                </div>
            `;
        } else {
            gens.forEach(item => {
                gensHtml += `
                    <div class="modal-generation-item" id="user-detail-gen-${item.id}">
                        <img src="${item.image_url}" alt="Thumbnail" class="modal-generation-thumb" onclick="openLightbox('${item.image_url}')">
                        <div class="modal-generation-content">
                            <p class="modal-generation-caption">"${item.caption}"</p>
                            <div class="modal-generation-meta">
                                <span><i class="fa-solid fa-microphone-lines"></i> ${item.voice}</span>
                                <span><i class="fa-solid fa-calendar-day"></i> ${item.timestamp}</span>
                                <span><i class="fa-solid fa-file-zipper"></i> ${item.size_formatted}</span>
                            </div>
                            <div class="modal-generation-actions">
                                <audio controls src="${item.audio_url}"></audio>
                                <button class="action-btn btn-delete" title="Delete generation" onclick="deleteGenerationItem(${item.id}, 'user-detail-gen-${item.id}')">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
        }

        contentBox.innerHTML = `
            <div class="user-profile-banner">
                <div class="user-profile-avatar ${user.is_admin ? 'avatar-admin' : ''}">
                    ${user.username.charAt(0).toUpperCase()}
                </div>
                <div class="user-profile-meta">
                    <h4>${user.username} ${roleBadgeHtml}</h4>
                    <p>User ID: #${user.id} · Registered (IST): ${user.created_at}</p>
                </div>
            </div>

            <div class="user-stats-mini-row">
                <div class="mini-stat-card">
                    <div class="mini-stat-num">${user.total_generations}</div>
                    <div class="mini-stat-label">Total Generations</div>
                </div>
                <div class="mini-stat-card">
                    <div class="mini-stat-num">${user.total_storage_formatted}</div>
                    <div class="mini-stat-label">Storage Footprint</div>
                </div>
                <div class="mini-stat-card">
                    <div class="mini-stat-num" style="font-size: 0.95rem;">${user.last_login}</div>
                    <div class="mini-stat-label">Last Login (IST)</div>
                </div>
            </div>

            <h4 style="margin-bottom: 0.85rem; font-size: 1.05rem; display: flex; align-items: center; gap: 0.5rem;">
                <i class="fa-solid fa-clock-rotate-left"></i> Generations History (${gens.length})
            </h4>
            <div class="user-generations-list">
                ${gensHtml}
            </div>
        `;
    } catch (err) {
        contentBox.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: #ef4444;">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                Failed to load user details: ${err.message}
            </div>
        `;
    }
}

// === CREATE NEW USER ===
function openCreateUserModal() {
    document.getElementById('create-username').value = '';
    document.getElementById('create-password').value = '';
    document.getElementById('create-confirm-password').value = '';
    document.getElementById('create-is-admin').checked = false;
    openModal('createUserModal');
}

async function handleCreateUserSubmit(event) {
    event.preventDefault();
    const username = document.getElementById('create-username').value.trim();
    const password = document.getElementById('create-password').value.trim();
    const confirmPassword = document.getElementById('create-confirm-password').value.trim();
    const isAdmin = document.getElementById('create-is-admin').checked;

    if (!username || !password) {
        showAdminToast('Username and password are required', 'danger');
        return;
    }

    if (password !== confirmPassword) {
        showAdminToast('Passwords do not match', 'danger');
        return;
    }

    try {
        const res = await fetch('/admin/api/users/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, is_admin: isAdmin })
        });
        const data = await res.json();
        if (res.ok) {
            closeModal('createUserModal');
            showAdminToast(data.message, 'success');
            setTimeout(() => window.location.reload(), 800);
        } else {
            showAdminToast(data.error || 'Failed to create user', 'danger');
        }
    } catch (err) {
        showAdminToast('Network error while creating user', 'danger');
    }
}

// === EDIT USER & RESET PASSWORD ===
function openEditUserModal(userId, username, isAdmin) {
    document.getElementById('edit-user-id').value = userId;
    document.getElementById('edit-username').value = username;
    document.getElementById('edit-password').value = '';
    document.getElementById('edit-is-admin').checked = (isAdmin === 'true' || isAdmin === true);
    openModal('editUserModal');
}

async function handleEditUserSubmit(event) {
    event.preventDefault();
    const userId = document.getElementById('edit-user-id').value;
    const username = document.getElementById('edit-username').value.trim();
    const password = document.getElementById('edit-password').value.trim();
    const isAdmin = document.getElementById('edit-is-admin').checked;

    try {
        const res = await fetch(`/admin/api/users/${userId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, is_admin: isAdmin })
        });
        const data = await res.json();
        if (res.ok) {
            closeModal('editUserModal');
            showAdminToast(data.message, 'success');
            setTimeout(() => window.location.reload(), 800);
        } else {
            showAdminToast(data.error || 'Failed to update user', 'danger');
        }
    } catch (err) {
        showAdminToast('Network error while updating user', 'danger');
    }
}

// === TOGGLE ADMIN PRIVILEGES ===
async function toggleUserAdmin(userId) {
    try {
        const res = await fetch(`/admin/api/users/${userId}/toggle-admin`, {
            method: 'POST'
        });
        const data = await res.json();
        if (res.ok) {
            showAdminToast(data.message, 'success');
            setTimeout(() => window.location.reload(), 700);
        } else {
            showAdminToast(data.error || 'Failed to update privileges', 'danger');
        }
    } catch (err) {
        showAdminToast('Error toggling administrator role', 'danger');
    }
}

// === DELETE USER ===
let pendingDeleteUserId = null;

function promptDeleteUser(userId, username) {
    pendingDeleteUserId = userId;
    document.getElementById('delete-user-name-placeholder').textContent = username;
    openModal('deleteUserModal');
}

async function confirmDeleteUser() {
    if (!pendingDeleteUserId) return;
    const userId = pendingDeleteUserId;

    try {
        const res = await fetch(`/admin/api/users/${userId}/delete`, {
            method: 'POST'
        });
        const data = await res.json();
        if (res.ok) {
            closeModal('deleteUserModal');
            showAdminToast(data.message, 'success');
            const row = document.getElementById(`user-row-${userId}`);
            if (row) {
                row.style.opacity = '0';
                row.style.transform = 'scale(0.95)';
                setTimeout(() => row.remove(), 300);
            } else {
                setTimeout(() => window.location.reload(), 800);
            }
        } else {
            showAdminToast(data.error || 'Failed to delete user', 'danger');
        }
    } catch (err) {
        showAdminToast('Network error deleting user', 'danger');
    }
}

// === DELETE GENERATION ITEM ===
async function deleteGenerationItem(itemId, domElementId) {
    if (!confirm('Are you sure you want to delete this caption and its voiceover audio file?')) return;

    try {
        const res = await fetch(`/admin/api/generations/${itemId}/delete`, {
            method: 'POST'
        });
        const data = await res.json();
        if (res.ok) {
            showAdminToast('Generation deleted', 'success');
            const el = document.getElementById(domElementId);
            if (el) {
                el.style.opacity = '0';
                setTimeout(() => el.remove(), 250);
            }
        } else {
            showAdminToast(data.error || 'Failed to delete generation', 'danger');
        }
    } catch (err) {
        showAdminToast('Error deleting generation', 'danger');
    }
}

// === CLEANUP ORPHANED FILES ===
async function runOrphanedCleanup() {
    const btn = document.getElementById('cleanup-orphans-btn');
    if (btn) btn.disabled = true;

    try {
        const res = await fetch('/admin/api/system/cleanup-orphaned', {
            method: 'POST'
        });
        const data = await res.json();
        if (res.ok) {
            showAdminToast(data.message, 'success');
            setTimeout(() => window.location.reload(), 1200);
        } else {
            showAdminToast(data.error || 'Cleanup failed', 'danger');
        }
    } catch (err) {
        showAdminToast('Network error during file cleanup', 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// === LIGHTBOX PREVIEW ===
function openLightbox(imageUrl) {
    const lightbox = document.getElementById('imageLightboxModal');
    const img = document.getElementById('lightbox-img');
    if (lightbox && img) {
        img.src = imageUrl;
        lightbox.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeLightbox() {
    const lightbox = document.getElementById('imageLightboxModal');
    if (lightbox) {
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// === LIVE IST CLOCK ===
function initAdminClock() {
    const clockEl = document.getElementById('admin-live-time');
    const diagClockEl = document.getElementById('diag-ist-time');
    if (!clockEl && !diagClockEl) return;

    function updateClock() {
        const now = new Date();
        const formatted = new Intl.DateTimeFormat('en-US', {
            timeZone: 'Asia/Kolkata',
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        }).format(now);

        if (clockEl) clockEl.textContent = formatted;
        if (diagClockEl) diagClockEl.textContent = `${formatted} IST`;
    }

    updateClock();
    setInterval(updateClock, 1000);
}

