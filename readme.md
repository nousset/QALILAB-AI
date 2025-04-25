# Générateur de Cas de Test pour Jira

Cette application permet de générer automatiquement des cas de test à partir d'user stories dans Jira. Elle s'intègre directement dans Jira grâce à Atlassian Connect et peut être hébergée sur Render.

## Fonctionnalités

- Intégration directe dans Jira via un bouton sur chaque user story
- Génération de cas de test au format Gherkin ou Actions/Résultats attendus
- Création automatique de tickets Jira pour les cas de test générés
- Interface web indépendante pour les utilisateurs qui préfèrent ne pas utiliser l'intégration Jira

## Prérequis

- Un compte Render
- Un compte Jira Cloud
- Un token API Jira

## Configuration

### 1. Configuration des variables d'environnement

Créez un fichier `.env` à partir du modèle `.env.example` :

```bash
cp .env.example .env
```

Remplissez les valeurs suivantes :

- `JIRA_BASE_URL` : URL de votre instance Jira Cloud (ex: votre-instance.atlassian.net)
- `JIRA_EMAIL` : Email de votre compte Jira
- `JIRA_API_TOKEN` : Token API généré dans les paramètres de sécurité de votre compte Atlassian
- `JIRA_PROJECT_KEY` : Clé du projet Jira où vous souhaitez créer les tickets de test

### 2. Déploiement sur Render

1. Connectez-vous à [Render](https://render.com)
2. Créez un nouveau "Web Service"
3. Connectez votre dépôt GitHub/GitLab contenant le code
4. Configurez les paramètres comme suit :
   - **Name**: nom-de-votre-choix
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Ajoutez les variables d'environnement depuis votre fichier `.env`
6. Déployez l'application

### 3. Configuration de l'add-on Jira

Une fois l'application déployée sur Render, vous devez installer l'add-on dans Jira :

1. Connectez-vous à votre instance Jira Cloud
2. Allez dans "Paramètres" > "Applications" > "Gérer les applications"
3. Cliquez sur "Télécharger l'application"
4. Entrez l'URL de l'application déployée + `/atlassian-connect.json` (ex: https://votre-app.onrender.com/atlassian-connect.json)
5. Suivez les instructions d'installation

## Utilisation

Une fois l'add-on installé, vous verrez un bouton "Générer Cas de Test" dans le panneau latéral droit de chaque issue Jira.

1. Ouvrez une user story dans Jira
2. Cliquez sur le bouton "Géné