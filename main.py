from flask import Flask 

# Utworzenie instancji aplikacji Flask 
app = Flask(__name__) 

# Zdefiniowanie trasy (route) dla strony głównej 
@app.route('/') 
def hello_world(): 
    return 'Hello, World!' 

# Uruchomienie aplikacji 
if __name__ == '__main__': 
    app.run(debug=True)