from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import re
from database.connection import get_db_connection

auth_bp = Blueprint('auth', __name__, template_folder='../templates')


def is_valid_email(email):
    """Validate email format."""
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(regex, email)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        address = request.form['address'].strip()
        password = request.form['password']
        confirm = request.form['confirm_password']

        errors = {}

        # --- Validation ---
        if not name or len(name) < 2:
            errors['name'] = "Name must be at least 2 characters."

        if not email:
            errors['email'] = "Email is required."
        elif not is_valid_email(email):
            errors['email'] = "Invalid email format."
        else:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                errors['email'] = "Email already exists."
            cursor.close()
            conn.close()

        if not phone:
            errors['phone'] = "Phone number is required."
        elif not re.match(r'^[0-9+\- ]+$', phone):
            errors['phone'] = "Invalid phone number."

        if not address:
            errors['address'] = "Address is required."

        if not password or len(password) < 6:
            errors['password'] = "Password must be at least 6 characters."
        if password != confirm:
            errors['confirm_password'] = "Passwords do not match."

        if errors:
            return render_template(
                'auth/register.html',
                errors=errors,
                name=name,
                email=email,
                phone=phone,
                address=address
            )

        # --- Insert user ---
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (name, email, password, phone, address, role, status)
            VALUES (%s, %s, %s, %s, %s, 'customer', 'active')
        """, (name, email, hashed_password, phone, address))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful. You can now login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', errors={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            flash("Email not registered.", "danger")
            return redirect(url_for('auth.login'))

        if user['status'] in ('inactive', 'deactivated'):
            flash("Your account has been deactivated. Please contact admin.", "danger")
            return redirect(url_for('auth.login'))

        if check_password_hash(user['password'], password):
            #  Save session
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            session['name'] = user['name']

            #  Redirect based on role
            if user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                print('as: ' + generate_password_hash("admin123"))
                return redirect(url_for('customer.home'))
        else:
            flash("Incorrect password.", "danger")

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('auth.login'))
