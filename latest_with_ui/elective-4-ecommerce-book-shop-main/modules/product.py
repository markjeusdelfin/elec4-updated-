from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from database.connection import get_db_connection
from modules.utils import admin_required
import os

product_bp = Blueprint('product', __name__, template_folder='../templates')

# =====================================
# HELPER FUNCTION
# =====================================


def allowed_file(filename):
    """Check if the uploaded file has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


# =====================================
# MANAGE PRODUCTS
# =====================================


@product_bp.route('/admin/products')
@admin_required
def manage_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Get search and category from URL parameters
        search = request.args.get('search', '').strip()
        
        # We set default to 'all' to ensure 'category_id' is never None
        category_id = request.args.get('category_id', 'all')

        # 2. Fetch categories for the filter dropdown
        cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
        categories = cursor.fetchall()

        # 3. Build the Dynamic Query
        query = """
            SELECT p.*, c.category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.category_id 
            WHERE 1=1
        """
        params = []

        # Filter by Title/Author
        if search:
            query += " AND (p.title LIKE %s OR p.author LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        # Filter by Category (only if it's not "all")
        if category_id and category_id != "all":
            query += " AND p.category_id = %s"
            params.append(category_id)

        # 4. Final Sorting and Execution
        query += " ORDER BY p.product_id ASC"
        cursor.execute(query, tuple(params))
        products = cursor.fetchall()

    finally:
        # 5. Always close connection even if query fails
        cursor.close()
        conn.close()

    return render_template(
        'admin/manage_products.html',
        products=products,
        categories=categories,
        selected_category=category_id, # Keeps the dropdown selected
        search=search                  # Keeps the search text in the box
    )


# =====================================
# ADD PRODUCT
# =====================================
@product_bp.route('/admin/add_product', methods=['GET', 'POST'])
@admin_required
def add_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', 0)
        stock = request.form.get('stock', 0)
        category_id = request.form.get('category_id') or None

        # Handle image upload
        image_file = request.files.get('image')
        image_filename = None
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            image_filename = f"/{image_path}"

        # Validation
        if not title or not price:
            flash('Title and price are required.', 'danger')
            return render_template('admin/product/add_product.html', categories=categories)

        cursor.execute("SELECT * FROM products WHERE title = %s", (title,))
        if cursor.fetchone():
            flash('Product title already exists.', 'danger')
            return render_template('admin/product/add_product.html', categories=categories)

        cursor.execute("""
            INSERT INTO products (title, author, description, price, stock, category_id, image)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (title, author, description, price, stock, category_id, image_filename))
        conn.commit()

        flash('Product added successfully!', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('product.manage_products'))

    cursor.close()
    conn.close()
    return render_template('admin/product/add_product.html', categories=categories)


# =====================================
# EDIT PRODUCT
# =====================================
@product_bp.route('/admin/edit_product/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = %s", (id,))
    product = cursor.fetchone()

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()

    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('product.manage_products'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', 0)
        stock = request.form.get('stock', 0)
        category_id = request.form.get('category_id') or None

        # Handle new image
        image_file = request.files.get('image')
        image_filename = product['image']  # keep old one by default
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            image_filename = f"/{image_path}"

        cursor.execute("""
            UPDATE products 
            SET title=%s, author=%s, description=%s, price=%s, stock=%s, category_id=%s, image=%s
            WHERE product_id=%s
        """, (title, author, description, price, stock, category_id, image_filename, id))
        conn.commit()

        flash('Product updated successfully!', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('product.manage_products'))

    cursor.close()
    conn.close()
    return render_template('admin/product/edit_product.html', product=product, categories=categories)


# =====================================
# DELETE PRODUCT
# =====================================
@product_bp.route('/admin/delete_product/<int:id>', methods=['POST'])
@admin_required
def delete_product(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE product_id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Product deleted successfully!', 'success')
    return redirect(url_for('product.manage_products'))
