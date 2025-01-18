from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # user or admin
    sales = db.relationship('Sale', backref='user', lazy=True)

# Sale model
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    offer_type = db.Column(db.String(100), nullable=False)  # Box or Mobile
    plan = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)  # Quantité
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_type = db.Column(db.String(20), nullable=False)  # Ajout de la colonne classe


# Archived Sale model
class ArchivedSale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    offer_type = db.Column(db.String(100), nullable=False)
    plan = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    archived_at = db.Column(db.DateTime, nullable=False)

@app.before_request
def restrict_access():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            session['role'] = user.role
        else:
            session.pop('user_id', None)

@app.route('/')
def home():
    return redirect(url_for('login'))



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

        return render_template('layout.html', page='login', error='Invalid username or password')

    return render_template('layout.html', page='login')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    # Filtrage par classe
    selected_class = request.form.get('class_filter', 'Brut')  # 'Brut' par défaut

    if user.role == 'admin':
        # Admin voit toutes les ventes
        if selected_class == 'Brut':
            all_sales = Sale.query.all()
        else:
            all_sales = Sale.query.filter_by(class_type=selected_class).all()

        total_vv = sum(sale.quantity for sale in all_sales if sale.class_type == 'VV')
        total_vr = sum(sale.quantity for sale in all_sales if sale.class_type == 'VR')
        total_mobiles = sum(sale.quantity for sale in all_sales if sale.class_type == 'Mobiles')

        return render_template('layout.html', page='dashboard',
                               all_sales=all_sales,
                               total_vv=total_vv,
                               total_vr=total_vr,
                               total_mobiles=total_mobiles,
                               selected_class=selected_class)

    elif user.role == 'user':
        # User voit uniquement ses ventes
        if selected_class == 'Brut':
            user_sales = Sale.query.filter_by(user_id=user.id).all()
        else:
            user_sales = Sale.query.filter_by(user_id=user.id, class_type=selected_class).all()

        total_vv = sum(sale.quantity for sale in user_sales if sale.class_type == 'VV')
        total_vr = sum(sale.quantity for sale in user_sales if sale.class_type == 'VR')
        total_mobiles = sum(sale.quantity for sale in user_sales if sale.class_type == 'Mobiles')

        return render_template('layout.html', page='dashboard',
                               all_sales=user_sales,
                               total_vv=total_vv,
                               total_vr=total_vr,
                               total_mobiles=total_mobiles,
                               selected_class=selected_class)




@app.route('/admin/create_user', methods=['GET', 'POST'])
def create_user():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            return render_template('layout.html', page='create_user', error='User already exists!')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, role='user')
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('layout.html', page='create_user')

@app.route('/admin/upload_sales', methods=['GET', 'POST'])
def upload_sales():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']

        if not file:
            return "No file uploaded"

        data = pd.read_excel(file)

        # Archiver les données existantes
        existing_sales = Sale.query.all()
        for sale in existing_sales:
            archived_sale = ArchivedSale(
                date=sale.date,
                offer_type=sale.offer_type,
                plan=sale.plan,
                quantity=sale.quantity,
                user_id=sale.user_id,
                archived_at=datetime.now()
            )
            db.session.add(archived_sale)

        Sale.query.delete()

        # Insérer les nouvelles données
        for index, row in data.iterrows():
            username = row['Nom Prénom']
            offer_type = row['Type (Box ou Mobile)']
            plan = row['Plan (ULTYM, MUST, 130Go, 20Go)']
            quantity = int(row['Quantité'])
            class_type = row['Class']  # Nouvelle colonne pour la classe

            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=generate_password_hash('default_password', method='pbkdf2:sha256'), role='user')
                db.session.add(user)
                db.session.commit()

            new_sale = Sale(date='2023-01-01', offer_type=offer_type, plan=plan, quantity=quantity, user_id=user.id, class_type=class_type)
            db.session.add(new_sale)

        db.session.commit()
        return "Sales uploaded successfully!"

    return render_template('layout.html', page='upload_sales')


@app.route('/admin/sales_ranking')
def sales_ranking():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    users = User.query.all()
    ranking_mobiles = []
    ranking_vr = []
    ranking_vv = []

    for user in users:
        total_sales_mobiles = sum(sale.quantity for sale in user.sales if sale.class_type == 'Mobiles')
        total_sales_vr = sum(sale.quantity for sale in user.sales if sale.class_type == 'VR')
        total_sales_vv = sum(sale.quantity for sale in user.sales if sale.class_type == 'VV')

        ranking_mobiles.append({'username': user.username, 'role': user.role, 'total_sales': total_sales_mobiles})
        ranking_vr.append({'username': user.username, 'role': user.role, 'total_sales': total_sales_vr})
        ranking_vv.append({'username': user.username, 'role': user.role, 'total_sales': total_sales_vv})

    ranking_mobiles.sort(key=lambda x: x['total_sales'], reverse=True)
    ranking_vr.sort(key=lambda x: x['total_sales'], reverse=True)
    ranking_vv.sort(key=lambda x: x['total_sales'], reverse=True)

    return render_template(
        'layout.html',
        page='sales_ranking',
        ranking_mobiles=ranking_mobiles,
        ranking_vr=ranking_vr,
        ranking_vv=ranking_vv,
        enumerate=enumerate
    )





@app.route('/admin/view_archives')
def view_archives():
    print("Accessing Archived Sales page...")  # Log
    if 'user_id' not in session or session.get('role') != 'admin':
        print("Unauthorized access!")  # Log
        return redirect(url_for('login'))

    archives = ArchivedSale.query.order_by(ArchivedSale.archived_at.desc()).all()
    print(f"Archives retrieved: {archives}")  # Log
    return render_template('layout.html', page='view_archives', archives=archives)


@app.route('/admin/all_sales')
def all_sales():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    users = User.query.all()
    user_sales_details = []

    for user in users:
        sales = Sale.query.filter_by(user_id=user.id).all()
        total_sales = sum(sale.quantity for sale in sales)
        user_sales_details.append({
            'user': user,
            'sales': sales,
            'total_sales': total_sales
        })

    total_global_sales = sum(detail['total_sales'] for detail in user_sales_details)

    # Passez toutes les données nécessaires au template
    return render_template('layout.html', page='all_sales', user_sales_details=user_sales_details, total_global_sales=total_global_sales)

@app.route('/admin/set_password', methods=['GET', 'POST'])
def set_password():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if not user:
            return "User not found"

        user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()

        return f"Password set successfully for {username}!"

    return '''
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Set User Password</h1>
        <form method="POST">
            <label for="username">Username:</label><br>
            <input type="text" name="username" id="username" required><br>
            <label for="password">New Password:</label><br>
            <input type="password" name="password" id="password" required><br>
            <button type="submit">Set Password</button>
        </form>
    </body>
    </html>
    '''




@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
