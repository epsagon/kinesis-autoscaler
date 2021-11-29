"""
Kinesis downscaler tests
"""
from unittest.mock import call
from datetime import datetime, timedelta, timezone
from freezegun import freeze_time
from pytest_mock import MockerFixture
from kinesis_autoscaler.kinesis_downscaler import KinesisDownscaler
from kinesis_autoscaler.models.autoscaler_log import KinesisAutoscalerLog
from kinesis_autoscaler.kinesis_autoscaler import (
    CW_CLIENT,
    KINESIS_CLIENT,
    LOGS_RETENTION_DAYS,
)
from tests.aws_client_mockers.cw_client_mocker import CloudWatchClientMocker
from tests.aws_client_mockers.kinesis_client_mocker import KinesisClientMocker


@freeze_time("2021-11-16")
def test_downscale_operation(mocker: MockerFixture) -> None:
    """
    Basic sanity test to ensure the scale-down calculation is correct
    and that the required aws requests are sent as expected.
    """
    stream_name = "subscribed-stream"
    scale_up_alarm_name = f"{stream_name}-scale-up"
    scale_down_alarm_name = f"{stream_name}-scale-down"
    current_shard_count = 10
    expected_target_shard_count = 8

    cw_client_mock = CloudWatchClientMocker(CW_CLIENT, mocker)
    kinesis_client_mock = KinesisClientMocker(KINESIS_CLIENT, mocker)

    kinesis_client_mock.describe_stream_summary(current_shard_count)
    update_shard_count_mock = kinesis_client_mock.update_shard_count(
        stream_name, current_shard_count, expected_target_shard_count
    )
    cw_client_mock.describe_alarms(
        alarm_names=[scale_up_alarm_name, scale_down_alarm_name]
    )
    put_metric_alarm_mock = cw_client_mock.put_metric_alarm()
    set_alarm_state_mock = cw_client_mock.set_alarm_state()
    cw_client_mock.get_metric_data(metric_data_results=[0.3, 0.4, 0.2])

    event_message = {
        "AlarmName": scale_down_alarm_name,
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

    KinesisDownscaler(event_message).scale()

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
    assert log.scaling_type == "SCALE_DOWN"

    frozen_datetime = datetime.utcnow().replace(tzinfo=timezone.utc)
    assert log.scaling_datetime == frozen_datetime
    assert log.expiration_datetime == frozen_datetime + timedelta(
        days=LOGS_RETENTION_DAYS
    )
