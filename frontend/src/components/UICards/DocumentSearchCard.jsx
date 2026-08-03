import React, { useState } from 'react';
import { Search, FileText, ChevronDown, ChevronUp, Layers, ExternalLink } from 'lucide-react';

const DocumentSearchCard = ({ data }) => {
  if (!data) return null;

  const query = data.query || 'Knowledge Query';
  const results = data.results || [];
  const [expandedId, setExpandedId] = useState(null);

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="ui-card card-document-search glass-card">
      {/* Header */}
      <div className="ui-card-header">
        <div className="flex items-center gap-2">
          <div className="card-icon-badge icon-blue">
            <Search size={18} />
          </div>
          <div>
            <h4 className="ui-card-title">Knowledge Search Results</h4>
            <span className="ui-card-subtitle">Query: "{query}"</span>
          </div>
        </div>
        <span className="badge badge-info text-xs">
          {results.length} Chunks Matched
        </span>
      </div>

      {/* Results List */}
      <div className="search-results-list">
        {results.length === 0 ? (
          <div className="text-xs text-zinc-400 p-3 text-center">No matching document chunks found.</div>
        ) : (
          results.map((res, idx) => {
            const isExpanded = expandedId === (res.id || idx);
            const scorePct = Math.min(100, Math.round((res.rrf_score || 0.05) * 1000));
            const formatStr = (res.file_format || 'TXT').toUpperCase();

            return (
              <div key={res.id || idx} className={`search-result-item ${isExpanded ? 'is-expanded' : ''}`}>
                <div className="result-header" onClick={() => toggleExpand(res.id || idx)}>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`format-badge format-${formatStr.toLowerCase()}`}>
                      {formatStr}
                    </span>
                    <span className="result-section-title truncate">
                      {res.section_title || 'General Section'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="score-pill" title="Reciprocal Rank Fusion Score">
                      <Layers size={11} />
                      <span>{res.rrf_score ? res.rrf_score.toFixed(4) : 'RRF'}</span>
                    </div>
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </div>

                {/* Snippet Preview */}
                <div className="result-snippet-preview">
                  {isExpanded ? res.snippet : `${res.snippet ? res.snippet.slice(0, 140) : ''}...`}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="ui-card-footer justify-between">
        <div className="flex items-center gap-1">
          <FileText size={12} />
          <span>Hybrid Vector & RRF RAG Search</span>
        </div>
      </div>
    </div>
  );
};

export default DocumentSearchCard;
