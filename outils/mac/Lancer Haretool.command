#!/bin/bash
# Lance Haretool avec le droit de lire le reseau (capture des paquets du jeu).
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine "Haretool.app" 2>/dev/null
echo "Haretool a besoin de ton mot de passe de session pour lire le reseau du jeu."
sudo "./Haretool.app/Contents/MacOS/HaretoolApp" &
sleep 2
osascript -e 'tell application "Terminal" to close front window' >/dev/null 2>&1 &
