"""
Kinesis autoscaler test utils
"""
from datetime import datetime, timezone


def parse_frozen_date(frozen_date: str) -> datetime:
    """
    Parses frozen date string as datetime object.
    :param frozen_date: date string in format Y-m-d (e.g. 2021-11-16)
    :return: datetime object of the frozen date
    """
    return (
        datetime.strptime(frozen_date, "%Y-%m-%d").utcnow().replace(tzinfo=timezone.utc)
    )
