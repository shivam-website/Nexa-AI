from flask import Flask, render_template, request, jsonify
import datetime
import webbrowser
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get API key for text generation (Nemo Mistral)
text_api_key = "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"

# In-memory chat history (shared for the session)
chat_memory = []
MAX_MEMORY = 100  # Store last 100 messages (user + assistant)

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
                "model": "mistralai/ministral-8b",
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
    return render_template('index.html')  # Your HTML page with a form to send queries

@app.route('/ask', methods=['POST'])
def handle_query():
    instruction = request.form.get('instruction', '').strip()
    response = None

    if instruction:
        # Handle fixed commands directly
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
            # Add user message to memory
            chat_memory.append({"role": "user", "content": instruction})
            if len(chat_memory) > MAX_MEMORY:
                chat_memory[:] = chat_memory[-MAX_MEMORY:]

            # Ask AI with full memory
            response_text = ask_ai_with_memory(chat_memory)

            # Add assistant's response to memory
            chat_memory.append({"role": "assistant", "content": response_text})
            if len(chat_memory) > MAX_MEMORY:
                chat_memory[:] = chat_memory[-MAX_MEMORY:]

            response = response_text

    if not response:
        return jsonify({"response": "Please provide a valid input"})

    return jsonify({"response": response.replace("\n", "\n\n")})

if __name__ == "__main__":
    app.run(debug=True)
