// Fonction pour extraire l'ID du ticket de l'URL
function getIssueKey() {
  const match = window.location.pathname.match(/\/browse\/([A-Z]+-\d+)/);
  return match ? match[1] : null;
}

// Fonction pour attendre qu'un élément soit présent
function waitForElement(selector, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const element = document.querySelector(selector);
    if (element) {
      resolve(element);
      return;
    }

    const observer = new MutationObserver(() => {
      const element = document.querySelector(selector);
      if (element) {
        observer.disconnect();
        resolve(element);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error('Timeout waiting for element'));
    }, timeout);
  });
}

// Fonction pour extraire la description du ticket
async function getIssueDescription() {
  // Sélecteurs possibles pour la description
  const descriptionSelectors = [
    // Pour la nouvelle interface Jira
    '[data-testid="issue.views.field.rich-text.description"] .ak-renderer-document',
    '[data-testid="issue.views.field.rich-text.description"] p',
    '.ak-renderer-document p',
    
    // Pour l'ancienne interface Jira
    '#description-val .user-content-block',
    '#description .user-content-block p',
    
    // Pour les descriptions plus spécifiques aux user stories
    '.user-content-block [data-test-id="description"]',
    '.issue-body-content .description .value',
    
    // Sélecteurs génériques
    '.description-content',
    '#description-field',
    '[name="description"]'
  ];

  try {
    // Essayer chaque sélecteur avec attente
    for (const selector of descriptionSelectors) {
      try {
        const element = await waitForElement(selector, 2000);
        if (element && element.textContent.trim()) {
          // Nettoyer le texte pour ne garder que le contenu de la description
          let description = element.textContent.trim();
          
          // Supprimer les éléments indésirables comme les tooltips, etc.
          description = description.replace(/^\s*Description\s*/i, '');
          description = description.replace(/^\s*User Story\s*/i, '');
          
          // Retourner la description nettoyée
          console.log('QaliLab AI: Description trouvée:', description.substring(0, 100) + '...');
          return description;
        }
      } catch (e) {
        // Continuer avec le sélecteur suivant
      }
    }
    
    // Si aucune description n'est trouvée, retourner null
    console.log('QaliLab AI: Aucune description trouvée');
    return null;
  } catch (error) {
    console.error('QaliLab AI: Erreur lors de l\'extraction de la description:', error);
    return null;
  }
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
  
  // Si une description est trouvée, l'utiliser, sinon utiliser l'ID du ticket
  const storyText = description || issueKey;
  
  const params = new URLSearchParams({
    story: storyText,
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
    button.addEventListener('click', async function(e) {
      e.preventDefault();
      
      try {
        // Extraire la description avant d'ouvrir le lien
        const description = await getIssueDescription();
        const url = buildQalilabUrl(issueKey, description);
        
        console.log('QaliLab AI: URL générée:', url);
        window.open(url, '_blank');
      } catch (error) {
        console.error('QaliLab AI: Erreur lors de la génération de l\'URL:', error);
        // Fallback: ouvrir avec juste l'ID du ticket
        const fallbackUrl = buildQalilabUrl(issueKey, null);
        window.open(fallbackUrl, '_blank');
      }
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

// Fonction pour initialiser l'extension
function init() {
  const issueKey = getIssueKey();
  if (issueKey) {
    addQaliLabButton();
    
    // Observer les changements dans l'interface
    const observer = new MutationObserver((mutations) => {
      // Vérifier si le bouton existe toujours
      if (!document.getElementById('qalilab-btn')) {
        addQaliLabButton();
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }
}

// Écouter les messages du script d'arrière-plan
chrome.runtime.onMessage.addListener(async (message) => {
  if (message.action === "openQaliLab") {
    const issueKey = getIssueKey();
    if (issueKey) {
      try {
        const description = await getIssueDescription();
        window.open(buildQalilabUrl(issueKey, description), '_blank');
      } catch (error) {
        console.error('QaliLab AI: Erreur:', error);
        window.open(buildQalilabUrl(issueKey, null), '_blank');
      }
    } else {
      alert('Veuillez naviguer vers une page de ticket Jira pour utiliser cet outil.');
    }
  }
});

// Initialiser l'extension
init();

// Log pour le débogage
console.log('QaliLab AI: Extension chargée avec extraction de description');