def add_months(y, m, d, n):
    """
    Add n calendar months to the given date (y, m, d).
    If the resulting day does not exist in the target month,
    it is clamped to the last day of that month.
    Handles negative n and year rollover in both directions.
    """
    import calendar

    # Total months from year 0, month 0
    total_months = y * 12 + (m - 1) + n
    # Normalize total_months to get new year and month
    new_y = total_months // 12
    new_m = total_months % 12 + 1

    # Clamp day to the last day of the target month
    last_day = calendar.monthrange(new_y, new_m)[1]
    new_d = min(d, last_day)

    return (new_y, new_m, new_d)
