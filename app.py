from dotenv import load_dotenv
import os
from flask import Flask, request, render_template_string, jsonify
import requests
import json

# Chargement des variables d'environnement
load_dotenv()

# Configuration
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "amaniconsulting.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "ACD")
API_URL = os.getenv("API_URL", "https://write-purchases-p-highlights.trycloudflare.com/v1/chat/completions")

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

def create_jira_ticket(test_content, summary="Cas de test généré automatiquement"):
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/issue/"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Authentification Basic (email + token API)
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
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
    
    success, result = create_jira_ticket(test_content, summary)
    
    if success:
        return jsonify({"success": True, "ticket_key": result})
    else:
        return jsonify({"success": False, "message": result})

@app.route("/get_issue_types", methods=["GET"])
def handle_get_issue_types():
    issue_types = get_issue_types()
    return jsonify({"issue_types": issue_types})

# Nouvelle route pour l'API qui prend une user story directement de Jira
@app.route("/api/generate_test", methods=["POST"])
def generate_test_api():
    data = request.json
    story_text = data.get("summary", "") + "\n" + data.get("description", "")
    format_choice = data.get("format", "gherkin")
    
    if not story_text.strip():
        return jsonify({"success": False, "message": "Texte de user story manquant"})
    
    prompt = build_prompt(story_text, format_choice)
    generated_test = generate_response(prompt)
    
    return jsonify({
        "success": True,
        "generated_test": generated_test
    })

# Point de terminaison pour la vérification de santé (pour Render)
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

# Point de terminaison pour l'installation/désinstallation du plugin Jira
@app.route("/atlassian-connect", methods=["GET"])
def atlassian_connect():
    with open('atlassian-connect.json', 'r') as file:
        data = json.load(file)
    return jsonify(data)

@app.route("/installed", methods=["POST"])
def installed():
    # Traiter l'événement d'installation
    return jsonify({"status": "ok"})

@app.route("/uninstalled", methods=["POST"])
def uninstalled():
    # Traiter l'événement de désinstallation
    return jsonify({"status": "ok"})

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
    
    # Modèle HTML simplifié
    html_template = """
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Génération de cas de test</title>
      <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; }
        textarea, pre, select { width: 100%; }
        pre { background-color: #f5f5f5; padding: 15px; border-radius: 5px; white-space: pre-wrap; }
        button { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background-color: #45a049; }
        .return-button { background-color: #2196F3; }
        .return-button:hover { background-color: #0b7dda; }
        .create-ticket-button { background-color: #ff9800; }
        .create-ticket-button:hover { background-color: #e68a00; }
        #status { padding: 10px; margin-top: 10px; display: none; }
        .success { background-color: #dff0d8; color: #3c763d; }
        .error { background-color: #f2dede; color: #a94442; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        select { padding: 8px; border-radius: 4px; border: 1px solid #ddd; }
      </style>
    </head>
    <body>
      <h1>Générer des cas de test à partir d'une User Story</h1>
      <form method="post">
        <div class="form-group">
          <label for="story">User Story :</label>
          <textarea id="story" name="story" rows="6" cols="60" placeholder="Entrez la user story ici...">{{ story }}</textarea>
        </div>
        <div class="form-group">
          Format de test :
          <label><input type="radio" name="format" value="gherkin" {% if format_choice != 'action' %}checked{% endif %}> Gherkin</label>
          <label><input type="radio" name="format" value="action" {% if format_choice == 'action' %}checked{% endif %}> Actions / Résultats attendus</label>
        </div>
        {% if jira_return_url %}
          <input type="hidden" name="returnUrl" value="{{ jira_return_url }}">
        {% endif %}
        <p><button type="submit">Générer</button></p>
      </form>

      {% if generated_test %}
        <h2>Cas de test généré :</h2>
        <pre id="generatedTest">{{ generated_test }}</pre>
        
        <div id="status"></div>
        
        {% if issue_types %}
        <div class="form-group">
          <label for="issueType">Type de ticket Jira :</label>
          <select id="issueType">
            {% for type in issue_types %}
            <option value="{{ type }}">{{ type }}</option>
            {% endfor %}
          </select>
        </div>
        {% endif %}
        
        <p>
          <button class="return-button" onclick="copyAndReturn()">Copier et retourner à Jira</button>
          <button class="create-ticket-button" onclick="createJiraTicket()">Créer un ticket Jira</button>
        </p>
        
        <script>
          function copyAndReturn() {
            const generatedTest = document.getElementById('generatedTest').textContent;
            const returnUrl = "{{ jira_return_url }}";
            const statusDiv = document.getElementById('status');
            
            // Copier dans le presse-papiers
            navigator.clipboard.writeText(generatedTest)
              .then(() => {
                statusDiv.textContent = 'Test copié dans le presse-papiers. Redirection...';
                statusDiv.className = 'success';
                statusDiv.style.display = 'block';
                
                // Rediriger après un court délai
                setTimeout(() => {
                  if (returnUrl) {
                    window.location.href = returnUrl;
                  }
                }, 1500);
              })
              .catch(err => {
                statusDiv.textContent = 'Erreur lors de la copie: ' + err;
                statusDiv.className = 'error';
                statusDiv.style.display = 'block';
              });
          }
          
          function createJiraTicket() {
            const generatedTest = document.getElementById('generatedTest').textContent;
            const statusDiv = document.getElementById('status');
            const summary = "Cas de test généré: " + document.querySelector('textarea[name="story"]').value.substring(0, 50) + "...";
            const issueTypeSelect = document.getElementById('issueType');
            const issueType = issueTypeSelect ? issueTypeSelect.value : null;
            
            statusDiv.textContent = 'Création du ticket Jira en cours...';
            statusDiv.className = '';
            statusDiv.style.display = 'block';
            
            const payload = {
                content: generatedTest,
                summary: summary
            };
            
            if (issueType) {
                payload.issueType = issueType;
            }
            
            fetch('/create_jira_ticket', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusDiv.textContent = 'Ticket Jira créé avec succès: ' + data.ticket_key;
                    statusDiv.className = 'success';
                    
                    // Ajouter un lien vers le ticket créé
                    const ticketLink = document.createElement('p');
                    ticketLink.innerHTML = `<a href="https://{{ JIRA_BASE_URL }}/browse/${data.ticket_key}" target="_blank">Voir le ticket ${data.ticket_key}</a>`;
                    statusDiv.appendChild(ticketLink);
                } else {
                    statusDiv.textContent = 'Erreur lors de la création du ticket: ' + data.message;
                    statusDiv.className = 'error';
                }
            })
            .catch(error => {
                statusDiv.textContent = 'Erreur: ' + error;
                statusDiv.className = 'error';
            });
          }
        </script>
      {% endif %}
    </body>
    </html>
    """
    
    return render_template_string(html_template,
                                  story=story_text,
                                  format_choice=format_choice,
                                  generated_test=generated_test,
                                  jira_return_url=jira_return_url,
                                  JIRA_BASE_URL=JIRA_BASE_URL,
                                  issue_types=issue_types)

# Nouvelle route pour la page qui sera appelée depuis Jira
@app.route("/jira-test-generator", methods=["GET"])
def jira_test_generator():
    issue_key = request.args.get("issueKey", "")
    jira_return_url = request.args.get("returnUrl", "")
    
    html_template = """
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Générateur de cas de test Jira</title>
      <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; }
        textarea, pre, select { width: 100%; }
        pre { background-color: #f5f5f5; padding: 15px; border-radius: 5px; white-space: pre-wrap; }
        button { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background-color: #45a049; }
        .return-button { background-color: #2196F3; }
        .return-button:hover { background-color: #0b7dda; }
        .create-ticket-button { background-color: #ff9800; }
        .create-ticket-button:hover { background-color: #e68a00; }
        #status { padding: 10px; margin-top: 10px; display: none; }
        .success { background-color: #dff0d8; color: #3c763d; }
        .error { background-color: #f2dede; color: #a94442; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        select { padding: 8px; border-radius: 4px; border: 1px solid #ddd; }
        #loading { display: none; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 2s linear infinite; display: inline-block; vertical-align: middle; margin-right: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
      </style>
      <script src="https://connect-cdn.atl-paas.net/all.js"></script>
    </head>
    <body>
      <h1>Générateur de cas de test pour {{ issue_key }}</h1>
      
      <div id="loading">
        <div class="spinner"></div> Chargement des détails de la user story...
      </div>
      
      <div id="content" style="display: none;">
        <div class="form-group">
          <label for="summary">Titre de la user story:</label>
          <input type="text" id="summary" name="summary" style="width: 100%; padding: 8px;" readonly>
        </div>
        
        <div class="form-group">
          <label for="description">Description:</label>
          <textarea id="description" name="description" rows="6" cols="60" readonly></textarea>
        </div>
        
        <div class="form-group">
          Format de test :
          <label><input type="radio" name="format" value="gherkin" checked> Gherkin</label>
          <label><input type="radio" name="format" value="action"> Actions / Résultats attendus</label>
        </div>
        
        <button id="generateButton">Générer un cas de test</button>
        
        <div id="result" style="margin-top: 20px; display: none;">
          <h2>Cas de test généré :</h2>
          <pre id="generatedTest"></pre>
          
          <div id="status"></div>
          
          <div class="form-group" id="issueTypeContainer" style="display: none;">
            <label for="issueType">Type de ticket Jira :</label>
            <select id="issueType"></select>
          </div>
          
          <p>
            <button class="return-button" onclick="copyAndReturn()">Copier et retourner à Jira</button>
            <button class="create-ticket-button" onclick="createJiraTicket()">Créer un ticket Jira</button>
          </p>
        </div>
      </div>
      
      <script>
        // Initialiser l'API AP
        AP.context.getContext(function(context) {
          const issueKey = "{{ issue_key }}";
          document.getElementById('loading').style.display = 'block';
          
          // Récupérer les détails de la story
          AP.request({
            url: '/rest/api/2/issue/' + issueKey + '?fields=summary,description',
            success: function(response) {
              const issue = JSON.parse(response);
              document.getElementById('summary').value = issue.fields.summary || '';
              document.getElementById('description').value = issue.fields.description || '';
              
              document.getElementById('loading').style.display = 'none';
              document.getElementById('content').style.display = 'block';
              
              // Charger les types de tickets
              fetch('/get_issue_types')
                .then(response => response.json())
                .then(data => {
                  if (data.issue_types && data.issue_types.length > 0) {
                    const issueTypeSelect = document.getElementById('issueType');
                    data.issue_types.forEach(type => {
                      const option = document.createElement('option');
                      option.value = type;
                      option.textContent = type;
                      issueTypeSelect.appendChild(option);
                    });
                    document.getElementById('issueTypeContainer').style.display = 'block';
                  }
                });
            },
            error: function(xhr, statusText, errorThrown) {
              document.getElementById('loading').style.display = 'none';
              alert('Erreur lors de la récupération des détails de la story: ' + statusText);
            }
          });
        });
        
        // Générer un cas de test
        document.getElementById('generateButton').addEventListener('click', function() {
          const summary = document.getElementById('summary').value;
          const description = document.getElementById('description').value;
          const format = document.querySelector('input[name="format"]:checked').value;
          const resultDiv = document.getElementById('result');
          const statusDiv = document.getElementById('status');
          
          resultDiv.style.display = 'none';
          document.getElementById('loading').style.display = 'block';
          
          fetch('/api/generate_test', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              summary: summary,
              description: description,
              format: format
            })
          })
          .then(response => response.json())
          .then(data => {
            document.getElementById('loading').style.display = 'none';
            if (data.success) {
              document.getElementById('generatedTest').textContent = data.generated_test;
              resultDiv.style.display = 'block';
            } else {
              statusDiv.textContent = 'Erreur: ' + data.message;
              statusDiv.className = 'error';
              statusDiv.style.display = 'block';
            }
          })
          .catch(error => {
            document.getElementById('loading').style.display = 'none';
            statusDiv.textContent = 'Erreur: ' + error;
            statusDiv.className = 'error';
            statusDiv.style.display = 'block';
          });
        });
        
        function copyAndReturn() {
          const generatedTest = document.getElementById('generatedTest').textContent;
          const returnUrl = "{{ jira_return_url }}";
          const statusDiv = document.getElementById('status');
          
          navigator.clipboard.writeText(generatedTest)
            .then(() => {
              statusDiv.textContent = 'Test copié dans le presse-papiers. Redirection...';
              statusDiv.className = 'success';
              statusDiv.style.display = 'block';
              
              setTimeout(() => {
                AP.navigator.navigateToIssue("{{ issue_key }}");
              }, 1500);
            })
            .catch(err => {
              statusDiv.textContent = 'Erreur lors de la copie: ' + err;
              statusDiv.className = 'error';
              statusDiv.style.display = 'block';
            });
        }
        
        function createJiraTicket() {
          const generatedTest = document.getElementById('generatedTest').textContent;
          const summary = document.getElementById('summary').value;
          const statusDiv = document.getElementById('status');
          const issueTypeSelect = document.getElementById('issueType');
          const issueType = issueTypeSelect ? issueTypeSelect.value : null;
          
          statusDiv.textContent = 'Création du ticket Jira en cours...';
          statusDiv.className = '';
          statusDiv.style.display = 'block';
          
          const payload = {
            content: generatedTest,
            summary: "Cas de test généré: " + summary.substring(0, 50) + "..."
          };
          
          if (issueType) {
            payload.issueType = issueType;
          }
          
          fetch('/create_jira_ticket', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
          })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              statusDiv.textContent = 'Ticket Jira créé avec succès: ' + data.ticket_key;
              statusDiv.className = 'success';
              
              const ticketLink = document.createElement('p');
              ticketLink.innerHTML = `<a href="https://{{ JIRA_BASE_URL }}/browse/${data.ticket_key}" target="_blank">Voir le ticket ${data.ticket_key}</a>`;
              statusDiv.appendChild(ticketLink);
            } else {
              statusDiv.textContent = 'Erreur lors de la création du ticket: ' + data.message;
              statusDiv.className = 'error';
            }
          })
          .catch(error => {
            statusDiv.textContent = 'Erreur: ' + error;
            statusDiv.className = 'error';
          });
        }
      </script>
    </body>
    </html>
    """
    
    return render_template_string(html_template,
                                  issue_key=issue_key,
                                  jira_return_url=jira_return_url,
                                  JIRA_BASE_URL=JIRA_BASE_URL)

if __name__ == "__main__":
    app.run(debug=True)