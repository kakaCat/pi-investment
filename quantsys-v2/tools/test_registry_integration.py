#!/usr/bin/env python3
"""Test Agent OS Registry integration for quantsys-v2."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from application.services.registry_client import get_registry_client


async def test_registry():
    """Test registry client operations."""
    print("=== Testing Agent OS Registry Integration ===\n")
    
    client = get_registry_client()
    
    # Test 1: Register
    print("1. Testing registration...")
    success = await client.register()
    if success:
        print("   ✅ Registration successful\n")
    else:
        print("   ❌ Registration failed\n")
        return
    
    # Test 2: Send heartbeat
    print("2. Testing heartbeat...")
    success = await client.heartbeat()
    if success:
        print("   ✅ Heartbeat successful\n")
    else:
        print("   ❌ Heartbeat failed\n")
    
    # Test 3: Keep alive for a few seconds
    print("3. Testing heartbeat loop (10 seconds)...")
    await client.start_heartbeat_loop(interval=5)
    await asyncio.sleep(10)
    await client.stop_heartbeat_loop()
    print("   ✅ Heartbeat loop tested\n")
    
    # Test 4: Unregister
    print("4. Testing unregistration...")
    success = await client.unregister()
    if success:
        print("   ✅ Unregistration successful\n")
    else:
        print("   ❌ Unregistration failed\n")
    
    await client.close()
    print("=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_registry())
