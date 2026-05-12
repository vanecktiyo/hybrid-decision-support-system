import React, { useState } from 'react';
import './FileUploader.css';
import { apiService } from '../services/api';

const FileUploader = ({ onFileUploaded, onError }) => {
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [file, setFile] = useState(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (file) => {
    const validTypes = ['text/csv', 'application/vnd.ms-excel', 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    const validExtensions = ['.csv', '.xlsx', '.xls'];
    
    const hasValidType = validTypes.includes(file.type);
    const hasValidExtension = validExtensions.some(ext => file.name.endsWith(ext));
    
    if (!hasValidType && !hasValidExtension) {
      onError('Invalid file type. Please upload CSV or Excel file.');
      return;
    }
    
    setFile(file);
    setLoading(true);
    setUploadProgress(0);
    
    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 200);
      
      const result = await apiService.uploadFile(file);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      
      onFileUploaded(result);
      
      setTimeout(() => {
        setLoading(false);
        setUploadProgress(0);
      }, 1000);
    } catch (error) {
      onError(error.message);
      setLoading(false);
      setUploadProgress(0);
      setFile(null);
    }
  };

  return (
    <div className="file-uploader">
      <div
        className={`upload-area ${dragActive ? 'active' : ''} ${loading ? 'loading' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="file-input"
          onChange={handleChange}
          accept=".csv,.xlsx,.xls"
          disabled={loading}
          style={{ display: 'none' }}
        />
        
        {!loading && (
          <>
            <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <h3>Upload Your Data File</h3>
            <p>Drag and drop your CSV or Excel file here</p>
            <p className="or">or</p>
            <label htmlFor="file-input" className="browse-button">
              Browse Files
            </label>
            <p className="file-info">
              Supported formats: CSV, XLSX, XLS (Max 50MB)
            </p>
          </>
        )}
        
        {loading && (
          <>
            <div className="loading-spinner"></div>
            <p>Uploading {file?.name}...</p>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p className="progress-text">{uploadProgress}%</p>
          </>
        )}
      </div>
    </div>
  );
};

export default FileUploader;
