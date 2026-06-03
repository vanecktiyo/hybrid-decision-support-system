import React, { useState } from 'react';
import './ResultsViewer.css';
import { apiService, downloadBlob } from '../services/api';

// ── Tier helpers ─────────────────────────────────────────────────────────────
const TIER_COLORS = {
  Excellent: { bg: '#d4edda', color: '#155724', border: '#c3e6cb' },
  Bon:       { bg: '#cce5ff', color: '#004085', border: '#b8daff' },
  Moyen:     { bg: '#fff3cd', color: '#856404', border: '#ffeeba' },
  Faible:    { bg: '#f8d7da', color: '#721c24', border: '#f5c6cb' },
};

const TierBadge = ({ tier }) => {
  if (!tier) return null;
  const style = TIER_COLORS[tier] || { bg: '#e9ecef', color: '#495057', border: '#dee2e6' };
  return (
    <span style={{
      background: style.bg, color: style.color, border: `1px solid ${style.border}`,
      borderRadius: 4, padding: '2px 8px', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {tier}
    </span>
  );
};

// ── SHAP explanation bar ──────────────────────────────────────────────────────
const ShapBar = ({ item, maxAbs }) => {
  const clamp = Math.max(maxAbs, 1e-9);
  const pct = Math.min(Math.abs(item.shap_value) / clamp, 1) * 100;
  const color = item.direction === 'positive' ? '#28a745' : '#dc3545';
  const decimals = Math.abs(item.shap_value) < 0.001 ? 5 : 3;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
      <span style={{ width: 110, fontSize: 11, color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {item.feature}
      </span>
      <div style={{ flex: 1, background: '#e9ecef', borderRadius: 3, height: 10, minWidth: 80 }}>
        <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 3 }} />
      </div>
      <span style={{ width: 64, fontSize: 11, color, textAlign: 'right', fontWeight: 600 }}>
        {item.shap_value > 0 ? '+' : ''}{item.shap_value.toFixed(decimals)}
      </span>
    </div>
  );
};

// ── Component ─────────────────────────────────────────────────────────────────
const ResultsViewer = ({ results, criteria = [], onError = () => {}, onValidate, onBack }) => {
  const [expandedShap, setExpandedShap] = useState(null);

  const handleDownloadCSV = async () => {
    try {
      if (!results?.result_id) throw new Error('Result ID not available');
      const blob = await apiService.downloadResultsCSV(results.result_id);
      downloadBlob(blob, `ranking_results_${results.result_id}.csv`);
    } catch (error) { onError(error.message); }
  };

  const handleDownloadExcel = async () => {
    try {
      if (!results?.result_id) throw new Error('Result ID not available');
      const blob = await apiService.downloadResultsExcel(results.result_id);
      downloadBlob(blob, `ranking_results_${results.result_id}.xlsx`);
    } catch (error) { onError(error.message); }
  };

  if (!results) return null;

  const { statistics, machine_learning: ml, hybrid } = results;

  let topResults = results.top_10;
  if (!topResults) {
    const topKey = Object.keys(results).find(key => /^top_\d+$/.test(key));
    topResults = topKey ? results[topKey] : [];
  }

  if (!statistics) return <div className="error-message">No statistics data available</div>;

  const mlEnabled = ml?.enabled === true;
  const hasModelResults = mlEnabled && ml.model_results && Object.keys(ml.model_results).length > 0;
  const hasShap = mlEnabled && topResults?.some(r => r.shap_explanation?.length > 0);
  const hasTopsis = topResults?.some(r => r.topsis_explanation?.length > 0);
  const hasJustification = hasShap || hasTopsis;

  const SCORE_COLS = new Set([
    'TOPSIS_Score', 'TOPSIS_Rank', 'ML_Score', 'Final_Score', 'Final_Rank',
    'Predicted_Tier', 'Classe_predite', 'shap_explanation', 'topsis_explanation',
  ]);
  const firstRow = topResults?.length > 0 ? topResults[0] : null;
  const idKey = results.id_column
    || (firstRow ? Object.keys(firstRow).find(k => !SCORE_COLS.has(k)) : 'ID');

  const colCount = 4 + (mlEnabled ? 2 : 0) + (hasJustification ? 1 : 0);

  return (
    <div className="results-viewer">
      {/* ── Header ── */}
      <div className="results-header">
        <h2>Résultats du Classement</h2>
        <div className="download-buttons">
          {onBack && (
            <button className="btn btn-secondary" onClick={onBack}>
              ← Retour
            </button>
          )}
          <button className="btn btn-primary" onClick={handleDownloadCSV}>
            Télécharger CSV
          </button>
          <button className="btn btn-primary" onClick={handleDownloadExcel}>
            Télécharger Excel
          </button>
          {onValidate && (
            <button className="btn btn-success" onClick={onValidate} style={{ marginLeft: 8 }}>
              ✓ Soumettre la validation
            </button>
          )}
        </div>
      </div>


      {hasJustification && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ fontSize: 12, color: '#888' }}>
            Cliquez sur ▶ pour voir la justification du classement (TOPSIS + ML)
          </span>
        </div>
      )}

      {/* ── Ranking Table ── */}
      <div className="top-results-section">
        <div className="section-title-row">
          <h3>Classement des candidats</h3>
          {hybrid && (
            <span className="hybrid-badge">
              {mlEnabled
                ? `Hybride : ${(hybrid.topsis_weight * 100).toFixed(0)}% TOPSIS + ${(hybrid.ml_weight * 100).toFixed(0)}% ${ml.best_model_display}`
                : 'TOPSIS pur (pas de colonne cible ML)'}
            </span>
          )}
        </div>
        <div className="table-container">
          <table className="results-table">
            <thead>
              <tr>
                <th>Rang</th>
                <th>ID</th>
                <th>Score TOPSIS</th>
                {mlEnabled && <th>Score ML</th>}
                {mlEnabled && <th>Classe prédite</th>}
                <th>Score final</th>
                {hasJustification && <th>Justification</th>}
              </tr>
            </thead>
            <tbody>
              {topResults && topResults.length > 0 ? (
                topResults.map((row, index) => (
                  <React.Fragment key={index}>
                    <tr>
                      <td className="rank">{row.Final_Rank ?? index + 1}</td>
                      <td>{row[idKey] ?? 'N/A'}</td>
                      <td>{row.TOPSIS_Score != null ? Number(row.TOPSIS_Score).toFixed(4) : 'N/A'}</td>
                      {mlEnabled && (
                        <td>{row.ML_Score != null ? Number(row.ML_Score).toFixed(4) : '—'}</td>
                      )}
                      {mlEnabled && (
                        <td><TierBadge tier={row.Classe_predite} /></td>
                      )}
                      <td className="final-score">
                        <span className="score-badge">
                          {row.Final_Score != null ? Number(row.Final_Score).toFixed(4) : 'N/A'}
                        </span>
                      </td>
                      {hasJustification && (
                        <td>
                          {(row.shap_explanation?.length > 0 || row.topsis_explanation?.length > 0) && (
                            <button
                              className="btn-shap-toggle"
                              onClick={() => setExpandedShap(expandedShap === index ? null : index)}
                              title="Voir la justification du classement"
                            >
                              {expandedShap === index ? '▼' : '▶'}
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                    {hasJustification && expandedShap === index && (
                      <tr className="shap-row">
                        <td colSpan={colCount} style={{ padding: '10px 16px', background: '#f8f9fa' }}>
                          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>

                            {/* TOPSIS contributions */}
                            {row.topsis_explanation?.length > 0 && (
                              <div style={{ flex: 1, minWidth: 220 }}>
                                <div style={{ fontSize: 12, color: '#1b3a6b', marginBottom: 6, fontWeight: 700 }}>
                                  Contribution TOPSIS par critère
                                </div>
                                {(() => {
                                  const maxAbs = Math.max(...row.topsis_explanation.map(t => Math.abs(t.contribution)), 1e-9);
                                  return row.topsis_explanation.map((item, i) => {
                                    const pct = Math.min(Math.abs(item.contribution) / maxAbs, 1) * 100;
                                    const color = item.direction === 'positive' ? '#28a745' : '#dc3545';
                                    return (
                                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                                        <span style={{ width: 110, fontSize: 11, color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                          {item.feature}
                                        </span>
                                        <span style={{ fontSize: 10, color: '#999', width: 32 }}>
                                          {(item.weight * 100).toFixed(0)}%
                                        </span>
                                        <div style={{ flex: 1, background: '#e9ecef', borderRadius: 3, height: 10, minWidth: 60 }}>
                                          <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 3 }} />
                                        </div>
                                        <span style={{ width: 64, fontSize: 11, color, textAlign: 'right', fontWeight: 600 }}>
                                          {item.contribution > 0 ? '+' : ''}{item.contribution.toFixed(3)}
                                        </span>
                                      </div>
                                    );
                                  });
                                })()}
                              </div>
                            )}

                            {/* SHAP contributions */}
                            {row.shap_explanation?.length > 0 && (
                              <div style={{ flex: 1, minWidth: 220 }}>
                                <div style={{ fontSize: 12, color: '#7c3aed', marginBottom: 6, fontWeight: 700 }}>
                                  Contribution ML (SHAP)
                                </div>
                                {(() => {
                                  const maxAbs = Math.max(...row.shap_explanation.map(s => Math.abs(s.shap_value)), 1e-9);
                                  return row.shap_explanation.map((item, i) => (
                                    <ShapBar key={i} item={item} maxAbs={maxAbs} />
                                  ));
                                })()}
                              </div>
                            )}

                          </div>
                          <div style={{ fontSize: 11, color: '#999', marginTop: 6 }}>
                            vert = facteur favorisant · rouge = facteur défavorisant
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              ) : (
                <tr>
                  <td colSpan={colCount} className="no-data">Aucun résultat disponible</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── ML Model ── */}
      {hasModelResults && (
        <div className="ml-section">
          <h3>Modèle d'apprentissage</h3>
          <p className="ml-subtitle">
            Modèle utilisé : <strong>{ml.best_model_display}</strong>
            &nbsp;· entraîné sur {ml.n_samples} échantillons, {ml.n_features} critères
            {ml.class_distribution && (
              <> · Distribution : {Object.entries(ml.class_distribution).map(([k, v]) => `${k}:${v}`).join(', ')}</>
            )}
          </p>

          {/* ── Honest performance on the held-out test set (rows never seen in training) ── */}
          {ml.holdout_metrics ? (
            <div className="holdout-box">
              <div className="holdout-title">
                Performance sur les données de test
                <span className="holdout-badge">
                  {ml.holdout_metrics.n_test} candidats jamais vus à l'entraînement
                </span>
              </div>
              <p className="holdout-hint">
                Ces scores mesurent la capacité réelle du modèle à généraliser : ils sont calculés
                sur un échantillon mis de côté avant l'entraînement (jamais utilisé pour apprendre).
              </p>
              <div className="holdout-metrics">
                <div className="holdout-metric">
                  <span className="holdout-metric-value">{(ml.holdout_metrics.accuracy * 100).toFixed(1)}%</span>
                  <span className="holdout-metric-label">Exactitude (accuracy)</span>
                </div>
                <div className="holdout-metric">
                  <span className="holdout-metric-value">{ml.holdout_metrics.f1_macro?.toFixed(4)}</span>
                  <span className="holdout-metric-label">F1-macro (test)</span>
                </div>
                {ml.holdout_metrics.roc_auc != null && (
                  <div className="holdout-metric">
                    <span className="holdout-metric-value">{ml.holdout_metrics.roc_auc?.toFixed(4)}</span>
                    <span className="holdout-metric-label">ROC-AUC (test)</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <p className="holdout-hint" style={{ fontStyle: 'italic' }}>
              Pas d'évaluation sur données de test (échantillon insuffisant pour mettre des candidats de côté).
              Les scores ci-dessous sont issus de la validation croisée uniquement.
            </p>
          )}
          <p className="ml-cv-note">
            Les scores ci-dessous sont obtenus par <strong>validation croisée</strong> sur les
            données d'entraînement, à ne pas confondre avec la performance sur les données de
            test affichée plus haut.
          </p>
          <div className="table-container">
            <table className="results-table">
              <thead>
                <tr>
                  <th>Modèle</th>
                  <th>{ml.metric_label || 'F1-macro'} (CV)</th>
                  <th>Précision (CV)</th>
                  <th>Validation</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ml.model_results).map(([key, m]) => (
                  <tr key={key}>
                    <td>{m.display_name}</td>
                    <td>{m.f1_macro != null ? m.f1_macro.toFixed(4) : '—'}</td>
                    <td>{m.accuracy != null ? m.accuracy.toFixed(4) : '—'}</td>
                    <td className={m.status === 'success' ? 'status-ok' : 'status-fail'}>
                      {m.status === 'success' ? `✓ ${m.metric || ''} (${m.cv_folds}-fold CV)` : `✗ ${m.error || ''}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
};

export default ResultsViewer;
