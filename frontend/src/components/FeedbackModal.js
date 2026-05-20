import React, { useState, useEffect } from 'react';
import './FeedbackModal.css';
import { apiService } from '../services/api';

/**
 * FeedbackModal - Interface for the "responsable de formation".
 *
 * Workflow:
 *  1. Responsable downloads the ranking CSV (already done in ResultsViewer)
 *  2. Opens this modal, reads the instructions
 *  3. Uploads the modified CSV (with Validated_Tier column filled in)
 *  4. Clicks "Soumettre" → POST /api/feedback/submit
 *  5. Success message confirms the data is saved for future ML training
 *
 * Props:
 *  - resultId     : string  — current result identifier (used as default session_id)
 *  - criteriaColumns: string[] — list of criteria column names used in this analysis
 *  - onClose      : () => void
 */
const TIER_LABELS = ['Excellent', 'Bon', 'Moyen', 'Faible'];

const FeedbackModal = ({ resultId, criteriaColumns = [], onClose }) => {
  const [file, setFile]           = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [status, setStatus]       = useState('idle'); // idle | loading | success | error
  const [message, setMessage]     = useState('');
  const [history, setHistory]     = useState(null);

  useEffect(() => {
    setSessionId(resultId ? `${resultId}_validated` : `session_${Date.now()}`);
    loadHistory();
  }, [resultId]);

  const loadHistory = async () => {
    try {
      const h = await apiService.getFeedbackHistory();
      setHistory(h);
    } catch (_) {}
  };

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f && f.name.endsWith('.csv')) {
      setFile(f);
      setMessage('');
    } else {
      setFile(null);
      setMessage('Veuillez sélectionner un fichier CSV.');
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      setMessage('Sélectionnez un fichier CSV avant de soumettre.');
      return;
    }
    try {
      setStatus('loading');
      const result = await apiService.submitFeedback(file, sessionId, criteriaColumns);
      setStatus('success');
      setMessage(result.message || 'Feedback enregistré avec succès.');
      loadHistory();
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
    }
  };

  const handleDelete = async (sid) => {
    try {
      await apiService.deleteFeedbackSession(sid);
      loadHistory();
    } catch (err) {
      setMessage(`Erreur suppression : ${err.message}`);
    }
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="feedback-modal">
        {/* Header */}
        <div className="modal-header">
          <h3>Validation du classement</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* Instructions */}
        <div className="modal-instructions">
          <h4>Comment procéder :</h4>
          <ol>
            <li>
              Téléchargez le CSV du classement (bouton <strong>Télécharger CSV</strong> dans les résultats).
            </li>
            <li>
              Ouvrez-le dans Excel ou LibreOffice. Localisez la colonne <code>Predicted_Tier</code>.
            </li>
            <li>
              <strong>Renommez-la</strong> <code>Validated_Tier</code> et corrigez les valeurs selon votre jugement.
              Valeurs acceptées : {' '}
              {TIER_LABELS.map(t => (
                <span key={t} className={`tier-inline tier-${t.toLowerCase()}`}>{t}</span>
              ))}
            </li>
            <li>Sauvegardez le fichier au format CSV et re-uploadez-le ci-dessous.</li>
          </ol>
          <p className="modal-note">
            Ces données seront utilisées pour entraîner le modèle ML lors des prochains classements,
            le rendant progressivement plus précis.
          </p>
        </div>

        {/* Session ID */}
        <div className="form-group">
          <label>Identifiant de session</label>
          <input
            type="text"
            className="form-input"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Nom unique pour cette session"
          />
        </div>

        {/* File upload */}
        <div className="form-group">
          <label>Fichier CSV validé</label>
          <input
            type="file"
            accept=".csv"
            className="form-input"
            onChange={handleFileChange}
          />
          {file && (
            <p className="file-selected">✓ {file.name} sélectionné</p>
          )}
        </div>

        {/* Message */}
        {message && (
          <div className={`modal-message ${status === 'success' ? 'msg-success' : 'msg-error'}`}>
            {message}
          </div>
        )}

        {/* Actions */}
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Fermer
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={status === 'loading' || !file}
          >
            {status === 'loading' ? 'Envoi en cours…' : 'Soumettre la validation'}
          </button>
        </div>

        {/* History */}
        {history && history.n_sessions > 0 && (
          <div className="modal-history">
            <h4>
              Historique ({history.n_sessions} session{history.n_sessions > 1 ? 's' : ''},
              {' '}{history.total_records} enregistrements au total)
            </h4>
            <table className="history-table">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Enregistrements</th>
                  <th>Distribution</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {history.sessions.map((s) => (
                  <tr key={s.session_id}>
                    <td className="session-id">{s.session_id}</td>
                    <td>{s.n_records}</td>
                    <td>
                      {Object.entries(s.tier_distribution).map(([tier, count]) => (
                        <span key={tier} className={`tier-inline tier-${tier.toLowerCase()}`}>
                          {tier}:{count}
                        </span>
                      ))}
                    </td>
                    <td>
                      <button
                        className="btn-delete"
                        onClick={() => handleDelete(s.session_id)}
                        title="Supprimer cette session"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default FeedbackModal;
