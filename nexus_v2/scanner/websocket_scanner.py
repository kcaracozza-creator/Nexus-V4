"""
NEXUS V2 - WebSocket Scanner Interface
Real-time scanner communication system replacing polling
"""

import asyncio
import websockets
import json
import logging
import threading
from typing import Dict, Any, Callable, Optional
from datetime import datetime
import queue

try:
    from nexus_v2.config import get_config
    _config = get_config()
    _DEFAULT_IP = _config.scanner.scanner_ip
    _DEFAULT_PORT = _config.scanner.scanner_port
except ImportError:
    _DEFAULT_IP = "192.168.1.219"
    _DEFAULT_PORT = 5001

logger = logging.getLogger(__name__)

class WebSocketScannerClient:
    """WebSocket-based scanner client for real-time updates"""

    def __init__(self, scanner_ip=None, scanner_port=None):
        scanner_ip = scanner_ip or _DEFAULT_IP
        scanner_port = scanner_port or _DEFAULT_PORT
        self.scanner_ip = scanner_ip
        self.scanner_port = scanner_port
        self.websocket_url = f"ws://{scanner_ip}:{scanner_port}/ws"
        
        self.websocket = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
        # Event handlers
        self.on_scan_complete = None
        self.on_scan_progress = None
        self.on_connection_status = None
        self.on_error = None
        
        # Message queue for thread-safe communication
        self.message_queue = queue.Queue()
        self.running = False
        
    def set_handlers(self, 
                    on_scan_complete: Optional[Callable] = None,
                    on_scan_progress: Optional[Callable] = None,
                    on_connection_status: Optional[Callable] = None,
                    on_error: Optional[Callable] = None):
        """Set event handlers for real-time updates"""
        self.on_scan_complete = on_scan_complete
        self.on_scan_progress = on_scan_progress  
        self.on_connection_status = on_connection_status
        self.on_error = on_error
        
    def start(self):
        """Start the WebSocket client in a separate thread"""
        if not self.running:
            self.running = True
            self.client_thread = threading.Thread(target=self._run_client, daemon=True)
            self.client_thread.start()
            logger.info(f"WebSocket scanner client started for {self.websocket_url}")
    
    def stop(self):
        """Stop the WebSocket client"""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())
        logger.info("WebSocket scanner client stopped")
    
    def _run_client(self):
        """Run the WebSocket client event loop"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._client_loop())
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
            if self.on_error:
                self.on_error(f"Client error: {e}")
        finally:
            loop.close()
    
    async def _client_loop(self):
        """Main client connection loop with auto-reconnect"""
        while self.running:
            try:
                async with websockets.connect(
                    self.websocket_url,
                    timeout=10,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    self.connected = True
                    self.reconnect_attempts = 0
                    
                    logger.info(f"Connected to scanner WebSocket: {self.websocket_url}")
                    if self.on_connection_status:
                        self.on_connection_status(True, "Connected to scanner")
                    
                    # Listen for messages
                    await self._handle_messages()
                    
            except websockets.exceptions.ConnectionClosedError:
                logger.warning("Scanner WebSocket connection closed")
                self.connected = False
                await self._handle_disconnect()
                
            except websockets.exceptions.InvalidURI:
                logger.error(f"Invalid WebSocket URI: {self.websocket_url}")
                break
                
            except ConnectionRefusedError:
                logger.warning(f"Scanner not available at {self.websocket_url}")
                self.connected = False
                await self._handle_disconnect()
                
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                self.connected = False
                await self._handle_disconnect()
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                await self._process_message(message)
        except websockets.exceptions.ConnectionClosedError:
            logger.info("WebSocket connection closed by server")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            message_type = data.get('type', 'unknown')
            
            logger.debug(f"Received message: {message_type}")
            
            if message_type == 'scan_complete':
                await self._handle_scan_complete(data)
            elif message_type == 'scan_progress':
                await self._handle_scan_progress(data)
            elif message_type == 'error':
                await self._handle_error_message(data)
            elif message_type == 'status':
                await self._handle_status_message(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _handle_scan_complete(self, data: Dict[str, Any]):
        """Handle scan complete message"""
        scan_result = data.get('result', {})
        scan_id = data.get('scan_id')
        
        logger.info(f"Scan complete: {scan_id}")
        
        if self.on_scan_complete:
            # Call handler in thread-safe manner
            self.message_queue.put(('scan_complete', scan_result))
    
    async def _handle_scan_progress(self, data: Dict[str, Any]):
        """Handle scan progress message"""
        progress = data.get('progress', 0)
        stage = data.get('stage', 'unknown')
        scan_id = data.get('scan_id')
        
        if self.on_scan_progress:
            self.message_queue.put(('scan_progress', {
                'progress': progress,
                'stage': stage,
                'scan_id': scan_id
            }))
    
    async def _handle_error_message(self, data: Dict[str, Any]):
        """Handle error message"""
        error = data.get('error', 'Unknown error')
        error_code = data.get('error_code')
        
        logger.error(f"Scanner error: {error} (code: {error_code})")
        
        if self.on_error:
            self.message_queue.put(('error', {
                'error': error,
                'error_code': error_code
            }))
    
    async def _handle_status_message(self, data: Dict[str, Any]):
        """Handle status message"""
        status = data.get('status', {})
        logger.debug(f"Scanner status: {status}")
    
    async def _handle_disconnect(self):
        """Handle disconnection and attempt reconnect"""
        self.connected = False
        
        if self.on_connection_status:
            self.message_queue.put(('connection_status', (False, "Disconnected from scanner")))
        
        if self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            wait_time = min(2 ** self.reconnect_attempts, 30)  # Exponential backoff
            
            logger.info(f"Attempting reconnect {self.reconnect_attempts}/{self.max_reconnect_attempts} in {wait_time}s")
            await asyncio.sleep(wait_time)
        else:
            logger.error("Max reconnection attempts reached")
    
    async def send_command(self, command: str, data: Optional[Dict] = None):
        """Send command to scanner via WebSocket"""
        if not self.connected or not self.websocket:
            logger.error("WebSocket not connected - cannot send command")
            return False
        
        try:
            message = {
                'command': command,
                'timestamp': datetime.now().isoformat(),
                'data': data or {}
            }
            
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent command: {command}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send command {command}: {e}")
            return False
    
    def request_scan(self, region_config: Optional[Dict] = None):
        """Request a new scan with optional region configuration"""
        asyncio.create_task(self.send_command('start_scan', {
            'region_config': region_config or {},
            'timestamp': datetime.now().isoformat()
        }))
    
    def request_status(self):
        """Request current scanner status"""
        asyncio.create_task(self.send_command('get_status'))
    
    def cancel_scan(self):
        """Cancel current scan operation"""
        asyncio.create_task(self.send_command('cancel_scan'))
    
    def get_pending_messages(self):
        """Get pending messages from queue (thread-safe)"""
        messages = []
        try:
            while True:
                message = self.message_queue.get_nowait()
                messages.append(message)
        except queue.Empty:
            pass
        return messages

# Convenience class for easier integration
class RealtimeScannerInterface:
    """High-level interface for real-time scanner communication"""

    def __init__(self, scanner_ip=None, scanner_port=None):
        scanner_ip = scanner_ip or _DEFAULT_IP
        scanner_port = scanner_port or _DEFAULT_PORT
        self.client = WebSocketScannerClient(scanner_ip, scanner_port)
        self.scan_callbacks = []
        self.progress_callbacks = []
        self.status_callbacks = []
        
        # Set up handlers
        self.client.set_handlers(
            on_scan_complete=self._on_scan_complete,
            on_scan_progress=self._on_scan_progress,
            on_connection_status=self._on_connection_status,
            on_error=self._on_error
        )
    
    def start(self):
        """Start the real-time scanner interface"""
        self.client.start()
    
    def stop(self):
        """Stop the real-time scanner interface"""
        self.client.stop()
    
    def add_scan_callback(self, callback: Callable):
        """Add callback for scan completion"""
        self.scan_callbacks.append(callback)
    
    def add_progress_callback(self, callback: Callable):
        """Add callback for scan progress updates"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable):
        """Add callback for connection status updates"""
        self.status_callbacks.append(callback)
    
    def _on_scan_complete(self, result: Dict[str, Any]):
        """Handle scan completion"""
        for callback in self.scan_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Scan callback error: {e}")
    
    def _on_scan_progress(self, progress: Dict[str, Any]):
        """Handle scan progress"""
        for callback in self.progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def _on_connection_status(self, connected: bool, message: str):
        """Handle connection status changes"""
        for callback in self.status_callbacks:
            try:
                callback(connected, message)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    def _on_error(self, error: str):
        """Handle errors"""
        logger.error(f"Scanner error: {error}")
    
    def scan_card(self, region_config: Optional[Dict] = None):
        """Initiate a card scan"""
        self.client.request_scan(region_config)
    
    def get_status(self):
        """Get current scanner status"""
        self.client.request_status()
    
    def is_connected(self) -> bool:
        """Check if connected to scanner"""
        return self.client.connected
    
    def process_messages(self):
        """Process pending messages (call from main thread)"""
        messages = self.client.get_pending_messages()
        
        for msg_type, data in messages:
            if msg_type == 'scan_complete':
                self._on_scan_complete(data)
            elif msg_type == 'scan_progress':
                self._on_scan_progress(data)
            elif msg_type == 'connection_status':
                connected, message = data
                self._on_connection_status(connected, message)
            elif msg_type == 'error':
                self._on_error(data.get('error', 'Unknown error'))