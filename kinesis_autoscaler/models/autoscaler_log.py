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

DEFAULT_STAGE = "dev"
DEFAULT_REGION = "us-east-1"


class KinesisAutoscalerLog(Model):
    """
    Represents Kinesis autoscaling event log
    """

    class Meta:
        """
        Table details
        """

        table_name = f"kinesis-autoscaler-logs-{os.getenv('STAGE', DEFAULT_STAGE)}"
        region = os.getenv("AWS_REGION", DEFAULT_REGION)

    stream_name = UnicodeAttribute(hash_key=True)
    scaling_datetime = UTCDateTimeAttribute(range_key=True)
    shard_count = NumberAttribute()
    target_shard_count = NumberAttribute()
    scaling_type = UnicodeAttribute()
    expiration_datetime = TTLAttribute()
