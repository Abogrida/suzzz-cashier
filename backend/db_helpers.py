# -*- coding: utf-8 -*-
"""
Helper function to safely access sqlite3.Row objects
"""

def safe_get(row, key, default=None):
    """
    Safely get value from sqlite3.Row object
    
    Args:
        row: sqlite3.Row object
        key: column name
        default: default value if key doesn't exist
    
    Returns:
        Value from row or default
    """
    try:
        return row[key]
    except (KeyError, IndexError):
        return default
