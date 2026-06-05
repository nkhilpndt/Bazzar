# E-Commerce Bazaar — DBMS Project

## Quick Start (VS Code Terminal)

```bash
pip install flask
python app.py
```
Open → http://127.0.0.1:5000

---

## Login Credentials

| Account | Email | Password |
|---------|-------|----------|
| Admin   | admin@bazaar.com | admin123 |
| User    | Register your own on /register |

---

## Features by Role

### Regular User
- Register & login with personal account
- Browse all products with ₹ prices
- Place orders (select quantity + payment method)
- View MY order history & status (Pending → Processing → Shipped → Delivered)
- View MY payment transaction history

### Admin
- See ALL users in a table (who registered, when, how much they spent)
- Add / Edit / Delete products
- View ALL orders across every user
- Update order status (Shipped / Delivered etc.)
- View ALL payments & update payment status
- Revenue dashboard

---

## SQL Tables

| Table    | Key Columns |
|----------|-------------|
| users    | user_id, user_name, email, password (hashed), phone, role, created_at |
| products | product_id, product_name, description, price, stock |
| orders   | order_id, user_id, product_id, quantity, total_amt, order_date, status |
| payments | payment_id, order_id, user_id, amount, payment_method, status_p, payment_date |

## SQL Indexes
- `idx_product_name` — fast product search
- `idx_order_user`   — fast per-user order lookup  
- `idx_pay_user`     — fast per-user payment lookup
