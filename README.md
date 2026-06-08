# MCDM hybride : classement intelligent de candidatures académiques

Un système d'aide à la décision qui classe des candidats en combinant le **jugement expert
multicritère** (AHP + TOPSIS) avec un **modèle d'apprentissage automatique entraîné sur les
décisions passées**, et qui explique chaque rang qu'il produit.

Il est générique par conception : vous importez un fichier CSV ou Excel, vous choisissez les
critères et les classes de décision depuis l'interface, et le même pipeline s'applique, que vous
classiez des candidats à une école d'ingénieurs, à un master ou à toute autre formation.

> Ce logiciel accompagne un mémoire de fin d'études à l'*Université Catholique de Lille*
> (2025-2026). La méthodologie complète, la revue systématique de littérature et l'évaluation
> détaillée sont présentées dans [`rapport/main.pdf`](rapport/main.pdf).

---

## Pourquoi ce projet

Deux familles de méthodes s'opposent habituellement pour le classement de candidatures.

Les méthodes multicritères (AHP, TOPSIS) sont **transparentes mais statiques** : une fois les poids
fixés par le décideur, elles appliquent une règle figée et n'apprennent jamais des décisions qui
s'accumulent au fil des années. L'apprentissage automatique fait l'inverse, il **apprend de
l'historique mais reste difficile à interpréter**.

Ce système réconcilie les deux. Le décideur exprime toujours ses préférences (poids AHP, classement
TOPSIS), mais un modèle entraîné sur les décisions validées vient se fondre dans le score final, et
les deux points de vue sont rendus explicables : contributions par critère du côté de TOPSIS,
valeurs SHAP du côté du modèle. Le décideur garde le contrôle et la transparence, et le système
s'affine à mesure que des décisions sont validées.

---

## Comment ça fonctionne

L'application guide l'utilisateur en cinq étapes et exécute, en coulisses, un pipeline en cinq
temps :

1. **Préparation des données** : encodage ordinal des critères catégoriels et gestion des valeurs
   manquantes. Aucune normalisation à cette étape, car chaque algorithme normalise de son côté
   (TOPSIS en interne, le modèle dans un pipeline par repli), ce qui évite la double normalisation
   et garde l'évaluation saine.
2. **AHP** : poids des critères dérivés des comparaisons par paires du décideur, avec un ratio de
   cohérence (CR) vérifié en temps réel.
3. **TOPSIS** : un classement complet par proximité à la solution idéale, chaque score étant
   décomposé en contributions par critère.
4. **Apprentissage automatique** : six classifieurs sont comparés par validation croisée, le
   meilleur (la forêt aléatoire, ici) est sélectionné puis optimisé, et SHAP explique ses
   prédictions.
5. **Fusion hybride** : le score TOPSIS et la probabilité de la meilleure classe prédite par le
   modèle sont combinés en un score unique, réglable par l'utilisateur (`α`, valeur par défaut
   `0,6`).

Si les données sont trop limitées pour entraîner un modèle fiable, ou si l'apprentissage est
désactivé, le système bascule proprement sur TOPSIS seul (`α = 1`).

---

## Démarrage rapide

**Prérequis :** Python 3.10+ et Node.js 16+ (avec npm).

### 1. Backend (API Flask)

```bash
cd backend
pip install -r requirements.txt
python app.py
```

L'API démarre sur `http://localhost:5000`. Elle crée ses dossiers d'exécution
(`uploads/`, `results/`, `historical/`) au premier lancement.

### 2. Frontend (React)

```bash
cd frontend
npm install
npm start
```

L'interface s'ouvre sur `http://localhost:3000` et relaie les appels vers le backend.

---

## Utilisation

Les cinq étapes guidées reprennent le pipeline :

1. **Import** : déposez un fichier CSV ou Excel, un aperçu s'affiche.
2. **Rapport de qualité** : les valeurs manquantes et les anomalies sont détectées, et vous
   choisissez la stratégie de remplacement (zéro par défaut, ce qui pénalise l'absence
   d'information plutôt que de la récompenser).
3. **Critères** : sélectionnez les critères, définissez l'encodage ordinal des critères
   catégoriels et, éventuellement, indiquez la colonne de vérité terrain pour le module
   d'apprentissage.
4. **Matrice AHP** : saisissez les comparaisons par paires (échelle de Saaty), le ratio de
   cohérence est validé en direct. Un curseur fixe le poids de fusion `α`.
5. **Résultats** : le classement complet, la classe prédite de chaque candidat, les justifications
   TOPSIS et SHAP, la performance sur le jeu de test, et un export (CSV ou Excel).

Une **boucle de rétroaction** ferme le cycle : téléchargez les résultats, corrigez la colonne de
classe selon votre vérité terrain, puis ré-importez le fichier. Les sessions validées sont stockées
et réinjectées dans les entraînements ultérieurs **dont les critères correspondent**, de sorte que
le modèle s'améliore à mesure que de vraies décisions s'accumulent.

---

## À propos de l'évaluation

Les chiffres affichés par l'application ne sont pas une « performance d'entraînement ». Un jeu de
test stratifié est mis de côté **avant** tout entraînement, la sélection et l'optimisation du modèle
ne voient jamais que les données restantes, et le chiffre final est mesuré sur ce jeu de test
intact.

Sur le jeu de données fourni de **815 candidatures réelles**, la forêt aléatoire retenue atteint un
**F1-macro d'environ 0,95** sur le jeu de test, équilibré entre les classes (y compris la plus
rare). Plus important encore, la fusion **améliore la qualité de la présélection** : la précision du
top-20 % passe de **0,70** (TOPSIS seul) à **0,76**, sans dégrader l'ordonnancement d'ensemble
(Spearman d'environ 0,51, statistiquement significatif). L'étude autonome qui produit ces chiffres
(comparaison des modèles, performance sur le test, Spearman, precision@k et balayage de `α`) se
trouve dans [`evaluation/`](evaluation/) et écrit ses résultats en CSV ainsi qu'une figure.

---

## Configuration

Les choix propres à chaque exécution (critères, poids, colonne cible, `α` de fusion) se font dans
l'interface et ne sont **pas** stockés dans un fichier. Ce que contient `config.yaml`, ce sont les
*constantes méthodologiques* : le seuil de cohérence, la fraction du jeu de test, le nombre de
replis de validation croisée, le nombre d'itérations d'optimisation. L'éditer permet d'ajuster la
méthodologie sans toucher au code, et si une clé (ou le fichier entier) est absente, le code retombe
sur les mêmes valeurs par défaut intégrées.

---

## Organisation du projet

```
version_2/
├── backend/             API Flask + le cœur MCDM / ML
│   ├── app.py             point d'entrée, blueprints, gestion des erreurs
│   ├── core/              ahp · topsis · data_processor · data_preprocessor ·
│   │                      ml_trainer · hybrid · historical_store · file_reader · config_manager
│   ├── routes/            upload · ranking · ahp · feedback · download
│   ├── tests/             150 tests unitaires (pytest)
│   └── requirements.txt
├── frontend/            application React monopage (le parcours guidé en 5 étapes)
│   └── src/components/    LandingPage · FileUploader · QAReport · CriteriaConfig ·
│                          AHPMatrix · Dashboard · ResultsViewer · FeedbackModal
├── evaluation/          étude autonome de l'apport du ML (Spearman, precision@k, balayage α)
├── data/                jeux de données d'entrée et fichiers de validation (non versionnés)
├── notebooks/           notebook de validation du module ML
├── docs/                manuel utilisateur (français) et articles de référence
├── rapport/             mémoire LaTeX : méthodologie, résultats → main.pdf
└── config.yaml          constantes méthodologiques
```

---

## Référence de l'API

| Méthode | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/health` | Vérification de l'état du service |
| `GET`  | `/api/info` | Métadonnées de l'application (version, algorithmes, formats) |
| `POST` | `/api/upload/file` | Importer un fichier CSV ou Excel |
| `GET`  | `/api/upload/preview/<filename>` | Aperçu du fichier importé |
| `GET`  | `/api/ranking/criteria-suggestions/<filename>` | Détection automatique des critères |
| `POST` | `/api/ahp/weights` | Calculer les poids AHP et le ratio de cohérence |
| `POST` | `/api/ahp/validate-matrix` | Valider la cohérence d'une matrice de comparaison |
| `POST` | `/api/ranking/process` | Exécuter le pipeline complet et renvoyer le classement |
| `GET`  | `/api/download/results/<result_id>` | Télécharger le classement (CSV ; ajouter `/excel` pour XLSX) |
| `POST` | `/api/feedback/submit` | Soumettre des classes validées pour l'apprentissage incrémental |
| `GET`  | `/api/feedback/history` | Lister les sessions historiques stockées |

---

## Tests

Le backend est couvert par une suite `pytest` (AHP, TOPSIS, traitement des données, entraînement du
modèle, fusion hybride, magasin historique et routes de validation) :

```bash
cd backend
python -m pytest
```

---

## Technologies utilisées

**Backend** : Python, Flask, scikit-learn, XGBoost, SHAP, pandas, NumPy.
**Frontend** : React 18.
**Rapport** : LaTeX (compilé avec MiKTeX / latexmk).

---

## Auteur et encadrement

**Vaneck Duramel DAGAR TIYO**, *Méthodes de prise de décision multicritère hybrides pour le
classement des candidatures*, 2025-2026.
Encadré par **Faiza AJMI** et **Jalal POSSIK**, Université Catholique de Lille.

Le stockage par fichiers est un choix assumé : il s'agit d'un prototype de recherche destiné à
valider l'approche. Le chemin vers un déploiement multi-utilisateur adossé à une base de données est
détaillé dans la section *Perspectives* du rapport.
