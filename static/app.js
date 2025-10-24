const api = (path, opts) => fetch('/api' + path, opts).then((r) => r.json());
let session = JSON.parse(localStorage.getItem('session') || 'null');
let currentFilter = 'all';

const dom = {
  authCard: document.getElementById('authCard'),
  adminPanel: document.getElementById('adminPanel'),
  userPanel: document.getElementById('userPanel'),
  billsCard: document.getElementById('billsCard'),
  sessionArea: document.getElementById('sessionArea'),
  usersList: document.getElementById('usersList'),
  participants: document.getElementById('participants'),
  billsArea: document.getElementById('billsArea'),
};

function setSession(s) {
  session = s;
  localStorage.setItem('session', JSON.stringify(s));
  renderSession();
}

function clearSession() {
  session = null;
  localStorage.removeItem('session');
  renderSession();
}

function renderSession() {
  if (!session) {
    dom.authCard.classList.remove('hidden');
    dom.adminPanel.classList.add('hidden');
    dom.userPanel.classList.add('hidden');
    dom.billsCard.classList.add('hidden');
    dom.sessionArea.innerHTML = '';
    return;
  }

  dom.authCard.classList.add('hidden');
  dom.billsCard.classList.remove('hidden');
  dom.sessionArea.innerHTML = `
    <div class="smallmuted">Logged in as <b>${session.username}</b> ${
    session.is_admin ? '<span class="badge">Admin</span>' : ''
  }</div>
    <button id="logoutBtn" class="linkbtn">Logout</button>
  `;
  document.getElementById('logoutBtn').onclick = clearSession;

  if (session.is_admin) dom.adminPanel.classList.remove('hidden');
  else dom.adminPanel.classList.add('hidden');

  dom.userPanel.classList.remove('hidden');
  document.getElementById('billDate').value = new Date()
    .toISOString()
    .slice(0, 10);
  loadUsers();
  loadBills();
}

document.getElementById('loginBtn').onclick = async () => {
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  if (!username || !password) return alert('Enter username and password');
  const res = await api('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (res.ok) setSession({ username: res.username, is_admin: res.is_admin });
  else alert(res.error || 'Login failed');
};

document.getElementById('addUserBtn').onclick = async () => {
  const username = document.getElementById('newUser').value.trim();
  const password = document.getElementById('newPass').value;
  if (!username || !password) return alert('Enter username and password');
  const res = await api('/admin/add_user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ admin: session.username, username, password }),
  });
  if (res.ok) {
    document.getElementById('newUser').value = '';
    document.getElementById('newPass').value = '';
    loadUsers();
  } else alert(res.error || 'Error adding user');
};

async function loadUsers() {
  const res = await api('/users');
  if (!res.ok) return alert('Could not load users');
  dom.usersList.innerHTML = '';
  dom.participants.innerHTML = '';

  for (const u of res.users) {
    const pill = document.createElement('div');
    pill.className = 'user-pill';
    pill.textContent = u;

    if (session.is_admin && u !== 'admin') {
      const del = document.createElement('button');
      del.className = 'linkbtn';
      del.textContent = 'Delete';
      del.onclick = async () => {
        if (!confirm(`Are you sure you want to delete ${u}?`)) return;
        const r = await api('/admin/delete_user', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin: session.username, username: u }),
        });
        if (r.ok) loadUsers();
        else alert(r.error || 'Error deleting user');
      };
      pill.appendChild(del);
    }
    dom.usersList.appendChild(pill);

    // skip admin in participants
    if (u === 'admin') continue;
    const lbl = document.createElement('label');
    lbl.className = 'user-pill';
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.value = u;
    if (u === session.username) {
      chk.checked = true;
      chk.disabled = true;
    }
    lbl.appendChild(chk);
    lbl.appendChild(document.createTextNode(u));
    dom.participants.appendChild(lbl);
  }
}

document.getElementById('createBillBtn').onclick = async () => {
  const amount = parseFloat(document.getElementById('billAmount').value);
  const date = document.getElementById('billDate').value;
  const description = document.getElementById('billDesc').value || '';
  const discount = document.getElementById('discount').checked;
  if (!amount || amount <= 0) return alert('Enter valid amount');

  const selected = Array.from(
    dom.participants.querySelectorAll('input:checked')
  ).map((i) => i.value);
  if (!selected.length) return alert('Select participants');

  const res = await api('/bills', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      creator: session.username,
      amount,
      date,
      description,
      participants: selected,
      discount,
    }),
  });
  if (res.ok) {
    document.getElementById('billAmount').value = '';
    document.getElementById('billDesc').value = '';
    document.getElementById('discount').checked = false;
    loadBills();
  } else alert(res.error || 'Error creating bill');
};

async function loadBills() {
  const res = await api(`/bills?username=${session.username}`);
  if (!res.ok) return (dom.billsArea.innerHTML = 'Error loading bills');

  const bills = res.bills.filter((b) => {
    if (currentFilter === 'unpaid-me')
      return b.shares.some(
        (s) => s.username === session.username && !s.is_paid
      );
    if (currentFilter === 'my-bills') return b.creator === session.username;
    if (currentFilter === 'unpaid-any') return b.shares.some((s) => !s.is_paid);
    return true;
  });

  dom.billsArea.innerHTML = '';
  for (const b of bills) {
    const total = b.shares.length;
    const paid = b.shares.filter((s) => s.is_paid).length;
    let statusColor = 'status-red';
    if (paid === total) statusColor = 'status-green';
    else if (paid > total / 2) statusColor = 'status-orange';

    const header = document.createElement('div');
    header.className = 'expand-header';
    header.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <b>${b.description || 'No description'}</b><br>
          <span class="smallmuted">${b.date} • Total: ${b.amount.toFixed(
      2
    )} • Creator: ${b.creator} ${
      b.discount ? '<span class="badge-warn">25% off</span>' : ''
    }</span>
        </div>
        <div class="smallmuted right">
          Due: ${formatDate(b.due_at)}<br>
          ${
            session.username === b.creator
              ? `<span class="status-bar ${statusColor}">${paid}/${total} paid</span>`
              : ''
          }
        </div>
      </div>
    `;
    if (session.username === 'admin') {
      const delBtn = document.createElement('button');
      delBtn.textContent = '🗑️ Delete';
      delBtn.className = 'delete-bill-btn';
      delBtn.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm('Delete this bill?')) return;

        const r = await api('/admin/delete_bill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin: session.username, bill_id: b.id }),
        });

        if (r.ok) {
          alert('Bill deleted!');
          loadBills();
        } else {
          alert(r.error || 'Error deleting bill');
        }
      };

      // Add the button to the right side of header
      header
        .querySelector('div[style*="justify-content:space-between"]')
        .appendChild(delBtn);
    }

    const content = document.createElement('div');
    content.className = 'hidden';

    const tbl = document.createElement('table');
    tbl.className = 'table';
    tbl.innerHTML = `<thead><tr><th>User</th><th>Share</th><th>Status</th><th></th></tr></thead>`;
    const tbody = document.createElement('tbody');

    for (const s of b.shares) {
      const tr = document.createElement('tr');
      const paidBadge = s.is_paid
        ? '<span class="badge">Paid</span>'
        : '<span class="badge-warn">Unpaid</span>';
      tr.innerHTML = `
        <td>${s.username}${s.username === b.creator ? ' • creator' : ''}</td>
        <td>${s.share_amount.toFixed(2)}</td>
        <td>${paidBadge}</td>
        <td></td>
      `;
      if (!s.is_paid && s.username === session.username) {
        const payBtn = document.createElement('button');
        payBtn.className = 'btn';
        payBtn.textContent = 'Mark Paid';
        payBtn.onclick = async () => {
          const r = await api(`/bills/${b.id}/pay`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: session.username }),
          });
          if (r.ok) loadBills();
          else alert(r.error || 'Error');
        };
        tr.querySelector('td:last-child').appendChild(payBtn);
      }
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    content.appendChild(tbl);

    const wrapper = document.createElement('div');
    wrapper.className = 'card';
    wrapper.appendChild(header);
    wrapper.appendChild(content);

    header.onclick = () => content.classList.toggle('hidden');
    dom.billsArea.appendChild(wrapper);
  }
}

function formatDate(d) {
  const date = new Date(d);
  return date.toLocaleString('en-US', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

document.addEventListener('click', (e) => {
  if (e.target.classList.contains('filter-btn')) {
    currentFilter = e.target.dataset.filter;
    document
      .querySelectorAll('.filter-btn')
      .forEach((btn) => btn.classList.remove('active'));
    e.target.classList.add('active');
    loadBills();
  }
});

window.onload = renderSession;
