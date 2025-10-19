import os
import time
import json as json_lib # Używamy aliasu, aby uniknąć konfliktu z flask.json
import statistics # Potrzebne do obliczeń
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
import google.generativeai as genai 

# --- Konfiguracja Aplikacji ---
app = Flask(__name__)

api_key = None
try:
    with open('api_key.txt', 'r') as f:
        api_key = f.read().strip()
except FileNotFoundError:
    pass # Plik nie istnieje, przejdziemy do zmiennej środowiskowej

# 2. Jeśli klucz nie został wczytany z pliku, spróbuj ze zmiennej środowiskowej
if not api_key:
    api_key = os.environ.get('GOOGLE_API_KEY')

# 3. Skonfiguruj genai, jeśli klucz jest dostępny
if api_key:
    genai.configure(api_key=api_key)
else:
    print("OSTRZEŻENIE: Klucz API Gemini nie został znaleziony ani w pliku api_key.txt, ani w zmiennej środowiskowej GOOGLE_API_KEY. Wywołania API nie będą działać.")

try:
    os.makedirs(app.instance_path)
except OSError:
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'app.db')
app.config['SECRET_KEY'] = 'twoj-bardzo-tajny-klucz-zmien-to' 

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- Modele Bazy Danych ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    reports = db.relationship('Report', backref='author', lazy=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False) # Będzie przechowywać pełny HTML raportu
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Trasy (Routes) ---

@app.route('/')
@login_required
def index():
    user_reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.id.desc()).all()
    # --- POPRAWKA ---
    # Upewniamy się, że ładujemy plik 'index.html'
    return render_template('index.html', history=user_reports or [])
    # --- KONIEC POPRAWKI ---

# --- Twoje trasy /login, /register, /logout (bez zmian) ---
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


# --- NOWA, ROZBUDOWANA FUNKCJA GENERUJĄCA RAPORT HTML ---

def generate_interactive_report_html(gus_data):
    """
    Przetwarza pełny JSON z GUS (z Gemini) i generuje bogaty raport HTML.
    Jest odporna na różne formaty wejściowe.
    """
    try:
        # --- ŚCIEŻKA A: Pełny raport z danymi (wykrywamy po 'data_series') ---
        if isinstance(gus_data, dict) and gus_data.get('data_series'):
            data_meta = gus_data.get('data_meta', {})
            # Sprawdzamy, czy data_series nie jest pustą listą
            if not gus_data['data_series']:
                    raise ValueError("Klucz 'data_series' jest pustą listą.")
                    
            # Bierzemy pierwszą serię TYLKO do obliczeń KPI i tabeli na dole
            # Wykres będzie używał WSZYSTKICH serii
            data_series_dla_kpi = gus_data['data_series'][0] 
            data_points = data_series_dla_kpi.get('data_points', [])

            if not data_points:
                raise ValueError("Klucz 'data_series' istnieje, ale 'data_points' jest pusty.")

            title = data_meta.get('title', 'Raport Danych')
            source = data_meta.get('source_info', 'Brak danych o źródle')
            latest_period_str = data_meta.get('latest_period', 'N/A')
            statistical_commentary = data_meta.get('statistical_commentary', 'Brak komentarza analitycznego.')

            # Konwersja na liczby z obsługą błędów (np. jeśli value nie jest liczbą)
            values = []
            valid_data_points = []
            for p in data_points:
                try:
                    values.append(float(p['value']))
                    valid_data_points.append(p)
                except (ValueError, TypeError):
                    print(f"Ostrzeżenie: Pomijam błędny punkt danych: {p}")
            
            if not values:
                    raise ValueError("Brak poprawnych punktów danych ('value') do przetworzenia.")

            data_points = valid_data_points # Używamy tylko poprawnych punktów

            # --- Obliczenia KPI (zabezpieczone przed błędami) ---
            # UWAGA: Te KPI wciąż bazują tylko na PIERWSZEJ serii danych
            latest_point = data_points[-1]
            previous_point = data_points[-2] if len(data_points) > 1 else None
            
            latest_date_parts = latest_point['category'].split('-')
            yoy_point = None # Ustawiamy domyślnie na None

            # Sprawdzamy, czy kategoria ma co najmniej 2 części (np. YYYY i MM)
            if len(latest_date_parts) >= 2:
                try:
                    # Próbujemy obliczyć kategorię r/r
                    yoy_category = f"{int(latest_date_parts[0]) - 1}-{latest_date_parts[1]}"
                    yoy_point = next((p for p in data_points if p['category'] == yoy_category), None)
                except (ValueError, IndexError):
                    # Przechwytujemy błąd, jeśli np. 'category' to 'Styczeń-2023' 
                    # (int('Styczeń') się nie uda) lub format jest jeszcze inny.
                    print(f"Ostrzeżenie: Nie można obliczyć r/r dla kategorii: {latest_point['category']}")
                    yoy_point = None # Na wszelki wypadek resetujemy

            kpi_latest = latest_point['value']
            kpi_mom_diff = round(kpi_latest - previous_point['value'], 2) if previous_point else None
            kpi_yoy_diff = round(kpi_latest - yoy_point['value'], 2) if yoy_point else None

            kpi_max = max(values)
            # Znajdź pierwszy pasujący element (na wypadek duplikatów max)
            kpi_max_point = next(p for p in data_points if p['value'] == kpi_max)
            kpi_max_date = kpi_max_point['category']

            kpi_min = min(values)
            # Znajdź pierwszy pasujący element (na wypadek duplikatów min)
            kpi_min_point = next(p for p in data_points if p['value'] == kpi_min)
            kpi_min_date = kpi_min_point['category']

            stat_mean = round(statistics.mean(values), 2)
            stat_median = round(statistics.median(values), 2)
            stat_stddev = round(statistics.stdev(values), 2) if len(values) > 1 else 0
            unit = data_meta.get('unit', '') # Pobieramy jednostkę

            # --- Funkcje pomocnicze do budowy HTML ---
            def get_diff_class(diff):
                if diff is None: return "diff-neutral"
                # Zakładamy, że spadek to dobrze (jak w bezrobociu)
                if unit == '%': # Specjalna logika dla procentów (np. bezrobocie)
                    if diff < 0: return "diff-positive" 
                    if diff > 0: return "diff-negative"
                else: # Ogólna logika (wzrost = dobrze)
                    if diff > 0: return "diff-positive"
                    if diff < 0: return "diff-negative"
                return "diff-neutral"

            def get_diff_icon(diff):
                if diff is None: return '<i data-lucide="minus"></i>'
                if unit == '%':
                        if diff < 0: return '<i data-lucide="arrow-down-right"></i>'
                        if diff > 0: return '<i data-lucide="arrow-up-right"></i>'
                else:
                        if diff > 0: return '<i data-lucide="arrow-up-right"></i>'
                        if diff < 0: return '<i data-lucide="arrow-down-right"></i>'
                return '<i data-lucide="minus"></i>'
            
            def format_diff(diff):
                if diff is None: return "Brak danych"
                return f"{diff:+.1f} {unit if unit != '%' else 'p.p.'}"

            # --- Budowanie komponentów HTML ---
            
            # A. Karty KPI
            kpi_html = f"""
            <div class="kpi-container">
                <div class="kpi-card">
                    <span class="kpi-title">Aktualna wartość ({latest_period_str})</span>
                    <span class="kpi-value">{kpi_latest}{unit}</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Zmiana (m/m)</span>
                    <span class="kpi-value {get_diff_class(kpi_mom_diff)}">
                        {get_diff_icon(kpi_mom_diff)} {format_diff(kpi_mom_diff)}
                    </span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Zmiana (r/r)</span>
                    <span class="kpi-value {get_diff_class(kpi_yoy_diff)}">
                        {get_diff_icon(kpi_yoy_diff)} {format_diff(kpi_yoy_diff)}
                    </span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Minimum</span>
                    <span class="kpi-value">{kpi_min}{unit} <span class="kpi-date">({kpi_min_date})</span></span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Maksimum</span>
                    <span class="kpi-value">{kpi_max}{unit} <span class="kpi-date">({kpi_max_date})</span></span>
                </div>
            </div>
            """

            # B. Wykres (Canvas + dane dla Chart.js) - WERSJA DLA WIELU SERII
            canvas_id = f"report-chart-{int(time.time() * 1000)}"
            
            # Zakładamy, że wszystkie serie mają te same etykiety (osie X)
            # Bierzemy etykiety z pierwszej serii (tej samej co dla KPI)
            chart_labels = [p['category'] for p in data_points] 

            # Definiujemy paletę kolorów dla kolejnych linii
            chart_colors = [
                {"border": "#3e95cd", "bg": "rgba(62, 149, 205, 0.2)"}, # Niebieski
                {"border": "#c45850", "bg": "rgba(196, 88, 80, 0.2)"}, # Czerwony
                {"border": "#3cba9f", "bg": "rgba(60, 186, 159, 0.2)"}, # Zielony
                {"border": "#e8c3b9", "bg": "rgba(232, 195, 185, 0.2)"}, # Różowy
                {"border": "#8e5ea2", "bg": "rgba(142, 94, 162, 0.2)"}  # Fioletowy
            ]

            datasets_list = []
            # Iterujemy po WSZYSTKICH seriach zwróconych przez AI
            for i, series in enumerate(gus_data['data_series']):
                series_data_points = series.get('data_points', [])
                # WAŻNE: Wartości dla wykresu muszą być pobrane z KAŻDEJ serii
                # Musimy też obsłużyć błędy konwersji, tak jak robiliśmy to dla KPI
                series_values = []
                for p in series_data_points:
                    try:
                        series_values.append(float(p['value']))
                    except (ValueError, TypeError):
                        series_values.append(None) # Dodaj null, jeśli dana jest błędna
                        
                color = chart_colors[i % len(chart_colors)] # Wybierz kolor z palety (zapętla się)
                
                dataset_object = {
                    "label": series.get('series_name', f'Seria {i+1}'),
                    "data": series_values,
                    "borderColor": color["border"],
                    "backgroundColor": color["bg"],
                    "fill": True,
                    "tension": 0.1
                }
                datasets_list.append(dataset_object)

            chart_config = {
                "type": data_meta.get("chart_type_suggestion", "line"),
                "data": {
                    "labels": chart_labels,
                    "datasets": datasets_list # <-- POPRAWKA: Używamy dynamicznej listy
                },
                "options": {
                    "responsive": True,
                    "maintainAspectRatio": False,
                    "plugins": {
                        "title": {
                            "display": True, 
                            "text": title, 
                            "color": "#E0E0E0" # Jasnoszary kolor tytułu
                        },
                        "legend": {
                            "labels": {
                                "color": "#E0E0E0" # Jasnoszary kolor tekstu legendy
                            }
                        }
                    },
                    "scales": {
                        "x": {
                            "title": {
                                "display": True, 
                                "text": data_meta.get('x_axis_label', 'Okres'), 
                                "color": "#B0B0B0" # Jasnoszary kolor osi
                            },
                            "ticks": { "color": "#B0B0B0" },
                            "grid": { "color": "rgba(255, 255, 255, 0.1)" }
                        },
                        "y": {
                            "title": {
                                "display": True, 
                                "text": data_meta.get('y_axis_label', 'Wartość'), 
                                "color": "#B0B0B0" # Jasnoszary kolor osi
                            },
                            "ticks": { "color": "#B0B0B0" },
                            "grid": { "color": "rgba(255, 255, 255, 0.1)" }
                        }
                    }
                }
            }
            
            # Serializujemy JSON i "wstrzykujemy" go do atrybutu data-
            chart_html = f"""
            <div class="chart-container">
                <canvas id="{canvas_id}" data-chart-config='{json_lib.dumps(chart_config)}'></canvas>
            </div>
            """
            
            # C. Komentarz analityczny (jako Markdown)
            analysis_html = f"""
            <h3>Analiza Statystyczna</h3>
            <div class="markdown-content">
                <pre>{statistical_commentary}</pre>
            </div>
            """

            # D. Tabela ze szczegółowymi danymi (wciąż bazuje tylko na PIERWSZEJ serii)
            table_rows = "".join([f"<tr><td>{p['category']}</td><td>{p['value']}{unit}</td></tr>" for p in reversed(data_points)])
            table_html = f"""
            <h3>Szczegółowe Dane</h3>
            <div class="table-container">
                <table class="report-table">
                    <thead>
                        <tr><th>Okres</th><th>{data_meta.get('y_axis_label', 'Wartość')} (dla serii: {data_series_dla_kpi.get('series_name', 'Seria 1')})</th></tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
            <p class="source-info">Źródło danych: {source}</p>
            """

            # --- Składanie końcowego HTML ---
            final_html = f"""
            <div class="interactive-report">
                <h2>{title}</h2>
                {kpi_html}
                {chart_html}
                {analysis_html}
                
                <h3>Podsumowanie statystyczne (cały okres, dla pierwszej serii)</h3>
                <ul class="stats-summary">
                    <li>Średnia: <strong>{stat_mean}{unit}</strong></li>
                    <li>Mediana: <strong>{stat_median}{unit}</strong></li>
                    <li>Odch. standardowe: <strong>{stat_stddev:.2f} {unit if unit != '%' else 'p.p.'}</strong></li>
                </ul>
                
                {table_html}
            </div>
            """
            return final_html

        # --- ŚCIEŻKA B: Prosta odpowiedź tekstowa (brak 'data_series') ---
        elif isinstance(gus_data, dict):
            commentary = gus_data.get('data_meta', {}).get('statistical_commentary')
            if not commentary:
                commentary = gus_data.get('text_response') # Dodatkowy fallback
            if not commentary:
                commentary = gus_data.get('message', 'Otrzymano odpowiedź, ale bez treści do wyświetlenia.')
            
            # Zwracamy jako blok markdown
            return f'<div class="markdown-content"><pre>{commentary}</pre></div>'
            
        # --- ŚCIEŻKA C: Odpowiedź nie jest słownikiem (np. błąd) ---
        else:
            return f'<div class="report-error"><p>Otrzymano nieoczekiwany format danych od AI.</p><pre>{str(gus_data)}</pre></div>'

    except Exception as e:
        print(f"Błąd podczas generowania raportu HTML: {e}")
        # Zwróć prosty błąd jako HTML, który pojawi się w czacie
        return f"""
        <div class="report-error">
            <h4>Błąd podczas generowania raportu</h4>
            <p>Niestety, wystąpił problem podczas analizy danych. Spróbuj zadać pytanie ponownie.</p>
            <p>Szczegóły błędu: {e}</p>
        </div>
        """


# --- ENDPOINTY API ---

@app.route('/api/prompt', methods=['POST'])
@login_required
def handle_prompt():
    data = request.json
    prompt_text = data.get('prompt')

    if not prompt_text:
        return jsonify({'error': 'Brak promptu'}), 400

    try:
        # 1. Pobierz pełne dane JSON od Gemini
        gus_data = get_data_from_gus(prompt_text)
        
        # 2. Wygeneruj bogaty raport HTML na podstawie tych danych
        ai_response_content = generate_interactive_report_html(gus_data)
        
        # 3. Wygeneruj tytuł dla historii
        report_title = generate_title_for_history(prompt_text)

        # 4. Zapisz raport (teraz jako HTML) do bazy danych
        new_report = Report(
            title=report_title,
            prompt=prompt_text,
            content=ai_response_content, # Zapisujemy pełny HTML
            user_id=current_user.id
        )
        db.session.add(new_report)
        db.session.commit()

        # 5. Zwróć HTML do frontendu
        return jsonify({
            'prompt': prompt_text,
            'response': ai_response_content,
            'new_history_item': { 'id': new_report.id, 'title': new_report.title }
        })

    except Exception as e:
        print(f"Błąd w /api/prompt: {e}")
        error_html = f'<div class="report-error"><p>Wystąpił błąd serwera: {e}</p></div>'
        return jsonify({'response': error_html})


# Endpoint do usuwania (bez zmian)
@app.route('/api/report/delete/<int:report_id>', methods=['DELETE'])
@login_required
def delete_report(report_id):
    try:
        report = Report.query.get(report_id)
        if not report:
            return jsonify({'error': 'Raport nie znaleziony'}), 404
        if report.user_id != current_user.id:
            return jsonify({'error': 'Brak autoryzacji'}), 403
        
        db.session.delete(report)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Błąd podczas usuwania raportu: {e}")
        return jsonify({'error': 'Błąd serwera'}), 500


# --- Logika AI (Teraz używa prawdziwego API) ---

def get_gemini_response(prompt):
    
    print(f"Wysyłanie promptu do Gemini: {prompt}")
    try:
        with open('prompt.txt', 'r', encoding='utf-8') as f:
            system_prompt_content = f.read().strip()
    except FileNotFoundError:
        print("BŁĄD: Brak pliku 'prompt.txt'. Używam domyślnego promptu systemowego.")
        # Możesz tu zdefiniować domyślny prompt systemowy, jeśli pliku nie ma
        system_prompt_content = "Jesteś asystentem AI. Odpowiedz na pytanie użytkownika." 
        # return {"status": "error", "message": "Brak pliku konfiguracyjnego 'prompt.txt'."}

    final_prompt = f"{system_prompt_content}\n\nZapytanie Użytkownika: \"{prompt}\""
    
    try:
        # Używamy modelu skonfigurowanego przez genai.configure()
        model = genai.GenerativeModel('gemini-2.5-pro') # Lub inny model, np. 2.5-pro
        
        # Ustawienia generowania - wymuszamy odpowiedź JSON
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json" 
        )

        response = model.generate_content(
            final_prompt,
            generation_config=generation_config
        )
        
        # Dostęp do surowego tekstu JSON (Gemini powinien zwrócić sam JSON)
        raw_text = response.text.strip()
        print(f"Otrzymano surową odpowiedź od Gemini:\n{raw_text}") # Logowanie odpowiedzi

        # Parsowanie JSON
        try:
            parsed_json = json_lib.loads(raw_text)
            return parsed_json
        except json_lib.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Surowy tekst, który nie dał się sparsować: {raw_text}")
            return {"status": "error", "message": f"Model zwrócił odpowiedź, która nie jest poprawnym formatem JSON. Treść: {raw_text}"}

    except Exception as e:
        print(f"Błąd podczas komunikacji z Google GenAI: {e}")
        return {"status": "error", "message": f"Wystąpił błąd podczas komunikacji z API AI: {e}"}


def get_data_from_gus(prompt):
    return get_gemini_response(prompt)


def generate_title_for_history(prompt):
    title = " ".join(prompt.split()[:4])
    if len(prompt.split()) > 4:
        title += "..."
    return title

# --- Uruchomienie ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Użyj host='0.0.0.0' jeśli chcesz, aby aplikacja była dostępna w sieci lokalnej
    app.run(debug=True, port=5000)