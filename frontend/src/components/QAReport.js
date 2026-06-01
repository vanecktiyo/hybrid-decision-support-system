import React, { useState } from 'react';
import './QAReport.css';

const QAReport = ({ report, filename, onConfirm, onGoBack }) => {
  const [agreed, setAgreed] = useState(false);
  const [expandedOutlier, setExpandedOutlier] = useState(null);
  const [missingStrategy, setMissingStrategy] = useState('zero');

  const toggleOutlier = (col) => setExpandedOutlier(prev => prev === col ? null : col);

  if (!report) return null;

  const criticalIssues = report.critical_issues || [];
  const hasBlockingIssues = criticalIssues.length > 0;
  const qualityScore = parseFloat(report.quality_score) || 0;
  const recommendation = report.recommendation || { level: 'warning', message: 'Vérifiez les données avant de continuer.' };

  const scoreColor = qualityScore >= 80 ? 'var(--success)' : qualityScore >= 60 ? 'var(--warning)' : 'var(--error)';
  const recClass   = recommendation?.level === 'good' ? 'recommendation-good'
                   : recommendation?.level === 'warning' ? 'recommendation-warning'
                   : recommendation?.level === 'error' ? 'recommendation-error'
                   : 'recommendation-warning';

  return (
    <div className="qa-report">
      <div className="report-header">
        <h2>Rapport qualité des données</h2>
        <p className="filename">Fichier : {filename}</p>
      </div>

      {/* Problèmes bloquants */}
      {hasBlockingIssues && (
        <div className="critical-issues-box">
          <div className="critical-issues-title">
            <span className="critical-icon">⛔</span>
            Fichier non conforme : impossible de continuer
          </div>
          <ul className="critical-issues-list">
            {criticalIssues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
          <p className="critical-issues-hint">
            Corrigez le fichier et importez-le à nouveau.
          </p>
        </div>
      )}

      {/* Score */}
      <div className="quality-card">
        <div className="score-circle">
          <svg width="96" height="96" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" strokeWidth="8"/>
            <circle cx="60" cy="60" r="52" fill="none" stroke={scoreColor} strokeWidth="8"
              strokeDasharray={`${(qualityScore / 100) * 326.7} 326.7`}
              strokeLinecap="round"
              style={{ transform: 'rotate(-90deg)', transformOrigin: '60px 60px' }}
            />
            <text x="60" y="68" textAnchor="middle" fontSize="26" fontWeight="700" fill={scoreColor}>
              {qualityScore.toFixed(1)}%
            </text>
          </svg>
        </div>
        <div className="score-text">
          <h3>Score de qualité global</h3>
          <p className={recClass}>{recommendation.message}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="statistics-grid">
        <div className="stat-box">
          <div className="stat-label">Total candidats</div>
          <div className="stat-value">{report.total_candidates}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Critères numériques</div>
          <div className="stat-value">{report.total_criteria_detected}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Critères catégoriels</div>
          <div className="stat-value">{report.text_converted.length}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Critères avec anomalies</div>
          <div className="stat-value">{Object.keys(report.outliers_detected).length}</div>
        </div>
      </div>

      {/* Critères */}
      <div className="criteria-section">
        <h3>Critères détectés ({report.criteria_names.length})</h3>
        <div className="criteria-list">
          {report.criteria_names.map((c, i) => <span key={i} className="criterion-tag">{c}</span>)}
        </div>
      </div>

      {/* Conversions texte */}
      {report.text_converted.length > 0 && (
        <div className="conversions-section">
          <h3>Colonnes à convertir en numérique ({report.text_converted.length})</h3>
          <div className="conversions-list">
            {report.text_converted.map((col, i) => (
              <div key={i} className="conversion-item">
                <span className="conversion-label">+</span>
                <span>{col}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manquants */}
      {Object.keys(report.missing_data_summary).length > 0 && (
        <div className="missing-section">
          <h3>Critères avec données manquantes ({Object.keys(report.missing_data_summary).length})</h3>
          <div className="missing-list">
            {Object.entries(report.missing_data_summary).map(([col, stats], i) => (
              <div key={i} className="missing-item">
                <span className="missing-label">{col}</span>
                <span className="missing-stats">{stats.count} manquants ({stats.percentage.toFixed(1)}%)</span>
              </div>
            ))}
          </div>
          <div className="missing-strategy">
            <label className="missing-strategy-label">
              Stratégie de remplacement :
            </label>
            <select
              className="missing-strategy-select"
              value={missingStrategy}
              onChange={e => setMissingStrategy(e.target.value)}
            >
              <option value="mean">Remplacer par la moyenne</option>
              <option value="median">Remplacer par la médiane</option>
              <option value="zero">Remplacer par 0</option>
            </select>
          </div>
        </div>
      )}

      {/* Outliers */}
      {Object.keys(report.outliers_detected).length > 0 && (
        <div className="outliers-section">
          <h3>Critères avec anomalies ({Object.keys(report.outliers_detected).length})</h3>
          <div className="outliers-list">
            {Object.entries(report.outliers_detected).map(([col, stats], i) => (
              <div key={i} className="outlier-item">
                <div className="outlier-summary">
                  <span className="outlier-label">{col}</span>
                  <span className="outlier-stats">
                    {stats.count} valeur(s) (bornes : {stats.lower_bound.toFixed(2)} à {stats.upper_bound.toFixed(2)})
                  </span>
                  {stats.candidates?.length > 0 && (
                    <button
                      className="btn-outlier-toggle"
                      onClick={() => toggleOutlier(col)}
                      title="Voir les candidats concernés"
                    >
                      {expandedOutlier === col ? '▲ Masquer' : '▶ Voir les candidats'}
                    </button>
                  )}
                </div>
                {expandedOutlier === col && stats.candidates?.length > 0 && (
                  <div className="outlier-candidates">
                    <table className="outlier-candidates-table">
                      <thead>
                        <tr>
                          <th>ID candidat</th>
                          <th>Valeur</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stats.candidates.map((c, ci) => (
                          <tr key={ci}>
                            <td>{c.id}</td>
                            <td className="outlier-candidate-value">{c.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="outlier-note">Vérifiez ces valeurs avant de continuer. Elles seront incluses dans l'analyse telles quelles.</p>
        </div>
      )}

      {/* Avertissements */}
      {report.warnings.length > 0 && (
        <div className="warnings-section">
          <h3>Avertissements ({report.warnings.length})</h3>
          <ul className="warnings-list">
            {report.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* Erreurs */}
      {report.errors.length > 0 && (
        <div className="errors-section">
          <h3>Erreurs ({report.errors.length})</h3>
          <ul className="errors-list">
            {report.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      {/* Recommandation */}
      <div className={`recommendation-box ${recClass}`}>
        <h3>Recommandation</h3>
        <p>{recommendation.message}</p>
      </div>

      {/* Actions */}
      <div className="qa-actions">
        <div>
          <button className="btn btn-secondary" onClick={onGoBack}>Changer de fichier</button>
        </div>
        {!hasBlockingIssues && (
          <div className="agreement">
            <label className="checkbox-label">
              <input type="checkbox" checked={agreed} onChange={e => setAgreed(e.target.checked)}/>
              J'ai lu le rapport et je souhaite continuer
            </label>
          </div>
        )}
        <button className="btn btn-primary" onClick={() => onConfirm(missingStrategy)} disabled={hasBlockingIssues || !agreed}>
          Continuer vers la configuration
        </button>
      </div>
    </div>
  );
};

export default QAReport;
