"""
Kinesis stream base autoscaler
"""
import logging
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
import boto3
from kinesis_autoscaler.models.autoscaler_log import KinesisAutoscalerLog

LOGS_RETENTION_DAYS = 14

CW_CLIENT = boto3.client("cloudwatch")
KINESIS_CLIENT = boto3.client("kinesis")


class KinesisAutoscaler(ABC):
    """
    Kinesis stream base autoscaler
    """

    def __init__(self, event_message: dict):
        """
        Initializes base KinesisAutoscaler instance.
        :param event_message: triggering alarm event
        """
        self.stream_name = None
        self.event_message = event_message

    def scale(self) -> None:
        """
        Scales Kinesis stream according to the triggered alarm.
        """
        self.stream_name = self.parse_stream_name()
        logging.info(f"Started stream scaling process. stream={self.stream_name}")

        alarm_shard_count = self.parse_alarm_shard_count()
        current_shard_count = self.get_current_shard_count()
        if alarm_shard_count != current_shard_count:
            logging.info("Alarm shard count out of sync. Syncing alarms")
            self.update_stream_alarms(current_shard_count)
            return

        target_shard_count = self.get_target_shard_count(current_shard_count)
        if current_shard_count == target_shard_count:
            logging.info(
                "Current and target shard counts are equal. Autoscaling canceled. "
                f"shard_count={current_shard_count}"
            )
            return

        self.update_shard_count(target_shard_count)
        self.update_stream_alarms(target_shard_count)
        self.write_scaling_log_to_db(current_shard_count, target_shard_count)
        logging.info(
            f"Scaling process finished successfully. stream={self.stream_name}"
        )

    def parse_stream_name(self) -> str:
        """
        Parses the stream name from the required metric definitions of the alarm.
        :return: name of the stream to scale
        """
        alarm_metrics = self.event_message["Trigger"]["Metrics"]
        for metric in alarm_metrics:
            if metric["Id"] in ("incomingBytes", "incomingRecords"):
                return metric["MetricStat"]["Metric"]["Dimensions"][0]["value"]

        raise ValueError("Could not parse stream name from alarm metrics")

    def parse_alarm_shard_count(self) -> int:
        """
        Parses the alarm shard count from the required math definition of the alarm.
        :return: stream's current shard count
        """
        alarm_metrics = self.event_message["Trigger"]["Metrics"]
        for metric in alarm_metrics:
            if metric["Id"] == "shardCount":
                return int(metric["Expression"])

        raise ValueError("Could not parse current shard count from alarm metrics")

    def get_current_shard_count(self) -> int:
        """
        Queries and returns the current open shard count of the stream.
        :return: stream's open shard count
        """
        response = KINESIS_CLIENT.describe_stream_summary(StreamName=self.stream_name)
        return response["StreamDescriptionSummary"]["OpenShardCount"]

    def update_stream_alarms(self, target_shard_count: int) -> None:
        """
        Updates the scaled stream alarms (scale-up and scale-down).
        Required after each scaling operation in order to sync the alarms
        thresholds, which are based on the current shard count of the stream.
        :param target_shard_count: the stream target shard count after the scale
        """
        alarm_names = self.get_alarm_names()
        response = CW_CLIENT.describe_alarms(AlarmNames=list(alarm_names.values()))
        if len(response["MetricAlarms"]) != 2:
            logging.warning(
                "Expected to update 2 scaling alarms. "
                f"Found {len(response['MetricAlarms'])} alarms"
            )
        for alarm in response["MetricAlarms"]:
            self.update_existing_alarm(alarm, target_shard_count)
            self.reset_alarm_state(alarm["AlarmName"])

    def get_alarm_names(self) -> dict:
        """
        Returns the stream alarm names based on integration requirement that
        relays on the alarms having the same name but with alarm type difference
        (scale-up/scale-down) in their name.
        :return: dict containing the stream alarm names
        """
        triggered_alarm_name = self.event_message["AlarmName"]
        if "scale-up" in triggered_alarm_name:
            return {
                "scale_up": triggered_alarm_name,
                "scale_down": triggered_alarm_name.replace("scale-up", "scale-down"),
            }
        elif "scale-down" in triggered_alarm_name:
            return {
                "scale_up": triggered_alarm_name.replace("scale-down", "scale-up"),
                "scale_down": triggered_alarm_name,
            }

        raise ValueError(
            "Triggered alarm should contain scale-up/scale-down in its name"
        )

    def update_existing_alarm(self, alarm: dict, target_shard_count: int) -> None:
        """
        Updates a stream alarm with the new shard count and disables
        attached actions from being invoked when unnecessary.
        :param alarm: stream alarm configuration
        :param target_shard_count: the stream target shard count after the scale
        """
        updated_alarm = self.copy_updateable_alarm_fields(alarm)

        should_disable_alarm = (
            "scale-down" in updated_alarm["AlarmName"] and target_shard_count == 1
        )
        updated_alarm["ActionsEnabled"] = not should_disable_alarm

        for metric in updated_alarm["Metrics"]:
            if metric["Id"] == "shardCount":
                metric["Expression"] = str(target_shard_count)

        CW_CLIENT.put_metric_alarm(**updated_alarm)
        logging.info(f"Updated stream alarm. alarm={alarm['AlarmName']}")

    @staticmethod
    def copy_updateable_alarm_fields(alarm: dict) -> dict:
        """
        Creates a dict containing all relevant alarm fields for alarm update.
        This is done because AWS doesn't support updating a single field in an
        existing alarm, the alarm must be updated the same way it is created.
        :param alarm: stream alarm configuration as returned from describe operation
        :return: stream alarm configuration as required for alarm update operation
        """
        alarm_keys_to_copy = (
            "AlarmName",
            "AlarmDescription",
            "ActionsEnabled",
            "OKActions",
            "AlarmActions",
            "InsufficientDataActions",
            "Unit",
            "EvaluationPeriods",
            "DatapointsToAlarm",
            "Threshold",
            "ComparisonOperator",
            "TreatMissingData",
            "EvaluateLowSampleCountPercentile",
            "Metrics",
            "Tags",
            "ThresholdMetricId",
        )
        return {key: alarm[key] for key in alarm_keys_to_copy if key in alarm}

    @staticmethod
    def reset_alarm_state(alarm_name: str) -> None:
        """
        Temporarily resets an alarm state.
        The alarm should be back to its actual state within moments, this is done
        because an alarm in ALARMED state won't be triggered twice even if it should.
        For example, if a stream is scaled up (scale-up alarm is triggered) but
        after the scale-up it is still above the threshold, it won't be triggered
        again without resetting its state. In other words, alarm doesn't invoke actions
        twice without state change.
        :param alarm_name: name of the alarm to reset its state
        """
        CW_CLIENT.set_alarm_state(
            AlarmName=alarm_name,
            StateValue="INSUFFICIENT_DATA",
            StateReason="Shard count metric updated",
        )

    @abstractmethod
    def get_target_shard_count(self, current_shard_count: int) -> int:
        """
        Calculates and returns the target shard count the stream should scale to.
        :param current_shard_count: the stream's current shard count
        :return: the shard count the stream should scale to
        """
        pass

    def update_shard_count(self, target_shard_count: int) -> None:
        response = KINESIS_CLIENT.update_shard_count(
            StreamName=self.stream_name,
            TargetShardCount=target_shard_count,
            ScalingType="UNIFORM_SCALING",
        )
        logging.info(
            f"Updated shard count successfully. stream={response['StreamName']} "
            f"current_count={response['CurrentShardCount']} "
            f"target_count={response['TargetShardCount']}"
        )

    def write_scaling_log_to_db(
        self, current_shard_count: int, target_shard_count: int
    ) -> None:
        """
        Writes scaling log to DB.
        :param current_shard_count: the stream current shard count
        :param target_shard_count: the stream target shard count after the scale
        """
        KinesisAutoscalerLog(
            stream_name=self.stream_name,
            scaling_datetime=datetime.utcnow().replace(tzinfo=timezone.utc),
            shard_count=current_shard_count,
            target_shard_count=target_shard_count,
            scaling_type=self.scaling_type,
            expiration_datetime=timedelta(days=LOGS_RETENTION_DAYS),
        ).save()

    @property
    @abstractmethod
    def scaling_type(self) -> str:
        """
        The scaling type of the operation.
        Used for writing the scaling type in the DB logs.
        """
        pass
