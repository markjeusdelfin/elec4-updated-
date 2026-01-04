from flask import session, redirect, url_for, flash


def admin_required(func):
    """Decorator to restrict routes to admin users only."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)

    return wrapper
