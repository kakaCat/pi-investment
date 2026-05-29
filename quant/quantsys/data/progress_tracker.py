"""
Progress tracker for backfill operations with resume capability.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Set


class ProgressTracker:
    """
    Tracks backfill progress and supports resume from interruption.

    Stores progress state in a JSON file with nested structure:
    {
        "symbol": {
            "data_type": ["date1", "date2", ...]
        }
    }

    Note: This tracker is designed for single-process use. Concurrent access
    from multiple processes may result in lost updates.
    """

    VALID_DATA_TYPES = {"daily", "minute"}

    def __init__(self, state_file: str = ".backfill_progress.json"):
        """
        Initialize progress tracker.

        Args:
            state_file: Path to JSON file for storing progress state
        """
        self.state_file = state_file
        self.state: Dict[str, Dict[str, Set[str]]] = {}

    def load(self) -> None:
        """
        Load progress state from JSON file.

        If file doesn't exist or contains invalid JSON, initializes empty state.
        Converts lists from JSON to sets for O(1) lookup performance.
        """
        if not os.path.exists(self.state_file):
            self.state = {}
            return

        try:
            with open(self.state_file, 'r') as f:
                loaded_state = json.load(f)
                # Convert lists to sets for O(1) lookups
                self.state = {
                    symbol: {
                        data_type: set(dates)
                        for data_type, dates in data_types.items()
                    }
                    for symbol, data_types in loaded_state.items()
                }
        except (json.JSONDecodeError, IOError):
            # Handle invalid JSON or read errors gracefully
            self.state = {}

    def reset(self) -> None:
        """
        Reset progress tracker by clearing state and removing state file.
        """
        self.state = {}
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)

    def save(self) -> None:
        """
        Save current state to JSON file using atomic write.

        Creates parent directory if needed.
        Uses atomic write pattern (write to temp file, then rename).
        Converts sets to lists for JSON serialization.
        """
        # Create parent directory if needed
        state_path = Path(self.state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        temp_file = self.state_file + '.tmp'
        try:
            # Convert sets to lists for JSON serialization
            serializable_state = {
                symbol: {
                    data_type: list(dates)
                    for data_type, dates in data_types.items()
                }
                for symbol, data_types in self.state.items()
            }

            with open(temp_file, 'w') as f:
                json.dump(serializable_state, f, indent=2)

            # Atomic rename (overwrites existing file on Unix)
            os.replace(temp_file, self.state_file)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            raise

    def mark_completed(self, symbol: str, data_type: str, date: str) -> None:
        """
        Mark a specific date as completed for a symbol and data type.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            data_type: Type of data ("daily" or "minute")
            date: Date string in ISO format (e.g., "2024-01-01")

        Raises:
            ValueError: If data_type is not "daily" or "minute"
        """
        if data_type not in self.VALID_DATA_TYPES:
            raise ValueError(f"Invalid data_type '{data_type}'. Must be one of {self.VALID_DATA_TYPES}")

        # Initialize nested structure if needed
        if symbol not in self.state:
            self.state[symbol] = {}

        if data_type not in self.state[symbol]:
            self.state[symbol][data_type] = set()

        # Add date (set automatically handles duplicates)
        self.state[symbol][data_type].add(date)

    def is_completed(self, symbol: str, data_type: str, date: str) -> bool:
        """
        Check if a date is already completed.

        Args:
            symbol: Stock symbol
            data_type: Type of data ("daily" or "minute")
            date: Date string in ISO format

        Returns:
            True if date is completed, False otherwise

        Raises:
            ValueError: If data_type is not "daily" or "minute"
        """
        if data_type not in self.VALID_DATA_TYPES:
            raise ValueError(f"Invalid data_type '{data_type}'. Must be one of {self.VALID_DATA_TYPES}")

        return (
            symbol in self.state and
            data_type in self.state[symbol] and
            date in self.state[symbol][data_type]
        )

    def get_pending_dates(
        self,
        symbol: str,
        data_type: str,
        all_dates: List[str]
    ) -> List[str]:
        """
        Filter out completed dates from all_dates.

        Args:
            symbol: Stock symbol
            data_type: Type of data ("daily" or "minute")
            all_dates: List of all dates to check

        Returns:
            List of dates that still need processing

        Raises:
            ValueError: If data_type is not "daily" or "minute"
        """
        if data_type not in self.VALID_DATA_TYPES:
            raise ValueError(f"Invalid data_type '{data_type}'. Must be one of {self.VALID_DATA_TYPES}")

        completed_dates = self.state.get(symbol, {}).get(data_type, set())
        return [date for date in all_dates if date not in completed_dates]

    def clear_symbol(self, symbol: str) -> None:
        """
        Remove all progress for a symbol (for retry scenarios).

        Args:
            symbol: Stock symbol to clear
        """
        if symbol in self.state:
            del self.state[symbol]
