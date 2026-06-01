import React, { useState } from 'react';
import './Dashboard.css';
import LandingPage from './LandingPage';
import FileUploader from './FileUploader';
import QAReport from './QAReport';
import CriteriaConfig from './CriteriaConfig';
import AHPMatrix from './AHPMatrix';
import ResultsViewer from './ResultsViewer';
import FeedbackModal from './FeedbackModal';
import { apiService } from '../services/api';

const STEPS = [
  { id: 'upload',     label: 'Import' },
  { id: 'qa_report',  label: 'Validation' },
  { id: 'config',     label: 'Critères' },
  { id: 'ahp_matrix', label: 'Matrice AHP' },
  { id: 'results',    label: 'Résultats' },
];
const STEP_IDS = STEPS.map(s => s.id);

const CheckIcon = () => (
  <svg className="step-check" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const BrandIcon = () => (
  <svg width="28" height="28" viewBox="0 0 60 56" fill="none">
    <polygon points="30,4  58,20  30,36  2,20"  fill="#ffffff"/>
    <polygon points="30,18 54,31  30,44  6,31"  fill="#ffffff" opacity="0.65"/>
    <polygon points="30,30 50,41  30,52 10,41"  fill="#ffffff" opacity="0.35"/>
  </svg>
);

const Dashboard = () => {
  const [currentStep, setCurrentStep] = useState('landing');
  const [fileInfo, setFileInfo] = useState(null);
  const [qaReport, setQAReport] = useState(null);
  const [missingStrategy, setMissingStrategy] = useState('mean');
  const [criteria, setCriteria] = useState([]);
  const [currentConfig, setCurrentConfig] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [processError, setProcessError] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);

  const handleFileUploaded = async (info) => {
    setFileInfo(info);
    setError(null);
    try {
      setLoading(true);
      const report = await apiService.validateFile(info.filename);
      setQAReport(report.validation_report);
      setCurrentStep('qa_report');
    } catch (err) {
      setError('Échec de la validation : ' + err.message);
      setCurrentStep('upload');
    } finally {
      setLoading(false);
    }
  };

  const handleQAReportConfirm = (strategy) => { setMissingStrategy(strategy); setCurrentStep('config'); };
  const handleQAReportBack = () => { setFileInfo(null); setQAReport(null); setCurrentStep('upload'); };

  const handleConfigReady = (config) => {
    setCurrentConfig(config);
    setCriteria(config.criteria);
    setError(null);
    setCurrentStep('ahp_matrix');
  };

  const handleAHPMatrixReady = async (ahpData) => {
    try {
      setProcessError(null);
      setLoading(true);
      const finalConfig = {
        ...currentConfig,
        ahp: { enabled: true, comparison_matrix: ahpData.comparison_matrix, weights: ahpData.weights, cr: ahpData.cr },
        hybrid: { topsis_weight: ahpData.topsis_weight ?? 0.6, ml_weight: ahpData.ml_weight ?? 0.4 },
      };
      const result = await apiService.processData(fileInfo.filename, finalConfig);
      if (result.status === 'success') { setResults(result); setCurrentStep('results'); }
    } catch (err) {
      setProcessError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setCurrentStep('upload');
    setFileInfo(null); setQAReport(null); setMissingStrategy('mean'); setCriteria([]);
    setCurrentConfig(null); setResults(null);
    setError(null); setProcessError(null); setShowFeedback(false);
  };

  const handleHome = () => {
    handleReset();
    setCurrentStep('landing');
  };

  const goToStep = (stepId) => {
    const targetIdx = STEP_IDS.indexOf(stepId);
    const currentIdx = STEP_IDS.indexOf(currentStep);
    if (targetIdx >= currentIdx) return;
    if (targetIdx < STEP_IDS.indexOf('config')) { setCriteria([]); setCurrentConfig(null); }
    if (targetIdx < STEP_IDS.indexOf('qa_report')) { setFileInfo(null); setQAReport(null); }
    setResults(null);
    setError(null);
    setProcessError(null);
    setCurrentStep(stepId);
  };

  if (currentStep === 'landing') {
    return (
      <>
        <LandingPage
          onStart={() => setCurrentStep('upload')}
          onValidate={() => setShowFeedback(true)}
        />
        {showFeedback && (
          <FeedbackModal
            resultId={null}
            criteriaColumns={[]}
            onClose={() => setShowFeedback(false)}
          />
        )}
      </>
    );
  }

  const activeIdx = STEP_IDS.indexOf(currentStep);

  return (
    <div className="app-shell">
      {/* Top bar */}
      <header className="app-topbar">
        <div className="topbar-brand" onClick={handleHome}>
          <BrandIcon />
          <span className="topbar-brand-name">Admission<span> Ranking</span></span>
        </div>
        <div className="topbar-divider"/>
        <span className="topbar-title">Système de classement multi-critères</span>
        <div className="topbar-spacer"/>
        <button className="topbar-home-btn" onClick={handleHome}>Accueil</button>
      </header>

      {/* Stepper */}
      <div className="stepper-bar">
        <div className="stepper-inner">
          {STEPS.map((step, i) => {
            const isCompleted = i < activeIdx;
            const isActive    = i === activeIdx;
            const cls = isCompleted ? 'completed' : isActive ? 'active' : '';
            return (
              <React.Fragment key={step.id}>
                <div
                  className={`stepper-step ${cls}${isCompleted ? ' clickable' : ''}`}
                  onClick={isCompleted ? () => goToStep(step.id) : undefined}
                >
                  <div className="step-circle">
                    {isCompleted ? <CheckIcon /> : i + 1}
                  </div>
                  <span className="step-name">{step.label}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`stepper-line ${isCompleted ? 'done' : ''}`}/>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Main */}
      <main className="app-main">
        {error && (
          <div className="alert-bar alert-error">
            <span>{error}</span>
            <button className="alert-close" onClick={() => setError(null)}>×</button>
          </div>
        )}
        {processError && (
          <div className="alert-bar alert-error">
            <span>Erreur de traitement : {processError}</span>
            <button className="alert-close" onClick={() => setProcessError(null)}>×</button>
          </div>
        )}

        <div className="content-card">
          <div className="card-body">
            {currentStep === 'upload' && (
              <FileUploader onFileUploaded={handleFileUploaded} onError={e => setError(e)} />
            )}
            {currentStep === 'qa_report' && (
              <QAReport report={qaReport} filename={fileInfo?.filename} onConfirm={handleQAReportConfirm} onGoBack={handleQAReportBack} />
            )}
            {currentStep === 'config' && (
              <CriteriaConfig filename={fileInfo?.filename} fileInfo={fileInfo} missingStrategy={missingStrategy} onConfigReady={handleConfigReady} onError={e => setError(e)} onBack={() => goToStep('qa_report')} />
            )}
            {currentStep === 'ahp_matrix' && (
              <AHPMatrix criteria={criteria} onMatrixReady={handleAHPMatrixReady} onError={e => setError(e)} onBack={() => setCurrentStep('config')} mlEnabled={!!currentConfig?.machine_learning?.target_column} />
            )}
            {currentStep === 'results' && (
              <ResultsViewer results={results} criteria={criteria} onError={e => setError(e)} onValidate={() => setShowFeedback(true)} onBack={() => goToStep('ahp_matrix')} />
            )}
          </div>
        </div>

        {currentStep === 'results' && (
          <div className="action-row">
            <button className="btn btn-secondary" onClick={handleReset}>Nouvelle analyse</button>
          </div>
        )}
      </main>

      {/* Processing overlay */}
      {loading && (
        <div className="processing-overlay">
          <div className="processing-box">
            <div className="spinner"/>
            <p className="processing-title">Analyse en cours…</p>
            <p className="processing-sub">AHP · TOPSIS · Machine Learning</p>
          </div>
        </div>
      )}

      <footer className="app-footer">
        Hybrid Multi-Criteria Decision Making System : AHP · TOPSIS · Machine Learning
      </footer>

      {showFeedback && (
        <FeedbackModal
          resultId={results?.result_id}
          criteriaColumns={criteria.map(c => c.source_column || c.name)}
          onClose={() => setShowFeedback(false)}
        />
      )}
    </div>
  );
};

export default Dashboard;
