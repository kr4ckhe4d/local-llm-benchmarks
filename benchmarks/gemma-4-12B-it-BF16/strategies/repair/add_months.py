import datetime
import calendar

def add_months(y, m, d, n):
    # Calculate total months from year 0 (approximate)
    # Using 1-based month indexing for calculation
    total_months = (y * 12) + (m - 1) + n
    
    new_y = total_months // 12
    new_m = (total_months % 12) + 1
    
    # Handle negative modulo behavior in Python for years
    # (e.g., if total_months is -1, new_y becomes -1 and new_m becomes 11)
    # This logic holds because // and % in Python follow the floor of the result.
    
    # Determine the last valid day of the target month/year
    _, last_day = calendar.monthrange(new_y, new_m)
    
    # Clamp the day to the maximum available in that month
    new_d = min(d, last_day)
    
    return (new_y, new_m, new_d)
