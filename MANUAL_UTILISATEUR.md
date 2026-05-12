# 📖 Manual Utilisateur - Application de Classement MCDM

## Table des Matières

1. [Introduction](#introduction)
2. [Préparer vos Données](#préparer-vos-données)
3. [Utiliser l'Application](#utiliser-lapplication)
4. [Étape 1: Uploader les Données](#étape-1-uploader-les-données)
5. [Étape 2: Valider la Qualité des Données](#étape-2-valider-la-qualité-des-données)
6. [Étape 3: Configurer les Critères](#étape-3-configurer-les-critères)
7. [Étape 4: Matrice AHP](#étape-4-matrice-ahp)
8. [Étape 5: Consulter les Résultats](#étape-5-consulter-les-résultats)
9. [Dépannage](#dépannage)
10. [FAQ](#faq)

---

## Introduction

L'application de Classement MCDM (Multi-Criteria Decision Making) est un outil **générique** permettant de:
- ✅ Charger une liste de candidats avec leurs critères
- ✅ Valider automatiquement la qualité des données
- ✅ Définir l'importance relative des critères (matrice AHP)
- ✅ Calculer un classement multicritères robuste
- ✅ Exporter les résultats en CSV/Excel

**Algorithmes utilisés:**
- 🔹 **AHP (Analytic Hierarchy Process)**: Évaluation de la cohérence des préférences
- 🔹 **TOPSIS**: Sélection basée sur l'idéal positif
- 🔹 **Machine Learning** (optionnel): Prédictions avancées
- 🔹 **Fusion Hybride**: Combinaison intelligente des résultats

---

## Préparer vos Données

### Format Attendu

Votre fichier doit être au format **CSV** ou **Excel** avec la structure suivante:

| ID | Critère_1 | Critère_2 | Critère_3 | ... |
|----|-----------|-----------|-----------|-----|
| 001 | 15.5 | 12.3 | 1 | ... |
| 002 | 14.2 | 11.8 | 1 | ... |
| 003 | 13.7 | 10.9 | 0 | ... |

### Exigences

#### ✅ Obligatoire

1. **Colonne ID unique**
   - Identifie chaque candidat
   - Nombres, texte ou codes acceptés
   - Valeurs uniques (pas de doublons)
   - **Noms suggérés**: `ID`, `Référence`, `Num_Candidat`, `Code`

2. **En-têtes clairs**
   - Sans accents bizarres
   - Sans espaces inutiles
   - Pas de caractères spéciaux (à part `_` ou `-`)
   - **Bons exemples**: `Moyenne_Finale`, `Note-Math`, `Experienceprofessionnelle`
   - **Mauvais exemples**: `Moy & Final`, `Note (math)`, `  Expérience  `

3. **Données numériques**
   - Nombres décimaux (15.5, 14.2, etc.)
   - Nombres entiers (1, 0, 12, etc.)
   - Texte converti auto: `Oui/Non` → `1/0`, `Supérieur à 12` → `12.5`, etc.

#### ⚠️ Accepté mais Nettoyé

- **Valeurs manquantes (vides)** → Remplies avec la médiane colonne
- **Texte numérique** (`"15.5"` → `15.5`)
- **Variations textuelles** (`"oui"` / `"Oui"` / `"OUI"` → `1`)
- **Espaces superflus** → Supprimés automatiquement

#### ❌ Non Autorisé

- Pas de colonnes totalement vides
- Pas de valeurs négatives non intentionnelles
- Pas d'en-têtes dupliqués
- Pas de caractères non ASCII (é, ç, ñ, etc.) dans les en-têtes

### Exemple Complet

```csv
ID,Moyenne_Finale,Niveau_Math,Exp_Mois,Engagement,Sportif
001,14.5,16,12,Oui,1
002,13.2,14,6,Non,0
003,15.8,18,24,Oui,1
004,12.1,11,3,Non,0
005,13.9,15,9,Oui,0
```

### Préparation Recommandée

Avant d'uploader, vérifiez:

1. **Complétude des données**
   ```
   ✓ Tous les candidats ont un ID
   ✓ Chaque critère a ≥ 80% de données remplies
   ✓ Pas de colonnes totalement vides
   ```

2. **Format**
   ```
   ✓ En-têtes sans accents
   ✓ Nombres sans symboles (pas de "€", "%", etc.)
   ✓ Booléens en "Oui/Non" ou 1/0
   ```

3. **Cohérence**
   ```
   ✓ Pas de doublons ID
   ✓ Minimum 10 candidats recommandé
   ✓ Critères logiquement liés
   ```

---

## Utiliser l'Application

### Accès

Ouvrez votre navigateur et allez à: **`http://localhost:3000`**

Vous verrez l'interface avec **5 étapes** identifiées par un stepper:

```
1️⃣  Upload File
   ↓
2️⃣  Validate Data (QA Report)
   ↓
3️⃣  Configure Criteria
   ↓
4️⃣  AHP Matrix
   ↓
5️⃣  View Results
```

---

## Étape 1: Uploader les Données

### Interface

1. Vous verrez une zone de **drag-drop** avec le message:
   > "Drag your CSV or Excel file here, or click to select"

2. **Options pour uploader:**
   - Glisser-déposer un fichier
   - Cliquer pour ouvrir un explorateur de fichiers

### Actions

```
1. Cliquez ou glissez-déposez votre fichier CSV/Excel
2. Attendez le message "File uploaded successfully"
3. Cliquez "Next →" (ou auto-passage)
   → L'app valide automatiquement la qualité
```

### Résultat

Vous verrez un **aperçu rapide** (5 premières lignes) avec:
- ✓ Nombre de candidats
- ✓ Colonnes détectées
- ✓ Types de données

---

## Étape 2: Valider la Qualité des Données

### Rapport QA (Quality Assurance)

Après upload, l'app affiche un **rapport détaillé** avec:

#### 🎯 Score de Qualité (0-100%)

Visualisé par un **cercle de progression**:
- 🟢 **≥ 80%**: Excellente qualité → Continuer
- 🟡 **60-79%**: Acceptable → Vérifier avertissements
- 🔴 **< 60%**: Faible qualité → Corriger avant de continuer

#### 📊 Statistiques Clés

```
Total Candidates: 150
Numeric Criteria: 8
Text Converted: 2
Missing Data: 3 colonnes affectées
Outliers Found: 12
```

#### ✅ Critères Détectés

Liste de toutes les colonnes numériques trouvées:
```
Academic_Score
Certificate_Level
Event_Count
Test_Score
Participation_Rate
```

#### 🔄 Text Converted to Numeric

Colonnes converties automatiquement:
```
✓ Sportif_HN (Oui/Non → 1/0)
✓ Engagement (Texte → Nombre)
```

#### ⚠️ Missing Data

Colonnes avec données manquantes:
```
Experience_Years: 5 missing (3.3%)
  → Rempli avec médiane
```

#### 🔍 Outliers Detected

Valeurs anormales détectées (mais conservées):
```
Average_Score: 2 outliers
  Bounds: 5.2 - 19.8
```

#### 📌 Recommendation

Messages guide:
- ✅ **"Data quality is good. Ready to proceed."** → Continue
- ⚠️ **"Data quality is acceptable but has some issues"** → Vérifiez avertissements
- ❌ **"Data quality is poor"** → Corrigez et réessayez

### Action

```
1. Lisez le rapport entièrement
2. Si score ≥ 60%:
   - Cochez "I understand the data quality status..."
   - Cliquez "Continue to Criteria Selection →"
3. Si score < 60%:
   - Cliquez "Upload Different File"
   - Corrigez les données et réessayez
```

---

## Étape 3: Configurer les Critères

### Interface

Vous verrez une **liste de checkboxes** avec tous les critères détectés:

```
☑️ Moyenne_Finale         [afficher plus]
☑️ Niveau_Math            [afficher plus]
☑️ Exp_Mois               [afficher plus]
☑️ Engagement             [afficher plus]
☐ Sportif_HN             [afficher plus]
...
```

### Actions

1. **Cochez/Décochez** les critères pertinents
   - ✅ Au moins 2 critères doivent être sélectionnés
   - ✅ Vous pouvez sélectionner tous les critères

2. **Exemple de sélection pour un Master IA:**
   - ✅ Moyenne_Finale (base académique)
   - ✅ Niveau_Math (essentiel pour IA)
   - ✅ Exp_Mois (expérience pratique)
   - ✅ Engagement (profil) → Optionnel
   - ✅ Sportif_HN (bonus) → Optionnel

3. **Cliquez "Continue to AHP Matrix →"**
   - Bouton actif si ≥ 2 critères sélectionnés

### Résultat

Passage à l'étape 4: Matrice AHP

---

## Étape 4: Matrice AHP

### C'est Quoi?

La **matrice AHP** permet de définir l'**importance relative** entre critères.

**Exemple:**
- "Moyenne finale est-elle 3× plus importante que l'expérience?"
- "Niveau math est-il 5× plus important que l'engagement?"

### Interface Matrice

Vous verrez une **grille N×N** (où N = nombre de critères):

```
              Moyenne  Math  Exp  Engagement
Moyenne       1.0      3.0   5.0   7.0
Math          0.33     1.0   3.0   5.0
Exp           0.20     0.33  1.0   3.0
Engagement    0.14     0.20  0.33  1.0
```

**Propriétés automatiques:**
- Diagonale = 1.0 (critère vs lui-même) → **Grisée, non-éditable**
- Triangle inférieur = **Réciproques** (auto-calculées, grisées)
- Triangle supérieur = **Éditable** (entrez vos comparaisons)

### Échelle Saaty

Utilisez cette échelle pour les comparaisons:

| Valeur | Signification |
|--------|---------------|
| 1 | Égale importance |
| 3 | Faiblement plus important |
| 5 | Fortement plus important |
| 7 | Très fortement plus important |
| 9 | Extrêmement plus important |
| 1/3, 1/5, 1/7, 1/9 | (Inverses pour l'autre direction) |

### Comment Remplir

**Exemple:**

"Je pense que la Moyenne finale est **5 fois plus importante** que l'Expérience"

→ Mettez **5** à la case `Moyenne × Exp`

Automatiquement, la case `Exp × Moyenne` devient **0.2** (1/5)

### Remplissage Recommandé

**Profil Master IA:**

| vs | Moyenne | Math | Exp | Engagement |
|----|---------|------|-----|-----------|
| **Moyenne** | 1 | 1/2 | 2 | 3 |
| **Math** | 2 | 1 | 3 | 5 |
| **Exp** | 1/2 | 1/3 | 1 | 2 |
| **Engagement** | 1/3 | 1/5 | 1/2 | 1 |

**Interprétation:**
- Math est 2× plus importante que Moyenne
- Moyenne est 2× plus importante que Expérience
- etc.

### Calculer les Poids

1. **Entrez vos comparaisons** dans le triangle supérieur
2. **Cliquez "Calculate Weights"**
3. Attendez le résultat (< 1 sec)

### Résultats

Vous verrez:

#### ✅ Poids Calculés

```
Moyenne:     45% ████████░
Math:        35% ███████░░
Expérience:  15% ███░░░░░░
Engagement:  5%  █░░░░░░░░
```

#### 🔍 Consistency Ratio (CR)

Affichage du CR:
```
CR = 0.0523
✓ Valid (CR < 0.1)  [Vert]
```

Interprétation:
- ✅ **CR < 0.1**: Vos comparaisons sont **cohérentes** ✓
- ⚠️ **CR ≥ 0.1**: Vos comparaisons sont **incohérentes** → Réviser

### Si CR est Mauvais

**Exemple:** CR = 0.45 (> 0.1)

Actions:
1. **Réviser vos comparaisons**
   - Cherchez les contradictions logiques
   - Exemple: Si `A > B` et `B > C`, mais `C > A` → Incohérent!

2. **Relancer le calcul**
   - Modifiez quelques valeurs
   - Cliquez "Calculate Weights" à nouveau

3. **Tips:**
   - Commencez par les grandes différences (1, 3, 5, 7, 9)
   - Évitez les comparaisons trop nuancées (2.5, 4.3, etc.)
   - Testez sur un sous-ensemble de critères

### Boutons d'Action

```
← Back                          [Revenir aux critères]
Calculate Weights              [Relancer calcul]
Proceed to Ranking →           [Continuer] (actif si CR < 0.1)
```

---

## Étape 5: Consulter les Résultats

### L'app Lance le Classement

Après clic sur "Proceed to Ranking →":

1. **Loading**: Affichage d'un spinner
2. **Backend Processing**:
   - Charge les données
   - Applique TOPSIS avec vos poids
   - Applique ML (si disponible)
   - Fusionne les résultats (hybride)
3. **Affichage des Résultats** (5-10 secondes)

### Statistiques Globales

```
Total Candidates:    150
Top Score:           0.8756
Average Score:       0.5234
Min Score:           0.1234
```

### Criteria Weights

Affichage graphique:

```
Moyenne:     45% ████████░
Math:        35% ███████░░
Expérience:  15% ███░░░░░░
Engagement:  5%  █░░░░░░░░
```

### Top 10 (ou Top N)

Tableau interactif:

| Rank | ID | TOPSIS_Score | Hybrid_Score | ML_Score |
|------|-------|--------------|--------------|----------|
| 1 | 045 | 0.87 | 0.85 | 0.83 |
| 2 | 012 | 0.85 | 0.84 | 0.82 |
| 3 | 089 | 0.83 | 0.81 | 0.79 |
| ... | ... | ... | ... | ... |

**Colonnes:**
- **Rank**: Position finale (1 = meilleur)
- **ID**: Identifiant candidat
- **TOPSIS_Score**: Score TOPSIS (0-1)
- **Hybrid_Score**: Score fusion final
- **ML_Score**: Prédiction ML (optionnel)

### Télécharger les Résultats

```
[Download CSV] → rankings_<date>.csv
[Download Excel] → rankings_<date>.xlsx
```

Fichiers contiennent:
- Tous les candidats (pas juste top 10)
- Tous les critères
- Classement final
- Scores détaillés

### Recommencer

```
[Start Over] → Retour étape 1
```

---

## Dépannage

### Erreur: "File has no rows"

**Cause:** Fichier CSV vide ou format invalide

**Solution:**
1. Vérifiez que le fichier n'est pas vide
2. Vérifiez le format (CSV/Excel valide)
3. Rechargez le fichier

### Erreur: "No ID column found"

**Cause:** Pas de colonne "ID" ou équivalente

**Solution:**
1. Renommez votre colonne ID en `ID`, `Référence`, ou `Code`
2. Sauvegardez et rechargez

### Erreur: "Select at least 2 criteria"

**Cause:** Vous avez sélectionné < 2 critères

**Solution:**
- Cochez au minimum 2 critères
- Cliquez "Continue..."

### Erreur: "Matrix is inconsistent! CR > 0.1"

**Cause:** Vos comparaisons AHP manquent de cohérence

**Solution:**
1. **Analysez vos comparaisons**
   - Cherchez les cycles logiques
   - Exemple: A > B, B > C, mais C > A = Incohérent!

2. **Ajustez les valeurs**
   ```
   Essayez: Réduire les écarts (9 → 7 → 5)
   Ou: Augmenter la cohérence avec des valeurs intermédiaires (1, 2, 3)
   ```

3. **Recalculez**

### Erreur: "No numeric columns detected"

**Cause:** Les colonnes sont en texte, pas numérique

**Solution:**
1. Vérifiez le format des données
2. Convertissez à nombres dans Excel/CSV
3. Rechargez

### Résultats Bizarres

**Symptôme:** Un candidat classe très haut/bas inattendu

**Cause Possibles:**
1. Outliers dans les données
2. Poids AHP mal calibrés
3. Critères non normalisés

**Solution:**
1. Vérifiez les données brutes (QA Report)
2. Ajustez la matrice AHP
3. Relancez le classement

---

## FAQ

### Q1: Combien de candidats minimum?

**R:** Techniquement 2, mais **au minimum 10** recommandé pour que TOPSIS soit pertinent.

### Q2: Combien de critères?

**R:** **2-15 critères optimaux**. Au-delà, la matrice AHP devient difficile à gérer.

### Q3: Mes données ont des textes dans les colonnes numériques?

**R:** L'app convertit auto:
- "Oui" → 1, "Non" → 0
- "Supérieur à 12" → 12.5
- Autres textes → colonnes ignorées

### Q4: Comment gérer les valeurs manquantes?

**R:** L'app les remplace par la **médiane** de la colonne automatiquement.

### Q5: Puis-je modifier les résultats après classement?

**R:** Non, le classement est immédiat. Pour changer:
1. Modifiez la matrice AHP
2. Relancez le classement

### Q6: Quelle est la différence TOPSIS vs Hybrid?

**R:**
- **TOPSIS**: Basé uniquement sur vos poids AHP
- **Hybrid**: Combine TOPSIS + ML (si données suffisantes)
- Utilisez **Hybrid_Score** pour plus de robustesse

### Q7: Puis-je exporter pour Excel?

**R:** Oui! Bouton "Download Excel" crée un `.xlsx` prêt à analyser.

### Q8: Comment le CR se calcule?

**R:** Formule Saaty: `CR = CI / RI`
- **CI**: Indice de Consistance
- **RI**: Indice Aléatoire (dépend du nombre critères)
- **Threshold**: < 0.1 pour cohérence acceptable

### Q9: Puis-je relancer avec d'autres données?

**R:** Oui! "Start Over" revient à l'étape 1 (upload) sans garder les données précédentes.

### Q10: Qui peut utiliser l'app?

**R:** Tout **décideur/coordinateur de formation** ayant:
- ✅ Données candidats structurées
- ✅ Critères clairement définis
- ✅ Capacité à évaluer l'importance relative (matrice AHP)

---

## Support

En cas de problème:
1. Vérifiez le format des données (Sect. 2)
2. Consultez la section Dépannage
3. Relisez le FAQ
4. Réessayez en suivant les étapes

---

**Dernière mise à jour:** Mai 2026
**Version:** 1.0
**Auteur:** Équipe MCDM Ranking
