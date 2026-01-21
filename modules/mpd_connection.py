"""
MPD Connection Module

Manages connection lifecycle to MPD (Music Player Daemon).
Handles connect/disconnect/auto-reconnect logic ONLY.

Architecture: Single Responsibility Principle (SRP)
- ONLY connection lifecycle management
- NO business logic (playback, search, etc.)
- Reusable across different MPD clients
"""

import logging
from typing import Optional
from contextlib import contextmanager

try:
    from mpd import MPDClient, ConnectionError as MPDConnectionError
except ImportError:
    MPDClient = None
    MPDConnectionError = Exception

from modules.base_module import BaseModule


class MPDConnection(BaseModule):
    """
    MPD connection lifecycle manager.

    Handles connecting, disconnecting, and automatic reconnection.
    Thread-safe context manager for reliable MPD operations.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6600,
        timeout: int = 10,
        debug: bool = False,
        verbose: bool = True,
        event_bus=None,
    ):
        """
        Initialize MPD connection manager.

        Args:
            host: MPD server hostname
            port: MPD server port
            timeout: Connection timeout in seconds
            debug: Enable debug logging
        """
        if MPDClient is None:
            raise RuntimeError("python-mpd2 is not installed; MPD control unavailable")

        super().__init__(__name__, debug=debug, verbose=verbose, event_bus=event_bus)
        self.host = host
        self.port = port
        self.timeout = timeout

        # Connection state
        self._client: Optional[MPDClient] = MPDClient()
        self._client.timeout = timeout
        self._connected = False

        if debug:
            self.logger.setLevel(logging.DEBUG)

    @property
    def client(self) -> MPDClient:
        """
        Get MPD client instance.

        Returns:
            MPDClient instance (may not be connected - use ensure_connection)
        """
        return self._client

    @property
    def is_connected(self) -> bool:
        """
        Check if currently connected to MPD.

        Returns:
            True if connected
        """
        return self._connected

    def connect(self) -> bool:
        """
        Connect to MPD server.

        Returns:
            True if connected successfully
        """
        try:
            if not self._connected:
                try:
                    self._client.connect(self.host, self.port)
                except (MPDConnectionError, ConnectionError) as conn_err:
                    # Handle "Already connected" case
                    if "Already connected" in str(conn_err):
                        self.logger.debug("MPD client already connected, reusing connection")
                    else:
                        raise  # Re-raise other connection errors

                self._connected = True
                self.logger.info(f"Connected to MPD at {self.host}:{self.port}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to MPD at {self.host}:{self.port}: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from MPD server"""
        try:
            if self._connected:
                self._client.close()
                self._client.disconnect()
                self._connected = False
                self.logger.info("Disconnected from MPD")
        except Exception as e:
            self.logger.warning(f"Error disconnecting from MPD: {e}")
            self._connected = False  # Force disconnect flag even if cleanup failed

    @contextmanager
    def ensure_connection(self):
        """
        Context manager to ensure MPD connection with auto-reconnect.

        Usage:
            with mpd_conn.ensure_connection():
                mpd_conn.client.status()

        Yields:
            None (use client property to access MPDClient)

        Raises:
            Re-raises connection errors after reconnect attempt
        """
        if not self._connected:
            self.connect()

        try:
            yield
        except (MPDConnectionError, ConnectionError, OSError) as e:
            # Only reconnect if we were previously connected (avoid double reconnect)
            if self._connected:
                self.logger.warning(f"MPD connection lost: {e}. Reconnecting...")
                self._connected = False
                self.connect()
            raise  # Let caller retry if needed

    def ping(self) -> bool:
        """
        Ping MPD server to verify connection is alive.

        Returns:
            True if connection is healthy
        """
        try:
            with self.ensure_connection():
                self._client.ping()
            return True
        except Exception as e:
            self.logger.debug(f"MPD ping failed: {e}")
            return False

    def __del__(self):
        """Cleanup: disconnect on destruction"""
        try:
            self.disconnect()
        except Exception:
            pass  # Ignore errors during cleanup
