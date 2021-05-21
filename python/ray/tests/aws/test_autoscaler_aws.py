import pytest

from ray.autoscaler._private.aws.config import _get_vpc_id_or_die
import ray.tests.aws.utils.stubs as stubs
import ray.tests.aws.utils.helpers as helpers
from ray.tests.aws.utils.constants import AUX_SUBNET, DEFAULT_SUBNET, \
    DEFAULT_SG_AUX_SUBNET, DEFAULT_SG, DEFAULT_SG_DUAL_GROUP_RULES, \
    DEFAULT_SG_WITH_RULES_AUX_SUBNET, AUX_SG, \
    DEFAULT_SG_WITH_NAME, DEFAULT_SG_WITH_NAME_AND_RULES, CUSTOM_IN_BOUND_RULES


def test_create_sg_different_vpc_same_rules(iam_client_stub, ec2_client_stub):
    # use default stubs to skip ahead to security group configuration
    stubs.skip_to_configure_sg(ec2_client_stub, iam_client_stub)

    # given head and worker nodes with custom subnets defined...
    # expect to first describe the worker subnet ID
    stubs.describe_subnets_echo(ec2_client_stub, AUX_SUBNET)
    # expect to second describe the head subnet ID
    stubs.describe_subnets_echo(ec2_client_stub, DEFAULT_SUBNET)
    # given no existing security groups within the VPC...
    stubs.describe_no_security_groups(ec2_client_stub)
    # expect to first create a security group on the worker node VPC
    stubs.create_sg_echo(ec2_client_stub, DEFAULT_SG_AUX_SUBNET)
    # expect new worker security group details to be retrieved after creation
    stubs.describe_sgs_on_vpc(
        ec2_client_stub,
        [AUX_SUBNET["VpcId"]],
        [DEFAULT_SG_AUX_SUBNET],
    )
    # expect to second create a security group on the head node VPC
    stubs.create_sg_echo(ec2_client_stub, DEFAULT_SG)
    # expect new head security group details to be retrieved after creation
    stubs.describe_sgs_on_vpc(
        ec2_client_stub,
        [DEFAULT_SUBNET["VpcId"]],
        [DEFAULT_SG],
    )

    # given no existing default head security group inbound rules...
    # expect to authorize all default head inbound rules
    stubs.authorize_sg_ingress(
        ec2_client_stub,
        DEFAULT_SG_DUAL_GROUP_RULES,
    )
    # given no existing default worker security group inbound rules...
    # expect to authorize all default worker inbound rules
    stubs.authorize_sg_ingress(
        ec2_client_stub,
        DEFAULT_SG_WITH_RULES_AUX_SUBNET,
    )

    # given our mocks and an example config file as input...
    # expect the config to be loaded, validated, and bootstrapped successfully
    config = helpers.bootstrap_aws_example_config_file("example-subnets.yaml")

    # expect the bootstrapped config to show different head and worker security
    # groups residing on different subnets
    assert config["head_node"]["SecurityGroupIds"] == [DEFAULT_SG["GroupId"]]
    assert config["head_node"]["SubnetIds"] == [DEFAULT_SUBNET["SubnetId"]]
    assert config["worker_nodes"]["SecurityGroupIds"] == [AUX_SG["GroupId"]]
    assert config["worker_nodes"]["SubnetIds"] == [AUX_SUBNET["SubnetId"]]

    # expect no pending responses left in IAM or EC2 client stub queues
    iam_client_stub.assert_no_pending_responses()
    ec2_client_stub.assert_no_pending_responses()


def test_create_sg_with_custom_inbound_rules_and_name(iam_client_stub,
                                                      ec2_client_stub):
    # use default stubs to skip ahead to security group configuration
    stubs.skip_to_configure_sg(ec2_client_stub, iam_client_stub)

    # expect to describe the head subnet ID
    stubs.describe_subnets_echo(ec2_client_stub, DEFAULT_SUBNET)
    # given no existing security groups within the VPC...
    stubs.describe_no_security_groups(ec2_client_stub)
    # expect to create a security group on the head node VPC
    stubs.create_sg_echo(ec2_client_stub, DEFAULT_SG_WITH_NAME)
    # expect new head security group details to be retrieved after creation
    stubs.describe_sgs_on_vpc(
        ec2_client_stub,
        [DEFAULT_SUBNET["VpcId"]],
        [DEFAULT_SG_WITH_NAME],
    )

    # given custom existing default head security group inbound rules...
    # expect to authorize both default and custom inbound rules
    stubs.authorize_sg_ingress(
        ec2_client_stub,
        DEFAULT_SG_WITH_NAME_AND_RULES,
    )

    # given the prior modification to the head security group...
    # expect the next read of a head security group property to reload it
    stubs.describe_sg_echo(ec2_client_stub, DEFAULT_SG_WITH_NAME_AND_RULES)

    _get_vpc_id_or_die.cache_clear()
    # given our mocks and an example config file as input...
    # expect the config to be loaded, validated, and bootstrapped successfully
    config = helpers.bootstrap_aws_example_config_file(
        "example-security-group.yaml")

    # expect the bootstrapped config to have the custom security group...
    # name and in bound rules
    assert config["provider"]["security_group"][
        "GroupName"] == DEFAULT_SG_WITH_NAME_AND_RULES["GroupName"]
    assert config["provider"]["security_group"][
        "IpPermissions"] == CUSTOM_IN_BOUND_RULES

    # expect no pending responses left in IAM or EC2 client stub queues
    iam_client_stub.assert_no_pending_responses()
    ec2_client_stub.assert_no_pending_responses()


def test_cloudwatch_agent_setup(ec2_client_stub, ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to install CloudWatch Agent on all nodes...
    # expect to wait for each EC2 instance status to report on OK state
    stubs.describe_instance_status_ok(ec2_client_stub, node_ids)
    # given all cluster EC2 instance status checks passed...
    # expect to send a CloudWatch Agent install command to all nodes via SSM
    cmd_id = stubs.send_command_cwa_install(ssm_client_stub, node_ids)
    # given a CloudWatch Agent install command sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)
    # given a successful CloudWatch Agent install on all nodes...
    # expect to store the CloudWatch Agent config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "agent")
    # given a successful CloudWatch Agent install on all nodes...
    # expect to send a command to satisfy CWA collectd preconditions via SSM
    cmd_id = stubs.send_command_cwa_collectd_init(ssm_client_stub, node_ids)
    # given a CWA collectd precondition setup command sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)

    # given that all CloudWatch Agent start preconditions are satisfied...
    # expect to send an SSM command to start CloudWatch Agent on all nodes
    parameter_name = helpers.get_ssm_param_name(cloudwatch_helper.cluster_name,
                                                "agent")
    cmd_id = stubs.send_command_start_cwa(ssm_client_stub, node_ids,
                                          parameter_name)
    # given a SSM command to start CloudWatch Agent sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)

    # given our mocks and the example CloudWatch Agent config as input...
    # expect CloudWatch Agent to be installed on each cluster node successfully
    cloudwatch_helper.ssm_install_cloudwatch_agent()

    # expect no pending responses left in client stub queues
    ec2_client_stub.assert_no_pending_responses()
    ssm_client_stub.assert_no_pending_responses()


def test_cloudwatch_dashboard_creation(cloudwatch_client_stub,
                                       ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to create a cluster CloudWatch dashboard...
    # expect to store the CloudWatch Dashboard config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "dashboard")

    # given a directive to create a cluster CloudWatch dashboard...
    # expect to make a call to create a dashboard for each node in the cluster
    stubs.put_cluster_dashboard_success(
        cloudwatch_client_stub,
        cloudwatch_helper,
    )

    # given our mocks and the example cloudwatch dashboard config as input...
    # expect a cluster CloudWatch dashboard to be created successfully
    cloudwatch_helper.put_cloudwatch_dashboard()
    # expect no pending responses left in the CloudWatch client stub queue
    cloudwatch_client_stub.assert_no_pending_responses()


def test_cloudwatch_alarm_creation(cloudwatch_client_stub, ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to create a cluster CloudWatch alarm...
    # expect to store the CloudWatch Alarm config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "alarm")

    # given a directive to create cluster CloudWatch alarms...
    # expect to make a call to create alarms for each node in the cluster
    stubs.put_cluster_alarms_success(cloudwatch_client_stub, cloudwatch_helper)

    # given our mocks and the example cloudwatch alarm config as input...
    # expect cluster alarms to be created successfully
    cloudwatch_helper.put_cloudwatch_alarm()

    # expect no pending responses left in the CloudWatch client stub queue
    cloudwatch_client_stub.assert_no_pending_responses()


def test_cloudwatch_agent_update_without_change(ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Agent Config without any change...
    # expect the stored the CloudWatch Agent Config is same as local config
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "agent")
    stubs.get_param_ssm_same(ssm_client_stub, cw_ssm_param_name,
                             cloudwatch_helper, "agent")

    # given our mocks and the same cloudwatch agent config as input...
    # expect no update performed on CloudWatch Agent Config
    cloudwatch_helper._update_cloudwatch_config("agent")


def test_cloudwatch_agent_update_with_change(ec2_client_stub, ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Agent Config with new changes...
    # expect the stored the CloudWatch Agent Config is different from local config
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "agent")
    stubs.get_param_ssm_different(ssm_client_stub, cw_ssm_param_name)

    # given an updated CloudWatch Agent Config file...
    # expect to store the new CloudWatch Agent config as an SSM parameter
    cmd_id = stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "agent")

    # given that updated CloudWatch Agent Config is put to Parameter Store...
    # expect to send an SSM command to restart CloudWatch Agent on all nodes
    cmd_id = stubs.send_command_stop_cwa(ssm_client_stub, node_ids)
    # given a SSM command to stop CloudWatch Agent sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)
    cmd_id = stubs.send_command_start_cwa(ssm_client_stub, node_ids,
                                          cw_ssm_param_name)
    # given a SSM command to start CloudWatch Agent sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)

    # given our mocks and the example CloudWatch Agent config as input...
    # expect CloudWatch Agent configured to use updated file on each cluster node successfully
    cloudwatch_helper._update_cloudwatch_config("agent")

    # expect no pending responses left in client stub queues
    ec2_client_stub.assert_no_pending_responses()
    ssm_client_stub.assert_no_pending_responses()


def test_cloudwatch_agent_update_without_cwa_preinstalled(
        ec2_client_stub, ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Agent Config without preinstalled agent...
    # expect the call to retrive the CloudWatch Agent Config gets an exception
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "agent")
    stubs.get_param_ssm_exception(ssm_client_stub, cw_ssm_param_name)

    # given a directive to install CloudWatch Agent on all nodes...
    # expect to wait for each EC2 instance status to report on OK state
    stubs.describe_instance_status_ok(ec2_client_stub, node_ids)
    # given all cluster EC2 instance status checks passed...
    # expect to send a CloudWatch Agent install command to all nodes via SSM
    cmd_id = stubs.send_command_cwa_install(ssm_client_stub, node_ids)
    # given a CloudWatch Agent install command sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)
    # given a successful CloudWatch Agent install on all nodes...
    # expect to store the CloudWatch Agent config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "agent")
    # given a successful CloudWatch Agent install on all nodes...
    # expect to send a command to satisfy CWA collectd preconditions via SSM
    cmd_id = stubs.send_command_cwa_collectd_init(ssm_client_stub, node_ids)
    # given a CWA collectd precondition setup command sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)

    # given that all CloudWatch Agent start preconditions are satisfied...
    # expect to send an SSM command to start CloudWatch Agent on all nodes
    cmd_id = stubs.send_command_start_cwa(ssm_client_stub, node_ids,
                                          cw_ssm_param_name)
    # given a SSM command to start CloudWatch Agent sent to all nodes...
    # expect to wait for the command to complete successfully on every node
    stubs.list_command_invocations_success(ssm_client_stub, node_ids, cmd_id)

    stubs.get_param_ssm_same(ssm_client_stub, cw_ssm_param_name,
                             cloudwatch_helper, "agent")

    # given our mocks and the updated CloudWatch Agent config to install agent...
    # expect CloudWatch Agent to be installed on each cluster node successfully
    cloudwatch_helper._update_cloudwatch_config("agent")

    # expect no pending responses left in client stub queues
    ec2_client_stub.assert_no_pending_responses()
    ssm_client_stub.assert_no_pending_responses()


def test_cloudwatch_dashboard_update_without_change(ec2_client_stub,
                                                    ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Dashboard Config without any change...
    # expect the stored the CloudWatch Dashboard Config is same as local config
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "dashboard")
    stubs.get_param_ssm_same(ssm_client_stub, cw_ssm_param_name,
                             cloudwatch_helper, "dashboard")
    # given a directive to update a cluster CloudWatch Dashboard Config without any change...
    # expect the stored the CloudWatch Dashboard Config is same as local config
    # given our mocks and the same cloudwatch dashboard config as input...
    # expect no update performed on CloudWatch Dashboard Config
    cloudwatch_helper._update_cloudwatch_config("dashboard")


def test_cloudwatch_dashboard_update_with_change(ssm_client_stub,
                                                 cloudwatch_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Dashboard Config with new changes...
    # expect the stored the CloudWatch Dashboard Config is different from local config
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "dashboard")
    stubs.get_param_ssm_different(ssm_client_stub, cw_ssm_param_name)

    # given an updated CloudWatch Dashboard Config file...
    # expect to store the new CloudWatch Dashboard config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "dashboard")

    # given that updated CloudWatch Dashboard Config is put to Parameter Store...
    # expect to make a call to create a new dashboard with the updated config
    stubs.put_cluster_dashboard_success(
        cloudwatch_client_stub,
        cloudwatch_helper,
    )

    # given our mocks and the updated cloudwatch dashboard config as input...
    # expect a cluster CloudWatch dashboard to be created successfully
    cloudwatch_helper._update_cloudwatch_config("dashboard")

    # expect no pending responses left in the CloudWatch client stub queue
    cloudwatch_client_stub.assert_no_pending_responses()


def test_cloudwatch_dashboard_update_without_existing_dashboard(
        ssm_client_stub, cloudwatch_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Dashboard Config that doesn't exist...
    # expect the call to retrive the CloudWatch Dashboard Config gets an exception
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "dashboard")
    stubs.get_param_ssm_exception(ssm_client_stub, cw_ssm_param_name)

    # given a directive to create a cluster CloudWatch dashboard...
    # expect to store the CloudWatch Dashboard config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "dashboard")

    # given a directive to create a cluster CloudWatch dashboard...
    # expect to make a call to create a dashboard for each node in the cluster
    stubs.put_cluster_dashboard_success(
        cloudwatch_client_stub,
        cloudwatch_helper,
    )
    stubs.get_param_ssm_same(ssm_client_stub, cw_ssm_param_name,
                             cloudwatch_helper, "dashboard")
    # given our mocks and the updated cloudwatch dashboard config as input...
    # expect a cluster CloudWatch dashboard to be created successfully
    cloudwatch_helper._update_cloudwatch_config("dashboard")

    # expect no pending responses left in the CloudWatch client stub queue
    cloudwatch_client_stub.assert_no_pending_responses()


def test_cloudwatch_alarm_without_change(ssm_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Alarm Config without any change...
    # expect the stored the CloudWatch Alarm Config is same as local config
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "alarm")
    stubs.get_param_ssm_same(ssm_client_stub, cw_ssm_param_name,
                             cloudwatch_helper, "alarm")
    # given our mocks and the same cloudwatch alarm config as input...
    # expect no update performed on CloudWatch Alarm Config
    cloudwatch_helper._update_cloudwatch_config("alarm")


def test_cloudwatch_alarm_with_change(ssm_client_stub, cloudwatch_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update a cluster CloudWatch Alarm Config with new changes...
    # expect the stored the CloudWatch Alarm Config is different from local config
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "alarm")
    stubs.get_param_ssm_different(ssm_client_stub, cw_ssm_param_name)

    # given a directive to update a cluster CloudWatch Alarm Config with new changes...
    # expect make calls to retrive the existing alarms and delete these alarms first
    stubs.get_metric_alarm(cloudwatch_client_stub)
    stubs.delete_metric_alarms(cloudwatch_client_stub)

    # given an updated CloudWatch Alarm Config file...
    # expect to store the new CloudWatch Alarm config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "alarm")

    # given that existing cloudwatch alarms are deleted...
    # expect to make a call to create new alarms with the updated config
    stubs.put_cluster_alarms_success(cloudwatch_client_stub, cloudwatch_helper)

    # given our mocks and the updated cloudwatch alarm config as input...
    # expect cluster alarms to be created successfully
    cloudwatch_helper._update_cloudwatch_config("alarm")

    # expect no pending responses left in the CloudWatch client stub queue
    cloudwatch_client_stub.assert_no_pending_responses()


def test_cloudwatch_alarm_update_without_existing_alarms(
        ssm_client_stub, cloudwatch_client_stub):
    # create test cluster node IDs and an associated cloudwatch helper
    node_ids = ["i-abc", "i-def"]
    cloudwatch_helper = helpers.get_cloudwatch_helper(node_ids)

    # given a directive to update cluster CloudWatch alarms which do not exist...
    # expect to get exception as get ssm alarm paramter reponse
    cw_ssm_param_name = helpers.get_ssm_param_name(
        cloudwatch_helper.cluster_name, "alarm")
    stubs.get_param_ssm_exception(ssm_client_stub, cw_ssm_param_name)

    # given a directive to create a cluster CloudWatch alarm...
    # expect to store the CloudWatch Alarm config as an SSM parameter
    stubs.put_parameter_cloudwatch_config(
        ssm_client_stub, cloudwatch_helper.cluster_name, "alarm")

    # given a directive to create cluster CloudWatch alarms...
    # expect to make a call to create alarms for each node in the cluster
    stubs.put_cluster_alarms_success(cloudwatch_client_stub, cloudwatch_helper)

    stubs.get_param_ssm_same(ssm_client_stub, cw_ssm_param_name,
                             cloudwatch_helper, "alarm")
    # given our mocks and the example cloudwatch alarm config as input...
    # expect cluster alarms to be created successfully
    cloudwatch_helper._update_cloudwatch_config("alarm")

    # expect no pending responses left in the CloudWatch client stub queue
    cloudwatch_client_stub.assert_no_pending_responses()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", __file__]))
