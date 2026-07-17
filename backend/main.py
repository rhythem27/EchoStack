import os
import json
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaProducer

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
        # Note: In development we continue, but in production this might be a fatal error.
    
    yield
    
    # Shutdown lifecycle
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
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("00000000-0000-0000-0000-000000000000")
):
    """
    Saves an uploaded document PDF locally, registers a PENDING entry in PostgreSQL,
    and publishes an ingestion job payload to Kafka.
    """
    # 1. Basic validation
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF documents are supported."
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
        # If Kafka was not ready during startup, try to reconnect
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
        # Note: Typically, we would fail-back or retry, or mark the document as FAILED
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
    Retrieves all documents registered in PostgreSQL.
    """
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, file_name, status, created_at FROM documents ORDER BY created_at DESC")
            return [
                {
                    "id": str(row["id"]),
                    "file_name": row["file_name"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None
                } for row in rows
            ]
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {str(e)}"
        )

class AgentChatRequest(BaseModel):
    message: str

@app.post("/agent/chat")
async def chat_with_agent(
    request: AgentChatRequest,
    user_context: dict = Depends(get_current_user_context)
):
    """
    Triggers the LangChain agent (System 1) with the user message.
    """
    try:
        response = await run_agent(request.message)
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
