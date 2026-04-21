from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    language = db.Column(db.String(10), nullable=False, default='ru')

with app.app_context():
    db.create_all()

# --- Маршруты теперь проще ---

@app.route('/')
def home():
    # Теперь он ищет файл index.html в папке templates
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        language = request.form['language']
        if User.query.filter_by(username=username).first():
            error = 'Пользователь уже существует!' if session.get('language', 'ru') == 'ru' else 'User already exists!'
        else:
            new_user = User(username=username, password=password, language=language)
            db.session.add(new_user)
            db.session.commit()
            session['language'] = language
            session['username'] = username
            return redirect(url_for('home'))
    
    # Ищет файл register.html в папке templates
    return render_template('register.html', error=error)

@app.route('/switch_language', methods=['GET'])
def switch_language():
    lang = request.args.get('lang')
    if lang and lang in ['ru', 'en']:
        session['language'] = lang
    return redirect(request.referrer or url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    session.pop('language', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
