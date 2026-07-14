# System Control & Data Flows

This document details the step-by-step sequencing for critical workloads in the dual-system agentic architecture.

---

## 1. Asynchronous Document Ingestion Flow

The document ingestion workflow handles large PDF, OCR, and table extractions asynchronously, decoupling client requests via Kafka and RAGFlow.

```mermaid
sequenceDiagram
    autonumber
    actor User as React Client
    participant API as FastAPI Ingress
    participant DB as PostgreSQL
    participant Broker as Kafka Broker (Topic: document.ingestion.events)
    participant Worker as Kafka Consumer Worker
    participant RAG as RAGFlow Engine
    
    User->>API: HTTP POST /v1/documents (file upload)
    Note over API: 1. Validate file format<br/>2. Save file temporarily
    API->>DB: INSERT INTO documents (file_name, status='PENDING') RETURNING id
    DB-->>API: returns doc_id
    
    API->>Broker: Publish JSON event (doc_id, user_id, temp_file_path)
    Broker-->>API: Acknowledge Publish
    
    API-->>User: HTTP 202 Accepted (doc_id, status='PENDING')
    
    Note over Worker: Consumer reads event<br/>from topic queue
    Broker->>Worker: Consume JSON Ingestion Event
    Worker->>DB: UPDATE documents SET status='PROCESSING' WHERE id = doc_id
    
    Worker->>RAG: ragflow_sdk.dataset.upload(temp_file_path, parser_config)
    Note over RAG: DeepDoc Layout OCR<br/>& Semantic Chunking
    RAG-->>Worker: Return array of text chunks & tables
    
    Note over Worker: Generate embeddings via text-embedding-3-large
    Worker->>DB: INSERT INTO vector_knowledge (doc_id, chunk_text, embedding)
    Worker->>DB: UPDATE documents SET status='COMPLETE' WHERE id = doc_id
```

### Event Payload Example (Kafka Topic: `document.ingestion.events`)
```json
{
  "event_id": "8fa1119b-c40d-4001-a20d-dcd6b60e657c",
  "timestamp": "2026-07-14T18:05:00Z",
  "user_id": "c13886b4-f6b7-4c4f-9dbb-8ccdc678cb2d",
  "doc_id": "a98cc8b4-023a-4a6c-9c09-cdab900a892b",
  "file_path": "/tmp/uploads/quarterly_report_2026.pdf",
  "parser_config": {
    "chunk_token_num": 512,
    "layout_recognize": true,
    "chunk_method": "naive"
  }
}
```

---

## 2. Real-Time Speech-to-Speech Flow

System 2 avoids cascading STT/TTS models by proxying a raw PCM stream from the browser through FastAPI to Gemini 3.1 Flash Live.

```mermaid
sequenceDiagram
    autonumber
    actor Browser as React (AudioWorklet)
    participant Proxy as FastAPI WS Proxy
    participant Redis as Redis Cache
    participant Gemini as Gemini Live API (WebSocket)
    
    Browser->>Proxy: wss://api.domain.com/ws/speech?token=JWT
    Note over Proxy: Validate JWT & check user role permissions
    Proxy->>Redis: Get permissions and user profile
    Redis-->>Proxy: user_id, role (premium), preferences
    
    Proxy->>Gemini: Establish WebSocket via google-genai SDK (aio.live.connect)
    Gemini-->>Proxy: WebSocket Open & Config Acknowledged
    Proxy-->>Browser: Connection Established
    
    par Async Loop 1: Microphone Stream
        loop Every 20-50ms
            Browser->>Proxy: Binary Frame: Base64 Encoded Int16 PCM (16kHz)
            Proxy->>Gemini: send_realtime_input (Raw Audio Bytes)
        end
    and Async Loop 2: AI Speaker Stream
        loop AI Response Generator
            Gemini->>Proxy: Server Content Frame (PCM Audio 24kHz)
            Proxy->>Browser: Binary Frame (Base64 PCM)
            Note over Browser: Adaptive Audio Buffer Queue plays PCM
        end
    end
```

---

## 3. Real-Time Asynchronous Tool Calling Flow

When the user asks for data stored in PostgreSQL or documents processed by RAGFlow, the Gemini model initiates a mid-stream tool execution request.

```mermaid
sequenceDiagram
    autonumber
    participant Gemini as Gemini Live API (WebSocket)
    participant Proxy as FastAPI WS Proxy
    participant DB as PostgreSQL (pgvector / user_analytics)
    
    Gemini->>Proxy: WebSocket Event: tool_call (function_name, arguments)
    Note over Proxy: Intercept and enforce RBAC permission matching
    
    alt User has permissions
        Proxy->>DB: Execute LangChain Tool Query (e.g. user_analytics)
        DB-->>Proxy: Return JSON Tool Data
        Proxy->>Gemini: session.send_tool_response(FunctionResponse, scheduling="INTERRUPT")
    else User lacks permissions
        Proxy->>Gemini: session.send_tool_response(FunctionResponse="Authorization Denied", scheduling="WHEN_IDLE")
    end
    
    Note over Gemini: Incorporate tool response<br/>and synthesize voice response
    Gemini->>Proxy: Server Content Frame (PCM Audio 24kHz)
    Proxy->>Browser: Binary Frame (Base64 PCM)
```

---

## 4. Speech Interruption & Barge-In Mechanics

A fluid voice interface must support sudden interruptions. The system utilizes Gemini's Server-Side Voice Activity Detection (VAD) to interrupt AI generation instantly.

```mermaid
sequenceDiagram
    autonumber
    actor Browser as React (AudioWorklet)
    participant Proxy as FastAPI WS Proxy
    participant Gemini as Gemini Live API (WebSocket)
    
    Note over Gemini: Gemini is streaming AI audio output
    Gemini->>Proxy: Server Content Frame (PCM Audio 24kHz)
    Proxy->>Browser: Play PCM audio to user
    
    User->>Browser: Speaks ("Wait, what was that index size?")
    Browser->>Proxy: Sends new PCM audio chunk (16kHz)
    Proxy->>Gemini: Forward audio bytes (send_realtime_input)
    
    Note over Gemini: Server-Side VAD detects user speech during AI speech
    Gemini->>Proxy: WebSocket Event: interrupted (cancel pending output)
    
    Proxy->>Browser: WebSocket Event: ABORT_OUTPUT
    Note over Browser: Flush playback queue immediately & halt Speaker
    
    Note over Gemini: Discard un-sent response tokens
    Browser->>Proxy: Continuous user audio frames
    Proxy->>Gemini: Forward user audio
```
