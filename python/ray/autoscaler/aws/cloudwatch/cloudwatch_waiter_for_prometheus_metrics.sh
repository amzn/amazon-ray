MAX_ATTEMPTS=120
DELAY_SECONDS=10
RAY_PROM_METRICS_FILE_PATH="/tmp/ray/prom_metrics_service_discovery.json"
CLUSTER_NAME=$1
while [ $MAX_ATTEMPTS -gt 0 ]; do
  if [ -f $RAY_PROM_METRICS_FILE_PATH ]; then
    echo "Restarting cloudwatch agent.This may take a few minutes..."
    sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop
    sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c ssm:ray_cloudwatch_agent_config_$CLUSTER_NAME
    exit 0
  else
    sleep $DELAY_SECONDS
    MAX_ATTEMPS=$((MAX_ATTEMPS-1))
  fi
done
