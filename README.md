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
| Linux    | Python 3.6     | 1.2.0       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp36-cp36m-manylinux2014_x86_64.whl)|
| Linux    | Python 3.7     | 1.2.0       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp37-cp37m-manylinux2014_x86_64.whl)|
| Linux    | Python 3.8     | 1.2.0       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp38-cp38-manylinux2014_x86_64.whl) |
| Windows  | Python 3.6     | 1.2.0       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp36-cp36m-win_amd64.whl)           |
| Windows  | Python 3.7     | 1.2.0       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp37-cp37m-win_amd64.whl)           |
| Windows  | Python 3.8     | 1.2.0       | [Link](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp38-cp38-win_amd64.whl)            |

All of the above wheels have passed unit tests. They can be installed via `pip install -U [wheel URL]`.

### Images
Latest Ray-optimized EC2 AMIs with Amazon Ray wheels pre-installed:

| Ray Wheel                                                                                                                       | Base AMI                                     | AMI ID                | Region    |
|---------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|-----------------------|-----------|
| [Linux - Python 3.6 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-025b0741c5ebf7d9f | us-east-1 |
| [Linux - Python 3.6 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-063108a9ccbb12ef2 | us-east-2 |
| [Linux - Python 3.6 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0956a36239fe22b61 | us-west-1 |
| [Linux - Python 3.6 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp36-cp36m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-070beff7e6aabee85 | us-west-2 |
| [Linux - Python 3.7 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0a4da390e7a168bb9 | us-east-1 |
| [Linux - Python 3.7 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0a4eafb4b01445f67 | us-east-2 |
| [Linux - Python 3.7 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-040918e102e989b89 | us-west-1 |
| [Linux - Python 3.7 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp37-cp37m-manylinux2014_x86_64.whl)| AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0e17b2106eb95aeeb | us-west-2 |
| [Linux - Python 3.8 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-04a8d96070f130eb1 | us-east-1 |
| [Linux - Python 3.8 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-09c70a296453d2d57 | us-east-2 |
| [Linux - Python 3.8 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-0f75730bc24008b20 | us-west-1 |
| [Linux - Python 3.8 - Ray 1.2.0](http://d168575n8y1h5x.cloudfront.net/latest/amzn_ray-1.2.0-cp38-cp38-manylinux2014_x86_64.whl) | AWS Deep Learning AMI (Ubuntu 18.04, 64-bit) | ami-04e23701d01e53705 | us-west-2 |

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
  ImageId: ami-0a4da390e7a168bb9

worker_nodes:
  InstanceType: r5n.2xlarge
  ImageId: ami-0a4da390e7a168bb9

# explicitly remove setup commands to keep the pre-installed version of ray
setup_commands: []
```

#### CloudWatch Integration
Each AMI comes with the
[CloudWatch Unified Agent](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/UseCloudWatchUnifiedAgent.html)
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

To disable the CloudWatch Unified Agent at cluster launch time, add the following setup command to your autoscaler
config:

```yaml
setup_commands:
  - sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop
```


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information about reporting potential security issues
or vulnerabilities.


## License

This project is licensed under the [Apache-2.0 License](LICENSE).

