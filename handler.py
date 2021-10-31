"""
Handler functions for Kinesis autoscaler
"""

import json
import logging
from kinesis_autoscaler.kinesis_upscaler import KinesisUpscaler
from kinesis_autoscaler.kinesis_downscaler import KinesisDownscaler

logging.getLogger().setLevel(logging.INFO)


def parse_sns_message(event: dict) -> dict:
    """
    Parses SNS record and returns its message.
    :param event: SNS event that triggered the lambda
    :return: parsed SNS message
    """
    return json.loads(event["Records"][0]["Sns"]["Message"])


def scale_up(event: dict, _context) -> None:
    """
    Lambda handler for scaling up Kinesis streams.
    :param event: Lambda triggering event
    """
    try:
        event_message = parse_sns_message(event)
        KinesisUpscaler(event_message).scale()
    except Exception:
        logging.exception("stream scale-up process failed")
        raise


def scale_down(event: dict, _context) -> None:
    """
    Lambda handler for scaling down Kinesis streams.
    :param event: Lambda triggering event
    """
    try:
        event_message = parse_sns_message(event)
        KinesisDownscaler(event_message).scale()
    except Exception:
        logging.exception("stream scale-down process failed")
        raise
