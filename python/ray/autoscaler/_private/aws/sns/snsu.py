from ray.autoscaler._private.aws.utils import client_cache
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SnsHelper:
    def __init__(self, region: str, **kwargs):
        self.sns = client_cache("sns", region, **kwargs)

    def subscribe(self,
                  topic_arn: str) -> str:
        response = self.sns.subscribe(TopicArn=topic_arn, Protocol='https')
        return response['SubscriptionArn']

    def publish(self,
                topic_arn: str,
                message: str) -> Dict[str, Any]:

        response = self.sns.publish(TopicArn=topic_arn, Message=message)
        return response
