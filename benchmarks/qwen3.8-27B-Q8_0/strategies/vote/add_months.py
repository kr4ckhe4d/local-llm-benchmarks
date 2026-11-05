def add_months(y, m, d, n):
    """Return a (year, month, day) tuple n calendar months after the given date.
    
    n may be negative. If the day does not exist in the target month,
    it is clamped to the last day of that month.
    """
    import calendar
    
    # Convert to zero-indexed month for easier arithmetic
    # Total months from year 0
    total_months = y * 12 + (m - 1)
    
    # Add n months
    new_total_months = total_months + n
    
    # Handle potential negative years
    # We need to be careful with Python's floor division for negative numbers
    # We want to compute new_year and new_month (1-12)
    # Using divmod carefully
    # For negative values, divmod gives floor division
    # Example: -1 // 12 = -1, -1 % 12 = 11 -> year -1, month 12? No, that's wrong.
    # Let's think: if total_months = -1, that means December of year -1? 
    # Actually, let's use a different approach.
    
    # Let's normalize: new_total_months is the number of months from year 0, month 1.
    # So year 1, month 1 = 12
    # Year 0, month 1 = 0
    # Year -1, month 1 = -12
    
    # We want new_year such that new_year * 12 <= new_total_months < (new_year+1)*12
    # And new_month = (new_total_months - new_year * 12) + 1
    
    # For positive: new_year = new_total_months // 12, new_month = (new_total_months % 12) + 1
    # For negative: e.g., new_total_months = -1
    #   We want year 0, month 12? No. 
    #   Let's say new_total_months = -1 means 1 month before year 0, month 1.
    #   That would be year -1, month 12? Or year 0, month 0? 
    #   Actually, let's define: month index 0 = year 0, month 1.
    #   So new_total_months = 0 -> (0, 1)
    #   new_total_months = 11 -> (0, 12)
    #   new_total_months = 12 -> (1, 1)
    #   new_total_months = -1 -> (-1, 12)
    #   new_total_months = -12 -> (-1, 1)
    
    # Using divmod:
    if new_total_months >= 0:
        new_year = new_total_months // 12
        new_month = (new_total_months % 12) + 1
    else:
        # For negative, we want to floor divide
        # -1 // 12 = -1, -1 % 12 = 11 -> new_year = -1, new_month = 11 + 1 = 12. Correct.
        # -12 // 12 = -1, -12 % 12 = 0 -> new_year = -1, new_month = 0 + 1 = 1. Correct.
        # -13 // 12 = -2, -13 % 12 = 11 -> new_year = -2, new_month = 12. Correct.
        new_year = new_total_months // 12
        new_month = (new_total_months % 12) + 1
    
    # Now clamp the day to the last day of new_month in new_year
    # Get the last day of the month
    if new_month == 12:
        next_year = new_year + 1
        next_month = 1
    else:
        next_year = new_year
        next_month = new_month + 1
    
    # Use calendar module to get the number of days in the month
    # calendar.monthrange(year, month) returns (weekday, number of days)
    # But calendar.monthrange may not handle year 0 or negative years well in all Python versions
    # Let's implement a helper to check if a year is a leap year
    def is_leap(year):
        return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if new_month == 2 and is_leap(new_year):
        max_day = 29
    else:
        max_day = days_in_month[new_month - 1]
    
    new_day = min(d, max_day)
    
    return (new_year, new_month, new_day)
