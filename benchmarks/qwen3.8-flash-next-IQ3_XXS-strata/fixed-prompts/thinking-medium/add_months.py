def add_months(y, m, d, n):
    total = (m - 1) + n
    new_year = y + total // 12
    new_month = total % 12 + 1

    def last_day(year, month):
        if month in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if month in (4, 6, 9, 11):
            return 30
        # February
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        return 28

    new_day = min(d, last_day(new_year, new_month))
    return (new_year, new_month, new_day)
