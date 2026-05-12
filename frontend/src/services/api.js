/*
 * API Service - Frontend backend communication
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

// Parse a failed response safely — backend may return HTML in debug mode
async function parseError(response, fallback = 'Erreur serveur') {
  try {
    const data = await response.json();
    return data.error || data.message || `${fallback} (HTTP ${response.status})`;
  } catch {
    return `${fallback} (HTTP ${response.status}). Vérifiez que le backend est démarré et relancez l'opération.`;
  }
}

export const apiService = {
  // Upload a file
  uploadFile: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/upload/file`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(await parseError(response, "Échec de l'upload"));
    }

    return response.json();
  },

  // Get file preview
  getPreview: async (filename) => {
    const response = await fetch(`${API_BASE_URL}/upload/preview/${filename}`);

    if (!response.ok) {
      throw new Error(await parseError(response, 'Aperçu indisponible'));
    }

    return response.json();
  },

  // Validate file and get QA report
  validateFile: async (filename) => {
    const response = await fetch(`${API_BASE_URL}/upload/validate/${filename}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(await parseError(response, 'Validation échouée'));
    }

    return response.json();
  },

  // Get criteria suggestions
  getCriteriaSuggestions: async (filename) => {
    const response = await fetch(`${API_BASE_URL}/ranking/criteria-suggestions/${filename}`);

    if (!response.ok) {
      throw new Error(await parseError(response, 'Chargement des critères échoué'));
    }

    return response.json();
  },

  // Process data with configuration
  processData: async (filename, config) => {
    const response = await fetch(`${API_BASE_URL}/ranking/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, config })
    });

    if (!response.ok) {
      throw new Error(await parseError(response, 'Traitement échoué'));
    }

    return response.json();
  },

  // Download results as CSV
  downloadResultsCSV: async (resultId) => {
    const response = await fetch(`${API_BASE_URL}/download/results/${resultId}`);

    if (!response.ok) {
      throw new Error(await parseError(response, 'Téléchargement CSV échoué'));
    }

    return response.blob();
  },

  // Download results as Excel
  downloadResultsExcel: async (resultId) => {
    const response = await fetch(`${API_BASE_URL}/download/results/${resultId}/excel`);

    if (!response.ok) {
      throw new Error(await parseError(response, 'Téléchargement Excel échoué'));
    }

    return response.blob();
  },

  // Get AHP matrix template
  getAHPMatrix: async (criteriaCount) => {
    const response = await fetch(`${API_BASE_URL}/ahp/matrix/${criteriaCount}`);

    if (!response.ok) {
      throw new Error(await parseError(response, 'Matrice AHP indisponible'));
    }

    return response.json();
  },

  // Calculate AHP weights from comparison matrix
  calculateAHPWeights: async (payload) => {
    const response = await fetch(`${API_BASE_URL}/ahp/weights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(await parseError(response, 'Calcul AHP échoué'));
    }

    return response.json();
  },

  // Validate AHP matrix
  validateAHPMatrix: async (matrix) => {
    const response = await fetch(`${API_BASE_URL}/ahp/validate-matrix`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ matrix })
    });

    if (!response.ok) {
      throw new Error(await parseError(response, 'Validation matrice échouée'));
    }

    return response.json();
  },

  // Submit validated ranking for incremental ML learning
  submitFeedback: async (file, sessionId, criteriaColumns) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    formData.append('criteria', JSON.stringify(criteriaColumns));

    const response = await fetch(`${API_BASE_URL}/feedback/submit`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await parseError(response, 'Soumission du feedback échouée'));
    }

    return response.json();
  },

  // Get historical feedback sessions
  getFeedbackHistory: async () => {
    const response = await fetch(`${API_BASE_URL}/feedback/history`);

    if (!response.ok) {
      throw new Error(await parseError(response, 'Historique indisponible'));
    }

    return response.json();
  },

  // Delete a historical session
  deleteFeedbackSession: async (sessionId) => {
    const response = await fetch(`${API_BASE_URL}/feedback/history/${sessionId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(await parseError(response, 'Suppression échouée'));
    }

    return response.json();
  },

  // Health check
  healthCheck: async () => {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  }
};

// Helper function to download blob
export const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};
