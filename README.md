# 💸 Bill Split Web App

A lightweight **bill-splitting web app** built with **Flask**, **SQLite**, and **vanilla HTML/CSS/JS** — no frameworks or dependencies beyond the basics.

---

## 🚀 Features

- **Admin Login**
  - Default credentials: `admin / admin123`
  - Add or remove users easily
- **User Dashboard**
  - Create and view bill splits
  - Automatically calculates each user's share
  - Option for the creator to get a **25% discount**
  - 24-hour due period for each bill
  - View who paid and who hasn’t
- **Simple Payments**
  - Each participant can mark their share as paid

---

## 🧠 Tech Stack

- **Frontend:** HTML, CSS, Vanilla JS  
- **Backend:** Python (Flask)  
- **Database:** SQLite (via Python `sqlite3` library)

---

## 🗂️ Project Structure

```

bill-split-webapp/
├── app.py               # Main Flask app
├── db.db                # Handles database logic
├── requirements.txt     # Dependencies
├── static/
│   ├── style.css        # UI styling
│   └── script.js        # Frontend logic & API calls
├── templates/
│   └── index.html       # Main web page
└── README.md

````

---

## ⚙️ Run Locally

1. Clone the repo:
   ```bash
   git clone https://github.com/AnasMansha/bill-split-webapp.git
   cd bill-split-webapp
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   python app.py
   ```

4. Visit:

   ```
   http://localhost:5000
   ```

---


## 👤 Admin Credentials

| Username | Password   |
| -------- | ---------- |
| `admin`  | `admin123` |

---

## 📸 Preview

Simple UI built with minimal HTML and CSS — clean, responsive, and focused on usability.

---

## 🧾 License

MIT License — free for personal or educational use.
