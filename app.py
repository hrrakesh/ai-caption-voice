import os
import base64
import uuid
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from sqlalchemy import text, inspect
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'antigravity-secret-key-13579')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voice_caption_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# =========================================================================
# HARDCODED ADMIN CREDENTIALS CONFIGURATION
# To change the admin username or password, modify these two lines directly:
# =========================================================================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123"
# =========================================================================

# Configure upload paths
UPLOAD_FOLDER = os.path.join('static', 'uploads')
IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, 'images')
AUDIO_FOLDER = os.path.join(UPLOAD_FOLDER, 'audio')

# Ensure folders exist
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.init_app(app)

# Initialize OpenAI Client (will check for API key when requests are made)
def get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure OPENAI_API_KEY in your environment or .env file.")
    return OpenAI(api_key=api_key)

# =========================================================================
# TIMEZONE CONFIGURATION (Indian Standard Time: UTC+05:30)
# =========================================================================
IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    """Convert naive (assumed UTC) or timezone-aware datetime to IST."""
    if not dt:
        return None
    if getattr(dt, 'tzinfo', None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def format_ist(dt, fmt='%Y-%m-%d %H:%M'):
    """Convert datetime to IST and format as string."""
    if not dt:
        return 'N/A'
    ist_dt = to_ist(dt)
    return ist_dt.strftime(fmt)

@app.template_filter('to_ist')
def jinja_to_ist(dt, fmt='%Y-%m-%d %H:%M'):
    """Jinja template filter to format any datetime into IST."""
    if not dt:
        return 'N/A'
    return format_ist(dt, fmt)

# User Database Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    captions = db.relationship('CaptionHistory', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'is_admin': bool(self.is_admin),
            'created_at': format_ist(self.created_at, '%Y-%m-%d %H:%M') + ' IST' if self.created_at else 'N/A',
            'last_login': format_ist(self.last_login, '%Y-%m-%d %H:%M') + ' IST' if self.last_login else 'Never',
            'caption_count': len(self.captions)
        }

# Caption History Model
class CaptionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    audio_filename = db.Column(db.String(200), nullable=False)
    voice = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'image_filename': self.image_filename,
            'caption': self.caption,
            'audio_filename': self.audio_filename,
            'voice': self.voice,
            'timestamp': format_ist(self.timestamp, '%Y-%m-%d %H:%M') + ' IST' if self.timestamp else 'N/A'
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin Access Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in with administrator credentials.', 'warning')
            return redirect(url_for('admin_login'))
        if not getattr(current_user, 'is_admin', False):
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Utility Helpers
def format_file_size(bytes_size):
    if bytes_size is None or bytes_size < 0:
        return "0 B"
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"

def get_folder_size(folder_path):
    total = 0
    file_count = 0
    if os.path.exists(folder_path):
        for entry in os.scandir(folder_path):
            if entry.is_file() and not entry.name.startswith('.'):
                total += entry.stat().st_size
                file_count += 1
    return total, file_count

def get_user_storage_usage(user_id):
    captions = CaptionHistory.query.filter_by(user_id=user_id).all()
    total_bytes = 0
    for cap in captions:
        img_path = os.path.join(IMAGE_FOLDER, cap.image_filename)
        audio_path = os.path.join(AUDIO_FOLDER, cap.audio_filename)
        if os.path.exists(img_path):
            total_bytes += os.path.getsize(img_path)
        if os.path.exists(audio_path):
            total_bytes += os.path.getsize(audio_path)
    return total_bytes

# Database Migration & Admin Seeding Helper
def init_db():
    with app.app_context():
        db.create_all()
        # Safe migration for existing SQLite databases
        try:
            insp = inspect(db.engine)
            if 'user' in insp.get_table_names():
                existing_cols = [c['name'] for c in insp.get_columns('user')]
                with db.engine.connect() as conn:
                    if 'is_admin' not in existing_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                    if 'created_at' not in existing_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME"))
                    if 'last_login' not in existing_cols:
                        conn.execute(text("ALTER TABLE user ADD COLUMN last_login DATETIME"))
                    conn.commit()
        except Exception as e:
            print(f"Migration note: {e}")

        # Ensure Admin user exists with ADMIN_USERNAME and ADMIN_PASSWORD
        try:
            admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
            if not admin_user:
                admin_user = User(
                    username=ADMIN_USERNAME,
                    password_hash=generate_password_hash(ADMIN_PASSWORD),
                    is_admin=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(admin_user)
                db.session.commit()
                print(f"Default admin created: {ADMIN_USERNAME}")
            else:
                admin_user.is_admin = True
                # Automatically sync password in database if ADMIN_PASSWORD was changed in app.py
                if not check_password_hash(admin_user.password_hash, ADMIN_PASSWORD):
                    admin_user.password_hash = generate_password_hash(ADMIN_PASSWORD)
                    print(f"Admin password updated to match app.py ADMIN_PASSWORD")
                if not admin_user.created_at:
                    admin_user.created_at = datetime.utcnow()
                db.session.commit()

            # Fill missing created_at for legacy users
            null_users = User.query.filter(User.created_at == None).all()
            for u in null_users:
                u.created_at = datetime.utcnow()
            if null_users:
                db.session.commit()
        except Exception as e:
            print(f"Admin seeding error: {e}")

# Initialize DB on load
init_db()

# Helper: Encode local image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Routes
@app.route('/')
@login_required
def index():
    # Fetch history for current user ordered by most recent
    history = CaptionHistory.query.filter_by(user_id=current_user.id).order_by(CaptionHistory.timestamp.desc()).all()
    return render_template('index.html', history=history)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if getattr(current_user, 'is_admin', False):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        # Check authentication (strict match with ADMIN_PASSWORD if hardcoded admin username)
        if user and username == ADMIN_USERNAME:
            if password == ADMIN_PASSWORD:
                password_matches = True
                user.is_admin = True
                if not check_password_hash(user.password_hash, ADMIN_PASSWORD):
                    user.password_hash = generate_password_hash(ADMIN_PASSWORD)
            else:
                password_matches = False
        else:
            password_matches = bool(user and check_password_hash(user.password_hash, password))
        
        if user and password_matches:
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            flash(f'Successfully logged in! Welcome, {user.username}.', 'success')
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if getattr(current_user, 'is_admin', False):
            return redirect(url_for('admin_dashboard'))
        flash('You are logged in as a standard user. Administrator privileges required.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        # Check authentication (strict match with ADMIN_PASSWORD if hardcoded admin username)
        if user and username == ADMIN_USERNAME:
            if password == ADMIN_PASSWORD:
                password_matches = True
                user.is_admin = True
                if not check_password_hash(user.password_hash, ADMIN_PASSWORD):
                    user.password_hash = generate_password_hash(ADMIN_PASSWORD)
            else:
                password_matches = False
        else:
            password_matches = bool(user and check_password_hash(user.password_hash, password))

        if user and password_matches:
            if user.is_admin:
                user.last_login = datetime.utcnow()
                db.session.commit()
                login_user(user)
                flash('Welcome to the Admin Dashboard!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Access denied. This user does not have administrator privileges.', 'danger')
        else:
            flash('Invalid administrator credentials.', 'danger')

    return render_template('admin_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
            
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')
            
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded'}), 400
        
    file = request.files['image']
    voice = request.form.get('voice', 'alloy')
    custom_prompt = request.form.get('custom_prompt', '').strip()
    
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
        
    try:
        # 1. Initialize OpenAI client (checks API key)
        client = get_openai_client()
        
        # 2. Save Image File
        unique_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            # Default to png if no recognized extension
            ext = '.png'
        
        image_filename = f"{unique_id}{ext}"
        image_path = os.path.join(IMAGE_FOLDER, image_filename)
        file.save(image_path)
        
        # 3. Base64 Encode Image
        base64_image = encode_image(image_path)
        
        # Determine image mime type
        mime_type = "image/jpeg"
        if ext == '.png':
            mime_type = "image/png"
        elif ext == '.webp':
            mime_type = "image/webp"
            
        # 4. Generate Caption using GPT-4o-mini (Vision)
        system_instruction = (
            "You are a descriptive AI assistant. Describe the uploaded image. "
            "Your description should be extremely descriptive, capturing the key elements, "
            "vibe, mood, and color palette. Write 1 or 2 paragraphs. "
            "CRITICAL: Do NOT use markdown like bold (* or **), headers, or bullet points, "
            "as your description will be read aloud by an TTS voiceover tool. Make it flow naturally "
            "as spoken speech."
        )
        
        prompt_text = "Describe this image in detail for a voiceover."
        if custom_prompt:
            prompt_text += f" Focus on: {custom_prompt}"
            
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        
        caption = response.choices[0].message.content.strip()
        
        # 5. Generate Voiceover using OpenAI TTS
        audio_filename = f"{unique_id}.mp3"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        
        tts_response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=caption
        )
        
        # Stream the audio response and write to file
        tts_response.stream_to_file(audio_path)
        
        # 6. Save to History
        history_item = CaptionHistory(
            user_id=current_user.id,
            image_filename=image_filename,
            caption=caption,
            audio_filename=audio_filename,
            voice=voice
        )
        db.session.add(history_item)
        db.session.commit()
        
        return jsonify({
            'id': history_item.id,
            'caption': caption,
            'image_filename': image_filename,
            'audio_filename': audio_filename,
            'voice': voice
        })
        
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"Processing failed: {str(e)}"}), 500

@app.route('/history/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_history(item_id):
    item = CaptionHistory.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({'error': 'Record not found or access denied'}), 404
        
    try:
        # Delete associated files
        image_path = os.path.join(IMAGE_FOLDER, item.image_filename)
        audio_path = os.path.join(AUDIO_FOLDER, item.audio_filename)
        
        if os.path.exists(image_path):
            os.remove(image_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f"Failed to delete: {str(e)}"}), 500

# ==========================================
# ADMIN DASHBOARD & MANAGEMENT ROUTES
# ==========================================

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # 1. Fetch Users
    users = User.query.order_by(User.id.asc()).all()
    total_users = len(users)
    admin_count = sum(1 for u in users if u.is_admin)
    regular_count = total_users - admin_count
    
    # 2. Fetch Captions & Voiceovers
    all_captions = CaptionHistory.query.order_by(CaptionHistory.timestamp.desc()).all()
    total_generations = len(all_captions)
    
    # 3. Storage Calculations
    img_bytes, img_count = get_folder_size(IMAGE_FOLDER)
    audio_bytes, audio_count = get_folder_size(AUDIO_FOLDER)
    total_storage_bytes = img_bytes + audio_bytes
    
    db_path = os.path.join(app.instance_path, 'voice_caption_app.db')
    db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    
    # 4. Voice Analytics
    voices_list = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
    voice_counts = {v: 0 for v in voices_list}
    for cap in all_captions:
        v_name = cap.voice.lower() if cap.voice else 'alloy'
        if v_name in voice_counts:
            voice_counts[v_name] += 1
        else:
            voice_counts[v_name] = voice_counts.get(v_name, 0) + 1
            
    top_voice_item = max(voice_counts.items(), key=lambda x: x[1]) if voice_counts and total_generations > 0 else ('None', 0)
    top_voice = {
        'name': top_voice_item[0].capitalize() if top_voice_item[1] > 0 else 'N/A',
        'count': top_voice_item[1],
        'percentage': round((top_voice_item[1] / total_generations * 100), 1) if total_generations > 0 else 0
    }
    
    voice_stats = []
    for v in voices_list:
        cnt = voice_counts.get(v, 0)
        pct = round((cnt / total_generations * 100), 1) if total_generations > 0 else 0
        voice_stats.append({
            'name': v.capitalize(),
            'slug': v,
            'count': cnt,
            'percentage': pct
        })
    
    # 5. Enriched Users List
    user_data = []
    active_creators = 0
    for u in users:
        u_caps = u.captions
        gen_count = len(u_caps)
        if gen_count > 0:
            active_creators += 1
            
        user_bytes = 0
        for c in u_caps:
            ipath = os.path.join(IMAGE_FOLDER, c.image_filename)
            apath = os.path.join(AUDIO_FOLDER, c.audio_filename)
            if os.path.exists(ipath):
                user_bytes += os.path.getsize(ipath)
            if os.path.exists(apath):
                user_bytes += os.path.getsize(apath)
                
        latest_cap = max(u_caps, key=lambda c: c.timestamp) if u_caps else None
        
        user_data.append({
            'id': u.id,
            'username': u.username,
            'is_admin': bool(u.is_admin),
            'created_at': u.created_at,
            'last_login': u.last_login,
            'generation_count': gen_count,
            'storage_bytes': user_bytes,
            'storage_formatted': format_file_size(user_bytes),
            'latest_generation': latest_cap.timestamp if latest_cap else None
        })
        
    stats = {
        'total_users': total_users,
        'admin_count': admin_count,
        'regular_count': regular_count,
        'active_creators': active_creators,
        'total_generations': total_generations,
        'total_storage_formatted': format_file_size(total_storage_bytes),
        'total_storage_bytes': total_storage_bytes,
        'img_count': img_count,
        'img_size_formatted': format_file_size(img_bytes),
        'audio_count': audio_count,
        'audio_size_formatted': format_file_size(audio_bytes),
        'db_size_formatted': format_file_size(db_size_bytes),
        'top_voice': top_voice,
        'openai_configured': bool(os.environ.get("OPENAI_API_KEY"))
    }
    
    current_ist_time = datetime.now(IST).strftime('%b %d, %Y, %I:%M:%S %p')
    
    return render_template('admin.html',
                           users=user_data,
                           captions=all_captions,
                           stats=stats,
                           voice_stats=voice_stats,
                           current_ist_time=current_ist_time)

@app.route('/admin/api/user/<int:user_id>')
@admin_required
def admin_api_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    captions = CaptionHistory.query.filter_by(user_id=user.id).order_by(CaptionHistory.timestamp.desc()).all()
    
    total_bytes = 0
    cap_data = []
    for c in captions:
        ipath = os.path.join(IMAGE_FOLDER, c.image_filename)
        apath = os.path.join(AUDIO_FOLDER, c.audio_filename)
        isize = os.path.getsize(ipath) if os.path.exists(ipath) else 0
        asize = os.path.getsize(apath) if os.path.exists(apath) else 0
        total_bytes += (isize + asize)
        
        cap_data.append({
            'id': c.id,
            'image_url': url_for('static', filename='uploads/images/' + c.image_filename),
            'audio_url': url_for('static', filename='uploads/audio/' + c.audio_filename),
            'caption': c.caption,
            'voice': c.voice.capitalize() if c.voice else 'Alloy',
            'timestamp': format_ist(c.timestamp, '%Y-%m-%d %I:%M %p') + ' IST' if c.timestamp else 'N/A',
            'size_formatted': format_file_size(isize + asize)
        })
        
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'is_admin': bool(user.is_admin),
            'created_at': format_ist(user.created_at, '%b %d, %Y %I:%M %p') + ' IST' if user.created_at else 'N/A',
            'last_login': format_ist(user.last_login, '%b %d, %Y %I:%M %p') + ' IST' if user.last_login else 'Never',
            'total_generations': len(captions),
            'total_storage_formatted': format_file_size(total_bytes)
        },
        'generations': cap_data
    })

@app.route('/admin/api/users/create', methods=['POST'])
@admin_required
def admin_create_user():
    data = request.get_json(silent=True) or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    is_admin_raw = data.get('is_admin')
    is_admin = str(is_admin_raw).lower() in ['true', '1', 'on', 'yes']
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({'error': f'Username "{username}" is already taken.'}), 400
        
    new_user = User(
        username=username,
        password_hash=generate_password_hash(password),
        is_admin=is_admin,
        created_at=datetime.utcnow()
    )
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'User "{username}" created successfully.',
        'user': new_user.to_dict()
    })

@app.route('/admin/api/users/<int:user_id>/update', methods=['POST'])
@admin_required
def admin_update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or request.form
    
    new_username = data.get('username', '').strip()
    new_password = data.get('password', '').strip()
    is_admin_raw = data.get('is_admin')
    
    if new_username and new_username != user.username:
        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != user.id:
            return jsonify({'error': f'Username "{new_username}" is already taken.'}), 400
        user.username = new_username
        
    if new_password:
        user.password_hash = generate_password_hash(new_password)
        
    if is_admin_raw is not None:
        flag = str(is_admin_raw).lower() in ['true', '1', 'on', 'yes']
        if user.id == current_user.id and not flag:
            return jsonify({'error': 'You cannot remove admin privileges from your own account.'}), 400
        user.is_admin = flag
        
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'User "{user.username}" updated successfully.',
        'user': user.to_dict()
    })

@app.route('/admin/api/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'You cannot remove admin privileges from your own account.'}), 400
        
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify({
        'success': True,
        'is_admin': bool(user.is_admin),
        'message': f'Updated role for "{user.username}" to {"Administrator" if user.is_admin else "Standard User"}.'
    })

@app.route('/admin/api/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'You cannot delete your own account while logged in.'}), 400
        
    username = user.username
    try:
        # Delete user's files
        for cap in user.captions:
            img_path = os.path.join(IMAGE_FOLDER, cap.image_filename)
            audio_path = os.path.join(AUDIO_FOLDER, cap.audio_filename)
            if os.path.exists(img_path):
                os.remove(img_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
        db.session.delete(user)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'User "{username}" and all associated data have been permanently deleted.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete user: {str(e)}'}), 500

@app.route('/admin/api/generations/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_delete_generation(item_id):
    cap = CaptionHistory.query.get_or_404(item_id)
    try:
        img_path = os.path.join(IMAGE_FOLDER, cap.image_filename)
        audio_path = os.path.join(AUDIO_FOLDER, cap.audio_filename)
        if os.path.exists(img_path):
            os.remove(img_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        db.session.delete(cap)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Generation record deleted successfully.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete generation: {str(e)}'}), 500

@app.route('/admin/api/system/cleanup-orphaned', methods=['POST'])
@admin_required
def admin_cleanup_orphaned():
    try:
        valid_images = {c.image_filename for c in CaptionHistory.query.all()}
        valid_audio = {c.audio_filename for c in CaptionHistory.query.all()}
        
        deleted_count = 0
        freed_bytes = 0
        
        if os.path.exists(IMAGE_FOLDER):
            for entry in os.scandir(IMAGE_FOLDER):
                if entry.is_file() and not entry.name.startswith('.') and entry.name not in valid_images:
                    freed_bytes += entry.stat().st_size
                    os.remove(entry.path)
                    deleted_count += 1
                    
        if os.path.exists(AUDIO_FOLDER):
            for entry in os.scandir(AUDIO_FOLDER):
                if entry.is_file() and not entry.name.startswith('.') and entry.name not in valid_audio:
                    freed_bytes += entry.stat().st_size
                    os.remove(entry.path)
                    deleted_count += 1
                    
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'freed_formatted': format_file_size(freed_bytes),
            'message': f'Cleaned up {deleted_count} orphaned files ({format_file_size(freed_bytes)} freed).'
        })
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
