from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_dance.contrib.google import make_google_blueprint, google
from authlib.integrations.flask_client import OAuth
from PIL import Image
import pytesseract
import os
import json
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "your_fallback_secret"

# API KEYS
GEMINI_API_KEY = "AIzaSyDQJcS5wwBi65AdfW5zHT2ayu1ShWgWcJg"
HUGGINGFACE_API_KEY = os.getenv

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

google_bp = make_google_blueprint(
    client_id="978102306464-qdjll3uos10m1nd5gcnr9iql9688db58.apps.googleusercontent.com",
    client_secret="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",
    redirect_url="/google_login/authorized"
)
app.register_blueprint(google_bp, url_prefix="/google_login")

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

chat_memory = []
MAX_MEMORY = 100

def load_users():
    if os.path.exists("users.json"):
        with open("users.json") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)

def ask_ai_with_memory(memory_messages):
    try:
        system_instruction = (
            "You are a helpful, clear, and concise assistant. "
            "Answer naturally like a friendly expert. "
            "If asked for code, reply with only the relevant code and minimal comments. "
            "If asked a question, keep answers short and direct without long explanations."
        )
        full_prompt = system_instruction + "\n" + "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in memory_messages])
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Gemini SDK error: {str(e)}"

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

    chat_memory.append({"role": "user", "content": instruction})
    if len(chat_memory) > MAX_MEMORY:
        chat_memory[:] = chat_memory[-MAX_MEMORY:]

    ai_response = ask_ai_with_memory(chat_memory)
    chat_memory.append({"role": "assistant", "content": ai_response})
    return jsonify({"response": ai_response})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files or request.files['image'].filename == '':
        return jsonify({"response": "No image uploaded or selected"})

    image = request.files['image']
    try:
        os.makedirs("uploads", exist_ok=True)
        image_path = os.path.join("uploads", image.filename)
        image.save(image_path)

        text = pytesseract.image_to_string(Image.open(image_path))
        os.remove(image_path)

        if not text.strip():
            return jsonify({"response": "No text found in the image."})

        chat_memory.append({"role": "user", "content": text})
        if len(chat_memory) > MAX_MEMORY:
            chat_memory[:] = chat_memory[-MAX_MEMORY:]

        ai_response = ask_ai_with_memory(chat_memory)
        chat_memory.append({"role": "assistant", "content": ai_response})

        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"response": f"Error processing image: {str(e)}"})

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
    return render_template('index.html')

@app.route('/start_new_chat', methods=['POST'])
def start_new_chat():
    global chat_memory
    chat_memory = []
    return jsonify({"response": "New chat started. How can I assist you today?"})

@app.route('/google-login')
def google_login():
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

if __name__ == "__main__":
    app.run(debug=True)
