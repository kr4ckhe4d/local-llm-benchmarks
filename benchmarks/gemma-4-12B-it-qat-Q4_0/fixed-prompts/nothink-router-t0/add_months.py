import datetime
import calendar

def add_months(y, m, d, n):
    # Calculate total months since year 0 (using 1-based month)
    total_months = (y * 12) + (m - 1) + n
    
    # Calculate new year and month
    new_y = total_months // 12
    new_m = (total_months % 12) + 1
    
    # Handle negative modulo behavior in Python for months
    if new_m <= 0:
        new_y -= 1
        new_m += 12
    elif new_m > 12:
        new_y += 1
        new_m -= 12

    # Determine the last day of the target month
    # calendar.monthrange returns (weekday of first day, number of days in month)
    _, last_day = calendar.monthrange(new_y, new_m)
    
    # Clamp the day to the maximum available in that month
    new_d = min(d, last_day)
    
    return (new_y, new_m, new_d)
