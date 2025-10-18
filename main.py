from flask import Flask, render_template, jsonify



# Utworzenie instancji aplikacji Flask

app = Flask(__name__)



# Proste dane statystyczne (np. liczba mieszkańców Płocka w kolejnych latach)

data = {

    "labels": ["2018", "2019", "2020", "2021", "2022", "2023"],

    "values": [121000, 120500, 120200, 119800, 119500, 119000]

}



@app.route('/')

def index():

    return render_template('index.html')

@app.route('/api/data')

def get_data():

    return jsonify(data)

# 2. Ludność i Demografia
# Wywoływana przez '/data/ludnosc' oraz url_for('data_ludnosc')
@app.route('/data/ludnosc')
def data_ludnosc():
    # Renderuje ludnosc.html
    return render_template('ludnosc.html', page_id='ludnosc')

# 3. Gospodarka i Finanse
# Wywoływana przez '/data/gospodarka' oraz url_for('data_gospodarka')
@app.route('/data/gospodarka')
def data_gospodarka():
    # Renderuje gospodarka.html
    return render_template('gospodarka.html', page_id='gospodarka')

# 4. Edukacja i Kultura
# Wywoływana przez '/data/edukacja' oraz url_for('data_edukacja')
@app.route('/data/edukacja')
def data_edukacja():
    # Renderuje edukacja.html
    return render_template('edukacja.html', page_id='edukacja')

# 5. Środowisko
# Wywoływana przez '/data/srodowisko' oraz url_for('data_srodowisko')
@app.route('/data/srodowisko')
def data_srodowisko():
    # Renderuje srodowisko.html
    return render_template('srodowisko.html', page_id='srodowisko')

# 6. Porównania Miast
# Wywoływana przez '/porownania/miasta' oraz url_for('porownania_miasta')
@app.route('/porownania/miasta')
def porownania_miasta():
    # Renderuje porownania_miasta.html
    return render_template('porownania_miast.html', page_id='porownania_miast')

# 7. Kontakt
# Wywoływana przez '/kontakt' oraz url_for('kontakt')
@app.route('/kontakt')
def kontakt():
    # Renderuje kontakt.html
    return render_template('kontakt.html', page_id='kontakt')


if __name__ == '__main__':
    # Uruchomienie aplikacji w trybie debugowania
    # Zostanie uruchomiona na http://127.0.0.1:5000/
    app.run(host='0.0.0.0', debug=True, port=8800)

