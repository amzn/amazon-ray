## Amazon Ray

**Ray provides a simple, universal API for building distributed applications.**
Please see the [Latest Ray Docs](https://ray.readthedocs.io/en/latest/index.html).

This repository serves as a staging area for ongoing enhancements to Ray focused on improving
its integration with AWS and other Amazon technologies. Associated large-scale refactoring,
rearchitecture, or experimental changes to Ray will typically be released and vetted here prior
to any subsequent contribution back to the [Ray Project](https://github.com/ray-project/ray).


## Latest Releases
### Wheels
Latest Amazon Ray wheels:

| Platform | Python Version | Ray Version | Wheel                                                                                                 |
|----------|----------------|-------------|-------------------------------------------------------------------------------------------------------|
| Linux    | Python 3.6     | 1.9.2       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp36-cp36m-manylinux2014_x86_64.whl)|
| Linux    | Python 3.7     | 1.9.2       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp37-cp37m-manylinux2014_x86_64.whl)|
| Linux    | Python 3.8     | 1.9.2       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp38-cp38-manylinux2014_x86_64.whl) |


All of the above wheels have passed unit tests. They can be installed via `pip install -U [wheel URL]`.

### Amazon Ray Images
Latest Ray-optimized EC2 AMIs with Amazon Ray wheels pre-installed:

| Ray Wheel                                                                                                                       | Base AMI                                     | AMI ID                | Region    |
|---------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|-----------------------|-----------|
| [Linux - Python 3.6 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0ec076d1d4cf24740 | us-east-1 |
| [Linux - Python 3.6 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-05c5ae4db3d904e36 | us-east-2 |
| [Linux - Python 3.6 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0571beb34ef22a29f | us-west-1 |
| [Linux - Python 3.6 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-049c97be6e59b38b1 | us-west-2 |
| [Linux - Python 3.7 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0cd43cad722dc3ae6 | us-east-1 |
| [Linux - Python 3.7 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-08f28214c5e591d5d | us-east-2 |
| [Linux - Python 3.7 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0f10a7def52ab3849 | us-west-1 |
| [Linux - Python 3.7 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0b298f3f656bc15e1 | us-west-2 |
| [Linux - Python 3.8 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0ea510fcb67686b48 | us-east-1 |
| [Linux - Python 3.8 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-01cff3275ce4dc684 | us-east-2 |
| [Linux - Python 3.8 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-09f8352c0f492acda | us-west-1 |
| [Linux - Python 3.8 - Ray 1.9.2](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.9.2-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-06d3d2ee794b34a21 | us-west-2 |

All of the above AMIs have passed unit tests and EC2 cluster integration tests. To use any of the above AMIs,
first ensure that you're launching your Ray EC2 cluster in the same region as the AMI, then specify the AMI ID
to use with your cluster's head and worker nodes in your autoscaler config:

```yaml
provider:
  type: aws
  region: us-east-1
  availability_zone: us-east-1a, us-east-1b, us-east-1c, us-east-1d, us-east-1f

head_node:
  InstanceType: r5n.xlarge
  ImageId: ami-0ec076d1d4cf24740

worker_nodes:
  InstanceType: r5n.2xlarge
  ImageId: ami-0ec076d1d4cf24740

# explicitly remove setup commands to keep the pre-installed version of ray
setup_commands: []
```

#### CloudWatch Integration
Each AMI comes with the
[Unified CloudWatch Agent](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/UseCloudWatchUnifiedAgent.html)
pre-installed and configured. The agent will automatically collect additional system level metrics for each EC2
instance in your Ray cluster and write Ray system logs out to the CloudWatch log groups *ray_logs_out* and
*ray_logs_err*.

Any logs written to `/tmp/ray/user/var/output/logs/*.info.log` will be automatically added to a corresponding
*ray_user_logs_info* CloudWatch log group, while logs written to `/tmp/ray/user/var/output/logs/*.debug.log` will
be added to a corresponding *ray_user_logs_debug* log group.

For log and metric publication to work you first need to ensure that the IAM role associated with your Ray
cluster EC2 instances is authorized to publish them. This can be done by attaching the following policy to this
IAM role, replacing `{AWS_ACCOUNT_ID}` with your 12-digit AWS account ID:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "cloudwatch:PutMetricData",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "CWAgent"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams",
        "logs:DescribeLogGroups"
      ],
      "Resource": [
        "arn:aws:logs:us-east-1:{AWS_ACCOUNT_ID}:log-group:ray_logs_out:*",
        "arn:aws:logs:us-east-1:{AWS_ACCOUNT_ID}:log-group:ray_logs_err:*",
        "arn:aws:logs:us-east-1:{AWS_ACCOUNT_ID}:log-group:ray_user_logs_debug:*",
        "arn:aws:logs:us-east-1:{AWS_ACCOUNT_ID}:log-group:ray_user_logs_info:*"
      ]
    }
  ]
}
```

A tail can be acquired on all logs written to a CloudWatch log group by
 ensuring that you have the
 [AWS CLI V2+ installed](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
 and then running:
```sh
aws logs tail $log_group_name --follow
```

To disable the Unified CloudWatch Agent at cluster launch time, add the following setup command to your autoscaler
config:

```yaml
setup_commands:
  - sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop
```

### Unified CloudWatch Agent Images
The AMIs below ship with the [Unified CloudWatch Agent]
(https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/UseCloudWatchUnifiedAgent.html) 
pre-installed. They should be used with any Ray cluster declaring an `agent` 
configuration under the `cloudwatch` section of its AWS [cluster config file]
(https://docs.ray.io/en/latest/cluster/config.html).

| Base AMI                                     | AMI ID                | Region    | Unified CloudWatch Agent Version |
|----------------------------------------------|-----------------------|-----------|----------------------------------|
| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-069f2811478f86c20 | us-east-1 | v1.247348.0b251302               |
| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-058cc0932940c2b8b | us-east-2 | v1.247348.0b251302               |
| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-044f95c9ef12883ef | us-west-1 | v1.247348.0b251302               |
| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0d88d9cbe28fac870 | us-west-2 | v1.247348.0b251302               |

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information about reporting potential security issues
or vulnerabilities.


## License

This project is licensed under the [Apache-2.0 License](LICENSE).
