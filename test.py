from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
from flask import send_file
import openpyxl
from io import BytesIO

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
    plain_password = db.Column(db.String(200), nullable=True)  # Stockage en clair (temporaire)
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
    contract_number = db.Column(db.String(50), nullable=False)  # Numéro de contrat

# Archived Sale model
class ArchivedSale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    offer_type = db.Column(db.String(100), nullable=False)
    plan = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    contract_number = db.Column(db.String(50), nullable=False)
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

    # Récupérer les filtres du formulaire
    filter_username = request.form.get('filter_username', '').strip()
    filter_contract_number = request.form.get('filter_contract_number', '').strip()

    # Début de la requête
    sales_query = Sale.query

    if user.role == 'admin':
        # Filtrer pour les administrateurs
        if filter_username:
            sales_query = sales_query.join(User).filter(User.username.ilike(f"%{filter_username}%"))
        if filter_contract_number:
            sales_query = sales_query.filter(Sale.contract_number.ilike(f"%{filter_contract_number}%"))
        all_sales = sales_query.all()
    elif user.role == 'user':
        # Filtrer uniquement les ventes de l'utilisateur connecté
        sales_query = sales_query.filter_by(user_id=user.id)
        if filter_contract_number:
            sales_query = sales_query.filter(Sale.contract_number.ilike(f"%{filter_contract_number}%"))
        all_sales = sales_query.all()

    # Calcul des totaux pour les cartes
    total_vv = sum(sale.quantity for sale in all_sales if sale.class_type == 'VV')
    total_vr = sum(sale.quantity for sale in all_sales if sale.class_type == 'VR')
    total_mobiles = sum(sale.quantity for sale in all_sales if sale.class_type == 'Mobiles')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template(
            'dashboard.html',  # Page sans layout
            all_sales=all_sales,
            total_vv=total_vv,
            total_vr=total_vr,
            total_mobiles=total_mobiles,
            filter_username=filter_username,
            filter_contract_number=filter_contract_number
        )


    return render_template(
        'layout.html',
        page='dashboard',
        all_sales=all_sales,
        total_vv=total_vv,
        total_vr=total_vr,
        total_mobiles=total_mobiles,
        filter_username=filter_username,
        filter_contract_number=filter_contract_number
    )






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

import string
import random
from werkzeug.security import generate_password_hash

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
                contract_number=sale.contract_number,
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
            class_type = row['Class']  # Classe (VR, VV, etc.)
            contract_number = str(row['Numéro de contrat'])  # Numéro de contrat

            user = User.query.filter_by(username=username).first()

            if not user:
                # Générer un mot de passe aléatoire pour les nouveaux utilisateurs
                plain_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                hashed_password = generate_password_hash(plain_password, method='pbkdf2:sha256')

                # Créer un nouvel utilisateur
                user = User(username=username, password=hashed_password, plain_password=plain_password, role='user')
                db.session.add(user)
                db.session.commit()

            # Créer une nouvelle vente associée à l'utilisateur
            new_sale = Sale(
                date=datetime.now().strftime('%Y-%m-%d'),  # Vous pouvez modifier cette date
                offer_type=offer_type,
                plan=plan,
                quantity=quantity,
                user_id=user.id,
                class_type=class_type,
                contract_number=contract_number,
            )
            db.session.add(new_sale)

        db.session.commit()
        return "Sales uploaded successfully!"

    return render_template('layout.html', page='upload_sales')


@app.route('/admin/export_users', methods=['GET'])
def export_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Créer un classeur Excel
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Users and Passwords"

    # Ajouter les en-têtes
    sheet.append(["Username", "Password"])

    # Récupérer tous les utilisateurs (sauf admin)
    users = User.query.filter(User.role != 'admin').all()

    # Ajouter les données des utilisateurs dans le fichier Excel
    for user in users:
        # Utiliser plain_password pour exporter les mots de passe en clair
        sheet.append([user.username, user.plain_password or "N/A"])

    # Sauvegarder le fichier Excel dans un flux en mémoire
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    # Retourner le fichier Excel au client
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='users_and_passwords.xlsx'
    )




@app.route('/admin/sales_ranking')
def sales_ranking():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Exclure les administrateurs
    users = User.query.filter(User.role != 'admin').all()
    ranking_mobiles = []
    ranking_vr = []
    ranking_vv = []

    for user in users:
        # Récupérer le total des ventes par classe pour chaque utilisateur
        total_sales_mobiles = sum(sale.quantity for sale in user.sales if sale.class_type == 'Mobiles')
        total_sales_vr = sum(sale.quantity for sale in user.sales if sale.class_type == 'VR')
        total_sales_vv = sum(sale.quantity for sale in user.sales if sale.class_type == 'VV')

        ranking_mobiles.append({'username': user.username, 'role': user.role, 'total_sales': total_sales_mobiles})
        ranking_vr.append({'username': user.username, 'role': user.role, 'total_sales': total_sales_vr})
        ranking_vv.append({'username': user.username, 'role': user.role, 'total_sales': total_sales_vv})

    # Trier chaque liste de classement par ventes totales (ordre décroissant)
    ranking_mobiles.sort(key=lambda x: x['total_sales'], reverse=True)
    ranking_vr.sort(key=lambda x: x['total_sales'], reverse=True)
    ranking_vv.sort(key=lambda x: x['total_sales'], reverse=True)

    # Passer les classements dans le contexte du template
    return render_template(
        'layout.html',
        page='sales_ranking',
        ranking_mobiles=ranking_mobiles,
        ranking_vr=ranking_vr,
        ranking_vv=ranking_vv,
        enumerate=enumerate
    )



@app.route('/admin/delete_archives', methods=['POST'])
def delete_archives():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        count_before = ArchivedSale.query.count()  # Compter les archives avant suppression
        print(f"Number of archives before deletion: {count_before}")

        ArchivedSale.query.delete()  # Supprime toutes les archives
        db.session.commit()

        count_after = ArchivedSale.query.count()  # Compter les archives après suppression
        print(f"Number of archives after deletion: {count_after}")

        flash(f'All {count_before} archives have been successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting archives: {str(e)}', 'error')
    
    return redirect(url_for('view_archives'))




@app.route('/admin/view_archives')
def view_archives():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    archives = ArchivedSale.query.all()
    enriched_archives = []

    for archive in archives:
        user = User.query.get(archive.user_id)
        enriched_archives.append({
            'username': user.username if user else 'Unknown',
            'date': archive.date,
            'offer_type': archive.offer_type,
            'plan': archive.plan,
            'quantity': archive.quantity,
            'contract_number': archive.contract_number,
            'archived_at': archive.archived_at
        })

    return render_template('layout.html', page='view_archives', archives=enriched_archives)



@app.route('/admin/all_sales', methods=['GET', 'POST'])
def all_sales():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Récupération des filtres
    filter_username = request.form.get('filter_username', None)
    filter_role = request.form.get('filter_role', None)
    filter_contract_number = request.form.get('filter_contract_number', None)  # Nouveau filtre

    query = User.query.filter(User.role != 'admin')  # Exclure les administrateurs

    # Application des filtres
    if filter_username:
        query = query.filter(User.username.like(f"%{filter_username}%"))
    if filter_role:
        query = query.filter(User.role == filter_role)

    users = query.all()
    user_sales_details = []

    for user in users:
        sales_query = Sale.query.filter_by(user_id=user.id)

        # Application du filtre par Numéro de Contrat
        if filter_contract_number:
            sales_query = sales_query.filter(Sale.contract_number.like(f"%{filter_contract_number}%"))

        sales = sales_query.all()

        # Calcul des totaux par type
        total_vv = sum(sale.quantity for sale in sales if sale.class_type == 'VV')
        total_vr = sum(sale.quantity for sale in sales if sale.class_type == 'VR')
        total_mobiles = sum(sale.quantity for sale in sales if sale.class_type == 'Mobiles')

        user_sales_details.append({
            'user': user,
            'sales': sales,
            'total_vv': total_vv,
            'total_vr': total_vr,
            'total_mobiles': total_mobiles
        })

    total_global_sales = sum(detail['total_vv'] + detail['total_vr'] + detail['total_mobiles'] for detail in user_sales_details)
    total_vv_sales = sum(detail['total_vv'] for detail in user_sales_details)

    return render_template(
        'layout.html',
        page='all_sales',
        user_sales_details=user_sales_details,
        total_global_sales=total_global_sales,
        total_vv_sales=total_vv_sales,
        filter_username=filter_username,
        filter_role=filter_role,

        filter_contract_number=filter_contract_number  # Inclure le nouveau filtre dans le contexte
    )





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

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        return "User not found", 404

    # Supprimer l'utilisateur et ses ventes associées
    Sale.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('all_sales'))



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)