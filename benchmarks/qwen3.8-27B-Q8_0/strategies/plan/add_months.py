def add_months(y, m, d, n):
    """Return a (year, month, day) tuple n calendar months after the given date.
    
    If the day does not exist in the target month, it is clamped to the last
    day of that month. n may be negative.
    """
    # Convert to absolute month count
    absolute_month = y * 12 + (m - 1) + n
    
    # Recover target year and month using floor division
    target_year = absolute_month // 12
    target_month = absolute_month % 12 + 1
    
    # Determine the last valid day of the target month
    if target_month in (1, 3, 5, 7, 8, 10, 12):
        last_day = 31
    elif target_month in (4, 6, 9, 11):
        last_day = 30
    else:  # February
        if _is_leap_year(target_year):
            last_day = 29
        else:
            last_day = 28
    
    # Clamp the day
    target_day = min(d, last_day)
    
    return (target_year, target_month, target_day)


def _is_leap_year(year):
    """Check if a year is a leap year in the Gregorian calendar."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
