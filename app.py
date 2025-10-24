from flask import Flask, request, jsonify, send_from_directory
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from flask_cors import CORS

DB_PATH = "data.db"
app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app)


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                is_admin INTEGER DEFAULT 0
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator TEXT,
                amount REAL,
                date TEXT,
                description TEXT,
                discount INTEGER,
                created_at TEXT,
                due_at TEXT
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS bill_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER,
                username TEXT,
                share_amount REAL,
                is_paid INTEGER DEFAULT 0,
                paid_at TEXT,
                FOREIGN KEY (bill_id) REFERENCES bills(id)
            )"""
        )
        conn.commit()

        # ensure default admin exists
        c.execute("SELECT 1 FROM users WHERE username = ?", ("admin",))
        if not c.fetchone():
            c.execute(
                "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                ("admin", "admin123", 1),
            )
            conn.commit()


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_admin_username(conn, username):
    if not username:
        return False
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    return bool(row and row["is_admin"])


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password required"}), 400

    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT username, is_admin FROM users WHERE username=? AND password=?",
            (username, password),
        )
        row = c.fetchone()
    finally:
        conn.close()

    if row:
        return jsonify(
            {"ok": True, "username": row["username"], "is_admin": bool(row["is_admin"])}
        )
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


@app.route("/api/admin/add_user", methods=["POST"])
def admin_add_user():
    data = request.json or {}
    admin = data.get("admin")
    username = data.get("username")
    password = data.get("password")

    if not admin or not username or not password:
        return jsonify(
            {"ok": False, "error": "admin, username and password required"}
        ), 400

    conn = db_conn()
    try:
        if not is_admin_username(conn, admin):
            return jsonify({"ok": False, "error": "Not authorized"}), 403

        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                (username, password, 0),
            )
            conn.commit()
            return jsonify({"ok": True})
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "user exists"}), 400
    finally:
        conn.close()


@app.route("/api/admin/delete_user", methods=["POST"])
def admin_delete_user():
    data = request.json or {}
    admin = data.get("admin")
    username = data.get("username")

    if not admin or not username:
        return jsonify({"ok": False, "error": "admin and username required"}), 400

    if username == "admin":
        return jsonify({"ok": False, "error": "cannot delete admin"}), 400

    conn = db_conn()
    try:
        if not is_admin_username(conn, admin):
            return jsonify({"ok": False, "error": "Not authorized"}), 403

        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/users", methods=["GET"])
def list_users():
    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT username FROM users ORDER BY username")
        rows = [r["username"] for r in c.fetchall()]
        return jsonify({"ok": True, "users": rows})
    finally:
        conn.close()


def distribute_shares(
    total_amount: float, participant_usernames: list[str], creator: str, discount: bool
):
    seen = set()
    participants = [
        p.strip()
        for p in participant_usernames
        if p and p.strip() not in seen and not seen.add(p.strip())
    ]
    if creator not in participants:
        participants.append(creator)

    n = len(participants)
    if n == 0:
        raise ValueError("no participants")

    if discount:
        # others pay slightly more so creator gets 25% off
        # total = x (creator) + (n-1)*y
        # x = 0.75*y => total = 0.75*y + (n-1)*y = (n-0.25)*y
        # y = total / (n - 0.25)
        y = total_amount / (n - 0.25)
        x = 0.75 * y
        exact_shares = [x if p == creator else y for p in participants]
    else:
        equal = total_amount / n
        exact_shares = [equal] * n

    rounded = [round(s, 2) for s in exact_shares]
    diff = round(total_amount - sum(rounded), 2)
    if abs(diff) >= 0.01:
        rounded[-1] = round(rounded[-1] + diff, 2)

    now_iso = datetime.utcnow().isoformat()
    results = [
        (p, s, 1 if p == creator else 0, now_iso if p == creator else None)
        for p, s in zip(participants, rounded)
    ]
    return results


@app.route("/api/bills", methods=["GET", "POST"])
def bills():
    # ---------- GET ----------
    if request.method == "GET":
        username = request.args.get("username")
        conn = db_conn()
        try:
            c = conn.cursor()

            if username:
                if not is_admin_username(conn, username):
                    # non-admin: only see bills they are involved in
                    c.execute(
                        """SELECT * FROM bills WHERE id IN (
                            SELECT bill_id FROM bill_shares WHERE username=?
                        ) ORDER BY created_at DESC""",
                        (username,),
                    )
                else:
                    # admin sees all
                    c.execute("SELECT * FROM bills ORDER BY created_at DESC")
            else:
                # default (no username)
                c.execute("SELECT * FROM bills ORDER BY created_at DESC")

            bills_out = []
            for b in c.fetchall():
                bid = b["id"]
                c2 = conn.cursor()
                c2.execute(
                    "SELECT username, share_amount, is_paid, paid_at FROM bill_shares WHERE bill_id=?",
                    (bid,),
                )
                shares = [dict(r) for r in c2.fetchall()]
                bills_out.append(
                    {
                        "id": bid,
                        "creator": b["creator"],
                        "amount": b["amount"],
                        "date": b["date"],
                        "description": b["description"],
                        "discount": bool(b["discount"]),
                        "created_at": b["created_at"],
                        "due_at": b["due_at"],
                        "shares": shares,
                    }
                )
            return jsonify({"ok": True, "bills": bills_out})
        finally:
            conn.close()

    # ---------- POST (create new bill) ----------
    data = request.json or {}
    creator = data.get("creator")
    amount_raw = data.get("amount", 0)
    date = data.get("date", "")
    description = data.get("description", "")
    participants = data.get("participants", [])
    discount = bool(data.get("discount", False))

    if not creator:
        return jsonify({"ok": False, "error": "creator required"}), 400

    if not isinstance(participants, list):
        return jsonify({"ok": False, "error": "participants must be a list"}), 400

    # parse amount
    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid amount"}), 400

    # filter out admin from participants
    conn = db_conn()
    try:
        participants = [p for p in participants if not is_admin_username(conn, p)]
    finally:
        conn.close()

    # distribute shares (includes creator automatically)
    try:
        shares_info = distribute_shares(amount, participants, creator, discount)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    now = datetime.utcnow()
    due = now + timedelta(hours=24)

    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO bills (creator, amount, date, description, discount, created_at, due_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                creator,
                amount,
                date,
                description,
                int(discount),
                now.isoformat(),
                due.isoformat(),
            ),
        )
        bill_id = c.lastrowid

        for username, share_amount, is_paid, paid_at in shares_info:
            c.execute(
                "INSERT INTO bill_shares (bill_id, username, share_amount, is_paid, paid_at) VALUES (?, ?, ?, ?, ?)",
                (bill_id, username, share_amount, is_paid, paid_at),
            )

        conn.commit()
        return jsonify({"ok": True, "bill_id": bill_id})
    finally:
        conn.close()


@app.route("/api/bills/<int:bill_id>/pay", methods=["POST"])
def pay_share(bill_id):
    data = request.json or {}
    username = data.get("username")
    if not username:
        return jsonify({"ok": False, "error": "username required"}), 400

    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, is_paid FROM bill_shares WHERE bill_id=? AND username=?",
            (bill_id, username),
        )
        row = c.fetchone()
        if not row:
            return jsonify({"ok": False, "error": "share not found"}), 404
        if row["is_paid"]:
            return jsonify({"ok": False, "error": "already paid"}), 400
        paid_at = datetime.utcnow().isoformat()
        c.execute(
            "UPDATE bill_shares SET is_paid=1, paid_at=? WHERE id=?",
            (paid_at, row["id"]),
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/bills/<int:bill_id>", methods=["GET"])
def get_bill(bill_id):
    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM bills WHERE id=?", (bill_id,))
        b = c.fetchone()
        if not b:
            return jsonify({"ok": False, "error": "not found"}), 404
        c.execute(
            "SELECT username, share_amount, is_paid, paid_at FROM bill_shares WHERE bill_id=?",
            (bill_id,),
        )
        shares = [dict(r) for r in c.fetchall()]
        return jsonify(
            {
                "ok": True,
                "bill": {
                    "id": b["id"],
                    "creator": b["creator"],
                    "amount": b["amount"],
                    "date": b["date"],
                    "description": b["description"],
                    "discount": bool(b["discount"]),
                    "created_at": b["created_at"],
                    "due_at": b["due_at"],
                    "shares": shares,
                },
            }
        )
    finally:
        conn.close()


@app.route("/api/admin/delete_bill", methods=["POST"])
def admin_delete_bill():
    data = request.json or {}
    admin = data.get("admin")
    bill_id = data.get("bill_id")

    if not admin or not bill_id:
        return jsonify({"ok": False, "error": "admin and bill_id required"}), 400

    conn = db_conn()
    try:
        if not is_admin_username(conn, admin):
            return jsonify({"ok": False, "error": "Not authorized"}), 403

        c = conn.cursor()
        c.execute("DELETE FROM bill_shares WHERE bill_id=?", (bill_id,))
        c.execute("DELETE FROM bills WHERE id=?", (bill_id,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
