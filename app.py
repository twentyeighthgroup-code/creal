from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from functools import wraps # Добавили для защиты страниц

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

# Декоратор для защиты страниц (если не залогинен - перекидывает на регистрацию)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('register'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required # Теперь главная доступна только после входа
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: # Если уже залогинен, не пускаем на страницу регистрации
        return redirect(url_for('home'))
        
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
            session['username'] = username
            session['language'] = language
            return redirect(url_for('home'))
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
        
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = user.username
            session['language'] = user.language
            return redirect(url_for('home'))
        else:
            error = 'Неверный логин или пароль!' if session.get('language', 'ru') == 'ru' else 'Invalid username or password!'
    return render_template('login.html', error=error)

@app.route('/switch_language', methods=['GET'])
def switch_language():
    lang = request.args.get('lang')
    if lang and lang in ['ru', 'en']:
        session['language'] = lang
    return redirect(request.referrer or url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return redirect(url_for('register'))

if __name__ == '__main__':
    app.debug = True  
    app.run()
