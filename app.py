from dotenv import load_dotenv
import os
from flask import Flask, request, render_template, jsonify, redirect, url_for
import requests
import json

# Chargement des variables d'environnement
load_dotenv()

# Configuration
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "amaniconsulting.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "ACD")
API_URL = os.getenv("API_URL", "https://classifieds-aimed-prix-helena.trycloudflare.com/v1/chat/completions")

app = Flask(__name__)

def generate_response(prompt, max_tokens=256):
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "mistral-7b-instruct-v0.3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"Erreur API: {response.status_code}"
    except Exception as e:
        return f"Erreur: {str(e)}"

def build_prompt(story_text, format_choice):
    if format_choice == "gherkin":
        return (
            f"Voici une user story : \"{story_text}\"\n"
            "En tant qu'assistant de test, génère un scénario de test au format Gherkin "
            "(Given/When/Then) en français."
        )
    else:
        return (
            f"Voici une user story : \"{story_text}\"\n"
            "En tant qu'assistant de test, génère un cas de test détaillant les actions "
            "à effectuer et les résultats attendus pour chaque action, en français."
        )

def get_issue_types():
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/issue/createmeta?projectKeys={JIRA_PROJECT_KEY}"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
    try:
        response = requests.get(api_endpoint, auth=auth)
        if response.status_code == 200:
            data = response.json()
            if data['projects'] and len(data['projects']) > 0:
                return [issue_type['name'] for issue_type in data['projects'][0]['issuetypes']]
        return []
    except Exception:
        return []

def create_jira_ticket(test_content, summary="Cas de test généré automatiquement", issue_type=None):
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/issue/"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Authentification Basic (email + token API)
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
    # Si le type de ticket n'est pas spécifié, essayons de trouver un type approprié
    if not issue_type:
        # D'abord, essayons de récupérer les types de tickets disponibles
        issue_types = get_issue_types()
        
        # Choisir un type approprié ou utiliser une valeur par défaut commune
        issue_type = "Story"  # Valeur par défaut
        
        # Si on a récupéré les types, on essaie de trouver un type approprié
        if issue_types:
            # Priorité pour les types communs dans cet ordre
            preferred_types = ["Test", "Story", "Task", "Bug", "Sub-task"]
            for preferred in preferred_types:
                if preferred in issue_types:
                    issue_type = preferred
                    break
    
    payload = {
        "fields": {
            "project": {
                "key": JIRA_PROJECT_KEY
            },
            "summary": summary,
            "description": test_content,
            "issuetype": {
                "name": issue_type
            }
        }
    }
    
    try:
        response = requests.post(api_endpoint, headers=headers, auth=auth, json=payload)
        if response.status_code in [200, 201]:
            result = response.json()
            return True, result["key"]  # Renvoie l'ID du ticket créé
        else:
            return False, f"Erreur API Jira: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

@app.route("/create_jira_ticket", methods=["POST"])
def handle_create_ticket():
    data = request.json
    test_content = data.get("content", "")
    summary = data.get("summary", "Cas de test généré automatiquement")
    issue_type = data.get("issueType")
    
    success, result = create_jira_ticket(test_content, summary, issue_type)
    
    if success:
        return jsonify({"success": True, "ticket_key": result})
    else:
        return jsonify({"success": False, "message": result})

@app.route("/get_issue_types", methods=["GET"])
def handle_get_issue_types():
    issue_types = get_issue_types()
    return jsonify({"issue_types": issue_types})

@app.route("/atlassian-connect.json")
def descriptor():
    """Fournit le descripteur atlassian-connect.json"""
    # Vérifie si le fichier existe, sinon génère un descripteur par défaut
    if os.path.exists('atlassian-connect.json'):
        with open('atlassian-connect.json', 'r') as f:
            descriptor = json.load(f)
    else:
        # Descripteur par défaut
        descriptor = {
            "name": "Générateur de Cas de Test",
            "description": "Génère des cas de test en format Gherkin ou actions/résultats à partir des user stories",
            "key": "test-case-generator",
            "baseUrl": request.url_root.rstrip('/'),
            "vendor": {
                "name": "Amani Consulting",
                "url": "https://amaniconsulting.atlassian.net"
            },
            "authentication": {
                "type": "none"
            },
            "apiVersion": 1,
            "modules": {
                "webPanels": [
                    {
                        "key": "test-generator-panel",
                        "name": {
                            "value": "Générer Cas de Test"
                        },
                        "location": "atl.jira.view.issue.right.context",
                        "url": "/jira-panel?issueKey={issue.key}&summary={issue.summary}&description={issue.description}",
                        "weight": 100
                    }
                ],
                "generalPages": [
                    {
                        "key": "test-generator-page",
                        "name": {
                            "value": "Génération de Cas de Test"
                        },
                        "url": "/",
                        "location": "system.top.navigation.bar"
                    }
                ]
            }
        }
    
    # Assure-toi que l'URL de base est correcte (pour le développement vs production)
    if os.environ.get("RENDER_EXTERNAL_URL"):
        descriptor["baseUrl"] = os.environ.get("RENDER_EXTERNAL_URL").rstrip('/')
    
    return jsonify(descriptor)

@app.route("/jira-panel")
def jira_panel():
    """Affiche le panneau dans Jira"""
    issue_key = request.args.get("issueKey", "")
    summary = request.args.get("summary", "")
    description = request.args.get("description", "")
    
    # URL pour retourner à l'issue Jira
    jira_return_url = f"https://{JIRA_BASE_URL}/browse/{issue_key}"
    
    # Construire l'URL avec les paramètres
    redirect_url = url_for('index', 
                          story=description,
                          returnUrl=jira_return_url,
                          autoGenerate="true")
    
    return redirect(redirect_url)

@app.route("/", methods=["GET", "POST"])
def index():
    story_text = ""
    format_choice = "gherkin"
    generated_test = None
    jira_return_url = None
    issue_types = get_issue_types()
    
    # Récupérer les paramètres
    if request.method == "GET":
        story_text = request.args.get("story", "").strip()
        format_choice = request.args.get("format", "gherkin")
        jira_return_url = request.args.get("returnUrl", "")
        auto_generate = request.args.get("autoGenerate", "false").lower() == "true"
        
        if story_text and auto_generate:
            prompt = build_prompt(story_text, format_choice)
            generated_test = generate_response(prompt)
    
    if request.method == "POST":
        story_text = request.form.get("story", "").strip()
        format_choice = request.form.get("format", "gherkin")
        jira_return_url = request.form.get("returnUrl", "")
        
        if story_text:
            prompt = build_prompt(story_text, format_choice)
            generated_test = generate_response(prompt)
    
    return render_template("index.html",
                          story=story_text,
                          format_choice=format_choice,
                          generated_test=generated_test,
                          jira_return_url=jira_return_url,
                          JIRA_BASE_URL=JIRA_BASE_URL,
                          issue_types=issue_types)

if __name__ == "__main__":
    # Créer le dossier templates s'il n'existe pas
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))