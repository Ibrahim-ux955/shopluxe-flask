import sys
sys.stdout.reconfigure(encoding='utf-8')
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer  # ✅ Add this
import os, json
from datetime import datetime, timedelta

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

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'vybezkhid7@gmail.com'
app.config['MAIL_PASSWORD'] = 'dpbx ahjn cinw qxxj'
app.config['MAIL_DEFAULT_SENDER'] = 'vybezkhid7@gmail.com'
mail = Mail(app)

# Helper functions
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

# Routes
from datetime import datetime

@app.route('/')
def index():
    products = load_data()
    current_time = datetime.now()

    # Convert string timestamps to datetime objects
    for p in products:
        if isinstance(p.get('timestamp'), str):
            p['timestamp'] = datetime.fromisoformat(p['timestamp'])

    # Define featured products: added in the last 7 days
    featured_products = [p for p in products if (current_time - p['timestamp']).days <= 7]

    return render_template(
        'index.html',
        products=products,
        featured_products=featured_products,
        current_time=current_time,
        selected_category='all'
    )


@app.route('/filtered/<category>')
def filtered(category):
    all_products = load_data()
    filtered_products = [p for p in all_products if category.lower() in p['category'].lower()]
    products = [{'index': i, **p} for i, p in enumerate(filtered_products)]
    return render_template('index.html', products=products, query='')

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
    if request.method == 'POST':
        name = request.form.get('name').title()
        price = request.form.get('price')
        category = request.form.get('category').title()
        description = request.form.get('description')
        stock = int(request.form.get('stock'))
        image = request.files.get('image')
        if not image or image.filename == '':
            flash("❌ Please upload an image")
            return redirect(url_for('admin'))
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_product = {
            'name': name,
            'price': price,
            'category': category,
            'description': description,
            'stock': stock,
            'image': filename,
            'timestamp': datetime.now().isoformat()
        }
        products = load_data()
        products.append(new_product)
        save_data(products)

        if stock <= 3:
            try:
                msg = Message('⚠️ Low Stock Alert', recipients=[app.config['MAIL_USERNAME']])
                msg.body = f"Low stock alert!\n\nProduct: {name}\nStock: {stock}"
                mail.send(msg)
            except Exception as e:
                print("Email send failed:", e)

        flash("✅ Product added!")
        return redirect(url_for('admin'))
    products = load_data()
    return render_template('index.html', products=products, query='')

  # <-- Add this

  


@app.template_filter('todatetime')
def todatetime_filter(s):
    return datetime.fromisoformat(s)


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

        # Send welcome email
        try:
            msg = Message("🎉 Welcome to ShopLuxe!", recipients=[email])
            msg.body = f"""Hello {name},

Thanks for signing up with ShopLuxe!

You can now log in and start exploring amazing products.

Best regards,  
ShopLuxe Team
"""
            mail.send(msg)
        except Exception as e:
            print("Email send failed:", e)

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

        token = serializer.dumps(email, salt='reset-password')
        reset_link = url_for('reset_with_token', token=token, _external=True)

        try:
            msg = Message("🔐 Password Reset Request", recipients=[email])
            msg.body = f"Hello,\n\nClick the link below to reset your password:\n\n{reset_link}\n\nThis link expires in 30 minutes."
            mail.send(msg)
        except Exception as e:
            print("Failed to send email:", e)
            flash("❌ Email send failed.")
            return redirect(url_for('forgot_password'))

        flash("📧 Check your email for the reset link.")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

# Admin login lockout config
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=5)


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
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], products[index]['image'])
        if os.path.exists(image_path):
            os.remove(image_path)
        del products[index]
        save_data(products)
        flash("🗑️ Product deleted.")
    else:
        flash("❌ Invalid product index.")
    return redirect(url_for('admin'))

@app.route('/product/<int:index>')
def product_detail(index):
    products = load_data()
    reviews = load_reviews()
    if 0 <= index < len(products):
        product = products[index]
        product['index'] = index
        product_category = product.get('category', '').strip().lower()
        related = [
            {'index': i, **p} for i, p in enumerate(products)
            if p.get('category', '').strip().lower() == product_category and i != index
        ][:4]
        product_reviews = [r for r in reviews if r['product_index'] == index]
        return render_template('product_detail.html', product=product, related=related, reviews=product_reviews)
    flash("⚠️ Product not found.")
    return redirect(url_for('index'))

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
        msg = Message("✅ Test Email from Flask App", recipients=[app.config['MAIL_USERNAME']])
        msg.body = "This is a test email to verify email sending from your Flask app."
        mail.send(msg)
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
    
    if category == 'all':
        products = get_all_products()
    else:
        products = get_products_by_category(category)

    featured_products = get_featured_products()

    return render_template('shop.html',
                           products=products,
                           featured_products=featured_products,
                           selected_category=category)
    
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
            cart_items.append(product)

    total = sum(float(p['price']) * p['quantity'] for p in cart_items)
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

        # Send confirmation and admin email
        try:
            item_lines = '\n'.join([
                f"{item['name']} x{item['quantity']} - GH₵ {item['price']}"
                for item in order['items']
            ])

            # Customer email
            msg = Message("🧾 Order Confirmation - ShopLuxe", recipients=[email])
            msg.body = f"""
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
            mail.send(msg)

            # Admin email
            admin_msg = Message("📦 New Order Received - ShopLuxe", recipients=[app.config['MAIL_USERNAME']])
            admin_msg.body = f"""Hello Admin,

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
            mail.send(admin_msg)

        except Exception as e:
            print("Failed to send email:", e)


        session.pop('cart', None)  # Clear cart
        return render_template('order_confirmation.html', order=order)

    return render_template('checkout.html', cart_items=cart_items, total=total)



@app.route('/order_confirmation')
def order_confirmation():
    order_info = session.get('order_info')
    if not order_info:
        flash("⚠️ No order found.")
        return redirect(url_for('cart'))
    return render_template('order_confirmation.html', order=order_info)

@app.route("/")
def home():
    return render_template('index.html', products=products)

@app.route("/healthz")
def health_check():
    return "OK", 200

if __name__ == "__main__":
    app.run()


    

if __name__ == '__main__':
    app.run(debug=True)
    

if __name__ == '__main__':
    app.run(debug=True)
