import os
import json
import uuid
import base64
import logging
import asyncio
import jwt
from typing import Dict, Any, Optional
from fastapi import WebSocket, status

from google import genai
from google.genai import types

from backend.config import settings
from backend.db import get_db_pool
from backend.auth import get_redis_client, current_user_id, current_user_permissions
from backend.agent import query_user_analytics, rag_knowledge_search

logger = logging.getLogger("backend-websocket")

# Tool priority configuration for Gemini speech responses
TOOL_PRIORITY = {
    "rag_knowledge_search": "INTERRUPT",  # Instantly stop speaking to give RAG document answers
    "query_user_analytics": "WHEN_IDLE"   # Answer analytics query once current phrase/turn completes
}

async def authenticate_websocket(token: str) -> dict:
    """
    Validates the connection token query parameter.
    Retrieves user permissions from Redis or fallback DB and returns user context.
    """
    if not token:
        raise ValueError("Authentication token is missing.")
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id_str = payload.get("user_id")
        role_id = payload.get("role_id")
        if not user_id_str or role_id is None:
            raise ValueError("Invalid token payload: missing user_id or role_id.")
        user_uuid = uuid.UUID(user_id_str)
    except jwt.PyJWTError as jwt_err:
        raise ValueError(f"Invalid or expired token: {str(jwt_err)}")
    except ValueError:
        raise ValueError("Invalid user_id format in token.")

    redis_client = get_redis_client()
    cache_key = f"user_permissions:{user_id_str}"
    
    permissions = None
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            permissions = data.get("permissions")
    except Exception as redis_err:
        logger.error(f"Redis fetch failed in WebSocket authentication: {redis_err}")

    if permissions is None:
        logger.info(f"Cache miss for WebSocket user {user_id_str}. Querying Postgres...")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.role_id, r.permissions
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.id = $1
                """,
                user_uuid
            )
            if not row:
                raise ValueError("User or role not found in database.")
            
            permissions = row["permissions"]
            if isinstance(permissions, str):
                permissions = json.loads(permissions)
            else:
                permissions = dict(permissions)
        
        try:
            cache_payload = {
                "role_id": role_id,
                "permissions": permissions
            }
            await redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
        except Exception as redis_err:
            logger.error(f"Failed to cache user permissions in WebSocket: {redis_err}")

    return {
        "user_id": user_uuid,
        "role_id": role_id,
        "permissions": permissions
    }

async def execute_live_tool(name: str, args: dict, user_context: dict) -> str:
    """
    Sets local contextvars, calls the requested tool asynchronously, and returns the response.
    """
    # Enforce thread/task-safe contextvars
    current_user_id.set(user_context["user_id"])
    current_user_permissions.set(user_context["permissions"])

    logger.info(f"Executing Live Agent tool: {name} with args: {args}")
    try:
        if name == "query_user_analytics":
            return await query_user_analytics.ainvoke({})
        elif name == "rag_knowledge_search":
            query_val = args.get("query") or args.get("search_query") or ""
            return await rag_knowledge_search.ainvoke({"query": query_val})
        else:
            return f"Error: Tool '{name}' is not supported."
    except Exception as e:
        logger.error(f"Error during tool execution: {e}")
        return f"Error executing tool: {str(e)}"

async def websocket_speech_proxy(websocket: WebSocket, token: Optional[str] = None):
    """
    Bidirectional WebSocket proxy connecting React client PCM stream to Gemini Live API.
    """
    await websocket.accept()

    try:
        user_context = await authenticate_websocket(token)
        logger.info(f"WebSocket client authenticated successfully. User: {user_context['user_id']}")
    except Exception as auth_err:
        logger.warning(f"WebSocket connection rejected: {auth_err}")
        # Close with policy violation code
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Ensure contextvars are initialized for this parent task
    current_user_id.set(user_context["user_id"])
    current_user_permissions.set(user_context["permissions"])

    # Initialize google-genai client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set.")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    genai_client = genai.Client(api_key=api_key)
    live_model = os.environ.get("GEMINI_LIVE_MODEL", "gemini-2.0-flash-exp")

    # Define tools and voice connection configuration
    live_config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
        tools=[
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="query_user_analytics",
                    description="Queries the user analytics database to retrieve engagement insights, such as total interactions and top topics.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={}
                    )
                ),
                types.FunctionDeclaration(
                    name="rag_knowledge_search",
                    description="Performs a semantic similarity search against the vector knowledge base using the query text to retrieve relevant document chunks.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING, 
                                description="The semantic search query text."
                            )
                        },
                        required=["query"]
                    )
                )
            ])
        ]
    )

    logger.info(f"Connecting to Gemini Live Endpoint using model: {live_model}")
    try:
        async with genai_client.aio.live.connect(
            model=live_model,
            config=live_config
        ) as gemini_session:
            
            async def client_to_gemini_loop():
                """
                Task A: Receives base64 audio frames from client, decodes them to PCM,
                and forwards them to the Gemini Live endpoint.
                """
                try:
                    while True:
                        msg_str = await websocket.receive_text()
                        payload = json.loads(msg_str)
                        
                        if payload.get("type") == "audio_chunk":
                            b64_data = payload.get("data")
                            if b64_data:
                                # Decode base64 PCM back to raw bytes (16kHz PCM little-endian)
                                raw_bytes = base64.b64decode(b64_data)
                                await gemini_session.send_realtime_input(
                                    media_chunks=[types.Blob(
                                        mime_type="audio/pcm;rate=16000",
                                        data=raw_bytes
                                    )]
                                )
                except Exception as e:
                    logger.info(f"Client to Gemini loop exited: {e}")

            async def gemini_to_client_loop():
                """
                Task B: Receives audio turns and tool execution calls from Gemini,
                processes/routes tools, and forwards outputs to the client.
                """
                try:
                    async for response in gemini_session.receive():
                        # 1. Forward Audio Output
                        server_content = response.server_content
                        if server_content is not None:
                            model_turn = server_content.model_turn
                            if model_turn is not None:
                                for part in model_turn.parts:
                                    if part.inline_data is not None:
                                        # Base64 encode raw 24kHz PCM audio back to the client
                                        b64_out = base64.b64encode(part.inline_data.data).decode("utf-8")
                                        await websocket.send_json({
                                            "type": "audio_chunk",
                                            "data": b64_out
                                        })
                            if server_content.interrupted:
                                logger.info("Gemini Live server content interrupted (VAD barge-in).")
                                await websocket.send_json({
                                    "type": "interrupted"
                                })

                        # 2. Intercept Tool Call requests
                        tool_call = response.tool_call
                        if tool_call is not None:
                            for call in tool_call.function_calls:
                                logger.info(f"Intercepted function call request: {call.name} (id: {call.id})")
                                
                                # Run tool asynchronously
                                tool_result = await execute_live_tool(call.name, call.args, user_context)
                                
                                # Fetch scheduling priority (INTERRUPT or WHEN_IDLE)
                                sched_mode = TOOL_PRIORITY.get(call.name, "WHEN_IDLE")
                                logger.info(f"Returning tool response with scheduling mode: {sched_mode}")
                                
                                await gemini_session.send_tool_response(
                                    types.LiveClientToolResponse(
                                        function_responses=[types.FunctionResponse(
                                            name=call.name,
                                            response={"result": tool_result},
                                            id=call.id,
                                            scheduling=sched_mode
                                        )]
                                    )
                                )
                except Exception as e:
                    logger.info(f"Gemini to Client loop exited: {e}")

            # Run loops concurrently
            await asyncio.gather(client_to_gemini_loop(), gemini_to_client_loop())

    except Exception as conn_err:
        logger.error(f"Error establishing session with Gemini Live: {conn_err}")
    finally:
        logger.info("WebSocket speech proxy session closed.")
        if websocket.client_state != status.WS_1011_INTERNAL_ERROR:
            try:
                await websocket.close()
            except Exception:
                pass
