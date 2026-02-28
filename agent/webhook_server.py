"""
agent/webhook_server.py
Phase 5: aiohttp web server for Fireflies.ai post-call webhook.

Scout currently has no HTTP server — this adds a lightweight aiohttp server
that runs in the same asyncio event loop alongside Telegram polling.

Endpoints:
  GET  /health             → 200 "Scout is alive" (Railway health check)
  POST /fireflies-webhook  → validates secret → queues transcript processing

Start with asyncio.gather() in main.py:
  await asyncio.gather(
      run_telegram(...),
      run_scheduler_loop(...),
      start_webhook_server(port, process_callback, webhook_secret),
  )
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os

from aiohttp import web

logger = logging.getLogger(__name__)


# ── Request Handlers ──────────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    """Railway health check. Always returns 200."""
    return web.Response(text="Scout is alive", status=200)


async def handle_fireflies_webhook(request: web.Request) -> web.Response:
    """
    Receives POST /fireflies-webhook from Fireflies.ai.
    Validates HMAC signature (if secret is configured), then queues processing.

    Fireflies webhook payload:
    {
        "meetingId": "...",
        "transcriptId": "...",
        "eventType": "Transcription completed",
        "clientReferenceId": "..."
    }
    """
    webhook_secret: str = request.app["webhook_secret"]
    process_callback = request.app["process_callback"]

    # Read raw body first (needed for HMAC validation)
    try:
        body_bytes = await request.read()
        data = json.loads(body_bytes)
    except Exception as e:
        logger.warning(f"[Webhook] Could not parse request body: {e}")
        return web.Response(text="Bad Request", status=400)

    # Validate HMAC signature if secret is configured
    if webhook_secret:
        sig_header = request.headers.get("X-Fireflies-Signature", "")
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected_sig):
            logger.warning("[Webhook] Invalid HMAC signature — rejecting request.")
            return web.Response(text="Unauthorized", status=401)

    event_type = data.get("eventType", "unknown")
    transcript_id = data.get("transcriptId") or data.get("meetingId", "")

    logger.info(f"[Webhook] Fireflies event: '{event_type}' | transcript: {transcript_id}")

    # Only process transcription completion events
    if "transcription" not in event_type.lower() and "completed" not in event_type.lower():
        logger.info(f"[Webhook] Ignoring non-transcription event: {event_type}")
        return web.Response(text="OK (ignored)", status=200)

    if not transcript_id:
        logger.warning("[Webhook] No transcript ID in payload.")
        return web.Response(text="No transcript ID", status=400)

    # Queue processing as a background task — respond to Fireflies immediately
    # so it doesn't time out waiting for us to finish processing
    asyncio.create_task(process_callback(transcript_id))
    logger.info(f"[Webhook] Queued processing for transcript: {transcript_id}")

    return web.Response(text="OK", status=200)


# ── Server Lifecycle ──────────────────────────────────────────────────────────

async def start_webhook_server(
    port: int,
    process_callback,
    webhook_secret: str = "",
) -> None:
    """
    Start the aiohttp web server and keep it running.

    port:             Railway's PORT env var
    process_callback: async callable(transcript_id: str)
    webhook_secret:   FIREFLIES_WEBHOOK_SECRET from Railway env

    This coroutine runs forever alongside Telegram polling via asyncio.gather().
    """
    app = web.Application()
    app["webhook_secret"] = webhook_secret
    app["process_callback"] = process_callback

    app.router.add_get("/health", handle_health)
    app.router.add_post("/fireflies-webhook", handle_fireflies_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"[Webhook] Server listening on 0.0.0.0:{port}")
    logger.info(f"[Webhook] Fireflies endpoint: POST /fireflies-webhook")
    logger.info(f"[Webhook] Health check: GET /health")

    # Keep running until cancelled
    try:
        while True:
            await asyncio.sleep(3600)  # just keeps the coroutine alive
    except asyncio.CancelledError:
        logger.info("[Webhook] Server shutting down.")
    finally:
        await runner.cleanup()
