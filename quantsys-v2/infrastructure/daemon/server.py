"""Daemon server main entry point."""
import sys
import asyncio
import json
import signal
from typing import Optional

from infrastructure.daemon.protocol import (
    parse_request,
    create_response,
    create_error_response,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR
)
from infrastructure.daemon.registry import get_global_registry, register_method

# Import handlers to register them
import infrastructure.daemon.handlers  # noqa: F401


# Built-in ping handler
@register_method("ping")
async def ping_handler(params: dict) -> str:
    """Built-in ping handler for health checks."""
    return json.dumps({"status": "ok", "message": "pong"}, ensure_ascii=False)


class DaemonServer:
    """JSON-RPC 2.0 daemon server."""

    def __init__(self):
        """Initialize daemon server."""
        self.registry = get_global_registry()
        self.running = True
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Setup graceful shutdown on SIGTERM/SIGINT."""
        def shutdown_handler(signum, frame):
            self.running = False
            sys.stderr.write("[daemon] Received shutdown signal\n")
            sys.stderr.flush()

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

    async def handle_request(self, line: str) -> str:
        """
        Handle a single JSON-RPC request.

        Args:
            line: Raw request line

        Returns:
            JSON-RPC response string
        """
        request_id = None

        try:
            # Parse request
            try:
                request = parse_request(line)
                request_id = request["id"]
                method = request["method"]
                params = request["params"]
            except ValueError as e:
                error_msg = str(e)
                if "Parse error" in error_msg:
                    return create_error_response(None, PARSE_ERROR, error_msg)
                else:
                    return create_error_response(None, INVALID_REQUEST, error_msg)

            # Get handler
            handler = self.registry.get_handler(method)
            if handler is None:
                return create_error_response(
                    request_id,
                    METHOD_NOT_FOUND,
                    f"Method '{method}' not found"
                )

            # Call handler
            try:
                result = await handler(params)
                return create_response(request_id, result)
            except ValueError as e:
                return create_error_response(
                    request_id,
                    INVALID_PARAMS,
                    f"Invalid params: {e}"
                )
            except Exception as e:
                return create_error_response(
                    request_id,
                    INTERNAL_ERROR,
                    f"Internal error: {e}"
                )

        except Exception as e:
            # Catch-all for unexpected errors
            return create_error_response(
                request_id,
                INTERNAL_ERROR,
                f"Unexpected error: {e}"
            )

    async def run(self):
        """Main server loop - read from stdin, write to stdout."""
        sys.stderr.write("[daemon] QuantSys daemon started\n")
        sys.stderr.flush()

        while self.running:
            try:
                # Read line from stdin (blocking)
                line = await asyncio.get_event_loop().run_in_executor(
                    None,
                    sys.stdin.readline
                )

                if not line:
                    # EOF reached
                    break

                line = line.strip()
                if not line:
                    continue

                # Handle request
                response = await self.handle_request(line)

                # Write response to stdout
                sys.stdout.write(response + "\n")
                sys.stdout.flush()

            except KeyboardInterrupt:
                break
            except Exception as e:
                sys.stderr.write(f"[daemon] Error in main loop: {e}\n")
                sys.stderr.flush()

        sys.stderr.write("[daemon] Shutting down\n")
        sys.stderr.flush()


def main():
    """Main entry point."""
    server = DaemonServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
