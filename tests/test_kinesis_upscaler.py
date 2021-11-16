"""
Kinesis upscaler tests
"""
from datetime import timedelta
from unittest.mock import call
from freezegun import freeze_time
from tests.utils import parse_frozen_date
from kinesis_autoscaler.kinesis_upscaler import KinesisUpscaler
from kinesis_autoscaler.models.autoscaler_log import KinesisAutoscalerLog
from kinesis_autoscaler.kinesis_autoscaler import (
    CW_CLIENT,
    KINESIS_CLIENT,
    LOGS_RETENTION_DAYS,
)

FROZEN_DATE = "2021-11-16"


@freeze_time(FROZEN_DATE)
def test_upscale_operation(mocker):
    """
    Basic sanity test to ensure the scale-up calculation is correct
    and that the required aws requests are sent as expected.
    """
    stream_name = "subscribed-stream"
    scale_up_alarm_name = f"{stream_name}-scale-up"
    scale_down_alarm_name = f"{stream_name}-scale-down"
    current_shard_count = 2
    expected_target_shard_count = 4

    mocker.patch.object(
        KINESIS_CLIENT,
        "describe_stream_summary",
        return_value={
            "StreamDescriptionSummary": {"OpenShardCount": current_shard_count}
        },
    )
    update_shard_count_mock = mocker.patch.object(
        KINESIS_CLIENT,
        "update_shard_count",
        return_value={
            "StreamName": stream_name,
            "CurrentShardCount": current_shard_count,
            "TargetShardCount": expected_target_shard_count,
        },
    )
    mocker.patch.object(
        CW_CLIENT,
        "describe_alarms",
        return_value={
            "MetricAlarms": [
                {
                    "AlarmName": scale_up_alarm_name,
                    "Metrics": [{"Id": "shardCount"}],
                },
                {
                    "AlarmName": scale_down_alarm_name,
                    "Metrics": [{"Id": "shardCount"}],
                },
            ]
        },
    )
    put_metric_alarm_mock = mocker.patch.object(CW_CLIENT, "put_metric_alarm")
    set_alarm_state_mock = mocker.patch.object(CW_CLIENT, "set_alarm_state")

    event_message = {
        "AlarmName": scale_up_alarm_name,
        "Trigger": {
            "Metrics": [
                {
                    "Id": "shardCount",
                    "Expression": f"{current_shard_count}",
                },
                {
                    "Id": "incomingBytes",
                    "MetricStat": {
                        "Metric": {
                            "Dimensions": [{"value": stream_name}],
                        },
                    },
                },
            ],
        },
    }

    KinesisUpscaler(event_message).scale()

    update_shard_count_mock.assert_called_once_with(
        StreamName=stream_name,
        ScalingType="UNIFORM_SCALING",
        TargetShardCount=expected_target_shard_count,
    )
    put_metric_alarm_mock.assert_has_calls(
        [
            call(
                AlarmName=scale_up_alarm_name,
                Metrics=[
                    {"Id": "shardCount", "Expression": f"{expected_target_shard_count}"}
                ],
                ActionsEnabled=True,
            ),
            call(
                AlarmName=scale_down_alarm_name,
                Metrics=[
                    {"Id": "shardCount", "Expression": f"{expected_target_shard_count}"}
                ],
                ActionsEnabled=True,
            ),
        ]
    )
    set_alarm_state_mock.assert_has_calls(
        [
            call(
                AlarmName=scale_up_alarm_name,
                StateValue="INSUFFICIENT_DATA",
                StateReason="Shard count metric updated",
            ),
            call(
                AlarmName=scale_down_alarm_name,
                StateValue="INSUFFICIENT_DATA",
                StateReason="Shard count metric updated",
            ),
        ]
    )

    logs = list(KinesisAutoscalerLog.scan())
    assert len(logs) == 1

    log = logs[0]
    assert log.stream_name == stream_name
    assert log.shard_count == current_shard_count
    assert log.target_shard_count == expected_target_shard_count
    assert log.scaling_type == "SCALE_UP"

    frozen_datetime = parse_frozen_date(FROZEN_DATE)
    assert log.scaling_datetime == frozen_datetime
    assert log.expiration_datetime == frozen_datetime + timedelta(
        days=LOGS_RETENTION_DAYS
    )
