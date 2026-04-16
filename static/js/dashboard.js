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

// Returns emoji icon for a given category name
function getIcon(cat) {
  return CAT_ICONS[cat] || '📦';
}

// Handles filter chip selection (All / Active / Paused / Cancelled)
function setFilter(btn, f) {
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  activeFilter = f;
  renderList();
}

// Filters SUBS to only payment records within the selected month
function getFilteredSubs() {
  const firstDay = new Date(selectedYear, selectedMonth, 1);
  const lastDay = new Date(selectedYear, selectedMonth + 1, 0);

  return SUBS.filter(s => {
    const payDate = new Date(s.SUBPAY_Date.replace(/-/g, '/'));
    return payDate >= firstDay && payDate <= lastDay;
  });
}

// Handles month picker input change
function onMonthPicked(value) {
  const [year, month] = value.split('-').map(Number);
  selectedYear = year;
  selectedMonth = month - 1;
  updateMonthView();
}

// Toggles visibility of the custom category input row
function showCustomCatInput(rowId) {
  const row = document.getElementById(rowId);
  const current = window.getComputedStyle(row).display;
  row.style.display = current === 'flex' ? 'none' : 'flex';
}

// Saves a new custom category to the DB and adds it to the dropdown
async function saveCustomCategory(selectId, inputId, rowId) {
  const name = document.getElementById(inputId).value.trim();
  if (!name) return alert('Please enter a category name');

  const formData = new FormData();
  formData.append('cat_name', name);
  formData.append('user_id', USER.USER_ID);

  const res = await fetch('/add-category', { method: 'POST', body: formData });
  if (!res.ok) return alert('Failed to save category');

  const select = document.getElementById(selectId);
  const option = document.createElement('option');
  option.value = name;
  option.textContent = name;
  select.appendChild(option);
  select.value = name;

  document.getElementById(rowId).style.display = 'none';
  document.getElementById(inputId).value = '';
}

// Deletes a custom category from the DB and reloads the page
async function deleteCategory(cat_id) {
  if (!confirm('Delete this custom category?')) return;
  const formData = new FormData();
  formData.append('cat_id', cat_id);
  formData.append('user_id', USER.USER_ID);

  const res = await fetch('/delete-category', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to delete category');
  }
}

// Pauses all payments from pause_date onwards for a subscription
async function pauseSubscription(sub_id, subpay_date) {
  if (!confirm('Pause this subscription?')) return;
  const formData = new FormData();
  formData.append('sub_id', sub_id);
  formData.append('user_id', USER.USER_ID);
  formData.append('pause_date', subpay_date);

  const res = await fetch('/pause-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to pause subscription');
  }
}

// Resumes all paused payments from resume_date onwards for a subscription
async function resumeSubscription(sub_id, subpay_date) {
  if (!confirm('Resume this subscription?')) return;
  const formData = new FormData();
  formData.append('sub_id', sub_id);
  formData.append('user_id', USER.USER_ID);
  formData.append('resume_date', subpay_date);

  const res = await fetch('/resume-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to resume subscription');
  }
}

// Updates the month label, picker value, and re-renders all dashboard sections
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

// Renders the subscription payment list for the selected month
// Clicking a card opens the payment edit modal; ✏️ opens subscription edit; ⏸️/▶️ pause/resume; 🗑️ cancels
function renderList() {
  const filtered = getFilteredSubs();
  const list = filtered.filter(s => activeFilter === 'All' || s.SUBPAY_Status === activeFilter);
  document.getElementById('subs-list').innerHTML = list.length ? list.map(s => `
    <div class="sub-card" onclick="openEditModal(${s.SUB_ID})">
      <div class="sub-icon">${getIcon(s.SUB_CAT)}</div>
      <div style="flex:1">
        <div class="sub-name">${s.SUB_Name}</div>
        <div class="sub-cat">${s.SUB_CAT || 'Uncategorized'}</div>
      </div>
      <span class="badge ${STATUS_BADGE[s.SUBPAY_Status] || ''}">${s.SUBPAY_Status}</span>
      <div>
        <div class="sub-cost">$${parseFloat(s.SUBPAY_Cost).toFixed(2)}</div>
        <div class="sub-freq">${s.SUBPAY_Date}</div>
      </div>
      <div style="display:flex;gap:4px;margin-left:8px" onclick="event.stopPropagation()">
        <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px" onclick="openPaymentModal(${s.SUBPAY_ID}, ${s.SUBPAY_Cost})">$</button>
        ${s.SUBPAY_Status === 'Active' ? `
          <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px" onclick="pauseSubscription(${s.SUB_ID}, '${s.SUBPAY_Date}')">⏸️</button>
        ` : s.SUBPAY_Status === 'Paused' ? `
          <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px" onclick="resumeSubscription(${s.SUB_ID}, '${s.SUBPAY_Date}')">▶️</button>
        ` : ''}
        ${s.SUBPAY_Status !== 'Cancelled' ? `
          <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px;color:var(--red)" onclick="cancelSubscription(${s.SUB_ID}, '${s.SUBPAY_Date}')">X</button>
        ` : ''}
      </div>
    </div>
  `).join('') : '<div style="color:var(--text-3);font-size:14px;padding:1rem 0">No subscriptions found.</div>';
}

// Opens the subscription edit modal pre-filled with the subscription's current data
function openEditModal(sub_id) {
  const s = SUBS.find(sub => sub.SUB_ID === sub_id);
  if (!s) return;
  document.getElementById('edit-sub-id').value = s.SUB_ID;
  document.getElementById('edit-sub-name').value = s.SUB_Name;
  document.getElementById('edit-sub-cat').value = s.SUB_CAT || '';
  document.getElementById('edit-sub-cost').value = s.SUBPAY_Cost;
  document.getElementById('edit-sub-freq').value = s.SUBVER_FREQ;
  document.getElementById('modal-edit').classList.add('open');
}

// Submits subscription update (name, category, cost, freq) to the backend
async function updateSubscription() {
  const formData = new FormData();
  formData.append('user_id', USER.USER_ID);
  formData.append('sub_id', document.getElementById('edit-sub-id').value);
  formData.append('sub_name', document.getElementById('edit-sub-name').value);
  formData.append('sub_cat', document.getElementById('edit-sub-cat').value);
  formData.append('subver_cost', document.getElementById('edit-sub-cost').value);
  formData.append('subver_freq', document.getElementById('edit-sub-freq').value);

  const res = await fetch('/update-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to update subscription');
  }
}

// Cancels a subscription from a specific payment date onwards
async function cancelSubscription(sub_id, subpay_date) {
  if (!confirm('Are you sure you want to cancel this subscription?')) return;
  const formData = new FormData();
  formData.append('sub_id', sub_id);
  formData.append('user_id', USER.USER_ID);
  formData.append('cancel_date', subpay_date);

  const res = await fetch('/cancel-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to cancel subscription');
  }
}

// Renders the stats cards (monthly total, annual estimate, active count)
function renderStats() {
  const filtered = getFilteredSubs();
  const active = filtered.filter(s => s.SUBPAY_Status === 'Active');
  const uniqueActive = [...new Set(active.map(s => s.SUB_ID))].length;
  const uniquePaused = [...new Set(filtered.filter(s => s.SUBPAY_Status === 'Paused').map(s => s.SUB_ID))].length;
  const monthlyTotal = active.reduce((sum, s) => sum + parseFloat(s.SUBPAY_Cost), 0);

  // annual estimate
  const annualEstimate = SUBS
  .filter(s => s.SUBPAY_Status === 'Active')
  .reduce((sum, s) => sum + parseFloat(s.SUBPAY_Cost), 0);

  document.querySelector('.stats-grid').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Monthly total</div>
      <div class="stat-value">$${monthlyTotal.toFixed(2)}</div>
      <div class="stat-sub">across ${uniqueActive} active subscriptions</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Annual estimate</div>
      <div class="stat-value">$${annualEstimate.toFixed(2)}</div>
      <div class="stat-sub">projected this year</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Active</div>
      <div class="stat-value" style="color:var(--accent)">${uniqueActive}</div>
      <div class="stat-sub">${uniquePaused} paused</div>
    </div>
  `;
}

// Renders the spending by category bar chart in the sidebar
function renderCats() {
  const filtered = getFilteredSubs();
  const active = filtered.filter(s => s.SUBPAY_Status === 'Active');
  const cats = {};
  active.forEach(s => {
    const cat = s.SUB_CAT || 'Uncategorized';
    cats[cat] = (cats[cat] || 0) + parseFloat(s.SUBPAY_Cost);
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

// Placeholder for recent activity — will use SUBSCRIPTION_PAYMENTS data when wired up
function renderActivity() {
  document.getElementById('activity').innerHTML = `
    <div style="color:var(--text-3);font-size:14px">No recent activity.</div>
  `;
}

// Collects add subscription form data and submits to backend
async function addSubscription() {
  const formData = new FormData();
  formData.append('user_id', USER.USER_ID);
  formData.append('sub_name', document.getElementById('modal-sub-name').value);
  formData.append('sub_cat', document.getElementById('modal-sub-cat').value);
  formData.append('sub_sdate', document.getElementById('modal-sub-date').value);
  formData.append('subver_cost', document.getElementById('modal-sub-cost').value);
  formData.append('subver_freq', document.getElementById('modal-sub-freq').value);

  const res = await fetch('/add-subscription', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to add subscription');
  }
}

// Opens the payment edit modal pre-filled with the payment's current cost
function openPaymentModal(subpay_id, cost) {
  document.getElementById('edit-subpay-id').value = subpay_id;
  document.getElementById('edit-subpay-cost').value = cost;
  document.getElementById('modal-payment').classList.add('open');
}

// Submits individual payment cost update to the backend
async function updatePayment() {
  const formData = new FormData();
  formData.append('user_id', USER.USER_ID);
  formData.append('subpay_id', document.getElementById('edit-subpay-id').value);
  formData.append('subpay_cost', document.getElementById('edit-subpay-cost').value);

  const res = await fetch('/update-payment', { method: 'POST', body: formData });
  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Failed to update payment');
  }
}

// Close modals when clicking on the overlay background
document.getElementById('modal-add').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.classList.remove('open');
});
document.getElementById('modal-edit').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.classList.remove('open');
});
document.getElementById('modal-payment').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.classList.remove('open');
});

// Set greeting from logged-in user data
document.querySelector('.page-title').textContent = `Hello ${USER.USER_FName}`;



// Initialize dashboard on page load
updateMonthView();
renderActivity();