from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify, flash
from database.connection import get_db_connection
import os
from werkzeug.utils import secure_filename
from datetime import datetime

from flask import session, request, redirect, url_for, render_template, flash
customer_bp = Blueprint('customer', __name__, template_folder='../templates')

def is_customer():
    return 'user_id' in session and session.get('role') == 'customer'

@customer_bp.route('/home')
def home():
    if not is_customer():
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch books (Added 'stock' explicitly to ensure it's selected)
    cursor.execute("SELECT * FROM products ORDER BY product_id DESC")
    books = cursor.fetchall()

    # 2. Fetch unique authors for the filter chips
    cursor.execute("SELECT DISTINCT author FROM products WHERE author IS NOT NULL LIMIT 8")
    authors = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Ensure stock is treated as an int in Python before rendering
    for book in books:
        book['stock'] = int(book['stock']) if book['stock'] is not None else 0
    
    return render_template('customer/home.html', books=books, authors=authors)

# --- SHOP & SEARCH ---
@customer_bp.route('/shop')
def shop():
    if not is_customer():
        return redirect(url_for('auth.login'))
    
    search_query = request.args.get('search', '').strip()
    category_id = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT p.*, c.category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.category_id 
        WHERE p.stock > 0
    """
    params = []

    if search_query:
        query += " AND (p.title LIKE %s OR p.author LIKE %s)"
        search_param = f"%{search_query}%"
        params.extend([search_param, search_param])

    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)

    query += " ORDER BY p.product_id DESC"
    
    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.execute("SELECT category_id, category_name FROM categories")
    categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('customer/shop.html', products=products, categories=categories)

# --- PRODUCT DETAILS ---
@customer_bp.route('/shop/<int:product_id>')
def product_details(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, c.category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.category_id 
        WHERE p.product_id = %s
    """, (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('customer/product_view.html', product=product)

# --- ADD TO CART (AJAX) ---
@customer_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if not is_customer():
        return jsonify({'success': False, 'message': 'Please log in to add items to your cart.'}), 401

    product_id = request.form.get('product_id')
    user_id = session.get('user_id') # Changed variable name for clarity
    
    try:
        quantity = int(request.form.get('quantity', 1))
        if quantity <= 0:
            return jsonify({'success': False, 'message': 'Quantity must be at least 1.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid quantity format.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. VALIDATE STOCK
        cursor.execute("SELECT title, stock FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            return jsonify({'success': False, 'message': 'Product not found.'}), 404
        
        if product['stock'] <= 0:
            return jsonify({'success': False, 'message': 'This item is currently out of stock.'}), 400

        # 2. CHECK EXISTING CART (Fixed column name to user_id)
        cursor.execute("SELECT cart_id, quantity FROM cart WHERE user_id = %s AND product_id = %s", 
                       (user_id, product_id))
        existing_item = cursor.fetchone()

        requested_total = quantity
        if existing_item:
            requested_total += existing_item['quantity']

        # 3. STOCK OVERFLOW CHECK
        if requested_total > product['stock']:
            return jsonify({
                'success': False, 
                'message': f"Cannot add more. You already have {existing_item['quantity'] if existing_item else 0} in cart, and only {product['stock']} are available."
            }), 400

        # 4. PERFORM DATABASE ACTION (Fixed column name to user_id)
        if existing_item:
            cursor.execute("UPDATE cart SET quantity = %s WHERE cart_id = %s", 
                           (requested_total, existing_item['cart_id']))
        else:
            # Matches your DB: user_id, product_id, quantity
            cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s)", 
                           (user_id, product_id, quantity))

        conn.commit()

        # 5. GET UPDATED CART COUNT (Fixed column name to user_id)
        cursor.execute("SELECT SUM(quantity) as total_items FROM cart WHERE user_id = %s", (user_id,))
        cart_stats = cursor.fetchone()
        
        new_count = int(cart_stats['total_items']) if cart_stats['total_items'] else 0

        return jsonify({
            'success': True, 
            'message': f"Added {product['title']} to cart!",
            'cart_count': new_count
        })

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}") # This will now show the actual error in your terminal
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()
        
        
@customer_bp.route('/cart')
def view_cart():
    if not is_customer():
        return redirect(url_for('auth.login'))
    
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Query using 'user_id' to match your DB schema
    query = """
        SELECT c.cart_id, c.quantity, p.product_id, p.title, p.price, p.image, p.stock
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = %s
    """
    cursor.execute(query, (user_id,))
    cart_items = cursor.fetchall()
    
    # FIX: Convert price to float during calculation to avoid TypeError
    subtotal = sum(float(item['price']) * item['quantity'] for item in cart_items)
    
    # Now subtotal (float) can be added to shipping (float)
    shipping = 50.00 if subtotal > 0 else 0.00
    total = subtotal + shipping
    
    cursor.close()
    conn.close()
    
    return render_template('customer/cart.html', 
                           cart_items=cart_items, 
                           subtotal=subtotal, 
                           shipping=shipping, 
                           total=total)
# Ensure the route matches the fetch URL exactly
# In your customer_bp file
@customer_bp.route('/update_cart/<int:cart_id>', methods=['POST'])
def update_cart(cart_id):
    if not session.get('user_id'):
        return jsonify(success=False, message="Unauthorized"), 401
    
    user_id = session.get('user_id')
    new_qty = request.form.get('quantity', type=int)

    if new_qty is None or new_qty < 1:
        return jsonify(success=False, message="Invalid quantity"), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Check stock availability and verify ownership
        cursor.execute("""
            SELECT p.stock, p.title FROM products p 
            JOIN cart c ON p.product_id = c.product_id 
            WHERE c.cart_id = %s AND c.user_id = %s
        """, (cart_id, user_id))
        item = cursor.fetchone()
        
        if not item:
            return jsonify(success=False, message="Item not found in cart"), 404

        if new_qty > item['stock']:
            return jsonify(success=False, message=f"Only {item['stock']} units of '{item['title']}' available"), 400

        # 2. Update the database
        cursor.execute("UPDATE cart SET quantity = %s WHERE cart_id = %s AND user_id = %s", 
                       (new_qty, cart_id, user_id))
        conn.commit()
        
        return jsonify(success=True)

    except Exception as e:
        print(f"Database Error: {e}")
        return jsonify(success=False, message="Server error occurred"), 500
    finally:
        cursor.close()
        conn.close()

# --- REMOVE SINGLE ITEM FROM CART ---
@customer_bp.route('/cart/remove/<int:cart_id>')
def remove_from_cart(cart_id):
    if not is_customer():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Ensure user_id check is present so users can't delete other people's cart items
        cursor.execute("DELETE FROM cart WHERE cart_id = %s AND user_id = %s", (cart_id, user_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Remove Error: {e}")
        return jsonify({'success': False}), 500
    finally:
        cursor.close()
        conn.close()


@customer_bp.route('/bulk_remove_cart', methods=['POST'])
def bulk_remove_cart():
    if not is_customer():
        return jsonify({'success': False}), 401
    
    data = request.get_json()
    cart_ids = data.get('cart_ids', [])
    user_id = session.get('user_id')

    if not cart_ids:
        return jsonify({'success': False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Securely delete only items belonging to the current user
    format_strings = ','.join(['%s'] * len(cart_ids))
    query = f"DELETE FROM cart WHERE user_id = %s AND cart_id IN ({format_strings})"
    
    try:
        cursor.execute(query, [user_id] + cart_ids)
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False}), 500
    finally:
        cursor.close()
        conn.close()

# --- CHECKOUT ---




@customer_bp.route('/checkout')
def checkout():
    if not is_customer():
        return redirect(url_for('auth.login'))
    
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch User details (for the "Cardholder Name" or "Billing Name")
    cursor.execute("SELECT name, address FROM users WHERE user_id = %s", (user_id,))
    user_info = cursor.fetchone()
    
    # 2. Fetch cart items with product titles (the product "Name")
    query = """
        SELECT c.quantity, p.title, p.price 
        FROM cart c 
        JOIN products p ON c.product_id = p.product_id 
        WHERE c.user_id = %s
    """
    cursor.execute(query, (user_id,))
    cart_items = cursor.fetchall()
    
    if not cart_items:
        cursor.close()
        conn.close()
        return redirect(url_for('customer.view_cart'))

    # Calculations
    subtotal = sum(float(item['price']) * item['quantity'] for item in cart_items)
    shipping = 50.00
    total = subtotal + shipping
    
    cursor.close()
    conn.close()
    
    return render_template('customer/checkout.html', 
                           items=cart_items, 
                           user=user_info, # Passing the customer name/info here
                           total=total, 
                           subtotal=subtotal, 
                           shipping=shipping)




@customer_bp.route('/place_order', methods=['POST'])
def place_order():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    customer_name = request.form.get('customer_name')
    address = request.form.get('address')
    payment_method = request.form.get('payment_method')

    proof_filename = None

    # Ensure upload folder exists
    payment_dir = os.path.join('static', 'img', 'payments')
    os.makedirs(payment_dir, exist_ok=True)

    if payment_method == 'Online' and 'payment_proof' in request.files:
        file = request.files['payment_proof']
        if file.filename:
            proof_filename = secure_filename(
                f"pay_{user_id}_{int(datetime.now().timestamp())}_{file.filename}"
            )
            file.save(os.path.join(payment_dir, proof_filename))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get cart items
        cursor.execute("""
            SELECT c.quantity, p.product_id, p.price
            FROM cart c
            JOIN products p ON c.product_id = p.product_id
            WHERE c.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()

        if not cart_items:
            return redirect(url_for('customer.view_cart'))

        subtotal = sum(float(i['price']) * i['quantity'] for i in cart_items)
        total = subtotal + 50.00

        # Create order
        cursor.execute("""
            INSERT INTO orders (user_id, name, address, total_amount, payment_method, status, order_date)
            VALUES (%s, %s, %s, %s, %s, 'Pending', NOW())
        """, (user_id, customer_name, address, total, payment_method))

        order_id = cursor.lastrowid

        # Payment record
        cursor.execute("""
            INSERT INTO payments (order_id, amount, method, proof, status, payment_date)
            VALUES (%s, %s, %s, %s, 'Completed', NOW())
        """, (order_id, total, payment_method, proof_filename or 'COD'))

        # Order items + stock update
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['product_id'], item['quantity'], item['price']))

            cursor.execute("""
                UPDATE products
                SET stock = stock - %s
                WHERE product_id = %s
            """, (item['quantity'], item['product_id']))

        # Clear cart
        cursor.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))

        conn.commit()

        return redirect(url_for('customer.order_complete'))

    except Exception as e:
        conn.rollback()
        print("ORDER ERROR:", e)
        flash("Order failed. Please try again.", "danger")
        return redirect(url_for('customer.checkout'))

    finally:
        cursor.close()
        conn.close()
        

@customer_bp.route('/order-complete')
def order_complete():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    return render_template('customer/order_success.html')

 
        
@customer_bp.route('/my_orders')
def my_orders():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all orders for this user to categorize them in the template
    cursor.execute("""
        SELECT * FROM orders 
        WHERE user_id = %s 
        ORDER BY order_date DESC
    """, (user_id,))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()        
    return render_template('customer/myorder.html', orders=orders)

@customer_bp.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session.get('user_id')
    reason = request.form.get('cancel_reason') 
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Verify ownership and status
        cursor.execute("""
            SELECT order_id FROM orders 
            WHERE order_id = %s AND user_id = %s AND status = 'Pending'
        """, (order_id, user_id))
        order = cursor.fetchone()

        if not order:
            flash("Action denied. This order cannot be cancelled.", "danger")
            return redirect(url_for('customer.my_orders'))

        # 2. Restore Product Stock using order_items
        cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
        items_to_return = cursor.fetchall()

        for item in items_to_return:
            cursor.execute("""
                UPDATE products 
                SET stock = stock + %s 
                WHERE product_id = %s
            """, (item['quantity'], item['product_id']))

        # 3. Update Order Status and use the NEW cancel_reason column
        cursor.execute("""
            UPDATE orders 
            SET status = 'Cancelled', cancel_reason = %s 
            WHERE order_id = %s
        """, (reason, order_id))
        
        conn.commit()
        flash("Order #ORD-{} has been removed from your active list.".format(order_id), "success")
            
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        flash("An error occurred during cancellation.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('customer.my_orders'))

