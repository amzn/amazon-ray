###########################################################################################################
#This bash script is meant to support prometheus metrics collection via cloudwatch agent.
#You can view the ray metrics being collected through AWS CloudWatch console.
###########################################################################################################

USAGE_INSTRUCTIONS='Usage: prometheus_ray_up.sh [OPTIONS] CLUSTER_CONFIG_FILE'

# ray up to start a new cluster
ray up "$@"

if [ $? -eq 0 ]; then
  AUTOSCALER_CONFIG_FILE=$(sed 's/.* //' <<< "$@")
  if [ ! -f "$AUTOSCALER_CONFIG_FILE" ]; then
    echo "Cluster config file not found"
    echo "$USAGE_INSTRUCTIONS"
    exit 1
  else
    CLUSTER_NAME=$(grep 'cluster_name' $AUTOSCALER_CONFIG_FILE| cut -d ':' -f 2 | xargs)
  fi

  # TODO remove the version number hardcoding from this script
  # download the latest prometheus
  ray exec "$AUTOSCALER_CONFIG_FILE" "sudo wget https://github.com/prometheus/prometheus/releases/download/v2.25.0/prometheus-2.25.0.linux-amd64.tar.gz -P /opt"
  ray exec "$AUTOSCALER_CONFIG_FILE" "cd /opt && sudo tar xvfz prometheus-2.25.0.linux-amd64.tar.gz"
  echo "Successfully installed prometheus on head node"

  # replace the default prometheus server configuration with ray services discovery supported configuration
  ray exec "$AUTOSCALER_CONFIG_FILE" "sudo cp --remove-destination /tmp/prometheus.yml /opt/prometheus-2.25.0.linux-amd64"
  echo "Successfully configured prometheus on head node"

  # start the prometheus server
  ray exec "$AUTOSCALER_CONFIG_FILE" "cd /opt/prometheus-2.25.0.linux-amd64 && sudo ./prometheus --config.file=prometheus.yml --web.enable-lifecycle --log.level=info &"
  echo "Successfully started prometheus on head node"

  # restart the cloudwatch agent with prometheus integrated
  echo "Restarting cloudwatch agent...this may take a few minutes."
  ray exec "$AUTOSCALER_CONFIG_FILE" "sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop"
  ray exec "$AUTOSCALER_CONFIG_FILE" "sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c ssm:ray_cloudwatch_agent_config_$CLUSTER_NAME"

else
  echo "Failed while waiting for ray up command to complete."
fi
