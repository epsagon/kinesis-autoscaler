"""
Kinesis client mocker
"""
from pytest_mock import MockerFixture


class KinesisClientMocker:
    """
    Kinesis client mocker.
    Used for stubbing API responses and asserting calls against mocks.
    """

    def __init__(self, client, mocker: MockerFixture):
        self.client = client
        self.mocker = mocker

    def describe_stream_summary(self, open_shard_count: int) -> MockerFixture:
        return self.mocker.patch.object(
            self.client,
            "describe_stream_summary",
            return_value={
                "StreamDescriptionSummary": {"OpenShardCount": open_shard_count}
            },
        )

    def update_shard_count(
        self,
        stream_name: str,
        current_shard_count: int,
        target_shard_count: int,
    ) -> MockerFixture:
        return self.mocker.patch.object(
            self.client,
            "update_shard_count",
            return_value={
                "StreamName": stream_name,
                "CurrentShardCount": current_shard_count,
                "TargetShardCount": target_shard_count,
            },
        )
