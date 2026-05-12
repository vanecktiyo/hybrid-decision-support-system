import React, { useState, useEffect } from 'react';
import './CriteriaConfig.css';
import { apiService } from '../services/api';

const CriteriaConfig = ({ filename, fileInfo, onConfigReady, onError }) => {
  const [numericCriteria, setNumericCriteria] = useState([]);
  const [categoricalCriteria, setCategoricalCriteria] = useState([]);
  const [idColumn, setIdColumn] = useState('ID');
  const [loading, setLoading] = useState(true);

  // numeric selections
  const [selectedNumeric, setSelectedNumeric] = useState([]);
  const [criteriaTypes, setCriteriaTypes] = useState({});

  // categorical selections + ordinal mappings
  const [selectedCategorical, setSelectedCategorical] = useState([]);
  const [categoricalTypes, setCategoricalTypes] = useState({});
  const [ordinalMappings, setOrdinalMappings] = useState({});

  // global settings
  const [targetColumn, setTargetColumn] = useState('');
  const [potentialTargets, setPotentialTargets] = useState([]);
  const [missingStrategy, setMissingStrategy] = useState('mean');
  const [totalMissing, setTotalMissing] = useState(0);

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

      const types = {};
      (data.suggested_criteria || []).forEach(c => { types[c.name] = c.type || 'benefit'; });
      setCriteriaTypes(types);

      const catTypes = {};
      (data.categorical_columns || []).forEach(c => { catTypes[c.name] = 'benefit'; });
      setCategoricalTypes(catTypes);

      // Default ordinal mapping: auto-assign 1..n alphabetically
      const mappings = {};
      (data.categorical_columns || []).forEach(c => {
        const m = {};
        c.unique_values.forEach((v, i) => { m[v] = String(i + 1); });
        mappings[c.name] = m;
      });
      setOrdinalMappings(mappings);

      // Count columns with missing values
      const allCols = [...(data.suggested_criteria || []), ...(data.categorical_columns || [])];
      setTotalMissing(allCols.filter(c => c.missing > 0).length);
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

    const numericSelected = numericCriteria
      .filter(c => selectedNumeric.includes(c.name))
      .map(c => ({ ...c, type: criteriaTypes[c.name] || 'benefit' }));

    const categoricalSelected = categoricalCriteria
      .filter(c => selectedCategorical.includes(c.name))
      .map(c => ({
        ...c,
        type: categoricalTypes[c.name] || 'benefit',
        encoding: Object.fromEntries(
          Object.entries(ordinalMappings[c.name] || {}).map(([k, v]) => [k, parseFloat(v)])
        ),
      }));

    const config = {
      data_source: { file_path: `data/raw/${filename}`, id_column: idColumn },
      criteria: [...numericSelected, ...categoricalSelected],
      missing_strategy: missingStrategy,
      ahp: { enabled: true },
      topsis: { enabled: true },
      machine_learning: {
        enabled: true,
        target_column: targetColumn || null,
        test_size: 0.2,
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
          <strong>Benefit ↑</strong> : valeur haute = meilleur (ex: GPA, score au test) &nbsp;|&nbsp;
          <strong>Cost ↓</strong> : valeur basse = meilleur (ex: frais, absentéisme)
        </p>

        {numericCriteria.length === 0 && (
          <p className="no-cols-msg">Aucune colonne numérique détectée.</p>
        )}

        {numericCriteria.map((crit, idx) => {
          const selected = selectedNumeric.includes(crit.name);
          const type = criteriaTypes[crit.name] || 'benefit';
          return (
            <div key={crit.name} className={`criteria-item ${!selected ? 'criteria-disabled' : ''}`}>
              <div className="criteria-checkbox">
                <input type="checkbox" checked={selected} onChange={() => handleToggleNumeric(crit.name)} id={`num-${idx}`} />
                <label htmlFor={`num-${idx}`}>
                  {crit.display_name || crit.name}
                  <span className="criteria-range"> ({crit.range?.[0]?.toFixed(1)} – {crit.range?.[1]?.toFixed(1)})</span>
                  {crit.missing > 0 && <span className="missing-badge"> ⚠ {crit.missing} manquants</span>}
                </label>
              </div>
              {selected && (
                <div className="criteria-type-toggle">
                  <button className={`type-btn ${type === 'benefit' ? 'type-btn-active benefit' : ''}`} onClick={() => setCriteriaTypes(p => ({ ...p, [crit.name]: 'benefit' }))} type="button">Benefit ↑</button>
                  <button className={`type-btn ${type === 'cost' ? 'type-btn-active cost' : ''}`} onClick={() => setCriteriaTypes(p => ({ ...p, [crit.name]: 'cost' }))} type="button">Cost ↓</button>
                </div>
              )}
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
            Ex : Licence=1, Master=2, Doctorat=3
          </p>

          {categoricalCriteria.map((crit, idx) => {
            const selected = selectedCategorical.includes(crit.name);
            const type = categoricalTypes[crit.name] || 'benefit';
            const mapping = ordinalMappings[crit.name] || {};
            return (
              <div key={crit.name} className={`criteria-item ${!selected ? 'criteria-disabled' : ''}`}>
                <div className="criteria-checkbox">
                  <input type="checkbox" checked={selected} onChange={() => handleToggleCategorical(crit.name)} id={`cat-${idx}`} />
                  <label htmlFor={`cat-${idx}`}>
                    {crit.display_name || crit.name}
                    <span className="criteria-range"> ({crit.unique_values.length} valeurs)</span>
                    {crit.missing > 0 && <span className="missing-badge"> ⚠ {crit.missing} manquants</span>}
                  </label>
                </div>

                {selected && (
                  <>
                    <div className="criteria-type-toggle">
                      <button className={`type-btn ${type === 'benefit' ? 'type-btn-active benefit' : ''}`} onClick={() => setCategoricalTypes(p => ({ ...p, [crit.name]: 'benefit' }))} type="button">Benefit ↑</button>
                      <button className={`type-btn ${type === 'cost' ? 'type-btn-active cost' : ''}`} onClick={() => setCategoricalTypes(p => ({ ...p, [crit.name]: 'cost' }))} type="button">Cost ↓</button>
                    </div>
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

      {/* Missing value strategy */}
      {totalMissing > 0 && (
        <div className="config-section">
          <label>Stratégie pour les valeurs manquantes ({totalMissing} colonne{totalMissing > 1 ? 's' : ''} concernée{totalMissing > 1 ? 's' : ''}) :</label>
          <select value={missingStrategy} onChange={e => setMissingStrategy(e.target.value)} className="select">
            <option value="mean">Remplacer par la moyenne</option>
            <option value="median">Remplacer par la médiane</option>
            <option value="zero">Remplacer par 0</option>
            <option value="exclude">Exclure les lignes incomplètes</option>
          </select>
        </div>
      )}

      {/* ML target column */}
      {potentialTargets.length > 0 && (
        <div className="config-section">
          <label>Colonne cible ML (optionnel) :</label>
          <p className="ml-hint">
            Si vous disposez d'une colonne de résultat historique (ex : score d'admission passé),
            le modèle ML s'entraîne dessus pour améliorer le classement.
          </p>
          <select value={targetColumn} onChange={e => setTargetColumn(e.target.value)} className="select">
            <option value="">— Aucune (TOPSIS + AHP uniquement) —</option>
            {potentialTargets.map(col => <option key={col} value={col}>{col}</option>)}
          </select>
        </div>
      )}

      <button
        className="btn btn-primary btn-large"
        onClick={handleProcessData}
        disabled={totalSelected < 2}
      >
        Continuer vers la matrice AHP →
      </button>
    </div>
  );
};

export default CriteriaConfig;
