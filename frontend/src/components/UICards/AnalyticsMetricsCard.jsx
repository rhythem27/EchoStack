import React from 'react';
import { Activity, BarChart2, Tag, Clock, User, ShieldCheck } from 'lucide-react';

const AnalyticsMetricsCard = ({ data }) => {
  if (!data) return null;

  const totalInteractions = data.total_interactions || 0;
  const topTopics = Array.isArray(data.top_topics)
    ? data.top_topics
    : (typeof data.top_topics === 'string' ? [data.top_topics] : []);
  const lastUpdated = data.last_updated_at
    ? new Date(data.last_updated_at).toLocaleString()
    : 'Just now';
  const userId = data.user_id ? `${data.user_id.slice(0, 8)}...` : 'System User';

  // Calculate simulated engagement percentage (cap at 100%)
  const engagementPct = Math.min(100, Math.round((totalInteractions / 50) * 100));

  return (
    <div className="ui-card card-analytics-metrics glass-card">
      {/* Header */}
      <div className="ui-card-header">
        <div className="flex items-center gap-2">
          <div className="card-icon-badge icon-purple">
            <BarChart2 size={18} />
          </div>
          <div>
            <h4 className="ui-card-title">User Engagement Insights</h4>
            <span className="ui-card-subtitle">Real-Time Interaction Telemetry</span>
          </div>
        </div>
        <span className="badge badge-success flex items-center gap-1 text-xs">
          <ShieldCheck size={12} /> Verified
        </span>
      </div>

      {/* Metrics Row */}
      <div className="ui-card-grid">
        <div className="metric-tile">
          <span className="tile-label">Total Interactions</span>
          <span className="tile-value text-purple font-mono">{totalInteractions.toLocaleString()}</span>
        </div>
        <div className="metric-tile">
          <span className="tile-label">Active Account</span>
          <span className="tile-value text-blue font-mono">{userId}</span>
        </div>
      </div>

      {/* Engagement Level Progress Bar */}
      <div className="progress-section">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-zinc-400">Activity Level</span>
          <span className="text-purple-300 font-mono">{engagementPct}% Score</span>
        </div>
        <div className="progress-bar-track">
          <div
            className="progress-bar-fill gradient-purple-blue"
            style={{ width: `${engagementPct}%` }}
          ></div>
        </div>
      </div>

      {/* Topics Badges */}
      {topTopics.length > 0 && (
        <div className="topics-section">
          <div className="flex items-center gap-1 text-xs text-zinc-400 mb-1.5">
            <Tag size={12} />
            <span>Top Active Topics</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {topTopics.map((topic, idx) => (
              <span key={idx} className="topic-chip">
                {typeof topic === 'object' ? JSON.stringify(topic) : topic}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Footer Timestamp */}
      <div className="ui-card-footer">
        <Clock size={12} />
        <span>Last Synced: {lastUpdated}</span>
      </div>
    </div>
  );
};

export default AnalyticsMetricsCard;
