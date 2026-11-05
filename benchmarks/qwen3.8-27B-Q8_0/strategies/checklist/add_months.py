import calendar

def add_months(y, m, d, n):
    """
    Returns a (year, month, day) tuple n calendar months after the given date.
    If the day does not exist in the target month, it is clamped to the last day.
    """
    # Convert to 0-based month index for easier arithmetic
    # Total months since year 0
    total_months = y * 12 + (m - 1)
    
    # Add n months
    target_total_months = total_months + n
    
    # Calculate target year and month
    # Handle negative numbers correctly using floor division
    target_year = target_total_months // 12
    target_month_index = target_total_months % 12
    target_month = target_month_index + 1  # Convert back to 1-based
    
    # Determine the last day of the target month
    last_day = calendar.monthrange(target_year, target_month)[1]
    
    # Clamp the day to the last day of the target month if necessary
    target_day = min(d, last_day)
    
    return (target_year, target_month, target_day)
