from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ============================================================
# Config
# ============================================================
PORT = int(os.getenv("PORT", "10002"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}")

JSONRPC_PATH = "/a2a/jsonrpc"
A2UI_MIME_TYPE = "application/json+a2ui"

# v0.8 standard catalog id (optional but recommended)
V0_8_STANDARD_CATALOG_ID = "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"

# ============================================================
# App + CORS
# ============================================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 開発用。本番はフロントの origin に絞る
    allow_credentials=False,
    allow_methods=["*"],          # OPTIONS preflight OK
    allow_headers=["*"],          # X-A2A-Extensions 等 OK
)

# ============================================================
# Utilities
# ============================================================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def jsonrpc_error(req_id: Any, code: int, message: str, http_status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        },
    )


def build_task_with_a2ui_messages(a2ui_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    task_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    return {
        "kind": "task",
        "id": task_id,
        "contextId": context_id,
        "status": {
            "state": "completed",
            "timestamp": now_iso(),
            "message": {
                "kind": "message",
                "role": "agent",
                "messageId": message_id,
                "parts": [
                    {
                        "kind": "data",
                        "mimeType": A2UI_MIME_TYPE,
                        "data": msg,
                    }
                    for msg in a2ui_messages
                ],
            },
        },
        "artifacts": [],
        "history": [],
    }


def extract_user_text_or_a2ui_event(params_message: Dict[str, Any]) -> Dict[str, Any]:
    parts = params_message.get("parts") or []
    result: Dict[str, Any] = {"text": None, "a2ui_event": None, "raw_parts": parts}

    for p in parts:
        kind = p.get("kind")
        if kind == "text" and result["text"] is None:
            result["text"] = p.get("text")
        elif kind == "data" and p.get("mimeType") == A2UI_MIME_TYPE and result["a2ui_event"] is None:
            result["a2ui_event"] = p.get("data")

    return result


def a2ui_messages_v0_8(title: str) -> List[Dict[str, Any]]:
    """
    v0.8 spec 形式に寄せた最小 UI:
      - surfaceUpdate: components は [{id, component:{...}}] 形式
      - dataModelUpdate: path + contents(キー付きのエントリ配列)
      - beginRendering: root + (optional) catalogId
    """
    surface_id = "main"

    # --- Components (Adjacency list + v0.8 "component" wrapper) ---
    surface_update = {
        "surfaceUpdate": {
            "surfaceId": surface_id,
            "components": [
                {
                    "id": "root",
                    "component": {
                        "Column": {
                            "children": {"explicitList": ["title_text", "row_buttons"]}
                        }
                    },
                },
                {
                    "id": "title_text",
                    "component": {
                        "Text": {
                            "usageHint": "h3",
                            "text": {"literalString": title},
                        }
                    },
                },
                {
                    "id": "row_buttons",
                    "component": {
                        "Row": {
                            "alignment": "center",
                            "children": {"explicitList": ["btn_ok", "btn_cancel"]},
                        }
                    },
                },
                {
                    "id": "btn_ok_text",
                    "component": {"Text": {"text": {"literalString": "OK"}}},
                },
                {
                    "id": "btn_ok",
                    "component": {
                        "Button": {
                            "child": "btn_ok_text",
                            "action": {"name": "clicked_ok"},
                        }
                    },
                },
                {
                    "id": "btn_cancel_text",
                    "component": {"Text": {"text": {"literalString": "Cancel"}}},
                },
                {
                    "id": "btn_cancel",
                    "component": {
                        "Button": {
                            "child": "btn_cancel_text",
                            "action": {"name": "clicked_cancel"},
                        }
                    },
                },
            ],
        }
    }

    # --- Data model update (IMPORTANT) ---
    # v0.8 は dataModelUpdate を "path" と "contents" で更新する（contents は Map のエントリ配列）
    # ルート（"/"）は Map である必要があるため、必ず key/value* 形式で渡す
    data_model_update = {
        "dataModelUpdate": {
            "surfaceId": surface_id,
            "path": "/",  # ルートを更新
            "contents": [
                {"key": "now", "valueString": now_iso()},
            ],
        }
    }

    # --- Render signal ---
    begin_rendering = {
        "beginRendering": {
            "surfaceId": surface_id,
            "root": "root",
            "catalogId": V0_8_STANDARD_CATALOG_ID,
        }
    }

    return [surface_update, data_model_update, begin_rendering]


# ============================================================
# Routes
# ============================================================
@app.get("/.well-known/agent-card.json")
def agent_card() -> Dict[str, Any]:
    return {
        "protocolVersion": "0.3.0",
        "name": "A2UI Python Agent (Stub)",
        "description": "Minimal A2A JSON-RPC agent that returns A2UI v0.8 messages.",
        "version": "0.1.0",
        "url": f"{PUBLIC_BASE_URL}{JSONRPC_PATH}",
        "capabilities": {"pushNotifications": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [{"id": "a2ui", "name": "A2UI", "tags": ["a2ui"]}],
    }


@app.post(JSONRPC_PATH)
async def jsonrpc_handler(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return jsonrpc_error(None, -32700, "Parse error: invalid JSON", http_status=400)

    req_id = body.get("id")
    if body.get("jsonrpc") != "2.0":
        return jsonrpc_error(req_id, -32600, "Invalid Request: jsonrpc must be '2.0'", http_status=400)

    method = body.get("method")
    params = body.get("params") or {}

    if method != "message/send":
        return jsonrpc_error(req_id, -32601, f"Method not found: {method}", http_status=404)

    params_message = params.get("message") or {}
    parsed = extract_user_text_or_a2ui_event(params_message)

    title = "Hello A2UI (v0.8 spec-compliant)"
    if parsed["text"]:
        title = f"You said: {parsed['text']}"
    elif parsed["a2ui_event"]:
        # クライアントイベントを受け取った場合（本格的には userAction を解析して分岐）
        title = f"Got A2UI event: {json.dumps(parsed['a2ui_event'], ensure_ascii=False)}"

    a2ui_msgs = a2ui_messages_v0_8(title)
    task = build_task_with_a2ui_messages(a2ui_msgs)

    return JSONResponse(
        status_code=200,
        content={"jsonrpc": "2.0", "id": req_id, "result": task},
    )


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True, "time": now_iso(), "publicBaseUrl": PUBLIC_BASE_URL}
