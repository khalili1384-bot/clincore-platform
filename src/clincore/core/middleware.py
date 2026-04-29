# ───────────────────────────────────────────────────────
# ClinCore Platform — Proprietary & Confidential
# Copyright © 2026 ClinCore
# All rights reserved. Unauthorized use strictly prohibited.
# ───────────────────────────────────────────────────────
import uuid


class RequestIDMiddleware:
    """Attach a unique X-Request-ID to every request and response (pure ASGI)."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        from starlette.requests import Request
        from starlette.datastructures import MutableHeaders
        
        request = Request(scope, receive)
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Store in scope state
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id
        
        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)
        
        await self.app(scope, receive, send_with_request_id)
