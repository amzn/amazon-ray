import botocore
import copy
import json
import os
import logging
import time
import hashlib
from enum import Enum
from ray.autoscaler._private.aws.utils import client_cache

logger = logging.getLogger(__name__)

RAY = "ray-autoscaler"
CLOUDWATCH_RAY_INSTANCE_PROFILE = RAY + "-cloudwatch-v1"
CLOUDWATCH_RAY_IAM_ROLE = RAY + "-cloudwatch-v1"


class CloudwatchConfigType(Enum):
    AGENT = "agent"
    DASHBOARD = "dashboard"
    ALARM = "alarm"


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
        self.CLOUDWATCH_CONFIG_TYPE_TO_CONFIG_VARIABLE_REPLACE_FUNC = {
            CloudwatchConfigType.AGENT.value: self.
            _replace_cwa_config_variables,
            CloudwatchConfigType.DASHBOARD.value: self.
            _replace_dashboard_config_variables,
            CloudwatchConfigType.ALARM.value: self.
            _replace_alarm_config_variables,
        }
        self.CLOUDWATCH_CONFIG_TYPE_TO_CLOUDWATCH_SETUP_FUNC = {
            CloudwatchConfigType.AGENT.value: self.
            ssm_install_cloudwatch_agent,
            CloudwatchConfigType.DASHBOARD.value: self.
            put_cloudwatch_dashboard,
            CloudwatchConfigType.ALARM.value: self.put_cloudwatch_alarm,
        }
        self.CLOUDWATCH_CONFIG_TYPE_TO_UPDATE_CONFIG_FUNC = {
            CloudwatchConfigType.AGENT.value: self._update_agent_config,
            CloudwatchConfigType.DASHBOARD.value: self.
            _update_dashboard_config,
            CloudwatchConfigType.ALARM.value: self._update_alarm_config,
        }

    def setup_from_config(self):
        for config_type in CloudwatchConfigType:
            if CloudwatchHelper.cloudwatch_config_exists(
                    self.provider_config,
                    config_type.value,
                    "config",
            ):
                self.CLOUDWATCH_CONFIG_TYPE_TO_CLOUDWATCH_SETUP_FUNC. \
                    get(config_type.value)()

    def update_from_config(self):
        for config_type in CloudwatchConfigType:
            if CloudwatchHelper.cloudwatch_config_exists(
                    self.provider_config,
                    config_type.value,
                    "config",
            ):
                self._update_cloudwatch_config(config_type.value)

    def ssm_install_cloudwatch_agent(self):
        """Install and Start CloudWatch Agent via Systems Manager (SSM)"""

        # wait for all EC2 instance checks to complete
        try:
            logger.info(
                "Waiting for EC2 instance health checks to complete before "
                "configuring CloudWatch Unified Agent. This may take a few "
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
            "Installing the CloudWatch Unified Agent package on {} node(s). "
            "This may take a few minutes as we wait for all package updates "
            "to complete...".format(len(self.node_ids)))
        try:
            self._ssm_command_waiter(
                "AWS-ConfigureAWSPackage",
                parameters_cwa_install,
            )
            logger.info(
                "Successfully installed CloudWatch Unified Agent on {} "
                "node(s)".format(len(self.node_ids)))
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
        cwa_config_ssm_param_name = self._get_ssm_param_name(
            CloudwatchConfigType.AGENT.value)
        cwa_config = self. \
            CLOUDWATCH_CONFIG_TYPE_TO_CONFIG_VARIABLE_REPLACE_FUNC \
            .get(CloudwatchConfigType.AGENT.value)()
        self._put_ssm_param(cwa_config, cwa_config_ssm_param_name)

        # satisfy collectd preconditions before starting cloudwatch agent
        logger.info(
            "Preparing to start CloudWatch Unified Agent on {} node(s)."
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
        self._restart_cloudwatch_agent(cwa_config_ssm_param_name)

    def put_cloudwatch_dashboard(self):
        """put dashboard to cloudwatch console"""

        cloudwatch_config = self.provider_config["cloudwatch"]
        dashboard_config = cloudwatch_config \
            .get(CloudwatchConfigType.DASHBOARD.value, {})
        dashboard_name = dashboard_config.get("name", self.cluster_name)
        widgets = self. \
            CLOUDWATCH_CONFIG_TYPE_TO_CONFIG_VARIABLE_REPLACE_FUNC. \
            get(CloudwatchConfigType.DASHBOARD.value)()

        # upload cloudwatch dashboard config to the SSM parameter store
        dashboard_config_ssm_param_name = self \
            ._get_ssm_param_name(CloudwatchConfigType.DASHBOARD.value)
        self._put_ssm_param(widgets, dashboard_config_ssm_param_name)
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

        data = self._load_config_file(CloudwatchConfigType.ALARM.value)
        param_data = []
        for node_id in self.node_ids:
            for item in data:
                item_out = copy.deepcopy(item)
                self._replace_all_config_variables(
                    item_out,
                    str(node_id),
                    self.cluster_name,
                    self.provider_config["region"],
                )
                param_data.append(item_out)
                self.cloudwatch_client.put_metric_alarm(**item_out)
        logger.info("Successfully put alarms to cloudwatch console")

        # upload cloudwatch alarm config to the SSM parameter store
        alarm_config_ssm_param_name = self._get_ssm_param_name(
            CloudwatchConfigType.ALARM.value)
        self._put_ssm_param(param_data, alarm_config_ssm_param_name)

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

    def _ssm_command_waiter(self, document_name, parameters,
                            retry_failed=True):
        """ wait for SSM command to complete on all cluster nodes """

        # This waiter differs from the built-in SSM.Waiter by
        # optimistically waiting for the command invocation to
        # exist instead of failing immediately, and by resubmitting
        # any failed command until all retry attempts are exhausted
        # by default.
        response = self._send_command_to_all_nodes(
            document_name,
            parameters,
        )
        command_id = response["Command"]["CommandId"]

        cloudwatch_config = self.provider_config["cloudwatch"]
        agent_retryer_config = cloudwatch_config \
            .get(CloudwatchConfigType.AGENT.value) \
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
                        logger.debug(f"SSM Command ID {command_id} failed.")
                        if retry_failed:
                            logger.debug(
                                f"Retrying in {delay_seconds} seconds.")
                            response = self._send_command_to_nodes(
                                document_name, parameters, node_id)
                            command_id = response["Command"]["CommandId"]
                            logger.debug("Sent SSM command ID {} to node {}"
                                         .format(command_id, node_id))
                        else:
                            logger.debug(
                                f"Ignoring Command ID {command_id} failure.")
                            break
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

    def _replace_all_config_variables(self, collection, node_id, cluster_name,
                                      region):
        """
        Replace known config variable occurrences in the input collection.
        The input collection must be either a dict or list.

        Returns a tuple consisting of the output collection and the number of
        modified strings in the collection (which is not necessarily equal to
        the number of variables replaced).
        """

        modified_value_count = 0
        for key in collection:
            if type(collection) is dict:
                value = collection.get(key)
                index_key = key
            elif type(collection) is list:
                value = key
                index_key = collection.index(key)
            if type(value) is str:
                collection[index_key] = self._replace_config_variables(
                    value, node_id, cluster_name, region)
                modified_value_count += (collection[index_key] != value)
            elif type(value) is dict or type(value) is list:
                collection[index_key], modified_count = self.\
                    _replace_all_config_variables(
                    value, node_id, cluster_name, region)
                modified_value_count += modified_count
        return collection, modified_value_count

    def _load_config_file(self, config_type):
        """load JSON config file"""
        cloudwatch_config = self.provider_config["cloudwatch"]
        json_config_file_section = cloudwatch_config.get(config_type, {})
        json_config_file_path = json_config_file_section.get("config", {})
        json_config_path = os.path.abspath(json_config_file_path)
        with open(json_config_path) as f:
            data = json.load(f)
        return data

    def _set_cloudwatch_ssm_config_param(self, parameter_name, config_type):
        """
        get cloudwatch config for the given param and config type from SSM
        if it exists, put it in the SSM param store if not
        """
        try:
            parameter_value = self._get_ssm_param(parameter_name)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.info(
                    "Cloudwatch {} config file is new.".format(config_type))
                self.CLOUDWATCH_CONFIG_TYPE_TO_CLOUDWATCH_SETUP_FUNC.get(
                    config_type)()
                parameter_value = self._get_ssm_param(parameter_name)
            else:
                logger.info("Failed to fetch Cloudwatch agent config from SSM "
                            "parameter store.")
                logger.error(e)
                raise e
        return parameter_value

    def _get_ssm_param(self, parameter_name):
        """
        get the SSM parameter value associated with the given parameter name
        """
        response = self.ssm_client.get_parameter(Name=parameter_name)
        res = response.get("Parameter", {})
        cwa_parameter = res.get("Value", {})
        return cwa_parameter

    def _sha1_hash_json(self, value):
        """calculate the json string sha1 hash"""
        hash = hashlib.new("sha1")
        binary_value = value.encode("ascii")
        hash.update(binary_value)
        sha1_res = hash.hexdigest()
        return sha1_res

    def _sha1_hash_file(self, config_type):
        """calculate the config file sha1 hash"""
        config = self.CLOUDWATCH_CONFIG_TYPE_TO_CONFIG_VARIABLE_REPLACE_FUNC. \
            get(config_type)()
        value = json.dumps(config)
        sha1_res = self._sha1_hash_json(value)
        return sha1_res

    def _update_cloudwatch_config(self, config_type):
        """
        check whether update operations are needed in
        cloudwatch related configs
        """
        param_name = self._get_ssm_param_name(config_type)
        cw_config_ssm = self._set_cloudwatch_ssm_config_param(
            param_name, config_type)
        cur_cw_config_crc = self._sha1_hash_file(config_type)
        ssm_cw_config_crc = self._sha1_hash_json(cw_config_ssm)
        # check if user updated cloudwatch related config files.
        # if so, perform corresponding actions.
        if cur_cw_config_crc != ssm_cw_config_crc:
            logger.info(
                "Cloudwatch {} config file has changed.".format(config_type))
            self.CLOUDWATCH_CONFIG_TYPE_TO_UPDATE_CONFIG_FUNC.get(
                config_type)()

    def _get_ssm_param_name(self, config_type):
        """return the parameter name for cloudwatch configs"""
        ssm_config_param_name = "ray_cloudwatch_{}_config_{}".format(
            config_type, self.cluster_name)
        return ssm_config_param_name

    def _put_ssm_param(self, parameter, parameter_name):
        """upload cloudwatch config to the SSM parameter store"""
        self.ssm_client.put_parameter(
            Name=parameter_name,
            Type="String",
            Value=json.dumps(parameter),
            Overwrite=True,
            Tier="Intelligent-Tiering",
        )

    def _replace_cwa_config_variables(self):
        """
        replace known variable occurrences in cloudwatch agent config file
        """
        cwa_config = self._load_config_file(CloudwatchConfigType.AGENT.value)
        self._replace_all_config_variables(
            cwa_config,
            None,
            self.cluster_name,
            self.provider_config["region"],
        )
        return cwa_config

    def _replace_dashboard_config_variables(self):
        """
        replace known variable occurrences in cloudwatch dashboard config file
        """
        data = self._load_config_file(CloudwatchConfigType.DASHBOARD.value)
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
        return widgets

    def _replace_alarm_config_variables(self):
        """
        replace known variable occurrences in cloudwatch alarm config file
        """
        data = self._load_config_file(CloudwatchConfigType.ALARM.value)
        param_data = []
        for node_id in self.node_ids:
            for item in data:
                item_out = copy.deepcopy(item)
                self._replace_all_config_variables(
                    item_out,
                    str(node_id),
                    self.cluster_name,
                    self.provider_config["region"],
                )
                param_data.append(item_out)
        return param_data

    def _restart_cloudwatch_agent(self, cwa_param_name):
        """restart cloudwatch agent"""
        logger.info(
            "Restarting CloudWatch Unified Agent package on {} node(s)."
            .format(len(self.node_ids)))
        self._stop_cloudwatch_agent()
        self._start_cloudwatch_agent(cwa_param_name)

    def _stop_cloudwatch_agent(self):
        """stop cloudwatch agent"""
        logger.info("Stopping CloudWatch Unified Agent package on {} node(s)."
                    .format(len(self.node_ids)))
        parameters_stop_cwa = {
            "action": ["stop"],
            "mode": ["ec2"],
        }
        # don't retry failed stop commands
        # (there's not always an agent to stop)
        self._ssm_command_waiter(
            "AmazonCloudWatch-ManageAgent",
            parameters_stop_cwa,
            False,
        )
        logger.info("CloudWatch Unified Agent stopped on {} node(s).".format(
            len(self.node_ids)))

    def _start_cloudwatch_agent(self, cwa_param_name):
        """start cloudwatch agent"""
        logger.info("Starting CloudWatch Unified Agent package on {} node(s)."
                    .format(len(self.node_ids)))
        parameters_start_cwa = {
            "action": ["configure"],
            "mode": ["ec2"],
            "optionalConfigurationSource": ["ssm"],
            "optionalConfigurationLocation": [cwa_param_name],
            "optionalRestart": ["yes"],
        }
        self._ssm_command_waiter(
            "AmazonCloudWatch-ManageAgent",
            parameters_start_cwa,
        )
        logger.info(
            "CloudWatch Unified Agent started successfully on {} node(s)."
            .format(len(self.node_ids)))

    def _update_agent_config(self):
        param_name = self.\
            _get_ssm_param_name(CloudwatchConfigType.AGENT.value)
        param_cwa = self. \
            CLOUDWATCH_CONFIG_TYPE_TO_CONFIG_VARIABLE_REPLACE_FUNC. \
            get(CloudwatchConfigType.AGENT.value)()
        self._put_ssm_param(param_cwa, param_name)
        self._restart_cloudwatch_agent(param_name)

    def _update_dashboard_config(self):
        self.put_cloudwatch_dashboard()

    def _update_alarm_config(self):
        cur_alarms = self.cloudwatch_client.describe_alarms()
        metric_alarm = cur_alarms.get("MetricAlarms", [])
        if metric_alarm:
            to_be_deleted = []
            for alarm in metric_alarm:
                to_be_deleted.append(alarm.get("AlarmName"))
            self.cloudwatch_client.delete_alarms(AlarmNames=to_be_deleted)
        self.put_cloudwatch_alarm()

    @staticmethod
    def resolve_instance_profile_name(config, default_instance_profile_name):
        cwa_cfg_exists = CloudwatchHelper.cloudwatch_config_exists(
            config,
            CloudwatchConfigType.AGENT.value,
            "config",
        )
        return CLOUDWATCH_RAY_INSTANCE_PROFILE if cwa_cfg_exists \
            else default_instance_profile_name

    @staticmethod
    def resolve_iam_role_name(config, default_iam_role_name):
        cwa_cfg_exists = CloudwatchHelper.cloudwatch_config_exists(
            config,
            CloudwatchConfigType.AGENT.value,
            "config",
        )
        return CLOUDWATCH_RAY_IAM_ROLE if cwa_cfg_exists \
            else default_iam_role_name

    @staticmethod
    def resolve_policy_arns(config, default_policy_arns):
        cwa_cfg_exists = CloudwatchHelper.cloudwatch_config_exists(
            config,
            CloudwatchConfigType.AGENT.value,
            "config",
        )
        if cwa_cfg_exists:
            default_policy_arns.extend([
                "arn:aws:iam::aws:policy/CloudWatchFullAccess",
                "arn:aws:iam::aws:policy/AmazonSSMFullAccess"
            ])
        return default_policy_arns

    @staticmethod
    def cloudwatch_config_exists(config, config_type, file_name):
        """check if cloudwatch config file exists"""

        cfg = config.get("cloudwatch", {}).get(config_type, {}).get(file_name)
        if cfg:
            assert os.path.isfile(cfg), \
                "Invalid CloudWatch Config File Path: {}".format(cfg)
        return bool(cfg)
