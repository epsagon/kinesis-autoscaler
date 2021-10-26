"""
Kinesis stream downscaler
"""
import math
from datetime import datetime, timedelta
from kinesis_autoscaler.kinesis_autoscaler import KinesisAutoscaler, CW_CLIENT


class KinesisDownscaler(KinesisAutoscaler):
    """
    Kinesis stream downscaler
    """

    scaling_type = "SCALE_DOWN"

    def get_target_shard_count(self, current_shard_count: int) -> int:
        """
        Calculates the scale-down operation target shard count.
        This is done by quering for the max usage factor and calculating
        the shard count that will result in a usage factor of 50% at the end
        of the scaling operation.
        :param current_shard_count: the current shard count of the stream
        :return: the shard count the stream should scale to
        """
        max_usage_factor = self.get_max_usage_factor(current_shard_count)
        used_shard_count = current_shard_count * max_usage_factor
        target_shard_count = math.ceil(used_shard_count * 2)
        min_possible_shard_count = math.ceil(current_shard_count / 2)
        return max(min_possible_shard_count, target_shard_count)

    def get_max_usage_factor(self, current_shard_count: int) -> float:
        """
        Queries for the stream max usage factor in the last 24 hours
        (5m aggregation) and returns the max data point value.
        :param current_shard_count: the current shard count of the stream
        :return: the maximum usage factor of the stream
        """
        current_datetime = datetime.now()

        response = CW_CLIENT.get_metric_data(
            StartTime=current_datetime - timedelta(days=1),
            EndTime=current_datetime,
            MetricDataQueries=[
                {
                    "Id": "shardCount",
                    "Expression": str(current_shard_count),
                    "ReturnData": False,
                },
                {
                    "Id": "incomingBytes",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/Kinesis",
                            "MetricName": "IncomingBytes",
                            "Dimensions": [
                                {"Name": "StreamName", "Value": self.stream_name},
                            ],
                        },
                        "Period": 300,
                        "Stat": "Sum",
                    },
                    "ReturnData": False,
                },
                {
                    "Id": "incomingRecords",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/Kinesis",
                            "MetricName": "IncomingRecords",
                            "Dimensions": [
                                {"Name": "StreamName", "Value": self.stream_name},
                            ],
                        },
                        "Period": 300,
                        "Stat": "Sum",
                    },
                    "ReturnData": False,
                },
                {
                    "Id": "incomingBytesFilledWithZeroForMissingDataPoints",
                    "Expression": "FILL(incomingBytes,0)",
                    "ReturnData": False,
                },
                {
                    "Id": "incomingRecordsFilledWithZeroForMissingDataPoints",
                    "Expression": "FILL(incomingRecords,0)",
                    "ReturnData": False,
                },
                {
                    "Id": "incomingBytesUsageFactor",
                    "Expression": "incomingBytesFilledWithZeroForMissingDataPoints/(1024*1024*60*5*shardCount)",
                    "ReturnData": False,
                },
                {
                    "Id": "incomingRecordsUsageFactor",
                    "Expression": "incomingRecordsFilledWithZeroForMissingDataPoints/(1000*60*5*shardCount)",
                    "ReturnData": False,
                },
                {
                    "Id": "maxIncomingUsageFactor",
                    "Expression": "MAX([incomingBytesUsageFactor,incomingRecordsUsageFactor])",
                    "ReturnData": True,
                },
            ],
        )

        max_usage_factor = max(response["MetricDataResults"][0]["Values"])
        return max_usage_factor
