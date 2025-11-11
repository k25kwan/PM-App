"""
Data sanitization utilities for SQL Server inserts.
Handles NaN, None, infinity, and type conversion edge cases.
"""
import pandas as pd
import numpy as np
import decimal
from decimal import Decimal


def sanitize_string(val, default=''):
    """
    Sanitize string/metadata values for SQL insert.
    
    Args:
        val: Input value (can be str, float, None)
        default: Default value if input is invalid (default: '')
    
    Returns:
        str: Sanitized string value
    """
    if val is None:
        return default
    if isinstance(val, float) and pd.isna(val):
        return default
    if val == '':
        return default
    return str(val)


def sanitize_float(val, default=None, precision=6):
    """
    Sanitize numeric values for SQL insert.
    Converts NaN/infinity to None (SQL NULL).
    
    Args:
        val: Input value (can be numeric, None, NaN, inf)
        default: Default value if input is invalid (default: None)
        precision: Number of decimal places to round to (default: 6)
    
    Returns:
        float or None: Sanitized numeric value or None
    """
    if val is None:
        return default
    if pd.isna(val):
        return default
    if np.isinf(val):
        return default
    
    try:
        result = float(val)
        if precision is not None:
            result = round(result, precision)
        return result
    except (ValueError, TypeError):
        return default


def sanitize_return(val, default=None):
    """
    Sanitize return/percentage values for SQL insert.
    Special handling for financial returns (6 decimal places).
    
    Args:
        val: Input return value (can be numeric, None, NaN, inf)
        default: Default value if input is invalid (default: None)
    
    Returns:
        float or None: Sanitized return value or None
    """
    return sanitize_float(val, default=default, precision=6)


def sanitize_price(val, default=None):
    """
    Sanitize price values for SQL insert.
    Uses 4 decimal places for prices.
    
    Args:
        val: Input price value (can be numeric, None, NaN, inf)
        default: Default value if input is invalid (default: None)
    
    Returns:
        float or None: Sanitized price value or None
    """
    return sanitize_float(val, default=default, precision=4)


def sanitize_decimal(val, default=None, precision=18, scale=4):
    """
    Sanitize values for DECIMAL SQL columns.
    
    Args:
        val: Input value
        default: Default value if input is invalid (default: None)
        precision: Total number of digits (default: 18)
        scale: Number of decimal places (default: 4)
    
    Returns:
        Decimal or None: Sanitized decimal value or None
    """
    if val is None or pd.isna(val) or np.isinf(val):
        return default
    
    try:
        # Convert to Decimal with specified precision/scale
        return Decimal(str(round(float(val), scale)))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return default
