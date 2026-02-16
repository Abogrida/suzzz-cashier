"""
WebSocket Connection Manager for Cloud Backend
Manages connections from Local Systems and routes commands
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket
import uuid


class ConnectionManager:
    def __init__(self):
        # Store active connections: {local_system_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Store pending responses: {command_id: asyncio.Future}
        self.pending_responses: Dict[str, asyncio.Future] = {}
        # Connection metadata: {local_system_id: {last_heartbeat, ...}}
        self.connection_metadata: Dict[str, dict] = {}
    
    async def connect(self, websocket: WebSocket, local_system_id: str):
        """Accept a new WebSocket connection from Local System"""
        await websocket.accept()
        self.active_connections[local_system_id] = websocket
        self.connection_metadata[local_system_id] = {
            "connected_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "status": "online"
        }
        print(f"[WebSocket] Local System {local_system_id} connected")
    
    def disconnect(self, local_system_id: str):
        """Remove a connection"""
        if local_system_id in self.active_connections:
            del self.active_connections[local_system_id]
        if local_system_id in self.connection_metadata:
            self.connection_metadata[local_system_id]["status"] = "offline"
        print(f"[WebSocket] Local System {local_system_id} disconnected")
    
    async def send_command(self, local_system_id: str, command: dict, timeout: int = 30) -> dict:
        """
        Send a command to Local System and wait for response
        
        Args:
            local_system_id: ID of the local system
            command: Command dict with type, payload, etc
            timeout: Max seconds to wait for response
            
        Returns:
            Response dict from local system
            
        Raises:
            Exception if local system offline or timeout
        """
        if local_system_id not in self.active_connections:
            raise Exception("Local System is offline")
        
        # Add command ID
        command_id = str(uuid.uuid4())
        command["id"] = command_id
        command["timestamp"] = datetime.now().isoformat()
        
        # Create future for response
        future = asyncio.Future()
        self.pending_responses[command_id] = future
        
        try:
            # Send command
            websocket = self.active_connections[local_system_id]
            await websocket.send_text(json.dumps(command))
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            raise Exception(f"Command timeout after {timeout}s")
        finally:
            # Cleanup
            if command_id in self.pending_responses:
                del self.pending_responses[command_id]
    
    async def handle_response(self, response: dict):
        """Handle response from Local System"""
        command_id = response.get("command_id")
        if command_id and command_id in self.pending_responses:
            future = self.pending_responses[command_id]
            if not future.done():
                future.set_result(response)
    
    async def handle_message(self, local_system_id: str, message: str):
        """Handle incoming message from Local System"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "response":
                # Response to a command
                await self.handle_response(data)
            elif message_type == "heartbeat":
                # Update last heartbeat
                if local_system_id in self.connection_metadata:
                    self.connection_metadata[local_system_id]["last_heartbeat"] = datetime.now().isoformat()
            elif message_type == "data_update":
                # Data sync update - could trigger refresh in Cloud Admin
                pass
            else:
                print(f"[WebSocket] Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            print(f"[WebSocket] Invalid JSON from {local_system_id}")
    
    def get_status(self) -> dict:
        """Get current connection status"""
        return {
            "active_connections": len(self.active_connections),
            "connections": {
                local_id: {
                    "status": meta.get("status"),
                    "last_heartbeat": meta.get("last_heartbeat"),
                    "connected_at": meta.get("connected_at")
                }
                for local_id, meta in self.connection_metadata.items()
            }
        }
    
    def is_online(self, local_system_id: str = "default") -> bool:
        """Check if Local System is online"""
        return local_system_id in self.active_connections


# Global instance
connection_manager = ConnectionManager()
