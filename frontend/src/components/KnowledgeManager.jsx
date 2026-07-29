import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Layers, 
  Trash2, 
  RefreshCw, 
  FileText, 
  Search, 
  X, 
  CheckCircle2, 
  AlertCircle,
  FileCode,
  Table,
  Presentation,
  AlignLeft,
  Info
} from 'lucide-react';

const getFileIcon = (fileName) => {
  const ext = fileName ? fileName.split('.').pop().toLowerCase() : '';
  switch (ext) {
    case 'pdf':
      return <FileText size={18} className="text-red-400" />;
    case 'docx':
      return <FileText size={18} className="text-blue-400" />;
    case 'csv':
      return <Table size={18} className="text-green-400" />;
    case 'pptx':
      return <Presentation size={18} className="text-amber-400" />;
    case 'md':
      return <FileCode size={18} className="text-purple-400" />;
    default:
      return <AlignLeft size={18} className="text-zinc-400" />;
  }
};

export default function KnowledgeManager({ backendUrl, isOpen, onClose, onRefresh }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [chunksData, setChunksData] = useState(null);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (e) {
      console.error('Failed to load documents:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDocs();
    }
  }, [isOpen, backendUrl]);

  const inspectChunks = async (doc) => {
    setSelectedDoc(doc);
    setLoadingChunks(true);
    try {
      const res = await fetch(`${backendUrl}/documents/${doc.id}/chunks`);
      if (res.ok) {
        const data = await res.json();
        setChunksData(data);
      } else {
        setChunksData(null);
      }
    } catch (e) {
      console.error('Failed to load chunks:', e);
      setChunksData(null);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleDelete = async (docId, fileName) => {
    if (!window.confirm(`Are you sure you want to delete "${fileName}" and all its vector embeddings?`)) {
      return;
    }
    try {
      const res = await fetch(`${backendUrl}/documents/${docId}`, { method: 'DELETE' });
      if (res.ok) {
        setStatusMsg({ type: 'success', text: `Document "${fileName}" deleted.` });
        if (selectedDoc && selectedDoc.id === docId) {
          setSelectedDoc(null);
          setChunksData(null);
        }
        fetchDocs();
        if (onRefresh) onRefresh();
      } else {
        setStatusMsg({ type: 'error', text: `Failed to delete document.` });
      }
    } catch (e) {
      setStatusMsg({ type: 'error', text: `Error: ${e.message}` });
    }
  };

  const handleReindex = async (docId, fileName) => {
    try {
      const res = await fetch(`${backendUrl}/documents/${docId}/reindex`, { method: 'POST' });
      if (res.ok) {
        setStatusMsg({ type: 'info', text: `Re-indexing triggered for "${fileName}".` });
        fetchDocs();
        if (onRefresh) onRefresh();
      } else {
        setStatusMsg({ type: 'error', text: `Failed to trigger re-index.` });
      }
    } catch (e) {
      setStatusMsg({ type: 'error', text: `Error: ${e.message}` });
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('WARNING: This will erase ALL knowledge documents and vector embeddings from PostgreSQL. Continue?')) {
      return;
    }
    try {
      const res = await fetch(`${backendUrl}/documents`, { method: 'DELETE' });
      if (res.ok) {
        setStatusMsg({ type: 'success', text: 'Entire knowledge base collection cleared.' });
        setSelectedDoc(null);
        setChunksData(null);
        fetchDocs();
        if (onRefresh) onRefresh();
      }
    } catch (e) {
      setStatusMsg({ type: 'error', text: `Error: ${e.message}` });
    }
  };

  if (!isOpen) return null;

  const filteredDocs = documents.filter(d => 
    d.file_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="km-modal-overlay">
      <div className="km-modal-container glass-card">
        {/* Modal Header */}
        <div className="km-modal-header">
          <div className="logo-group">
            <Database className="header-icon-blue" size={24} />
            <h2>Knowledge Base Explorer</h2>
          </div>
          <div className="km-header-actions">
            <button onClick={handleClearAll} className="btn btn-danger-outline btn-sm">
              <Trash2 size={15} /> Clear Collection
            </button>
            <button onClick={onClose} className="km-close-btn">
              <X size={20} />
            </button>
          </div>
        </div>

        {statusMsg && (
          <div className={`status-banner ${statusMsg.type === 'error' ? 'banner-error' : 'banner-info'} m-3`}>
            {statusMsg.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
            <p>{statusMsg.text}</p>
          </div>
        )}

        {/* Modal Content Split: Left = Doc List, Right = Chunk Viewer */}
        <div className="km-modal-body">
          {/* Left Column: Document Catalog */}
          <div className="km-doc-catalog">
            <div className="km-search-box">
              <Search size={16} className="search-icon" />
              <input 
                type="text" 
                placeholder="Search knowledge documents..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="text-input"
              />
            </div>

            <div className="km-catalog-list">
              {loading ? (
                <div className="list-empty"><RefreshCw className="icon-pulse" size={20} /> Loading catalog...</div>
              ) : filteredDocs.length === 0 ? (
                <div className="list-empty">No matching documents indexed.</div>
              ) : (
                filteredDocs.map((doc) => {
                  const isSelected = selectedDoc && selectedDoc.id === doc.id;
                  return (
                    <div 
                      key={doc.id} 
                      className={`km-doc-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => inspectChunks(doc)}
                    >
                      <div className="km-doc-info">
                        <div className="km-doc-title">
                          {getFileIcon(doc.file_name)}
                          <span>{doc.file_name}</span>
                        </div>
                        <div className="km-doc-meta">
                          <span className={`doc-status status-${doc.status.toLowerCase()}`}>{doc.status}</span>
                          <span className="km-chunk-count">
                            <Layers size={13} /> {doc.chunk_count || 0} chunks
                          </span>
                        </div>
                      </div>

                      <div className="km-card-actions" onClick={(e) => e.stopPropagation()}>
                        <button 
                          title="Re-index document"
                          onClick={() => handleReindex(doc.id, doc.file_name)}
                          className="btn-icon text-blue-400 hover:text-blue-300"
                        >
                          <RefreshCw size={15} />
                        </button>
                        <button 
                          title="Delete document"
                          onClick={() => handleDelete(doc.id, doc.file_name)}
                          className="btn-icon text-red-400 hover:text-red-300"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Chunk Inspector */}
          <div className="km-chunk-inspector">
            {selectedDoc ? (
              <div className="km-inspector-content">
                <div className="km-inspector-header">
                  <h3>Chunk Breakdown for <span>{selectedDoc.file_name}</span></h3>
                  {chunksData && (
                    <span className="badge badge-info">{chunksData.total_chunks} Total Chunks</span>
                  )}
                </div>

                {loadingChunks ? (
                  <div className="list-empty"><RefreshCw className="icon-pulse" size={20} /> Fetching document chunks...</div>
                ) : chunksData && chunksData.chunks.length > 0 ? (
                  <div className="km-chunks-list">
                    {chunksData.chunks.map((chunk, idx) => (
                      <div key={chunk.id || idx} className="km-chunk-card glass-card">
                        <div className="km-chunk-card-header">
                          <span className="km-chunk-badge">Chunk #{idx + 1}</span>
                          {chunk.metadata?.section_title && (
                            <span className="km-meta-tag section-tag">
                              Section: {chunk.metadata.section_title}
                            </span>
                          )}
                          {chunk.metadata?.file_format && (
                            <span className="km-meta-tag format-tag">
                              {chunk.metadata.file_format.toUpperCase()}
                            </span>
                          )}
                        </div>
                        <div className="km-chunk-text">
                          <pre>{chunk.chunk_text}</pre>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="list-empty">No vector chunks persisted for this document.</div>
                )}
              </div>
            ) : (
              <div className="km-inspector-empty">
                <Info size={40} className="text-zinc-600 mb-3" />
                <p>Select a document from the left catalog to inspect vector chunks and metadata tags.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
