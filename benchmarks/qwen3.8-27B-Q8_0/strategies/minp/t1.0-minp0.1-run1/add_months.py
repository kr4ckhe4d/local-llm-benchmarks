def add_months(y, m, d, n):
    """
    Add n calendar months to the date (y, m, d).
    
    If the resulting day does not exist in the target month,
    it is clamped to the last day of that month.
    
    Args:
        y: year
        m: month (1-12)
        d: day (1-31, valid for the given month)
        n: number of months to add (can be negative)
    
    Returns:
        A tuple (year, month, day)
    """
    import calendar
    
    # Calculate total months
    total_months = y * 12 + (m - 1) + n
    
    # Calculate new year and month
    new_y = total_months // 12
    new_m = (total_months % 12) + 1
    
    # Handle negative case: Python's floor division and modulo work correctly
    # for negative numbers in a way that keeps new_m in 1-12
    
    # Get the last day of the target month
    last_day = calendar.monthrange(new_y, new_m)[1]
    
    # Clamp the day to the last day if it exceeds
    new_d = min(d, last_day)
    
    return (new_y, new_m, new_d)
