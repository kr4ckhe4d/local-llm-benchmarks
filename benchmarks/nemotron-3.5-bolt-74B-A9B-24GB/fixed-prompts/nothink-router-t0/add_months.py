import calendar

def add_months(y, m, d, n):
    total_months = m - 1 + n
    new_y = y + total_months // 12
    new_m = total_months % 12 + 1
    max_day = calendar.monthrange(new_y, new_m)[1]
    new_d = min(d, max_day)
    return (new_y, new_m, new_d)
