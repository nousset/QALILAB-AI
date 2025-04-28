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
API_URL = os.getenv("API_URL", "https://asked-securities-clubs-nelson.trycloudflare.com/v1/chat/completions")

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
    
def build_prompt(story_text, format_choice, language_choice="fr"):
    # Détermine la langue pour le prompt
    lang = "français" if language_choice == "fr" else "anglais"
    
    if format_choice == "gherkin":
        return (
            f"Voici une user story : \"{story_text}\"\n"
            f"En tant qu'assistant de test, génère un scénario de test au format Gherkin "
            f"(Given/When/Then) en {lang}."
        )
    else:
        return (
            f"Voici une user story : \"{story_text}\"\n"
            f"En tant qu'assistant de test, génère un cas de test détaillant les actions "
            f"à effectuer et les résultats attendus pour chaque action, en {lang}."
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
    
    
def add_comment_button_to_issue(issue_key):
    """Ajoute un commentaire avec un bouton vers votre application"""
    
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
    button_link = f"https://qalilab-ai.onrender.com/jira-panel?issueKey={issue_key}"
    
    link_text = f"[Générer des cas de test|{button_link}]"
    
    comment = {
        "body": f"Cliquez ici pour {link_text} pour cette user story."
    }
    
    try:
        response = requests.post(api_endpoint, json=comment, auth=auth)
        if response.status_code == 201:
            return True, "Commentaire ajouté avec succès"
        else:
            return False, f"Erreur: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

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
    
@app.route("/check-app-status")
def check_app_status():
    """Endpoint pour vérifier l'état de l'application et sa configuration"""
    # Vérifie si le fichier descripteur existe
    descriptor_exists = os.path.exists('atlassian-connect.json')
    
    # Si le fichier existe, charge-le pour vérification
    descriptor_content = None
    if descriptor_exists:
        try:
            with open('atlassian-connect.json', 'r') as f:
                descriptor_content = json.load(f)
        except Exception as e:
            descriptor_content = {"error": str(e)}
    
    # Vérifie si les variables d'environnement obligatoires sont définies
    env_vars = {
        "JIRA_BASE_URL": bool(JIRA_BASE_URL),
        "JIRA_EMAIL": bool(JIRA_EMAIL),
        "JIRA_API_TOKEN": bool(JIRA_API_TOKEN),
        "JIRA_PROJECT_KEY": bool(JIRA_PROJECT_KEY)
    }
    
    # Vérifie les templates
    templates_dir = os.path.exists('templates')
    index_template = os.path.exists('templates/index.html') if templates_dir else False
    
    status = {
        "app_running": True,
        "descriptor_exists": descriptor_exists,
        "descriptor_content": descriptor_content,
        "env_vars": env_vars,
        "templates_directory_exists": templates_dir,
        "index_template_exists": index_template,
        "app_url": request.url_root,
        "descriptor_url": request.url_root.rstrip('/') + "/atlassian-connect.json"
    }
    
    return jsonify(status)
    

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
    print("Demande du descripteur reçue!")
    with open('atlassian-connect.json', 'r') as f:
        descriptor = json.load(f)
    
    # Assure-toi que l'URL de base est correcte
    descriptor["baseUrl"] = "https://qalilab-ai.onrender.com"
    
    print(f"Descripteur servi: {json.dumps(descriptor)}")
    return jsonify(descriptor)

@app.route("/jira-panel")
def jira_panel():
    """Affiche le panneau dans Jira"""
    issue_key = request.args.get("issueKey", "")
    summary = request.args.get("summary", "")
    description = request.args.get("description", "")
    language = request.args.get("language", "fr")  # Ajout du paramètre de langue
    
    print(f"Requête reçue pour l'issue {issue_key}")
    
    # URL pour retourner à l'issue Jira
    jira_return_url = f"https://{JIRA_BASE_URL}/browse/{issue_key}"
    
    # Construire l'URL avec les paramètres
    redirect_url = url_for('index', 
                          story=description,
                          returnUrl=jira_return_url,
                          language=language,
                          autoGenerate="true")
    
    return redirect(redirect_url)

@app.route("/installed", methods=["POST"])
def installed():
    """Gère l'installation de l'application"""
    print("Application installée!")
    return jsonify({"status": "ok"})

@app.route("/uninstalled", methods=["POST"])
def uninstalled():
    """Gère la désinstallation de l'application"""
    print("Application désinstallée!")
    return jsonify({"status": "ok"})

@app.route("/add-link-to-issue/<issue_key>")
def add_link(issue_key):
    """Route pour ajouter un commentaire avec un lien à une issue Jira"""
    success, message = add_comment_button_to_issue(issue_key)
    if success:
        return jsonify({
            "success": True, 
            "message": f"Lien ajouté à l'issue {issue_key}", 
            "details": message
        })
    else:
        return jsonify({
            "success": False, 
            "message": f"Erreur lors de l'ajout du lien à l'issue {issue_key}", 
            "details": message
        }), 400

@app.route("/check-env", methods=["GET"])
def check_env():
    """Route de diagnostic pour vérifier les variables d'environnement (masquées)"""
    env_status = {
        "JIRA_BASE_URL": JIRA_BASE_URL,
        "JIRA_EMAIL": JIRA_EMAIL[:3] + "***" if JIRA_EMAIL else None,
        "JIRA_API_TOKEN": "***" if JIRA_API_TOKEN else None,
        "JIRA_PROJECT_KEY": JIRA_PROJECT_KEY,
    }
    return jsonify(env_status)

@app.route("/add-links-to-user-stories", methods=["GET"])
def add_links_to_user_stories():
    """Ajoute des liens à toutes les user stories du projet"""
    # Récupérer les issues de type User Story du projet
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/search"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
    # JQL pour obtenir toutes les User Stories du projet
    jql = f"project = {JIRA_PROJECT_KEY} AND issuetype = 'Story' ORDER BY created DESC"
    
    params = {
        "jql": jql,
        "maxResults": 100  # Augmenté à 100 pour traiter plus de stories
    }
    
    try:
        response = requests.get(api_endpoint, auth=auth, params=params)
        if response.status_code != 200:
            return jsonify({
                "success": False,
                "message": f"Erreur lors de la récupération des user stories: {response.status_code} - {response.text}"
            }), 400
            
        data = response.json()
        issues = data.get("issues", [])
        
        if not issues:
            return jsonify({
                "success": True,
                "message": "Aucune user story trouvée dans le projet"
            })
        
        results = []
        for issue in issues:
            issue_key = issue["key"]
            success, message = add_comment_button_to_issue(issue_key)
            results.append({
                "issue_key": issue_key,
                "success": success,
                "message": message
            })
        
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        return jsonify({
            "success": True,
            "message": f"Traitement terminé. {successful} liens ajoutés avec succès, {failed} échecs.",
            "results": results
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erreur: {str(e)}"
        }), 500

@app.route("/", methods=["GET", "POST"])
def index():
    story_text = ""
    format_choice = "gherkin"
    language_choice = "fr"  # Français par défaut
    generated_test = None
    jira_return_url = None
    issue_types = get_issue_types()
    
    # Récupérer les paramètres
    if request.method == "GET":
        story_text = request.args.get("story", "").strip()
        format_choice = request.args.get("format", "gherkin")
        language_choice = request.args.get("language", "fr")
        jira_return_url = request.args.get("returnUrl", "")
        auto_generate = request.args.get("autoGenerate", "false").lower() == "true"
        
        if story_text and auto_generate:
            prompt = build_prompt(story_text, format_choice, language_choice)
            generated_test = generate_response(prompt)
    
    if request.method == "POST":
        story_text = request.form.get("story", "").strip()
        format_choice = request.form.get("format", "gherkin")
        language_choice = request.form.get("language", "fr")
        jira_return_url = request.form.get("returnUrl", "")
        
        if story_text:
            prompt = build_prompt(story_text, format_choice, language_choice)
            generated_test = generate_response(prompt)
    
    return render_template("index.html",
                          story=story_text,
                          format_choice=format_choice,
                          language_choice=language_choice,
                          generated_test=generated_test,
                          jira_return_url=jira_return_url,
                          JIRA_BASE_URL=JIRA_BASE_URL,
                          issue_types=issue_types)

if __name__ == "__main__":
    # Créer le dossier templates s'il n'existe pas
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))