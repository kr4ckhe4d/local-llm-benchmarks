def add_months(y, m, d, n):
    def is_leap(year):
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    def days_in_month(year, month):
        if month == 2:
            return 29 if is_leap(year) else 28
        return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]

    total_months = y * 12 + (m - 1) + n
    ty, tm = divmod(total_months, 12)
    tm += 1
    td = min(d, days_in_month(ty, tm))
    return (ty, tm, td)
