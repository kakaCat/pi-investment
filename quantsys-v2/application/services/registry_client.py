"""Agent OS Registry integration for quantsys-v2.

Automatically registers quantsys-v2 as an Agent to Agent OS Registry
on startup and maintains heartbeat connection.

Architecture:
- Registers on FastAPI lifespan startup
- Sends heartbeat every 30 seconds
- Unregisters on shutdown (graceful)
- Falls back silently if Agent OS unavailable
"""
import asyncio
import logging
import os
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class QuantsysV2RegistryClient:
    """Registry client for quantsys-v2 to register with Agent OS."""
    
    def __init__(self, agent_os_url: str = "http://127.0.0.1:8080"):
        """Initialize registry client.
        
        Args:
            agent_os_url: Agent OS base URL
        """
        self.agent_os_url = agent_os_url.rstrip('/')
        self.agent_id = f"quantsys-v2-{os.getpid()}"
        self.session_id = None
        self.client = httpx.AsyncClient(timeout=10.0)
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.registered = False
        
    async def register(self) -> bool:
        """Register quantsys-v2 to Agent OS Registry.
        
        Returns:
            True if registration successful, False otherwise
        """
        try:
            payload = {
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "type": "trading-system",
                "capabilities": [
                    "kline-data",
                    "market-analysis", 
                    "signal-generation",
                    "backtesting",
                    "portfolio-management",
                    "risk-management",
                    "trading-execution"
                ],
                "status": "idle",
                "host": "127.0.0.1",
                "port": 5001,
                "pid": os.getpid(),
                "version": "2.0",
                "metadata": {
                    "service": "quantsys-v2",
                    "description": "Quantitative Trading System Backend",
                    "api_base": "http://127.0.0.1:5001"
                }
            }
            
            response = await self.client.post(
                f"{self.agent_os_url}/api/v1/registry/agents/register",
                json=payload
            )
            
            if response.status_code in (200, 201):
                result = response.json()
                logger.info(
                    f"✅ Registered to Agent OS Registry: "
                    f"agent_id={self.agent_id}, id={result.get('id')}"
                )
                self.registered = True
                self.session_id = result.get('session_id')
                return True
            else:
                logger.warning(
                    f"⚠️ Registry registration failed: "
                    f"{response.status_code} {response.text}"
                )
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to register with Agent OS Registry: {e}")
            return False
    
    async def heartbeat(self) -> bool:
        """Send heartbeat to Agent OS Registry.
        
        Returns:
            True if heartbeat successful, False otherwise
        """
        if not self.registered:
            return False
            
        try:
            payload = {
                "agent_id": self.agent_id,
                "status": "idle",  # TODO: 根据实际状态动态设置
                "metadata": {
                    "timestamp": asyncio.get_event_loop().time()
                }
            }
            
            response = await self.client.post(
                f"{self.agent_os_url}/api/v1/registry/agents/heartbeat",
                json=payload
            )
            
            if response.status_code == 200:
                logger.debug(f"💓 Heartbeat sent: {self.agent_id}")
                return True
            else:
                logger.warning(
                    f"⚠️ Heartbeat failed: "
                    f"{response.status_code} {response.text}"
                )
                return False
                
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
            return False
    
    async def unregister(self) -> bool:
        """Unregister from Agent OS Registry.
        
        Returns:
            True if unregistration successful, False otherwise
        """
        if not self.registered:
            return True
            
        try:
            payload = {
                "agent_id": self.agent_id
            }
            
            response = await self.client.post(
                f"{self.agent_os_url}/api/v1/registry/agents/unregister",
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Unregistered from Agent OS: {self.agent_id}")
                self.registered = False
                return True
            else:
                logger.warning(
                    f"⚠️ Unregister failed: "
                    f"{response.status_code} {response.text}"
                )
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to unregister: {e}")
            return False
    
    async def start_heartbeat_loop(self, interval: int = 30):
        """Start background heartbeat loop.
        
        Args:
            interval: Heartbeat interval in seconds (default: 30)
        """
        if self.heartbeat_task is not None:
            logger.warning("Heartbeat loop already running")
            return
            
        async def _heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.heartbeat()
                except asyncio.CancelledError:
                    logger.info("Heartbeat loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Heartbeat loop error: {e}")
        
        self.heartbeat_task = asyncio.create_task(_heartbeat_loop())
        logger.info(f"🔄 Started heartbeat loop (interval={interval}s)")
    
    async def stop_heartbeat_loop(self):
        """Stop background heartbeat loop."""
        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
            logger.info("⏹️ Stopped heartbeat loop")
    
    async def close(self):
        """Close the registry client and release resources."""
        await self.stop_heartbeat_loop()
        await self.unregister()
        await self.client.aclose()
        logger.debug("QuantsysV2RegistryClient closed")


# ==================== Global Singleton ====================

_registry_client: Optional[QuantsysV2RegistryClient] = None


def get_registry_client(
    agent_os_url: str = "http://127.0.0.1:8080"
) -> QuantsysV2RegistryClient:
    """Get global registry client instance.
    
    Args:
        agent_os_url: Agent OS base URL
        
    Returns:
        QuantsysV2RegistryClient instance
    """
    global _registry_client
    if _registry_client is None or _registry_client.client.is_closed:
        _registry_client = QuantsysV2RegistryClient(agent_os_url=agent_os_url)
    return _registry_client


async def close_registry_client():
    """Close the global registry client."""
    global _registry_client
    if _registry_client is not None:
        await _registry_client.close()
        _registry_client = None
