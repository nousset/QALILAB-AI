// Ce script gère les clics sur l'icône de l'extension
chrome.action.onClicked.addListener((tab) => {
    // Envoyer un message au script de contenu
    chrome.tabs.sendMessage(tab.id, { action: "openQaliLab" });
  });