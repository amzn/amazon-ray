#!/usr/bin/env python3

import os
import sys
import boto3

from aws_cdk import core
from ray_ec2.ray_ec2_stack import CdkStack, AmazonRayStackProps

# amzn-ray 1.2.0, cp37, us-east-1
DEFAULT_AMZN_RAY_AMI = "ami-0a4da390e7a168bb9"
AMZN_RAY_AMI_ACCOUNT = "160082703681"


def _get_default_ami_helper():
    client = boto3.client("ec2")

    if "PYENV_VERSION" not in os.environ.keys():
        pyenv_version = "{}{}".format(sys.version_info.major,
                                      sys.version_info.minor)
    else:
        pyenv_version = "".join(os.environ["PYENV_VERSION"].split("."))
    version_filter = "cp" + pyenv_version
    filters = [{
        "Name": "owner-id",
        "Values": [
            AMZN_RAY_AMI_ACCOUNT,
        ]
    }, {
        "Name": "name",
        "Values": ["*" + version_filter + "*"]
    }, {
        "Name": "state",
        "Values": [
            "available",
        ]
    }, {
        "Name": "is-public",
        "Values": [
            "true",
        ]
    }]
    describe_image_response = client.describe_images(Filters=filters)
    image_list = describe_image_response.get("Images", [])
    ami_match = False
    if image_list:
        sorted_image_response = sorted(image_list,
                                       key=lambda k: k["CreationDate"],
                                       reverse=True)
        ami_res = sorted_image_response[0].get("ImageId", "")
        if ami_res:
            ami_match = True
    if not ami_match:
        ami_res = DEFAULT_AMZN_RAY_AMI
        print("Default AMI: \"Linux - Python 3.7 - Amazon Ray 1.2.0\" "
              "in us-east-1.")
    print(f"Default AMI ID: {ami_res}")
    return ami_res


# Define your account id to make import vpc work
env_cn = core.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"],
                          region=os.environ["CDK_DEFAULT_REGION"])
app = core.App()

if "AMI" not in os.environ.keys():
    ami = _get_default_ami_helper()
else:
    ami = os.environ["AMI"]

if "CDK_PREFIX" not in os.environ.keys():
    raise KeyError("CDK prefix not defined in the environment. "
                   "Add it via \'export CDK_PREFIX=your_prefix\'")

amazon_ray_props = AmazonRayStackProps(prefix=os.environ["CDK_PREFIX"],
                                       ami=ami)

ray_stack = CdkStack(app, id="cdk-ray", env=env_cn, props=amazon_ray_props)

app.synth()
