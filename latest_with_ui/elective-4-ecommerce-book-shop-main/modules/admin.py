from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from functools import wraps
from database.connection import get_db_connection
from werkzeug.security import generate_password_hash
from modules.utils import admin_required
admin_bp = Blueprint('admin', __name__, template_folder='../templates')

# ==================================================
# DASHBOARD
# ==================================================


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')


# ==================================================
# PRODUCTS MANAGEMENT
# ==================================================
@admin_bp.route('/products')
@admin_required
def manage_products():
    return render_template('admin/manage_products.html')


# ==================================================
# CATEGORIES MANAGEMENT
# ==================================================
@admin_bp.route('/categories')
@admin_required
def manage_categories():
    return render_template('admin/manage_categories.html')


# ==================================================
# ORDERS MANAGEMENT
# ==================================================
@admin_bp.route('/orders')
@admin_required
def process_orders():
    return render_template('admin/process_orders.html')


# ==================================================
# USERS MANAGEMENT (Search + Filter)
# ==================================================
@admin_bp.route('/users')
@admin_required
def manage_users():
    """Display all customers for admin control with search & filter"""
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    sql = "SELECT * FROM users WHERE role = 'customer'"
    params = []

    if search_query:
        sql += " AND (name LIKE %s OR email LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    if status_filter != 'all':
        sql += " AND status = %s"
        params.append(status_filter)

    sql += " ORDER BY user_id DESC"

    cur.execute(sql, params)
    users = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        'admin/manage_users.html',
        users=users,
        search_query=search_query,
        status_filter=status_filter
    )


# ==================================================
# ACTIVATE / DEACTIVATE USER
# ==================================================
@admin_bp.route('/user/<int:user_id>/toggle/<string:action>')
@admin_required
def toggle_user_status(user_id, action):
    status = 'active' if action == 'activate' else 'inactive'

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET status=%s WHERE user_id=%s",
                (status, user_id))
    conn.commit()
    cur.close()
    conn.close()

    flash(f"User account has been {status}.", "info")
    return redirect(url_for('admin.manage_users'))


# ==================================================
# RESET USER PASSWORD
# ==================================================
@admin_bp.route('/user/<int:user_id>/reset_password')
@admin_required
def reset_user_password(user_id):
    new_password = generate_password_hash("123456")  # default reset password
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password=%s WHERE user_id=%s",
                (new_password, user_id))
    conn.commit()
    cur.close()
    conn.close()

    flash("User password has been reset to '123456'.", "warning")
    return redirect(url_for('admin.manage_users'))
