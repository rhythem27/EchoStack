import os
import json
import uuid
import base64
import logging
import asyncio
import jwt
from typing import Dict, Any, Optional
from fastapi import WebSocket, status
from langfuse.decorators import observe, langfuse_context

from google import genai
from google.genai import types

from backend.config import settings
from backend.db import get_db_pool
from backend.auth import get_redis_client, current_user_id, current_user_permissions
from backend.agent import query_user_analytics, rag_knowledge_search, web_search, python_code_interpreter

logger = logging.getLogger("backend-websocket")

# Tool priority configuration for Gemini speech responses
TOOL_PRIORITY = {
    "rag_knowledge_search": "WHEN_IDLE",
    "web_search": "WHEN_IDLE",
    "python_code_interpreter": "WHEN_IDLE",
    "query_user_analytics": "WHEN_IDLE"
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

@observe(name="live-tool-execution", as_type="span")
async def execute_live_tool(name: str, args: dict, user_context: dict) -> str:
    """
    Sets local contextvars, calls the requested tool asynchronously, and returns the response.
    """
    current_user_id.set(user_context["user_id"])
    current_user_permissions.set(user_context["permissions"])

    langfuse_context.update_current_observation(
        name=f"live-tool-{name}",
        input={"tool_name": name, "args": args},
        metadata={"user_id": str(user_context.get("user_id"))}
    )

    logger.info(f"Executing Live Agent tool: {name} with args: {args}")
    try:
        if name == "query_user_analytics":
            res = await query_user_analytics.ainvoke({})
        elif name == "rag_knowledge_search":
            query_val = args.get("query") or args.get("search_query") or ""
            res = await rag_knowledge_search.ainvoke({"query": query_val})
        elif name == "web_search":
            query_val = args.get("query") or args.get("search_query") or ""
            res = await web_search.ainvoke({"query": query_val})
        elif name == "python_code_interpreter":
            code_val = args.get("code") or args.get("expression") or ""
            res = await python_code_interpreter.ainvoke({"code": code_val})
        else:
            res = f"Error: Tool '{name}' is not supported."
        
        langfuse_context.update_current_observation(output=res)
        return res
    except Exception as e:
        logger.error(f"Error during tool execution: {e}")
        err_msg = f"Error executing tool: {str(e)}"
        langfuse_context.update_current_observation(output=err_msg)
        return err_msg

@observe(name="speech-to-speech-session", as_type="agent")
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
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    current_user_id.set(user_context["user_id"])
    current_user_permissions.set(user_context["permissions"])

    langfuse_context.update_current_trace(
        name="speech-to-speech-session",
        user_id=str(user_context["user_id"]),
        tags=["speech-to-speech", "gemini-live", "system-2"],
        metadata={"role_id": user_context["role_id"]}
    )

    # Session audio & vision chunk telemetry recorder
    session_id = str(uuid.uuid4())
    from datetime import datetime, timezone
    session_start_iso = datetime.now(timezone.utc).isoformat()
    audio_telemetry_logs = []
    chunk_counter = 0

    # Initialize google-genai client
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set in settings or os.environ.")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    genai_client = genai.Client(api_key=api_key)
    live_model = settings.GEMINI_LIVE_MODEL or os.environ.get("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")

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
                ),
                types.FunctionDeclaration(
                    name="web_search",
                    description="Performs a real-time web search to retrieve current information, news, or factual references.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING, 
                                description="The search query term or question."
                            )
                        },
                        required=["query"]
                    )
                ),
                types.FunctionDeclaration(
                    name="python_code_interpreter",
                    description="Executes Python code in a safe sandbox for mathematical calculations, data formatting, or complex formulas.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "code": types.Schema(
                                type=types.Type.STRING, 
                                description="The Python code string to execute."
                            )
                        },
                        required=["code"]
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
                nonlocal chunk_counter
                try:
                    while True:
                        msg_str = await websocket.receive_text()
                        payload = json.loads(msg_str)
                        
                        if payload.get("type") == "audio_chunk":
                            b64_data = payload.get("data")
                            if b64_data:
                                try:
                                    raw_bytes = base64.b64decode(b64_data)
                                    chunk_counter += 1
                                    audio_telemetry_logs.append({
                                        "chunk_index": chunk_counter,
                                        "direction": "client_to_agent",
                                        "media_type": "audio/pcm;rate=16000",
                                        "byte_length": len(raw_bytes),
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    })
                                    await gemini_session.send_realtime_input(
                                        audio=types.Blob(
                                            mime_type="audio/pcm;rate=16000",
                                            data=raw_bytes
                                        )
                                    )
                                except Exception as send_err:
                                    logger.warning(f"Failed sending audio chunk to Gemini Live: {send_err}")
                        elif payload.get("type") == "video_frame":
                            b64_data = payload.get("data")
                            if b64_data:
                                try:
                                    if "," in b64_data:
                                        b64_data = b64_data.split(",", 1)[1]
                                    raw_bytes = base64.b64decode(b64_data)
                                    chunk_counter += 1
                                    audio_telemetry_logs.append({
                                        "chunk_index": chunk_counter,
                                        "direction": "client_to_agent",
                                        "media_type": "image/jpeg",
                                        "byte_length": len(raw_bytes),
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    })
                                    logger.info(f"Forwarding video frame ({len(raw_bytes)} bytes) to Gemini Live endpoint.")
                                    await gemini_session.send_realtime_input(
                                        video=types.Blob(
                                            mime_type="image/jpeg",
                                            data=raw_bytes
                                        )
                                    )
                                except Exception as send_err:
                                    logger.warning(f"Failed sending video frame to Gemini Live: {send_err}")
                except Exception as e:
                    logger.info(f"Client to Gemini loop exited: {e}")

            async def gemini_to_client_loop():
                nonlocal chunk_counter
                try:
                    while True:
                        async for response in gemini_session.receive():
                            # 1. Forward Audio Output
                            server_content = response.server_content
                            if server_content is not None:
                                model_turn = server_content.model_turn
                                if model_turn is not None:
                                    for part in model_turn.parts:
                                        if part.inline_data is not None:
                                            chunk_counter += 1
                                            audio_telemetry_logs.append({
                                                "chunk_index": chunk_counter,
                                                "direction": "agent_to_client",
                                                "media_type": "audio/pcm;rate=24000",
                                                "byte_length": len(part.inline_data.data),
                                                "timestamp": datetime.now(timezone.utc).isoformat()
                                            })
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
                                    
                                    try:
                                        await websocket.send_json({
                                            "type": "tool_call",
                                            "tool_name": call.name,
                                            "args": call.args
                                        })
                                    except Exception:
                                        pass

                                    tool_result = await execute_live_tool(call.name, call.args, user_context)
                                    
                                    try:
                                        await websocket.send_json({
                                            "type": "tool_result",
                                            "tool_name": call.name,
                                            "result": tool_result
                                        })
                                    except Exception:
                                        pass

                                    sched_mode = TOOL_PRIORITY.get(call.name, "WHEN_IDLE")
                                    logger.info(f"Returning tool response with scheduling mode: {sched_mode}")
                                    
                                    await gemini_session.send_tool_response(
                                        function_responses=[types.FunctionResponse(
                                            name=call.name,
                                            response={"result": tool_result},
                                            id=call.id,
                                            scheduling=sched_mode
                                        )]
                                    )
                except Exception as e:
                    logger.error(f"Gemini to Client loop error: {e}", exc_info=True)

            task_a = asyncio.create_task(client_to_gemini_loop())
            task_b = asyncio.create_task(gemini_to_client_loop())
            done, pending = await asyncio.wait([task_a, task_b], return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()

    except Exception as conn_err:
        logger.error(f"Error establishing session with Gemini Live: {conn_err}")
    finally:
        logger.info("WebSocket speech proxy session closed.")
        # Export audio stream chunks telemetry to JSON file inside 'chunks' folder
        try:
            export_dir = os.path.join("chunks", "audio_chunks")
            os.makedirs(export_dir, exist_ok=True)
            export_file = f"audio_session_{session_id}.json"
            export_path = os.path.join(export_dir, export_file)
            latest_path = os.path.join("chunks", "audio_chunks_latest.json")
            
            export_payload = {
                "session_id": session_id,
                "user_id": str(user_context.get("user_id")),
                "session_started_at": session_start_iso,
                "session_ended_at": datetime.now(timezone.utc).isoformat(),
                "total_chunks_processed": len(audio_telemetry_logs),
                "chunks": audio_telemetry_logs
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_payload, f, indent=2, ensure_ascii=False)
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(export_payload, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(audio_telemetry_logs)} audio stream chunks to JSON file: {export_path}")
            logger.info(f"Updated latest audio chunks file: {latest_path}")
        except Exception as export_err:
            logger.error(f"Failed exporting audio chunk JSON: {export_err}")

        if websocket.client_state != status.WS_1011_INTERNAL_ERROR:
            try:
                await websocket.close()
            except Exception:
                pass
