import React from 'react';

/**
 * Real-Time Vision Spatial Anchoring Overlay Component
 * Converts normalized [ymin, xmin, ymax, xmax] (0-1000 scale) coordinates 
 * into responsive CSS overlay boxes with glowing borders, reticle corners, and labels.
 */
const VisionOverlay = ({ highlights = [] }) => {
  if (!highlights || highlights.length === 0) return null;

  return (
    <div className="vision-overlay-container">
      {highlights.map((item) => {
        const box = item.box_2d || [0, 0, 1000, 1000];
        const ymin = Math.max(0, Math.min(1000, box[0] ?? 0));
        const xmin = Math.max(0, Math.min(1000, box[1] ?? 0));
        const ymax = Math.max(0, Math.min(1000, box[2] ?? 1000));
        const xmax = Math.max(0, Math.min(1000, box[3] ?? 1000));

        const top = `${(ymin / 10).toFixed(2)}%`;
        const left = `${(xmin / 10).toFixed(2)}%`;
        const height = `${Math.max(3, (ymax - ymin) / 10).toFixed(2)}%`;
        const width = `${Math.max(3, (xmax - xmin) / 10).toFixed(2)}%`;

        return (
          <div
            key={item.id}
            className="spatial-box"
            style={{
              top,
              left,
              width,
              height
            }}
          >
            {/* Label badge */}
            <div className="spatial-label">
              <span className="spatial-label-dot"></span>
              <span className="spatial-label-text">{item.label || 'Target Object'}</span>
            </div>

            {/* Corner accent reticles */}
            <div className="reticle reticle-tl" />
            <div className="reticle reticle-tr" />
            <div className="reticle reticle-bl" />
            <div className="reticle reticle-br" />
          </div>
        );
      })}
    </div>
  );
};

export default VisionOverlay;
