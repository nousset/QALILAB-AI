from dotenv import load_dotenv
import os
import re
import time
from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
import requests
import json
import logging
from datetime import datetime

# Configuration du logging améliorée
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                   handlers=[logging.StreamHandler()])
logger = logging.getLogger("qalilab-ai")

# Chargement des variables d'environnement
load_dotenv()

# Configuration
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "amaniconsulting.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "ACD")
API_URL = os.getenv("API_URL", "https://remark-flags-unlike-friday.trycloudflare.com/v1/chat/completions/v1/chat/completions")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://qalilab-ai.onrender.com")

logger.info(f"Démarrage de l'application QaliLab AI")
logger.info(f"URL de base de l'application: {APP_BASE_URL}")
logger.info(f"URL de base Jira: {JIRA_BASE_URL}")

app = Flask(__name__)

# Ajouter les headers CORS et de sécurité à toutes les réponses
@app.after_request
def add_headers(response):
    """Ajoute les headers nécessaires pour l'intégration avec Jira Cloud"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    
    # Headers pour permettre l'affichage dans des iframes Jira
    response.headers['X-Frame-Options'] = 'ALLOW-FROM https://*.atlassian.net'
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' *.atlassian.net"
    
    return response

def generate_response(prompt, max_tokens=206):
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "mistral-7b-instruct-v0.3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    try:
        # Augmente le timeout pour éviter les erreurs 524
        response = requests.post(API_URL, headers=headers, json=payload, timeout=180)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            logger.error(f"Erreur API: {response.status_code} - {response.text}")
            return f"Erreur API: {response.status_code}"
    except Exception as e:
        logger.error(f"Exception lors de l'appel API: {str(e)}")
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

def extract_issue_key_from_url(url):
    """Extrait la clé d'issue de l'URL de retour Jira"""
    if not url:
        return ""
    
    match = re.search(r'/browse/([A-Z]+-\d+)', url)
    if match:
        return match.group(1)
    return ""

def update_jira_story(issue_key, updated_description):
    """Met à jour la description d'une user story dans Jira"""
    if not issue_key or not issue_key.strip():
        logger.error("Clé d'issue manquante ou invalide")
        return False, "Clé d'issue manquante ou invalide"
    
    logger.info(f"Tentative de mise à jour pour l'issue: {issue_key}")
    
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
    payload = {
        "fields": {
            "description": updated_description
        }
    }
    
    try:
        logger.info(f"Envoi de la requête à: {api_endpoint}")
        logger.info(f"Payload: {json.dumps(payload)}")
        
        response = requests.put(
            api_endpoint, 
            json=payload, 
            auth=auth,
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"Statut de la réponse: {response.status_code}")
        logger.info(f"Contenu de la réponse: {response.text[:200]}...")  # Tronquer pour éviter des logs trop longs
        
        if response.status_code in [200, 204]:
            return True, "Description mise à jour avec succès"
        else:
            error_msg = f"Erreur lors de la mise à jour: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"Exception lors de la mise à jour: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

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
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des types d'issues: {str(e)}")
        return []
    
def add_comment_button_to_issue(issue_key):
    """Ajoute un commentaire avec un bouton vers votre application"""
    
    api_endpoint = f"https://{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    
    button_link = f"{APP_BASE_URL}/jira-panel?issueKey={issue_key}"
    
    # Utiliser le formatage Atlassian pour créer un bouton plus visible
    comment = {
        "body": (
            "h2. QaliLab AI - Générateur de Tests\n\n"
            "{panel:title=Générateur de cas de test|borderColor=#0052CC|titleBGColor=#0052CC|titleColor=white|bgColor=#FFFFFF}\n"
            "Utilisez QaliLab AI pour générer automatiquement des cas de test pour cette User Story.\n\n"
            "{button:Générer des cas de test|" + button_link + "}\n\n"
            "_(Cliquez sur le bouton ci-dessus pour ouvrir l'outil QaliLab AI)_\n"
            "{panel}"
        )
    }
    
    try:
        response = requests.post(api_endpoint, json=comment, auth=auth)
        if response.status_code == 201:
            return True, "Commentaire ajouté avec succès"
        else:
            error_msg = f"Erreur: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"Exception: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

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
        "JIRA_PROJECT_KEY": bool(JIRA_PROJECT_KEY),
        "APP_BASE_URL": bool(APP_BASE_URL)
    }
    
    # Vérifie les templates
    templates_dir = os.path.exists('templates')
    index_template = os.path.exists('templates/index.html') if templates_dir else False
    
    status = {
        "app_running": True,
        "app_version": "1.2",  # Mise à jour de la version
        "server_time": datetime.now().isoformat(),
        "descriptor_exists": descriptor_exists,
        "descriptor_content": descriptor_content,
        "env_vars": env_vars,
        "templates_directory_exists": templates_dir,
        "index_template_exists": index_template,
        "app_url": APP_BASE_URL,
        "descriptor_url": f"{APP_BASE_URL}/atlassian-connect.json"
    }
    
    return jsonify(status)

@app.route("/update_jira_story", methods=["POST"])
def handle_update_story():
    """Endpoint pour mettre à jour une user story dans Jira"""
    data = request.json
    issue_key = data.get("issueKey", "").strip()
    updated_description = data.get("description", "")
    
    logger.info(f"Requête de mise à jour reçue pour l'issue: {issue_key}")
    
    if not issue_key or not updated_description:
        error_msg = "Paramètres manquants: issueKey et description requis"
        logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 400
    
    # Validation supplémentaire pour la clé d'issue
    if not re.match(r'^[A-Z]+-\d+$', issue_key):
        error_msg = f"Format de clé d'issue invalide: {issue_key}"
        logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 400
    
    success, message = update_jira_story(issue_key, updated_description)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route("/get_issue_types", methods=["GET"])
def handle_get_issue_types():
    issue_types = get_issue_types()
    return jsonify({"issue_types": issue_types})

@app.route("/atlassian-connect.json")
@app.route("/atlassian-connect.json")
def descriptor():
    """Fournit le descripteur atlassian-connect.json conforme aux standards Jira Cloud"""
    logger.info("Demande du descripteur reçue!")
    
    # Descripteur conforme optimisé pour Jira Cloud
    descriptor = {
        "name": "QaliLab AI",
        "description": "Générateur de cas de test pour les user stories Jira",
        "key": "com.amaniconsulting.qalilab-ai",
        "baseUrl": APP_BASE_URL,
        "vendor": {
            "name": "Amani Consulting",
            "url": f"https://{JIRA_BASE_URL}"
        },
        "authentication": {
            "type": "jwt"
        },
        "apiVersion": 1,
        "lifecycle": {
            "installed": "/installed",
            "uninstalled": "/uninstalled"
        },
        "scopes": [
            "read",
            "write"
        ],
        "modules": {
            "webItems": [
                {
                    "key": "qalilab-tools-button",
                    "name": {
                        "value": "Générer des tests"
                    },
                    "location": "jira.issue.tools",
                    "url": "/jira-panel?issueKey={issue.key}",
                    "target": {
                        "type": "dialog",
                        "options": {
                            "width": "85%",
                            "height": "85%"
                        }
                    },
                    "tooltip": {
                        "value": "Générer des cas de test pour cette User Story"
                    },
                    "conditions": [
                        {
                            "condition": "user_is_logged_in"
                        }
                    ]
                },
                {
                    "key": "qalilab-header-button",
                    "name": {
                        "value": "Générer des tests"
                    },
                    "location": "jira.issue.header-actions",
                    "url": "/jira-panel?issueKey={issue.key}",
                    "tooltip": {
                        "value": "Générer des cas de test pour cette User Story"
                    },
                    "conditions": [
                        {
                            "condition": "user_is_logged_in"
                        }
                    ]
                }
            ],
            "webPanels": [
                {
                    "key": "qalilab-right-panel",
                    "name": {
                        "value": "QaliLab AI"
                    },
                    "location": "atl.jira.view.issue.right.context",
                    "url": "/jira-panel?issueKey={issue.key}",
                    "layout": {
                        "width": "100%",
                        "height": "100%"
                    },
                    "conditions": [
                        {
                            "condition": "user_is_logged_in"
                        }
                    ]
                }
            ],
            "generalPages": [
                {
                    "key": "qalilab-main-page",
                    "name": {
                        "value": "QaliLab AI"
                    },
                    "url": "/",
                    "location": "jira.top.navigation.bar",
                    "conditions": [
                        {
                            "condition": "user_is_logged_in"
                        }
                    ]
                }
            ]
        },
        "enableLicensing": False  # Corrigé : false -> False (majuscule en Python)
    }
    
    # Écrire également le descripteur dans un fichier pour référence
    with open('atlassian-connect.json', 'w') as f:
        json.dump(descriptor, f, indent=2)
    
    logger.info(f"Descripteur servi: {json.dumps(descriptor)[:200]}...")
    return jsonify(descriptor)

@app.route("/jira-panel")
def jira_panel():
    """Affiche le panneau dans Jira"""
    issue_key = request.args.get("issueKey", "")
    summary = request.args.get("summary", "")
    description = request.args.get("description", "")
    language = request.args.get("language", "fr")
    
    logger.info(f"Requête jira-panel reçue pour l'issue {issue_key}")
    
    # URL pour retourner à l'issue Jira
    jira_return_url = f"https://{JIRA_BASE_URL}/browse/{issue_key}"
    
    # Construire l'URL avec les paramètres - utiliser issueKey pour rester cohérent
    redirect_url = url_for('index', 
                          story=description,
                          issueKey=issue_key,
                          returnUrl=jira_return_url,
                          language=language,
                          autoGenerate="true")
    
    logger.info(f"Redirection vers: {redirect_url}")
    return redirect(redirect_url)

@app.route("/installed", methods=["POST"])
def installed():
    """Gère l'installation de l'application"""
    logger.info("Application installée!")
    # Loguer les données reçues pour le débogage
    try:
        data = request.json
        logger.info(f"Données d'installation reçues: {json.dumps(data)[:200]}...")
    except Exception as e:
        logger.warning(f"Impossible de parser les données d'installation: {str(e)}")
    
    return jsonify({"status": "ok", "message": "Application installée avec succès"})

@app.route("/uninstalled", methods=["POST"])
def uninstalled():
    """Gère la désinstallation de l'application"""
    logger.info("Application désinstallée!")
    return jsonify({"status": "ok", "message": "Application désinstallée avec succès"})

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
        "APP_BASE_URL": APP_BASE_URL
    }
    return jsonify(env_status)

@app.route("/test-jira-auth", methods=["GET"])
def test_jira_auth():
    """Route pour tester l'authentification Jira"""
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    test_url = f"https://{JIRA_BASE_URL}/rest/api/2/myself"
    
    try:
        response = requests.get(test_url, auth=auth)
        if response.status_code == 200:
            user_data = response.json()
            return jsonify({
                "success": True,
                "message": "Authentification réussie",
                "user": {
                    "name": user_data.get("displayName"),
                    "email": user_data.get("emailAddress")
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Échec de l'authentification: {response.status_code}",
                "details": response.text
            }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erreur lors du test d'authentification: {str(e)}"
        }), 500

@app.route("/force-install")
def force_install():
    """Force la création d'un nouveau descripteur et guide l'utilisateur pour la réinstallation"""
    try:
        # Générer un nouveau descripteur
        key_timestamp = int(time.time())
        new_descriptor = {
            "name": "QaliLab AI Test",
            "description": "Test d'installation pour QaliLab AI",
            "key": f"com.amaniconsulting.qalilab-ai-test-{key_timestamp}",
            "baseUrl": APP_BASE_URL,
            "vendor": {
                "name": "Amani Consulting",
                "url": f"https://{JIRA_BASE_URL}"
            },
            "authentication": {
                "type": "none"  # Simplifier pour le test
            },
            "apiVersion": 1,
            "lifecycle": {
                "installed": "/installed",
                "uninstalled": "/uninstalled"
            },
            "scopes": [
                "read"
            ],
            "modules": {
                "webItems": [
                    {
                        "key": "test-button",
                        "name": {
                            "value": "Test QaliLab AI"
                        },
                        "location": "jira.issue.header-actions",
                        "url": "/jira-panel?issueKey={issue.key}&language=fr",
                        "weight": 1000
                    }
                ],
                "generalPages": [
                    {
                        "key": "test-page",
                        "name": {
                            "value": "Test Page"
                        },
                        "url": "/",
                        "location": "system.top.navigation.bar"
                    }
                ]
            },
            "context": "jira"
        }
        
        # Sauvegarder comme version de test
        test_descriptor_path = 'test-descriptor.json'
        with open(test_descriptor_path, 'w') as f:
            json.dump(new_descriptor, f, indent=2)
        
        install_url = f"{APP_BASE_URL}/test-descriptor.json"
        
        # Créer une page HTML avec les instructions
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>QaliLab AI - Force Install</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-5">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h4>QaliLab AI - Installation forcée</h4>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-info">
                            <p>Un nouveau descripteur de test a été créé. Suivez ces étapes pour installer l'application de test :</p>
                        </div>
                        
                        <ol class="list-group list-group-numbered mb-4">
                            <li class="list-group-item">Accédez à l'administration Jira</li>
                            <li class="list-group-item">Allez dans "Gérer les applications" > "Rechercher des applications"</li>
                            <li class="list-group-item">Cliquez sur "Télécharger une application"</li>
                            <li class="list-group-item">Collez l'URL suivante : <code class="bg-light p-2">{install_url}</code></li>
                            <li class="list-group-item">Suivez les instructions pour installer l'application</li>
                            <li class="list-group-item">Retournez sur un ticket Jira pour vérifier si le bouton "Test QaliLab AI" apparaît</li>
                        </ol>
                        
                        <div class="d-flex justify-content-between">
                            <a href="{install_url}" target="_blank" class="btn btn-primary">Voir le descripteur de test</a>
                            <a href="/check-app-status" class="btn btn-secondary">Vérifier le statut de l'application</a>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-descriptor.json")
def test_descriptor():
    """Sert le descripteur de test"""
    try:
        with open('test-descriptor.json', 'r') as f:
            descriptor = json.load(f)
        return jsonify(descriptor)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/direct-test")
def direct_test():
    """Page de test direct de l'application"""
    issue_key = request.args.get("issueKey", "ACD-5330")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>QaliLab AI - Test Direct</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4>QaliLab AI - Test de fonctionnement</h4>
                </div>
                <div class="card-body">
                    <div class="alert alert-success">
                        <p><strong>✅ Succès :</strong> Si vous voyez cette page, l'application fonctionne correctement.</p>
                    </div>
                    
                    <h5>Tests disponibles :</h5>
                    <ul class="list-group mb-4">
                        <li class="list-group-item">
                            <a href="/jira-panel?issueKey={issue_key}" target="_blank">
                                Ouvrir le panneau Jira pour {issue_key}
                            </a>
                        </li>
                        <li class="list-group-item">
                            <a href="/check-app-status" target="_blank">
                                Vérifier le statut de l'application
                            </a>
                        </li>
                        <li class="list-group-item">
                            <a href="/test-jira-auth" target="_blank">
                                Tester l'authentification Jira
                            </a>
                        </li>
                        <li class="list-group-item">
                            <a href="/force-install" target="_blank">
                                Créer une installation de test
                            </a>
                        </li>
                    </ul>
                    
                    <h5>Diagnostic de l'intégration Jira :</h5>
                    <p>Si l'application fonctionne correctement ici mais que l'intégration avec Jira pose problème :</p>
                    <ol>
                        <li>Vérifiez que vous utilisez bien Jira Cloud (et non Jira Server)</li>
                        <li>Assurez-vous que l'application est correctement installée dans Jira</li>
                        <li>Essayez de désinstaller puis réinstaller l'application</li>
                        <li>Vérifiez que votre utilisateur a les permissions nécessaires</li>
                    </ol>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/", methods=["GET", "POST"])
def index():
    """Page d'accueil de l'application"""
    try:
        story_text = ""
        format_choice = "gherkin"
        language_choice = "fr"  # Français par défaut
        generated_test = None
        jira_return_url = None
        issue_key = ""
        
        # Récupérer les paramètres
        if request.method == "GET":
            story_text = request.args.get("story", "").strip()
            format_choice = request.args.get("format", "gherkin")
            language_choice = request.args.get("language", "fr")
            jira_return_url = request.args.get("returnUrl", "")
            auto_generate = request.args.get("autoGenerate", "false").lower() == "true"
            
            # Récupérer issueKey ou l'extraire de l'URL de retour si nécessaire
            issue_key = request.args.get("issueKey", "")
            if not issue_key and jira_return_url:
                # Essayer d'extraire l'ID de l'issue depuis l'URL de retour
                issue_key = extract_issue_key_from_url(jira_return_url)
                logger.info(f"Issue key extraite de l'URL de retour: {issue_key}")
            
            logger.info(f"Issue key finale: {issue_key}")
            
            if story_text and auto_generate:
                try:
                    prompt = build_prompt(story_text, format_choice, language_choice)
                    generated_test = generate_response(prompt, max_tokens=512)
                except Exception as e:
                    logger.error(f"Erreur lors de la génération du test: {str(e)}")
                    generated_test = f"Erreur lors de la génération du test: {str(e)}"
        
        # Pour POST
        elif request.method == "POST":
            story_text = request.form.get("story", "").strip()
            format_choice = request.form.get("format", "gherkin")
            language_choice = request.form.get("language", "fr")
            jira_return_url = request.form.get("returnUrl", "")
            
            # Récupérer issueKey ou l'extraire de l'URL de retour
            issue_key = request.form.get("issueKey", "")
            if not issue_key and jira_return_url:
                issue_key = extract_issue_key_from_url(jira_return_url)
                logger.info(f"Issue key extraite de l'URL de retour (POST): {issue_key}")
            
            if story_text:
                try:
                    prompt = build_prompt(story_text, format_choice, language_choice)
                    generated_test = generate_response(prompt, max_tokens=512)
                except Exception as e:
                    logger.error(f"Erreur lors de la génération du test: {str(e)}")
                    generated_test = f"Erreur lors de la génération du test: {str(e)}"
        
        # Récupération des types d'issues en toute sécurité
        issue_types = []
        try:
            issue_types = get_issue_types()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des types d'issues: {str(e)}")
        
        # Vérifier si le template existe
        if os.path.exists('templates/index.html'):
            return render_template("index.html",
                                story=story_text,
                                format_choice=format_choice,
                                language_choice=language_choice,
                                generated_test=generated_test,
                                jira_return_url=jira_return_url,
                                issue_key=issue_key,
                                JIRA_BASE_URL=JIRA_BASE_URL,
                                APP_BASE_URL=APP_BASE_URL,
                                issue_types=issue_types)
        else:
            # Réponse de secours si le template n'existe pas
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>QaliLab AI</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; }}
                    .alert {{ background-color: #f8d7da; padding: 15px; border-radius: 4px; margin-bottom: 20px; }}
                    .info {{ background-color: #d1ecf1; padding: 15px; border-radius: 4px; }}
                </style>
            </head>
            <body>
                <h1>QaliLab AI</h1>
                <div class="info">
                    <p>L'application QaliLab AI est fonctionnelle.</p>
                    <p>Template non trouvé. Veuillez vous assurer que le dossier templates et le fichier index.html existent.</p>
                    <p>Paramètres reçus :</p>
                    <ul>
                        <li>Issue Key: {issue_key}</li>
                        <li>Format: {format_choice}</li>
                        <li>Langue: {language_choice}</li>
                    </ul>
                </div>
            </body>
            </html>
            """
    except Exception as e:
        logger.error(f"Erreur dans la route index: {str(e)}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>QaliLab AI - Erreur</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .error {{ background-color: #f8d7da; padding: 15px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <h1>QaliLab AI</h1>
            <div class="error">
                <h2>Une erreur est survenue</h2>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """

if __name__ == "__main__":
    # Créer le dossier templates s'il n'existe pas
    if not os.path.exists('templates'):
        os.makedirs('templates')
        logger.info("Dossier 'templates' créé")
    
    # Écrire le fichier de descripteur à jour
    try:
        # Utiliser le contexte d'application pour générer le descripteur
        with app.app_context():
            # Créer directement le descripteur au lieu d'appeler la route
            desc_content = descriptor()
            logger.info("Fichier de descripteur généré avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de la génération du fichier de descripteur: {str(e)}")
    
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Démarrage du serveur sur le port {port}")
    app.run(host="0.0.0.0", port=port)