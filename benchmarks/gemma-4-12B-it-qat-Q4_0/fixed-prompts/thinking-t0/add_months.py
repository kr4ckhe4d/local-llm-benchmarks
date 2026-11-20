def add_months(y, m, d, n):
    # Calculate the total number of months from a base point
    # We use (m - 1) to make the month 0-indexed for easier modulo arithmetic
    total_months = (m - 1) + n
    
    # Calculate new year and new month
    # // 12 handles both positive and negative rollover correctly in Python
    new_y = y + (total_months // 12)
    new_m = (total_months % 12) + 1
    
    # Determine the number of days in the target month/year
    if new_m in [4, 6, 9, 11]:
        last_day = 30
    elif new_m == 2:
        # Leap year check
        if (new_y % 4 == 0 and new_y % 100 != 0) or (new_y % 400 == 0):
            last_day = 29
        else:
            last_day = 28
    else:
        last_day = 31
        
    # Clamp the day to the maximum available in that month
    new_d = min(d, last_day)
    
    return (new_y, new_m, new_d)
