#!/bin/bash

# Création du dossier public/images pour l'icône
mkdir -p public/images

# Copie de l'icône SVG vers le format PNG
echo "Installation des dépendances nécessaires..."
pip install -r requirements.txt

# Vérification de l'existence du fichier .env
if [ ! -f .env ]; then
    echo "Création du fichier .env à partir de .env.example..."
    cp .env.example .env
    echo "Veuillez éditer le fichier .env avec vos informations d'identification Jira."
else
    echo "Le fichier .env existe déjà."
fi

# Conversion de l'icône SVG en PNG (si ImageMagick est installé)
if command -v convert &> /dev/null; then
    echo "Conversion de l'icône SVG en PNG..."
    convert -background none test-icon.svg public/images/test-icon.png
else
    echo "ImageMagick n'est pas installé. Veuillez créer manuellement un fichier PNG pour l'icône."
    echo "Ou installer ImageMagick avec 'apt-get install imagemagick' ou 'brew install imagemagick'"
fi

echo "Configuration terminée! Pour lancer l'application localement, exécutez:"
echo "flask run --debug"
echo ""
echo "N'oubliez pas de mettre à jour l'URL de base dans atlassian-connect.json avant le déploiement."