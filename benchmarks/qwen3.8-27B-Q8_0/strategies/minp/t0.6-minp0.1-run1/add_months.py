def add_months(y, m, d, n):
    """
    Add n calendar months to the date (y, m, d).
    Returns a tuple (year, month, day).
    If the resulting day exceeds the number of days in the target month,
    it is clamped to the last day of that month.
    n can be negative.
    """
    # Convert to zero-indexed month for easier arithmetic
    total_months = y * 12 + (m - 1) + n
    # Handle negative total_months correctly (Python's % and // handle this)
    new_y = total_months // 12
    new_m = total_months % 12 + 1  # Convert back to 1-indexed month
    
    # Get the last day of the target month
    # Use a helper to determine days in month
    def days_in_month(year, month):
        if month in (1, 3, 5, 7, 8, 10, 12):
            return 31
        elif month in (4, 6, 9, 11):
            return 30
        elif month == 2:
            # Leap year check
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                return 29
            else:
                return 28
    
    last_day = days_in_month(new_y, new_m)
    new_d = min(d, last_day)
    
    return (new_y, new_m, new_d)
