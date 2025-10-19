import os
import time
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from google import genai

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
        ai_response_content = get_ai_report(gus_data)
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

def get_gemini_response(prompt):
    client = genai.Client()

    # 1. Wczytanie stałego prompta (System Instruction) i połączenie w jeden string
    try:
        with open('prompt.txt', 'r', encoding='utf-8') as f:
            system_prompt_content = f.read().strip()
    except FileNotFoundError:
        # Zgłoszenie błędu, jeśli plik systemowy nie istnieje
        raise FileNotFoundError("Brak pliku 'prompt.txt'. Upewnij się, że został utworzony z systemowym promptem.")

    # 2. Zbudowanie końcowego prompta dla modelu
    # Używamy formatu wymagającego odpowiedzi JSON, wstawiając query do szablonu.
    final_prompt = f"{system_prompt_content}\n\nZapytanie Użytkownika: \"{prompt}\""
    
    # 3. Wywołanie modelu
    response = client.models.generate_content(
        model="gemini-2.5-pro", 
        contents=final_prompt
    )
    
    # 4. Przetwarzanie odpowiedzi: Usunięcie markdownowych znaczników JSON i parsowanie
    raw_text = response.text.strip()
    
    # Usuwanie bloków kodu markdown (```json ... ```)
    if raw_text.startswith("```json"):
        raw_text = raw_text.strip("`").strip("json").strip()
    elif raw_text.startswith("```"):
         raw_text = raw_text.strip("`").strip()

    try:
        # Parsowanie do słownika Pythona
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Raw text failed to decode: {raw_text}")
        raise ValueError("Model zwrócił nieprawidłowy format JSON, lub odpowiedź nie jest tylko JSON-em.")

def get_data_from_gus(prompt):
    return get_gemini_response(prompt)

def get_ai_report(gus_data):
    return gus_data['data_meta']['statistical_commentary']

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