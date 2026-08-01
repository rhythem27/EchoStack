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
  ArrowRight,
  Camera,
  Monitor,
  Globe,
  Code,
  Cpu,
  Sparkles,
  Copy,
  Trash2,
  LogIn,
  LogOut,
  User
} from 'lucide-react';
import KnowledgeManager from './components/KnowledgeManager';
import FrameDeduplicator from './utils/frameDeduplicator';
import VisionOverlay from './components/VisionOverlay';
import AuthModal from './components/AuthModal';
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

// Inline AudioWorklet Processor for downsampling audio to 16kHz Int16 PCM
const WORKLET_CODE = `
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.bufferSize = 480; 
    this.buffer = new Int16Array(this.bufferSize);
    this.bufferIndex = 0;
    this.sourceIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channelData = input[0];
    const ratio = sampleRate / this.targetSampleRate;

    for (let i = 0; i < channelData.length; i++) {
      this.sourceIndex += 1;
      if (this.sourceIndex >= ratio) {
        this.sourceIndex -= ratio;

        let sample = channelData[i];
        if (sample > 1.0) sample = 1.0;
        else if (sample < -1.0) sample = -1.0;

        let intVal = Math.floor(sample * 32768);
        if (intVal > 32767) intVal = 32767;
        else if (intVal < -32768) intVal = -32768;

        this.buffer[this.bufferIndex++] = intVal;

        if (this.bufferIndex >= this.bufferSize) {
          this.port.postMessage(this.buffer.slice(0));
          this.bufferIndex = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('audio-processor', AudioProcessor);
`;

const getWorkletBlobUrl = () => {
  const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
  return URL.createObjectURL(blob);
};

function App() {
  // Connection / Config States
  const [backendUrl, setBackendUrl] = useState('http://127.0.0.1:8000');
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
  const [isKmOpen, setIsKmOpen] = useState(false);
  
  // Multimodal Vision & Tools State
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [isScreenShareActive, setIsScreenShareActive] = useState(false);
  const [activeTool, setActiveTool] = useState(null); // { name, label, status: 'running'|'completed' }

  // Authentication & User Portal State
  const [authUser, setAuthUser] = useState(() => {
    try {
      const saved = localStorage.getItem('echostack_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('echostack_token') || '');
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Live Speech Transcripts State
  const [transcripts, setTranscripts] = useState([
    { id: '1', sender: 'ai', text: 'Hello! I am EchoStack AI Assistant. Connect speech or ask me anything.', time: 'System' }
  ]);
  const [copySuccess, setCopySuccess] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('echostack_token');
    localStorage.removeItem('echostack_user');
    setAuthUser(null);
    setAuthToken('');
    addLog('Logged out of EchoStack session.', 'info');
  };

  const copyTranscriptText = () => {
    if (transcripts.length === 0) return;
    const fullText = transcripts.map(t => `[${t.sender.toUpperCase()}] ${t.text}`).join('\n');
    navigator.clipboard.writeText(fullText);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const clearTranscripts = () => {
    setTranscripts([]);
  };

  // Metrics & Visual Logs
  const [logs, setLogs] = useState([]);
  const [latency, setLatency] = useState(0);
  const [rttStart, setRttStart] = useState(null);
  
  // Audio, Video & Socket References
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const workletNodeRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const scheduledSourcesRef = useRef([]);
  const nextPlaybackTimeRef = useRef(0);

  // Vision Video Streaming & Deduplication Refs
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const videoStreamRef = useRef(null);
  const videoIntervalRef = useRef(null);
  const frameDeduplicatorRef = useRef(new FrameDeduplicator({ threshold: 0.15, forceKeyframeIntervalMs: 15000 }));
  const [visionStats, setVisionStats] = useState(null);
  const [spatialHighlights, setSpatialHighlights] = useState([]);

  // Tool display label lookup
  const TOOL_LABELS = {
    rag_knowledge_search: 'Searching Vector Knowledge...',
    web_search: 'Searching Live Web...',
    python_code_interpreter: 'Executing Python Sandbox...',
    query_user_analytics: 'Fetching User Analytics...',
    highlight_spatial_object: 'Highlighting Spatial Target...'
  };

  // Spatial Anchoring Highlight Trigger
  const triggerSpatialHighlight = (label, box_2d) => {
    const newHighlight = {
      id: `${Date.now()}-${Math.random()}`,
      label: label || 'Target Object',
      box_2d: box_2d || [0, 0, 1000, 1000],
      timestamp: Date.now()
    };
    setSpatialHighlights((prev) => [...prev, newHighlight]);
    addLog(`Spatial Anchoring: Highlighted '${newHighlight.label}' at ${JSON.stringify(newHighlight.box_2d)}`, 'info');

    setTimeout(() => {
      setSpatialHighlights((prev) => prev.filter((h) => h.id !== newHighlight.id));
    }, 5000);
  };

  // Helper video frame loop with SSIM deduplication
  const startVideoFrameLoop = (stream) => {
    if (videoIntervalRef.current) clearInterval(videoIntervalRef.current);
    if (frameDeduplicatorRef.current) frameDeduplicatorRef.current.reset();
    setVisionStats(null);

    videoIntervalRef.current = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      if (!videoRef.current || !canvasRef.current) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video.videoWidth === 0 || video.videoHeight === 0) return;

      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Evaluate frame through SSIM Deduplication filter
      const res = frameDeduplicatorRef.current.processFrame(canvas);
      setVisionStats(res.stats);

      if (res.shouldSend) {
        const b64Jpeg = canvas.toDataURL('image/jpeg', 0.6);
        wsRef.current.send(JSON.stringify({
          type: 'video_frame',
          data: b64Jpeg
        }));
        if (res.isKeyframe) {
          console.log('[Vision Deduplicator] Sent KEYFRAME to Gemini Live.');
        } else {
          console.log(`[Vision Deduplicator] Sent motion frame (diff: ${res.diff.toFixed(3)} >= threshold ${res.stats.threshold}).`);
        }
      } else {
        console.log(`[Vision Deduplicator] Skipped identical frame (diff: ${res.diff.toFixed(3)} < threshold ${res.stats.threshold}). Skip rate: ${res.stats.skipPercentage}% (${res.stats.skippedFrames}/${res.stats.totalFrames} skipped)`);
      }
    }, 1000); // 1 frame per second evaluation rate
  };

  const stopVideoStreaming = () => {
    if (videoIntervalRef.current) {
      clearInterval(videoIntervalRef.current);
      videoIntervalRef.current = null;
    }
    if (videoStreamRef.current) {
      videoStreamRef.current.getTracks().forEach(track => track.stop());
      videoStreamRef.current = null;
    }
    if (frameDeduplicatorRef.current) {
      const stats = frameDeduplicatorRef.current.getStats();
      if (stats.totalFrames > 0) {
        addLog(`Vision stream stopped. Skipped ${stats.skipPercentage}% redundant static frames (${stats.skippedFrames}/${stats.totalFrames} skipped).`, 'info');
      }
      frameDeduplicatorRef.current.reset();
    }
    setVisionStats(null);
    setIsCameraActive(false);
    setIsScreenShareActive(false);
  };

  // Helper log generator
  const addLog = (message, type = 'info') => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [{ time, message, type }, ...prev].slice(0, 100));
  };

  // 1. Fetch default fallback JWT token (00000000-0000-0000-0000-000000000000)
  const fetchToken = async () => {
    try {
      addLog('Fetching default system fallback token (00000000-0000-0000-0000-000000000000)...', 'info');
      let res;
      try {
        res = await fetch(`${backendUrl}/auth/token`);
      } catch (err) {
        const altUrl = backendUrl.includes('localhost') 
          ? backendUrl.replace('localhost', '127.0.0.1') 
          : 'http://localhost:8000';
        addLog(`Primary endpoint unreachable. Trying fallback: ${altUrl}...`, 'warning');
        res = await fetch(`${altUrl}/auth/token`);
        setBackendUrl(altUrl);
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAuthToken(data.token);
      
      // Decode JWT payload locally to extract roles/permissions
      const payloadBase64 = data.token.split('.')[1];
      const payloadDecoded = JSON.parse(window.atob(payloadBase64));
      addLog(`Default fallback token loaded. User UUID: ${payloadDecoded.user_id}`, 'info');

      setPermissions({
        can_access_admin_tools: true,
        can_query_analytics: true,
        can_write_knowledge: true,
        can_chat_live: true
      });
      return data.token;
    } catch (e) {
      addLog(`Failed to fetch default auth token from ${backendUrl}: ${e.message}. Ensure backend server is running.`, 'error');
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
    if (activeTab === 'documents' || isKmOpen) {
      fetchDocuments();
      const interval = setInterval(fetchDocuments, 4000);
      return () => clearInterval(interval);
    }
  }, [activeTab, isKmOpen, backendUrl]);

  // Load documents list on start
  useEffect(() => {
    fetchDocuments();
  }, [backendUrl]);

  // 3. Document Upload (Multi-Format RAG ingestion)
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const allowed = ['.pdf', '.docx', '.txt', '.csv', '.md', '.pptx'];
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!allowed.includes(ext)) {
      setUploadStatus({ type: 'error', text: `Unsupported file format. Allowed: ${allowed.join(', ')}` });
      return;
    }

    setUploading(true);
    setUploadStatus({ type: 'info', text: `Uploading and registering ${file.name}...` });
    addLog(`Initiating RAG document ingestion for ${file.name}`, 'info');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', authUser?.id || '00000000-0000-0000-0000-000000000000');

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
    if (sessionState === 'connecting' || sessionState === 'connected') return;

    setSessionState('connecting');
    addLog('Starting speech session sequence...', 'info');
    
    let stream = null;
    try {
      // 1. Request microphone access first
      addLog('Requesting microphone access...', 'info');
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1
        }
      });
      mediaStreamRef.current = stream;
    } catch (micErr) {
      addLog(`Microphone access failed: ${micErr.message}. Please allow microphone permission in your browser address bar.`, 'error');
      setSessionState('error');
      return;
    }

    let activeToken = authToken;
    try {
      if (!activeToken) {
        addLog('No account logged in. Using default fallback system token (00000000-0000-0000-0000-000000000000)...', 'info');
        activeToken = await fetchToken();
      } else {
        try {
          const payloadBase64 = activeToken.split('.')[1];
          const payloadDecoded = JSON.parse(window.atob(payloadBase64));
          addLog(`Authenticated with logged-in account (@${authUser?.username || 'user'}). User UUID: ${payloadDecoded.user_id}`, 'info');
        } catch (err) {
          addLog('Authenticated with active user session token.', 'info');
        }
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

          // Register and initialize the downsampler Worklet script
          addLog('Registering AudioWorklet script...', 'info');
          try {
            const workletUrl = new URL('/audio-processor.js', window.location.origin).href;
            await audioCtx.audioWorklet.addModule(workletUrl);
          } catch (workletErr) {
            addLog(`AudioWorklet URL load fallback triggered: ${workletErr.message}`, 'warning');
            const blobUrl = getWorkletBlobUrl();
            await audioCtx.audioWorklet.addModule(blobUrl);
          }

          if (audioCtx.state === 'closed') {
            addLog('AudioContext closed prior to Worklet initialization.', 'warning');
            return;
          }

          const workletNode = new AudioWorkletNode(audioCtx, 'audio-processor');
          workletNodeRef.current = workletNode;

          const source = audioCtx.createMediaStreamSource(stream);
          source.connect(workletNode);
          
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
              
              if (!rttStart) {
                setRttStart(performance.now());
              }
            }
          };

          addLog('Microphone streaming active (Task A started).', 'info');
        } catch (audioErr) {
          addLog(`Audio Context setup failed: ${audioErr.message}`, 'error');
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
        else if (msg.type === 'spatial_highlight') {
          triggerSpatialHighlight(msg.label, msg.box_2d);
        }
        else if (msg.type === 'tool_call') {
          const label = TOOL_LABELS[msg.tool_name] || `Executing ${msg.tool_name}...`;
          setActiveTool({ name: msg.tool_name, label, args: msg.args, status: 'running' });
          addLog(`Tool call initiated: [${msg.tool_name}] with args ${JSON.stringify(msg.args)}`, 'info');
          if (msg.tool_name === 'highlight_spatial_object' && msg.args) {
            triggerSpatialHighlight(msg.args.label, msg.args.box_2d);
          }
        }
        else if (msg.type === 'tool_result') {
          setActiveTool((prev) => prev ? { ...prev, status: 'completed' } : null);
          const snippet = msg.result ? (typeof msg.result === 'string' ? msg.result.slice(0, 120) : JSON.stringify(msg.result).slice(0, 120)) : '';
          addLog(`Tool [${msg.tool_name}] finished. Output snippet: ${snippet}...`, 'info');
          setTimeout(() => {
            setActiveTool(null);
          }, 3500);
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

  const toggleCamera = async () => {
    if (isCameraActive) {
      stopVideoStreaming();
      addLog('Camera streaming stopped.', 'info');
      return;
    }

    try {
      if (isScreenShareActive) stopVideoStreaming();
      
      addLog('Requesting webcam access...', 'info');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { max: 5 } }
      });
      videoStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsCameraActive(true);
      startVideoFrameLoop(stream);
      addLog('Camera streaming active (1 frame/sec).', 'info');
    } catch (err) {
      addLog(`Failed to start camera: ${err.message}`, 'error');
    }
  };

  const toggleScreenShare = async () => {
    if (isScreenShareActive) {
      stopVideoStreaming();
      addLog('Screen sharing stopped.', 'info');
      return;
    }

    try {
      if (isCameraActive) stopVideoStreaming();

      addLog('Requesting screen capture stream...', 'info');
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { max: 5 } }
      });
      videoStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      stream.getVideoTracks()[0].onended = () => {
        stopVideoStreaming();
        addLog('Screen share stopped by user.', 'info');
      };

      setIsScreenShareActive(true);
      startVideoFrameLoop(stream);
      addLog('Screen capture streaming active (1 frame/sec).', 'info');
    } catch (err) {
      addLog(`Failed to start screen share: ${err.message}`, 'error');
    }
  };

  const stopAudioSession = () => {
    stopVideoStreaming();
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

        <div className="flex items-center gap-3">
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

          {/* Authentication & User Badge */}
          {authUser ? (
            <div className="user-identity-badge">
              <div className="user-avatar-circle">
                {(authUser.full_name || authUser.username || 'U')[0].toUpperCase()}
              </div>
              <div className="user-identity-info">
                <span className="user-identity-name">{authUser.full_name || authUser.username}</span>
                <span className="user-identity-username">@{authUser.username}</span>
              </div>
              <span className={`user-role-pill user-role-${authUser.role_name}`}>
                {authUser.role_name}
              </span>
              <button 
                onClick={handleLogout} 
                className="header-logout-btn flex items-center gap-1"
                title="Sign Out"
              >
                <LogOut size={14} />
                <span>Logout</span>
              </button>
            </div>
          ) : (
            <button 
              onClick={() => setIsAuthOpen(true)} 
              className="btn btn-primary text-xs py-half px-3 flex items-center gap-1"
              style={{ fontSize: '0.82rem', padding: '0.4rem 0.85rem' }}
            >
              <LogIn size={15} />
              <span>Sign In / Register</span>
            </button>
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
                id="doc-uploader" 
                accept=".pdf,.docx,.txt,.csv,.md,.pptx" 
                onChange={handleFileUpload} 
                className="hidden-input" 
                disabled={uploading}
              />
              <label htmlFor="doc-uploader" className="upload-label">
                <FileUp size={36} className="upload-icon-pulse" />
                <span>Drag or click to upload Document</span>
                <span className="file-desc">Supports .pdf, .docx, .txt, .csv, .md, .pptx</span>
              </label>
            </div>

            {uploadStatus && (
              <div className={`status-banner ${uploadStatus.type === 'error' ? 'banner-error' : 'banner-info'}`}>
                {uploadStatus.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
                <p>{uploadStatus.text}</p>
              </div>
            )}

            <div className="document-list-container">
              <div className="flex items-center justify-between mb-2">
                <h3>Indexed System Files</h3>
                <button 
                  onClick={() => setIsKmOpen(true)}
                  className="btn btn-secondary py-half px-2 text-xs flex items-center gap-1"
                  style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
                >
                  <Database size={13} /> Manage KB
                </button>
              </div>

              {documents.length === 0 ? (
                <div className="list-empty">No documents found. Upload a file to start RAG.</div>
              ) : (
                <ul className="doc-list">
                  {documents.map((doc) => (
                    <li key={doc.id} className="doc-item" onClick={() => setIsKmOpen(true)} style={{ cursor: 'pointer' }}>
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

          {/* Hidden video and canvas elements for frame extraction */}
          <video ref={videoRef} autoPlay playsInline muted style={{ display: 'none' }} />
          <canvas ref={canvasRef} style={{ display: 'none' }} />

          {/* Active Video Feed Preview Tile */}
          {(isCameraActive || isScreenShareActive) && (
            <div className="video-preview-tile glass-card">
              <div className="video-preview-header">
                <span className="badge badge-success flex items-center gap-1">
                  <span className="ping-dot"></span>
                  {isCameraActive ? 'Webcam Stream Active' : 'Screen Capture Active'}
                </span>
                <span className="text-xs font-mono text-zinc-400">1 FPS JPEG Input</span>
              </div>
              <div className="video-viewport">
                <video 
                  ref={(el) => {
                    if (el && videoStreamRef.current) el.srcObject = videoStreamRef.current;
                  }} 
                  autoPlay 
                  playsInline 
                  muted 
                />
                <VisionOverlay highlights={spatialHighlights} />
              </div>
            </div>
          )}

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

            {/* Live Tool Execution Animated Badge */}
            {activeTool && (
              <div className={`tool-execution-badge status-${activeTool.status}`}>
                <Cpu size={16} className="icon-pulse text-purple-400" />
                <span className="tool-label">{activeTool.label}</span>
                <span className="tool-dot"></span>
              </div>
            )}
            
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

          {/* User Session & Multimodal Vision Controllers */}
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
              <div className="controls-stack">
                {/* Top Row: Camera & Screen Share */}
                <div className="btn-group">
                  <button 
                    onClick={toggleCamera} 
                    className={`btn ${isCameraActive ? 'btn-danger' : 'btn-secondary'}`}
                  >
                    <Camera size={18} /> {isCameraActive ? 'Stop Camera' : 'Camera Share'}
                  </button>
                  <button 
                    onClick={toggleScreenShare} 
                    className={`btn ${isScreenShareActive ? 'btn-danger' : 'btn-secondary'}`}
                  >
                    <Monitor size={18} /> {isScreenShareActive ? 'Stop Screen' : 'Screen Share'}
                  </button>
                </div>

                {/* Bottom Row: Mute & Call Cut (Stop Session) */}
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
              </div>
            )}
          </div>

          {/* Live Speech Transcript UI Panel */}
          <div className="speech-transcript-panel glass-card">
            <div className="speech-transcript-header">
              <div className="speech-transcript-title">
                <FileText size={16} className="text-purple-400" />
                <span>Live Audio Transcript</span>
              </div>
              <div className="speech-transcript-actions">
                <button 
                  onClick={copyTranscriptText} 
                  className="transcript-btn"
                  title="Copy transcript to clipboard"
                >
                  <Copy size={13} />
                  <span>{copySuccess ? 'Copied!' : 'Copy'}</span>
                </button>
                <button 
                  onClick={clearTranscripts} 
                  className="transcript-btn"
                  title="Clear transcript history"
                >
                  <Trash2 size={13} />
                  <span>Clear</span>
                </button>
              </div>
            </div>

            <div className="speech-transcript-list">
              {transcripts.length === 0 ? (
                <div className="transcript-empty">
                  No transcripts recorded yet. Start live speech session to stream audio conversation.
                </div>
              ) : (
                transcripts.map((t) => (
                  <div 
                    key={t.id} 
                    className={`transcript-bubble transcript-bubble-${t.sender === 'user' ? 'user' : 'ai'}`}
                  >
                    {t.text}
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Right column: Observability Logs & System Telemetry */}
        <section className="portal-column glass-card">
          <div className="column-header">
            <Shield size={20} className="header-icon-green" />
            <h2>Security & Telemetry</h2>
          </div>

          <div className="card-body telemetry-card">
            
            {/* Micro panel showing JWT RBAC Permissions & Super Admin Status */}
            <div className="telemetry-section">
              <div className="flex items-center justify-between mb-2">
                <h3>Secure Identity & Token Roles</h3>
                <span className="badge badge-success text-xs" style={{ background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.4)' }}>
                  Role ID: 0 (Super Admin)
                </span>
              </div>
              <div className="permissions-badge-grid">
                <div className="badge-item">
                  <span className="badge-dot dot-success"></span>
                  <span>Super Admin Master Control</span>
                </div>
                <div className="badge-item">
                  <span className="badge-dot dot-success"></span>
                  <span>PUT /admin/users/:id/role</span>
                </div>
                <div className="badge-item">
                  <span className="badge-dot dot-success"></span>
                  <span>Redis Instant Cache Purge</span>
                </div>
                <div className="badge-item">
                  <span className="badge-dot dot-success"></span>
                  <span>Full Analytics & RAG Access</span>
                </div>
              </div>
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
                  <span className="metric-label">Vision SSIM Filter</span>
                  <span className="metric-value font-mono text-green">
                    {visionStats ? `Skipped ${visionStats.skipPercentage}%` : 'Threshold 0.15'}
                  </span>
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

      {/* Knowledge Base Explorer Modal */}
      <KnowledgeManager 
        backendUrl={backendUrl} 
        isOpen={isKmOpen} 
        onClose={() => setIsKmOpen(false)} 
        onRefresh={fetchDocuments}
      />

      {/* Auth & Identity Modal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onAuthSuccess={(user, token) => {
          setAuthUser(user);
          setAuthToken(token);
          addLog(`Authenticated as ${user.full_name || user.username} (@${user.username}).`, 'info');
        }}
      />
    </div>
  );
}

export default App;
