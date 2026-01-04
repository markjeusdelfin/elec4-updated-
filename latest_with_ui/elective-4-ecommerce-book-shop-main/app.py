from flask import Flask, redirect, url_for, render_template
from modules.auth import auth_bp
from modules.admin import admin_bp
from modules.customer import customer_bp
from modules.product import product_bp
from modules.category import category_bp
from modules.admin_orders import admin_orders_bp
import os


app = Flask(__name__)
app.secret_key = "secret123"  # Change this in production!

@app.route('/')
def landing():
    return render_template('index.html')

# File Upload Config
app.config['UPLOAD_FOLDER'] = 'static/img'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(customer_bp, url_prefix="/customer")
app.register_blueprint(product_bp, url_prefix="/product")
app.register_blueprint(category_bp, url_prefix="/category")
app.register_blueprint(admin_orders_bp, url_prefix="/admin")


# Prevent cached pages after logout


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    print("\n=== Available Routes ===")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint:30} {rule.rule}")
    print("========================\n")
    app.run(debug=True)
