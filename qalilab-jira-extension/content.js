// Ce script s'exécute sur toutes les pages Jira correspondant au pattern dans le manifest

// Fonction pour extraire l'ID du ticket de l'URL
function getIssueKey() {
    const match = window.location.pathname.match(/\/browse\/([A-Z]+-\d+)/);
    return match ? match[1] : null;
  }
  
  // Fonction pour ajouter le bouton QaliLab à l'interface Jira
  function addQaliLabButton() {
    const issueKey = getIssueKey();
    if (!issueKey) return; // Ne rien faire si nous ne sommes pas sur une page de ticket
    
    // Chercher différents emplacements possibles pour ajouter le bouton
    // 1. L'en-tête du ticket (ancien)
    const headerOld = document.querySelector('#jira-issue-header');
    // 2. L'en-tête du ticket (nouveau)
    const headerNew = document.querySelector('[data-testid="issue-view-header"]');
    // 3. Les actions du ticket
    const actionsContainer = document.querySelector('[data-testid="issue-actions-container"]');
    
    // Créer le bouton s'il n'existe pas déjà
    if (!document.getElementById('qalilab-btn')) {
      const button = document.createElement('a');
      button.id = 'qalilab-btn';
      button.className = 'qalilab-button';
      button.href = 'https://qalilab-ai.onrender.com/jira-panel?issueKey=' + issueKey;
      button.target = '_blank';
      button.title = 'Générer des cas de test avec QaliLab AI';
      
      // Ajouter l'icône et le texte
      button.innerHTML = '<span class="qalilab-icon">🧪</span> QaliLab AI';
      
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
  
  // Fonction pour ouvrir QaliLab AI dans un nouvel onglet
  function openQaliLab() {
    const issueKey = getIssueKey();
    if (issueKey) {
      window.open('https://qalilab-ai.onrender.com/jira-panel?issueKey=' + issueKey, '_blank');
    } else {
      alert('Veuillez naviguer vers une page de ticket Jira pour utiliser cet outil.');
    }
  }
  
  // Écouter les messages du script d'arrière-plan
  chrome.runtime.onMessage.addListener((message) => {
    if (message.action === "openQaliLab") {
      openQaliLab();
    }
  });
  
  // Exécuter au chargement de la page
  addQaliLabButton();
  
  // Observer les changements DOM pour les applications SPA (Single Page Application)
  const observer = new MutationObserver((mutations) => {
    // Vérifier si nous sommes toujours sur la même page de ticket
    const currentIssueKey = getIssueKey();
    if (currentIssueKey && !document.getElementById('qalilab-btn')) {
      addQaliLabButton();
    }
  });
  
  // Démarrer l'observation
  observer.observe(document.body, { childList: true, subtree: true });
  
  // Afficher un message dans la console
  console.log('QaliLab AI: Extension chargée');