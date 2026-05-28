import os
from datetime import datetime # Добавили импорт времени
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) 
    language = db.Column(db.String(10), nullable=False, default='ru')

# Модель поста
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(20), default='news')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.relationship('Like', backref='post', lazy=True)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('register'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required 
def home():
    # Получаем все посты, отсортированные от новых к старым
    all_posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('index.html', posts=all_posts)

@app.route('/add_post', methods=['POST'])
@login_required
def add_post():
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category', 'news')
    
    if title and content:
        new_post = Post(title=title, content=content, category=category, author=session['username'])
        db.session.add(new_post)
        db.session.commit()
        flash('Пост успешно опубликован!', 'success')
    return redirect(url_for('home'))

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    # Находим текущего пользователя по имени из сессии
    user = User.query.filter_by(username=session['username']).first()
    
    # Проверяем, есть ли уже лайк от этого пользователя
    existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
    
    if existing_like:
        db.session.delete(existing_like) # Убираем лайк
    else:
        new_like = Like(user_id=user.id, post_id=post_id) # Ставим лайк
        db.session.add(new_like)
    
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    # Удалять может только автор
    if post.author == session['username']:
        db.session.delete(post)
        db.session.commit()
        flash('Пост удален.', 'warning')
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        language = request.form['language']
        if User.query.filter_by(username=username).first():
            error = 'Пользователь уже существует!'
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password, language=language)
            db.session.add(new_user)
            db.session.commit()
            session['username'] = username
            session['language'] = language
            return redirect(url_for('home'))
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['username'] = user.username
            session['language'] = user.language
            return redirect(url_for('home'))
        else:
            error = 'Неверный логин или пароль!'
    return render_template('login.html', error=error)

@app.route('/switch_language', methods=['GET'])
def switch_language():
    lang = request.args.get('lang')
    if lang in ['ru', 'en']: session['language'] = lang
    return redirect(request.referrer or url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return redirect(url_for('register'))

if __name__ == '__main__':
    app.run(debug=True)
