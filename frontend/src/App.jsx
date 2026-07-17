import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Database,
  Shield,
  FileUp,
  FileText,
  RefreshCw,
  Play,
  Square,
  Activity,
  CheckCircle2,
  AlertCircle,
  ArrowRight
} from 'lucide-react';
import './App.css';

// Converts Float32 audio samples back into 16-bit PCM arrays
const float32ToInt16PCM = (float32Array) => {
  const int16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    let sample = float32Array[i];
    if (sample > 1.0) sample = 1.0;
    else if (sample < -1.0) sample = -1.0;
    int16[i] = Math.floor(sample * 32768);
  }
  return int16;
};

// Converts base64 encoded raw 24kHz Int16 PCM audio into Float32Array for AudioContext
const base64ToFloat32Array = (base64Str) => {
  const binaryString = window.atob(base64Str);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  const int16PCM = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(int16PCM.length);
  for (let i = 0; i < int16PCM.length; i++) {
    float32[i] = int16PCM[i] / 32768.0;
  }
  return float32;
};

// Converts Int16 PCM ArrayBuffer back to base64 for transmission
const int16BufferToBase64 = (buffer) => {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
};

function App() {
  // Connection / Config States
  const [backendUrl, setBackendUrl] = useState('http://localhost:8000');
  const [token, setToken] = useState('');
  const [permissions, setPermissions] = useState(null);
  
  // Dashboard Statuses
  const [sessionState, setSessionState] = useState('disconnected'); // disconnected, connecting, connected, error
  const [agentState, setAgentState] = useState('idle'); // idle, listening (user talking), speaking (agent speaking)
  const [isMuted, setIsMuted] = useState(false);
  const [activeTab, setActiveTab] = useState('agent'); // agent, documents, logs

  // RAG & Document Management
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  
  // Metrics & Visual Logs
  const [logs, setLogs] = useState([]);
  const [latency, setLatency] = useState(0);
  const [rttStart, setRttStart] = useState(null);
  
  // Audio & Socket References
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const workletNodeRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const scheduledSourcesRef = useRef([]);
  const nextPlaybackTimeRef = useRef(0);

  // Helper log generator
  const addLog = (message, type = 'info') => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [{ time, message, type }, ...prev].slice(0, 100));
  };

  // 1. Fetch JWT token & verify permissions
  const fetchToken = async () => {
    try {
      addLog('Fetching authentication token from backend...', 'info');
      const res = await fetch(`${backendUrl}/auth/token`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setToken(data.token);
      
      // Decode JWT payload locally to extract roles/permissions
      const payloadBase64 = data.token.split('.')[1];
      const payloadDecoded = JSON.parse(window.atob(payloadBase64));
      addLog(`Authenticated successfully. User UUID: ${payloadDecoded.user_id}`, 'info');

      // Query permissions mapping using dummy fetch or simulated endpoint (permissions cached in redis)
      // Since it's development, we'll populate state
      setPermissions({
        can_access_admin_tools: true,
        can_query_analytics: true,
        can_write_knowledge: true,
        can_chat_live: true
      });
      return data.token;
    } catch (e) {
      addLog(`Failed to fetch debug auth token: ${e.message}`, 'error');
      setSessionState('error');
      throw e;
    }
  };

  // 2. Fetch Document List
  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${backendUrl}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (e) {
      console.error("Failed to fetch documents", e);
    }
  };

  // Poll for document updates when active
  useEffect(() => {
    if (activeTab === 'documents') {
      fetchDocuments();
      const interval = setInterval(fetchDocuments, 4000);
      return () => clearInterval(interval);
    }
  }, [activeTab, backendUrl]);

  // Load documents list on start
  useEffect(() => {
    fetchDocuments();
  }, [backendUrl]);

  // 3. Document Upload (PDF RAG ingestion)
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.name.endsWith('.pdf')) {
      setUploadStatus({ type: 'error', text: 'Only PDF documents are supported.' });
      return;
    }

    setUploading(true);
    setUploadStatus({ type: 'info', text: `Uploading and registering ${file.name}...` });
    addLog(`Initiating RAG document ingestion for ${file.name}`, 'info');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', '00000000-0000-0000-0000-000000000000'); // Seed admin user

    try {
      const res = await fetch(`${backendUrl}/upload-document`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setUploadStatus({ type: 'success', text: `Document submitted! ID: ${data.document_id}` });
      addLog(`RAG job accepted. Ingestion status: ${data.status}`, 'info');
      fetchDocuments();
    } catch (err) {
      setUploadStatus({ type: 'error', text: `Upload failed: ${err.message}` });
      addLog(`Failed to upload document: ${err.message}`, 'error');
    } finally {
      setUploading(false);
    }
  };

  // 4. Playback Queue Flusher (Barge-In)
  const flushPlaybackQueue = () => {
    addLog('Interruption (VAD Barge-In) detected: Flushing playback queue', 'info');
    scheduledSourcesRef.current.forEach(({ source }) => {
      try {
        source.stop();
      } catch (e) {
        // Source may have already finished playing
      }
    });
    scheduledSourcesRef.current = [];
    nextPlaybackTimeRef.current = 0;
    setAgentState('listening');
  };

  // 5. Stream Incoming Chunks to AudioContext (Task B helper)
  const playIncomingAudioChunk = (float32Array) => {
    if (!audioContextRef.current) return;
    const ctx = audioContextRef.current;
    
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    // Creating mono buffer at 24kHz (Gemini Live Audio Output Spec)
    const audioBuffer = ctx.createBuffer(1, float32Array.length, 24000);
    audioBuffer.copyToChannel(float32Array, 0);

    const sourceNode = ctx.createBufferSource();
    sourceNode.buffer = audioBuffer;
    sourceNode.connect(ctx.destination);

    // Adaptive queue scheduling
    const currentTime = ctx.currentTime;
    let startTime = nextPlaybackTimeRef.current;

    // If scheduled time is behind current time (queue empty/underrun), catch up
    if (startTime < currentTime) {
      // 50ms safety offset to avoid clipping
      startTime = currentTime + 0.05; 
    }

    sourceNode.start(startTime);
    nextPlaybackTimeRef.current = startTime + audioBuffer.duration;

    // Track for barge-in stop capability
    const item = { source: sourceNode, endTime: nextPlaybackTimeRef.current };
    scheduledSourcesRef.current.push(item);

    sourceNode.onended = () => {
      scheduledSourcesRef.current = scheduledSourcesRef.current.filter(i => i !== item);
      if (scheduledSourcesRef.current.length === 0) {
        setAgentState('idle');
      }
    };

    setAgentState('speaking');
  };

  // 6. Connect WebSocket and start Speech Session
  const startAudioSession = async () => {
    setSessionState('connecting');
    addLog('Starting speech session sequence...', 'info');
    
    let activeToken = token;
    try {
      if (!activeToken) {
        activeToken = await fetchToken();
      }
      
      // Establish WebSocket
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = backendUrl.replace(/^https?:\/\//, '');
      const wsUrl = `${wsProtocol}//${wsHost}/ws/speech?token=${activeToken}`;
      
      addLog(`Connecting to secure speech WebSocket proxy...`, 'info');
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        addLog('WebSocket connection established. Starting Audio Context...', 'info');
        setSessionState('connected');

        try {
          // Initialize Audio Context for Audio Worklet
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          audioContextRef.current = audioCtx;
          
          // Request mic stream (Task A initialization)
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              channelCount: 1
            }
          });
          mediaStreamRef.current = stream;

          // Register and initialize the downsampler Worklet script
          addLog('Registering AudioWorklet script...', 'info');
          await audioCtx.audioWorklet.addModule('/audio-processor.js');

          const workletNode = new AudioWorkletNode(audioCtx, 'audio-processor');
          workletNodeRef.current = workletNode;

          const source = audioCtx.createMediaStreamSource(stream);
          source.connect(workletNode);
          
          // NOTE: Do not connect workletNode to audioCtx.destination, 
          // as we want to transmit the microphone stream, not echo it back.

          // Listen to worklet output (downsampled Int16 array buffers)
          workletNode.port.onmessage = (event) => {
            if (isMuted) return;
            const int16PCM = event.data; // Int16Array from worklet (480 samples, 30ms)

            // Convert to Base64
            const b64Audio = int16BufferToBase64(int16PCM.buffer);

            // Send payload to backend WebSocket
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({
                type: 'audio_chunk',
                data: b64Audio
              }));
              
              // Record timestamp for simple round-trip latency checks
              if (!rttStart) {
                setRttStart(performance.now());
              }
            }
          };

          addLog('Microphone streaming active (Task A started).', 'info');
        } catch (audioErr) {
          addLog(`Audio Context/Microphone setup failed: ${audioErr.message}`, 'error');
          stopAudioSession();
        }
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        // Task B: Receive responses
        if (msg.type === 'audio_chunk') {
          // Calculate simple latency metrics
          if (rttStart) {
            const timeDiff = Math.round(performance.now() - rttStart);
            setLatency(timeDiff);
            setRttStart(null); // Reset for next measurement
          }

          // Decode base64 24kHz Int16 to Float32 AudioBuffer
          const float32Audio = base64ToFloat32Array(msg.data);
          
          // Stream block to AudioContext
          playIncomingAudioChunk(float32Audio);
        } 
        else if (msg.type === 'interrupted') {
          // Barge-in Interruption Signal from VAD
          flushPlaybackQueue();
        }
      };

      ws.onclose = () => {
        addLog('Speech session WebSocket closed.', 'info');
        stopAudioSession();
      };

      ws.onerror = (err) => {
        addLog(`WebSocket connection error`, 'error');
        setSessionState('error');
      };

    } catch (err) {
      addLog(`Failed to start session: ${err.message}`, 'error');
      setSessionState('error');
    }
  };

  const stopAudioSession = () => {
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    // Stop mic tracks
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    // Close Worklet
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    // Close Audio Context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    flushPlaybackQueue();
    setSessionState('disconnected');
    setAgentState('idle');
    addLog('Live speech session stopped.', 'info');
  };

  // Toggle mic stream mute state
  const toggleMute = () => {
    setIsMuted(!isMuted);
    addLog(`Microphone ${!isMuted ? 'muted' : 'unmuted'}`, 'info');
  };

  return (
    <div className="app-container">
      {/* Background glowing gradients */}
      <div className="bg-glow bg-glow-purple"></div>
      <div className="bg-glow bg-glow-blue"></div>

      {/* Header bar */}
      <header className="main-header glass-card">
        <div className="logo-group">
          <div className="logo-icon">
            <Activity className="icon-pulse" size={24} />
          </div>
          <h1>EchoStack <span className="gradient-text font-light">Live Portal</span></h1>
        </div>
        <div className="connection-status">
          {sessionState === 'connected' && (
            <span className="badge badge-success">
              <span className="ping-dot"></span> Secure Speech Active
            </span>
          )}
          {sessionState === 'connecting' && (
            <span className="badge badge-warning">Connecting...</span>
          )}
          {sessionState === 'disconnected' && (
            <span className="badge badge-idle">Ready</span>
          )}
          {sessionState === 'error' && (
            <span className="badge badge-error">Connection Error</span>
          )}
        </div>
      </header>

      {/* Main Grid Content */}
      <div className="portal-grid">
        
        {/* Left column: Configuration and RAG Knowledge Base */}
        <section className="portal-column glass-card">
          <div className="column-header">
            <Database size={20} className="header-icon-blue" />
            <h2>Document Ingestion (RAG)</h2>
          </div>
          
          <div className="card-body">
            <div className="form-group">
              <label>Gateway Endpoint</label>
              <input 
                type="text" 
                value={backendUrl} 
                onChange={(e) => setBackendUrl(e.target.value)} 
                disabled={sessionState === 'connected'} 
                className="text-input"
              />
            </div>

            <div className="drag-upload-zone">
              <input 
                type="file" 
                id="pdf-uploader" 
                accept=".pdf" 
                onChange={handleFileUpload} 
                className="hidden-input" 
                disabled={uploading}
              />
              <label htmlFor="pdf-uploader" className="upload-label">
                <FileUp size={36} className="upload-icon-pulse" />
                <span>Drag or click to upload PDF</span>
                <span className="file-desc">Requires .pdf format</span>
              </label>
            </div>

            {uploadStatus && (
              <div className={`status-banner ${uploadStatus.type === 'error' ? 'banner-error' : 'banner-info'}`}>
                {uploadStatus.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
                <p>{uploadStatus.text}</p>
              </div>
            )}

            <div className="document-list-container">
              <h3>Indexed System Files</h3>
              {documents.length === 0 ? (
                <div className="list-empty">No documents found. Upload a PDF to start RAG.</div>
              ) : (
                <ul className="doc-list">
                  {documents.map((doc) => (
                    <li key={doc.id} className="doc-item">
                      <FileText size={18} className="doc-icon" />
                      <div className="doc-details">
                        <span className="doc-name">{doc.file_name}</span>
                        <span className={`doc-status status-${doc.status.toLowerCase()}`}>{doc.status}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>

        {/* Center column: Speech Agent Controller & Active Visualizer */}
        <section className="portal-column flex-center glass-card main-agent-card">
          <div className="column-header">
            <Activity size={20} className="header-icon-purple" />
            <h2>Live Speech-to-Speech</h2>
          </div>

          <div className="visualizer-container">
            {/* Morphing glow ring base on Agent state */}
            <div className={`agent-orb state-${agentState} session-${sessionState}`}>
              {sessionState === 'connected' ? (
                <div className="orb-inner">
                  {agentState === 'speaking' && <Volume2 size={48} className="icon-state" />}
                  {agentState === 'listening' && <Mic size={48} className="icon-state" />}
                  {agentState === 'idle' && <Activity size={48} className="icon-state text-blue" />}
                </div>
              ) : (
                <div className="orb-inner">
                  <Play size={48} className="icon-state text-zinc-500" />
                </div>
              )}
              
              {/* Radial animated ripples for speaking and listening */}
              {agentState === 'speaking' && (
                <>
                  <div className="ripple ripple-1 border-blue"></div>
                  <div className="ripple ripple-2 border-blue"></div>
                </>
              )}
              {agentState === 'listening' && (
                <>
                  <div className="ripple ripple-1 border-pink"></div>
                  <div className="ripple ripple-2 border-pink"></div>
                </>
              )}
            </div>
            
            <div className="state-descriptor">
              {sessionState === 'connected' ? (
                <>
                  <span className="state-title capitalize">{agentState}</span>
                  <span className="state-subtitle">
                    {agentState === 'speaking' && 'Gemini is replying...'}
                    {agentState === 'listening' && 'Listening to your microphone...'}
                    {agentState === 'idle' && 'Waiting for you to speak'}
                  </span>
                </>
              ) : (
                <>
                  <span className="state-title">Agent Offline</span>
                  <span className="state-subtitle">Establish a secure session to start</span>
                </>
              )}
            </div>
          </div>

          {/* User Session Controller */}
          <div className="controls-container">
            {sessionState !== 'connected' ? (
              <button 
                onClick={startAudioSession} 
                disabled={sessionState === 'connecting'} 
                className="btn btn-primary"
              >
                {sessionState === 'connecting' ? 'Establishing Pipeline...' : 'Start Live Session'}
              </button>
            ) : (
              <div className="btn-group">
                <button 
                  onClick={toggleMute} 
                  className={`btn ${isMuted ? 'btn-danger' : 'btn-secondary'}`}
                >
                  {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
                  {isMuted ? 'Muted' : 'Mute'}
                </button>
                <button onClick={stopAudioSession} className="btn btn-danger">
                  <Square size={18} /> Stop Session
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Right column: Observability Logs & System Telemetry */}
        <section className="portal-column glass-card">
          <div className="column-header">
            <Shield size={20} className="header-icon-green" />
            <h2>Security & Telemetry</h2>
          </div>

          <div className="card-body telemetry-card">
            
            {/* Micro panel showing JWT RBAC Permissions */}
            <div className="telemetry-section">
              <h3>Secure Identity & Token Roles</h3>
              {permissions ? (
                <div className="permissions-badge-grid">
                  <div className="badge-item">
                    <span className="badge-dot dot-success"></span>
                    <span>Admin Tools Allowed</span>
                  </div>
                  <div className="badge-item">
                    <span className="badge-dot dot-success"></span>
                    <span>Analytics Queries Checked</span>
                  </div>
                  <div className="badge-item">
                    <span className="badge-dot dot-success"></span>
                    <span>RAG Document Indexing</span>
                  </div>
                  <div className="badge-item">
                    <span className="badge-dot dot-success"></span>
                    <span>Gemini Speech Proxy</span>
                  </div>
                </div>
              ) : (
                <div className="telemetry-empty">Unauthenticated. Establish session to load JWT payload.</div>
              )}
            </div>

            {/* Micro panel showing Pipeline details */}
            <div className="telemetry-section border-t pt-4">
              <h3>Telemetry Metrics</h3>
              <div className="metrics-grid">
                <div className="metric-box">
                  <span className="metric-label">Input Audio</span>
                  <span className="metric-value font-mono">16kHz Int16</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">Output Audio</span>
                  <span className="metric-value font-mono">24kHz Int16</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">VAD Interrupter</span>
                  <span className="metric-value text-pink font-semibold">Barge-in On</span>
                </div>
                <div className="metric-box">
                  <span className="metric-label">Latencies (RTT)</span>
                  <span className="metric-value font-mono text-green">{latency ? `${latency}ms` : '0ms'}</span>
                </div>
              </div>
            </div>

            {/* DB Tools mapping */}
            <div className="telemetry-section border-t pt-4">
              <h3>LangChain Tool Priority Rules</h3>
              <div className="tools-priority-list">
                <div className="tool-priority-item">
                  <span className="tool-name">rag_knowledge_search</span>
                  <span className="badge badge-error py-half">INTERRUPT</span>
                </div>
                <div className="tool-priority-item">
                  <span className="tool-name">query_user_analytics</span>
                  <span className="badge badge-warning py-half">WHEN_IDLE</span>
                </div>
              </div>
            </div>

            {/* Visual raw websocket activity log */}
            <div className="telemetry-section border-t pt-4 flex-grow flex flex-col min-h-0">
              <h3>Stream Activity Logger</h3>
              <div className="log-panel">
                {logs.length === 0 ? (
                  <div className="log-empty">No connection activity. Logs will show when session starts.</div>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className={`log-row type-${log.type}`}>
                      <span className="log-time">[{log.time}]</span>
                      <span className="log-message">{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        </section>

      </div>
    </div>
  );
}

export default App;
