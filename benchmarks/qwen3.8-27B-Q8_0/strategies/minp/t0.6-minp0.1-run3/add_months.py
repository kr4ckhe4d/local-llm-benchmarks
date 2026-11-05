def add_months(y, m, d, n):
    """
    Add n calendar months to the given date (y, m, d).
    
    If the resulting day does not exist in the target month,
    it is clamped to the last day of that month.
    
    Args:
        y: year
        m: month (1-12)
        d: day of month
        n: number of months to add (can be negative)
    
    Returns:
        A tuple (year, month, day) representing the new date.
    """
    # Calculate the total number of months from year 0
    total_months = y * 12 + (m - 1) + n
    
    # Handle negative total months properly
    # Python's divmod handles negative numbers with floor division
    new_year, new_month_idx = divmod(total_months, 12)
    new_month = new_month_idx + 1
    
    # Determine the last day of the target month
    def last_day_of_month(year, month):
        if month == 2:
            # Leap year check
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                return 29
            else:
                return 28
        elif month in (4, 6, 9, 11):
            return 30
        else:
            return 31
    
    max_day = last_day_of_month(new_year, new_month)
    new_day = min(d, max_day)
    
    return (new_year, new_month, new_day)
