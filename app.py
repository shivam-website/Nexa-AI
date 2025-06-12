from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_dance.contrib.google import make_google_blueprint, google
from authlib.integrations.flask_client import OAuth
from PIL import Image
import pytesseract
import os
import json
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "your_fallback_secret_key_here"

# API Configuration
GEMINI_API_KEY = "AIzaSyDQJcS5wwBi65AdfW5zHT2ayu1ShWgWcJg"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# OAuth Setup
google_bp = make_google_blueprint(
    client_id="978102306464-qdjll3uos10m1nd5gcnr9iql9688db58.apps.googleusercontent.com",
    client_secret="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",
    redirect_url="/google_login/authorized",
    scope=["profile", "email"]
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

# Chat Memory Management
chat_memory = []
MAX_MEMORY = 100
MIN_RESPONSE_LENGTH = 150  # Minimum words for a satisfactory response

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
        # Enhanced system instruction for detailed responses
        system_instruction = (
            "You are Aivora AI, a highly knowledgeable and articulate assistant. "
            "Provide comprehensive, detailed responses that thoroughly address the user's needs. "
            "Structure your answers with clear organization: "
            "1. Start with a concise direct answer "
            "2. Provide detailed explanations "
            "3. Include relevant examples or analogies "
            "4. Offer additional context when helpful "
            "For technical questions, provide complete code examples with explanations. "
            "For subjective questions, present multiple perspectives. "
            "Use markdown formatting for better readability (``` for code, **bold** for emphasis)."
        )
        
        # Format conversation history effectively
        conversation_history = "\n".join([
            f"{m['role'].capitalize()}: {m['content']}" 
            for m in memory_messages[-6:]  # Keep recent context
        ])
        
        # Configure for longer, high-quality responses
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=4000,
            temperature=0.7,
            top_p=0.9,
            top_k=40
        )
        
        response = model.generate_content(
            system_instruction + "\n\nCurrent conversation:\n" + conversation_history,
            generation_config=generation_config
        )
        
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Error generating response: {str(e)}"

def ensure_response_quality(response, memory_messages):
    """Ensure responses meet minimum quality standards"""
    if len(response.split()) < MIN_RESPONSE_LENGTH and not any(
        kw in response.lower() for kw in ['code', 'error', 'sorry']
    ):
        follow_up = (
            "Please expand your previous answer with: "
            "1. More detailed explanations "
            "2. Practical examples "
            "3. Relevant context "
            "4. Any helpful analogies"
        )
        enhanced_response = ask_ai_with_memory(
            memory_messages + [{"role": "user", "content": follow_up}]
        )
        return enhanced_response
    return response

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', chat_memory=chat_memory)

@app.route('/ask', methods=['POST'])
def handle_query():
    instruction = request.form.get('instruction', '').strip()
    if not instruction:
        return jsonify({"response": "Please provide a valid input"})

    chat_memory.append({"role": "user", "content": instruction})
    if len(chat_memory) > MAX_MEMORY:
        # Smart memory management - summarize older messages
        summary_prompt = (
            "Summarize this conversation history preserving key technical details, "
            "user preferences, and important context in 3-4 concise paragraphs:"
        )
        old_messages = "\n".join([m['content'] for m in chat_memory[:-50]])
        chat_memory[:] = [
            {"role": "assistant", "content": ask_ai_with_memory([
                {"role": "user", "content": f"{summary_prompt}\n{old_messages}"}
            ])}
        ] + chat_memory[-50:]

    ai_response = ask_ai_with_memory(chat_memory)
    ai_response = ensure_response_quality(ai_response, chat_memory)
    chat_memory.append({"role": "assistant", "content": ai_response})
    
    return jsonify({
        "response": ai_response,
        "memory_length": len(chat_memory)
    })

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

        chat_memory.append({"role": "user", "content": f"Extracted text from image:\n{text}"})
        ai_response = ask_ai_with_memory(chat_memory)
        ai_response = ensure_response_quality(ai_response, chat_memory)
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
        session['user'] = user_info.json()
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    if google.authorized:
        user_info = google.get('/oauth2/v2/userinfo')
        if user_info.ok:
            session['user'] = user_info.json()
            return redirect(url_for('index'))
    elif 'microsoft_token' in session:
        return redirect(url_for('index'))
    return render_template('index.html')

@app.route('/start_new_chat', methods=['POST'])
def start_new_chat():
    global chat_memory
    # Save important context before clearing
    if len(chat_memory) > 3:
        summary = ask_ai_with_memory([{
            "role": "user", 
            "content": "Summarize key user preferences and context from this conversation in one paragraph"
        }])
        chat_memory = [{"role": "assistant", "content": summary}]
    else:
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
    session['user'] = user
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
