from flask import Blueprint, render_template, redirect, url_for, session, flash, request, send_file
from functools import wraps
from database.connection import get_db_connection
from werkzeug.security import generate_password_hash
from modules.utils import admin_required
admin_bp = Blueprint('admin', __name__, template_folder='../templates')
import io
from reportlab.pdfgen import canvas
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



@admin_bp.route('/sales_report')
def sales_report():
    period = request.args.get('period', 'daily') # daily, weekly, monthly
    export_type = request.args.get('export')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. SQL Logic for different timeframes
    if period == 'weekly':
        date_query = "WHERE order_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
    elif period == 'monthly':
        date_query = "WHERE order_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
    else: # daily
        date_query = "WHERE DATE(order_date) = CURDATE()"

    query = f"""
        SELECT o.order_id, o.order_date, o.total_amount, u.name as customer_name, o.status
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        {date_query}
        ORDER BY o.order_date DESC
    """
    cursor.execute(query)
    sales_data = cursor.fetchall()
    
    total_sales = sum(float(item['total_amount']) for item in sales_data)

    # 2. Handle Exporting to PDF
    if export_type == 'pdf':
        return generate_pdf_report(sales_data, period, total_sales)

    cursor.close()
    conn.close()
    return render_template('admin/sales_report.html', 
                           sales=sales_data, 
                           period=period, 
                           total_sales=total_sales)

def generate_pdf_report(data, period, total):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, f"Paper Haven - {period.capitalize()} Sales Report")
    
    p.setFont("Helvetica", 12)
    y = 750
    p.drawString(100, y, "Order ID | Customer | Date | Amount")
    y -= 20
    
    for row in data:
        p.drawString(100, y, f"{row['order_id']} | {row['customer_name']} | {row['order_date'].strftime('%Y-%m-%d')} | ₱{row['total_amount']}")
        y -= 20
        if y < 50: p.showPage(); y = 800 # Handle page overflow
        
    p.drawString(100, y - 20, f"TOTAL REVENUE: ₱{total:.2f}")
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"sales_{period}.pdf")
