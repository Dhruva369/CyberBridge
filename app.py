from flask import Flask, request, jsonify, render_template, session
import requests
from langdetect import detect
import json
import os
import re
import markdown  # New import
from bleach.sanitizer import Cleaner  # New import for HTML sanitization

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')  # Needed for session storage

def load_emergency_contacts():
    with open(os.path.join(os.path.dirname(__file__), 'data', 'emergency_contacts.json'), 'r') as f:
        return json.load(f)

EMERGENCY_CONTACTS = load_emergency_contacts()

API_KEY = os.environ.get('API_KEY')  # Replace with your actual API key
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Limit conversation history size
MAX_HISTORY = 10  

def format_response(response):
    # First pass - clean basic markdown artifacts
    response = response.replace("__", "").replace("`", "")
    
    lines = response.split('\n')
    html_lines = []
    in_list = False
    in_ordered_list = False
    
    for line in lines:
        stripped = line.strip()
        
        # Handle numbered headers with bold text (e.g., "1. **Contact Local Law Enforcement**")
        numbered_header_match = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', stripped)
        if numbered_header_match:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            html_lines.append(f'<h3>{numbered_header_match.group(2)}</h3>')
            continue
            
        # Handle regular markdown headers
        elif stripped.startswith('###'):
            html_lines.append(f'<h3>{stripped[4:]}</h3>')
        elif stripped.startswith('##'):
            html_lines.append(f'<h2>{stripped[3:]}</h2>')
        elif stripped.startswith('#'):
            html_lines.append(f'<h1>{stripped[2:]}</h1>')
            
        # Handle unordered lists
        elif stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            content = stripped[2:].replace("**", "")
            html_lines.append(f'<li>{content}</li>')
            
        # Handle ordered lists (regular numbered items)
        elif re.match(r'^\d+\.\s+', stripped):
            if not in_ordered_list:
                html_lines.append('<ol>')
                in_ordered_list = True
            content = re.sub(r'^\d+\.\s+', '', stripped).replace("**", "")
            html_lines.append(f'<li>{content}</li>')
            
        # Handle horizontal rules
        elif '---' in stripped or '===' in stripped:
            html_lines.append('<hr>')
            
        # Handle regular paragraphs
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_ordered_list:
                html_lines.append('</ol>')
                in_ordered_list = False
            if stripped:
                # Clean remaining bold markers for paragraphs
                clean_line = stripped.replace("**", "")
                html_lines.append(f'<p>{clean_line}</p>')
    
    # Close any open lists
    if in_list:
        html_lines.append('</ul>')
    if in_ordered_list:
        html_lines.append('</ol>')
    
    return ''.join(html_lines)

def get_emergency_contacts(region=None):
    """Return filtered emergency contacts"""
    if region:
        region = region.lower()
        return [contact for contact in EMERGENCY_CONTACTS 
                if region in contact['regions'] or 'all' in contact['regions']]
    return EMERGENCY_CONTACTS


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

@app.route("/cybercrimes")
def cybercrimes():
    return render_template("cybercrimes.html")

@app.route("/resources")
def resources():
    return render_template("resources.html")


@app.route("/documents")
def documents():
    return render_template("documents.html")

@app.route("/videos")
def videos():
    return render_template("videos.html")

@app.route("/courses")
def courses():
    return render_template("courses.html")

@app.route("/api/clear_session", methods=["POST"])
def clear_session():
    session.pop("chat_history", None)  # Remove chat history from session
    session.modified = True
    return jsonify({"status": "success"})

@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    if "chat_history" not in session:
        session["chat_history"] = []

    session["chat_history"].append({"role": "user", "content": user_input})
    session["chat_history"] = session["chat_history"][-MAX_HISTORY:]

    # If bot is expecting a region name
    if session.get("awaiting_state"):
        region_input = user_input.strip().lower()
        region_contacts = get_emergency_contacts(region_input)

        if region_contacts and all("all" not in contact['regions'] for contact in region_contacts):
            contacts_text = "\n".join(
                f"{contact['name']}: {contact['number']} ({contact['description']})"
                for contact in region_contacts
            )
            bot_response = f"Here are the emergency contacts for {region_input.title()}:\n\n{contacts_text}"
        else:
            national_contacts = get_emergency_contacts("all")
            national_text = "\n".join(
                f"{contact['name']}: {contact['number']} ({contact['description']})"
                for contact in national_contacts
            )
            bot_response = f"I'm sorry, I couldn't identify your state.\n\nHere is the national cybercrime helpline:\n\n{national_text}"

        session["awaiting_state"] = False
        formatted_response = format_response(bot_response)
        return jsonify({"response": formatted_response})

    #Detect if emergency query
    emergency_keywords = ["emergency", "helpline", "contact", "number"]
    is_emergency_query = any(keyword in user_input.lower() for keyword in emergency_keywords)

    if is_emergency_query:
        region = None
        for contact in EMERGENCY_CONTACTS:
            for r in contact["regions"]:
                if r != "all" and r in user_input.lower():
                    region = r
                    break
            if region:
                break

        if region:
            contacts = get_emergency_contacts(region)
            contacts_text = "\n".join(
                f"{contact['name']}: {contact['number']} ({contact['description']})"
                for contact in contacts
            )
            bot_response = f"Here are the relevant emergency contacts:\n\n{contacts_text}\n\nPlease call the appropriate number for your location."
        else:
            national_contacts = get_emergency_contacts("all")
            national_text = "\n".join(
                f"{contact['name']}: {contact['number']} ({contact['description']})"
                for contact in national_contacts
            )
            bot_response = f"National Emergency Helpline:\n\n{national_text}\n\nWhich Indian state are you from?"
            session["awaiting_state"] = True
            session.modified = True

        formatted_response = format_response(bot_response)
        return jsonify({"response": formatted_response})

    #Otherwise, proceed with chatbot logic
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # Create chatbot prompt with history
    payload = {
        "model": "deepseek/deepseek-r1-distill-qwen-14b:free",
        "messages": [
            {"role": "system", "content": """
                Think of yourself as an expert that provides accurate, precise, and detailed but medium-length information about cybercrimes, laws & reporting procedures in India. 
                Only respond to cybercrime-related questions. If a user asks unrelated questions, politely decline. 
                NEVER EVER RESPOND IN CHINESE, NOT EVEN A SIGNLE CHARACTER. Always respond in English. 
                EMERGENCY CONTACTS:
                - When asked about emergency numbers, only mention Indian national helpline and (100) for polica and (102) for ambulance
                - Never give out any other contact number apart from the ones I mentionedd here, never invent or guess contact numbers
                - If unsure about a region, provide the Indian national helpline (1930)
                If the user asks about:
                - Cyber laws, check the official websites and provide details from the official Indian Constitution, IT Act, IPC.
                - Evidence collection, explain how to collect & preserve digital evidence.
                - Punishments, mention relevant sections from IT Act & IPC.
                - Reporting cybercrime, provide step-by-step instructions.
                - Helpline numbers, mention 1930 only. Only give Indian cybercrime cell number, don't give 市公安局 Cybercrime Cell. 
                - Safety measures, list actionable steps.
                1. NEVER use Markdown (no #, *, -, `, _)
                2. For lists: Use numbers like 1) 2) 3)
                3. For sections: Put section names in ALL CAPS
                4. For separation: Use blank lines between sections
                5. For links: Show full URL (https://example.com)
                Example of PERFECT response:
                IMPORTANT STEPS
                1) First action
                2) Second action
                CONTACT INFO
                Phone: 12345
                Website: https://cybercrime.gov.in
                If unsure, say: "I'm sorry, I don't have information on that."
                Do not use ** or ## or any other formatting in your responses.
            """}
        ] + session["chat_history"]
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        bot_response = data["choices"][0]["message"]["content"]

        # Ensure response is in English
        if not is_english(bot_response):
            bot_response = "I'm sorry, I can only provide responses in English."

        formatted_response = format_response(bot_response)  # Now uses proper Markdown conversion

        print(bot_response)
        print(formatted_response)

        session["chat_history"].append({"role": "assistant", "content": bot_response})
        session.modified = True

        return jsonify({"response": formatted_response})

        # Add bot response to history
        session["chat_history"].append({"role": "assistant", "content": bot_response})
        session.modified = True

        return jsonify({"response": formatted_response})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

# Function to check if the response is in English
def is_english(text):
    try:
        return detect(text) == "en"
    except:
        return False

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
    
