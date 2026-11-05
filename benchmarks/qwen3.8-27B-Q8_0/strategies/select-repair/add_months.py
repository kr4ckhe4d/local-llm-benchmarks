def add_months(y, m, d, n):
    """
    Add n calendar months to the given date (y, m, d).
    If the resulting day does not exist in the target month,
    it is clamped to the last day of that month.
    n may be negative.
    """
    import calendar

    # Convert to zero-based month index for easier arithmetic
    # Total months since year 0
    total_months = y * 12 + (m - 1) + n
    # Handle negative total_months correctly
    new_year = total_months // 12
    new_month = total_months % 12 + 1

    # Get the last day of the target month
    last_day = calendar.monthrange(new_year, new_month)[1]

    # Clamp the day
    new_day = min(d, last_day)

    return (new_year, new_month, new_day)
