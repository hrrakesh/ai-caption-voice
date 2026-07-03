import os
import base64
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'antigravity-secret-key-13579')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voice_caption_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# User Database Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    captions = db.relationship('CaptionHistory', backref='user', lazy=True, cascade='all, delete-orphan')

# Caption History Model
class CaptionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    audio_filename = db.Column(db.String(200), nullable=False)
    voice = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables helper
with app.app_context():
    db.create_all()

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
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

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

if __name__ == '__main__':
    app.run(debug=True)
