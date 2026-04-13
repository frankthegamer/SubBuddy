function showPanel(which) {
  document.querySelectorAll('.form-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.login-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + which).classList.add('active');
  document.querySelectorAll('.login-tab').forEach(b => {
    if (b.getAttribute('onclick').includes(which)) b.classList.add('active');
  });
}

async function signIn() {
  const email = document.getElementById('si-email').value;
  const password = document.getElementById('si-pass').value;

  const formData = new FormData();
  formData.append('user_email', email);
  formData.append('user_password', password);

  const res = await fetch('/', { method: 'POST', body: formData });

  if (res.redirected) {
    window.location.href = res.url;
  } else {
    const data = await res.json();
    alert(data.error || 'Login failed');
  }
}

async function register() {
  const formData = new FormData();
  formData.append('user_fname', document.getElementById('r-fname').value);
  formData.append('user_lname', document.getElementById('r-lname').value);
  formData.append('user_email', document.getElementById('r-email').value);
  formData.append('user_password', document.getElementById('r-pass').value);
  formData.append('user_phone', document.getElementById('r-phone').value);

  const res = await fetch('/register', { method: 'POST', body: formData });

  if (res.redirected) {
    window.location.href = res.url;
  } else {
    alert('Registration failed');
  }
}