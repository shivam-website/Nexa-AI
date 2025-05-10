from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import datetime
import webbrowser
import requests

app = Flask(__name__)
CORS(app)  # ✅ Enable CORS so frontend can talk to backend from other domains

# Hardcoded API key for text generation (Nemo Mistral)
text_api_key = "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"

# In-memory chat history
chat_memory = []
MAX_MEMORY = 100

# Function to query the Nemo Mistral API with memory
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
        return "Error processing API response"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def handle_query():
    instruction = request.form.get('instruction', '').strip()
    response = None

    if instruction:
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

            response_text = ask_ai_with_memory(chat_memory)
            chat_memory.append({"role": "assistant", "content": response_text})
            if len(chat_memory) > MAX_MEMORY:
                chat_memory[:] = chat_memory[-MAX_MEMORY:]

            response = response_text

    if not response:
        return jsonify({"response": "Please provide a valid input"})

    return jsonify({"response": response.replace("\n", "\n\n")})



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
