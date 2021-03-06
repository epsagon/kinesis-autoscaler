"""
Service constants
"""
import os

DEFAULT_REGION = "us-east-1"
REGION = os.getenv("AWS_REGION", DEFAULT_REGION)

DEFAULT_STAGE = "dev"
STAGE = os.getenv("STAGE", DEFAULT_STAGE)

LOGS_RETENTION_DAYS = 14
