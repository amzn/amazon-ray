import ray.experimental.data.deltacat.aws.clients as aws_utils
import logging
from ray.experimental.data.deltacat import logs
from typing import Any, Dict, Optional, Generator
from botocore.client import BaseClient

logger = logs.configure_application_logger(logging.getLogger(__name__))


def sns_client_cache(region: Optional[str], **kwargs) -> BaseClient:

    return aws_utils.client_cache("sns", region, **kwargs)


def subscribe(topic_arn: str,
              **sns_client_kwargs) -> Generator[Dict[str, Any], None, None]:

    sns = sns_client_cache(None, **sns_client_kwargs)
    response = sns.subscribe(TopicArn=topic_arn, Protocol='https')
    return response['SubscriptionArn']


def publish(topic_arn: str, message: str,
            **sns_client_kwargs) -> Generator[Dict[str, Any], None, None]:

    sns = sns_client_cache(None, **sns_client_kwargs)
    response = sns.publish(TopicArn=topic_arn, Message=message)
    return response
