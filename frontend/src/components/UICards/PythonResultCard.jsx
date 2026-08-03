import React, { useState } from 'react';
import { Code, Terminal, Copy, Check, AlertTriangle, Play } from 'lucide-react';

const PythonResultCard = ({ data }) => {
  if (!data) return null;

  const code = data.code || '# No python code provided';
  const output = data.output || 'No output stream returned.';
  const status = data.status || 'success';
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedOutput, setCopiedOutput] = useState(false);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleCopyOutput = () => {
    navigator.clipboard.writeText(output);
    setCopiedOutput(true);
    setTimeout(() => setCopiedOutput(false), 2000);
  };

  return (
    <div className="ui-card card-python-result glass-card">
      {/* Header */}
      <div className="ui-card-header">
        <div className="flex items-center gap-2">
          <div className="card-icon-badge icon-green">
            <Code size={18} />
          </div>
          <div>
            <h4 className="ui-card-title">Python Code Interpreter</h4>
            <span className="ui-card-subtitle">Isolated Sandbox Execution</span>
          </div>
        </div>
        <span className={`badge ${status === 'success' ? 'badge-success' : 'badge-error'} flex items-center gap-1 text-xs`}>
          {status === 'success' ? <Play size={11} /> : <AlertTriangle size={11} />}
          {status === 'success' ? 'Executed' : 'Execution Error'}
        </span>
      </div>

      {/* Code Box */}
      <div className="code-block-container">
        <div className="code-block-header">
          <div className="flex items-center gap-1 text-xs font-mono text-zinc-400">
            <Terminal size={12} />
            <span>Python 3.11</span>
          </div>
          <button onClick={handleCopyCode} className="copy-icon-btn" title="Copy code">
            {copiedCode ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <pre className="code-block-content font-mono">{code}</pre>
      </div>

      {/* Output Console Box */}
      <div className="output-console-container">
        <div className="output-console-header">
          <span className="text-xs font-mono text-zinc-400">Execution Output</span>
          <button onClick={handleCopyOutput} className="copy-icon-btn" title="Copy output">
            {copiedOutput ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <pre className={`output-console-content font-mono ${status === 'error' ? 'text-red-400' : 'text-zinc-200'}`}>
          {output}
        </pre>
      </div>
    </div>
  );
};

export default PythonResultCard;
