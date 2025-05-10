from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_dance.contrib.google import make_google_blueprint, google
from authlib.integrations.flask_client import OAuth
from PIL import Image
import pytesseract
import datetime
import webbrowser
import os
import json
import requests

app = Flask(__name__)
app.secret_key = "your_fallback_secret"

# ========== GOOGLE OAUTH ==========

google_bp = make_google_blueprint(
    client_id="978102306464-qdjll3uos10m1nd5gcnr9iql9688db58.apps.googleusercontent.com",
    client_secret="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",
    redirect_url="/google.login/google/authorized"
)
app.register_blueprint(google_bp, url_prefix="/google.login")

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

text_api_key = "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"

def ask_ai_with_memory(memory_messages):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {text_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistral/ministral-8b",
                "messages": memory_messages,
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        return f"API Error: {str(e)}"
    except KeyError:
        return "Unexpected response from AI API."

# ========== IMAGE GENERATION (Craiyon) ==========

def generate_image(prompt):
    url = "https://api.craiyon.com/generate"
    data = {"prompt": prompt}

    try:
        response = requests.post(url, json=data, timeout=30)
        if response.status_code == 200:
            images = response.json()['images']
            return images[0]
    except Exception as e:
        print(f"Image generation error: {e}")
    return None

@app.route('/generate_image', methods=['POST'])
def generate_image_route():
    prompt = request.form.get('prompt', '').strip()
    if not prompt:
        return jsonify({"response": "Please provide a valid prompt for image generation"})

    image_url = generate_image(prompt)
    if image_url:
        return jsonify({"image_url": image_url})
    return jsonify({"response": "Failed to generate image. Try again later."})

# ========== MAIN ROUTES ==========

@app.route('/')
def index():
    if 'user' not in session:
        return redirect('/login')
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def handle_query():
    instruction = request.form.get('instruction', '').strip()
    if not instruction:
        return jsonify({"response": "Please provide a valid input"})

    if 'your name' in instruction:
        response = "My name is JARVIS."
    elif 'shivam' in instruction:
        response = "MR. Shivam is my developer."
    elif 'date' in instruction:
        response = datetime.datetime.now().strftime('%B %d, %Y')
    elif 'open youtube' in instruction:
        webbrowser.open("https://youtube.com")
        response = "Opening YouTube"
    elif 'open google' in instruction:
        webbrowser.open("https://google.com")
        response = "Opening Google"
    elif 'play music' in instruction:
        webbrowser.open("https://youtu.be/IrZC5H5ZSm8?si=SWddD_ohU8xW65Lw")
        response = "Playing music"
    else:
        chat_memory.append({"role": "user", "content": instruction})
        if len(chat_memory) > MAX_MEMORY:
            chat_memory[:] = chat_memory[-MAX_MEMORY:]

        ai_response = ask_ai_with_memory(chat_memory)
        chat_memory.append({"role": "assistant", "content": ai_response})
        response = ai_response

    return jsonify({"response": response.replace("\n", "\n\n")})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"response": "No image uploaded"})

    image = request.files['image']
    if image.filename == '':
        return jsonify({"response": "No image selected"})

    # Save image to disk temporarily
    os.makedirs("uploads", exist_ok=True)
    image_path = os.path.join("uploads", image.filename)
    image.save(image_path)

    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        os.remove(image_path)

        chat_memory.append({"role": "user", "content": text})
        if len(chat_memory) > MAX_MEMORY:
            chat_memory[:] = chat_memory[-MAX_MEMORY:]

        ai_response = ask_ai_with_memory(chat_memory)
        chat_memory.append({"role": "assistant", "content": ai_response})

        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"response": f"Error processing image: {str(e)}"})

# ========== AUTH ROUTES ==========

@app.route('/login')
def login():
    if google.authorized:
        user_info = google.get('/oauth2/v2/userinfo')
        if user_info.ok:
            session['user'] = user_info.json().get('email')
            return redirect('/')
    elif 'microsoft_token' in session:
        return redirect('/')
    return render_template('index.html')

@app.route('/google_login/authorized')
def google_login_authorized():
    if not google.authorized:
        return redirect(url_for("login"))

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        session['user'] = resp.json().get("email")
        return redirect('/')
    return redirect(url_for('login'))

@app.route('/microsoft_login')
def microsoft_login():
    redirect_uri = url_for('microsoft_authorize', _external=True)
    return microsoft.authorize_redirect(redirect_uri)

@app.route('/microsoft_authorize')
def microsoft_authorize():
    token = microsoft.authorize_access_token()
    user = microsoft.get('me').json()
    session['user'] = user['userPrincipalName']
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# ========== MAIN ==========

if __name__ == "__main__":
    app.run(debug=True)
