import calendar

def add_months(y, m, d, n):
    # Convert to zero-indexed month for easier arithmetic
    total_months = y * 12 + (m - 1) + n
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    # Handle negative modulo in Python: % already gives non-negative result for positive divisor
    # But let's be safe: if new_month < 1, adjust
    if new_month < 1:
        new_month += 12
        new_year -= 1
    # Get the last day of the target month
    last_day = calendar.monthrange(new_year, new_month)[1]
    # Clamp the day
    new_day = min(d, last_day)
    return (new_year, new_month, new_day)
