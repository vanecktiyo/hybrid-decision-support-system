# Manuel d'utilisation — Système Hybride MCDM

**Version 2.0 — Vaneck DAGAR, 2026**

Système d'aide à la décision multicritère pour le classement des candidatures académiques.
Méthodes : AHP (poids des critères) + TOPSIS (classement) + Modèle ML (optionnel).

---

## Table des matières

1. [Prérequis techniques](#1-prérequis-techniques)
2. [Format du fichier de données](#2-format-du-fichier-de-données)
3. [Règles par type de colonne](#3-règles-par-type-de-colonne)
4. [Ce que l'application gère automatiquement](#4-ce-que-lapplication-gère-automatiquement)
5. [Ce que le responsable doit préparer](#5-ce-que-le-responsable-doit-préparer)
6. [Exemple de fichier valide](#6-exemple-de-fichier-valide)
7. [Guide pas à pas — Les 5 étapes](#7-guide-pas-à-pas--les-5-étapes)
8. [Comprendre les résultats](#8-comprendre-les-résultats)
9. [Erreurs fréquentes](#9-erreurs-fréquentes)

---

## 1. Prérequis techniques

- Navigateur web moderne (Chrome, Firefox, Edge)
- Backend Flask démarré sur `http://localhost:5000`
- Frontend React démarré sur `http://localhost:3000`

Pour lancer l'application :

```bash
# Terminal 1 — Backend
cd version_2/backend
python app.py

# Terminal 2 — Frontend
cd version_2/frontend
npm start
```

---

## 2. Format du fichier de données

### Exigences obligatoires

Le fichier **doit** respecter ces critères. Toute exigence non satisfaite bloque l'analyse.

| Critère | Exigence |
|---|---|
| **Extensions acceptées** | `.csv`, `.xlsx`, `.xls` |
| **Taille maximale** | 50 Mo |
| **Encodage (CSV)** | UTF-8 |
| **Première ligne** | Noms des colonnes (headers obligatoires) |
| **Colonne identifiant** | Une colonne `ID` (ou variante reconnue) avec un identifiant unique par candidat — **obligatoire** |
| **Critères quantifiables** | Au moins 2 colonnes numériques (ou catégorielles ordonnables) utilisables pour le classement |
| **Une ligne = un candidat** | Pas de lignes fusionnées, pas de sous-totaux, pas de lignes vides intercalées |
| **IDs uniques** | Chaque candidat doit avoir un identifiant distinct dans la colonne ID — **bloquant** si des doublons sont détectés |
| **Cellules fusionnées (Excel)** | Interdites — défusionner avant l'export |
| **Feuilles Excel** | Une seule feuille active |

> Si la colonne ID est absente ou contient des doublons, l'application affiche une erreur bloquante et refuse de continuer.

### Exigences recommandées

| Critère | Recommandation |
|---|---|
| **Nombre de candidats** | Au moins 8 (minimum pour activer le ML) |
| **Colonnes complètes** | Éviter les colonnes avec plus de 50% de valeurs manquantes |

---

## 3. Règles par type de colonne

### 3.1 Colonne identifiant — obligatoire, 1 seule

Identifie chaque candidat de façon unique. Peut être un numéro, un nom, un code.

Noms reconnus automatiquement : `ID`, `id`, `name`, `nom`, `reference`, `ref`, `student_id`, `candidat_id`, `index`.
Si votre colonne a un autre nom, vous la sélectionnez dans l'application (étape 3).

```
ID      Nom_Candidat    Reference
1001    Dupont Alice    REF-2024-001
1002    Martin Théo     REF-2024-002
```

> Les valeurs doivent être **uniques** — pas de doublons.

---

### 3.2 Colonnes critères numériques — au moins 2 obligatoires

Ce sont les colonnes sur lesquelles le classement est basé.
Valeurs entières ou décimales. Les unités et échelles sont libres — TOPSIS normalise
automatiquement chaque critère lors du calcul.

```
GPA     Score_Test    Annees_Experience    Note_Entretien
3.8     85            5                   14.5
3.2     91            2                   12.0
```

> **Tous les critères sont évalués en « bénéfice »** : une valeur plus haute = meilleur
> candidat. Pour un critère où « moins est mieux » (ex : frais, délai), transformez-le
> avant l'upload (par ex. en inversant l'échelle) afin qu'une valeur haute traduise un
> meilleur profil.

---

### 3.3 Colonnes critères catégorielles — optionnel

Colonnes texte dont les valeurs sont ordonnables (du moins bon au meilleur).

```
Niveau_Etudes    Mention        Statut_Dossier
Licence          Passable       Incomplet
Master           Bien           Complet
Doctorat         Très bien      Complet
```

Limites :
- Entre **2 et 20 valeurs distinctes** par colonne
- Les valeurs doivent être **cohérentes** (pas de fautes de frappe, pas de casse mixte)

Dans l'application (étape 3), vous attribuez un score numérique à chaque valeur :

```
Exemple pour Niveau_Etudes :
  Licence  = 1   (le moins valorisé)
  Master   = 2
  Doctorat = 3   (le plus valorisé)
```

> Les colonnes texte non-ordonnables (ville, prénom, email) sont automatiquement ignorées.

---

### 3.4 Colonne cible ML — optionnel

Une colonne **catégorielle** contenant la **vérité terrain** : la classe réelle connue
de chaque candidat (issue d'une sélection passée). Elle sert uniquement à entraîner le
modèle ML et **ne participe pas** au classement TOPSIS.

Les **noms et le nombre de classes sont libres** — l'application ne se limite à aucun
vocabulaire imposé. Quelques exemples valides :

```
Admission          Decision           Niveau_Final
Admis              A                  Non_classe
Refusé             B                  Moyen
Admis              C                  Excellent
```

> **Important** : la cible doit être une colonne d'**étiquettes** (texte) avec au moins
> **2 classes distinctes**. L'application vous demandera de définir l'ordre des classes
> (0 = le moins bon, valeur max = le meilleur).
>
> ⚠️ La colonne utilisée pour construire la vérité terrain (ex : un classement) **ne doit
> pas** être sélectionnée comme critère de classement, sinon le modèle « relit » la réponse
> (fuite de données) et ses scores deviennent trompeurs.

| Contrainte | Valeur |
|---|---|
| Type de colonne | Catégorielle (texte) — noms de classes libres |
| Nombre de classes | Au moins 2 valeurs distinctes |
| Minimum total | Au moins 8 candidats pour activer le ML |

> Si absent ou insuffisant, l'application utilise TOPSIS + AHP uniquement (sans ML).

---

## 4. Ce que l'application gère automatiquement

| Situation | Comportement |
|---|---|
| Colonnes avec valeurs manquantes | Détectées dans le rapport QA. Stratégie choisie par l'utilisateur : moyenne, médiane, ou zéro. **Aucun candidat n'est jamais exclu** — tout candidat est classé |
| Échelles différentes entre critères | Normalisation automatique au moment du calcul (TOPSIS : normalisation vectorielle ; ML : mise à l'échelle interne par repli de validation croisée) |
| Colonnes texte non-ordonnables | Ignorées — non proposées comme critères |
| Colonne identifiant | Détection automatique par nom, sinon sélection manuelle |
| Doublons | Signalés dans le rapport QA |
| Valeurs aberrantes (outliers) | Signalées dans le rapport QA |

---

## 5. Ce que le responsable doit préparer

Les situations suivantes ne sont **pas** gérées par l'application et doivent être résolues avant l'upload :

| Situation | Action requise |
|---|---|
| Cellules fusionnées dans Excel | Défusionner toutes les cellules |
| Données réparties sur plusieurs feuilles | Consolider sur une seule feuille |
| Valeurs texte parasites dans colonnes numériques (`N/A`, `-`, `?`, `—`) | Remplacer par une valeur numérique ou laisser la cellule vide |
| Colonnes date/heure comme critère | Convertir en valeur numérique (ex : âge en années, ancienneté en mois) |
| Encodage CSV incorrect (accents cassés) | Sauvegarder en UTF-8 depuis Excel : Fichier → Enregistrer sous → CSV UTF-8 |
| Valeurs catégorielles incohérentes (`master`, `Master`, `MASTER`) | Uniformiser la casse avant l'export |
| Identifiant non unique | S'assurer que chaque candidat a un ID distinct |

---

## 6. Exemple de fichier valide

### Fichier CSV

```csv
ID,GPA,Score_TOEFL,Annees_Experience,Niveau_Etudes,Frais_Scolarite,Score_Historique
1001,3.8,105,3,Master,12000,0.87
1002,3.2,98,1,Licence,8000,0.65
1003,3.9,112,5,Doctorat,15000,0.91
1004,2.9,88,2,Licence,7500,0.58
1005,3.5,101,4,Master,11000,0.79
1006,3.7,108,3,Doctorat,14000,0.85
1007,3.1,94,1,Licence,9000,0.62
1008,3.6,103,2,Master,13000,0.80
```

**Correspondance des colonnes :**

| Colonne | Type | Rôle dans l'application |
|---|---|---|
| `ID` | Identifiant | Colonne ID (détectée automatiquement) |
| `GPA` | Numérique | Critère Benefit ↑ |
| `Score_TOEFL` | Numérique | Critère Benefit ↑ |
| `Annees_Experience` | Numérique | Critère Benefit ↑ |
| `Niveau_Etudes` | Catégoriel | Critère (Licence=1, Master=2, Doctorat=3) |
| `Frais_Scolarite` | Numérique | Critère (transformer pour qu'une valeur haute = mieux) |
| `Score_Historique` | Numérique | Non utilisable comme cible ML (la cible doit être catégorielle) |

---

## 7. Guide pas à pas — Les 5 étapes

### Étape 1 — Upload du fichier

- Glissez-déposez votre fichier CSV ou Excel, ou cliquez pour sélectionner.
- Taille maximale : 50 Mo.
- L'application affiche un aperçu des premières lignes.

### Étape 2 — Rapport QA (Validation automatique)

L'application analyse la qualité des données et affiche :

- **Score de qualité global** (0–100%) calculé sur l'ensemble des colonnes détectées
- **Données manquantes** par colonne, avec choix de la stratégie de remplacement (moyenne, médiane, ou zéro). Par défaut : **zéro** (le candidat sans information est pénalisé, mais jamais exclu)
- **Anomalies (outliers)** par critère, avec la liste des candidats concernés
- **Avertissements** divers (IDs dupliqués, colonnes difficiles à convertir, etc.)

**Deux niveaux de résultat possibles :**

| Résultat | Signification | Action |
|---|---|---|
| Erreur bloquante (encart rouge) | Exigence obligatoire non respectée (ex : pas de colonne ID) | Corriger le fichier et le réimporter |
| Avertissements (orange) | Problèmes de qualité non bloquants | Vérifier avant de continuer |

> Vous ne pouvez pas passer à l'étape suivante tant qu'une erreur bloquante est présente.

### Étape 3 — Configuration des critères

1. **Vérifiez la colonne ID** détectée automatiquement. Corrigez si nécessaire.
2. **Critères numériques** : cochez les colonnes à utiliser. Tous les critères sont en « bénéfice » (valeur haute = meilleur).
3. **Critères catégoriels** (si présents) : cochez et attribuez un score à chaque valeur (1 = le moins bon).
4. **Colonne cible ML** (optionnel) : sélectionnez une colonne catégorielle de vérité terrain. Un mapping s'affiche pour définir l'ordre des classes (0 = le moins bon, valeur max = le meilleur). La colonne cible est automatiquement exclue des critères. **N'utilisez pas comme critère la colonne qui a servi à fabriquer la cible** (risque de fuite de données).

> Au minimum 2 critères doivent être sélectionnés pour continuer.

### Étape 4 — Matrice AHP (comparaison par paires)

La matrice AHP permet de définir l'importance **relative** de chaque critère par rapport aux autres.

- Utilisez l'échelle de Saaty : `1` = importance égale, `3` = modérément plus important, `5` = fortement, `7` = très fortement, `9` = extrêmement.
- Seule la **moitié supérieure** est saisie. La moitié inférieure (réciproques) se remplit automatiquement.
- Cliquez **Calculer les poids** pour vérifier la cohérence (CR < 0.10 obligatoire).
- Si CR ≥ 0.10, révisez vos jugements les plus incertains.

### Étape 5 — Résultats

L'application affiche :
- Le classement final avec le score de chaque candidat
- Les poids AHP par critère (avec le ratio de cohérence CR)
- Si ML activé :
  - **Performance sur les données de test** : score honnête mesuré sur un échantillon
    mis de côté avant l'entraînement (jamais utilisé pour apprendre) — c'est l'indicateur
    de référence de la qualité réelle du modèle.
  - Tableau comparatif des modèles par **validation croisée** (F1-macro), qui sert à
    sélectionner le meilleur modèle — à ne pas confondre avec la performance test.
  - La justification par candidat (contributions TOPSIS + SHAP).
- Boutons d'export CSV et Excel

### Étape 6 (optionnelle) — Validation et apprentissage incrémental

Depuis la page de résultats, le bouton **Soumettre la validation** ouvre une fenêtre qui
permet d'enrichir le modèle avec votre vérité terrain :

1. Téléchargez le classement (**CSV** ou **Excel**).
2. Ouvrez-le, repérez la colonne `Classe_predite`.
3. **Renommez-la `Validated_Tier`** et inscrivez la classe réelle de chaque candidat
   selon votre jugement.
4. Les **noms et le nombre de classes sont libres** (ex. `Admis / Refusé`, ou `A / B / C / D`…),
   avec un **minimum de 2 classes distinctes**.
5. Sauvegardez (CSV ou Excel) et ré-uploadez le fichier dans la fenêtre.

Ces données sont stockées comme **session historique** et réutilisées pour l'entraînement
lors des prochains classements **dont les critères sont identiques** (le système ignore les
sessions aux critères différents pour éviter de mélanger des profils incomparables).

---

## 8. Comprendre les résultats

### Score TOPSIS (Ci)

Coefficient de proximité à la solution idéale. Compris entre 0 et 1.

| Valeur | Interprétation |
|---|---|
| Proche de 1 | Candidat très proche du profil idéal |
| Proche de 0 | Candidat très éloigné du profil idéal |

### Score ML

Probabilité d'appartenir à la meilleure classe selon le modèle entraîné (0 à 1).
Reflète la décision prédite selon les données historiques fournies.

### Classe prédite

Étiquette prédite par le modèle ML pour chaque candidat, selon les classes de votre vérité
terrain (ex : Admis / Refusé, ou Non_classe / Moyen / Bon / Excellent).

### Score Final (Hybride)

```
Score Final = α × Score TOPSIS + β × Score ML
```

Où α et β sont définis à l'étape 4 (matrice AHP) via le slider de pondération hybride.
Par défaut : α = 60%, β = 40%.

Si aucune colonne cible ML n'est fournie : Score Final = Score TOPSIS (α = 100%).

### Ratio de cohérence AHP (CR)

Mesure la cohérence logique de vos comparaisons par paires.

| CR | Signification |
|---|---|
| < 0.10 | Jugements cohérents — poids valides |
| ≥ 0.10 | Jugements incohérents — à réviser |

---

## 9. Erreurs fréquentes

| Message d'erreur | Cause probable | Solution |
|---|---|---|
| **Fichier non conforme : impossible de continuer** | Colonne ID absente du fichier | Ajouter une colonne `ID` avec un identifiant unique par candidat |
| *File not found* | Fichier déplacé après upload | Re-uploader le fichier |
| *No criteria configured* | Aucun critère sélectionné à l'étape 3 | Sélectionner au moins 2 critères |
| *Matrix is inconsistent (CR ≥ 0.10)* | Comparaisons AHP contradictoires | Revoir les valeurs les plus incertaines |
| *Column not found* | Nom de colonne modifié entre les étapes | Recommencer depuis l'étape 1 |
| *Too few samples for ML* | Moins de 8 lignes dans le fichier | Ajouter des données ou désactiver le ML |
| *La colonne cible est numérique* | Colonne ML cible de type numérique | Utiliser une colonne catégorielle (texte) comme cible ML |
| *La colonne doit contenir au moins 2 classes distinctes* (validation) | Vérité terrain à une seule classe | Fournir au moins 2 classes différentes dans `Validated_Tier` |
| Accents mal affichés | CSV non encodé en UTF-8 | Sauvegarder en CSV UTF-8 depuis Excel |
| Colonne catégorielle non proposée comme critère | Trop de valeurs distinctes (> 20) | Regrouper les catégories avant l'export |
| Score de qualité très bas (< 50%) | Nombreuses valeurs manquantes ou colonne ID absente | Corriger les problèmes listés dans le rapport QA |

---

*Système Hybride MCDM v2.0 — Vaneck DAGAR, 2026*
