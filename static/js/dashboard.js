const STATUS_BADGE = { Active: 'badge-green', Paused: 'badge-yellow', Cancelled: 'badge-red' };
let activeFilter = 'All';

// Month selector state
let selectedYear = new Date().getFullYear();
let selectedMonth = new Date().getMonth(); // 0-indexed

const CAT_ICONS = {
  'Entertainment':    '🎬',
  'Music':            '🎵',
  'Software & Tools': '💻',
  'Cloud Storage':    '☁️',
  'Health & Fitness': '💪',
  'Education':        '✏️',
  'News & Media':     '📰',
  'Gaming':           '🎮',
};

function getIcon(cat) {
  return CAT_ICONS[cat] || '📦';
}

function setFilter(btn, f) {
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  activeFilter = f;
  renderList();
}

function getFilteredSubs() {
  const firstDay = new Date(selectedYear, selectedMonth, 1);
  const lastDay = new Date(selectedYear, selectedMonth + 1, 0);

  return SUBS.filter(s => {
    const startDate = new Date(s.SUB_SDate);
    const cancelDate = s.SUB_CancelDate ? new Date(s.SUB_CancelDate) : null;
    const startedBeforeMonthEnd = startDate <= lastDay;
    const notCancelledBeforeMonthStart = !cancelDate || cancelDate >= firstDay;

    console.log(s.SUB_Name, 'start:', startDate, 'lastDay:', lastDay, 'passes:', startedBeforeMonthEnd && notCancelledBeforeMonthStart);

    return startedBeforeMonthEnd && notCancelledBeforeMonthStart;
  });
}

function onMonthPicked(value) {
  console.log('month picked:', value);
  const [year, month] = value.split('-').map(Number);
  selectedYear = year;
  selectedMonth = month - 1;
  updateMonthView();
}

function updateMonthView() {
  const label = new Date(selectedYear, selectedMonth, 1)
    .toLocaleString('default', { month: 'long', year: 'numeric' });
  document.getElementById('month-label').textContent = label;
  const pad = m => String(m + 1).padStart(2, '0');
  document.getElementById('month-picker').value = `${selectedYear}-${pad(selectedMonth)}`;
  renderStats();
  renderList();
  renderCats();
}

function renderList() {
  const filtered = getFilteredSubs();
  const list = filtered.filter(s => activeFilter === 'All' || s.SUB_Status === activeFilter);
  document.getElementById('subs-list').innerHTML = list.length ? list.map(s => `
    <div class="sub-card" onclick="openEditModal(${s.SUB_ID})">
      <div class="sub-icon">${getIcon(s.SUB_CAT)}</div>
      <div style="flex:1">
        <div class="sub-name">${s.SUB_Name}</div>
        <div class="sub-cat">${s.SUB_CAT || 'Uncategorized'}</div>
      </div>
      <span class="badge ${STATUS_BADGE[s.SUB_Status] || ''}">${s.SUB_Status}</span>
      <div>
        <div class="sub-cost">$${parseFloat(s.SUBVER_Cost).toFixed(2)}</div>
        <div class="sub-freq">${s.SUBVER_FREQ.toLowerCase()}</div>
      </div>
      <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px;color:var(--red);margin-left:8px" onclick="event.stopPropagation();deleteSubscription(${s.SUB_ID})">🗑️</button>
    </div>
  `).join('') : '<div style="color:var(--text-3);font-size:14px;padding:1rem 0">No subscriptions found.</div>';
}

function openEditModal(sub_id) {
  const s = SUBS.find(sub => sub.SUB_ID === sub_id);
  if (!s) return;
  document.getElementById('edit-sub-id').value = s.SUB_ID;
  document.getElementById('edit-sub-name').value = s.SUB_Name;
  document.getElementById('edit-sub-cat').value = s.SUB_CAT || '';
  document.getElementById('edit-sub-date').value = s.SUB_SDate;
  document.getElementById('edit-sub-status').value = s.SUB_Status;
  document.getElementById('edit-sub-cost').value = s.SUBVER_Cost;
  document.getElementById('edit-sub-freq').value = s.SUBVER_FREQ;
  document.getElementById('modal-edit').classList.add('open');
}

async function updateSubscription() {
  const formData = new FormData();
  formData.append('user_id', USER.USER_ID);
  formData.append('sub_id', document.getElementById('edit-sub-id').value);
  formData.append('sub_name', document.getElementById('edit-sub-name').value);
  formData.append('sub_cat', document.getElementById('edit-sub-cat').value);
  formData.append('sub_sdate', document.getElementById('edit-sub-date').value);
  formData.append('sub_status', document.getElementById('edit-sub-status').value);
  formData.append('subver_cost', document.getElementById('edit-sub-cost').value);
  formData.append('subver_freq', document.getElementById('edit-sub-freq').value);


  const res = await fetch('/update-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to update subscription');
  }
}

async function deleteSubscription(sub_id) {
  if (!confirm('Are you sure you want to delete this subscription?')) return;
  const formData = new FormData();
  formData.append('sub_id', sub_id);
  formData.append('user_id', USER.USER_ID);

  const res = await fetch('/delete-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to delete subscription');
  }
}

function renderStats() {
  const filtered = getFilteredSubs();
  const active = filtered.filter(s => s.SUB_Status === 'Active');
  const paused = filtered.filter(s => s.SUB_Status === 'Paused');
  const monthlyTotal = active.reduce((sum, s) => sum + parseFloat(s.SUBVER_Cost), 0);
  const annualEstimate = monthlyTotal * 12;

  document.querySelector('.stats-grid').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Monthly total</div>
      <div class="stat-value">$${monthlyTotal.toFixed(2)}</div>
      <div class="stat-sub">across ${active.length} active subscriptions</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Annual estimate</div>
      <div class="stat-value">$${annualEstimate.toFixed(2)}</div>
      <div class="stat-sub">projected this year</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Active</div>
      <div class="stat-value" style="color:var(--accent)">${active.length}</div>
      <div class="stat-sub">${paused.length} paused</div>
    </div>
  `;
}

function renderCats() {
  const filtered = getFilteredSubs();
  const active = filtered.filter(s => s.SUB_Status === 'Active');
  const cats = {};
  active.forEach(s => {
    const cat = s.SUB_CAT || 'Uncategorized';
    cats[cat] = (cats[cat] || 0) + parseFloat(s.SUBVER_Cost);
  });
  const total = Object.values(cats).reduce((a, b) => a + b, 0);
  const colors = ['#2d6a4f','#52b788','#74c69d','#95d5b2','#b7e4c7','#d8f3dc','#1b4332'];

  document.getElementById('cat-chart').innerHTML = total === 0
    ? '<div style="color:var(--text-3);font-size:14px">No active subscriptions.</div>'
    : Object.entries(cats).map(([k, v], i) => `
        <div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:13px;color:var(--text-2)">${k}</span>
            <span style="font-size:13px;font-family:'DM Mono',monospace">$${v.toFixed(2)}</span>
          </div>
          <div class="progress-wrap" style="height:6px">
            <div class="progress-bar" style="width:${Math.round(v / total * 100)}%;background:${colors[i % colors.length]}"></div>
          </div>
        </div>
      `).join('');
}

function renderActivity() {
  document.getElementById('activity').innerHTML = `
    <div style="color:var(--text-3);font-size:14px">No recent activity.</div>
  `;
}

async function addSubscription() {
  const formData = new FormData();
  formData.append('user_id', USER.USER_ID);
  formData.append('sub_name', document.getElementById('modal-sub-name').value);
  formData.append('sub_cat', document.getElementById('modal-sub-cat').value);
  formData.append('sub_sdate', document.getElementById('modal-sub-date').value);
  formData.append('sub_status', document.getElementById('modal-sub-status').value);
  formData.append('subver_cost', document.getElementById('modal-sub-cost').value);
  formData.append('subver_freq', document.getElementById('modal-sub-freq').value);


  const res = await fetch('/add-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to add subscription');
  }
}


function toggleProfileMenu() {
  const menu = document.getElementById('profile-menu');
  menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}

// Close profile menu when clicking outside
document.addEventListener('click', e => {
  const menu = document.getElementById('profile-menu');
  const avatar = document.querySelector('.avatar');
  if (!menu.contains(e.target) && !avatar.contains(e.target)) {
    menu.style.display = 'none';
  }
});

// Modal close on overlay click
document.getElementById('modal-add').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.classList.remove('open');
});
document.getElementById('modal-edit').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.classList.remove('open');
});

// Render user greeting
document.querySelector('.page-title').textContent = `Good morning, ${USER.USER_FName}`;
document.querySelector('.avatar').textContent = USER.USER_FName[0] + USER.USER_LName[0];





updateMonthView();
renderActivity();