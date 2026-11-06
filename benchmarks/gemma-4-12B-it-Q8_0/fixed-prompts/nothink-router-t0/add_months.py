import datetime
import calendar

def add_months(y, m, d, n):
    # Calculate total months from year 0 (using 1-based month)
    total_months = (y * 12) + (m - 1) + n
    
    # Calculate new year and month
    new_y = total_months // 12
    new_m = (total_months % 12) + 1
    
    # Handle negative modulo behavior in Python for years
    # (e.g., -1 // 12 is -1, but we want to ensure correct year/month mapping)
    if new_m <= 0:
        new_y -= 1
        new_m += 12
    elif new_m > 12:
        new_y += 1
        new_m -= 12

    # Determine the last valid day of the target month
    _, last_day = calendar.monthrange(new_y, new_m)
    
    # Clamp the day to the maximum available in that month
    new_d = min(d, last_day)
    
    return (new_y, new_m, new_d)
