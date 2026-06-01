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
  ÉTAPE 1 — DataProcessor    (nettoyage : encodage, valeurs manquantes ; PAS de normalisation)
     │
     ▼
  ÉTAPE 2 — AHP              (calcul des poids)
     │
     ▼
  ÉTAPE 3 — TOPSIS           (classement multicritère ; normalisation vectorielle interne)
     │
     ▼
  ÉTAPE 4 — MLTrainer        (classification ; normalisation par fold dans un Pipeline)
     │
     ▼
  ÉTAPE 5 — HybridRanker     (fusion TOPSIS + ML)
     │
     ▼
  Résultats JSON
```

> Note d'architecture : la normalisation n'est volontairement **pas** faite dans DataProcessor.
> Chaque consommateur normalise selon ses besoins — TOPSIS sur l'ensemble (normalisation
> vectorielle), le ML par repli de validation croisée — ce qui évite la double normalisation
> et la fuite de prétraitement côté ML.

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

## 4. Combien de classes pour le ML ?

Le nombre de classes n'est **pas figé** : le système s'adapte au nombre de classes
présentes dans la colonne de vérité terrain fournie par le responsable (au minimum 2).

- Avec **2 classes** (ex. Admis / Refusé), le ML produit un filtre binaire.
- Avec **plusieurs classes** (ex. Non_classe / Moyen / Bon / Excellent), le ML produit une
  hiérarchie plus fine ; les candidats d'une même classe sont ensuite départagés par le
  score final hybride.

Le choix relève du responsable : il dépend de la granularité de la décision à reproduire.
Le système détecte automatiquement le nombre de classes et adapte sa métrique d'évaluation
(ROC-AUC en binaire, F1-macro en multiclasse).

---

## 5. C'est quoi la vérité terrain (ground truth) ?

La vérité terrain, c'est la référence fiable utilisée pour entraîner le modèle ML : la
classe réelle de chaque candidat, issue d'une décision passée connue.

**Point méthodologique important (à savoir présenter).** Une première version dérivait les
étiquettes des **quartiles de la moyenne** (`Moyenne_finale`). C'était commode pour démarrer,
mais cela créait une **fuite de données** (*target leakage*) : la cible était une simple
fonction d'un critère (la moyenne), et comme la moyenne servait aussi de critère d'entrée,
le modèle « relisait » la réponse au lieu de l'apprendre. Symptôme typique : des scores
quasi parfaits (~98 %) aussi bien en entraînement qu'en test — signe d'une fuite, pas d'un
bon modèle.

**Correction adoptée.** La vérité terrain provient désormais du **classement réel** des
candidats (`Classement`), une information **indépendante de la moyenne** (corrélation ≈ −0,08).
Les classes sont construites à partir de ce classement :

| Source | Classe |
|--------|--------|
| Candidats non classés | Non_classe |
| Rangs les plus faibles | Moyen |
| Rangs intermédiaires | Bon |
| Meilleurs rangs | Excellent |

Règle d'or qui en découle : **la colonne ayant servi à construire la vérité terrain ne doit
jamais figurer parmi les critères** de classement. Après correction, le modèle atteint des
scores honnêtes (~0,92 F1-macro sur les données de test jamais vues), validés par une série
de tests anti-fuite (performance hors classe « Non_classe », sur dossiers complets, etc.).

Enfin, le système reste **incrémental** : via le FeedbackModal, le responsable soumet de
vraies décisions validées (n'importe quel jeu de classes ≥ 2), qui enrichissent l'historique
et affinent le modèle au fil des sessions.
