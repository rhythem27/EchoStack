# EchoStack User Roles & Permissions Reference

This document outlines the Role-Based Access Control (RBAC) model, permissions, default seed accounts, and system session types implemented across EchoStack.

---

## 1. System User Roles & Permissions

EchoStack enforces a 3-tier Role-Based Access Control model stored in PostgreSQL and cached in Redis.

### 🛡️ Admin Role (Role ID: 1)
* **Role Name**: `admin`
* **Description**: Full System Administrator with complete privileges across all tools, databases, and streaming interfaces.
* **Permissions in English**:
  * **Admin Tools Access**: Granted. Can execute system-level admin tools (such as the Python Code Sandbox).
  * **User Analytics Queries**: Granted. Can query user analytics databases for interaction insights.
  * **Knowledge Base Indexing**: Granted. Can upload documents, perform vector searches, and modify vector knowledge.
  * **Live Agent Speech Proxy**: Granted. Can establish real-time speech and vision sessions with Gemini Live.

---

### ⚡ Premium Role (Role ID: 2)
* **Role Name**: `premium`
* **Description**: Power User with access to vector search, analytics, and live streaming, but restricted from administrative sandbox execution.
* **Permissions in English**:
  * **Admin Tools Access**: Restricted. Cannot run administrative sandbox tools or custom code execution.
  * **User Analytics Queries**: Granted. Can query user interaction analytics and topic metrics.
  * **Knowledge Base Indexing**: Granted. Can upload documents and perform RAG vector knowledge searches.
  * **Live Agent Speech Proxy**: Granted. Can establish real-time speech and vision sessions with Gemini Live.

---

### 👤 Standard Role (Role ID: 3)
* **Role Name**: `standard`
* **Description**: Basic User restricted to real-time speech and vision interaction without access to internal analytics or vector search.
* **Permissions in English**:
  * **Admin Tools Access**: Restricted. Cannot execute administrative tools.
  * **User Analytics Queries**: Restricted. Cannot access internal user analytics.
  * **Knowledge Base Indexing**: Restricted. Cannot query or modify vector knowledge indexing.
  * **Live Agent Speech Proxy**: Granted. Can interact via real-time speech and vision streaming.

---

## 2. System Session Types

EchoStack manages four types of sessions:

1. **Real-Time Speech & Vision WebSocket Session (`/ws/speech`)**:
   * **Identifier**: Unique UUID assigned per connection (e.g., `f47ac10b-58cc-4372-a567-0e02b2c3d479`).
   * **Purpose**: Manages bidirectional 16kHz PCM audio streaming, 24kHz audio playback, SSIM camera frame deduplication, and spatial bounding box overlays with Gemini Live.

2. **Agent Chat Session (`/agent/chat`)**:
   * **Identifier**: Authenticated User UUID.
   * **Purpose**: Manages REST API interactions with the LangChain agent for single-turn or multi-turn text interaction and tool processing.

3. **Background Ingestion Worker Session**:
   * **Identifier**: Document Processing ID (`doc_id` UUID).
   * **Purpose**: Background Kafka consumer pipeline processing document layout extraction, semantic chunking, and `pgvector` indexing.

4. **Redis Permission Cache Session**:
   * **Identifier**: `user_permissions:<user_id>`
   * **Purpose**: Caches user role permissions in Redis for 1 hour (3600s TTL) to prevent repeated PostgreSQL lookup queries during streaming.
