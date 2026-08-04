# EchoStack 🚀
### Enterprise Real-Time Multimodal Speech-to-Speech & Agentic RAG Ecosystem

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.0-61DAFB.svg?logo=react&logoColor=white)](https://reactjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B_pgvector-4169E1.svg?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7.0%2B_Session_Cache-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)
[![Apache Kafka](https://img.shields.io/badge/Apache_Kafka-Event_Ingestion-231F20.svg?logo=apachekafka&logoColor=white)](https://kafka.apache.org)
[![Apache Spark](https://img.shields.io/badge/Apache_Spark-3.5_ETL-E25A1C.svg?logo=apachespark&logoColor=white)](https://spark.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Containerized_Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![WebSockets](https://img.shields.io/badge/WebSockets-Realtime_Stream-010101.svg?logo=socketdotio&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
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
- **Dual-Payload Generative UI Protocol**: Emits voice-triggered interactive UI card payloads (`AnalyticsMetricsCard`, `DocumentSearchCard`, `PythonResultCard`) over WebSockets while streaming natural language audio output.
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

## 💡 Interactive Prompts & Feature Showcase

You can interact with **EchoStack** via speech (voice), text, or live camera feed. Below are example prompts showcasing the platform's capabilities:

### 🎙️ 1. Real-Time Speech & User Analytics
- **"Hey Echo, show me a summary of my account analytics and total interaction history for this week."**
  - *Behind the scenes*: Triggers `query_user_analytics` to query PostgreSQL DB, emits an interactive `AnalyticsMetricsCard` UI widget over WebSockets, and speaks an executive voice summary.
- **"What are my current account permissions and assigned security roles?"**
  - *Behind the scenes*: Checks RBAC permissions cached in Redis for fast validation.

### 🎨 2. Voice-Triggered Dynamic UI Cards (Generative UI Protocol)
- **"Search knowledge base for deployment guides and architecture setup."**
  - *Behind the scenes*: Executes `rag_knowledge_search` hybrid RAG retriever, emitting a clickable `DocumentSearchCard` with document format badges (`PDF`, `DOCX`), RRF relevance scores, and expandable snippet dropdowns directly into the chat timeline.
- **"Calculate compound growth on $10,000 at 7.5% over 5 years using Python."**
  - *Behind the scenes*: Executes `python_code_interpreter`, mounting a `PythonResultCard` with code syntax highlighting, console output logs, and one-click copy buttons.

### 👁️ 2. Multimodal Camera & Spatial Object Detection
- **"Look at what I am holding in front of the camera — identify the object and draw a bounding box around it."**
  - *Behind the scenes*: Processes 1 FPS JPEG video frames and returns `highlight_spatial_object` coordinates (`[ymin, xmin, ymax, xmax]`) to render real-time bounding box overlays on screen.
- **"Inspect the text on my screen and explain what this architecture diagram represents."**
  - *Behind the scenes*: Analyzes live screen-share frames and provides step-by-step visual explanations.

### 📚 3. Hybrid RAG Document Knowledge Search
- **"Search the knowledge base for our PostgreSQL vector indexing and deployment setup."**
  - *Behind the scenes*: Runs hybrid vector search (BAAI/bge-small-en-v1.5) + keyword search using Reciprocal Rank Fusion (**RRF**) against ingested `.pdf`, `.docx`, `.md`, or `.csv` files.
- **"What does section 2 of our architecture manual say about Kafka event ingestion topics?"**
  - *Behind the scenes*: Retrieves relevant document chunks and synthesizes exact section references.

### 🧮 4. Sandboxed Python Code Interpretation & Math
- **"Run a Python script to compute the 30-day compound growth rate on a $10,000 investment at 8.5% annual return."**
  - *Behind the scenes*: Executes code safely inside `python_code_interpreter` sandbox and returns exact math calculations.
- **"Calculate the mean and standard deviation for this dataset `[12, 45, 67, 89, 23, 56, 78]` using Python."**

### 🌐 5. Live Web Search & Fact Retrieval
- **"Search the web for the latest updates on Gemini Live API features and release notes."**
  - *Behind the scenes*: Invokes `web_search` tool (via Tavily / DuckDuckGo API) to fetch real-time facts and citations.

---

## 🛠️ Key Capabilities & Features

### 🎨 Voice-Triggered Dynamic UI Cards (Generative UI Protocol)
- **Dual-Payload Event Multiplexing**: Tools emit structured JSON UI metadata (`ui_card`) alongside text summaries (`voice_text`). The WebSocket proxy pushes `RENDER_UI_CARD` events to the React client while sending clean voice summaries to Gemini Live for natural speech output.
- **Interactive Component Cards**:
  - `AnalyticsMetricsCard`: Displays user interaction metrics, activity score progress bar, topic chips, and sync timestamps.
  - `DocumentSearchCard`: Renders RAG search results with format tags (`PDF`, `DOCX`, `TXT`), Reciprocal Rank Fusion (RRF) relevance scores, and expandable snippet views.
  - `PythonResultCard`: Dark code block (`Python 3.11`), output console stream, execution status badge, and copy buttons.

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
│   ├── api/                  # REST Endpoint Routers (Users, Auth, RAG, Cards)
│   │   ├── cards.py          # UI Cards API Schema & Template Endpoints
│   │   ├── super_admin.py    # Super Admin Management Endpoints
│   │   └── users.py          # User Identity & Token Endpoints
│   ├── agent.py              # System 1 LangChain Agent & Dual-Payload Tools
│   ├── analytics_job.py      # Apache Spark PySpark ETL Analytics Job
│   ├── auth.py               # JWT Validation & Redis Permission Cache
│   ├── db.py                 # PostgreSQL asyncpg Connection Pooling
│   ├── main.py               # FastAPI App & Router Integration
│   ├── websocket.py          # Gemini Live Speech Proxy & UI Event Multiplexer
│   └── worker.py             # Kafka Document Processing Worker
├── test_pipeline/            # Quality Assurance Test Pipeline & Runner
│   ├── pytest.ini            # Pytest Configuration (Async Mode, Markers & Logs)
│   ├── logging_plugin.py     # Custom Pytest Plugin for Detailed Failure Error Logs
│   ├── conftest.py           # Async Fixtures, DB/Redis Mocks, Token Generators
│   ├── run_pipeline.py       # Central CLI Pipeline Test Runner
│   ├── unit/                 # Core Functions & Auth Unit Tests
│   ├── api/                  # REST API & RBAC Endpoint Tests
│   └── integration/          # AI Agent & WebSocket Speech Proxy Tests
├── frontend/                 # React 18 Web Application
│   ├── src/
│   │   ├── App.jsx           # Multimodal Workspace Dashboard & Card Listener
│   │   ├── components/       # KnowledgeManager, AuthModal, VisionOverlay
│   │   │   └── UICards/      # AnalyticsMetricsCard, DocumentSearchCard, PythonResultCard
│   │   └── App.css           # Glassmorphism Styling & UI Card Animations
│   └── public/
│       └── audio-processor.js # AudioWorklet Downsampler (16kHz PCM)
├── scripts/                  # Automated Test & Verification Scripts
│   └── test_phase11_dual_payload.py # Dual-Payload Protocol Test Suite
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

## 🧪 System Verification & Quality Assurance Pipeline

### Quality Assurance Test Pipeline (`test_pipeline/`)
Run real-world unit, API contract, integration, and WebSocket protocol tests with formatted failure error logging:

```bash
# Run complete test pipeline (All Suites)
poetry run python test_pipeline/run_pipeline.py

# Target specific test suites (unit | api | integration | websocket)
poetry run python test_pipeline/run_pipeline.py --suite api
poetry run python test_pipeline/run_pipeline.py --suite unit
poetry run python test_pipeline/run_pipeline.py --suite integration
poetry run python test_pipeline/run_pipeline.py --suite websocket

# Enable fail-fast (-x) and verbose (-v) output
poetry run python test_pipeline/run_pipeline.py -x -v
```

### Detailed Failure Logging
If any test fails, the custom `FailureLoggerPlugin` (`test_pipeline/logging_plugin.py`) automatically catches the failure and prints structured error logs containing:
- Test Node ID, file path, and execution phase.
- Exception class, message, and formatted stack traceback.
- Captured stdout/stderr streams and request/response payloads.

### Legacy Verification Scripts
```bash
# Run Phase 11 Dual-Payload Protocol verification script
poetry run python scripts/test_phase11_dual_payload.py

# Trigger background PySpark ETL analytics job
poetry run python backend/analytics_job.py
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.