"""Shared pytest fixtures for the MAC Converter regression suite."""

import os
import sys

# Ensure the worktree root is on sys.path so tests can import mac_formats etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
