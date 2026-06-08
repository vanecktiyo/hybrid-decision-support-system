# Script de soutenance (~15 min)

> Repères : viser ~14 min de parole + 1 min de marge. Les intercalaires de section (« Plan »
> surligné) servent de respirations : 5 s, on annonce la section et on enchaîne.
> Débit ~150 mots/min. Ne pas lire — ce sont des repères.

---

## 1. Titre  · ~20 s
Bonjour, je m'appelle Vaneck DAGAR TIYO. Je vous présente mon travail :
un **système d'aide intelligente au classement des candidatures académiques**, qui combine
l'aide à la décision multicritère et l'apprentissage automatique. Ce travail a été encadré par
Madame Faiza AJMI et Monsieur Jalal POSSIK.

## 2. Plan  · ~15 s
Je commencerai par le contexte et l'objectif, puis l'état de l'art, la méthode, les résultats,
avant d'aborder les limites, les perspectives et la conclusion.

---

## 3. Contexte et problématique  · ~50 s
Classer des candidatures académiques mobilise **plusieurs critères** et souvent **plusieurs
évaluateurs**. C'est un processus difficile à rendre **objectif, transparent et sans
ambiguïté** : les jugements sont subjectifs et la pondération des critères reste implicite.
C'est aussi **chronophage** quand les candidatures sont nombreuses, et les critères pertinents
**changent d'une formation à l'autre**.
D'où ma problématique : **comment automatiser ce classement de façon objective, transparente
et explicable, et qui s'améliore avec les décisions passées ?**

## 4. Objectif  · ~35 s
L'objectif est donc de concevoir un **outil générique** qui automatise ce classement, de
manière transparente et explicable. Trois propriétés visées : **générique** — les critères et
les classes sont configurables selon la formation ; **explicable** — chaque rang est justifié ;
et **adaptatif** — le système s'améliore à partir des décisions validées.

---

## 5. (Intercalaire) État de l'art  · ~5 s
Voyons d'abord ce que dit la littérature.

## 6. Revue systématique (PRISMA)  · ~40 s
J'ai mené une **revue systématique** selon la méthodologie PRISMA, en partant du problème
lui-même. Sur 142 références identifiées dans cinq bases, après suppression des doublons et
filtrage, j'ai retenu **56 travaux**, dont **12** servent de socle principal. C'est cette revue
qui a fait émerger les méthodes pertinentes : l'AHP, TOPSIS, l'apprentissage et l'IA explicable.

## 7. Positionnement  · ~45 s
Deux constats. D'un côté, l'**AHP–TOPSIS** est mûr pour le classement : transparent, mais
**statique** — il n'apprend pas des décisions passées. De l'autre, l'**apprentissage** exploite
l'historique mais reste **opaque**. Mon système se place **au croisement** : il combine les
deux et ajoute l'explicabilité, dans le prolongement des travaux de Poongothai et de James.

---

## 8. (Intercalaire) Méthode  · ~5 s
Venons-en à la méthode.

## 9. AHP — pondération des critères  · ~40 s
La première brique, l'**AHP**, sert à pondérer les critères. Le décideur compare les critères
**deux à deux** sur l'échelle de Saaty ; les poids sont obtenus comme le **vecteur propre
principal** de la matrice. La cohérence des jugements est contrôlée par le **ratio de cohérence
CR** : s'il dépasse 0,10, on demande de réviser. Dans notre cas, les critères sont les attributs
des candidatures, et la matrice est saisie à chaque usage : l'outil reste paramétrable.

## 10. TOPSIS — classement des candidats  · ~40 s
La deuxième brique, **TOPSIS**, produit le classement. On normalise, on pondère par les poids
AHP, puis on calcule pour chaque candidat sa **distance à la solution idéale** et à la solution
anti-idéale. Le coefficient de proximité **Cᵢ**, entre 0 et 1, donne le classement : plus on est
proche de 1, meilleur est le profil. Tous les critères sont orientés « bénéfice ».

## 11. Module d'apprentissage  · ~40 s
La troisième brique : l'**apprentissage**. À partir des **décisions validées** — la vérité
terrain — un modèle supervisé apprend à associer le **profil d'un candidat** à sa **classe**.
Les entrées sont les critères ; la colonne qui définit la vérité terrain n'est jamais une
entrée. On **compare plusieurs modèles**, on retient le meilleur par validation croisée, et les
prédictions sont rendues **explicables** par SHAP.

## 12. Architecture  · ~30 s
Côté réalisation : une architecture **client–serveur** découplée — un frontend React en cinq
étapes guidées, un backend Flask qui orchestre les modules métier (AHP, TOPSIS, ML, fusion).
Les échanges se font en JSON ; le stockage est volontairement léger pour le prototype.

## 13. Pipeline de traitement  · ~30 s
L'enchaînement complet : **préparation** des données, **AHP** pour les poids, **TOPSIS** pour le
score, **apprentissage** pour la prédiction et SHAP, puis la **fusion** des deux en un score
final, qui donne le classement et ses justifications.

---

## 14. (Intercalaire) Résultats  · ~5 s
Passons aux résultats.

## 15. Jeu de données  · ~35 s
J'ai travaillé sur un jeu **réel de 815 candidatures**, décrites par cinq critères, avec pour
vérité terrain le **classement réel** réparti en quatre classes ordonnées. La distribution est
**déséquilibrée** : la classe « Excellent » est rare — un point important pour l'évaluation.

## 16. Comparaison des six modèles  · ~35 s
J'ai comparé **six classifieurs** par validation croisée. Les modèles d'arbres dominent
nettement les modèles linéaires, et c'est la **forêt aléatoire** qui obtient le meilleur
F1-macro. Elle est donc retenue, puis ses hyperparamètres sont optimisés.

## 17. Performance sur le jeu de test  · ~40 s
Sur un **jeu de test mis de côté avant tout entraînement**, le modèle atteint **96 % d'exactitude**
et un **F1-macro de 0,95**. Surtout, la performance reste **équilibrée jusqu'à la classe rare**,
l'« Excellent » — ce que la matrice de confusion confirme : les erreurs sont rares et entre
classes voisines.

## 18. Pondération AHP (interface)  · ~25 s
Voici concrètement la matrice de comparaison saisie dans l'application : les poids des critères
sont calculés automatiquement, et le ratio de cohérence — ici 0,058 — valide la cohérence des
jugements.

## 19. Classement : sans ML vs avec ML  · ~60 s  *(diapo clé)*
Et voici l'effet de l'apprentissage sur le classement. À gauche, TOPSIS seul ; à droite, avec
la fusion. Regardez les mouvements : le candidat **#648** passe de la 7ᵉ à la **2ᵉ** place, le
**#498**, absent du top 8, entre directement à la **3ᵉ** place. À l'inverse, le **#376**,
2ᵉ avec TOPSIS, **sort du top 8** — le modèle l'a jugé moins bon. Et le **#132** reste stable.
Autrement dit, l'apprentissage **réordonne le haut du classement** là où ça compte.

## 20. Explicabilité  · ~40 s
Chaque rang est **justifié de deux façons** : du côté TOPSIS, la contribution de chaque
**critère** au score ; du côté du modèle, les valeurs **SHAP**, qui montrent la contribution de
chaque **variable** à la prédiction, candidat par candidat. Le décideur comprend donc
**pourquoi** un candidat occupe son rang.

## 21. Apport de l'apprentissage  · ~70 s  *(diapo clé)*
Maintenant, l'apport est-il réel ? Je le mesure sur le jeu de test avec deux indicateurs : le
**Spearman**, qui juge l'ordre global, et la **précision au sommet** — la qualité des 20 % les
mieux classés. Résultat : la fusion **conserve l'ordre global** (Spearman autour de 0,51) et
**améliore le sommet** — la précision top-20 % passe de **0,70 à 0,76**. La courbe montre que ce
gain est maximal autour de **α = 0,6**, la valeur par défaut.
Enfin, j'ai vérifié que ce lien n'est pas dû au hasard : un **test de significativité de
Spearman** donne une p-value **bien inférieure à 0,001**, très en dessous du seuil de 5 % — le
lien est **statistiquement significatif**.

---

## 22. (Intercalaire) Limites et perspectives  · ~5 s
J'en viens aux limites et aux perspectives.

## 23. Limites et perspectives  · ~55 s
Trois limites, chacune ouvrant une piste. D'abord, l'évaluation porte sur **un seul jeu de
données** : il faudra une **validation élargie**, sur d'autres contextes et en conditions
réelles. Ensuite, l'apprentissage est **supervisé**, donc dépendant des décisions déjà
étiquetées ; une piste non explorée serait d'essayer des **approches non supervisées** pour
réduire cette dépendance. Enfin, c'est un **prototype mono-utilisateur** : l'étape suivante est
un **déploiement multi-utilisateur** avec base de données, authentification et traçabilité.

---

## 24. (Intercalaire) Conclusion  · ~5 s

## 25. Conclusion  · ~50 s
Pour conclure : j'ai conçu un système **hybride** — AHP, TOPSIS et apprentissage — **générique**
et **explicable**. Le modèle est fiable sur des données non vues, avec un F1-macro d'environ
**0,95**, et surtout la fusion **améliore concrètement la présélection** des meilleurs candidats
par rapport à TOPSIS seul, sans dégrader l'ordre d'ensemble. Le classement produit est
**transparent et justifiable**, ce qui répond au sujet.
Je vous remercie de votre attention et je suis à votre disposition pour vos questions.

---

### Aide-mémoire chiffres
- **815** candidatures · 5 critères · 4 classes (Excellent rare)
- 6 modèles comparés → **forêt aléatoire** ; test : **exactitude 0,957 / F1-macro 0,945**
- CR matrice AHP = **0,058**
- Mouvements : #648 7→2 · #498 horstop→3 · #376 2→horstop · #132 8→8
- Apport : Spearman ≈ **0,51** · top-20 % **0,70 → 0,76** · α optimal **0,6**
- Test Spearman : **p < 0,001 ≪ α = 0,05**

### Réponses prêtes (Q&R)
- *Pourquoi la forêt aléatoire ?* meilleur F1-macro en VC, robuste, gère le déséquilibre, et explicable (SHAP).
- *#648 va au rang 1 ?* Non : **rang 2** (le #38 reste 1ᵉ). Dire « de la 7ᵉ à la 2ᵉ ».
- *Pas de fuite ?* la cible (classement réel) n'est jamais une variable d'entrée ; test mis de côté avant l'entraînement.
- *Pourquoi α = 0,6 ?* maximise la précision au sommet sans dégrader l'ordre global (cf. courbe).
