// Fonction pour extraire l'ID du ticket de l'URL
function getIssueKey() {
  const match = window.location.pathname.match(/\/browse\/([A-Z]+-\d+)/);
  return match ? match[1] : null;
}

// Fonction pour extraire la description du ticket
function getIssueDescription() {
  // Essayez différents sélecteurs pour la description
  const descriptionSelectors = [
    '[data-testid="issue.views.issue-base.foundation.description.text"]',
    '.issue-body-content .user-content-block .content',
    '.user-content-block',
    '#description-val',
    '.user-content-block p'
  ];

  for (const selector of descriptionSelectors) {
    const element = document.querySelector(selector);
    if (element && element.textContent.trim()) {
      return element.textContent.trim().substring(0, 500); // Limite à 500 caractères
    }
  }
  
  // Si la description n'est pas trouvée, retourner null
  return null;
}

// Fonction pour encoder une chaîne pour une URL
function encodeForUrl(str) {
  if (!str) return '';
  return encodeURIComponent(str.trim());
}

// Fonction pour construire l'URL complète avec tous les paramètres
function buildQalilabUrl(issueKey, description) {
  const baseUrl = 'https://qalilab-ai.onrender.com/';
  const returnUrl = `https://amaniconsulting.atlassian.net/browse/${issueKey}`;
  
  const params = new URLSearchParams({
    story: description || issueKey,
    format: 'gherkin',
    autoGenerate: 'true',
    returnUrl: returnUrl,
    issueKey: issueKey
  });
  
  return `${baseUrl}?${params.toString()}`;
}

// Fonction pour ajouter le bouton QaliLab à l'interface Jira
function addQaliLabButton() {
  const issueKey = getIssueKey();
  if (!issueKey) return; // Ne rien faire si nous ne sommes pas sur une page de ticket
  
  // Chercher différents emplacements possibles pour ajouter le bouton
  const headerOld = document.querySelector('#jira-issue-header');
  const headerNew = document.querySelector('[data-testid="issue-view-header"]');
  const actionsContainer = document.querySelector('[data-testid="issue-actions-container"]');
  
  // Créer le bouton s'il n'existe pas déjà
  if (!document.getElementById('qalilab-btn')) {
    const button = document.createElement('a');
    button.id = 'qalilab-btn';
    button.className = 'qalilab-button';
    button.target = '_blank';
    button.title = 'Générer des cas de test avec QaliLab AI';
    
    // Ajouter l'icône et le texte
    button.innerHTML = '<span class="qalilab-icon">🧪</span> QaliLab AI';
    
    // Mettre à jour le lien à chaque clic pour capturer le contenu actuel
    button.addEventListener('click', function(e) {
      e.preventDefault();
      
      // Extraire la description avant d'ouvrir le lien
      const description = getIssueDescription();
      const url = buildQalilabUrl(issueKey, description);
      
      console.log('QaliLab AI: URL générée:', url);
      window.open(url, '_blank');
    });
    
    // Trouver le meilleur emplacement pour ajouter le bouton
    if (headerOld) {
      headerOld.appendChild(button);
    } else if (headerNew) {
      headerNew.appendChild(button);
    } else if (actionsContainer) {
      actionsContainer.appendChild(button);
    } else {
      // Si aucun emplacement idéal n'est trouvé, ajouter un bouton flottant
      button.classList.add('qalilab-floating');
      document.body.appendChild(button);
    }
    
    console.log('QaliLab AI: Bouton ajouté avec succès');
  }
}

// Observer les changements DOM pour capturer le contenu dynamiquement
const descriptionObserver = new MutationObserver((mutations) => {
  // Mettre à jour le bouton si nécessaire
  addQaliLabButton();
});

// Fonction pour initialiser l'extension
function init() {
  const issueKey = getIssueKey();
  if (issueKey) {
    addQaliLabButton();
    
    // Observer les changements dans le contenu du ticket
    descriptionObserver.observe(document.body, { 
      childList: true, 
      subtree: true,
      characterData: true 
    });
  }
}

// Écouter les messages du script d'arrière-plan
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === "openQaliLab") {
    const issueKey = getIssueKey();
    const description = getIssueDescription();
    if (issueKey) {
      window.open(buildQalilabUrl(issueKey, description), '_blank');
    } else {
      alert('Veuillez naviguer vers une page de ticket Jira pour utiliser cet outil.');
    }
  }
});

// Initialiser l'extension
init();

// Log pour le débogage
console.log('QaliLab AI: Extension chargée avec support URL dynamique');