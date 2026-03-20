const API = '';
let accessToken = localStorage.getItem('access_token');
let refreshToken = localStorage.getItem('refresh_token');
let currentFolderId = null;
let folders = [];
let allFiles = [];

// ── INIT ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (accessToken) showApp();
  else showAuth();

  setupAuth();
  setupApp();
});

function showAuth() {
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
}

function showApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
  loadAll();
}

// ── HTTP ──────────────────────────────────────────────────────────────
async function api(method, path, body, isFormData = false) {
  const headers = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  if (body && !isFormData) headers['Content-Type'] = 'application/json';

  const res = await fetch(API + path, {
    method,
    headers,
    body: isFormData ? body : (body ? JSON.stringify(body) : undefined),
  });

  if (res.status === 401 && refreshToken) {
    const ok = await doRefresh();
    if (ok) return api(method, path, body, isFormData);
    logout();
    return null;
  }

  return res;
}

async function doRefresh() {
  const res = await fetch(API + '/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  accessToken = data.access_token;
  refreshToken = data.refresh_token;
  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('refresh_token', refreshToken);
  return true;
}

// ── AUTH ──────────────────────────────────────────────────────────────
function setupAuth() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const which = tab.dataset.tab;
      document.getElementById('login-form').classList.toggle('hidden', which !== 'login');
      document.getElementById('register-form').classList.toggle('hidden', which !== 'register');
    });
  });

  document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const err = document.getElementById('login-error');
    err.textContent = '';

    const res = await fetch(API + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) { err.textContent = data.detail || 'Ошибка входа'; return; }

    accessToken = data.access_token;
    refreshToken = data.refresh_token;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    showApp();
  });

  document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const err = document.getElementById('register-error');
    err.textContent = '';

    const res = await fetch(API + '/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) { err.textContent = data.detail || 'Ошибка регистрации'; return; }

    toast('Аккаунт создан! Войдите.', 'success');
    document.querySelector('.tab[data-tab="login"]').click();
  });
}

// ── APP ───────────────────────────────────────────────────────────────
function setupApp() {
  // upload
  document.getElementById('upload-btn').addEventListener('click', () => {
    document.getElementById('file-input').click();
  });
  document.getElementById('file-input').addEventListener('change', e => {
    [...e.target.files].forEach(uploadFile);
    e.target.value = '';
  });

  // drag & drop
  const main = document.querySelector('.main');
  main.addEventListener('dragover', e => { e.preventDefault(); main.style.opacity = '.6'; });
  main.addEventListener('dragleave', () => { main.style.opacity = ''; });
  main.addEventListener('drop', e => {
    e.preventDefault();
    main.style.opacity = '';
    [...e.dataTransfer.files].forEach(uploadFile);
  });

  // logout
  document.getElementById('logout-btn').addEventListener('click', logout);

  // new folder
  document.getElementById('new-folder-btn').addEventListener('click', () => {
    openModal('Новая папка', '<input id="folder-name-input" placeholder="Название папки" />', async () => {
      const name = document.getElementById('folder-name-input').value.trim();
      if (!name) return;
      const res = await api('POST', '/folders', { name, parent_id: currentFolderId });
      if (res?.ok) { toast('Папка создана', 'success'); loadFolders(); }
      else toast('Ошибка', 'error');
    });
    setTimeout(() => document.getElementById('folder-name-input')?.focus(), 50);
  });

  // all files nav
  document.querySelector('.nav-item[data-folder="null"]').addEventListener('click', () => {
    currentFolderId = null;
    document.getElementById('current-folder-name').textContent = 'Все файлы';
    document.querySelectorAll('.nav-item, .folder-item').forEach(el => el.classList.remove('active'));
    document.querySelector('.nav-item').classList.add('active');
    renderFiles();
  });

  // search
  document.getElementById('search-input').addEventListener('input', e => {
    renderFiles(e.target.value.toLowerCase());
  });
}

function logout() {
  if (refreshToken) api('POST', '/auth/logout', { refresh_token: refreshToken });
  accessToken = null; refreshToken = null;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  showAuth();
}

// ── DATA ──────────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadFolders(), loadFiles(), loadQuota()]);
}

async function loadFiles() {
  const res = await api('GET', '/files?limit=200');
  if (!res?.ok) return;
  allFiles = await res.json();
  renderFiles();
}

async function loadFolders() {
  const res = await api('GET', '/folders');
  if (!res?.ok) return;
  folders = await res.json();
  renderFolders();
}

async function loadQuota() {
  const res = await api('GET', '/quota/info');
  if (!res?.ok) return;
  const { used_bytes, quota_bytes } = await res.json();
  const pct = Math.min(100, (used_bytes / quota_bytes) * 100);
  document.getElementById('quota-fill').style.width = pct + '%';
  document.getElementById('quota-text').textContent =
    `${formatSize(used_bytes)} / ${formatSize(quota_bytes)}`;
}

// ── RENDER ────────────────────────────────────────────────────────────
function renderFolders() {
  const list = document.getElementById('folder-list');
  list.innerHTML = '';
  folders.forEach(f => {
    const el = document.createElement('div');
    el.className = 'folder-item' + (currentFolderId === f.id ? ' active' : '');
    el.innerHTML = `
      <span class="folder-icon">📁</span>
      <span class="folder-name">${esc(f.name)}</span>
      <span class="folder-del" data-id="${f.id}" title="Удалить">✕</span>
    `;
    el.addEventListener('click', e => {
      if (e.target.classList.contains('folder-del')) {
        e.stopPropagation();
        confirmDeleteFolder(f);
        return;
      }
      currentFolderId = f.id;
      document.getElementById('current-folder-name').textContent = f.name;
      document.querySelectorAll('.nav-item, .folder-item').forEach(el => el.classList.remove('active'));
      el.classList.add('active');
      renderFiles();
    });
    list.appendChild(el);
  });
}

function renderFiles(query = '') {
  const list = document.getElementById('file-list');
  const empty = document.getElementById('empty-state');

  let files = allFiles;
  if (currentFolderId !== null) {
    files = files.filter(f => f.folder_id === currentFolderId);
  }
  if (query) {
    files = files.filter(f => f.name.toLowerCase().includes(query));
  }

  // remove file items (keep upload progress items)
  list.querySelectorAll('.file-item').forEach(el => el.remove());
  empty.classList.toggle('hidden', files.length > 0);

  files.forEach(f => {
    const el = document.createElement('div');
    el.className = 'file-item';
    el.innerHTML = `
      <span class="file-icon">${fileIcon(f.content_type)}</span>
      <div class="file-info">
        <div class="file-name">${esc(f.name)}</div>
        <div class="file-meta">${formatSize(f.size_bytes)} · ${formatDate(f.created_at)}</div>
      </div>
      <div class="file-actions">
        <button class="file-action-btn" title="Скачать" data-action="download">⬇</button>
        <button class="file-action-btn" title="Поделиться" data-action="share">🔗</button>
        <button class="file-action-btn" title="Переименовать" data-action="rename">✏️</button>
        <button class="file-action-btn danger" title="Удалить" data-action="delete">🗑</button>
      </div>
    `;
    el.querySelector('[data-action=download]').addEventListener('click', () => downloadFile(f));
    el.querySelector('[data-action=share]').addEventListener('click', () => shareFile(f));
    el.querySelector('[data-action=rename]').addEventListener('click', () => renameFile(f));
    el.querySelector('[data-action=delete]').addEventListener('click', () => confirmDeleteFile(f));
    list.appendChild(el);
  });
}

// ── UPLOAD ────────────────────────────────────────────────────────────
async function uploadFile(file) {
  const list = document.getElementById('file-list');
  document.getElementById('empty-state').classList.add('hidden');

  const progressEl = document.createElement('div');
  progressEl.className = 'upload-progress file-item';
  progressEl.innerHTML = `
    <span class="file-icon">⏳</span>
    <span class="progress-name">${esc(file.name)}</span>
    <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
  `;
  list.prepend(progressEl);
  progressEl.querySelector('.progress-fill').style.width = '60%';

  const form = new FormData();
  form.append('file', file);
  const url = '/files/upload' + (currentFolderId ? `?folder_id=${currentFolderId}` : '');
  const res = await api('POST', url, form, true);

  progressEl.remove();

  if (res?.ok) {
    toast(`Загружен: ${file.name}`, 'success');
    await Promise.all([loadFiles(), loadQuota()]);
  } else {
    const data = await res?.json();
    toast(data?.detail || 'Ошибка загрузки', 'error');
  }
}

// ── FILE ACTIONS ──────────────────────────────────────────────────────
async function downloadFile(f) {
  const res = await api('GET', `/files/${f.id}/download`);
  if (!res?.ok) { toast('Ошибка', 'error'); return; }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = f.original_name;
  a.click();
  URL.revokeObjectURL(a.href);
  toast(`Скачивается: ${f.name}`, 'success');
}

async function shareFile(f) {
  const res = await api('POST', `/share/${f.id}`, { ttl_hours: 24 });
  if (!res?.ok) { toast('Ошибка', 'error'); return; }
  const data = await res.json();
  const link = `${location.origin}${data.url}`;
  openModal('Публичная ссылка', `
    <p>Ссылка действительна 24 часа.</p>
    <div class="share-link" id="share-link-text" title="Нажмите чтобы скопировать">${esc(link)}</div>
  `, null, 'Закрыть');
  document.getElementById('share-link-text')?.addEventListener('click', () => {
    navigator.clipboard.writeText(link);
    toast('Ссылка скопирована', 'success');
  });
}

async function renameFile(f) {
  openModal('Переименовать', `<input id="rename-input" value="${esc(f.name)}" />`, async () => {
    const name = document.getElementById('rename-input').value.trim();
    if (!name || name === f.name) return;
    const res = await api('PATCH', `/files/${f.id}`, { name });
    if (res?.ok) { toast('Переименовано', 'success'); loadFiles(); }
    else toast('Ошибка', 'error');
  });
  setTimeout(() => {
    const inp = document.getElementById('rename-input');
    if (inp) { inp.focus(); inp.select(); }
  }, 50);
}

function confirmDeleteFile(f) {
  openModal('Удалить файл', `<p>Удалить <strong>${esc(f.name)}</strong>? Это действие необратимо.</p>`, async () => {
    const res = await api('DELETE', `/files/${f.id}`);
    if (res?.ok) { toast('Файл удалён', 'success'); await Promise.all([loadFiles(), loadQuota()]); }
    else toast('Ошибка', 'error');
  }, 'Удалить', true);
}

function confirmDeleteFolder(f) {
  openModal('Удалить папку', `<p>Удалить папку <strong>${esc(f.name)}</strong> и все файлы в ней?</p>`, async () => {
    const res = await api('DELETE', `/folders/${f.id}`);
    if (res?.ok) {
      toast('Папка удалена', 'success');
      if (currentFolderId === f.id) {
        currentFolderId = null;
        document.getElementById('current-folder-name').textContent = 'Все файлы';
      }
      await Promise.all([loadFolders(), loadFiles(), loadQuota()]);
    } else toast('Ошибка', 'error');
  }, 'Удалить', true);
}

// ── MODAL ─────────────────────────────────────────────────────────────
function openModal(title, bodyHtml, onConfirm, confirmText = 'OK', isDanger = false) {
  const overlay = document.getElementById('modal-overlay');
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;
  const confirmBtn = document.getElementById('modal-confirm');
  const cancelBtn = document.getElementById('modal-cancel');

  confirmBtn.textContent = confirmText;
  confirmBtn.className = 'btn ' + (isDanger ? 'btn-danger' : 'btn-primary');

  if (!onConfirm) {
    confirmBtn.classList.add('hidden');
    cancelBtn.textContent = confirmText || 'Закрыть';
  } else {
    confirmBtn.classList.remove('hidden');
    cancelBtn.textContent = 'Отмена';
  }

  overlay.classList.remove('hidden');

  const close = () => overlay.classList.add('hidden');
  cancelBtn.onclick = close;
  overlay.onclick = e => { if (e.target === overlay) close(); };
  confirmBtn.onclick = async () => { if (onConfirm) await onConfirm(); close(); };
}

// ── TOAST ─────────────────────────────────────────────────────────────
let toastTimer;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast ' + type;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3000);
}

// ── UTILS ─────────────────────────────────────────────────────────────
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 ** 3) return (bytes / 1024 ** 2).toFixed(1) + ' MB';
  return (bytes / 1024 ** 3).toFixed(2) + ' GB';
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function fileIcon(ct = '') {
  if (ct.startsWith('image/')) return '🖼';
  if (ct.startsWith('video/')) return '🎬';
  if (ct.startsWith('audio/')) return '🎵';
  if (ct.includes('pdf')) return '📄';
  if (ct.includes('zip') || ct.includes('gzip') || ct.includes('tar')) return '🗜';
  if (ct.includes('json') || ct.includes('javascript') || ct.includes('html') || ct.includes('css')) return '💻';
  if (ct.includes('text')) return '📝';
  return '📦';
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
