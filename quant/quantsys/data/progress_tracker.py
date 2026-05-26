"""
Progress tracker for backfill operations with resume capability.
"""
import json
import os
from pathlib import Path
from typing import Dict, List


class ProgressTracker:
    """
    Tracks backfill progress and supports resume from interruption.

    Stores progress state in a JSON file with nested structure:
    {
        "symbol": {
            "data_type": ["date1", "date2", ...]
        }
    }
    """

    def __init__(self, state_file: str = ".backfill_progress.json"):
        """
        Initialize progress tracker.

        Args:
            state_file: Path to JSON file for storing progress state
        """
        self.state_file = state_file
        self.state: Dict[str, Dict[str, List[str]]] = {}

    def load(self) -> None:
        """
        Load progress state from JSON file.

        If file doesn't exist or contains invalid JSON, initializes empty state.
        """
        if not os.path.exists(self.state_file):
            self.state = {}
            return

        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except (json.JSONDecodeError, IOError):
            # Handle invalid JSON or read errors gracefully
            self.state = {}

    def save(self) -> None:
        """
        Save current state to JSON file using atomic write.

        Creates parent directory if needed.
        Uses atomic write pattern (write to temp file, then rename).
        """
        # Create parent directory if needed
        state_path = Path(self.state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        temp_file = self.state_file + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(self.state, f, indent=2)

        # Atomic rename (overwrites existing file on Unix)
        os.replace(temp_file, self.state_file)

    def mark_completed(self, symbol: str, data_type: str, date: str) -> None:
        """
        Mark a specific date as completed for a symbol and data type.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            data_type: Type of data ("daily" or "minute")
            date: Date string in ISO format (e.g., "2024-01-01")
        """
        # Initialize nested structure if needed
        if symbol not in self.state:
            self.state[symbol] = {}

        if data_type not in self.state[symbol]:
            self.state[symbol][data_type] = []

        # Add date if not already present (avoid duplicates)
        if date not in self.state[symbol][data_type]:
            self.state[symbol][data_type].append(date)

    def is_completed(self, symbol: str, data_type: str, date: str) -> bool:
        """
        Check if a date is already completed.

        Args:
            symbol: Stock symbol
            data_type: Type of data ("daily" or "minute")
            date: Date string in ISO format

        Returns:
            True if date is completed, False otherwise
        """
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
        """
        completed_dates = self.state.get(symbol, {}).get(data_type, [])
        return [date for date in all_dates if date not in completed_dates]

    def clear_symbol(self, symbol: str) -> None:
        """
        Remove all progress for a symbol (for retry scenarios).

        Args:
            symbol: Stock symbol to clear
        """
        if symbol in self.state:
            del self.state[symbol]
