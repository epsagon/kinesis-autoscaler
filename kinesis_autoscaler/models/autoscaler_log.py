"""
Autoscaling event log DynamoDB model
"""
from pynamodb.models import Model
from pynamodb.attributes import (
    TTLAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from kinesis_autoscaler.constants import REGION, STAGE


class KinesisAutoscalerLog(Model):
    """
    Represents Kinesis autoscaling event log
    """

    class Meta:
        """
        Table details
        """

        table_name = f"kinesis-autoscaler-logs-{STAGE}"
        region = REGION

    stream_name = UnicodeAttribute(hash_key=True)
    scaling_datetime = UTCDateTimeAttribute(range_key=True)
    shard_count = NumberAttribute()
    target_shard_count = NumberAttribute()
    scaling_type = UnicodeAttribute()
    expiration_datetime = TTLAttribute()
