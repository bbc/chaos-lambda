from __future__ import print_function

import random
import time

import boto3


PROBABILITY_TAG = "chaos-lambda-termination"
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


def get_asg_probability(asg, default):
    value = get_asg_tag(asg, PROBABILITY_TAG, None)
    if value is None:
        return default

    probability = safe_float(value, None)
    if probability is not None and 0.0 <= probability <= 1.0:
        return probability

    asg_name = asg["AutoScalingGroupName"]
    log("bad-probability", "[" + value + "]", "in", asg_name)
    return default


def get_asg_instance_id(asg, default):
    instances = asg.get("Instances", [])
    if len(instances) == 0:
        return None

    probability = get_asg_probability(asg, default)
    if random.random() >= probability:
        return None
    else:
        return random.choice(instances).get("InstanceId", None)


def get_all_asgs(autoscaling):
    paginator = autoscaling.get_paginator("describe_auto_scaling_groups")
    for response in paginator.paginate():
        for asg in response.get("AutoScalingGroups", []):
            yield asg


def get_targets(autoscaling, default_probability):
    targets = []
    for asg in get_all_asgs(autoscaling):
        instance_id = get_asg_instance_id(asg, default_probability)
        if instance_id is not None:
            targets.append((asg["AutoScalingGroupName"], instance_id))
    return targets


def terminate_targets(ec2, targets):
    for asg_name, instance_id in targets:
        log("targeting", instance_id, "in", asg_name)

    instance_ids = [instance_id for (asg_name, instance_id) in targets]
    response = ec2.terminate_instances(InstanceIds=instance_ids)

    results = []
    for i in response.get("TerminatingInstances", []):
        results.append((i["InstanceId"], i["CurrentState"]["Name"]))

    for instance_id, state in results:
        log("result", instance_id, "is", state)

    return results


def chaos_lambda(region, default_probability):
    log("triggered", region)
    autoscaling = boto3.client("autoscaling", region_name=region)
    targets = get_targets(autoscaling, default_probability)
    if len(targets) != 0:
        ec2 = boto3.client("ec2", region_name=region)
        terminate_targets(ec2, targets)


def handler(event, context):
    region = context.invoked_function_arn.split(":")[3]
    chaos_lambda(region, DEFAULT_PROBABILITY)


def handler_default_off(event, context):
    region = context.invoked_function_arn.split(":")[3]
    chaos_lambda(region, 0.0)
