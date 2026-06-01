import React, { useState, useEffect, useRef } from 'react';
import './LandingPage.css';

const features = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    title: 'Pondération AHP',
    description: "Construisez une matrice de comparaison par paires selon la méthode Analytic Hierarchy Process. Le ratio de cohérence (CR) garantit la fiabilité des poids calculés.",
    tag: 'Analytic Hierarchy Process',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M18 20V10M12 20V4M6 20v-6" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    title: 'Classement TOPSIS',
    description: "Ordonnez les candidats par proximité à la solution idéale. Chaque critère est normalisé automatiquement lors du calcul (valeur haute = meilleur profil).",
    tag: 'Multi-Criteria Ranking',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" strokeLinecap="round"/>
      </svg>
    ),
    title: 'Classification ML',
    description: "Plusieurs classificateurs (Random Forest, Gradient Boosting, SVM, XGBoost…) sont comparés ; le meilleur prédit la classe de chaque candidat, évalué honnêtement sur des données de test.",
    tag: 'Machine Learning',
  },
];

const steps = [
  { num: '01', title: 'Import des données', desc: 'Chargez votre fichier CSV ou Excel. Un rapport qualité automatique vérifie les valeurs manquantes et les anomalies.' },
  { num: '02', title: 'Sélection des critères', desc: "Choisissez les critères numériques et catégoriels (valeur haute = meilleur), et la colonne cible de vérité terrain pour le module ML." },
  { num: '03', title: 'Matrice AHP', desc: 'Renseignez vos préférences par paires. Les poids AHP sont calculés et le ratio de cohérence est vérifié automatiquement.' },
  { num: '04', title: 'Analyse hybride', desc: "TOPSIS classe les alternatives. Le modèle ML prédit les classes et enrichit le score final via la formule de fusion pondérée." },
  { num: '05', title: 'Résultats & Export', desc: "Consultez le classement détaillé avec les scores TOPSIS, les probabilités ML et les explications SHAP. Exportez en CSV ou Excel." },
];

const LandingPage = ({ onStart, onValidate }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close the menu on outside click or Escape
  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const handleMenuAction = (action) => {
    setMenuOpen(false);
    if (action) action();
  };

  return (
  <div className="landing">

    {/* ── Nav ── */}
    <nav className="landing-nav">
      <div className="landing-nav-inner">
        <div className="landing-brand">
          <svg className="brand-icon" viewBox="0 0 60 56" fill="none">
            <polygon points="30,4  58,20  30,36  2,20"  fill="#1e3a8a"/>
            <polygon points="30,18 54,31  30,44  6,31"  fill="#2563eb" opacity="0.75"/>
            <polygon points="30,30 50,41  30,52 10,41"  fill="#3b82f6" opacity="0.5"/>
          </svg>
          <span className="brand-name">Admission<span className="brand-pro"> Ranking</span></span>
        </div>
        <div className="landing-nav-links">
          <button className="btn btn-primary" onClick={onStart}>
            Lancer l'application
          </button>

          {/* ── Menu (extensible : validation, authentification, …) ── */}
          <div className="nav-menu" ref={menuRef}>
            <button
              className="nav-menu-trigger"
              onClick={() => setMenuOpen(o => !o)}
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="Ouvrir le menu"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2.5" strokeLinecap="round">
                <line x1="3" y1="6"  x2="21" y2="6"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            </button>
            {menuOpen && (
              <div className="nav-menu-dropdown" role="menu">
                <button className="nav-menu-item" role="menuitem" onClick={() => handleMenuAction(onValidate)}>
                  Soumettre une validation
                </button>
                <button className="nav-menu-item nav-menu-item-disabled" role="menuitem" disabled title="Bientôt disponible">
                  Connexion
                  <span className="nav-menu-soon">bientôt</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>

    {/* ── Hero ── */}
    <section className="landing-hero">
      <div className="hero-inner">
        <div className="hero-label">Système de Classement Académique</div>
        <h1 className="hero-title">
          Décisions objectives et<br />transparentes par critères multiples
        </h1>
        <p className="hero-sub">
          Un outil d'aide à la décision qui transforme vos critères d'admission en un classement fiable, objectif et explicable.
        </p>
        <div className="hero-actions">
          <button className="btn btn-hero-primary" onClick={onStart}>
            Commencer l'analyse
          </button>
        </div>
      </div>
      <div className="hero-bg-shape"/>
    </section>

    {/* ── Features ── */}
    <section className="landing-features">
      <div className="section-inner">
        <div className="section-label">Fonctionnalités</div>
        <h2 className="section-title">Une approche hybride rigoureuse</h2>
        <p className="section-sub">
          Chaque composant du système repose sur des méthodes reconnues dans la littérature académique.
        </p>
        <div className="features-grid">
          {features.map((f, i) => (
            <div className="feature-card" key={i}>
              <div className="feature-icon">{f.icon}</div>
              <div className="feature-tag">{f.tag}</div>
              <h3 className="feature-title">{f.title}</h3>
              <p className="feature-desc">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* ── Steps ── */}
    <section className="landing-steps">
      <div className="section-inner">
        <div className="section-label">Processus</div>
        <h2 className="section-title">Cinq étapes, un résultat fiable</h2>
        <div className="steps-list">
          {steps.map((s, i) => (
            <div className="step-item" key={i}>
              <div className="step-num">{s.num}</div>
              <div className="step-body">
                <h4 className="step-title">{s.title}</h4>
                <p className="step-desc">{s.desc}</p>
              </div>
              {i < steps.length - 1 && <div className="step-connector"/>}
            </div>
          ))}
        </div>
        <div className="steps-cta">
          <button className="btn btn-primary btn-lg" onClick={onStart}>
            Démarrer maintenant
          </button>
        </div>
      </div>
    </section>

    {/* ── Footer ── */}
    <footer className="landing-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <svg className="brand-icon brand-icon-sm" viewBox="0 0 60 56" fill="none">
            <polygon points="30,4  58,20  30,36  2,20"  fill="#ffffff"/>
            <polygon points="30,18 54,31  30,44  6,31"  fill="#ffffff" opacity="0.65"/>
            <polygon points="30,30 50,41  30,52 10,41"  fill="#ffffff" opacity="0.35"/>
          </svg>
          <span>Admission Ranking</span>
        </div>
        <p className="footer-copy">
          Hybrid Multi-Criteria Decision Making System : AHP · TOPSIS · Machine Learning
        </p>
      </div>
    </footer>
  </div>
  );
};

export default LandingPage;
