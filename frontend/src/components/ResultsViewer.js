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
const ShapBar = ({ item }) => {
  const maxAbs = 0.3; // visual clamp
  const pct = Math.min(Math.abs(item.shap_value) / maxAbs, 1) * 100;
  const color = item.direction === 'positive' ? '#28a745' : '#dc3545';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
      <span style={{ width: 110, fontSize: 11, color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {item.feature}
      </span>
      <div style={{ flex: 1, background: '#e9ecef', borderRadius: 3, height: 10, minWidth: 80 }}>
        <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 3 }} />
      </div>
      <span style={{ width: 52, fontSize: 11, color, textAlign: 'right', fontWeight: 600 }}>
        {item.shap_value > 0 ? '+' : ''}{item.shap_value.toFixed(3)}
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

  const { statistics, ahp, topsis, machine_learning: ml, hybrid } = results;

  let topResults = results.top_10;
  if (!topResults) {
    const topKey = Object.keys(results).find(key => /^top_\d+$/.test(key));
    topResults = topKey ? results[topKey] : [];
  }

  if (!statistics) return <div className="error-message">No statistics data available</div>;

  const mlEnabled = ml?.enabled === true;
  const hasFeatureImportance = mlEnabled && ml.feature_importance && Object.keys(ml.feature_importance).length > 0;
  const hasModelResults = mlEnabled && ml.model_results && Object.keys(ml.model_results).length > 0;
  const hasShap = mlEnabled && topResults?.some(r => r.shap_explanation?.length > 0);

  const SCORE_COLS = new Set([
    'TOPSIS_Score', 'TOPSIS_Rank', 'ML_Score', 'Final_Score', 'Final_Rank',
    'Predicted_Tier', 'shap_explanation',
  ]);
  const firstRow = topResults?.length > 0 ? topResults[0] : null;
  const idKey = results.id_column
    || (firstRow ? Object.keys(firstRow).find(k => !SCORE_COLS.has(k)) : 'ID');

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

      {/* ── Statistics ── */}
      <div className="statistics-grid">
        <div className="stat-card">
          <h4>Candidats</h4>
          <p className="stat-value">{statistics.total_candidates ?? 'N/A'}</p>
        </div>
        <div className="stat-card">
          <h4>Score max</h4>
          <p className="stat-value">{statistics.top_score != null ? statistics.top_score.toFixed(4) : 'N/A'}</p>
        </div>
        <div className="stat-card">
          <h4>Score moyen</h4>
          <p className="stat-value">{statistics.avg_score != null ? statistics.avg_score.toFixed(4) : 'N/A'}</p>
        </div>
        <div className="stat-card">
          <h4>Écart-type</h4>
          <p className="stat-value">{statistics.std_dev != null ? statistics.std_dev.toFixed(4) : 'N/A'}</p>
        </div>
      </div>

      {hasShap && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ fontSize: 12, color: '#888' }}>
            Cliquez sur ▶ pour voir la justification SHAP
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
                {mlEnabled && <th>P(Excellent)</th>}
                {mlEnabled && <th>Tier prédit</th>}
                <th>Score final</th>
                {hasShap && <th>Justification</th>}
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
                        <td><TierBadge tier={row.Predicted_Tier} /></td>
                      )}
                      <td className="final-score">
                        <span className="score-badge">
                          {row.Final_Score != null ? Number(row.Final_Score).toFixed(4) : 'N/A'}
                        </span>
                      </td>
                      {hasShap && (
                        <td>
                          {row.shap_explanation?.length > 0 && (
                            <button
                              className="btn-shap-toggle"
                              onClick={() => setExpandedShap(expandedShap === index ? null : index)}
                              title="Voir la justification SHAP"
                            >
                              {expandedShap === index ? '▼' : '▶'}
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                    {hasShap && expandedShap === index && row.shap_explanation?.length > 0 && (
                      <tr className="shap-row">
                        <td colSpan={mlEnabled ? 7 : 5} style={{ padding: '8px 16px', background: '#f8f9fa' }}>
                          <div style={{ fontSize: 12, color: '#555', marginBottom: 6, fontWeight: 600 }}>
                            Facteurs influençant le tier Excellent (SHAP) :
                          </div>
                          {row.shap_explanation.map((item, i) => (
                            <ShapBar key={i} item={item} />
                          ))}
                          <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                            vert = facteur favorisant Excellent · rouge = facteur défavorisant
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              ) : (
                <tr>
                  <td colSpan={mlEnabled ? 7 : 4} className="no-data">Aucun résultat disponible</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── ML Model Comparison ── */}
      {hasModelResults && (
        <div className="ml-section">
          <h3>Comparaison des modèles ML</h3>
          <p className="ml-subtitle">
            Meilleur modèle : <strong>{ml.best_model_display}</strong>
            &nbsp;(F1-macro = {ml.best_f1_macro?.toFixed(4)})
            &nbsp;· entraîné sur {ml.n_samples} échantillons, {ml.n_features} critères
            {ml.class_distribution && (
              <> · Distribution : {Object.entries(ml.class_distribution).map(([k, v]) => `${k}:${v}`).join(', ')}</>
            )}
          </p>
          <div className="table-container">
            <table className="results-table">
              <thead>
                <tr>
                  <th>Modèle</th>
                  <th>F1-macro (CV)</th>
                  <th>Précision (CV)</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ml.model_results).map(([key, m]) => (
                  <tr key={key} className={key === ml.best_model ? 'best-model-row' : ''}>
                    <td>
                      {m.display_name}
                      {key === ml.best_model && <span className="best-badge"> ★ Meilleur</span>}
                    </td>
                    <td>{m.f1_macro != null ? m.f1_macro.toFixed(4) : '—'}</td>
                    <td>{m.accuracy != null ? m.accuracy.toFixed(4) : '—'}</td>
                    <td className={m.status === 'success' ? 'status-ok' : 'status-fail'}>
                      {m.status === 'success' ? `✓ (${m.cv_folds}-fold CV)` : `✗ ${m.error || ''}`}
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
