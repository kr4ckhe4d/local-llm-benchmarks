def add_months(y, m, d, n):
    import calendar

    total_months = y * 12 + (m - 1) + n
    ny, nm = divmod(total_months, 12)
    nm += 1

    last_day = calendar.monthrange(ny, nm)[1]
    return (ny, nm, min(d, last_day))
