# -*- coding: utf-8 -*-
"""
Évaluation rigoureuse du module d'apprentissage et de son apport au classement
==============================================================================

Démarche méthodologique reproduite ici, de bout en bout, sur un SEUL découpage
train/test (cohérence des chiffres) :

  1. Découpe stratifiée train/test (80/20).
  2. Comparaison de six classifieurs par validation croisée sur le TRAIN.
  3. Sélection du meilleur modèle (F1-macro), puis optimisation de ses
     hyperparamètres (RandomizedSearchCV) sur le TRAIN.
  4. Performance du modèle retenu sur le JEU DE TEST (données non vues).
  5. Classement SANS apprentissage (TOPSIS seul) puis AVEC (fusion).
  6. Apport du ML : corrélation de Spearman + précision top-20 %, et balayage
     du poids de fusion alpha pour situer le meilleur compromis.

Pourquoi recalculer le ML (et pas réutiliser la colonne ML_Score de l'export) ?
-------------------------------------------------------------------------------
  * TOPSIS est NON supervisé : son score, exporté par l'interface avec les VRAIS
    poids AHP du décideur, est valide candidat par candidat -> on le réutilise.
  * Le ML est supervisé : on le ré-entraîne sur le TRAIN uniquement et on prédit
    le TEST, pour une estimation honnête de la généralisation. La colonne
    ML_Score de l'export (modèle entraîné sur 100 % des données) est ignorée.

Garanties anti-fuite
--------------------
  * Features = EXACTEMENT les 5 critères, et rien d'autre.
  * `classe` = cible (y), jamais une feature.
  * `Classement` (rang réel, source de la vérité terrain) = référence
    d'évaluation uniquement, JAMAIS feature, JAMAIS pour entraîner.
  * `ID` sert seulement à la jointure.
  * Mise à l'échelle dans un Pipeline (ajustée sur le train seul).

Sorties
-------
  CSV  -> evaluation/results/
  PNG  -> rapport/images/alpha_sweep.png  (courbe d'apport selon alpha)
"""

from __future__ import annotations

import os
import warnings
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
)
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import (
    train_test_split, cross_val_score, StratifiedKFold, RandomizedSearchCV,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix,
)

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # version_2/

EXPORT_FILE = os.path.join(HERE, "ranking_results_candidats_mcdm_csv (1).csv")
SOURCE_FILE = os.path.join(ROOT, "data", "input", "candidats_mcdm.csv")
OUT_DIR = os.path.join(HERE, "results")
FIG_DIR = os.path.join(ROOT, "rapport", "images")

# Les 5 critères, et EUX SEULS, sont les features. Liste blanche explicite.
FEATURES = ["Moyenne", "Niveau_Math", "Alternance", "Licence_EDN", "Diplome_norm"]

# Ordre des classes (du moins bon au meilleur) -> encodage entier ordonné.
CLASS_ORDER = ["Non_classe", "Moyen", "Bon", "Excellent"]

TEST_SIZE = 0.2
RANDOM_STATE = 42
N_FOLDS = 5
ALPHA_DEFAULT = 0.6
ALPHA_GRID = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]   # 1.0 = TOPSIS seul ; 0.0 = ML seul
TOP_FRACTION = 0.20

# Noms d'affichage des modèles
DISPLAY = {
    "random_forest": "Forêt aléatoire",
    "gradient_boosting": "Gradient Boosting",
    "xgboost": "XGBoost",
    "decision_tree": "Arbre de décision",
    "logistic_regression": "Régression logistique",
    "svm": "SVM (RBF)",
}

# Grille d'optimisation du modèle gagnant (identique au backend, ml_trainer.py)
RF_PARAM_GRID = {
    "model__n_estimators": [50, 100, 200, 300],
    "model__max_depth": [5, 8, 10, 15, None],
    "model__min_samples_split": [2, 5, 10],
    "model__min_samples_leaf": [1, 2, 4],
}


def candidate_models() -> dict:
    """Six classifieurs candidats (config par défaut, identique à l'esprit du backend)."""
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5,
            class_weight="balanced", random_state=RANDOM_STATE),
        "gradient_boosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "decision_tree": DecisionTreeClassifier(
            max_depth=10, class_weight="balanced", random_state=RANDOM_STATE),
        "logistic_regression": LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE),
        "svm": SVC(kernel="rbf", class_weight="balanced",
                   probability=True, random_state=RANDOM_STATE),
    }
    try:
        from xgboost import XGBClassifier
        models["xgboost"] = XGBClassifier(
            random_state=RANDOM_STATE, eval_metric="mlogloss",
            tree_method="hist", verbosity=0)
    except Exception as exc:
        print(f"[info] XGBoost indisponible ({exc}); modèle ignoré.")
    return models


def make_pipeline(estimator) -> Pipeline:
    """MinMaxScaler + estimateur : la mise à l'échelle est ajustée par repli/train."""
    fresh = estimator.__class__(**estimator.get_params())
    return Pipeline([("scaler", MinMaxScaler()), ("model", fresh)])


# --------------------------------------------------------------------------- #
# Métriques de qualité de classement
# --------------------------------------------------------------------------- #
def spearman_vs_ranking(score: np.ndarray, classement: np.ndarray) -> float:
    """Spearman entre score (haut=meilleur) et -classement (sorte que positif=bon alignement)."""
    rho, _ = spearmanr(score, -classement)
    return float(rho)


def precision_top_k_rang(score: np.ndarray, classement: np.ndarray,
                         frac: float = TOP_FRACTION) -> float:
    """Précision top-k par le rang : proportion du top-k prédit qui est dans le top-k réel."""
    n = len(score)
    k = max(1, int(round(frac * n)))
    top_pred = set(np.argsort(-score)[:k].tolist())
    top_true = set(np.argsort(classement)[:k].tolist())
    return len(top_pred & top_true) / k


def precision_top_k_classe(score: np.ndarray, y_true_int: np.ndarray,
                           good_classes: set, frac: float = TOP_FRACTION) -> float:
    """Précision top-k par la classe : proportion du top-k prédit appartenant à {Bon, Excellent}."""
    n = len(score)
    k = max(1, int(round(frac * n)))
    top_idx = np.argsort(-score)[:k]
    return float(np.isin(y_true_int[top_idx], list(good_classes)).sum()) / k


# --------------------------------------------------------------------------- #
def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    # 1) Chargement + jointure ------------------------------------------------ #
    exp = pd.read_csv(EXPORT_FILE)
    src = pd.read_csv(SOURCE_FILE)
    gt = src[["ID", "classe", "Classement"]].copy()
    df = exp.merge(gt, on="ID", how="inner", validate="one_to_one")

    class_to_int = {c: i for i, c in enumerate(CLASS_ORDER)}
    int_to_class = {i: c for c, i in class_to_int.items()}
    best_idx = len(CLASS_ORDER) - 1
    good_classes = {class_to_int["Bon"], class_to_int["Excellent"]}
    df["y"] = df["classe"].map(class_to_int)
    if df["y"].isna().any():
        raise ValueError(f"Classe(s) inconnue(s) : {df.loc[df['y'].isna(), 'classe'].unique()}")
    df["y"] = df["y"].astype(int)
    X, y = df[FEATURES].copy(), df["y"].values
    print(f"[1] Jointure : {len(df)} candidats | features = {FEATURES}")

    # 2) Découpe stratifiée train/test --------------------------------------- #
    idx = np.arange(len(df))
    idx_tr, idx_te = train_test_split(
        idx, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y)
    X_tr, X_te = X.iloc[idx_tr], X.iloc[idx_te]
    y_tr, y_te = y[idx_tr], y[idx_te]
    print(f"[2] Split stratifié : {len(idx_tr)} train / {len(idx_te)} test")

    cv = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    # 3) Comparaison des six modèles (VC sur le train) ----------------------- #
    print(f"[3] Comparaison des modèles (VC {N_FOLDS} replis, sur le train)...")
    rows = []
    for name, est in candidate_models().items():
        try:
            pipe = make_pipeline(est)
            f1 = cross_val_score(pipe, X_tr, y_tr, cv=cv, scoring="f1_macro")
            acc = cross_val_score(make_pipeline(est), X_tr, y_tr, cv=cv, scoring="accuracy")
            rows.append({
                "modele": DISPLAY[name], "cle": name,
                "f1_macro_vc": round(float(f1.mean()), 4),
                "f1_macro_ecart_type": round(float(f1.std()), 4),
                "precision_vc": round(float(acc.mean()), 4),
            })
            print(f"     {DISPLAY[name]:<22} F1-macro={f1.mean():.4f}  acc={acc.mean():.4f}")
        except Exception as exc:
            print(f"     {DISPLAY[name]:<22} ÉCHEC : {exc}")
    comp = pd.DataFrame(rows).sort_values("f1_macro_vc", ascending=False).reset_index(drop=True)

    best_key = comp.iloc[0]["cle"]
    best_f1 = comp.iloc[0]["f1_macro_vc"]
    print(f"    -> meilleur modèle : {DISPLAY[best_key]} (F1-macro VC = {best_f1})")

    # 4) Optimisation des hyperparamètres du modèle retenu (sur le train) ----- #
    base_models = candidate_models()
    default_pipe = make_pipeline(base_models[best_key])
    chosen_pipe, tuned_score, best_params = default_pipe, best_f1, {}
    if best_key == "random_forest":
        print("[4] Optimisation (RandomizedSearchCV) de la forêt aléatoire...")
        search = RandomizedSearchCV(
            estimator=make_pipeline(base_models[best_key]),
            param_distributions=RF_PARAM_GRID, n_iter=20, scoring="f1_macro",
            cv=cv, random_state=RANDOM_STATE, n_jobs=-1)
        search.fit(X_tr, y_tr)
        print(f"     meilleur F1-macro VC après réglage = {search.best_score_:.4f}")
        print(f"     paramètres = {search.best_params_}")
        if search.best_score_ > best_f1:
            chosen_pipe = search.best_estimator_
            tuned_score = round(float(search.best_score_), 4)
            best_params = {k.replace("model__", ""): v for k, v in search.best_params_.items()}
            print("     -> configuration réglée RETENUE (améliore le défaut).")
        else:
            print("     -> configuration par défaut conservée (le réglage n'améliore pas).")
    else:
        print(f"[4] (Optimisation détaillée prévue pour la forêt aléatoire ; modèle retenu = {DISPLAY[best_key]}.)")

    # 5) Réentraînement sur le train, prédiction du test --------------------- #
    final_pipe = clone(chosen_pipe).fit(X_tr, y_tr)
    y_pred = final_pipe.predict(X_te)
    classes_ = final_pipe.named_steps["model"].classes_
    raw_proba = final_pipe.predict_proba(X_te)
    proba_full = np.zeros((len(X_te), len(CLASS_ORDER)))
    for j, c in enumerate(classes_):
        proba_full[:, int(c)] = raw_proba[:, j]
    proba_best = proba_full[:, best_idx]
    print(f"[5] Modèle retenu réentraîné sur le train, prédiction du test ({len(X_te)})")

    # 6) Performance sur le test --------------------------------------------- #
    labels_int = list(range(len(CLASS_ORDER)))
    acc = accuracy_score(y_te, y_pred)
    f1m = f1_score(y_te, y_pred, average="macro", labels=labels_int)
    rep = classification_report(y_te, y_pred, labels=labels_int,
                                target_names=CLASS_ORDER, output_dict=True, zero_division=0)
    perf_rows = [
        {"indicateur": "Modèle retenu", "valeur": DISPLAY[best_key]},
        {"indicateur": "Exactitude (test)", "valeur": round(acc, 4)},
        {"indicateur": "F1-macro (test)", "valeur": round(f1m, 4)},
        {"indicateur": "F1-macro VC (train, retenu)", "valeur": tuned_score},
        {"indicateur": "n_test", "valeur": int(len(y_te))},
    ]
    for c in CLASS_ORDER:
        perf_rows.append({"indicateur": f"F1 classe {c}", "valeur": round(rep[c]["f1-score"], 4)})
        perf_rows.append({"indicateur": f"support test {c}", "valeur": int(rep[c]["support"])})
    perf = pd.DataFrame(perf_rows)
    cm = confusion_matrix(y_te, y_pred, labels=labels_int)
    cm_df = pd.DataFrame(cm, index=[f"vrai_{c}" for c in CLASS_ORDER],
                         columns=[f"pred_{c}" for c in CLASS_ORDER])

    # 7) Composantes de classement sur le test ------------------------------- #
    test = df.iloc[idx_te].copy().reset_index(drop=True)
    topsis = test["TOPSIS_Score"].values
    classement_te = test["Classement"].values
    fusion_default = ALPHA_DEFAULT * topsis + (1 - ALPHA_DEFAULT) * proba_best

    sum_rows = []
    for nom, sc in [("TOPSIS_seul", topsis), ("ML_seul", proba_best),
                    (f"Fusion_alpha_{ALPHA_DEFAULT}", fusion_default)]:
        rho, pval = spearmanr(sc, -classement_te)   # p-value de la corrélation
        sum_rows.append({
            "methode": nom,
            "spearman_vs_classement_reel": round(float(rho), 4),
            "spearman_pvalue": "{:.2e}".format(pval),
            "precision_top20_rang": round(precision_top_k_rang(sc, classement_te), 4),
            "precision_top20_classe_bon_excellent": round(precision_top_k_classe(sc, y_te, good_classes), 4),
        })
    summary = pd.DataFrame(sum_rows)

    # 8) Balayage de alpha ---------------------------------------------------- #
    alpha_rows = []
    for a in ALPHA_GRID:
        fused = a * topsis + (1 - a) * proba_best
        alpha_rows.append({
            "alpha": a,
            "composition": ("TOPSIS seul" if a == 1.0 else "ML seul" if a == 0.0
                            else f"{a:.1f} TOPSIS + {1-a:.1f} ML"),
            "spearman_vs_classement_reel": round(spearman_vs_ranking(fused, classement_te), 4),
            "precision_top20_rang": round(precision_top_k_rang(fused, classement_te), 4),
            "precision_top20_classe_bon_excellent": round(precision_top_k_classe(fused, y_te, good_classes), 4),
        })
    alpha_df = pd.DataFrame(alpha_rows)

    # 9) Tables détaillées TOPSIS / Fusion sur le test ----------------------- #
    topsis_out = pd.DataFrame({
        "ID": test["ID"].values, "classe_reelle": test["classe"].values,
        "Classement_reel": classement_te, "TOPSIS_Score": topsis,
    }).sort_values("TOPSIS_Score", ascending=False).reset_index(drop=True)
    topsis_out.insert(0, "rang_TOPSIS", np.arange(1, len(topsis_out) + 1))

    fusion_out = pd.DataFrame({
        "ID": test["ID"].values, "classe_reelle": test["classe"].values,
        "Classement_reel": classement_te, "TOPSIS_Score": topsis,
        "ML_proba_meilleure_classe": np.round(proba_best, 6),
        "Classe_predite_ML": [int_to_class[i] for i in y_pred],
        f"Fusion_Score_alpha_{ALPHA_DEFAULT}": np.round(fusion_default, 6),
    }).sort_values(f"Fusion_Score_alpha_{ALPHA_DEFAULT}", ascending=False).reset_index(drop=True)
    fusion_out.insert(0, "rang_Fusion", np.arange(1, len(fusion_out) + 1))

    # 10) Écriture des CSV ---------------------------------------------------- #
    comp.drop(columns=["cle"]).to_csv(os.path.join(OUT_DIR, "eval_model_comparison.csv"),
                                      index=False, encoding="utf-8-sig")
    perf.to_csv(os.path.join(OUT_DIR, "eval_ml_performance.csv"), index=False, encoding="utf-8-sig")
    cm_df.to_csv(os.path.join(OUT_DIR, "eval_confusion_matrix.csv"), encoding="utf-8-sig")
    summary.to_csv(os.path.join(OUT_DIR, "eval_summary.csv"), index=False, encoding="utf-8-sig")
    alpha_df.to_csv(os.path.join(OUT_DIR, "eval_alpha_sweep.csv"), index=False, encoding="utf-8-sig")
    topsis_out.to_csv(os.path.join(OUT_DIR, "eval_topsis_test.csv"), index=False, encoding="utf-8-sig")
    fusion_out.to_csv(os.path.join(OUT_DIR, "eval_fusion_test.csv"), index=False, encoding="utf-8-sig")
    if best_params:
        pd.DataFrame([best_params]).to_csv(os.path.join(OUT_DIR, "eval_best_params.csv"),
                                           index=False, encoding="utf-8-sig")

    # 11) Figure : courbe d'apport selon alpha ------------------------------- #
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a_sorted = alpha_df.sort_values("alpha")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    # Échelle commune (les deux indicateurs sont dans [0,1]) -> comparaison honnête :
    # le Spearman apparaît plat, la précision top-20 % varie réellement.
    ax.plot(a_sorted["alpha"], a_sorted["precision_top20_rang"],
            "o-", color="#1f5fa8", label="Précision top-20 %")
    ax.plot(a_sorted["alpha"], a_sorted["spearman_vs_classement_reel"],
            "s--", color="#a83232", label="Spearman (vs classement réel)")
    ax.axvline(ALPHA_DEFAULT, color="#888888", linestyle=":", linewidth=1.2)
    ax.text(ALPHA_DEFAULT + 0.015, 0.43, r"$\alpha = 0{,}6$ (défaut)",
            color="#555555", fontsize=9)
    ax.set_xlabel(r"$\alpha$  (poids de TOPSIS ; $1-\alpha$ = poids du ML)")
    ax.set_ylabel("Valeur de l'indicateur")
    ax.set_ylim(0.40, 0.80)
    ax.set_xticks(ALPHA_GRID)
    ax.set_title(r"Apport de la fusion selon le poids $\alpha$ (jeu de test)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="center left", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig_path = os.path.join(FIG_DIR, "alpha_sweep.png")
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)

    # 12) Récapitulatif console ---------------------------------------------- #
    pd.set_option("display.width", 130); pd.set_option("display.max_columns", 20)
    print("\n=== COMPARAISON DES MODÈLES (VC, train) ===")
    print(comp.drop(columns=["cle"]).to_string(index=False))
    print("\n=== PERFORMANCE DU MODÈLE RETENU (test) ===")
    print(perf.to_string(index=False))
    print("\n=== MATRICE DE CONFUSION (test) ===")
    print(cm_df.to_string())
    print("\n=== CLASSEMENT : TOPSIS vs ML vs FUSION (test) ===")
    print(summary.to_string(index=False))
    print("\n=== BALAYAGE DE ALPHA (test) ===")
    print(alpha_df.to_string(index=False))
    print(f"\n[OK] CSV -> {OUT_DIR}")
    print(f"[OK] Figure -> {fig_path}")


if __name__ == "__main__":
    main()
