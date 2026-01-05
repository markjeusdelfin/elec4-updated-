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
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category_id', 'all')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Fetch categories for filter dropdown
        cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
        categories = cursor.fetchall()
        
        # Build query with filters
        query = """
            SELECT p.*, c.category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.category_id 
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (p.title LIKE %s OR p.author LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        if category_id and category_id != "all":
            query += " AND p.category_id = %s"
            params.append(category_id)
        
        query += " ORDER BY p.product_id ASC"
        cursor.execute(query, tuple(params))
        products = cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/manage_products.html', 
                           products=products, 
                           categories=categories,
                           selected_category=category_id,
                           search=search)


# ==================================================
# CATEGORIES MANAGEMENT
# ==================================================
@admin_bp.route('/categories')
@admin_required
def manage_categories():
    search = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if search:
            cursor.execute("""
                SELECT * FROM categories
                WHERE category_name LIKE %s OR description LIKE %s
                ORDER BY created_at ASC
            """, (f"%{search}%", f"%{search}%"))
        else:
            cursor.execute("SELECT * FROM categories ORDER BY created_at ASC")
        
        categories = cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/manage_categories.html', categories=categories, search=search)


# ==================================================
# ORDERS MANAGEMENT
# ==================================================
@admin_bp.route('/orders')
@admin_required
def process_orders():
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Build query with filters
    query = """
        SELECT o.*, u.name as customer_name, u.email as customer_email
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    
    if status_filter != 'all':
        query += " AND o.status = %s"
        params.append(status_filter)
    
    if search_query:
        query += " AND (u.name LIKE %s OR u.email LIKE %s OR o.order_id LIKE %s)"
        search_param = f"%{search_query}%"
        params.extend([search_param, search_param, search_param])
    
    query += " ORDER BY o.order_date DESC"
    
    cursor.execute(query, params)
    orders = cursor.fetchall()
    
    # Fetch order items for each order
    order_details = {}
    for order in orders:
        cursor.execute("""
            SELECT oi.*, p.title, p.image 
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.product_id 
            WHERE oi.order_id = %s
        """, (order['order_id'],))
        order_details[order['order_id']] = cursor.fetchall()
    
    # Get counts for status tabs
    cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    
    cursor.close()
    conn.close()
    
    return render_template('admin/process_orders.html', 
                           orders=orders, 
                           order_details=order_details,
                           status_filter=status_filter,
                           search_query=search_query,
                           status_counts=status_counts)


@admin_bp.route('/order/<int:order_id>/approve', methods=['POST'])
@admin_required
def approve_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE orders SET status = 'Approved' WHERE order_id = %s AND status = 'Pending'", (order_id,))
        conn.commit()
        flash(f"Order #{order_id} has been approved.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error approving order: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.process_orders'))


@admin_bp.route('/order/<int:order_id>/decline', methods=['POST'])
@admin_required
def decline_order(order_id):
    decline_reason = request.form.get('decline_reason', 'No reason provided')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get order items to restore stock
        cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
        items = cursor.fetchall()
        
        # Restore stock
        for item in items:
            cursor.execute("UPDATE products SET stock = stock + %s WHERE product_id = %s", 
                          (item['quantity'], item['product_id']))
        
        # Update order status
        cursor.execute("UPDATE orders SET status = 'Declined', decline_reason = %s WHERE order_id = %s", 
                      (decline_reason, order_id))
        conn.commit()
        flash(f"Order #{order_id} has been declined.", "warning")
    except Exception as e:
        conn.rollback()
        flash(f"Error declining order: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.process_orders'))


@admin_bp.route('/order/<int:order_id>/ship', methods=['POST'])
@admin_required
def ship_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE orders SET status = 'Shipped' WHERE order_id = %s AND status = 'Approved'", (order_id,))
        conn.commit()
        flash(f"Order #{order_id} has been marked as shipped.", "info")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating order: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.process_orders'))


@admin_bp.route('/order/<int:order_id>/deliver', methods=['POST'])
@admin_required
def deliver_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE orders SET status = 'Delivered' WHERE order_id = %s AND status = 'Shipped'", (order_id,))
        conn.commit()
        flash(f"Order #{order_id} has been marked as delivered.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating order: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.process_orders'))


@admin_bp.route('/order/<int:order_id>/update_status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    """Update order status to any valid status"""
    new_status = request.form.get('status')
    valid_statuses = ['Pending', 'Approved', 'Shipped', 'Delivered', 'Declined']
    
    if new_status not in valid_statuses:
        flash("Invalid status selected.", "danger")
        return redirect(url_for('admin.process_orders'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get current order status
        cursor.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        
        if not order:
            flash(f"Order #{order_id} not found.", "danger")
            return redirect(url_for('admin.process_orders'))
        
        old_status = order['status']
        
        # If changing FROM Declined to another status, we need to deduct stock again
        if old_status == 'Declined' and new_status != 'Declined':
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
            items = cursor.fetchall()
            for item in items:
                cursor.execute("UPDATE products SET stock = stock - %s WHERE product_id = %s", 
                              (item['quantity'], item['product_id']))
        
        # If changing TO Declined from another status, restore stock
        if old_status != 'Declined' and new_status == 'Declined':
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
            items = cursor.fetchall()
            for item in items:
                cursor.execute("UPDATE products SET stock = stock + %s WHERE product_id = %s", 
                              (item['quantity'], item['product_id']))
        
        # Update the status
        cursor.execute("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))
        conn.commit()
        flash(f"Order #{order_id} status updated to {new_status}.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating order status: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin.process_orders'))


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
