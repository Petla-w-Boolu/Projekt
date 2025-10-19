import os
import time
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# --- Konfiguracja Aplikacji ---
app = Flask(__name__)

# Upewnij się, że folder 'instance' istnieje
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Ustawienie ścieżki do bazy danych w folderze 'instance'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')
app.config['SECRET_KEY'] = 'twoj-bardzo-tajny-klucz-zmien-to' # Ważne: Zmień to!


# --- Inicjalizacja Rozszerzeń ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- Modele Bazy Danych (Użytkownicy i Raporty) ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    reports = db.relationship('Report', backref='author', lazy=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Trasy (Routes) ---

@app.route('/')
@login_required
def index():
    user_reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.id.desc()).all()
    return render_template('index.html', history=user_reports)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Logowanie nieudane. Sprawdź e-mail i hasło.', 'danger')
            
    return render_template('login.html', is_login_page=True)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Ten e-mail jest już zajęty.', 'warning')
            return render_template('login.html', is_login_page=False)

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        flash('Konto zostało utworzone! Możesz się teraz zalogować.', 'success')
        return redirect(url_for('login'))
        
    return render_template('login.html', is_login_page=False)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ENDPOINTY API ---

@app.route('/api/prompt', methods=['POST'])
@login_required
def handle_prompt():
    data = request.json
    prompt_text = data.get('prompt')

    if not prompt_text:
        return jsonify({'error': 'Brak promptu'}), 400

    try:
        gus_data = get_data_from_gus(prompt_text)
        ai_response_content = get_ai_report(prompt_text, gus_data)
        report_title = generate_title_for_history(prompt_text)

        new_report = Report(
            title=report_title,
            prompt=prompt_text,
            content=ai_response_content,
            user_id=current_user.id
        )
        db.session.add(new_report)
        db.session.commit()

        return jsonify({
            'prompt': prompt_text,
            'response': ai_response_content,
            'new_history_item': { 'id': new_report.id, 'title': new_report.title }
        })

    except Exception as e:
        print(f"Błąd w /api/prompt: {e}")
        return jsonify({'error': str(e)}), 500

# --- NOWY KOD: ENDPOINT DO USUWANIA RAPORTU ---
@app.route('/api/report/delete/<int:report_id>', methods=['DELETE'])
@login_required
def delete_report(report_id):
    try:
        # 1. Znajdź raport w bazie danych
        report = Report.query.get(report_id)

        # 2. Sprawdź, czy raport istnieje
        if not report:
            return jsonify({'error': 'Raport nie znaleziony'}), 404

        # 3. Sprawdź, czy obecny użytkownik jest właścicielem raportu (BARDZO WAŻNE!)
        if report.user_id != current_user.id:
            return jsonify({'error': 'Brak autoryzacji'}), 403

        # 4. Usuń raport z bazy danych
        db.session.delete(report)
        db.session.commit()

        # 5. Zwróć potwierdzenie sukcesu
        return jsonify({'success': True}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Błąd podczas usuwania raportu: {e}")
        return jsonify({'error': 'Błąd serwera'}), 500
# --- KONIEC NOWEGO KODU ---


# --- Funkcje "zaślepki" (STUBS) - DO IMPLEMENTACJI ---

def get_data_from_gus(prompt):
    """
    TODO: Zaimplementuj logikę pobierania danych z Banku Danych Lokalnych GUS.
    """
    print(f"[Symulacja GUS] Szukam danych dla: {prompt}")
    if "bezrobocie" in prompt.lower():
        return {"kategoria": "Bezrobocie", "wartosc": "5.2%", "okres": "Q3 2024", "zrodlo": "GUS BDL"}
    return {"zrodlo": "GUS BDL", "info": "Nie znaleziono konkretnych danych, dane ogólne."}

def get_ai_report(prompt, gus_data):
    """
    TODO: Zaimplementuj właściwe wywołanie API do modelu AI (np. Gemini).
    """
    print(f"[Symulacja AI] Generowanie raportu dla: {prompt} z danymi: {gus_data}")
    time.sleep(1.5)
    
    mock_response = f"Oto analiza dla Twojego zapytania: **'{prompt}'**.\n\n"
    if "wartosc" in gus_data:
        mock_response += f"Według danych z Głównego Urzędu Statystycznego (BDL), **{gus_data['kategoria']}** w Płocku wyniosło **{gus_data['wartosc']}** (dane za {gus_data['okres']}).\n\n"
    else:
        mock_response += "Nie udało mi się znaleźć konkretnych wskaźników w bazie GUS dla tego zapytania, ale oto ogólna analiza tematu dla Płocka...\n\n"
    
    mock_response += "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    return mock_response

def generate_title_for_history(prompt):
    """
    TODO: Zaimplementuj generowanie krótkiego tytułu (też można przez AI)
    """
    title = " ".join(prompt.split()[:4])
    if len(prompt.split()) > 4:
        title += "..."
    return title

# --- Uruchomienie ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)