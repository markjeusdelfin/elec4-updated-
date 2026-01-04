from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from database.connection import get_db_connection

admin_orders_bp = Blueprint(
    'admin_orders',
    __name__,
    template_folder='../templates/admin'
)

def is_admin():
    return 'user_id' in session and session.get('role') == 'admin'


@admin_orders_bp.route('/orders')
def orders():
    if not is_admin():
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.*, u.name AS customer_name
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        ORDER BY o.order_date DESC
    """)
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('orders.html', orders=orders)


@admin_orders_bp.route('/orders/update/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not is_admin():
        return redirect(url_for('auth.login'))

    status = request.form.get('status')
    reason = request.form.get('reason')

    conn = get_db_connection()
    cursor = conn.cursor()

    if status == 'Declined':
        cursor.execute("""
            UPDATE orders
            SET status = %s, cancel_reason = %s
            WHERE order_id = %s
        """, (status, reason, order_id))
    else:
        cursor.execute("""
            UPDATE orders
            SET status = %s
            WHERE order_id = %s
        """, (status, order_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Order updated successfully", "success")
    return redirect(url_for('admin_orders.orders'))
