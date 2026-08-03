import React from 'react';
import AnalyticsMetricsCard from './AnalyticsMetricsCard';
import DocumentSearchCard from './DocumentSearchCard';
import PythonResultCard from './PythonResultCard';

const CARD_COMPONENTS = {
  AnalyticsMetricsCard,
  DocumentSearchCard,
  PythonResultCard
};

const UICardDispatcher = ({ component, data }) => {
  const ComponentToRender = CARD_COMPONENTS[component];

  if (!ComponentToRender) {
    console.warn(`[UICardDispatcher] Unknown card component: ${component}`);
    return (
      <div className="ui-card glass-card p-3 text-xs text-zinc-400">
        Unknown UI Card component: "{component}"
      </div>
    );
  }

  return (
    <div className="ui-card-wrapper animate-slide-up">
      <ComponentToRender data={data} />
    </div>
  );
};

export default UICardDispatcher;
