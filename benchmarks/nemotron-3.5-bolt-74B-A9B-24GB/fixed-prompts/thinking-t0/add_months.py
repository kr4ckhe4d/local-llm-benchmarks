def add_months(y, m, d, n):
    total_months = y * 12 + m - 1 + n
    new_y = total_months // 12
    new_m = total_months % 12 + 1

    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    max_day = days_in_month[new_m - 1]

    if new_m == 2 and ((new_y % 4 == 0 and new_y % 100 != 0) or (new_y % 400 == 0)):
        max_day = 29

    new_d = min(d, max_day)
    return (new_y, new_m, new_d)
