from flask import Flask, render_template, jsonify

API_USER = 'f1419a42-2ab1-440c-caeb-08de0e3351a1'

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

if __name__ == '__main__':
    app.run(debug=True)