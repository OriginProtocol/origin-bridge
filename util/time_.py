import datetime


def unix_to_datetime(unix_timestamp):
    return datetime.datetime.utcfromtimestamp(
        int(unix_timestamp)
    )

def to_js_timestamp(date_time):
    return int(date_time.timestamp() * 1000)

