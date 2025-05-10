import os
import datetime
import webbrowser
import requests
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # ✅ Enable CORS so frontend can talk to backend from other domains

# Hardcoded API key for Qwen3 (you can replace this with your actual key)
text_api_key = "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"

# In-memory chat history
chat_memory = []
MAX_MEMORY = 100

# Function to query the Qwen3 API with memory
def ask_ai_with_memory(memory_messages, text_api_key):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {text_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.5-pro-preview",  # Updated model for Qwen3-30b-a3b
                "messages": memory_messages,
                "temperature": 0.7
            },
            timeout=30
        )
        # Check if the response was successful
        response.raise_for_status()

        # Parse and return the content of the response
        return response.json()["choices"][0]["message"]["content"].strip()

    except requests.exceptions.HTTPError as http_err:
        # Specifically handle Unauthorized (401)
        if http_err.response.status_code == 401:
            return "Unauthorized: Please check your API key."
        # Handle other HTTP errors (e.g., 404, 500)
        return f"HTTP Error: {http_err.response.status_code} - {http_err.response.text}"

    except requests.exceptions.RequestException as req_err:
        # General request errors (e.g., timeout, connection error)
        return f"API Error: {str(req_err)}"
    
    except KeyError:
        # In case the response format changes or is unexpected
        return "Error processing API response. The response format may have changed."


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

            response_text = ask_ai_with_memory(chat_memory, text_api_key)
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
