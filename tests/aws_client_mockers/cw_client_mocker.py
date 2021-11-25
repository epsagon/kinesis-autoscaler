"""
CloudWatch client mocker
"""
from typing import Tuple
from pytest_mock import MockerFixture


class CloudWatchClientMocker:
    """
    CloudWatch client mocker.
    Used for stubbing API responses and asserting calls against mocks.
    """

    def __init__(self, client, mocker: MockerFixture):
        self.client = client
        self.mocker = mocker

    def describe_alarms(self, alarm_names: Tuple[str, ...]) -> MockerFixture:
        return self.mocker.patch.object(
            self.client,
            "describe_alarms",
            return_value={
                "MetricAlarms": [
                    {
                        "AlarmName": alarm,
                        "Metrics": [{"Id": "shardCount"}],
                    }
                    for alarm in alarm_names
                ]
            },
        )

    def put_metric_alarm(self) -> MockerFixture:
        return self.mocker.patch.object(self.client, "put_metric_alarm")

    def set_alarm_state(self) -> MockerFixture:
        return self.mocker.patch.object(self.client, "set_alarm_state")

    def get_metric_data(self, metric_data_results: Tuple[float, ...]) -> MockerFixture:
        return self.mocker.patch.object(
            self.client,
            "get_metric_data",
            return_value={"MetricDataResults": [{"Values": metric_data_results}]},
        )
