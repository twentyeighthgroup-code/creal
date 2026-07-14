import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- 1. Безопасная конфигурация ---
# В продакшене SECRET_KEY должен быть сложным и храниться в переменных окружения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_supersecretkey_change_me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки загрузки файлов (защита от перегрузки сервера)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # Максимум 2 МБ на файл
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Создаем папку для загрузок, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
print(f"--- БАЗА ДАННЫХ ИНИЦИАЛИЗИРОВАНА: {app.config['SQLALCHEMY_DATABASE_URI']} ---")

# --- 2. Модели данных ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) 
    language = db.Column(db.String(10), nullable=False, default='ru')
    avatar_filename = db.Column(db.String(120), default='default.png')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(20), default='news')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # Каскадное удаление лайков при удалении поста
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete-orphan")

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)

with app.app_context():
    db.create_all()

# --- 3. Утилиты и Декораторы ---
def allowed_file(filename):
    """Проверка расширения файла для безопасности"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            # ИСПРАВЛЕНО: перенаправляем на login, а не на register
            flash('Для доступа к этой странице необходимо войти в систему.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 4. Маршруты (Routes) ---

@app.route('/')
@login_required 
def home():
    user = User.query.filter_by(username=session['username']).first()
    
    # Защита от "призрачной" сессии (если пользователь удален из БД, но сессия жива)
    if not user:
        session.clear()
        flash('Ваша сессия недействительна. Пожалуйста, войдите снова.', 'error')
        return redirect(url_for('login'))
        
    all_posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('index.html', posts=all_posts, user=user)

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'file' not in request.files:
        flash('Файл не выбран.', 'error')
        return redirect(url_for('home'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран.', 'error')
        return redirect(url_for('home'))
        
    if file and allowed_file(file.filename):
        # Генерируем уникальное имя файла, чтобы избежать перезаписи и конфликтов
        original_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(original_filename)
        unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        user = User.query.filter_by(username=session['username']).first()
        if user:
            user.avatar_filename = unique_filename
            db.session.commit()
            flash('Аватар успешно обновлен!', 'success')
    else:
        flash(f'Недопустимый формат файла. Разрешены: {", ".join(ALLOWED_EXTENSIONS)}', 'error')
        
    return redirect(url_for('home'))

@app.route('/add_post', methods=['POST'])
@login_required
def add_post():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    category = request.form.get('category', 'news')
    
    if title and content:
        try:
            new_post = Post(title=title, content=content, category=category, author=session['username'])
            db.session.add(new_post)
            db.session.commit()
            flash('Пост успешно опубликован!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при сохранении поста.', 'error')
    else:
        flash('Заголовок и содержание не могут быть пустыми.', 'error')
        
    return redirect(url_for('home'))

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('login'))
        
    existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
    
    try:
        if existing_like:
            db.session.delete(existing_like)
        else:
            new_like = Like(user_id=user.id, post_id=post_id)
            db.session.add(new_like)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Ошибка при обработке лайка.', 'error')
        
    return redirect(url_for('home'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author == session['username']:
        try:
            db.session.delete(post)
            db.session.commit()
            flash('Пост успешно удален.', 'success')
        except Exception:
            db.session.rollback()
            flash('Ошибка при удалении поста.', 'error')
    else:
        flash('У вас нет прав для удаления этого поста.', 'error')
        
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('home'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        language = request.form.get('language', 'ru')
        
        # Валидация данных
        if not username or not password:
            error = 'Имя пользователя и пароль обязательны для заполнения!'
        elif len(username) < 3:
            error = 'Имя пользователя должно содержать минимум 3 символа!'
        elif len(password) < 6:
            error = 'Пароль должен содержать минимум 6 символов!'
        elif User.query.filter_by(username=username).first():
            error = 'Пользователь с таким именем уже существует!'
        else:
            try:
                hashed_password = generate_password_hash(password)
                new_user = User(username=username, password=hashed_password, language=language)
                db.session.add(new_user)
                db.session.commit()
                
                session['username'] = username
                session['language'] = language
                flash('Регистрация прошла успешно! Добро пожаловать.', 'success')
                return redirect(url_for('home'))
            except Exception:
                db.session.rollback()
                error = 'Произошла ошибка при регистрации. Попробуйте позже.'
                
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            session['language'] = user.language
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('home'))
        else:
            error = 'Неверное имя пользователя или пароль!'
            
    return render_template('login.html', error=error)

@app.route('/switch_language', methods=['GET'])
def switch_language():
    lang = request.args.get('lang')
    if lang in ['ru', 'en']:
        session['language'] = lang
        # Если пользователь авторизован, обновляем язык и в БД
        if 'username' in session:
            user = User.query.filter_by(username=session['username']).first()
            if user:
                user.language = lang
                db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # В продакшене используйте gunicorn или waitress, а не debug=True
    app.run(debug=True, host='0.0.0.0', port=5000)
