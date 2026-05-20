# Explications pour la soutenance

## 1. C'est quoi une API ?

Par définition, une API (Application Programming Interface) est une interface qui permet à deux programmes informatiques de communiquer entre eux.

**Dans notre application, ces deux programmes sont :**

- **Programme 1 — le Frontend (React)** : tourne sur `http://localhost:3000`. C'est l'interface utilisateur, ce que l'utilisateur voit dans le navigateur.
- **Programme 2 — le Backend (Flask)** : tourne sur `http://localhost:5000`. C'est le moteur de calcul — AHP, TOPSIS, ML, SHAP.

L'API Flask est l'interface qui permet à ces deux programmes de se parler. Quand l'utilisateur clique sur "Lancer le classement" dans React, le frontend envoie une requête HTTP `POST /api/ranking/process` au backend Flask, qui exécute le pipeline et renvoie les résultats en JSON. React reçoit le JSON et affiche les résultats.

```
React (navigateur)  ──── HTTP / JSON ────▶  Flask (serveur)
                    ◀────────────────────
```

Sans l'API, les deux programmes ne pourraient pas communiquer — React ne peut pas exécuter du Python, et Flask ne peut pas afficher une interface graphique.

---

## 2. Le backend est-il un pipeline ?

Non, le backend et le pipeline sont deux choses différentes.

**Le backend** c'est l'ensemble du serveur Flask — il gère les requêtes, les fichiers, les routes, les réponses. C'est l'infrastructure.

**Le pipeline** c'est une séquence de traitements à l'intérieur du backend — spécifiquement dans `routes/ranking.py` quand on appelle `/api/ranking/process` :

```
Données brutes
     │
     ▼
  ÉTAPE 1 — DataProcessor    (normalisation)
     │
     ▼
  ÉTAPE 2 — AHP              (calcul des poids)
     │
     ▼
  ÉTAPE 3 — TOPSIS           (classement multicritère)
     │
     ▼
  ÉTAPE 4 — MLTrainer        (classification 4 niveaux)
     │
     ▼
  ÉTAPE 5 — HybridRanker     (fusion TOPSIS + ML)
     │
     ▼
  Résultats JSON
```

**Le pipeline est une fonctionnalité du backend**, pas le backend lui-même. Le backend fait aussi d'autres choses : recevoir les fichiers uploadés, servir les résultats en téléchargement, stocker l'historique, etc.

---

## 3. Pourquoi Flask et pas FastAPI ?

Flask a été choisi pour sa simplicité — c'est un micro-framework léger, facile à mettre en place pour une API REST basique.

FastAPI aurait été plus adapté pour ce projet car :

| | Flask | FastAPI |
|---|---|---|
| Performance | Synchrone (bloquant) | Asynchrone (non-bloquant) |
| Validation des données | Manuelle | Automatique (Pydantic) |
| Documentation API | Aucune auto | Swagger UI auto-générée |
| Typage | Optionnel | Natif |
| Pipeline ML long | Bloque le serveur | Gérable en async |

Le point le plus critique : le pipeline ML (entraînement + SHAP) peut prendre plusieurs secondes. Avec Flask synchrone, le serveur est bloqué pendant ce temps. Avec FastAPI, cela aurait pu être géré proprement avec `async/await`. Une migration vers FastAPI est possible dans une version future.

---

## 4. Pourquoi 4 classes ML et pas 2 ?

Avec 2 classes (Admis / Refusé), le ML produirait un filtre binaire — un candidat est soit admis soit refusé. Cela ne permet pas de distinguer les niveaux à l'intérieur des admis.

Avec 4 classes (Faible / Moyen / Bon / Excellent), le ML produit une hiérarchie. Les candidats Excellent sont ensuite départagés entre eux par le score final hybride. Cela donne un classement beaucoup plus nuancé et utile pour le responsable.

---

## 5. C'est quoi la vérité terrain (ground truth) ?

La vérité terrain, c'est la référence fiable utilisée pour entraîner le modèle ML. Dans notre cas, les étiquettes de tier (Faible / Moyen / Bon / Excellent) ont été attribuées à partir des quartiles de la colonne `Moyenne_finale` :

| Quartile | Tier |
|----------|------|
| < Q25 (11.02) | Faible |
| Q25 – Q50 (12.14) | Moyen |
| Q50 – Q75 (13.35) | Bon |
| ≥ Q75 (13.35) | Excellent |

Ce labeling par quartiles est une approche bootstrap — il permet de démarrer l'apprentissage sans données historiques validées. Au fur et à mesure que le responsable corrige les prédictions via le FeedbackModal, le modèle apprend de vraies décisions expertes et devient progressivement plus précis.
