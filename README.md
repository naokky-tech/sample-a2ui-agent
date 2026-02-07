# a2ui-agent-sample

`server.py` is a minimal FastAPI-based A2A JSON-RPC agent that returns A2UI v0.8-compliant UI messages. It exposes an agent card, a JSON-RPC endpoint, and a health check.

## What It Does

- Serves an agent card at `/.well-known/agent-card.json`
- Accepts `message/send` JSON-RPC calls at `/a2a/jsonrpc`
- Returns a completed task containing A2UI v0.8 messages (a small UI with a title and OK/Cancel buttons)
- Provides a health check at `/healthz`

## Requirements

- Python 3.9+
- `fastapi`
- `uvicorn`

## Quick Start

```bash
pip install fastapi uvicorn
python server.py
```

By default it listens on port `10002`.

## Environment Variables

- `PORT`: Port to bind (default: `10002`)
- `PUBLIC_BASE_URL`: Base URL used in the agent card (default: `http://localhost:<PORT>`)

## Endpoints

1. `GET /.well-known/agent-card.json`
   - Returns metadata for the agent (protocol version, capabilities, skills, etc.).
2. `POST /a2a/jsonrpc`
   - JSON-RPC 2.0 endpoint. Only `message/send` is supported.
3. `GET /healthz`
   - Returns `{ ok: true, time: <ISO8601>, publicBaseUrl: <string> }`.

## JSON-RPC Request Example

```bash
curl -s http://localhost:10002/a2a/jsonrpc \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "kind": "message",
        "role": "user",
        "parts": [
          { "kind": "text", "text": "Hello!" }
        ]
      }
    }
  }'
```

## Notes

- CORS is fully open for development; restrict `allow_origins` for production use.
- If the request includes an A2UI event in a `data` part with MIME type `application/json+a2ui`, the response title will echo that event.
