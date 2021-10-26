"""
Kinesis stream upscaler
"""
import math
from kinesis_autoscaler.kinesis_autoscaler import KinesisAutoscaler


class KinesisUpscaler(KinesisAutoscaler):
    """
    Kinesis stream upscaler
    """

    scaling_type = "SCALE_UP"

    def get_target_shard_count(self, current_shard_count: int) -> int:
        """
        Calculates the scale-up operation target shard count.
        This is done in 25% increments for faster scaling operation
        (as described by AWS in the UpdateShardCount API docs).
        :param current_shard_count: the current shard count of the stream
        :return: the shard count the stream should scale to
        """
        scale_up_pct = 25
        if current_shard_count <= 3:
            scale_up_pct = 100
        elif current_shard_count <= 50:
            scale_up_pct = 50

        return math.ceil(current_shard_count * (1 + scale_up_pct / 100))
