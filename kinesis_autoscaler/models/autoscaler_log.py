"""
Autoscaling event log DynamoDB model
"""
import os
from pynamodb.models import Model
from pynamodb.attributes import (
    TTLAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)


class KinesisAutoscalerLog(Model):
    """
    Represents Kinesis autoscaling event log
    """

    class Meta:
        """
        Table details
        """

        table_name = f"kinesis-autoscaler-logs-{os.environ['STAGE']}"
        region = os.environ["AWS_REGION"]

    stream_name = UnicodeAttribute(hash_key=True)
    scaling_datetime = UTCDateTimeAttribute(range_key=True)
    shard_count = NumberAttribute()
    target_shard_count = NumberAttribute()
    scaling_type = UnicodeAttribute()
    expiration_datetime = TTLAttribute()
