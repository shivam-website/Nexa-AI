from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_dance.contrib.google import make_google_blueprint, google
from authlib.integrations.flask_client import OAuth
from PIL import Image
import pytesseract
import os
import json
import requests

app = Flask(__name__)
app.secret_key = "your_fallback_secret"

HUGGINGFACE_API_KEY = os.getenv()

# ========== GOOGLE OAUTH ==========
google_bp = make_google_blueprint(
    client_id="978102306464-qdjll3uos10m1nd5gcnr9iql9688db58.apps.googleusercontent.com",
    client_secret="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",
    redirect_url="/google_login/authorized"
)
app.register_blueprint(google_bp, url_prefix="/google_login")

# ========== MICROSOFT OAUTH ==========
oauth = OAuth(app)
microsoft = oauth.register(
    name='microsoft',
    client_id="your_microsoft_client_id",
    client_secret="your_microsoft_client_secret",
    access_token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
    authorize_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
    api_base_url='https://graph.microsoft.com/v1.0/',
    client_kwargs={'scope': 'User.Read'}
)

# ========== CHAT MEMORY ==========
chat_memory = []
MAX_MEMORY = 100

# ========== USER DATABASE ==========
def load_users():
    if os.path.exists("users.json"):
        with open("users.json") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)

# ========== AI CHAT (OpenRouter + Mistral) ==========

load_dotenv()  # take environment variables from .env.

api_key = os.getenv('TEXT_API_KEY')
def ask_ai_with_memory(memory_messages):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistral/ministral-8b",  # Fixed typo in model name
                "messages": memory_messages,
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        # Debug log for AI response
        app.logger.debug(f"AI response data: {data}")
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        return "⚠️ No response from AI. Please try again."
    except requests.exceptions.RequestException as e:
        return f"⚠️ API Error: {str(e)}"
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"

# ========== ROUTES ==========

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def handle_query():
    instruction = request.form.get('instruction', '').strip()
    if not instruction:
        return jsonify({"response": "Please provide a valid input"})

    # Append user message
    chat_memory.append({"role": "user", "content": instruction})
    if len(chat_memory) > MAX_MEMORY:
        chat_memory[:] = chat_memory[-MAX_MEMORY:]

    ai_response = ask_ai_with_memory(chat_memory)
    chat_memory.append({"role": "assistant", "content": ai_response})

    return jsonify({"response": ai_response})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"response": "No image uploaded"})
    image = request.files['image']
    if image.filename == '':
        return jsonify({"response": "No image selected"})
    try:
        os.makedirs("uploads", exist_ok=True)
        image_path = os.path.join("uploads", image.filename)
        image.save(image_path)

        text = pytesseract.image_to_string(Image.open(image_path))
        os.remove(image_path)

        if not text.strip():
            return jsonify({"response": "No text found in the image."})

        # Add extracted text to chat memory and get AI response
        chat_memory.append({"role": "user", "content": text})
        if len(chat_memory) > MAX_MEMORY:
            chat_memory[:] = chat_memory[-MAX_MEMORY:]
        ai_response = ask_ai_with_memory(chat_memory)
        chat_memory.append({"role": "assistant", "content": ai_response})

        return jsonify({"response": ai_response})

    except Exception as e:
        return jsonify({"response": f"Error processing image: {str(e)}"})

# ========== AUTH ROUTES ==========

@app.route('/google_login/authorized')
def google_login_authorized():
    if not google.authorized:
        return redirect(url_for("login"))
    user_info = google.get("/oauth2/v2/userinfo")
    if user_info.ok:
        session['user'] = user_info.json().get("email")
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    if google.authorized:
        user_info = google.get('/oauth2/v2/userinfo')
        if user_info.ok:
            session['user'] = user_info.json().get('email')
            return redirect(url_for('index'))
    elif 'microsoft_token' in session:
        return redirect(url_for('index'))
    return render_template('index.html')  # Login page

@app.route('/start_new_chat', methods=['POST'])
def start_new_chat():
    global chat_memory
    chat_memory = []  # Clear chat memory
    return jsonify({"response": "New chat started. How can I assist you today?"})

@app.route('/google-login')
def google_login():
    # Trigger Google OAuth flow
    return google.authorize(callback=url_for('google_login_authorized', _external=True))

@app.route('/microsoft_login')
def microsoft_login():
    redirect_uri = url_for('microsoft_authorize', _external=True)
    return microsoft.authorize_redirect(redirect_uri)

@app.route('/microsoft_authorize')
def microsoft_authorize():
    token = microsoft.authorize_access_token()
    user = microsoft.get('me').json()
    session['user'] = user.get('userPrincipalName')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# ========== MAIN ==========

if __name__ == "__main__":
    # Use debug=True only for development, consider removing it in production
    app.run(debug=True)
