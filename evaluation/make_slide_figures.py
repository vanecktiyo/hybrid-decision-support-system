# -*- coding: utf-8 -*-
"""
Génère les figures de la présentation (slides) à partir des données et des
résultats d'évaluation, dans un style cohérent avec le thème Beamer.

Sorties -> version_2/slides/images/
  - class_distribution.png : répartition des 4 classes (jeu complet)
  - model_comparison.png   : F1-macro (VC) des 6 modèles, forêt aléatoire mise en avant
  - confusion_matrix.png   : matrice de confusion sur le jeu de test (heatmap)
Et recopie alpha_sweep.png + captures utiles depuis rapport/images/.
"""
import os
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results")
RAP_IMG = os.path.join(ROOT, "rapport", "images")
OUT = os.path.join(ROOT, "slides", "images")
os.makedirs(OUT, exist_ok=True)

PRIMARY = "#1B3A6B"
ACCENT = "#2563EB"
MLPURPLE = "#7C3AED"
GOOD = "#0A7C42"
GRAY = "#9AA7BD"
SOFT = "#F1F4F9"

CLASS_ORDER = ["Non_classe", "Moyen", "Bon", "Excellent"]
CLASS_LABEL = {"Non_classe": "Non_classé", "Moyen": "Moyen", "Bon": "Bon", "Excellent": "Excellent"}

plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#444444"})


def fig_class_distribution():
    src = pd.read_csv(os.path.join(ROOT, "data", "input", "candidats_mcdm.csv"))
    counts = src["classe"].value_counts().reindex(CLASS_ORDER)
    labels = [CLASS_LABEL[c] for c in CLASS_ORDER]
    colors = [GRAY, ACCENT, PRIMARY, GOOD]
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    bars = ax.bar(labels, counts.values, color=colors, edgecolor="white")
    for b, v in zip(bars, counts.values):
        ax.text(b.get_x() + b.get_width() / 2, v + 6, str(int(v)),
                ha="center", va="bottom", fontweight="bold")
    ax.set_ylabel("Nombre de candidats")
    ax.set_title("Répartition des classes (815 candidatures)", color=PRIMARY, fontweight="bold")
    ax.set_ylim(0, max(counts.values) * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "class_distribution.png"), dpi=160)
    plt.close(fig)


def fig_model_comparison():
    comp = pd.read_csv(os.path.join(RES, "eval_model_comparison.csv"))
    comp = comp.sort_values("f1_macro_vc", ascending=True)  # horizontal: best on top
    names = comp["modele"].tolist()
    vals = comp["f1_macro_vc"].values
    colors = [MLPURPLE if "aléatoire" in n.lower() else ACCENT for n in names]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    bars = ax.barh(names, vals, color=colors, edgecolor="white")
    for b, v in zip(bars, vals):
        ax.text(v + 0.006, b.get_y() + b.get_height() / 2, f"{v:.3f}".replace(".", ","),
                va="center", fontweight="bold", fontsize=11)
    ax.set_xlabel("$F_1$-macro (validation croisée)")
    ax.set_xlim(0.7, 1.0)
    ax.set_title("Comparaison des modèles", color=PRIMARY, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "model_comparison.png"), dpi=160)
    plt.close(fig)


def fig_confusion_matrix():
    cm = pd.read_csv(os.path.join(RES, "eval_confusion_matrix.csv"), index_col=0)
    labels = [CLASS_LABEL[c] for c in CLASS_ORDER]
    mat = cm.values.astype(int)
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(4)); ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_yticks(range(4)); ax.set_yticklabels(labels)
    thr = mat.max() / 2
    for i in range(4):
        for j in range(4):
            ax.text(j, i, mat[i, j], ha="center", va="center",
                    color="white" if mat[i, j] > thr else "#1B3A6B", fontweight="bold")
    ax.set_xlabel("Classe prédite"); ax.set_ylabel("Classe réelle")
    ax.set_title("Matrice de confusion (jeu de test)", color=PRIMARY, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "confusion_matrix.png"), dpi=160)
    plt.close(fig)


def copy_assets():
    # alpha sweep (déjà généré pour le rapport)
    a = os.path.join(RAP_IMG, "alpha_sweep.png")
    if os.path.exists(a):
        shutil.copy(a, os.path.join(OUT, "alpha_sweep.png"))
    # captures utiles
    for name in ["ui_ahp.png", "ui_resultats.png", "ui_shap.png"]:
        s = os.path.join(RAP_IMG, name)
        if os.path.exists(s):
            shutil.copy(s, os.path.join(OUT, name))


if __name__ == "__main__":
    fig_class_distribution()
    fig_model_comparison()
    fig_confusion_matrix()
    copy_assets()
    print("Figures écrites dans :", OUT)
    print(os.listdir(OUT))
