import os
import json
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaProducer
from langfuse.decorators import observe, langfuse_context

from backend.config import settings
from backend.db import init_db_pool, close_db_pool, get_db_pool
from backend.auth import get_redis_client, get_current_user_context
from backend.agent import run_agent
from backend.websocket import websocket_speech_proxy
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-main")

# Global Kafka Producer instance
kafka_producer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    global kafka_producer
    logger.info("Initializing database connection pool...")
    await init_db_pool()
    
    logger.info("Initializing Redis connection...")
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        
    logger.info("Initializing Kafka Producer...")
    try:
        kafka_producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3
        )
    except Exception as e:
        logger.error(f"Failed to initialize Kafka Producer: {e}")
    
    yield
    
    # Shutdown lifecycle
    logger.info("Flushing Langfuse telemetry context...")
    try:
        langfuse_context.flush()
    except Exception as e:
        logger.error(f"Failed to flush Langfuse context: {e}")

    logger.info("Closing database connection pool...")
    await close_db_pool()
    
    logger.info("Closing Redis connection...")
    try:
        redis_client = get_redis_client()
        await redis_client.close()
    except Exception as e:
        logger.error(f"Failed to close Redis client: {e}")
        
    if kafka_producer:
        logger.info("Closing Kafka Producer...")
        kafka_producer.close()

app = FastAPI(
    title="EchoStack Core API Gateway",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-document", status_code=status.HTTP_202_ACCEPTED)
@observe(name="upload-document-api")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("00000000-0000-0000-0000-000000000000")
):
    """
    Saves an uploaded document PDF locally, registers a PENDING entry in PostgreSQL,
    and publishes an ingestion job payload to Kafka.
    """
    langfuse_context.update_current_trace(
        name="upload-document-api",
        user_id=user_id,
        tags=["api", "upload", "ingestion"],
        metadata={"file_name": file.filename}
    )
    # 1. Multi-format validation
    allowed_exts = (".pdf", ".docx", ".txt", ".csv", ".md", ".pptx")
    if not file.filename.lower().endswith(allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported extensions are: {', '.join(allowed_exts)}"
        )
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format for user_id."
        )

    doc_id = uuid.uuid4()
    temp_file_name = f"{doc_id}_{file.filename}"
    temp_file_path = os.path.join(settings.UPLOAD_DIR, temp_file_name)
    
    logger.info(f"Saving uploaded file to {temp_file_path}...")
    try:
        with open(temp_file_path, "wb") as buffer:
            # Read in chunks to prevent loading huge files completely in memory
            while chunk := await file.read(65536):
                buffer.write(chunk)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file locally: {str(e)}"
        )

    # 2. Insert PENDING tracking row into PostgreSQL
    logger.info(f"Registering document {doc_id} in PostgreSQL as PENDING...")
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (id, user_id, file_name, status)
                VALUES ($1, $2, $3, $4)
                """,
                doc_id, user_uuid, file.filename, "PENDING"
            )
    except Exception as e:
        # Cleanup file if DB insert fails
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        logger.error(f"Database insertion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database initialization failed: {str(e)}"
        )

    # 3. Publish payload event to Kafka
    if kafka_producer is None:
        try:
            kafka_producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3
            )
        except Exception as e:
            logger.error(f"Kafka Producer reconnection failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Asynchronous streaming queue unavailable."
            )

    event_payload = {
        "doc_id": str(doc_id),
        "user_id": str(user_uuid),
        "file_path": temp_file_path,
        "file_name": file.filename
    }

    logger.info(f"Publishing ingestion job for doc {doc_id} to topic '{settings.KAFKA_INGESTION_TOPIC}'...")
    try:
        kafka_producer.send(settings.KAFKA_INGESTION_TOPIC, event_payload)
        kafka_producer.flush()
    except Exception as e:
        logger.error(f"Failed to publish event to Kafka: {e}")
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'FAILED' WHERE id = $1",
                doc_id
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register background ingestion task: {str(e)}"
        )

    return {
        "document_id": str(doc_id),
        "file_name": file.filename,
        "status": "PENDING",
        "message": "Document uploaded successfully. Processing started in background."
    }

@app.get("/documents")
async def list_documents():
    """
    Retrieves all documents registered in PostgreSQL along with chunk counts.
    """
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT d.id, d.file_name, d.status, d.created_at, COUNT(vk.id) AS chunk_count
                FROM documents d
                LEFT JOIN vector_knowledge vk ON d.id = vk.doc_id
                GROUP BY d.id, d.file_name, d.status, d.created_at
                ORDER BY d.created_at DESC
                """
            )
            return [
                {
                    "id": str(row["id"]),
                    "file_name": row["file_name"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "chunk_count": row["chunk_count"]
                } for row in rows
            ]
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {str(e)}"
        )

@app.get("/documents/{doc_id}/chunks")
async def get_document_chunks(doc_id: str):
    """
    Retrieves chunk breakdowns and metadata tags for a specific document.
    """
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document UUID.")

    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            doc = await conn.fetchrow("SELECT id, file_name, status, created_at FROM documents WHERE id = $1", doc_uuid)
            if not doc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            rows = await conn.fetch(
                "SELECT id, chunk_text, metadata FROM vector_knowledge WHERE doc_id = $1 ORDER BY id ASC",
                doc_uuid
            )

            chunks = []
            for row in rows:
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                chunks.append({
                    "id": str(row["id"]),
                    "chunk_text": row["chunk_text"],
                    "metadata": meta or {}
                })

            return {
                "id": str(doc["id"]),
                "file_name": doc["file_name"],
                "status": doc["status"],
                "created_at": doc["created_at"].isoformat() if doc["created_at"] else None,
                "total_chunks": len(chunks),
                "chunks": chunks
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch chunks for doc {doc_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Deletes an individual document and all its associated vector chunks.
    """
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document UUID.")

    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM documents WHERE id = $1", doc_uuid)
            if result == "DELETE 0":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            return {"message": f"Document {doc_id} and its associated vectors deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/documents")
async def clear_knowledge_base():
    """
    Clears all documents and vector knowledge base records.
    """
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM vector_knowledge")
            await conn.execute("DELETE FROM documents")
            return {"message": "Knowledge base cleared successfully."}
    except Exception as e:
        logger.error(f"Failed to clear knowledge base: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/documents/{doc_id}/reindex")
async def reindex_document(doc_id: str):
    """
    Re-indexes an existing document by clearing its vector chunks and setting status to PENDING.
    """
    global kafka_producer
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document UUID.")

    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            doc = await conn.fetchrow("SELECT id, user_id, file_name FROM documents WHERE id = $1", doc_uuid)
            if not doc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            # Remove existing vector chunks for re-indexing
            await conn.execute("DELETE FROM vector_knowledge WHERE doc_id = $1", doc_uuid)
            await conn.execute("UPDATE documents SET status = 'PENDING' WHERE id = $1", doc_uuid)

            # Check if file exists in upload dir
            temp_file_name = f"{doc['id']}_{doc['file_name']}"
            temp_file_path = os.path.join(settings.UPLOAD_DIR, temp_file_name)

            if kafka_producer and os.path.exists(temp_file_path):
                event_payload = {
                    "doc_id": str(doc["id"]),
                    "user_id": str(doc["user_id"]),
                    "file_path": temp_file_path,
                    "file_name": doc["file_name"]
                }
                kafka_producer.send(settings.KAFKA_INGESTION_TOPIC, event_payload)
                kafka_producer.flush()

            return {
                "id": str(doc["id"]),
                "status": "PENDING",
                "message": f"Re-indexing triggered for document {doc['file_name']}."
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to re-index document {doc_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

class AgentChatRequest(BaseModel):
    message: str

@app.post("/agent/chat")
@observe(name="chat-with-agent-api")
async def chat_with_agent(
    request: AgentChatRequest,
    user_context: dict = Depends(get_current_user_context)
):
    """
    Triggers the LangChain agent (System 1) with the user message.
    """
    uid = str(user_context.get("user_id", "guest"))
    langfuse_context.update_current_trace(
        name="chat-with-agent-api",
        user_id=uid,
        tags=["api", "chat"]
    )
    try:
        response = await run_agent(request.message, user_id=uid)
        return {"response": response}
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )

@app.get("/auth/token")
def get_debug_token():
    """
    Utility endpoint to retrieve a valid JWT token for the default system admin user.
    """
    import jwt
    payload = {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "role_id": 1
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"token": token}

@app.websocket("/ws/speech")
async def websocket_speech(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time speech-to-speech proxy.
    """
    await websocket_speech_proxy(websocket, token)
