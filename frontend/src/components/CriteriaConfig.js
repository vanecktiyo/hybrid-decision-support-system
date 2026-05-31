import React, { useState, useEffect } from 'react';
import './CriteriaConfig.css';
import { apiService } from '../services/api';

const CriteriaConfig = ({ filename, fileInfo, missingStrategy = 'mean', onConfigReady, onError, onBack }) => {
  const [numericCriteria, setNumericCriteria] = useState([]);
  const [categoricalCriteria, setCategoricalCriteria] = useState([]);
  const [idColumn, setIdColumn] = useState('ID');
  const [loading, setLoading] = useState(true);

  // numeric selections (all criteria are benefit: higher = better)
  const [selectedNumeric, setSelectedNumeric] = useState([]);

  // categorical selections + ordinal mappings
  const [selectedCategorical, setSelectedCategorical] = useState([]);
  const [ordinalMappings, setOrdinalMappings] = useState({});

  // global settings
  const [targetColumn, setTargetColumn] = useState('');
  const [potentialTargets, setPotentialTargets] = useState([]);
  const [targetMapping, setTargetMapping] = useState({});

  useEffect(() => {
    if (!targetColumn) { setTargetMapping({}); return; }
    setSelectedNumeric(prev => prev.filter(n => n !== targetColumn));
    setSelectedCategorical(prev => prev.filter(n => n !== targetColumn));
    const target = potentialTargets.find(t => t.name === targetColumn);
    if (target) {
      // Known tier labels with semantic order (0 = worst, highest = best)
      const KNOWN_ORDER = {
        'faible': 0, 'moyen': 1, 'bon': 2, 'excellent': 3,
        'refusé': 0, 'refuse': 0, 'admis': 1, 'admitted': 1,
        'non': 0, 'no': 0, 'oui': 1, 'yes': 1,
        'low': 0, 'medium': 1, 'high': 2,
      };
      const autoMap = {};
      const vals = target.unique_values;
      const allKnown = vals.every(v => v.toLowerCase() in KNOWN_ORDER);
      if (allKnown) {
        vals.forEach(v => { autoMap[v] = String(KNOWN_ORDER[v.toLowerCase()]); });
      } else {
        vals.forEach((v, i) => { autoMap[v] = String(i); });
      }
      setTargetMapping(autoMap);
    }
  }, [targetColumn]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadCriteriaSuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filename]);

  const loadCriteriaSuggestions = async () => {
    try {
      setLoading(true);
      const data = await apiService.getCriteriaSuggestions(filename);

      setNumericCriteria(data.suggested_criteria || []);
      setCategoricalCriteria(data.categorical_columns || []);
      setIdColumn(data.id_column);
      setPotentialTargets(data.potential_target_columns || []);

      setSelectedNumeric((data.suggested_criteria || []).map(c => c.name));

      // Default ordinal mapping: auto-assign 1..n alphabetically
      const mappings = {};
      (data.categorical_columns || []).forEach(c => {
        const m = {};
        c.unique_values.forEach((v, i) => { m[v] = String(i + 1); });
        mappings[c.name] = m;
      });
      setOrdinalMappings(mappings);

    } catch (error) {
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleNumeric = (name) => {
    setSelectedNumeric(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  const handleToggleCategorical = (name) => {
    setSelectedCategorical(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  const handleOrdinalChange = (colName, value, score) => {
    setOrdinalMappings(prev => ({
      ...prev,
      [colName]: { ...prev[colName], [value]: score }
    }));
  };

  const totalSelected = selectedNumeric.length + selectedCategorical.length;

  const handleProcessData = () => {
    if (totalSelected < 2) {
      onError('Sélectionnez au moins 2 critères');
      return;
    }

    // Validate ordinal mappings
    for (const colName of selectedCategorical) {
      const mapping = ordinalMappings[colName] || {};
      const cat = categoricalCriteria.find(c => c.name === colName);
      if (!cat) continue;
      for (const val of cat.unique_values) {
        const score = parseFloat(mapping[val]);
        if (isNaN(score)) {
          onError(`Valeur manquante dans le mapping de "${colName}" pour "${val}"`);
          return;
        }
      }
    }

    // All criteria are benefit (higher = better); type kept for backend compatibility.
    const numericSelected = numericCriteria
      .filter(c => selectedNumeric.includes(c.name))
      .map(c => ({ ...c, type: 'benefit' }));

    const categoricalSelected = categoricalCriteria
      .filter(c => selectedCategorical.includes(c.name))
      .map(c => ({
        ...c,
        type: 'benefit',
        encoding: Object.fromEntries(
          Object.entries(ordinalMappings[c.name] || {}).map(([k, v]) => [k, parseFloat(v)])
        ),
      }));

    // Validate target mapping if ML target selected
    if (targetColumn) {
      const targetInfo = potentialTargets.find(t => t.name === targetColumn);
      if (targetInfo) {
        for (const val of targetInfo.unique_values) {
          const v = parseInt(targetMapping[val]);
          if (isNaN(v)) {
            onError(`Mapping incomplet pour la colonne cible "${targetColumn}" : valeur manquante pour "${val}"`);
            return;
          }
        }
        const mappedValues = Object.values(targetMapping).map(v => parseInt(v));
        if (new Set(mappedValues).size !== mappedValues.length) {
          onError(`Mapping invalide : deux classes ne peuvent pas avoir le même rang dans "${targetColumn}"`);
          return;
        }
      }
    }

    const config = {
      data_source: { file_path: `data/raw/${filename}`, id_column: idColumn },
      criteria: [...numericSelected, ...categoricalSelected],
      missing_strategy: missingStrategy,
      ahp: { enabled: true },
      topsis: { enabled: true },
      machine_learning: {
        enabled: true,
        target_column: targetColumn || null,
        target_mapping: targetColumn
          ? Object.fromEntries(Object.entries(targetMapping).map(([k, v]) => [k, parseInt(v) || 0]))
          : {},
      },
      hybrid: { topsis_weight: 0.6, ml_weight: 0.4 },
    };

    onConfigReady(config);
  };

  if (loading) {
    return <div className="criteria-config loading">Chargement des suggestions...</div>;
  }

  return (
    <div className="criteria-config">
      <h3>Configurer les critères de classement</h3>

      {/* ID Column */}
      <div className="config-section">
        <label>Colonne identifiant (ID) :</label>
        <select value={idColumn} onChange={e => setIdColumn(e.target.value)} className="select">
          {fileInfo?.column_names?.map(col => (
            <option key={col} value={col}>{col}</option>
          ))}
        </select>
      </div>

      {/* Numeric criteria */}
      <div className="criteria-list">
        <h4>Critères numériques ({selectedNumeric.length} sélectionnés)</h4>
        <p className="criteria-hint">
          Tous les critères sont évalués en <strong>bénéfice</strong> : une valeur plus haute = meilleur candidat.
        </p>

        {numericCriteria.length === 0 && (
          <p className="no-cols-msg">Aucune colonne numérique détectée.</p>
        )}

        {numericCriteria.map((crit, idx) => {
          const isTarget = crit.name === targetColumn;
          const selected = selectedNumeric.includes(crit.name);
          return (
            <div key={crit.name} className={`criteria-item ${!selected || isTarget ? 'criteria-disabled' : ''}`}>
              <div className="criteria-checkbox">
                <input type="checkbox" checked={selected && !isTarget} onChange={() => !isTarget && handleToggleNumeric(crit.name)} disabled={isTarget} id={`num-${idx}`} />
                <label htmlFor={`num-${idx}`}>
                  {crit.display_name || crit.name}
                  <span className="criteria-range"> ({crit.range?.[0]?.toFixed(1)} – {crit.range?.[1]?.toFixed(1)})</span>
                  {crit.missing > 0 && <span className="missing-badge"> ⚠ {crit.missing} manquants</span>}
                  {isTarget && <span className="target-badge"> Cible ML</span>}
                </label>
              </div>
            </div>
          );
        })}
      </div>

      {/* Categorical criteria */}
      {categoricalCriteria.length > 0 && (
        <div className="criteria-list">
          <h4>Critères catégoriels ({selectedCategorical.length} sélectionnés)</h4>
          <p className="criteria-hint">
            Attribuez un score numérique à chaque valeur pour définir l'ordre d'importance.
          </p>

          {categoricalCriteria.map((crit, idx) => {
            const isTarget = crit.name === targetColumn;
            const selected = selectedCategorical.includes(crit.name);
            const mapping = ordinalMappings[crit.name] || {};
            return (
              <div key={crit.name} className={`criteria-item ${!selected || isTarget ? 'criteria-disabled' : ''}`}>
                <div className="criteria-checkbox">
                  <input type="checkbox" checked={selected && !isTarget} onChange={() => !isTarget && handleToggleCategorical(crit.name)} disabled={isTarget} id={`cat-${idx}`} />
                  <label htmlFor={`cat-${idx}`}>
                    {crit.display_name || crit.name}
                    <span className="criteria-range"> ({crit.unique_values.length} valeurs)</span>
                    {crit.missing > 0 && <span className="missing-badge"> ⚠ {crit.missing} manquants</span>}
                    {isTarget && <span className="target-badge"> Cible ML</span>}
                  </label>
                </div>

                {selected && (
                  <>
                    <div className="ordinal-mapping">
                      <span className="ordinal-label">Score par valeur (1 = le moins bon) :</span>
                      <div className="ordinal-grid">
                        {crit.unique_values.map(val => (
                          <div key={val} className="ordinal-item">
                            <span className="ordinal-value-name">{val}</span>
                            <span className="ordinal-equals">=</span>
                            <input
                              type="number"
                              min="1"
                              step="1"
                              className="ordinal-input"
                              value={mapping[val] ?? ''}
                              onChange={e => handleOrdinalChange(crit.name, val, e.target.value)}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ML target column */}
      {potentialTargets.length > 0 && (
        <div className="config-section">
          <label>Colonne cible ML (optionnel) :</label>
          <p className="ml-hint">
            Sélectionnez une colonne contenant des étiquettes catégorielles historiques
            (ex : Faible / Moyen / Bon / Excellent, Admis / Refusé).
            Le modèle ML s'entraîne sur ces décisions passées pour améliorer le classement.
          </p>
          <select value={targetColumn} onChange={e => setTargetColumn(e.target.value)} className="select">
            <option value="">— Aucune (TOPSIS + AHP uniquement) —</option>
            {potentialTargets.map(t => <option key={t.name} value={t.name}>{t.name}</option>)}
          </select>

          {targetColumn && potentialTargets.find(t => t.name === targetColumn) && (
            <div className="ordinal-mapping" style={{ marginTop: 12 }}>
              <span className="ordinal-label">
                Définissez l'ordre des classes (0 = le moins bon, valeur max = le meilleur) :
              </span>
              <div className="ordinal-grid">
                {potentialTargets.find(t => t.name === targetColumn).unique_values.map(val => (
                  <div key={val} className="ordinal-item">
                    <span className="ordinal-value-name">{val}</span>
                    <span className="ordinal-equals">=</span>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      className="ordinal-input"
                      value={targetMapping[val] ?? ''}
                      onChange={e => setTargetMapping(prev => ({ ...prev, [val]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        {onBack && (
          <button className="btn btn-secondary" onClick={onBack}>
            ← Retour
          </button>
        )}
        <button
          className="btn btn-primary btn-large"
          onClick={handleProcessData}
          disabled={totalSelected < 2}
        >
          Continuer vers la matrice AHP →
        </button>
      </div>
    </div>
  );
};

export default CriteriaConfig;
