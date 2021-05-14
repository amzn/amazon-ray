from aws_cdk import (aws_ec2 as ec2, aws_iam as iam, core)
from aws_cdk.aws_ec2 import CfnLaunchTemplate as lt


class AmazonRayStackProps:
    """Properies of the Amazon Ray onboarding stack."""
    def __init__(self, prefix: str, ami: str):
        """Init the properties class.

        Parameters:
            ami: AMI used in the stack
            prefix: Prefix of resource names in the stack
        """
        self.prefix = prefix
        self.ami = ami


class CdkStack(core.Stack):
    """Stack for setting up AWS resources required to start a Ray cluster.

    The stack configures:
    1. a core Ray execution role with associated roles and policies interacting
        with other AWS services (e.g., ec2, s3, CloudWatch, CloudFormation)
    2. a security group that allows intracluster communication
        and ssh inbound traffic
    3. a launch template that contains launch parameters, e.g., AMI,
        IAM instance profile and security group created in 2)
    """
    def __init__(self, scope: core.Construct, id: str,
                 props: AmazonRayStackProps, **kwargs) -> None:
        super().__init__(scope,
                         id,
                         stack_name=f"{props.prefix}-amzn-ray-cdk",
                         **kwargs)
        self.props = props

        # Add IAM pass role for a head instance to launch worker nodes
        # w/ an instance profile
        ray_iam_pass_ps = iam.PolicyStatement(effect=iam.Effect.ALLOW,
                                              actions=["iam:PassRole"],
                                              resources=["*"])
        # Add minimum policies for an ec2 instance to launch a ray cluster
        # that creates/updates an associated CloudFormation stack.
        ray_cloudformation_ps = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudformation:UpdateStack",
                "cloudformation:ValidateTemplate", "cloudformation:ListStacks",
                "cloudformation:DescribeStacks"
            ],
            resources=["*"])

        ray_exec_role_policies = iam.PolicyDocument(
            statements=[ray_iam_pass_ps, ray_cloudformation_ps])

        # Ray execution Role
        ray_exec_role = iam.Role(
            self,
            "RayExecutionRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            role_name=f"{props.prefix}RayClusterRoleCDK",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonEC2FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMFullAccess")
            ],
            inline_policies=[ray_exec_role_policies])
        # Add instance profile
        # Get the underlying CfnInstanceProfile from the L2 construct
        # CDK escape hatch docs:
        # https://docs.aws.amazon.com/cdk/latest/guide/cfn_layer.html
        ray_instance_profile = iam.CfnInstanceProfile(
            self,
            "InstanceProfile",
            roles=[ray_exec_role.role_name],
            path="/",
            instance_profile_name=f"{props.prefix}RayClusterInstanceProfileCDK"
        )
        # Configure VPC
        vpc = ec2.Vpc.from_lookup(self, "default_vpc", is_default=True)
        ray_sg = ec2.SecurityGroup(
            self,
            "RayClusterSecurityGroup",
            vpc=vpc,
            description="Ray cluster security group.",
            security_group_name=f"{props.prefix}RayClusterSecurityGroupCDK",
            allow_all_outbound=True,
        )
        ray_sg_connections = ec2.Connections(security_groups=[ray_sg])
        # Enable ray intracluster communication
        ray_sg_connections.allow_from(ray_sg, ec2.Port.tcp_range(0, 65535))
        # Enable ssh to the instance
        ray_sg_connections.allow_from(ec2.Peer.any_ipv4(), ec2.Port.tcp(22))

        # Launch template
        launch_template_data_property = lt.LaunchTemplateDataProperty(
            iam_instance_profile=lt.IamInstanceProfileProperty(
                arn=ray_instance_profile.attr_arn),
            image_id=props.ami,
            security_group_ids=[ray_sg.security_group_id])
        lt(self,
           "RayClusterLaunchTemplate",
           launch_template_name=f"{props.prefix}RayClusterLaunchTemplateCDK",
           launch_template_data=launch_template_data_property)
