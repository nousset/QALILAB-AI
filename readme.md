# Générateur de Cas de Test pour Jira

Cette application Flask s'intègre à Jira pour générer automatiquement des cas de test à partir des user stories existantes.

## Fonctionnalités

- Bouton intégré directement dans l'interface Jira pour les user stories
- Génération de cas de test au format Gherkin ou Actions/Résultats attendus
- Création automatique de tickets de test dans Jira
- API de génération de test basée sur Mistral-7B

## Structure des fichiers

- `app.py` - Application Flask principale
- `atlassian-connect.json` - Descripteur pour l'intégration avec Jira
- `requirements.txt` - Dépendances Python
- `Dockerfile` - Pour le déploiement conteneurisé
- `render.yaml` - Configuration pour le déploiement sur Render

## Configuration

### Variables d'environnement

Copiez le fichier `.env.example` vers `.env` et remplissez les variables suivantes :

```
JIRA_BASE_URL=votre-instance.atlassian.net
JIRA_EMAIL=votre-email@example.com
JIRA_API_TOKEN=votre-token-api-jira
JIRA_PROJECT_KEY=VOTRE_PROJET
API_URL=url-de-votre-api-de-generation
```

## Déploiement sur Render

### Prérequis

- Un compte [Render](https://render.com)
- Un compte administrateur Jira

### Étapes de déploiement

1. Créez un nouveau Web Service sur Render
2. Connectez votre repository Git
3. Render détectera automatiquement la configuration depuis `render.yaml`
4. Configurez les variables d'environnement dans le dashboard Render
5. Une fois déployé, notez l'URL de votre application (ex: `https://test-case-generator.onrender.com`)

### Configuration du descripteur Jira

1. Modifiez le fichier `atlassian-connect.json` et remplacez `"baseUrl": "https://votre-application.onrender.com"` par l'URL de votre application Render
2. Redéployez l'application

### Installation dans Jira

1. Dans Jira, allez dans **Paramètres** > **Apps** > **Gérer les apps**
2. Cliquez sur **Télécharger une app**
3. Entrez l'URL de votre application suivie de `/atlassian-connect` (ex: `https://test-case-generator.onrender.com/atlassian-connect`)
4. Suivez les instructions d'installation

## Utilisation

1. Naviguez vers une user story dans Jira
2. Cliquez sur le bouton "Générer un cas de test" dans les outils de l'issue
3. L'application récupérera automatiquement les détails de la user story
4. Choisissez le format de test souhaité (Gherkin ou Actions/Résultats)
5. Cliquez sur "Générer un cas de test"
6. Une fois le test généré, vous pouvez :
   - Copier le contenu et retourner à Jira
   - Créer automatiquement un ticket de test dans Jira

## Développement local

Pour exécuter l'application localement :

```bash
# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement (ou utiliser un fichier .env)
export JIRA_BASE_URL=votre-instance.atlassian.net
export JIRA_EMAIL=votre-email@example.com
export JIRA_API_TOKEN=votre-token-api
export JIRA_PROJECT_KEY=VOTRE_PROJET
export API_URL=url-de-votre-api

# Lancer l'application
flask run --debug
```

Pour tester l'intégration Jira en local, vous pouvez utiliser un service comme ngrok pour exposer votre application locale à Internet.

## Support

Pour toute question ou problème, veuillez créer une issue dans ce repository.