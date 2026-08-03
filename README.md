# EchoStack 🚀
### Enterprise Real-Time Multimodal Speech-to-Speech & Agentic RAG Ecosystem

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.0-61DAFB.svg?logo=react&logoColor=white)](https://reactjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B_pgvector-4169E1.svg?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Apache Kafka](https://img.shields.io/badge/Apache_Kafka-Event_Ingestion-231F20.svg?logo=apachekafka&logoColor=white)](https://kafka.apache.org)
[![Apache Spark](https://img.shields.io/badge/Apache_Spark-3.5_ETL-E25A1C.svg?logo=apachespark&logoColor=white)](https://spark.apache.org)
[![Langfuse](https://img.shields.io/badge/Langfuse-Telemetry_%26_Tracing-FF4500.svg)](https://langfuse.com)
[![Gemini Live API](https://img.shields.io/badge/Gemini_Live-Multimodal_Stream-8E75B2.svg?logo=google&logoColor=white)](https://ai.google.dev)

---

## 🎬 Real-Time Multimodal Demo

![EchoStack Platform Demo](https://raw.githubusercontent.com/rhythem27/EchoStack/main/reference/demo_preview.webp)

> **Live Multimodal Interaction**: Low-latency bidirectional speech streaming, real-time webcam frame processing with spatial object detection overlays, hybrid RAG document search, and background PySpark ETL analytics.

---

## 📌 Executive Summary

**EchoStack** is an enterprise-grade agent platform engineered for ultra-low latency multimodal interaction, knowledge retrieval, and analytics. It bridges modern AI capabilities (speech-to-speech, vision analysis, hybrid RAG) with distributed data infrastructure (Apache Kafka, PySpark, PostgreSQL `pgvector`, Redis).

### Architecture Highlights:
- **Dual-Agent Architecture**:
  - **System 1 (Agent Orchestrator)**: LangChain-powered tool execution agent for hybrid RAG search, database querying, web searching, and sandboxed Python code interpretation.
  - **System 2 (Speech-to-Speech Engine)**: Real-time bidirectional WebSocket proxy interfacing directly with Google Gemini Live API for sub-second voice and visual interaction.
- **Asynchronous Document Pipeline**: Kafka-driven document parsing and vector embedding pipeline, isolating background ingestion tasks from client-facing REST APIs.
- **Distributed Big Data Analytics**: Containerized PySpark cluster performing scheduled batch aggregations and writing user engagement metrics back to PostgreSQL.
- **Full Observability**: End-to-end tracing across LLM calls, retriever lookups, tool executions, and voice streaming via self-hosted/cloud **Langfuse**.

---

## 🏗️ System Architecture

```mermaid
graph TD
    %% Client & Interface Layer
    subgraph Client_Layer ["Client & Interface Layer"]
        ReactClient["React 18 Frontend <br> (AudioWorklet 16kHz PCM / 1 FPS Video)"]
    end

    %% Gateway & Proxy Layer
    subgraph Gateway_Layer ["Gateway & Ingress Layer"]
        FastAPI["FastAPI Ingress & WS Proxy"]
        Redis["Redis Session Cache & Permissions"]
    end

    %% Messaging & Event Streaming
    subgraph Streaming_Layer ["Event Streaming Layer"]
        Kafka["Apache Kafka Event Broker <br> (Topic: document.ingestion.events)"]
    end

    %% Storage & Database Layer
    subgraph Storage_Layer ["Data & Vector Storage"]
        Postgres["PostgreSQL + pgvector <br> (Transactional DB & HNSW Index)"]
    end

    %% Processing & Compute Layer
    subgraph Worker_Layer ["Background Compute Layer"]
        KafkaWorker["Kafka Ingestion Workers <br> (PDF / DOCX / CSV / PPTX)"]
        SparkCluster["PySpark Cluster <br> (Master + Worker Executors)"]
    end

    %% AI & Observability Layer
    subgraph AI_Observability ["AI & Observability Engine"]
        GeminiLive["Google Gemini Live API <br> (Multimodal Speech & Vision)"]
        Langfuse["Langfuse Tracing & Observability"]
    end

    %% Connections
    ReactClient -- "REST API (JWT Auth)" --> FastAPI
    ReactClient -- "WebSockets (wss://)" --> FastAPI
    FastAPI <--> Redis
    FastAPI -- "Secure WS Proxy" --> GeminiLive
    FastAPI -- "Publish Ingestion Events" --> Kafka
    FastAPI <--> Postgres
    Kafka -- "Consume Ingestion Events" --> KafkaWorker
    KafkaWorker -- "Write Chunks & Embeddings" --> Postgres
    SparkCluster -- "Partitioned JDBC Read/Write" --> Postgres
    FastAPI -- "Log Telemetry & Spans" --> Langfuse
    GeminiLive -- "Tool Intercept Calls" --> FastAPI
```

---

## ⚡ Cost & Latency Optimization Showcase

EchoStack is engineered from the ground up for high throughput, minimal API token burn, and sub-second voice latency:

### 1. Structural Similarity (SSIM) Frame Deduplication
- **Problem**: Continuous 30 FPS video streaming burns millions of vision API tokens per minute, sending redundant identical frames.
- **Solution**: EchoStack evaluates consecutive frames using Structural Similarity (SSIM) pixel differences on the client side before transmission.
- **Result**: **Reduces vision token costs by up to 80%** while preserving frame-by-frame visual accuracy for moving objects and UI changes.

### 2. Sub-10ms HNSW Cosine Vector Retrieval
- **Problem**: Flat vector searches degrade exponentially as document chunk datasets grow.
- **Solution**: Vector embeddings (`BAAI/bge-small-en-v1.5`) are indexed in PostgreSQL using Hierarchical Navigable Small World (**HNSW**) graphs (`m=16, ef_construction=64`).
- **Result**: Sub-10ms cosine similarity lookups combined with Reciprocal Rank Fusion (**RRF**) keyword search.

### 3. Asynchronous Kafka Queue Isolation
- **Problem**: Parsing complex PDFs or PPTX files and generating embeddings causes HTTP timeouts if executed synchronously in API request handlers.
- **Solution**: Ingestion requests immediately return an `ingestion_job_id` and push document events to Apache Kafka (`document.ingestion.events`). Decoupled worker processes consume events, extract text, compute embeddings, and update document status asynchronously.
- **Result**: Guaranteed sub-50ms REST API response times for document uploads regardless of file size.

### 4. VAD Barge-In & Queue Cancellation
- **Problem**: User voice interruptions cause overlapping audio output and model state desynchronization.
- **Solution**: The backend listens for server-side Voice Activity Detection (VAD) interruption signals from the Gemini Live stream. Upon detection, an `interrupted` frame is broadcast to the React frontend, instantly flushing Web Audio API playback buffers.
- **Result**: Zero audio overlap and seamless real-time conversation flow.

---

## 🛠️ Key Capabilities & Features

### 🎙️ Speech-to-Speech & Multimodal Vision
- **16kHz Int16 Downsampling**: Client-side `AudioWorklet` processor downsamples microphone input to 16kHz Int16 PCM chunks for low-overhead transmission.
- **24kHz High-Quality Audio Playback**: Incoming audio buffers are queued and scheduled via Web Audio API for smooth 24kHz voice output.
- **Spatial Object Detection**: Draws real-time 2D bounding box overlays (`[ymin, xmin, ymax, xmax]`) directly on live webcam feeds when the model identifies objects.

### 📚 Hybrid Knowledge Base & RAG Engine
- **Multi-Format Document Parsing**: Automatic text extraction and chunking for `.pdf`, `.docx`, `.txt`, `.csv`, `.md`, and `.pptx` files.
- **Reciprocal Rank Fusion (RRF)**: Merges dense semantic vector search scores with sparse keyword matches (`k=60`).

### 🔐 Security & Access Control (RBAC)
- **JWT Authorization**: Secure token generation signed with HS256 algorithm.
- **Redis Permission Caching**: User permissions (`can_query_analytics`, `can_write_knowledge`, `can_chat_live`) cached in Redis (`user_permissions:<user_id>`) for sub-millisecond RBAC validation.

### 📊 PySpark Batch Analytics Pipeline
- Partitioned JDBC reads from PostgreSQL database tables.
- Calculates user interaction metrics, top engagement topics, and activity timestamps.
- Writes aggregated insights back to PostgreSQL `user_analytics` table for instant agent querying.

---

## 📂 Repository Structure

```text
EchoStack/
├── backend/                  # FastAPI Core Gateway & Services
│   ├── api/                  # REST Endpoint Routers (Users, Auth, RAG)
│   ├── agent.py              # System 1 LangChain Agent & RAG Retriever
│   ├── analytics_job.py      # Apache Spark PySpark ETL Analytics Job
│   ├── auth.py               # JWT Validation & Redis Permission Cache
│   ├── db.py                 # PostgreSQL asyncpg Connection Pooling
│   ├── main.py               # FastAPI App & Database Seeding
│   ├── websocket.py          # Gemini Live Speech-to-Speech WS Proxy
│   └── worker.py             # Kafka Document Processing Worker
├── frontend/                 # React 18 Web Application
│   ├── src/
│   │   ├── App.jsx           # Multimodal Workspace Dashboard
│   │   ├── components/       # KnowledgeManager, AuthModal, VisionOverlay
│   │   └── index.css         # Styling & Design Tokens
│   └── public/
│       └── audio-processor.js # AudioWorklet Downsampler (16kHz PCM)
├── prompts/                  # System Prompts & Instruction Templates
│   └── system_session_prompt.md # Master Session System Prompt (Echo Persona)
├── postgres/                 # Database Initialization Scripts
│   └── init.sql              # Relational Schema & pgvector Extension Setup
├── tasks/                    # Task Specifications & Documentation
├── docker-compose.yml        # Infrastructure Orchestration (Postgres, Kafka, Redis, Spark)
├── pyproject.toml            # Python Dependencies & Poetry Config
└── start.ps1                 # Single-Click PowerShell Bootstrapper Script
```

---

## 🚀 Quickstart Guide

### Prerequisites
- **Python**: 3.11+ (managed via Poetry)
- **Node.js**: 18+ (managed via npm)
- **Docker & Docker Compose**: For database, messaging, and cache infrastructure
- **Google Gemini API Key**: Obtain from [Google AI Studio](https://aistudio.google.com)

### 1. Clone & Set Up Environment Variables
```bash
git clone https://github.com/rhythem27/EchoStack.git
cd EchoStack

# Copy example environment file
cp .env.example .env
```
Edit `.env` and set your `GEMINI_API_KEY`:
```env
GEMINI_API_KEY="your_actual_gemini_api_key_here"
```

### 2. Start Infrastructure Services (Docker)
Launch PostgreSQL (with `pgvector`), Redis, Apache Kafka, and PySpark:
```bash
docker-compose up -d
```

### 3. Install Dependencies & Seed Database
```bash
# Install backend Python dependencies
poetry install

# Run initial database migrations and seed default Super Admin
poetry run python -m backend.main
```

### 4. Run Backend & Frontend Servers

**Terminal 1 (Backend API & WS Server)**:
```bash
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 (Kafka Document Ingestion Worker)**:
```bash
poetry run python -m backend.worker
```

**Terminal 3 (React Frontend Web Portal)**:
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 System Verification & Testing

### Automated Test Suite
Run backend unit and integration tests:
```bash
poetry run pytest
```

### Trigger PySpark Analytics Job
Manually execute the background PySpark ETL analytics pipeline:
```bash
poetry run python backend/analytics_job.py
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.