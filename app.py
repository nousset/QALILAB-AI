from dotenv import load_dotenv
import os
from flask import Flask, request, render_template_string, jsonify, redirect, url_for, send_from_directory
from flask_cors import CORS
import requests
import json
import urllib.parse
import jwt
import datetime
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# --------------------------
# Configuration Jira
# --------------------------
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL","https://qalilab-ai.onrender.com")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")
BASE_URL = os.getenv("BASE_URL", "https://qalilab-ai.onrender.com")

# JWT Secret pour authentification Atlassian Connect
JWT_SECRET = os.getenv("JWT_SECRET", "")
# Si JWT_SECRET n'est pas défini, il sera initialisé lors de l'installation de l'application

# Configuration LLM API
API_URL = os.getenv("API_URL", "https://rpm-retain-sender-probably.trycloudflare.com/v1/chat/completions")

app = Flask(__name__)
CORS(app)

# Stockage temporaire pour les informations de connexion client
# Dans une application de production, utilisez une base de données
clients = {}

def generate_response(prompt, max_tokens=256):
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-7b-instruct-v0.3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            logger.error(f"Erreur API LLM: {response.status_code} - {response.text}")
            return f"Erreur API: {response.status_code} - {response.text}"
    except Exception as e:
        logger.error(f"Erreur de connexion à LM Studio: {str(e)}")
        return f"Erreur de connexion à LM Studio: {str(e)}"

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



@app.route("/")
def home():
    return """
    <html>
    <head>
        <title>TestGen AI pour Jira</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #0052CC; }
            .card { background: #f4f5f7; border-radius: 5px; padding: 20px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>TestGen AI pour Jira</h1>
        <div class="card">
            <h2>Application installée avec succès</h2>
            <p>Cette application est conçue pour être utilisée dans Jira. Pour l'installer dans votre instance Jira, utilisez le descripteur Atlassian Connect :</p>
            <code>https://votre-domaine.com/atlassian-connect.json</code>
        </div>
        <p>Pour plus d'informations sur l'installation, consultez la documentation Atlassian Connect.</p>
    </body>
    </html>
    """
# Routes pour servir le logo et les fichiers statiques
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Routes Atlassian Connect
@app.route("/atlassian-connect.json")
def serve_descriptor():
    with open('atlassian-connect.json', 'r') as f:
        descriptor = json.load(f)
    return jsonify(descriptor)

@app.route("/installed", methods=["POST"])
def installed():
    try:
        data = request.get_json()
        client_key = data.get("clientKey")
        
        # Stocke les informations de connexion
        clients[client_key] = {
            "base_url": data.get("baseUrl"),
            "oauth_client_id": data.get("oauthClientId", ""),
            "shared_secret": data.get("sharedSecret"),
            "public_key": data.get("publicKey", ""),
            "installed_date": datetime.datetime.now().isoformat()
        }
        
        # Dans une application de production, stockez ces informations dans une base de données
        logger.info(f"Application installée pour le client: {client_key}")
        
        return jsonify({"status": "installed"})
    except Exception as e:
        logger.error(f"Erreur lors de l'installation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/uninstalled", methods=["POST"])
def uninstalled():
    try:
        data = request.get_json()
        client_key = data.get("clientKey")
        
        # Supprime les informations de connexion
        if client_key in clients:
            del clients[client_key]
        
        logger.info(f"Application désinstallée pour le client: {client_key}")
        
        return jsonify({"status": "uninstalled"})
    except Exception as e:
        logger.error(f"Erreur lors de la désinstallation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Fonction pour vérifier le JWT
def verify_jwt(req):
    try:
        # Récupère le token JWT depuis l'en-tête Authorization
        authorization = req.headers.get("Authorization", "")
        token = authorization.replace("JWT ", "")
        
        if not token:
            # Vérifie si le token est passé en paramètre de requête
            token = req.args.get("jwt", "")
        
        if not token:
            logger.warning("Aucun token JWT trouvé")
            return None
        
        # Décode le JWT
        decoded = jwt.decode(token, options={"verify_signature": False})
        client_key = decoded.get("iss")
        
        if client_key not in clients:
            logger.warning(f"Client inconnu: {client_key}")
            return None
        
        # Vérification complète avec la clé partagée
        shared_secret = clients[client_key]["shared_secret"]
        decoded_verified = jwt.decode(token, shared_secret, algorithms=["HS256"])
        
        return decoded_verified
    except Exception as e:
        logger.error(f"Erreur de vérification JWT: {str(e)}")
        return None

# Route principale pour le générateur de tests dans la boîte de dialogue Jira
@app.route("/jira-test-generator", methods=["GET"])
def jira_test_generator():
    jwt_data = verify_jwt(request)
    
    if not jwt_data:
        return jsonify({"error": "JWT invalide"}), 401
    
    # Récupère les informations du contexte de l'issue Jira
    issue_key = request.args.get("issueKey", "")
    client_key = jwt_data.get("iss")
    
    if not issue_key and jwt_data.get("context", {}).get("jira", {}).get("issue", {}).get("key"):
        issue_key = jwt_data["context"]["jira"]["issue"]["key"]
    
    # Si on a une clé d'issue mais pas de contexte complet, on récupère les données depuis l'API Jira
    if issue_key and client_key in clients:
        try:
            base_url = clients[client_key]["base_url"]
            
            # Création d'un JWT pour l'API Jira
            now = datetime.datetime.now()
            exp = now + datetime.timedelta(minutes=3)
            
            jwt_payload = {
                "iss": "test-generator-app",
                "iat": int(now.timestamp()),
                "exp": int(exp.timestamp()),
                "qsh": "context-qsh", # Simplification, normalement calculé
                "sub": client_key
            }
            
            shared_secret = clients[client_key]["shared_secret"]
            jwt_token = jwt.encode(jwt_payload, shared_secret, algorithm="HS256")
            
            # Récupère les détails de l'issue
            issue_url = f"{base_url}/rest/api/3/issue/{issue_key}"
            headers = {
                "Authorization": f"JWT {jwt_token}",
                "Accept": "application/json"
            }
            
            response = requests.get(issue_url, headers=headers)
            if response.status_code == 200:
                issue_data = response.json()
                summary = issue_data.get("fields", {}).get("summary", "")
                description = issue_data.get("fields", {}).get("description", "")
                description_text = ""
                
                # Extraction du texte de description (format ADF)
                if isinstance(description, dict) and description.get("content"):
                    for content in description.get("content", []):
                        if content.get("type") == "paragraph" and content.get("content"):
                            for text_part in content.get("content", []):
                                if text_part.get("type") == "text":
                                    description_text += text_part.get("text", "") + "\n"
            else:
                summary = ""
                description_text = ""
                logger.warning(f"Impossible de récupérer les données de l'issue: {response.status_code}")
        except Exception as e:
            summary = ""
            description_text = ""
            logger.error(f"Erreur lors de la récupération des données de l'issue: {str(e)}")
    else:
        summary = ""
        description_text = ""
    
    story_text = f"{summary}\n\n{description_text}".strip()
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Générateur de cas de test</title>
      <link rel="stylesheet" href="https://unpkg.com/@atlaskit/css-reset@6.0.5/dist/bundle.css"/>
      <link rel="stylesheet" href="https://unpkg.com/@atlaskit/reduced-ui-pack@13.0.0/dist/bundle.css"/>
      <script src="https://connect-cdn.atl-paas.net/all.js"></script>
      <style>
        body { 
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; 
          margin: 20px; 
          background-color: #f4f5f7;
        }
        .card {
          background-color: white;
          border-radius: 3px;
          box-shadow: 0 1px 2px rgba(0,0,0,0.1);
          padding: 20px;
          margin-bottom: 20px;
        }
        textarea { 
          width: 100%; 
          min-height: 120px; 
          padding: 8px;
          border: 1px solid #dfe1e6;
          border-radius: 3px;
          resize: vertical;
          font-family: inherit;
          font-size: 14px;
        }
        .field-group {
          margin-bottom: 16px;
        }
        label {
          display: block;
          font-weight: 500;
          margin-bottom: 8px;
        }
        .radio-group {
          margin-bottom: 16px;
        }
        .radio-label {
          margin-right: 16px;
          font-weight: normal;
          display: inline-flex;
          align-items: center;
        }
        pre { 
          background-color: #f4f5f7; 
          padding: 12px; 
          border-radius: 3px; 
          white-space: pre-wrap;
          font-family: monospace;
          font-size: 14px;
          line-height: 1.4;
          border: 1px solid #dfe1e6;
        }
        .ak-button {
          margin-right: 8px;
        }
        #result {
          margin-top: 20px;
          display: none;
        }
        .header {
          display: flex;
          align-items: center;
          margin-bottom: 16px;
        }
        .header h2 {
          margin: 0;
          flex-grow: 1;
        }
        .header-icon {
          margin-right: 10px;
        }
        .header-buttons {
          display: flex;
          gap: 8px;
        }
        .card-title {
          font-size: 16px;
          font-weight: 500;
          margin-bottom: 12px;
        }
        .spinner {
          display: inline-block;
          border: 2px solid #f3f3f3;
          border-top: 2px solid #0052cc;
          border-radius: 50%;
          width: 16px;
          height: 16px;
          animation: spin 1s linear infinite;
          margin-right: 8px;
          vertical-align: middle;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        #loading {
          display: none;
          margin-top: 16px;
        }
      </style>
    </head>
    <body>
      <div class="header">
        <div class="header-icon">🧠</div>
        <h2>Générateur de cas de test</h2>
      </div>
      
      <div class="card">
        <div class="card-title">Informations de la user story</div>
        <div class="field-group">
          <label for="storyText">Description</label>
          <textarea id="storyText" placeholder="Entrez la user story ici...">{{ story_text }}</textarea>
        </div>
        
        <div class="radio-group">
          <label>Format de test :</label>
          <label class="radio-label">
            <input type="radio" name="format" value="gherkin" checked> Gherkin (Given/When/Then)
          </label>
          <label class="radio-label">
            <input type="radio" name="format" value="action"> Actions / Résultats attendus
          </label>
        </div>
        
        <button id="generateBtn" class="ak-button ak-button__appearance-primary">Générer le test</button>
        
        <div id="loading">
          <div class="spinner"></div> Génération du test en cours...
        </div>
      </div>
      
      <div id="result" class="card">
        <div class="card-title">Test généré</div>
        <pre id="generatedTest"></pre>
        
        <div class="header-buttons">
          <button id="saveBtn" class="ak-button ak-button__appearance-primary">Créer une tâche avec ce test</button>
          <button id="copyBtn" class="ak-button ak-button__appearance-default">Copier</button>
        </div>
      </div>
      
      <script>
        // Initialisation AP
        AP.context.getContext(function(context) {
          console.log("Context:", context);
          document.getElementById('issue-key').textContent = context.jira.issue ? context.jira.issue.key : 'N/A';
        });
        
        document.getElementById('generateBtn').addEventListener('click', function() {
          const storyText = document.getElementById('storyText').value;
          const format = document.querySelector('input[name="format"]:checked').value;
          
          if (!storyText.trim()) {
            AP.flag.create({
              title: 'Champ obligatoire',
              body: 'Veuillez entrer une description de user story',
              type: 'error'
            });
            return;
          }
          
          // Afficher le chargement
          document.getElementById('loading').style.display = 'block';
          document.getElementById('result').style.display = 'none';
          
          fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ story: storyText, format: format })
          })
          .then(response => response.json())
          .then(data => {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('generatedTest').textContent = data.result;
            document.getElementById('result').style.display = 'block';
          })
          .catch(err => {
            document.getElementById('loading').style.display = 'none';
            AP.flag.create({
              title: 'Erreur',
              body: 'Erreur lors de la génération du test: ' + err,
              type: 'error'
            });
          });
        });
        
        document.getElementById('saveBtn').addEventListener('click', function() {
          const generatedTest = document.getElementById('generatedTest').textContent;
          const storyText = document.getElementById('storyText').value;
          const storySummary = storyText.split('\n')[0].slice(0, 50) || "Cas de test";
          
          AP.context.getContext(function(context) {
            const issueKey = context.jira.issue ? context.jira.issue.key : '';
            
            fetch('/api/create-task', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                generated_test: generatedTest,
                summary: `Test: ${storySummary}`,
                parent_issue: issueKey,
                jwt: AP.context.getToken()
              })
            })
            .then(response => response.json())
            .then(data => {
              if (data.issue && data.issue.key) {
                AP.flag.create({
                  title: 'Succès',
                  body: 'Tâche de test créée: ' + data.issue.key,
                  type: 'success'
                });
                
                // Fermer la boîte de dialogue
                setTimeout(() => {
                  AP.dialog.close();
                  // Rafraîchir la page pour voir le nouveau ticket lié
                  AP.jira.refreshIssuePage();
                }, 2000);
              } else {
                AP.flag.create({
                  title: 'Erreur',
                  body: 'Erreur lors de la création de la tâche: ' + JSON.stringify(data),
                  type: 'error'
                });
              }
            })
            .catch(err => {
              AP.flag.create({
                title: 'Erreur',
                body: 'Erreur réseau: ' + err,
                type: 'error'
              });
            });
          });
        });
        
        document.getElementById('copyBtn').addEventListener('click', function() {
          const generatedTest = document.getElementById('generatedTest').textContent;
          
          // Copier dans le presse-papiers
          navigator.clipboard.writeText(generatedTest).then(function() {
            AP.flag.create({
              title: 'Copié',
              body: 'Test copié dans le presse-papiers',
              type: 'success'
            });
          }, function() {
            AP.flag.create({
              title: 'Erreur',
              body: 'Impossible de copier dans le presse-papiers',
              type: 'warning'
            });
          });
        });
      </script>
      <div id="issue-key" style="display: none;"></div>
    </body>
    </html>
    """
    return render_template_string(html_template, story_text=story_text)

# API pour la génération de tests
@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.json
    story_text = data.get("story", "").strip()
    format_choice = data.get("format", "gherkin")
    
    if not story_text:
        return jsonify({"error": "Aucune user story fournie"}), 400

    prompt = build_prompt(story_text, format_choice)
    generated_test = generate_response(prompt, max_tokens=500)
    return jsonify({"result": generated_test})

# API pour la création de tâches Jira
@app.route("/api/create-task", methods=["POST"])
def api_create_task():
    data = request.json
    test_content = data.get("generated_test", "")
    summary = data.get("summary", "Cas de test généré automatiquement")
    parent_issue = data.get("parent_issue", "")
    jwt_token = data.get("jwt", "")

    if not test_content:
        return jsonify({"error": "Aucun contenu de test fourni"}), 400
    
    # Vérification JWT
    try:
        decoded = jwt.decode(jwt_token, options={"verify_signature": False})
        client_key = decoded.get("iss")
        
        if client_key not in clients:
            return jsonify({"error": "Client non autorisé"}), 401
            
        # Récupération des informations d'authentification du client
        client_info = clients[client_key]
        base_url = client_info["base_url"]
        
        # Création d'un JWT pour l'API Jira
        now = datetime.datetime.now()
        exp = now + datetime.timedelta(minutes=3)
        
        jwt_payload = {
            "iss": "test-generator-app",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "qsh": "context-qsh", # Simplification, normalement calculé
            "sub": client_key
        }
        
        shared_secret = client_info["shared_secret"]
        api_jwt = jwt.encode(jwt_payload, shared_secret, algorithm="HS256")
        
        # Formatage ADF pour Jira
        adf_description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": test_content}
                    ]
                }
            ]
        }
        
        # Prépare le payload avec les champs appropriés
        payload = {
            "fields": {
                "summary": summary,
                "description": adf_description,
                "issuetype": {"name": "Test"}  # Vérifie que ce type existe dans ton projet Jira
            }
        }
        
        # Si un ticket parent est spécifié, récupère le projet et ajoute le lien
        if parent_issue:
            # Récupère les informations du ticket parent
            issue_url = f"{base_url}/rest/api/3/issue/{parent_issue}"
            headers = {
                "Authorization": f"JWT {api_jwt}",
                "Accept": "application/json"
            }
            
            response = requests.get(issue_url, headers=headers)
            if response.status_code == 200:
                parent_data = response.json()
                project_key = parent_data.get("fields", {}).get("project", {}).get("key")
                
                if project_key:
                    payload["fields"]["project"] = {"key": project_key}
            
            # Ajoute le lien avec le ticket parent si supporté
            try:
                # On essaie d'abord avec le champ parent
                payload["fields"]["parent"] = {"key": parent_issue}
            except:
                # Sinon nous créerons un lien après la création du ticket
                pass
        
        # Crée le ticket de test
        create_url = f"{base_url}/rest/api/3/issue"
        headers = {
            "Authorization": f"JWT {api_jwt}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(create_url, headers=headers, json=payload)
        
        if response.status_code == 201:
            result = response.json()
            new_issue_key = result.get("key")
            
            # Si le champ parent n'est pas supporté, crée un lien
            if parent_issue and "parent" not in payload["fields"]:
                link_url = f"{base_url}/rest/api/3/issueLink"
                link_payload = {
                    "type": {"name": "Tests"},  # Ou un autre type approprié comme "Relates to"
                    "inwardIssue": {"key": new_issue_key},
                    "outwardIssue": {"key": parent_issue}
                }
                
                link_response = requests.post(link_url, headers=headers, json=link_payload)
                
                if link_response.status_code != 201:
                    logger.warning(f"Erreur lors de la création du lien: {link_response.status_code}")
            
            return jsonify({"message": "Tâche Jira créée", "issue": result}), 201
        else:
            logger.error(f"Erreur lors de la création du ticket: {response.status_code} - {response.text}")
            return jsonify({"error": response.text}), response.status_code
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la tâche: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Logo SVG pour l'icône du glance
@app.route("/static/brain.svg")
def serve_brain_svg():
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0052CC" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44A2.5 2.5 0 0 1 2 17.5v-11a2.5 2.5 0 0 1 2.5-2.5h5zm5 0A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44A2.5 2.5 0 0 0 22 17.5v-11a2.5 2.5 0 0 0-2.5-2.5h-5z"/>
    <path d="M12 4.5C12 5.88 13.12 7 14.5 7H17a2 2 0 0 1 2 2v.5a2 2 0 0 1-2 2"/>
    <path d="M12 4.5C12 5.88 10.88 7 9.5 7H7a2 2 0 0 0-2 2v.5a2 2 0 0 0 2 2"/>
    <path d="M14 12H9"/>
    <path d="M12 4.5V16.5"/>
    </svg>'''
    
    return svg_content, 200, {'Content-Type': 'image/svg+xml'}

if __name__ == "__main__":
    # Vérification du répertoire static
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # Création du fichier SVG
    with open('static/brain.svg', 'w') as f:
        f.write('''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0052CC" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44A2.5 2.5 0 0 1 2 17.5v-11a2.5 2.5 0 0 1 2.5-2.5h5zm5 0A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44A2.5 2.5 0 0 0 22 17.5v-11a2.5 2.5 0 0 0-2.5-2.5h-5z"/>
        <path d="M12 4.5C12 5.88 13.12 7 14.5 7H17a2 2 0 0 1 2 2v.5a2 2 0 0 1-2 2"/>
        <path d="M12 4.5C12 5.88 10.88 7 9.5 7H7a2 2 0 0 0-2 2v.5a2 2 0 0 0 2 2"/>
        <path d="M14 12H9"/>
        <path d="M12 4.5V16.5"/>
    </svg>''')
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


   