from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, hashlib, os
from functools import wraps

app = Flask(__name__)
app.secret_key = "bazaar_secret_2024"
DB = "bazaar.db"

# ─── helpers ────────────────────────────────────────────────────────────────
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))
        return f(*a, **kw)
    return wrapper

# ─── DB init ────────────────────────────────────────────────────────────────
def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name  TEXT NOT NULL,
        email      TEXT NOT NULL UNIQUE,
        password   TEXT NOT NULL,
        phone      TEXT,
        role       TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS products (
        product_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        description  TEXT,
        price        REAL NOT NULL CHECK(price >= 0),
        stock        INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
        created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS orders (
        order_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity   INTEGER NOT NULL DEFAULT 1,
        total_amt  REAL NOT NULL,
        order_date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        status     TEXT NOT NULL DEFAULT 'Pending',
        FOREIGN KEY (user_id)    REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );

    CREATE TABLE IF NOT EXISTS payments (
        payment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id       INTEGER NOT NULL,
        user_id        INTEGER NOT NULL,
        amount         REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'UPI',
        status_p       TEXT NOT NULL DEFAULT 'Pending',
        payment_date   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (user_id)  REFERENCES users(user_id)
    );

    CREATE INDEX IF NOT EXISTS idx_product_name ON products(product_name);
    CREATE INDEX IF NOT EXISTS idx_order_user   ON orders(user_id);
    CREATE INDEX IF NOT EXISTS idx_pay_user     ON payments(user_id);
    """)

    # Admin seed
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (user_name,email,password,phone,role)
            VALUES (?,?,?,?,?)
        """, ("Admin", "admin@bazaar.com", hash_pw("admin123"), "9000000000", "admin"))

        cur.executescript("""
        INSERT INTO products (product_name,description,price,stock) VALUES
            ('OnePlus 12',       'Snapdragon 8 Gen 3 flagship phone',   64999, 50),
            ('Banarasi Saree',   'Pure silk saree with zari border',     5499, 45),
            ('Pressure Cooker', 'Hawkins 5L stainless steel',            1499, 80),
            ('Gold Earrings',    '22K gold jhumka earrings',            12500, 30),
            ('Cricket Bat',     'Kashmir willow Grade-A bat',            2999, 60),
            ('Yoga Mat',         'Anti-slip 6mm mat',                     799, 200),
            ('Laptop Bag',       '15.6" waterproof backpack',            1299, 90),
            ('Cotton Kurta',    'Handwoven festive edition',              1899,120);
        """)
        con.commit()
    con.close()

# ─── AUTH ────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET","POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    err = None
    if request.method == "POST":
        con = db()
        u = con.execute("SELECT * FROM users WHERE email=? AND password=?",
                        (request.form["email"], hash_pw(request.form["password"]))).fetchone()
        con.close()
        if u:
            session.update(user_id=u["user_id"], user_name=u["user_name"], role=u["role"])
            return redirect(url_for("dashboard"))
        err = "Invalid email or password."
    return render_template("login.html", err=err)

@app.route("/register", methods=["GET","POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    err = None
    if request.method == "POST":
        name  = request.form["user_name"].strip()
        email = request.form["email"].strip()
        pw    = request.form["password"]
        phone = request.form.get("phone","").strip()
        if len(pw) < 6:
            err = "Password must be at least 6 characters."
        else:
            con = db()
            try:
                con.execute("INSERT INTO users (user_name,email,password,phone) VALUES (?,?,?,?)",
                            (name, email, hash_pw(pw), phone))
                con.commit()
                con.close()
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                err = "Email already registered."
            finally:
                con.close()
    return render_template("register.html", err=err)

@app.route("/logout")
def logout():
    name = session.get("user_name","")
    session.clear()
    flash(f"{name} has been logged out.", "info")
    return redirect(url_for("login"))

# ─── DASHBOARD ───────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    con = db()
    if session["role"] == "admin":
        stats = {
            "users":    con.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
            "products": con.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "orders":   con.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "revenue":  con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status_p='Paid'").fetchone()[0],
        }
        recent = con.execute("""
            SELECT o.order_id, u.user_name, p.product_name, o.total_amt, o.order_date, o.status
            FROM orders o
            JOIN users u ON o.user_id=u.user_id
            JOIN products p ON o.product_id=p.product_id
            ORDER BY o.order_id DESC LIMIT 8
        """).fetchall()
    else:
        stats = {
            "orders":  con.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)).fetchone()[0],
            "pending": con.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='Pending'", (uid,)).fetchone()[0],
            "paid":    con.execute("SELECT COUNT(*) FROM payments WHERE user_id=? AND status_p='Paid'", (uid,)).fetchone()[0],
            "spent":   con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE user_id=? AND status_p='Paid'", (uid,)).fetchone()[0],
        }
        recent = con.execute("""
            SELECT o.order_id, p.product_name, o.total_amt, o.order_date, o.status
            FROM orders o JOIN products p ON o.product_id=p.product_id
            WHERE o.user_id=? ORDER BY o.order_id DESC LIMIT 5
        """, (uid,)).fetchall()
    con.close()
    return render_template("dashboard.html", stats=stats, recent=recent)

# ─── PRODUCTS ────────────────────────────────────────────────────────────────
@app.route("/products")
@login_required
def products():
    con = db()
    prods = con.execute("SELECT * FROM products ORDER BY product_id").fetchall()
    con.close()
    return render_template("products.html", products=prods)

@app.route("/products/add", methods=["POST"])
@login_required
@admin_required
def add_product():
    con = db()
    con.execute("INSERT INTO products (product_name,description,price,stock) VALUES (?,?,?,?)",
                (request.form["product_name"], request.form["description"],
                 float(request.form["price"]), int(request.form["stock"])))
    con.commit(); con.close()
    flash("Product added.", "success")
    return redirect(url_for("products"))

@app.route("/products/update/<int:pid>", methods=["POST"])
@login_required
@admin_required
def update_product(pid):
    con = db()
    con.execute("UPDATE products SET product_name=?,description=?,price=?,stock=? WHERE product_id=?",
                (request.form["product_name"], request.form["description"],
                 float(request.form["price"]), int(request.form["stock"]), pid))
    con.commit(); con.close()
    flash("Product updated.", "success")
    return redirect(url_for("products"))

@app.route("/products/delete/<int:pid>")
@login_required
@admin_required
def delete_product(pid):
    con = db()
    con.execute("DELETE FROM products WHERE product_id=?", (pid,))
    con.commit(); con.close()
    flash("Product deleted.", "info")
    return redirect(url_for("products"))

# ─── ORDERS ──────────────────────────────────────────────────────────────────
@app.route("/orders")
@login_required
def orders():
    uid = session["user_id"]
    con = db()
    if session["role"] == "admin":
        rows = con.execute("""
            SELECT o.order_id, u.user_name, u.email, p.product_name,
                   o.quantity, o.total_amt, o.order_date, o.status
            FROM orders o
            JOIN users u ON o.user_id=u.user_id
            JOIN products p ON o.product_id=p.product_id
            ORDER BY o.order_id DESC
        """).fetchall()
    else:
        rows = con.execute("""
            SELECT o.order_id, p.product_name, o.quantity,
                   o.total_amt, o.order_date, o.status
            FROM orders o
            JOIN products p ON o.product_id=p.product_id
            WHERE o.user_id=? ORDER BY o.order_id DESC
        """, (uid,)).fetchall()
    con.close()
    return render_template("orders.html", orders=rows)

@app.route("/orders/place/<int:pid>", methods=["POST"])
@login_required
def place_order(pid):
    uid = session["user_id"]
    qty = int(request.form.get("quantity", 1))
    con = db()
    prod = con.execute("SELECT * FROM products WHERE product_id=?", (pid,)).fetchone()
    if not prod or prod["stock"] < qty:
        flash("Insufficient stock.", "error")
        con.close()
        return redirect(url_for("products"))
    total = prod["price"] * qty
    con.execute("UPDATE products SET stock=stock-? WHERE product_id=?", (qty, pid))
    cur = con.execute(
        "INSERT INTO orders (user_id,product_id,quantity,total_amt,status) VALUES (?,?,?,?,'Processing')",
        (uid, pid, qty, total))
    order_id = cur.lastrowid
    method = request.form.get("payment_method", "UPI")
    con.execute("INSERT INTO payments (order_id,user_id,amount,payment_method,status_p) VALUES (?,?,?,?,'Paid')",
                (order_id, uid, total, method))
    con.commit(); con.close()
    flash(f"Order placed! ₹{total:,.0f} paid via {method}.", "success")
    return redirect(url_for("orders"))

@app.route("/orders/update/<int:oid>", methods=["POST"])
@login_required
@admin_required
def update_order(oid):
    con = db()
    con.execute("UPDATE orders SET status=? WHERE order_id=?",
                (request.form["status"], oid))
    con.commit(); con.close()
    flash("Order status updated.", "success")
    return redirect(url_for("orders"))

# ─── PAYMENTS ────────────────────────────────────────────────────────────────
@app.route("/payments")
@login_required
def payments():
    uid = session["user_id"]
    con = db()
    if session["role"] == "admin":
        rows = con.execute("""
            SELECT pay.payment_id, pay.order_id, u.user_name, u.email,
                   p.product_name, pay.amount, pay.payment_method,
                   pay.status_p, pay.payment_date
            FROM payments pay
            JOIN users u ON pay.user_id=u.user_id
            JOIN orders o ON pay.order_id=o.order_id
            JOIN products p ON o.product_id=p.product_id
            ORDER BY pay.payment_id DESC
        """).fetchall()
        total_paid    = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status_p='Paid'").fetchone()[0]
        total_pending = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status_p='Pending'").fetchone()[0]
    else:
        rows = con.execute("""
            SELECT pay.payment_id, pay.order_id, p.product_name,
                   pay.amount, pay.payment_method, pay.status_p, pay.payment_date
            FROM payments pay
            JOIN orders o ON pay.order_id=o.order_id
            JOIN products p ON o.product_id=p.product_id
            WHERE pay.user_id=? ORDER BY pay.payment_id DESC
        """, (uid,)).fetchall()
        total_paid    = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE user_id=? AND status_p='Paid'", (uid,)).fetchone()[0]
        total_pending = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE user_id=? AND status_p='Pending'", (uid,)).fetchone()[0]
    con.close()
    return render_template("payments.html", payments=rows,
                           total_paid=total_paid, total_pending=total_pending)

@app.route("/payments/update/<int:pid>", methods=["POST"])
@login_required
@admin_required
def update_payment(pid):
    con = db()
    con.execute("UPDATE payments SET status_p=? WHERE payment_id=?",
                (request.form["status_p"], pid))
    con.commit(); con.close()
    flash("Payment status updated.", "success")
    return redirect(url_for("payments"))

# ─── ADMIN: ALL USERS ────────────────────────────────────────────────────────
@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    con = db()
    rows = con.execute("""
        SELECT u.user_id, u.user_name, u.email, u.phone, u.role, u.created_at,
               COUNT(DISTINCT o.order_id) AS total_orders,
               COALESCE(SUM(pay.amount),0) AS total_spent
        FROM users u
        LEFT JOIN orders o   ON o.user_id=u.user_id
        LEFT JOIN payments pay ON pay.user_id=u.user_id AND pay.status_p='Paid'
        GROUP BY u.user_id
        ORDER BY u.user_id
    """).fetchall()
    con.close()
    return render_template("admin_users.html", users=rows)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

