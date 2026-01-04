# ===========================================
# modules/category.py (WITH DEBUGGING)
# ===========================================
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.connection import get_db_connection
from modules.utils import admin_required
category_bp = Blueprint('category', __name__, template_folder='../templates')


def is_admin():
    """Check if user is admin"""
    return 'user_id' in session and session.get('role') == 'admin'


# ===========================================
# CATEGORY MANAGEMENT
# ===========================================

@category_bp.route('/categories')
@admin_required
def manage_categories():
    """Display all categories"""
    if not is_admin():
        flash('⚠️ Access denied. Admin only.', 'danger')
        return redirect(url_for('auth.login'))

    search = request.args.get('search', '').strip()

    conn = None
    cursor = None
    categories = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        print("Fetching categories from database...")

        # Add search condition
        if search:
            cursor.execute("""
                SELECT * FROM categories
                WHERE category_name LIKE %s OR description LIKE %s
                ORDER BY created_at ASC
            """, (f"%{search}%", f"%{search}%"))
        else:
            cursor.execute("SELECT * FROM categories ORDER BY created_at ASC")

        categories = cursor.fetchall()
        conn.commit()

        print(f"Found {len(categories)} categories")

    except Exception as e:
        print(f"ERROR fetching categories: {str(e)}")
        flash(f' Error loading categories: {str(e)}', 'danger')

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Pass search query to template
    return render_template('admin/manage_categories.html', categories=categories, search=search)


@category_bp.route('/categories/add', methods=['GET', 'POST'])
@admin_required
def add_category():
    """Add a new category"""
    if not is_admin():
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        category_name = request.form.get('category_name', '').strip()
        description = request.form.get('description', '').strip()

        print(f"Attempting to add category: {category_name}")

        if not category_name:
            flash('Category name is required!', 'danger')
            return render_template('admin/category/add_category.html')

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Check if category already exists
            cursor.execute(
                "SELECT * FROM categories WHERE category_name = %s",
                (category_name,)
            )
            existing = cursor.fetchone()

            if existing:
                flash(
                    f'Category "{category_name}" already exists!', 'warning')
                return render_template('admin/category/add_category.html')

            # Insert new category
            cursor.execute(
                "INSERT INTO categories (category_name, description) VALUES (%s, %s)",
                (category_name, description)
            )
            conn.commit()

            print(f"✓ Category '{category_name}' added successfully!")
            flash(
                f'Category "{category_name}" added successfully!', 'success')

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"ERROR adding category: {str(e)}")
            flash(f'Error adding category: {str(e)}', 'danger')

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        return redirect(url_for('category.manage_categories'))

    return render_template('admin/category/add_category.html')


@category_bp.route('/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def edit_category(category_id):
    """Edit an existing category"""
    if not is_admin():
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('auth.login'))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            category_name = request.form.get('category_name', '').strip()
            description = request.form.get('description', '').strip()

            if not category_name:
                flash('Category name is required!', 'danger')
                cursor.execute(
                    "SELECT * FROM categories WHERE category_id=%s", (category_id,))
                category = cursor.fetchone()
                return render_template('admin/category/edit_category.html', category=category)

            cursor.execute(
                "UPDATE categories SET category_name=%s, description=%s WHERE category_id=%s",
                (category_name, description, category_id)
            )
            conn.commit()

            print(f"✓ Category '{category_name}' updated successfully!")
            flash(
                f'Category "{category_name}" updated successfully!', 'success')

            return redirect(url_for('category.manage_categories'))

        # GET request - show edit form
        cursor.execute(
            "SELECT * FROM categories WHERE category_id=%s", (category_id,))
        category = cursor.fetchone()

        if not category:
            flash('Category not found!', 'danger')
            return redirect(url_for('category.manage_categories'))

        return render_template('admin/category/edit_category.html', category=category)

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"ERROR editing category: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('category.manage_categories'))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@category_bp.route('/categories/delete/<int:category_id>')
@admin_required
def delete_category(category_id):
    """Delete a category"""
    if not is_admin():
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('auth.login'))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if category exists
        cursor.execute(
            "SELECT category_name FROM categories WHERE category_id=%s", (category_id,))
        category = cursor.fetchone()

        if not category:
            flash('Category not found!', 'danger')
            return redirect(url_for('category.manage_categories'))

        # Delete category
        cursor.execute(
            "DELETE FROM categories WHERE category_id=%s", (category_id,))
        conn.commit()

        print(f"✓ Category '{category['category_name']}' deleted!")
        flash(
            f'Category "{category["category_name"]}" deleted successfully!', 'success')

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"ERROR deleting category: {str(e)}")
        flash(f'Error deleting category: {str(e)}', 'danger')

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('category.manage_categories'))
