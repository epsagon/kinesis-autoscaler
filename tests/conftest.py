"""
Shared tests configuration
"""
import time
from typing import Iterator
import pytest
from moto import mock_dynamodb2
from pynamodb.models import Model
from kinesis_autoscaler.models.autoscaler_log import KinesisAutoscalerLog


def recreate_model_table(model: Model) -> None:
    """
    Recreates a table for a given PynamoDB model
    :param model: the PynamoDB model to recreate the table for
    """
    if model.exists():
        model.delete_table()
        while model.exists():
            time.sleep(0.1)

    model.create_table(wait=True)


@pytest.fixture(autouse=True)
def autoscaler_log_model() -> Iterator[None]:
    """
    Sets up and tears down the autoscaler log model
    """
    with mock_dynamodb2():
        recreate_model_table(KinesisAutoscalerLog)
        yield
        KinesisAutoscalerLog.delete_table()
