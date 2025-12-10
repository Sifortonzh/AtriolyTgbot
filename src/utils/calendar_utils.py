import datetime
import holidays
from lunarcalendar import Converter, Solar, Lunar

# Define major Chinese Lunar Holidays (Month, Day)
LUNAR_HOLIDAYS = {
    (1, 1): "春节 (Chinese New Year)",
    (1, 15): "元宵节 (Lantern Festival)",
    (5, 5): "端午节 (Dragon Boat Festival)",
    (8, 15): "中秋节 (Mid-Autumn Festival)",
    (9, 9): "重阳节 (Double Ninth Festival)",
    (12, 30): "除夕 (Chinese New Year's Eve)" # Approximation
}

def get_today_holidays() -> list[str]:
    """Returns a list of holiday names for today (UTC+8)."""
    # 1. Get current time in China
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    events = []

    # 2. Check Western/International Holidays (CN + US defaults)
    cn_holidays = holidays.CN(years=now.year)
    if now.date() in cn_holidays:
        events.append(cn_holidays.get(now.date()))
    
    # Add manual Western ones if not in lib
    if now.month == 2 and now.day == 14: events.append("Valentine's Day")
    if now.month == 12 and now.day == 25: events.append("Christmas")

    # 3. Check Lunar Holidays
    solar = Solar(now.year, now.month, now.day)
    lunar = Converter.Solar2Lunar(solar)
    
    key = (lunar.month, lunar.day)
    if key in LUNAR_HOLIDAYS:
        events.append(LUNAR_HOLIDAYS[key])

    return events