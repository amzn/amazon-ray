
# CDK Integration with Ray

This is a CDK Python project to automate the process of configuring AWS resources 
needed for setting up a Ray cluster. It defines cloud infrastructure required to 
launch the cluster as code, and delegates to AWS CloudFormation for 
infrastructure provisioning.

To install the AWS CDK Toolkit, follow the [official developer guide](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html#getting_started_prerequisites).

First, you will need to install the AWS CDK:

```
$ sudo npm install -g aws-cdk
```

You can check the toolkit version with this command:

```
$ cdk --version
```

Now you are ready to create a virtualenv:

```
$ python3 -m venv .venv
```

Activate your virtualenv:

```
$ source .venv/bin/activate
```
Install the required dependencies:

```
$ pip install -r requirements.txt
```

At this point, you can deploy the stack by executing:
```
./cdk-deploy.sh -s demo # stack prefix
```
This shell script calls `cdk deploy` under the hood and displays progress 
information as your stack is deployed. When it's done, the command prompt 
reappears. You can go to the CloudFormation console and see that it lists 
`demo-amzn-ray-cdk`.

## Project contents

`README.md` -- The introductory README for this project.

`ray_ec2_stack.py` —- A custom CDK stack construct that is the core of the 
AmznRay CDK application. It is where we bring the core stack components together 
before synthesizing our Cloudformation template.

`requirements.txt` —- Pip uses this file to install all of the dependencies for 
this CDK app.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation
