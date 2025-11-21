import pandas as pd
import numpy as np
import decimal
from decimal import Decimal


def sanitize_string(val, default=''):
    if val is None:
        return default
    if isinstance(val, float) and pd.isna(val):
        return default
    if val == '':
        return default
    return str(val)


def sanitize_float(val, default=None, precision=6):
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
    return sanitize_float(val, default=default, precision=6)


def sanitize_price(val, default=None):
    return sanitize_float(val, default=default, precision=4)


def sanitize_decimal(val, default=None, precision=18, scale=4):
    if val is None or pd.isna(val) or np.isinf(val):
        return default
    
    try:
        return Decimal(str(round(float(val), scale)))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return default
