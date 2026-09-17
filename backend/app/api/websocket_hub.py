import json
import asyncio
from fastapi import WebSocket
from typing import List, Dict

class WebSocketHub:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.journal = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            after = websocket.query_params.get('after')
            if self.journal:
                try:
                    cursor = max(0, int(after)) if after is not None else self.journal.recent_cursor()
                except ValueError:
                    cursor = 0
                # Lock prevents live broadcasts overtaking replay on this socket.
                while True:
                    events = self.journal.replay(cursor)
                    for event in events:
                        await asyncio.wait_for(websocket.send_text(json.dumps({**event, 'replayed': True})), timeout=5)
                        cursor = event['sequence']
                    if len(events) < 1000:
                        break
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: Dict):
        async with self._lock:
            event = self.journal.append(event_type, data) if self.journal else {"event": event_type, "data": data}
            payload = json.dumps(event)
            for conn in list(self.active_connections):
                try:
                    await asyncio.wait_for(conn.send_text(payload), timeout=5)
                except Exception:
                    self.disconnect(conn)

hub = WebSocketHub()
