let selectedUser = null;

    function switchTab(btn, panelId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(panelId).classList.add('active');
    }

    async function searchUsers() {
      const q = document.getElementById('search-input').value.trim();
      if (!q) return;
      const res = await fetch(`/admin/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      const results = data.users;

      document.getElementById('user-detail').style.display = 'none';
      document.getElementById('search-results').innerHTML = results.length
        ? results.map(u => `
            <div class="user-result" onclick="selectUser(${JSON.stringify(u).replace(/"/g, '&quot;')})">
              <div class="user-avatar">${u.USER_FName[0]}${u.USER_LName[0]}</div>
              <div style="flex:1">
                <div style="font-weight:500;font-size:14px">${u.USER_FName} ${u.USER_LName}</div>
                <div style="font-size:12px;color:var(--text-3)">${u.USER_Email}</div>
              </div>
              <div style="font-size:12px;color:var(--text-3)">ID: ${u.USER_ID}</div>
            </div>`).join('')
        : '<div style="color:var(--text-3);font-size:14px">No users found.</div>';
    }

    async function selectUser(user) {
      selectedUser = user;

      // Fill edit modal fields
      document.getElementById('edit-user-id').value = user.USER_ID;
      document.getElementById('edit-user-fname').value = user.USER_FName;
      document.getElementById('edit-user-lname').value = user.USER_LName;
      document.getElementById('edit-user-email').value = user.USER_Email;
      document.getElementById('edit-user-phone').value = user.USER_Phone || '';

      document.getElementById('detail-name').textContent = `${user.USER_FName} ${user.USER_LName}`;
      document.getElementById('detail-email').textContent = user.USER_Email;

      document.getElementById('user-detail').style.display = 'block';
    }

    function renderUserSubs(subs, userId) {
      const el = document.getElementById('user-subs');
      if (!subs.length) {
        el.innerHTML = '<div style="color:var(--text-3);font-size:14px">No subscriptions.</div>';
        return;
      }
      // Group by SUB_ID to show one row per subscription (latest payment)
      const seen = new Set();
      const unique = subs.filter(s => {
        if (seen.has(s.SUB_ID)) return false;
        seen.add(s.SUB_ID); return true;
      });
      el.innerHTML = `<div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">` +
        unique.map(s => `
          <div class="sub-row">
            <span style="flex:1;font-weight:500">${s.SUB_Name}</span>
            <span style="color:var(--text-3)">${s.SUB_CAT || 'Uncategorized'}</span>
            <span style="font-family:'DM Mono',monospace">$${parseFloat(s.SUBPAY_Cost).toFixed(2)}</span>
            <button class="btn btn-secondary" style="padding:2px 8px;font-size:12px"
              onclick="openEditSub(${JSON.stringify(s).replace(/"/g, '&quot;')}, ${userId})">✏️</button>
            <button class="btn btn-secondary" style="padding:2px 8px;font-size:12px;color:var(--red)"
              onclick="deleteSub(${s.SUB_ID})">🗑️</button>
          </div>`).join('') + `</div>`;
    }

    function openEditSub(s, userId) {
      document.getElementById('edit-sub-user-id').value = userId;
      document.getElementById('edit-sub-id').value = s.SUB_ID;
      document.getElementById('edit-sub-name').value = s.SUB_Name;
      document.getElementById('edit-sub-cat').value = s.SUB_CAT || '';
      document.getElementById('edit-sub-cost').value = s.SUBPAY_Cost;
      document.getElementById('edit-sub-freq').value = s.SUBVER_FREQ;
      document.getElementById('modal-edit-sub').classList.add('open');
    }

    async function deleteSub(sub_id) {
      if (!confirm('Delete this subscription and all its payment history?')) return;
      const fd = new FormData();
      fd.append('sub_id', sub_id);
      await fetch('/admin/delete-subscription', { method: 'POST', body: fd });
      if (selectedUser) selectUser(selectedUser); // refresh
    }

    async function deleteUser() {
      if (!selectedUser) return;
      if (!confirm(`Delete ${selectedUser.USER_FName}'s account and all their data? This cannot be undone.`)) return;
      const fd = new FormData();
      fd.append('user_id', selectedUser.USER_ID);
      await fetch('/admin/delete-user', { method: 'POST', body: fd });
      document.getElementById('user-detail').style.display = 'none';
      document.getElementById('search-results').innerHTML = '';
      selectedUser = null;
    }

    function openReassignModal(fam_id) {
      document.getElementById('reassign-fam-id').value = fam_id;
      document.getElementById('modal-reassign').classList.add('open');
    }

    async function dissolveFamily(fam_id, name) {
        if (!confirm(`Dissolve "${name}"? All members will be removed.`)) return;
        const userId = document.body.dataset.userId;
        const fd = new FormData();
        fd.append('fam_id', fam_id);
        fd.append('user_id', userId);
        const res = await fetch('/admin/dissolve-family', { method: 'POST', body: fd });
        window.location.href = `/${userId}/admin`;
    }

    function toggleProfileMenu() {
      const menu = document.getElementById('profile-menu');
      menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }

    function viewSubscriptions() {
        if (!selectedUser) return;
        window.open(`/${selectedUser.USER_ID}/dashboard`, '_blank');
    }


    function openEditFamily(fam_id, fam_name, fam_slimit) {
      document.getElementById('edit-fam-id').value = fam_id;
      document.getElementById('edit-fam-name').value = fam_name;
      document.getElementById('edit-fam-slimit').value = fam_slimit || '';
      document.getElementById('modal-edit-family').classList.add('open');
    }

    document.addEventListener('click', e => {
      const menu = document.getElementById('profile-menu');
      const avatar = document.querySelector('.avatar');
      if (menu && avatar && !menu.contains(e.target) && !avatar.contains(e.target))
        menu.style.display = 'none';
    });
    document.querySelectorAll('.modal-overlay').forEach(m => {
      m.addEventListener('click', e => { if (e.target === m) m.classList.remove('open'); });
    });

    // Allow pressing Enter to search
    document.getElementById('search-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') searchUsers();
    });