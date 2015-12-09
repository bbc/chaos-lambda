from __future__ import print_function

import random
import time

import boto3


TERMINATE_PROBABILITY = 1.0 / 6.0


def get_asg_instance_id(asg):
    instances = asg.get("Instances", [])
    if len(instances) == 0:
        return None
    elif random.random() > TERMINATE_PROBABILITY:
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


def lambda_monkey(region):
    autoscaling = boto3.client("autoscaling", region_name=region)
    targets = get_targets(autoscaling)

    if len(targets) == 0:
        return

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for asg_name, instance_id in targets:
        print(timestamp, "targeting", instance_id, "in", asg_name)

    instance_ids = [instance_id for (asg_name, instance_id) in targets]
    ec2 = boto3.client("ec2", region_name=region)
    ec2.terminate_instances(InstanceIds=instance_ids)


def handler(event, context):
    lambda_monkey("eu-west-1")
