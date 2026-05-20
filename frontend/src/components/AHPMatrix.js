import React, { useState, useEffect } from 'react';
import './AHPMatrix.css';
import { apiService } from '../services/api';

// Saaty scale options: 9 (extreme preference) down to 1/9
const SAATY_OPTIONS = [
  { label: '9',   value: 9 },
  { label: '8',   value: 8 },
  { label: '7',   value: 7 },
  { label: '6',   value: 6 },
  { label: '5',   value: 5 },
  { label: '4',   value: 4 },
  { label: '3',   value: 3 },
  { label: '2',   value: 2 },
  { label: '1',   value: 1 },
  { label: '1/2', value: 1/2 },
  { label: '1/3', value: 1/3 },
  { label: '1/4', value: 1/4 },
  { label: '1/5', value: 1/5 },
  { label: '1/6', value: 1/6 },
  { label: '1/7', value: 1/7 },
  { label: '1/8', value: 1/8 },
  { label: '1/9', value: 1/9 },
];

// Convert a float to the nearest Saaty fraction label
const toFractionLabel = (value) => {
  if (value >= 1) {
    const rounded = Math.round(value);
    return String(rounded);
  }
  const denom = Math.round(1 / value);
  return `1/${denom}`;
};

// Find the closest Saaty option value for a given float
const snapToSaaty = (value) =>
  SAATY_OPTIONS.reduce((best, opt) =>
    Math.abs(opt.value - value) < Math.abs(best.value - value) ? opt : best
  ).value;

const AHPMatrix = ({ criteria, onMatrixReady, onError, onBack }) => {
  const [matrix, setMatrix] = useState([]);
  const [weights, setWeights] = useState(null);
  const [cr, setCR] = useState(null);
  const [isValid, setIsValid] = useState(false);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    initializeMatrix();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criteria]);

  const initializeMatrix = async () => {
    try {
      setLoading(true);
      const n = criteria.length;
      const response = await apiService.getAHPMatrix(n);
      if (response && response.matrix) {
        setMatrix(response.matrix);
      } else {
        setMatrix(Array(n).fill(0).map(() => Array(n).fill(1)));
      }
    } catch (error) {
      onError('Erreur initialisation matrice : ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMatrixChange = (i, j, value) => {
    const numValue = parseFloat(value);
    if (!numValue || numValue <= 0) return;

    const newMatrix = matrix.map(row => [...row]);
    newMatrix[i][j] = numValue;
    newMatrix[j][i] = 1 / numValue;

    setMatrix(newMatrix);
    setCR(null);
    setIsValid(false);
    setWeights(null);
    setMessage('');
  };

  const calculateWeights = async () => {
    try {
      setCalculating(true);
      const payload = { matrix, criteria_count: criteria.length, criteria };
      const response = await apiService.calculateAHPWeights(payload);

      if (response.status === 'success') {
        setWeights(response.weights);
        setCR(response.cr);
        if (response.cr < 0.1) {
          setIsValid(true);
          setMessage(`✓ Matrice cohérente (CR = ${response.cr.toFixed(4)}, seuil < 0.10)`);
        } else {
          setIsValid(false);
          setMessage(`⚠ Matrice incohérente (CR = ${response.cr.toFixed(4)}, seuil > 0.10). Révisez vos comparaisons.`);
        }
      } else {
        onError(response.message || 'Erreur calcul des poids');
      }
    } catch (error) {
      onError('Erreur : ' + error.message);
    } finally {
      setCalculating(false);
    }
  };

  const handleProceed = (force = false) => {
    if (!weights) {
      onError('Calculez d\'abord les poids');
      return;
    }
    if (!isValid && !force) return;

    onMatrixReady({ comparison_matrix: matrix, weights, cr });
  };

  if (loading) {
    return <div className="ahp-matrix loading"><p>Chargement...</p></div>;
  }


  return (
    <div className="ahp-matrix">
      <h3>Matrice de comparaison par paires (AHP)</h3>
      <p className="ahp-subtitle">
        Pour chaque paire, indiquez combien de fois le critère de la <strong>ligne</strong> est
        plus important que celui de la <strong>colonne</strong>.
        Utilisez une valeur &gt; 1 si la ligne est plus importante, &lt; 1 si elle l'est moins.
      </p>

      {/* Scale reference */}
      <div className="scale-reference">
        <div className="scale-grid">
          <span><strong>1</strong> = Égal</span>
          <span><strong>3</strong> = Modéré</span>
          <span><strong>5</strong> = Fort</span>
          <span><strong>7</strong> = Très fort</span>
          <span><strong>9</strong> = Extrême</span>
          <span><strong>1/3, 1/5…</strong> = Préférence inverse</span>
        </div>
      </div>

      {/* Matrix table */}
      <div className="matrix-container">
        <table className="ahp-table">
          <tbody>
            {/* First row: column headers */}
            <tr>
              <th className="corner-cell"></th>
              {criteria.map((c, idx) => (
                <th key={idx} className="col-header">
                  {c.name}
                </th>
              ))}
            </tr>

            {/* Data rows: row header + cells */}
            {criteria.map((rowCrit, i) => (
              <tr key={i}>
                <th className="row-header">{rowCrit.name}</th>
                {criteria.map((_, j) => (
                  <td key={`${i}-${j}`} className={i === j ? 'cell-diagonal' : i > j ? 'cell-lower' : 'cell-upper'}>
                    {i === j ? (
                      <span className="diagonal-val">1</span>
                    ) : i < j ? (
                      <select
                        className="matrix-select"
                        value={snapToSaaty(matrix[i]?.[j] ?? 1)}
                        onChange={(e) => handleMatrixChange(i, j, e.target.value)}
                        disabled={calculating}
                      >
                        {SAATY_OPTIONS.map(opt => (
                          <option key={opt.label} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="reciprocal-val">
                        {toFractionLabel(matrix[i]?.[j] ?? 1)}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Message */}
      {message && (
        <div className={`ahp-message ${isValid ? 'success' : 'warning'}`}>
          {message}
        </div>
      )}

      {/* Weights */}
      {weights && (
        <div className="weights-display">
          <h5>Poids calculés :</h5>
          <div className="weights-list">
            {criteria.map((c) => (
              <div key={c.name} className="weight-item">
                <span className="weight-name">{c.name}</span>
                <div className="weight-bar">
                  <div className="weight-fill" style={{ width: `${(weights[c.name] ?? 0) * 100}%` }} />
                </div>
                <span className="weight-value">{((weights[c.name] ?? 0) * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="ahp-actions">
        <button className="btn btn-secondary" onClick={onBack} disabled={calculating}>
          ← Retour
        </button>
        <button className="btn btn-primary" onClick={calculateWeights} disabled={calculating}>
          {calculating ? 'Calcul…' : 'Calculer les poids'}
        </button>
        {isValid ? (
          <button className="btn btn-success" onClick={() => handleProceed(false)}>
            Continuer vers le classement →
          </button>
        ) : (
          weights && (
            <button className="btn btn-warning" onClick={() => handleProceed(true)}
              title={`CR = ${cr?.toFixed(4)} — continuer quand même avec ces poids`}>
              Continuer malgré l'incohérence →
            </button>
          )
        )}
      </div>
    </div>
  );
};

export default AHPMatrix;
