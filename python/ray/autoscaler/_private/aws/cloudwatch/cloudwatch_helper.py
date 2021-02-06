import botocore
import copy
import json
import os
import logging
import time
from ray.autoscaler._private.aws.utils import client_cache

logger = logging.getLogger(__name__)

CWA_CONFIG_SSM_PARAM_NAME_BASE = "ray_cloudwatch_agent_config"
RAY = "ray-autoscaler"
CLOUDWATCH_RAY_INSTANCE_PROFILE = RAY + "-cloudwatch-v1"
CLOUDWATCH_RAY_IAM_ROLE = RAY + "-cloudwatch-v1"


class CloudwatchHelper:
    def __init__(self, provider_config, node_ids, cluster_name):
        # dedupe and sort node IDs to support deterministic unit test stubs
        self.node_ids = sorted(list(set(node_ids)))
        self.cluster_name = cluster_name
        self.provider_config = provider_config
        region = provider_config["region"]
        self.ec2_client = client_cache("ec2", region)
        self.ssm_client = client_cache("ssm", region)
        self.cloudwatch_client = client_cache("cloudwatch", region)

    def setup_from_config(self):
        # check if user specified a cloudwatch agent config file path.
        # if so, install and start cloudwatch agent
        if CloudwatchHelper.cloudwatch_config_exists(
                self.provider_config,
                "agent",
                "config",
        ):
            self.ssm_install_cloudwatch_agent()

        # check if user specified a cloudwatch dashboard config file path.
        # if so, put cloudwatch dashboard
        if CloudwatchHelper.cloudwatch_config_exists(
                self.provider_config,
                "dashboard",
                "config",
        ):
            self.put_cloudwatch_dashboard()

        # check if user specified a cloudwatch alarm config file path.
        # if so, put cloudwatch alarms
        if CloudwatchHelper.cloudwatch_config_exists(
                self.provider_config,
                "alarm",
                "config",
        ):
            self.put_cloudwatch_alarm()

    def ssm_install_cloudwatch_agent(self):
        """Install and Start CloudWatch Agent via Systems Manager (SSM)"""

        # wait for all EC2 instance checks to complete
        try:
            logger.info(
                "Waiting for EC2 instance health checks to complete before "
                "installing CloudWatch Unified Agent. This may take a few "
                "minutes...")
            waiter = self.ec2_client.get_waiter("instance_status_ok")
            waiter.wait(InstanceIds=self.node_ids)
        except botocore.exceptions.WaiterError as e:
            logger.error(
                "Failed while waiting for EC2 instance checks to complete: {}".
                format(e.message))
            raise e

        # install the cloudwatch agent on each cluster node
        parameters_cwa_install = {
            "action": ["Install"],
            "name": ["AmazonCloudWatchAgent"],
            "version": ["latest"]
        }
        logger.info(
            "Installing the CloudWatch Unified Agent package on {} nodes. "
            "This may take a few minutes as we wait for all package updates "
            "to complete...".format(len(self.node_ids)))
        try:
            self._ssm_command_waiter(
                "AWS-ConfigureAWSPackage",
                parameters_cwa_install,
            )
            logger.info(
                "Successfully installed CloudWatch Unified Agent on {} nodes".
                format(len(self.node_ids)))
        except botocore.exceptions.WaiterError as e:
            logger.error(
                "Failed while waiting for SSM CloudWatch Unified Agent "
                "package install command to complete on all cluster nodes: {}"
                .format(e))
            raise e

        # upload cloudwatch agent config to the SSM parameter store
        logger.info(
            "Uploading CloudWatch Unified Agent config to the SSM parameter"
            "store.")
        cwa_config = self._load_config_file("agent")
        self._replace_all_config_variables(
            cwa_config,
            None,
            self.cluster_name,
            self.provider_config["region"],
        )
        cwa_config_ssm_param_name = "{}_{}".format(
            CWA_CONFIG_SSM_PARAM_NAME_BASE,
            self.cluster_name,
        )
        self.ssm_client.put_parameter(
            Name=cwa_config_ssm_param_name,
            Type="String",
            Value=json.dumps(cwa_config),
            Overwrite=True,
        )

        # satisfy collectd preconditions before starting cloudwatch agent
        logger.info("Preparing to start CloudWatch Unified Agent on {} nodes."
                    .format(len(self.node_ids)))
        parameters_run_shell = {
            "commands": [
                "mkdir -p /usr/share/collectd/",
                "touch /usr/share/collectd/types.db"
            ],
        }
        self._ssm_command_waiter(
            "AWS-RunShellScript",
            parameters_run_shell,
        )

        # start cloudwatch agent
        logger.info("Starting CloudWatch Unified Agent package on {} nodes."
                    .format(len(self.node_ids)))
        parameters_start_cwa = {
            "action": ["configure"],
            "mode": ["ec2"],
            "optionalConfigurationSource": ["ssm"],
            "optionalConfigurationLocation": [cwa_config_ssm_param_name],
            "optionalRestart": ["yes"],
        }
        self._ssm_command_waiter(
            "AmazonCloudWatch-ManageAgent",
            parameters_start_cwa,
        )
        logger.info(
            "CloudWatch Unified Agent started successfully on all nodes."
            .format(len(self.node_ids)))

    def put_cloudwatch_dashboard(self):
        """put dashboard to cloudwatch console"""

        cloudwatch_config = self.provider_config["cloudwatch"]
        dashboard_config = cloudwatch_config.get("dashboard", {})
        dashboard_name = dashboard_config.get("name", self.cluster_name)
        data = self._load_config_file("dashboard")
        widgets = []
        for item in data:
            self._replace_all_config_variables(
                item,
                None,
                self.cluster_name,
                self.provider_config["region"],
            )
            for node_id in self.node_ids:
                item_out = copy.deepcopy(item)
                (item_out, modified_str_count) = \
                    self._replace_all_config_variables(
                        item_out,
                        str(node_id),
                        None,
                        None,
                    )
                widgets.append(item_out)
                if not modified_str_count:
                    break  # no per-node dashboard widgets specified

        response = self.cloudwatch_client.put_dashboard(
            DashboardName=dashboard_name,
            DashboardBody=json.dumps({
                "widgets": widgets
            }))
        issue_count = len(response.get("DashboardValidationMessages", []))
        if issue_count > 0:
            for issue in response.get("DashboardValidationMessages"):
                logging.error("Error in dashboard config: {} - {}".format(
                    issue["Message"], issue["DataPath"]))
            raise Exception(
                "Errors in dashboard configuration: {} issues raised".format(
                    issue_count))
        else:
            logger.info("Successfully put dashboard to cloudwatch console")
        return response

    def put_cloudwatch_alarm(self):
        """ put cloudwatch metric alarms read from config """

        data = self._load_config_file("alarm")
        for node_id in self.node_ids:
            for item in data:
                item_out = copy.deepcopy(item)
                self._replace_all_config_variables(
                    item_out,
                    str(node_id),
                    self.cluster_name,
                    self.provider_config["region"],
                )
                self.cloudwatch_client.put_metric_alarm(**item_out)
        logger.info("Successfully put alarms to cloudwatch console")

    def _send_command_to_nodes(self, document_name, parameters, node_ids):
        """ send SSM command to the given nodes """
        logger.debug("Sending SSM command to {} node(s). Document name: {}. "
                     "Parameters: {}.".format(
                         len(node_ids), document_name, parameters))
        response = self.ssm_client.send_command(
            InstanceIds=self.node_ids,
            DocumentName=document_name,
            Parameters=parameters,
            MaxConcurrency=str(min(len(self.node_ids), 100)),
            MaxErrors="0")
        return response

    def _send_command_to_all_nodes(self, document_name, parameters):
        """ send SSM command to all nodes """
        return self._send_command_to_nodes(
            document_name,
            parameters,
            self.node_ids,
        )

    def _ssm_command_waiter(self, document_name, parameters):
        """ wait for SSM command to complete on all cluster nodes """

        # This waiter differs from the built-in SSM.Waiter by
        # optimistically waiting for the command invocation to
        # exist instead of failing immediately, and by resubmitting
        # any failed command until all retry attempts are exhausted.
        response = self._send_command_to_all_nodes(
            document_name,
            parameters,
        )
        command_id = response["Command"]["CommandId"]

        cloudwatch_config = self.provider_config["cloudwatch"]
        agent_retryer_config = cloudwatch_config \
            .get("agent") \
            .get("retryer", {})
        max_attempts = agent_retryer_config.get("max_attempts", 120)
        delay_seconds = agent_retryer_config.get("delay_seconds", 30)
        num_attempts = 0
        for node_id in self.node_ids:
            while True:
                num_attempts += 1
                logger.debug("Listing SSM command ID {} invocations on node {}"
                             .format(command_id, node_id))
                response = self.ssm_client.list_command_invocations(
                    CommandId=command_id,
                    InstanceId=node_id,
                )
                cmd_invocations = response["CommandInvocations"]
                if not cmd_invocations:
                    logger.debug(
                        "SSM Command ID {} invocation does not exist. If "
                        "the command was just started, it may take a "
                        "few seconds to register.".format(command_id))
                else:
                    if len(cmd_invocations) > 1:
                        logger.warning(
                            "Expected to find 1 SSM command invocation with "
                            "ID {} on node {} but found {}: {}".format(
                                command_id,
                                node_id,
                                len(cmd_invocations),
                                cmd_invocations,
                            ))
                    cmd_invocation = cmd_invocations[0]
                    if cmd_invocation["Status"] == "Success":
                        logger.debug(
                            "SSM Command ID {} completed successfully."
                            .format(command_id))
                        break
                    if num_attempts >= max_attempts:
                        logger.error(
                            "Max attempts for command {} exceeded on node {}"
                            .format(command_id, node_id))
                        raise botocore.exceptions.WaiterError(
                            name="ssm_waiter",
                            reason="Max attempts exceeded",
                            last_response=cmd_invocation,
                        )
                    if cmd_invocation["Status"] == "Failed":
                        logger.debug(
                            "SSM Command ID {} failed. Retrying in {} seconds."
                            .format(command_id, delay_seconds))
                        response = self._send_command_to_nodes(
                            document_name, parameters, node_id)
                        command_id = response["Command"]["CommandId"]
                        logger.debug("Sent SSM command ID {} to node {}"
                                     .format(command_id, node_id))
                time.sleep(delay_seconds)

    def _replace_config_variables(self, string, node_id, cluster_name, region):
        """
        replace known config variable occurrences in the input string
        does not replace variables with undefined or empty strings
        """

        if node_id:
            string = string.replace("{instance_id}", node_id)
        if cluster_name:
            string = string.replace("{cluster_name}", cluster_name)
        if region:
            string = string.replace("{region}", region)
        return string

    def _replace_all_config_variables(
            self,
            collection,
            node_id,
            cluster_name,
            region,
    ):
        """
        Replace known config variable occurrences in the input collection.
        The input collection must be either a dict or list.

        Returns a tuple consisting of the output collection and the number of
        modified strings in the collection (which is not necessarily equal to
        the number of variables replaced).
        """

        modified_value_count = 0
        if type(collection) is dict:
            for key, value in collection.items():
                if type(value) is dict or type(value) is list:
                    (collection[key], modified_count) = \
                        self._replace_all_config_variables(
                            collection[key],
                            node_id,
                            cluster_name,
                            region
                        )
                    modified_value_count += modified_count
                elif type(value) is str:
                    collection[key] = self._replace_config_variables(
                        value,
                        node_id,
                        cluster_name,
                        region,
                    )
                    modified_value_count += (collection[key] != value)
        if type(collection) is list:
            for i in range(len(collection)):
                if type(collection[i]) is dict or type(collection[i]) is list:
                    (collection[i], modified_count) = \
                        self._replace_all_config_variables(
                            collection[i],
                            node_id,
                            cluster_name,
                            region
                        )
                    modified_value_count += modified_count
                elif type(collection[i]) is str:
                    value = collection[i]
                    collection[i] = self._replace_config_variables(
                        value,
                        node_id,
                        cluster_name,
                        region,
                    )
                    modified_value_count += (collection[i] != value)
        return collection, modified_value_count

    def _load_config_file(self, section_name):
        """load JSON config file"""

        cloudwatch_config = self.provider_config["cloudwatch"]
        json_config_file_section = cloudwatch_config.get(section_name, {})
        json_config_file_path = json_config_file_section.get("config", {})
        json_config_path = os.path.abspath(json_config_file_path)
        with open(json_config_path) as f:
            data = json.load(f)
        return data

    @staticmethod
    def resolve_instance_profile_name(config, default_instance_profile_name):
        cwa_cfg_exists = CloudwatchHelper.cloudwatch_config_exists(
            config,
            "agent",
            "config",
        )
        return CLOUDWATCH_RAY_INSTANCE_PROFILE if cwa_cfg_exists \
            else default_instance_profile_name

    @staticmethod
    def resolve_iam_role_name(config, default_iam_role_name):
        cwa_cfg_exists = CloudwatchHelper.cloudwatch_config_exists(
            config,
            "agent",
            "config",
        )
        return CLOUDWATCH_RAY_IAM_ROLE if cwa_cfg_exists \
            else default_iam_role_name

    @staticmethod
    def resolve_policy_arns(config, default_policy_arns):
        cwa_cfg_exists = CloudwatchHelper.cloudwatch_config_exists(
            config,
            "agent",
            "config",
        )
        if cwa_cfg_exists:
            default_policy_arns.extend([
                "arn:aws:iam::aws:policy/CloudWatchFullAccess",
                "arn:aws:iam::aws:policy/AmazonSSMFullAccess"
            ])
        return default_policy_arns

    @staticmethod
    def cloudwatch_config_exists(config, section_name, file_name):
        """check if cloudwatch config file exists"""

        cfg = config.get("cloudwatch", {}).get(section_name, {}).get(file_name)
        if cfg:
            assert os.path.isfile(cfg), \
                "Invalid CloudWatch Config File Path: {}".format(cfg)
        return bool(cfg)
