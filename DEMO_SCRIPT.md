# Script de démo — Tunisna (3-4 minutes)

Basé sur ce qui est réellement construit : un classifieur XGBoost **réellement
entraîné** sur un vrai jeu de données d'incendies (Algerian Forest Fires Dataset,
243 relevés historiques réels, précision 86% / ROC-AUC 0.94 sur données de test),
météo réelle en direct (Open-Meteo), NDVI satellite réel (NASA Earthdata/MODIS),
FIRMS (satellite, réel), une **prévision de risque à 3 jours** basée sur de vraies
prévisions météo, une carte Leaflet temps réel (SSE), un agent LLM d'explication
bilingue FR/EN (Ollama, avec fallback), un écran touriste et un **tableau de bord
Ministère** avec recommandation d'alternative.

## 0. Avant de commencer (setup, hors chrono)
- `uvicorn backend.main:app --reload` lancé, terminal visible en fond.
- Onglet 1 ouvert sur `http://localhost:8000/` (carte).
- Onglet 2 ouvert sur `http://localhost:8000/tourist` (écran touriste), pas encore au premier plan.
- Onglet 3 ouvert sur `http://localhost:8000/dashboard` (tableau de bord), pas encore au premier plan.
- Si Ollama tourne, tant mieux ; sinon ne rien dire, le fallback est invisible pour le public.

## 1. Le problème (30s)
"Chaque année, la Tunisie doit gérer des risques environnementaux — incendies de
forêt, canicules — mais l'information est éclatée : la météo a ses données, la
protection civile a les siennes, le tourisme n'a rien d'unifié. Résultat : soit on
ferme une zone sans alternative, soit on ne réagit pas assez vite. Ça coûte des vies
et ça coûte des touristes."

## 2. La carte, état normal (40s)
Montrer l'onglet 1. "Voici Tunisna : une carte temps réel de 6 zones
touristiques — Tabarka, Aïn Draham, Bulla Regia, Dougga, Ichkeul, Hammamet. Chaque
zone a un score de risque de 0 à 100. Ce score n'est pas une formule inventée : c'est
un modèle XGBoost entraîné sur des données réelles d'incendies méditerranéens,
combiné à la météo réelle de maintenant, aux foyers actifs détectés par les
satellites de la NASA (FIRMS), et au NDVI — l'indice de végétation, lui aussi une
vraie donnée satellite NASA, pas une valeur inventée." Indiquer le badge "🟢 Live" :
"la carte reçoit les mises à jour en direct, pas en rafraîchissant la page."
Cliquer sur un marqueur pour montrer le popup : température, vent, humidité, pluie,
foyers, NDVI, **le détail du modèle IA** (probabilité d'incendie, confiance,
explication citant les moyennes réelles du jeu d'entraînement), **et la prévision à
3 jours** en bas du popup — trois points colorés montrant comment le risque évolue
avec la météo réelle des prochains jours. "Le système n'attend pas que le risque
arrive, il le voit venir."

## 3. Le scénario de crise en direct (45s)
"Simulons maintenant une dégradation soudaine à Aïn Draham — canicule, vent fort,
végétation asséchée, premiers foyers détectés." Cliquer sur **"🔥 Trigger fire
scenario (Aïn Draham)"**. Le marqueur passe au rouge en direct, score 90+, niveau
critique. "La carte réagit en temps réel — c'est exactement ce qui remonterait
d'une vraie dégradation météo et satellite."

## 4. L'agent IA qui explique — et qui voit dans le temps (50s)
Basculer sur l'onglet 2 (écran touriste). "Un touriste qui prévoit de visiter Aïn
Draham dans deux jours pose simplement la question à l'app — et choisit sa date."
Sélectionner "Aïn Draham", choisir une date dans 2 jours, cliquer "Vérifier". Montrer
le résultat : badge, la ligne "📅 Basé sur une prévision météo réelle pour le..." —
"ce n'est pas les conditions d'aujourd'hui qu'on lui montre, c'est une vraie
prévision Open-Meteo pour SA date de visite" — puis l'explication générée par le LLM
citant les vrais chiffres de cette prévision, et surtout — "le système ne se contente
pas de dire non, il recommande immédiatement la zone voisine la plus sûre. Le
tourisme continue, la sécurité est respectée."
Mentionner : "Et même si le LLM local tombe en panne pendant la démo, le système a
un filet de sécurité — les vrais chiffres et la meilleure alternative sont toujours
calculés, avec ou sans le LLM. Le modèle de prédiction, lui, tourne indépendamment
du LLM : c'est lui qui calcule le score, le LLM ne fait que le mettre en mots."

Si un juge demande "où est l'IA ?" : ouvrir `training/train_fire.py` et
`models/wildfire_model_meta.json` pour montrer l'entraînement réel, les métriques
sur données de test, et la citation exacte du dataset (Zenodo, DOI, licence
CC-BY-4.0).

## 5. Le tableau de bord Ministère (30s)
Basculer sur l'onglet 3 (`/dashboard`). "Le touriste a son app, mais les autorités
ont besoin d'une vue d'ensemble pour décider." Montrer les 6 zones triées par
risque, les compteurs (zones critiques, élevées, score moyen, couverture NDVI
satellite réelle), tout en direct via le même flux temps réel que la carte. Cliquer
sur le bouton **EN** en haut à droite : toute l'interface — labels, tableau,
explication touriste — bascule en anglais instantanément. "Pensé pour un public
international, pas seulement tunisien."

## 6. Reset + vision (30s)
Revenir sur la carte, cliquer "↺ Reset scenario" pour montrer que tout redevient
vert. "Ce qu'on a construit : un moteur de score réel, une prévision à 3 jours, une
carte réactive en temps réel, un agent d'explication IA bilingue, une redirection
touristique intelligente, et un tableau de bord décisionnel — pas juste une alerte,
une solution complète. La suite : inondations, coupures d'eau/électricité, imagerie
Sentinel-2 pour la déforestation, un vrai score de Confiance Touristique multi-
facteurs — un projet qui parle directement au Ministère du Tourisme et à la
Protection Civile, dans l'esprit de Tunisie Capitale Arabe du Tourisme 2027."

## Filet de sécurité si quelque chose casse pendant la démo
- Météo : aucune clé requise (Open-Meteo) — si le réseau coupe quand même, valeurs
  par défaut réalistes (28°C, vent 10km/h, humidité 45%, 0mm pluie).
- Pas de clé FIRMS → foyers actifs à 0 par défaut : la démo continue normalement,
  juste sans données satellite incendie live.
- Date au-delà de J+3 → l'app le dit explicitement ("pas de prévision fiable...")
  et retombe sur les conditions actuelles, jamais une fausse prévision.
- Ollama down → l'explication utilise le template français de secours, avec les
  vrais chiffres, sans jamais planter l'écran touriste.
- Modèle ML jamais entraîné (`python -m training.train_fire` pas lancé) → le score
  retombe sur la formule pondérée de secours, et `/api/predict/{zone}` renvoie
  explicitement `"ml": null` plutôt qu'un faux chiffre.
- Le bouton de scénario peut être re-cliqué autant de fois que nécessaire ; "Reset
  scenario" ramène tout à l'état stable avant de recommencer.
