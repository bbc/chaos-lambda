from __future__ import print_function

import random
import time

import boto3


PROBABILITY_TAG = "lambda-monkey-termination"
DEFAULT_PROBABILITY = 1.0 / 6.0


def log(*args):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(timestamp, *args)


def get_asg_tag(asg, name, default=None):
    name = name.lower()
    for tag in asg.get("Tags", []):
        if tag.get("Key", "").lower() == name:
            return tag.get("Value", "")
    return default


def safe_float(s, default):
    try:
        return float(s)
    except ValueError:
        return default


def get_asg_instance_id(asg):
    instances = asg.get("Instances", [])

    value = get_asg_tag(asg, PROBABILITY_TAG, "")
    probability = safe_float(value, DEFAULT_PROBABILITY)

    if len(instances) == 0:
        return None
    elif random.random() >= probability:
        return None
    else:
        return random.choice(instances).get("InstanceId", None)


def get_targets(autoscaling):
    response = autoscaling.describe_auto_scaling_groups()

    targets = []
    for asg in response.get("AutoScalingGroups", []):
        instance_id = get_asg_instance_id(asg)
        if instance_id is not None:
            targets.append((asg["AutoScalingGroupName"], instance_id))

    return targets


def terminate_targets(ec2, targets):
    for asg_name, instance_id in targets:
        log("targeting", instance_id, "in", asg_name)

    instance_ids = [instance_id for (asg_name, instance_id) in targets]
    response = ec2.terminate_instances(InstanceIds=instance_ids)
    for i in response.get("TerminatingInstances", []):
        log("result", i["InstanceId"], "is", i["CurrentState"]["Name"])


def lambda_monkey(region):
    autoscaling = boto3.client("autoscaling", region_name=region)
    targets = get_targets(autoscaling)
    if len(targets) != 0:
        ec2 = boto3.client("ec2", region_name=region)
        terminate_targets(ec2, targets)


def handler(event, context):
    region = context.invoked_function_arn.split(":")[3]
    log("triggered", region)
    lambda_monkey(region)
