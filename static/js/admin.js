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

  document.getElementById('search-results').innerHTML = results.length
    ? results.map(u => `
        <div class="user-result">
          <div class="user-avatar">${u.USER_FName[0]}${u.USER_LName[0]}</div>
          <div style="flex:1">
            <div style="font-weight:500;font-size:14px">${u.USER_FName} ${u.USER_LName}</div>
            <div style="font-size:12px;color:var(--text-3)">${u.USER_Email} · ID: ${u.USER_ID}</div>
          </div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px"
              onclick="window.open('/${u.USER_ID}/dashboard','_blank')">Visit dashboard</button>
            <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px"
              onclick='selectUser(${JSON.stringify(u).replace(/"/g, "&quot;")});document.getElementById("modal-edit-user").classList.add("open")'>Edit account</button>
            <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px;color:var(--red)"
              onclick='selectUser(${JSON.stringify(u).replace(/"/g, "&quot;")});deleteUser()'>Delete account</button>
          </div>
        </div>`).join('')
    : '<div style="color:var(--text-3);font-size:14px">No users found.</div>';
  }



    async function deleteUser() {
      if (!selectedUser) return;
      if (!confirm(`Delete ${selectedUser.USER_FName}'s account and all their data? This cannot be undone.`)) return;
      const fd = new FormData();
      fd.append('user_id', document.body.dataset.userId);        // logged-in admin
      fd.append('target_user_id', selectedUser.USER_ID);         // user to delete

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