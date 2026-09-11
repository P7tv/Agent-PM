import React, { useState, useEffect } from 'react';
import { Folder, File, RefreshCw } from 'lucide-react';

export default function WorkspaceFileBrowser({ projectId }) {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [contentLoading, setContentLoading] = useState(false);

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/files`);
      const data = await res.json();
      setFiles(data.files || []);
    } catch (e) {
      console.error('Error fetching files:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) fetchFiles();
  }, [projectId]);

  const handleSelectFile = async (path) => {
    setSelectedFile(path);
    setContentLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/files/content?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      setFileContent(data.content || '');
    } catch (e) {
      setFileContent('// Error loading file content');
    } finally {
      setContentLoading(false);
    }
  };

  return (
    <div className="file-browser-container">
      <div className="file-browser-sidebar">
        <div className="file-browser-header">
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Workspace Files</span>
          <button className="view-btn" onClick={fetchFiles} title="Refresh file list" style={{ padding: '2px 6px' }}>
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
        <div className="file-tree-list">
          {files.map((f) => (
            <div
              key={f.path}
              className={`file-tree-item ${selectedFile === f.path ? 'active' : ''}`}
              onClick={() => !f.is_dir && handleSelectFile(f.path)}
            >
              {f.is_dir ? <Folder size={13} className="text-amber-400 flex-shrink-0" /> : <File size={13} className="text-slate-400 flex-shrink-0" />}
              <span className="file-tree-name truncate">{f.name}</span>
            </div>
          ))}
          {!files.length && !loading && (
            <p className="text-xs text-slate-500 p-3">No files found</p>
          )}
        </div>
      </div>
      <div className="file-viewer-main">
        {selectedFile ? (
          <>
            <div className="file-viewer-header">
              <span className="font-mono text-xs text-slate-300">{selectedFile}</span>
            </div>
            <pre className="file-content-pre">
              {contentLoading ? '// Loading...' : fileContent}
            </pre>
          </>
        ) : (
          <div className="file-viewer-empty">
            <p className="text-sm text-slate-400">Select a file from the left to view contents</p>
          </div>
        )}
      </div>
    </div>
  );
}
