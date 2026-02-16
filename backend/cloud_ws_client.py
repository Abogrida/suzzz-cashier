"""
WebSocket Client for Local System
Connects to Cloud Backend and executes commands
"""
import asyncio
import json
import websockets
import os
from datetime import datetime
from typing import Callable, Dict
import traceback


class CloudWebSocketClient:
    def __init__(self, cloud_url: str, local_system_id: str = "default", sync_secret: str = None):
        """
        Initialize WebSocket client
        
        Args:
            cloud_url: Cloud backend URL (e.g., "wss://suzz-cloud.onrender.com")
            local_system_id: Unique ID for this local system
            sync_secret: Authentication secret
        """
        self.cloud_url = cloud_url
        self.local_system_id = local_system_id
        self.sync_secret = sync_secret or os.environ.get("SYNC_SECRET", "my_secure_password_123")
        self.websocket = None
        self.running = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 300  # 5 minutes max
        self.command_handlers: Dict[str, Callable] = {}
        
    def register_command_handler(self, command_type: str, handler: Callable):
        """Register a handler for a specific command type"""
        self.command_handlers[command_type] = handler
        print(f"[WS Client] Registered handler for: {command_type}")
    
    async def connect(self):
        """Connect to Cloud Backend WebSocket"""
        ws_url = f"{self.cloud_url}/ws/control?local_system_id={self.local_system_id}"
        
        try:
            self.websocket = await websockets.connect(ws_url)
            print(f"[WS Client] Connected to {self.cloud_url}")
            self.reconnect_delay = 5  # Reset delay on successful connection
            return True
        except Exception as e:
            print(f"[WS Client] Connection failed: {e}")
            return False
    
    async def send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        if self.websocket:
            try:
                heartbeat_msg = {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                    "local_system_id": self.local_system_id
                }
                await self.websocket.send(json.dumps(heartbeat_msg))
            except Exception as e:
                print(f"[WS Client] Heartbeat failed: {e}")
    
    async def handle_command(self, command: dict):
        """
        Handle incoming command from Cloud
        
        Expected format:
        {
            "id": "command-uuid",
            "type": "add_product",
            "payload": {...},
            "timestamp": "..."
        }
        """
        command_id = command.get("id")
        command_type = command.get("type")
        payload = command.get("payload", {})
        
        print(f"[WS Client] Received command: {command_type} (ID: {command_id})")
        
        try:
            # Find handler
            if command_type not in self.command_handlers:
                raise Exception(f"Unknown command type: {command_type}")
            
            handler = self.command_handlers[command_type]
            
            # Execute handler
            result = await handler(payload)
            
            # Send success response
            response = {
                "type": "response",
                "command_id": command_id,
                "status": "success",
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.websocket.send(json.dumps(response))
            print(f"[WS Client] Command {command_type} executed successfully")
            
        except Exception as e:
            # Send error response
            print(f"[WS Client] Command {command_type} failed: {e}")
            traceback.print_exc()
            
            error_response = {
                "type": "response",
                "command_id": command_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            if self.websocket:
                await self.websocket.send(json.dumps(error_response))
    
    async def listen(self):
        """Listen for messages from Cloud"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    # Handle different message types
                    if "type" in data and data["type"] != "heartbeat":
                        # It's a command
                        await self.handle_command(data)
                        
                except json.JSONDecodeError:
                    print(f"[WS Client] Invalid JSON received: {message}")
                except Exception as e:
                    print(f"[WS Client] Error handling message: {e}")
                    traceback.print_exc()
                    
        except websockets.exceptions.ConnectionClosed:
            print("[WS Client] Connection closed by server")
        except Exception as e:
            print(f"[WS Client] Listen error: {e}")
    
    async def heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            await self.send_heartbeat()
            await asyncio.sleep(10)  # Every 10 seconds
    
    async def run(self):
        """Main run loop with auto-reconnect"""
        self.running = True
        
        while self.running:
            # Try to connect
            if await self.connect():
                # Start heartbeat task
                heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                
                # Listen for messages
                await self.listen()
                
                # Cancel heartbeat when disconnected
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Reconnect with exponential backoff
            if self.running:
                print(f"[WS Client] Reconnecting in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def stop(self):
        """Stop the client"""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())


# Global instance
ws_client = None


def get_ws_client(cloud_url: str = None):
    """Get or create global WebSocket client"""
    global ws_client
    if ws_client is None and cloud_url:
        ws_client = CloudWebSocketClient(cloud_url)
    return ws_client
