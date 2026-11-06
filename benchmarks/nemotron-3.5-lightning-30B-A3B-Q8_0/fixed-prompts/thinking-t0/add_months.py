import calendar

def add_months(y, m, d, n):
    total_months = y * 12 + m - 1 + n
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    _, last_day = calendar.monthrange(new_year, new_month)
    new_day = min(d, last_day)
    return (new_year, new_month, new_day)
