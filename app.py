import sys
sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer  # ✅ Add this
import os, json
from uuid import uuid4
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.jinja_env.globals['session'] = session
app.secret_key = 'secret123'
app.config['UPLOAD_FOLDER'] = 'static/shoes'

# ✅ Add this line below secret key
serializer = URLSafeTimedSerializer(app.secret_key)

DATA_FILE = 'data.json'
RESTOCK_FILE = 'restock_requests.json'
REVIEWS_FILE = 'reviews.json'
USERS_FILE = 'users.json'
ADMIN_PASSWORD = 'Mohammed_@3'

# ------------------------------
# Email (generic SMTP) config
# ------------------------------
# Configure these environment variables in your deployment:
# MAIL_SERVER (default: smtp.gmail.com), MAIL_PORT (default: 465 for SSL),
# MAIL_USERNAME, MAIL_PASSWORD
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

def send_email(to_email, subject, body):
    """
    Generic SMTP email sender. Uses MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD.
    If MAIL_USERNAME or MAIL_PASSWORD are not set, raises an exception.
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        raise Exception("Mail credentials not configured (MAIL_USERNAME / MAIL_PASSWORD).")

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = MAIL_USERNAME
    msg['To'] = to_email

    # Use SSL if port 465, otherwise use starttls for common ports (587)
    if MAIL_PORT == 465:
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) as server:
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)

# ------------------------------
# Helper functions for data
# ------------------------------
def load_data():
    if not os.path.exists(DATA_FILE): return []
    with open(DATA_FILE, 'r') as f: return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=4)

def load_restock_requests():
    if not os.path.exists(RESTOCK_FILE): return []
    with open(RESTOCK_FILE, 'r') as f: return json.load(f)

def save_restock_requests(data):
    with open(RESTOCK_FILE, 'w') as f: json.dump(data, f, indent=4)

def load_reviews():
    if not os.path.exists(REVIEWS_FILE): return []
    with open(REVIEWS_FILE, 'r') as f: return json.load(f)

def save_reviews(data):
    with open(REVIEWS_FILE, 'w') as f: json.dump(data, f, indent=4)

def load_users():
    if not os.path.exists(USERS_FILE): return []
    with open(USERS_FILE, 'r') as f: return json.load(f)

def save_users(data):
    with open(USERS_FILE, 'w') as f: json.dump(data, f, indent=4)

# Get all products
def get_all_products():
    return load_data()  # Returns the full list of products

# Get products by category
def get_products_by_category(category):
    products = load_data()
    return [p for p in products if p.get('category', '').lower() == category.lower()]

# Get featured products (e.g., newest 4 products)
def get_featured_products():
    products = load_data()
    # Sort products by timestamp descending
    products_sorted = sorted(products, key=lambda x: x.get('timestamp', ''), reverse=True)
    return products_sorted[:4]  # Returns top 4 newest products
  
def ensure_product_ids():
    products = load_data()
    updated = False
    for p in products:
        if 'id' not in p:
            p['id'] = str(uuid4())
            updated = True
    if updated:
        save_data(products)

ensure_product_ids()  

# Routes
@app.route('/')
def index():
    products = load_data()
    current_time = datetime.now()

    # Convert string timestamps to datetime objects
    for p in products:
        if isinstance(p.get('timestamp'), str):
            p['timestamp'] = datetime.fromisoformat(p['timestamp'])

        # ✅ Ensure both "image" and "images" exist
        if 'images' not in p and 'image' in p:
            p['images'] = [p['image']]
        elif 'images' in p and 'image' not in p:
            p['image'] = p['images'][0]

    # Define featured products: added in the last 7 days
    featured_products = [
        p for p in products if (current_time - p['timestamp']).days <= 7
    ]

    return render_template(
        'index.html',
        products=products,
        featured_products=featured_products,
        current_time=current_time,
        selected_category='all'
    )

@app.route('/filtered/<category>')
def filtered(category):
    current_time = datetime.now()
    all_products = load_data()

    # Convert string timestamps to datetime objects
    for p in all_products:
        if isinstance(p.get('timestamp'), str):
            p['timestamp'] = datetime.fromisoformat(p['timestamp'])

    # Filter products by category
    if category.lower() == 'all':
        filtered_products = all_products
    else:
        filtered_products = [p for p in all_products if category.lower() in p['category'].lower()]

    # Add index to each product for links
    products = [{'index': i, **p} for i, p in enumerate(filtered_products)]

    # Define featured products: added in the last 7 days
    featured_products = [p for p in filtered_products if (current_time - p['timestamp']).days <= 7]

    return render_template(
        'index.html',
        products=products,
        featured_products=featured_products,
        current_time=current_time,
        selected_category=category
    )

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    now = datetime.now()
    attempts = session.get('admin_attempts', 0)
    locked_until = session.get('admin_locked_until')

    if locked_until:
        locked_time = datetime.fromisoformat(locked_until)
        if now < locked_time:
            minutes_left = int((locked_time - now).total_seconds() // 60 + 1)
            flash(f"⛔ Too many failed attempts. Try again in {minutes_left} minute(s).")
            return render_template('admin_login.html')
        else:
            # Lockout expired
            session.pop('admin_locked_until', None)
            session['admin_attempts'] = 0

    if request.method == 'POST':
        password = request.form.get('password')

        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_attempts'] = 0
            session.pop('admin_locked_until', None)
            return redirect(url_for('admin'))
        else:
            session['admin_attempts'] = attempts + 1
            if session['admin_attempts'] >= MAX_ATTEMPTS:
                lockout_time = now + LOCKOUT_DURATION
                session['admin_locked_until'] = lockout_time.isoformat()
                flash("🚫 Too many failed attempts. You're locked out for 5 minutes.")
            else:
                remaining = MAX_ATTEMPTS - session['admin_attempts']
                flash(f"❌ Incorrect password. {remaining} attempt(s) remaining.")

    return render_template('admin_login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    products = load_data()
    reviews = load_reviews()  # optional, if you want to display reviews in admin

    if request.method == 'POST':
        name = request.form.get('name', '').title()
        price = request.form.get('price', '')
        category = request.form.get('category', '').title()
        description = request.form.get('description', '')
        stock = int(request.form.get('stock', 0))

        # ✅ Handle multiple image uploads
        uploaded_files = request.files.getlist('images')
        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
            flash("❌ Please upload at least one image")
            return redirect(url_for('admin'))

        image_filenames = []
        for file in uploaded_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filenames.append(filename)

        # Create new product
        new_product = {
            'id': str(uuid4()),  # unique ID
            'name': name,
            'price': price,
            'category': category,
            'description': description,
            'stock': stock,
            'images': image_filenames,
            'timestamp': datetime.now().isoformat()
        }

        products.append(new_product)
        save_data(products)
        flash("✅ Product added successfully!")
        return redirect(url_for('admin'))

    return render_template(
        'admin.html',
        products=products,
        reviews=reviews,
        current_time=datetime.now()
    )

@app.template_filter('todatetime')
def todatetime_filter(s):
    if isinstance(s, datetime):
        return s
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None  # or handle error
    return None

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not name or not email or not password:
            flash("❌ All fields are required.")
            return redirect(url_for('signup'))

        users = load_users()
        if any(u['email'] == email for u in users):
            flash("❌ Email already registered.")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        users.append({'name': name, 'email': email, 'password': hashed_password})
        save_users(users)

        # Send welcome email via generic SMTP
        body = f"""Hello {name},

Thanks for signing up with ShopLuxe!

You can now log in and start exploring amazing products.

Best regards,
ShopLuxe Team
"""
        try:
            send_email(email, "🎉 Welcome to ShopLuxe!", body)
        except Exception as e:
            flash("⚠️ Email not sent. Please check your email configuration.")
            # Don't redirect to any auth route — keep user signup flow intact

        flash("✅ Account created. Please log in.")
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        users = load_users()
        user = next((u for u in users if u['email'] == email), None)

        if user and check_password_hash(user['password'], password):
            session['user'] = {'name': user['name'], 'email': user['email']}
            flash("✅ Logged in successfully.")
            return redirect(url_for('profile'))
        else:
            flash("❌ Invalid credentials.")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        users = load_users()
        user = next((u for u in users if u['email'] == email), None)

        if not user:
            flash("❌ Email not found.")
            return redirect(url_for('forgot_password'))

        # Generate password reset token
        token = serializer.dumps(email, salt='reset-password')
        reset_link = url_for('reset_with_token', token=token, _external=True)

        try:
            body = f"""Hello,

Click the link below to reset your password:

{reset_link}

This link expires in 30 minutes.
"""
            send_email(email, "🔐 Password Reset Request", body)

        except Exception as e:
            print("Failed to send email:", e)
            flash("❌ Email send failed.")
            return redirect(url_for('forgot_password'))

        flash("📧 Check your email for the reset link.")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/reset_with_token/<token>', methods=['GET', 'POST'])
def reset_with_token(token):
    try:
        email = serializer.loads(token, salt='reset-password', max_age=1800)  # 30 min
    except:
        flash("❌ Reset link expired or invalid.")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        if not new_password:
            flash("❌ Please enter a new password.")
            return redirect(url_for('reset_with_token', token=token))

        users = load_users()
        user = next((u for u in users if u['email'] == email), None)
        if user:
            user['password'] = generate_password_hash(new_password)
            save_users(users)
            flash("✅ Password reset successful. Please log in.")
            return redirect(url_for('login'))

        flash("❌ User not found.")
        return redirect(url_for('login'))

    return render_template('reset_with_token.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        flash("⚠️ Please log in first.")
        return redirect(url_for('login'))

    users = load_users()
    user = next((u for u in users if u['email'] == session['user']['email']), None)

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_name = request.form.get('name')
        new_password = request.form.get('password')

        if not check_password_hash(user['password'], current_password):
           flash("❌ Incorrect current password.")
           return redirect(url_for('profile'))


        if user['password'] != current_password:
            flash("❌ Incorrect current password.")
            return redirect(url_for('profile'))

        # If password is correct, update profile
        user['name'] = new_name or user['name']
        if new_password:
            user['password'] = generate_password_hash(new_password)
        save_users(users)

        flash("✅ Profile updated successfully.")
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("👋 Logged out.")
    return redirect(url_for('index'))

@app.route('/delete/<int:index>', methods=['POST'])
def delete(index):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    products = load_data()
    if 0 <= index < len(products):
        # Only try to delete image if it exists
        if 'image' in products[index] and products[index]['image']:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], products[index]['image'])
            if os.path.exists(image_path):
                os.remove(image_path)

        # Remove product from the list
        del products[index]
        save_data(products)
        flash("🗑️ Product deleted.")
    else:
        flash("❌ Invalid product index.")

    return redirect(url_for('admin'))

@app.route('/product/<product_id>')
def product_detail(product_id):
    products = load_data()
    reviews = load_reviews()

    # Find product by ID safely
    product = next((p for p in products if p.get('id') == product_id), None)
    if not product:
        flash("⚠️ Product not found.")
        return redirect(url_for('index'))

    # Optional: add 'index' for templates needing it
    product['index'] = products.index(product)

    # Related products (max 4)
    product_category = product.get('category', '').strip().lower()
    related = []
    for p in products:
        if p.get('category', '').strip().lower() == product_category and p.get('id') != product_id:
            # Ensure each related product has an 'id'
            if 'id' not in p:
                continue
            related.append(p)
        if len(related) >= 4:
            break

    # Images for product_detail page
    product_images = product.get('images') or ([product.get('image')] if product.get('image') else [])

    # Product reviews
    product_reviews = [r for r in reviews if r.get('product_index') == product['index']]

    return render_template(
        'product_detail.html',
        product=product,
        related=related,
        reviews=product_reviews,
        product_images=product_images
    )

@app.route('/submit_review/<int:index>', methods=['POST'])
def submit_review(index):
    name = request.form.get('name')
    comment = request.form.get('comment')
    rating = int(request.form.get('rating'))
    timestamp = datetime.now().isoformat()

    if not name or not comment or rating not in range(1, 6):
        flash("❌ Please provide a name, comment, and rating (1-5).")
        return redirect(url_for('product_detail', index=index))

    reviews = load_reviews()
    reviews.append({
        'product_index': index,
        'name': name,
        'comment': comment,
        'rating': rating,
        'timestamp': timestamp
    })
    save_reviews(reviews)

    flash("✅ Review submitted!")
    return redirect(url_for('product_detail', index=index))

@app.route('/restock_notify/<int:index>', methods=['POST'])
def restock_notify(index):
    email = request.form.get('email')
    products = load_data()
    if not email or index < 0 or index >= len(products):
        flash("❌ Invalid request")
        return redirect(url_for('product_detail', index=index))
    requests = load_restock_requests()
    product = products[index]
    requests.append({
        'email': email,
        'product_name': product['name'],
        'product_index': index,
        'timestamp': datetime.now().isoformat()
    })
    save_restock_requests(requests)
    flash("✅ You’ll be notified when it's back in stock!")
    return redirect(url_for('product_detail', index=index))

@app.route('/edit/<int:index>', methods=['GET', 'POST'])
def edit_product(index):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    products = load_data()
    if index < 0 or index >= len(products):
        flash("❌ Invalid product")
        return redirect(url_for('admin'))
    product = products[index]
    if request.method == 'POST':
        product['name'] = request.form.get('name').title()
        product['price'] = request.form.get('price')
        product['category'] = request.form.get('category').title()
        product['description'] = request.form.get('description')
        product['stock'] = int(request.form.get('stock'))
        image = request.files.get('image')
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product['image'] = filename
        products[index] = product
        save_data(products)
        flash("✅ Product updated successfully")
        return redirect(url_for('admin'))
    return render_template('edit_product.html', product=product, index=index, reviews=load_reviews())

@app.route('/test_email')
def test_email():
    try:
        target = os.environ.get('MAIL_USERNAME') or 'test@example.com'
        send_email(target, "✅ Test Email from Flask App", "This is a test email to verify email sending from your Flask app.")
        return "✅ Test email sent successfully!"
    except Exception as e:
        return f"❌ Email failed: {str(e)}"
    
@app.route('/test-logo')
def test_logo():
    return '''
    <img src="/static/logo/shopluxe.png" alt="Test Logo" style="height:100px;">
    '''
    
@app.route('/shop')
def shop():
    category = request.args.get('category', 'all')
    
    if category.lower() == 'all':
        products = get_all_products()
    else:
        products = get_products_by_category(category)

    featured_products = get_featured_products()
    current_time = datetime.now()

    return render_template(
        'shop.html',
        products=products,
        featured_products=featured_products,
        selected_category=category,
        current_time=current_time
    )

# ------------------ CART ROUTES ------------------

# Initialize cart in session if not present
def get_cart():
    if 'cart' not in session:
        session['cart'] = []
    return session['cart']

@app.route('/add_to_cart/<int:index>', methods=['POST'])
def add_to_cart(index):
    quantity = int(request.form.get("quantity", 1))
    cart = get_cart()

    for item in cart:
        if item['index'] == index:
            item['quantity'] += quantity
            break
    else:
        cart.append({'index': index, 'quantity': quantity})

    session['cart'] = cart
    flash("🛒 Product added to cart!")
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def cart():
    cart = get_cart()
    products = load_data()
    cart_items = []

    for item in cart:
        index = item.get("index")
        quantity = item.get("quantity", 1)
        if 0 <= index < len(products):
            product = products[index].copy()
            product['quantity'] = quantity
            # Convert price to float
            product['price'] = float(product.get('price', 0))
            cart_items.append(product)

    total = sum(p['price'] * p['quantity'] for p in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_cart()
    products = load_data()
    cart_items = []

    for item in cart:
        index = item.get("index")
        quantity = item.get("quantity", 1)
        if 0 <= index < len(products):
            product = products[index].copy()
            product['quantity'] = quantity
            cart_items.append(product)

    total = sum(float(p['price']) * p['quantity'] for p in cart_items)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')

        if not name or not email or not phone:
            flash("❌ All fields are required.")
            return redirect(url_for('checkout'))

        order = {
            'name': name,
            'email': email,
            'phone': phone,
            'items': cart_items,
            'total': total
        }

        # Compose email content
        item_lines = '\n'.join([f"{item['name']} x{item['quantity']} - GH₵ {item['price']}" for item in cart_items])
        customer_body = f"""
Hello {name},

Thank you for your order on ShopLuxe! 🎉

Order Summary:
--------------
{item_lines}
--------------
Total: GH₵ {total}

We’ll contact you if needed. Thanks again!

Best regards,
ShopLuxe Team
"""
        admin_body = f"""
Hello Admin,

A new order has been placed on ShopLuxe.

Customer Info:
Name: {name}
Email: {email}
Phone: {phone}

Order Summary:
--------------
{item_lines}
--------------
Total: GH₵ {total}

Check your dashboard for more details.
"""

        # Send emails safely using generic SMTP
        try:
            send_email(email, "🧾 Order Confirmation - ShopLuxe", customer_body)
            # Replace the admin email below with your admin address or keep as-is
            send_email(os.environ.get('ADMIN_EMAIL', 'vybezkhid7@gmail.com'), "📦 New Order Received - ShopLuxe", admin_body)
        except Exception as e:
            flash("⚠️ Emails could not be sent. Please check email configuration.")
            # keep flow moving; do not redirect to any removed auth routes

        # Clear cart and save order in session for confirmation page
        session.pop('cart', None)
        session['order_info'] = order

        return redirect(url_for('order_confirmation'))

    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/confirm_order', methods=['POST'])
def confirm_order():
    cart = get_cart()
    products = load_data()

    # Build cart_items with full product info
    cart_items = []
    for item in cart:
        index = item.get('index')
        quantity = item.get('quantity', 1)
        if 0 <= index < len(products):
            product = products[index].copy()
            product['quantity'] = quantity
            # Ensure price is float
            product['price'] = float(product.get('price', 0))
            cart_items.append(product)

    total = sum(item['price'] * item['quantity'] for item in cart_items)

    order_info = {
        'name': request.form['name'],
        'email': request.form['email'],
        'phone': request.form['phone'],
        'items': cart_items,
        'total': total
    }

    session['order_info'] = order_info

    # ----------------------------
    # Send confirmation email
    # ----------------------------
    email_body = f"Hi {order_info['name']},\n\nThank you for your order! Here are your order details:\n\n"
    for item in cart_items:
        email_body += f"- {item['name']} x{item['quantity']} : GH₵ {item['price']}\n"
    email_body += f"\nTotal: GH₵ {total}\n\nShopluxe Team"

    try:
        send_email(order_info['email'], "Shopluxe Order Confirmation", email_body)
        flash("✅ Order confirmed! A confirmation email has been sent.")
    except Exception as e:
        print("❌ Failed to send email:", e)
        flash("⚠️ Order confirmed, but failed to send email. Please check email configuration.")

    return redirect(url_for('order_confirmation'))

@app.route('/order_confirmation')
def order_confirmation():
    order_info = session.get('order_info')
    if not order_info:
        flash("⚠️ No order found.")
        return redirect(url_for('cart'))
    return render_template('order_confirmation.html', order=order_info)

@app.route("/healthz")
def health_check():
    return "OK", 200

if __name__ == "__main__":
    app.run()
