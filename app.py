import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_supersecretkey_change_me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки загрузки (Увеличили до 50 МБ для видео)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 МБ
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'webm'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# --- МОДЕЛИ ---
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
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete-orphan")

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)

# НОВАЯ МОДЕЛЬ: Creals (Видео)
class Creal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_filename = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    author = db.Column(db.String(80), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.relationship('CrealLike', backref='creal', lazy=True, cascade="all, delete-orphan")

class CrealLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creal_id = db.Column(db.Integer, db.ForeignKey('creal.id', ondelete='CASCADE'), nullable=False)

with app.app_context():
    db.create_all()

# --- ГЕНЕРАЦИЯ ТЕСТОВЫХ ДАННЫХ ---
def seed_test_data():
    with app.app_context():
        if User.query.count() == 0:
            # Создаем тестового пользователя
            test_user = User(
                username='tegcompany_admin',
                password=generate_password_hash('admin123'),
                language='ru',
                avatar_filename='default.png'
            )
            db.session.add(test_user)
            db.session.commit()

            # Создаем тестовый пост
            test_post = Post(
                title='Добро пожаловать в Creal! 🚀',
                content='Это первая тестовая запись. Платформа разработана командой Tegcompany для быстрого обмена идеями и контентом.',
                author='tegcompany_admin',
                category='news'
            )
            db.session.add(test_post)
            
            # Создаем тестовый "Creal" (используем заглушку, если реального видео нет)
            # В реальном сценарии здесь будет имя загруженного файла
            test_creal = Creal(
                video_filename='sample_video.mp4', 
                description='Первый тестовый Creal от команды разработки! #tegcompany #innovation',
                author='tegcompany_admin'
            )
            db.session.add(test_creal)
            db.session.commit()
            print("--- ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ ---")

seed_test_data()

# --- УТИЛИТЫ ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Сессия истекла. Войдите снова.'})
            flash('Для доступа к этой странице необходимо войти в систему.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- МАРШРУТЫ ---
@app.route('/')
@login_required 
def home():
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))
    all_posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('index.html', posts=all_posts, user=user)

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не выбран.'}) if is_ajax else redirect(url_for('home'))
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран.'}) if is_ajax else redirect(url_for('home'))
        
    if file and allowed_file(file.filename) and file.filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
        name, ext = os.path.splitext(secure_filename(file.filename))
        unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        user = User.query.filter_by(username=session['username']).first()
        user.avatar_filename = unique_filename
        db.session.commit()
        return jsonify({'success': True, 'message': 'Аватар обновлен!', 'avatar_url': url_for('static', filename=f'uploads/{unique_filename}')})
    return jsonify({'success': False, 'message': 'Недопустимый формат изображения.'})

@app.route('/add_post', methods=['POST'])
@login_required
def add_post():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if title and content:
        new_post = Post(title=title, content=content, author=session['username'])
        db.session.add(new_post)
        db.session.commit()
        return jsonify({
            'success': True, 'message': 'Пост опубликован!',
            'post': {'id': new_post.id, 'title': new_post.title, 'content': new_post.content, 'author': new_post.author, 'likes_count': 0}
        })
    return jsonify({'success': False, 'message': 'Заполните все поля.'})

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    user = User.query.filter_by(username=session['username']).first()
    existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        is_liked = False
    else:
        db.session.add(Like(user_id=user.id, post_id=post_id))
        is_liked = True
    db.session.commit()
    
    return jsonify({'success': True, 'likes_count': Like.query.filter_by(post_id=post_id).count(), 'is_liked': is_liked})

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author == session['username']:
        db.session.delete(post)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Пост удален.', 'post_id': post_id})
    return jsonify({'success': False, 'message': 'Нет прав.'})

# --- НОВЫЕ МАРШРУТЫ ДЛЯ CREALS ---
@app.route('/upload_creal', methods=['POST'])
@login_required
def upload_creal():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if 'video' not in request.files:
        return jsonify({'success': False, 'message': 'Видео не выбрано.'})
    
    file = request.files['video']
    desc = request.form.get('description', '').strip()
    
    if file and file.filename != '' and allowed_file(file.filename) and file.filename.rsplit('.', 1)[1].lower() in {'mp4', 'mov', 'webm'}:
        name, ext = os.path.splitext(secure_filename(file.filename))
        unique_filename = f"creal_{uuid.uuid4().hex[:8]}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        new_creal = Creal(video_filename=unique_filename, description=desc, author=session['username'])
        db.session.add(new_creal)
        db.session.commit()
        
        return jsonify({
            'success': True, 'message': 'Creal успешно опубликован!',
            'creal': {
                'id': new_creal.id,
                'video_url': url_for('static', filename=f'uploads/{unique_filename}'),
                'description': new_creal.description,
                'author': new_creal.author,
                'likes_count': 0
            }
        })
    return jsonify({'success': False, 'message': 'Ошибка загрузки. Разрешены только MP4, MOV, WEBM (до 50 МБ).'})

@app.route('/like_creal/<int:creal_id>', methods=['POST'])
@login_required
def like_creal(creal_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    user = User.query.filter_by(username=session['username']).first()
    existing_like = CrealLike.query.filter_by(user_id=user.id, creal_id=creal_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        is_liked = False
    else:
        db.session.add(CrealLike(user_id=user.id, creal_id=creal_id))
        is_liked = True
    db.session.commit()
    
    return jsonify({'success': True, 'likes_count': CrealLike.query.filter_by(creal_id=creal_id).count(), 'is_liked': is_liked})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        language = request.form.get('language', 'ru')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not username or not password: error = 'Заполните все поля!'
        elif len(username) < 3: error = 'Минимум 3 символа для имени!'
        elif len(password) < 6: error = 'Минимум 6 символов для пароля!'
        elif User.query.filter_by(username=username).first(): error = 'Имя занято!'
        else:
            db.session.add(User(username=username, password=generate_password_hash(password), language=language))
            db.session.commit()
            session['username'] = username
            session['language'] = language
            if is_ajax: return jsonify({'success': True, 'message': 'Успешно!', 'redirect_url': url_for('home')})
            return redirect(url_for('home'))
        if is_ajax: return jsonify({'success': False, 'message': error})
        return render_template('register.html', error=error)
    return render_template('register.html', error=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if user and check_password_hash(user.password, request.form.get('password', '')):
            session['username'] = user.username
            session['language'] = user.language
            if is_ajax: return jsonify({'success': True, 'message': 'Добро пожаловать!', 'redirect_url': url_for('home')})
            return redirect(url_for('home'))
        error = 'Неверный логин или пароль!'
        if is_ajax: return jsonify({'success': False, 'message': error})
        return render_template('login.html', error=error)
    return render_template('login.html', error=None)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
