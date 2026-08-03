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
import bcrypt
import jwt

from backend.config import settings
from backend.db import init_db_pool, close_db_pool, get_db_pool
from backend.auth import get_redis_client, get_current_user_context
from backend.agent import run_agent
from backend.websocket import websocket_speech_proxy
from backend.api.super_admin import router as super_admin_router
from backend.api.users import router as users_router
from backend.api.cards import router as cards_router
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-main")

# Global Kafka Producer instance
kafka_producer = None

async def seed_super_admin_account():
    """
    Dynamically seeds/upserts the Super Admin role (ID: 0) and Super Admin user account 
    using settings.SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, and SUPER_ADMIN_ID from .env.
    """
    logger.info("Verifying/seeding Super Admin account in PostgreSQL...")
    try:
        try:
            admin_uuid = uuid.UUID(settings.SUPER_ADMIN_ID)
        except ValueError:
            admin_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, settings.SUPER_ADMIN_ID)

        hashed_bytes = bcrypt.hashpw(settings.SUPER_ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt())
        hashed_password = hashed_bytes.decode("utf-8")

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Upsert Super Admin role (ID: 0)
            await conn.execute(
                """
                INSERT INTO roles (id, role_name, permissions) VALUES 
                (0, 'super_admin', '{"is_super_admin": true, "can_manage_users": true, "can_access_admin_tools": true, "can_query_analytics": true, "can_write_knowledge": true, "can_chat_live": true}'::jsonb)
                ON CONFLICT (id) DO UPDATE SET permissions = EXCLUDED.permissions;
                """
            )

            # 2. Upsert Super Admin user account
            user_row = await conn.fetchrow(
                """
                INSERT INTO users (id, email, password_hash, role_id, full_name, username) 
                VALUES ($1, $2, $3, 0, 'Rhythem Sharma', 'echo_admin')
                ON CONFLICT (email) DO UPDATE SET 
                    role_id = 0, 
                    password_hash = $3,
                    full_name = COALESCE(users.full_name, 'Rhythem Sharma'),
                    username = COALESCE(users.username, 'echo_admin')
                RETURNING id;
                """,
                admin_uuid,
                settings.SUPER_ADMIN_EMAIL,
                hashed_password
            )
            actual_user_id = user_row["id"]

            # 3. Seed user_profiles
            await conn.execute(
                """
                INSERT INTO user_profiles (user_id, usage_tier)
                VALUES ($1, 'super_admin')
                ON CONFLICT (user_id) DO NOTHING;
                """,
                actual_user_id
            )

            # 4. Seed user_analytics
            await conn.execute(
                """
                INSERT INTO user_analytics (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING;
                """,
                actual_user_id
            )

            # 5. Seed System Fallback Guest User (00000000-0000-0000-0000-000000000000)
            fallback_uuid = uuid.UUID("00000000-0000-0000-0000-000000000000")
            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, role_id, full_name, username) 
                VALUES ($1, 'guest@echostack.internal', 'no_password_guest_account', 0, 'System Guest', 'guest')
                ON CONFLICT (id) DO NOTHING;
                """,
                fallback_uuid
            )
            await conn.execute(
                "INSERT INTO user_profiles (user_id, usage_tier) VALUES ($1, 'guest') ON CONFLICT (user_id) DO NOTHING;",
                fallback_uuid
            )
            await conn.execute(
                "INSERT INTO user_analytics (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING;",
                fallback_uuid
            )

            logger.info(f"Super Admin account '{settings.SUPER_ADMIN_EMAIL}' and Fallback Guest account verified/seeded successfully.")
    except Exception as e:
        logger.error(f"Failed to seed Super Admin account: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    global kafka_producer
    logger.info("Initializing database connection pool...")
    await init_db_pool()
    
    # Run Super Admin database seeder
    await seed_super_admin_account()
    
    logger.info("Initializing Redis connection...")
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        
    if settings.ENABLE_KAFKA:
        logger.info("Initializing Kafka Producer...")
        try:
            kafka_producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=1,
                max_block_ms=1000,
                request_timeout_ms=1000,
                api_version_auto_timeout_ms=1000
            )
            logger.info("Kafka Producer initialized successfully.")
        except Exception as e:
            logger.warning(f"Kafka Producer initialization skipped or timed out: {e}")
            kafka_producer = None
    else:
        logger.info("Kafka Producer disabled via ENABLE_KAFKA=false (Local Development Mode).")
        kafka_producer = None
    
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
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:3000", "http://localhost:8000"
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Super Admin router & Users API router
app.include_router(super_admin_router)
app.include_router(users_router)
app.include_router(cards_router)

@app.get("/auth/super-admin-token")
async def get_super_admin_token():
    """
    Dev helper endpoint returning a valid Super Admin JWT token signed with SECRET_KEY.
    """
    try:
        try:
            admin_uuid_str = str(uuid.UUID(settings.SUPER_ADMIN_ID))
        except ValueError:
            admin_uuid_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, settings.SUPER_ADMIN_ID))

        payload = {
            "user_id": admin_uuid_str,
            "email": settings.SUPER_ADMIN_EMAIL,
            "role_id": 0
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": admin_uuid_str,
            "email": settings.SUPER_ADMIN_EMAIL,
            "role_id": 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Super Admin token: {str(e)}"
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
    global kafka_producer
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

    # 3. Publish payload event to Kafka (with graceful local fallback)
    event_payload = {
        "doc_id": str(doc_id),
        "user_id": str(user_uuid),
        "file_path": temp_file_path,
        "file_name": file.filename
    }

    if settings.ENABLE_KAFKA and kafka_producer is None:
        try:
            kafka_producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=1,
                max_block_ms=1000,
                request_timeout_ms=1000
            )
        except Exception as kafka_init_err:
            logger.warning(f"Kafka Producer unavailable: {kafka_init_err}. Local fallback mode active.")

    if kafka_producer is not None:
        try:
            logger.info(f"Publishing ingestion job for doc {doc_id} to topic '{settings.KAFKA_INGESTION_TOPIC}'...")
            kafka_producer.send(settings.KAFKA_INGESTION_TOPIC, event_payload)
            kafka_producer.flush()
        except Exception as e:
            logger.warning(f"Failed to publish event to Kafka broker: {e}")
            kafka_producer = None
    else:
        logger.info(f"Kafka queue offline. Document {doc_id} registered in database as PENDING.")

    return {
        "document_id": str(doc_id),
        "file_name": file.filename,
        "status": "PENDING",
        "message": "Document uploaded successfully and registered for processing."
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

            # Clean up local file from disk
            if os.path.exists(settings.UPLOAD_DIR):
                for f in os.listdir(settings.UPLOAD_DIR):
                    if f.startswith(doc_id):
                        try:
                            os.remove(os.path.join(settings.UPLOAD_DIR, f))
                        except Exception as file_err:
                            logger.warning(f"Failed to remove upload file {f}: {file_err}")

            return {"message": f"Document {doc_id} and its associated vectors deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/documents")
async def clear_knowledge_base():
    """
    Wipes the entire vector knowledge base and document registry.
    """
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM documents")
            
            # Clean up all local upload files
            if os.path.exists(settings.UPLOAD_DIR):
                for f in os.listdir(settings.UPLOAD_DIR):
                    try:
                        file_path = os.path.join(settings.UPLOAD_DIR, f)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception as file_err:
                        logger.warning(f"Failed to clear upload file {f}: {file_err}")

            return {"message": "Knowledge base and local uploads wiped successfully."}
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

@app.get("/chunks/list")
def list_chunk_files():
    """
    Lists all document chunk JSON files and audio session chunk JSON files from 'chunks/'.
    """
    base_dir = "chunks"
    doc_dir = os.path.join(base_dir, "document_chunks")
    audio_dir = os.path.join(base_dir, "audio_chunks")

    doc_files = os.listdir(doc_dir) if os.path.exists(doc_dir) else []
    audio_files = os.listdir(audio_dir) if os.path.exists(audio_dir) else []

    return {
        "document_chunks": doc_files,
        "audio_chunks": audio_files,
        "latest_files": [f for f in os.listdir(base_dir) if f.endswith(".json")] if os.path.exists(base_dir) else []
    }

@app.get("/chunks/file/{category}/{filename}")
def get_chunk_file(category: str, filename: str):
    """
    Retrieves the contents of a specified JSON chunk file from 'chunks/'.
    """
    if category in ["latest", "root"]:
        file_path = os.path.join("chunks", filename)
    elif category in ["document_chunks", "audio_chunks"]:
        file_path = os.path.join("chunks", category, filename)
    else:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
