import React, { useState, useEffect } from 'react';
import { Folder, File, RefreshCw, ChevronRight, ChevronDown, Loader2 } from 'lucide-react';
import { useToast } from './Toast';

const buildTree = (flatFiles) => {
  const root = { name: 'root', path: '', is_dir: true, children: [] };
  const map = { '': root };

  flatFiles.forEach(f => {
    map[f.path] = { ...f, children: f.is_dir ? [] : undefined };
  });

  flatFiles.forEach(f => {
    const parts = f.path.split('/');
    parts.pop();
    const parentPath = parts.join('/');
    const parent = map[parentPath] || root;
    if (!parent.children) parent.children = [];
    parent.children.push(map[f.path]);
  });

  const sortNode = (node) => {
    if (node.children) {
      node.children.sort((a, b) => {
        if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      node.children.forEach(sortNode);
    }
  };
  sortNode(root);

  return root.children;
};

function FileTreeNode({ node, depth, selectedFile, onSelect, expandedFolders, toggleFolder }) {
  const isExpanded = expandedFolders.has(node.path);
  
  return (
    <>
      <div 
        className={`file-tree-item ${selectedFile === node.path ? 'active' : ''}`}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
        onClick={() => {
          if (node.is_dir) toggleFolder(node.path);
          else onSelect(node.path);
        }}
      >
        {node.is_dir ? (
          <>
            {isExpanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
            <Folder size={13} className="text-amber-400 flex-shrink-0" />
          </>
        ) : (
          <>
            <span style={{ width: 14, display: 'inline-block' }}></span>
            <File size={13} className="text-slate-400 flex-shrink-0" />
          </>
        )}
        <span className="file-tree-name truncate">{node.name}</span>
      </div>
      {node.is_dir && isExpanded && node.children && node.children.map(child => (
        <FileTreeNode 
          key={child.path} 
          node={child} 
          depth={depth + 1} 
          selectedFile={selectedFile} 
          onSelect={onSelect} 
          expandedFolders={expandedFolders} 
          toggleFolder={toggleFolder} 
        />
      ))}
    </>
  );
}

export default function WorkspaceFileBrowser({ projectId }) {
  const [files, setFiles] = useState([]);
  const [fileTree, setFileTree] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [contentLoading, setContentLoading] = useState(false);
  const [expandedFolders, setExpandedFolders] = useState(new Set());

  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const toggleFolder = (path) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/files`);
      const data = await res.json();
      const flatFiles = data.files || [];
      setFiles(flatFiles);
      setFileTree(buildTree(flatFiles));
      
      // Auto-expand root folders by default
      const rootFolders = new Set();
      flatFiles.forEach(f => {
        if (f.is_dir && f.path.split('/').length === 1) {
          rootFolders.add(f.path);
        }
      });
      setExpandedFolders(rootFolders);
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
    setIsEditing(false);
    setSaveSuccess(false);
    setContentLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/files/content?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      const content = data.content || '';
      setFileContent(content);
      setEditContent(content);
    } catch (e) {
      setFileContent('// Error loading file content');
      setEditContent('// Error loading file content');
    } finally {
      setContentLoading(false);
    }
  };

  const toast = useToast();

  const handleSaveFile = async () => {
    if (!selectedFile || isSaving) return;
    setIsSaving(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/apply-change`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filepath: selectedFile,
          content: editContent,
          commit_message: `Update ${selectedFile}`
        })
      });
      if (res.ok) {
        setFileContent(editContent);
        setIsEditing(false);
        setSaveSuccess(true);
        toast.success(`Saved ${selectedFile} successfully!`);
        setTimeout(() => setSaveSuccess(false), 3000);
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to save file');
      }
    } catch (err) {
      toast.error('Error saving file: ' + err.message);
    } finally {
      setIsSaving(false);
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
          {fileTree.map((node) => (
            <FileTreeNode 
              key={node.path}
              node={node}
              depth={0}
              selectedFile={selectedFile}
              onSelect={handleSelectFile}
              expandedFolders={expandedFolders}
              toggleFolder={toggleFolder}
            />
          ))}
          {!fileTree.length && !loading && (
            <p className="text-xs text-slate-500 p-3">No files found</p>
          )}
        </div>
      </div>
      <div className="file-viewer-main">
        {selectedFile ? (
          <>
            <div className="file-viewer-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="font-mono text-xs text-slate-300">{selectedFile}</span>
                {saveSuccess && (
                  <span style={{ fontSize: '11px', color: 'var(--success, #10b981)', fontWeight: '600' }}>
                    ✓ Saved & Committed
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {isEditing ? (
                  <>
                    <button
                      className="view-btn"
                      onClick={() => {
                        setEditContent(fileContent);
                        setIsEditing(false);
                      }}
                      disabled={isSaving}
                      style={{ fontSize: '11px', padding: '3px 8px' }}
                    >
                      Cancel
                    </button>
                    <button
                      className="dispatch-btn"
                      onClick={handleSaveFile}
                      disabled={isSaving}
                      style={{ fontSize: '11px', padding: '3px 10px' }}
                    >
                      {isSaving ? 'Saving...' : '💾 Save & Commit'}
                    </button>
                  </>
                ) : (
                  <button
                    className="view-btn"
                    onClick={() => {
                      setEditContent(fileContent);
                      setIsEditing(true);
                    }}
                    style={{ fontSize: '11px', padding: '3px 8px' }}
                  >
                    ✏️ Edit File
                  </button>
                )}
              </div>
            </div>
            {isEditing ? (
              <textarea
                className="file-content-editor"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                spellCheck={false}
                style={{
                  flex: 1,
                  width: '100%',
                  padding: '16px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  lineHeight: '1.6',
                  color: 'var(--text-primary)',
                  background: 'var(--bg-canvas)',
                  border: 'none',
                  outline: 'none',
                  resize: 'none'
                }}
              />
            ) : (
              <pre className="file-content-pre">
                {contentLoading ? '// Loading...' : fileContent}
              </pre>
            )}
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
