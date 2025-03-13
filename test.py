from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import aliased
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
    plain_password = db.Column(db.String(200), nullable=True)  # Stockage temporaire du mot de passe
    role = db.Column(db.String(20), default='user')  # 'user', 'admin', ou 'manager'
    sales = db.relationship('Sale', backref='user', lazy=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Référence au manager
    managed_users = db.relationship('User', backref=db.backref('manager', remote_side=[id]), lazy=True)  # Relation inverse


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
    date_rdv = db.Column(db.String(10), nullable=True)  # Nouvelle colonne Date RDV
    date_raccordement = db.Column(db.String(10), nullable=True)  # Nouvelle colonne Date Raccordement
    client_name = db.Column(db.String(100), nullable=True)  # Nouvelle colonne Nom Client

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
    date_rdv = db.Column(db.String(10), nullable=True)  # Nouvelle colonne Date RDV
    date_raccordement = db.Column(db.String(10), nullable=True)  # Nouvelle colonne Date Raccordement
    client_name = db.Column(db.String(100), nullable=True)  # Nouvelle colonne Nom Client

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

    user = User.query.get(session['user_id'])  # Récupère l'utilisateur connecté

    # Récupérer tous les managers pour afficher la liste dans le filtre
    all_managers = User.query.filter_by(role='manager').all()

    # Récupérer les filtres depuis le formulaire
    filter_username = request.form.get('filter_username', '').strip()
    filter_contract_number = request.form.get('filter_contract_number', '').strip()
    filter_managers = request.form.getlist('filter_managers')  # Récupération en LISTE

    # Préparer la requête de base pour les ventes
    sales_query = Sale.query

    if user.role == 'admin':
        # Filtrer par username
        if filter_username:
            sales_query = sales_query.join(User).filter(User.username.ilike(f"%{filter_username}%"))

        # Filtrer par numéro de contrat
        if filter_contract_number:
            sales_query = sales_query.filter(Sale.contract_number.ilike(f"%{filter_contract_number}%"))

        # Filtrer par plusieurs managers sélectionnés
        if filter_managers:
            sales_query = sales_query.join(Sale.user).filter(User.manager_id.in_(filter_managers))

        all_sales = sales_query.options(db.joinedload(Sale.user).joinedload(User.manager)).all()

    elif user.role == 'manager':
        # Les managers voient uniquement les ventes de leurs utilisateurs affiliés
        managed_user_ids = [u.id for u in user.managed_users]
        sales_query = sales_query.filter(Sale.user_id.in_(managed_user_ids))

        # Appliquer les filtres
        if filter_username:
             sales_query = sales_query.join(User, Sale.user_id == User.id).filter(User.username.ilike(f"%{filter_username}%"))
        if filter_contract_number:
            sales_query = sales_query.filter(Sale.contract_number.ilike(f"%{filter_contract_number}%"))

        all_sales = sales_query.options(db.joinedload(Sale.user)).all()

    elif user.role == 'user':
        # Les utilisateurs voient uniquement leurs propres ventes
        sales_query = sales_query.filter_by(user_id=user.id)
        if filter_contract_number:
            sales_query = sales_query.filter(Sale.contract_number.ilike(f"%{filter_contract_number}%"))

        all_sales = sales_query.options(db.joinedload(Sale.user)).all()

    else:
        # Cas où le rôle est inconnu (sécurité)
        all_sales = []

    # Calcul des totaux pour les types de ventes (VV, VR, Mobiles)
    total_vv = sum(sale.quantity for sale in all_sales if sale.class_type == 'VV')
    total_vr = sum(sale.quantity for sale in all_sales if sale.class_type == 'VR')
    total_mobiles = sum(sale.quantity for sale in all_sales if sale.class_type == 'Mobiles')

    # Rendu du tableau
    return render_template(
        'layout.html',
        page='dashboard',
        all_sales=all_sales,
        all_managers=all_managers,  # Envoyer la liste des managers
        filter_managers=filter_managers,  # Passer les managers sélectionnés
        filter_username=filter_username,
        filter_contract_number=filter_contract_number,
        total_vv=total_vv,
        total_vr=total_vr,
        total_mobiles=total_mobiles
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



@app.route('/admin/manage_managers')
def manage_managers():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    managers = User.query.filter_by(role='manager').all()
    all_managers = User.query.filter_by(role='manager').all()  # Pour la réaffectation

    return render_template('layout.html', page='manage_managers', managers=managers, all_managers=all_managers)




@app.route('/admin/delete_manager/<int:manager_id>', methods=['POST'])
def delete_manager(manager_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    manager = User.query.get(manager_id)

    if not manager or manager.role != 'manager':
        flash("❌ Manager introuvable.", "error")
        return redirect(url_for('manage_managers'))

    try:
        # Récupérer les vendeurs affiliés à ce manager
        managed_users = User.query.filter_by(manager_id=manager.id).all()

        if managed_users:
            # Trouver un autre manager actif pour réaffecter les vendeurs
            other_manager = User.query.filter(User.role == 'manager', User.id != manager.id).first()
            
            for user in managed_users:
                user.manager_id = other_manager.id if other_manager else None  # Réaffectation ou suppression du lien

        # Supprimer les ventes du manager
        Sale.query.filter_by(user_id=manager.id).delete()

        # Supprimer le manager
        db.session.delete(manager)
        db.session.commit()

        flash(f"✅ Manager {manager.username} supprimé et ses vendeurs ont été réaffectés.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erreur lors de la suppression : {str(e)}", "error")

    return redirect(url_for('manage_managers'))



@app.route('/admin/reassign_users', methods=['POST'])
def reassign_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    old_manager_id = request.form.get('old_manager')
    new_manager_id = request.form.get('new_manager', None)  # Peut être vide

    old_manager = User.query.get(old_manager_id)
    new_manager = User.query.get(new_manager_id) if new_manager_id else None

    if not old_manager or old_manager.role != 'manager':
        flash("❌ Manager à supprimer introuvable.", "error")
        return redirect(url_for('manage_managers'))

    try:
        # Réaffecter les vendeurs
        for user in old_manager.managed_users:
            user.manager_id = new_manager.id if new_manager else None

        db.session.commit()
        flash("✅ Vendeurs réaffectés avec succès.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erreur lors de la réaffectation : {str(e)}", "error")

    return redirect(url_for('manage_managers'))




@app.route('/admin/upload_sales', methods=['GET', 'POST'])
def upload_sales():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            return "No file uploaded", 400  # Retourne une erreur si aucun fichier n'est fourni

        try:
            data = pd.read_excel(file)  # Charge le fichier Excel

            # Archiver les ventes existantes
            existing_sales = Sale.query.all()
            for sale in existing_sales:
                archived_sale = ArchivedSale(
                    date=sale.date,
                    offer_type=sale.offer_type,
                    plan=sale.plan,
                    quantity=sale.quantity,
                    user_id=sale.user_id,
                    contract_number=sale.contract_number,
                    date_rdv=sale.date_rdv,
                    date_raccordement=sale.date_raccordement,
                    client_name=sale.client_name,
                    archived_at=datetime.now()
                )
                db.session.add(archived_sale)

            Sale.query.delete()  # Supprime les anciennes ventes

            # Parcourir les données du fichier Excel
            for _, row in data.iterrows():
                username = row['Nom Prénom']
                manager_username = row['Manager'] if 'Manager' in row and pd.notnull(row['Manager']) else None
                offer_type = row['Type (Box ou Mobile)']
                plan = row['Plan (ULTYM, MUST, 130Go, 20Go)']
                quantity = int(row['Quantité']) if pd.notnull(row['Quantité']) else 0
                class_type = row['Class'] if pd.notnull(row['Class']) else ''
                contract_number = str(row['Numéro de contrat']) if pd.notnull(row['Numéro de contrat']) else ''
                date_rdv = row['Date RDV'] if pd.notnull(row['Date RDV']) else ''
                date_raccordement = row['Date Raccordement'] if pd.notnull(row['Date Raccordement']) else ''
                client_name = row['Nom Client'] if pd.notnull(row['Nom Client']) else ''

                # Convertir les dates en chaînes si elles existent
                if date_rdv:
                    date_rdv = pd.to_datetime(date_rdv).strftime('%Y-%m-%d')
                if date_raccordement:
                    date_raccordement = pd.to_datetime(date_raccordement).strftime('%Y-%m-%d')

                # Gestion ou création du manager
                manager = None
                if manager_username:
                    manager = User.query.filter_by(username=manager_username, role='manager').first()
                    if not manager:
                        # Crée un nouveau manager si absent
                        manager_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                        manager_hashed_password = generate_password_hash(manager_password, method='pbkdf2:sha256')
                        manager = User(username=manager_username, password=manager_hashed_password, plain_password=manager_password, role='manager')
                        db.session.add(manager)
                        db.session.commit()

                # Gestion ou création de l'utilisateur
                user = User.query.filter_by(username=username).first()
                if not user:
                    user_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                    user_hashed_password = generate_password_hash(user_password, method='pbkdf2:sha256')
                    user = User(username=username, password=user_hashed_password, plain_password=user_password, role='user', manager=manager)
                    db.session.add(user)
                else:
                    user.manager = manager  # Met à jour le manager de l'utilisateur existant

                db.session.commit()

                # Crée une nouvelle vente associée à l'utilisateur
                new_sale = Sale(
                    date=datetime.now().strftime('%Y-%m-%d'),
                    offer_type=offer_type,
                    plan=plan,
                    quantity=quantity,
                    user_id=user.id,
                    class_type=class_type,
                    contract_number=contract_number,
                    date_rdv=date_rdv,
                    date_raccordement=date_raccordement,
                    client_name=client_name
                )
                db.session.add(new_sale)

            db.session.commit()
            return "Sales and users with managers uploaded successfully!"

        except Exception as e:
            db.session.rollback()  # Annule les modifications en cas d'erreur
            return f"An error occurred: {str(e)}", 500

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
    sheet.append(["Username", "Role", "Password"])

    # Récupérer tous les utilisateurs (y compris les managers si souhaité)
    users = User.query.all()

    # Ajouter les données des utilisateurs dans le fichier Excel
    for user in users:
        if user.role in ['user', 'manager']:  # Inclure les utilisateurs et les managers
            sheet.append([user.username, user.role, user.plain_password or "N/A"])

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
            'date_rdv': archive.date_rdv,  # Ajout de la colonne Date RDV
            'date_raccordement': archive.date_raccordement,  # Ajout de la colonne Date Raccordement
            'client_name': archive.client_name,  # Ajout de la colonne Nom Client
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