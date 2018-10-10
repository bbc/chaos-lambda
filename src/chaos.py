from __future__ import print_function

import json
import os
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


def send_notification(sns, instance_id, asg_name):
    topic = os.environ.get("termination_topic_arn", "").strip()
    if topic == '':
        return
    notification = {
        "event_name": "chaos_lambda.terminating",
        "instance_id": instance_id,
        "asg_name": asg_name,
    }
    sns.publish(
        TopicArn=topic,
        Message=json.dumps(notification)
    )


def terminate_targets(ec2, sns, targets):
    for asg_name, instance_id in targets:
        log("targeting", instance_id, "in", asg_name)
        send_notification(sns, instance_id, asg_name)

    instance_ids = [instance_id for (asg_name, instance_id) in targets]
    response = ec2.terminate_instances(InstanceIds=instance_ids)

    results = []
    for i in response.get("TerminatingInstances", []):
        results.append((i["InstanceId"], i["CurrentState"]["Name"]))

    for instance_id, state in results:
        log("result", instance_id, "is", state)

    return results


def chaos_lambda(regions, default_probability):
    for region in regions:
        log("triggered", region)
        autoscaling = boto3.client("autoscaling", region_name=region)
        targets = get_targets(autoscaling, default_probability)
        if len(targets) != 0:
            ec2 = boto3.client("ec2", region_name=region)
            sns = boto3.client("sns", region_name=region)
            terminate_targets(ec2, sns, targets)


def get_regions(context):
    v = os.environ.get("regions", "").strip()
    if len(v) == 0:
        return [context.invoked_function_arn.split(":")[3]]
    else:
        return filter(None, [s.strip() for s in v.split(",")])


def get_default_probability():
    v = os.environ.get("probability", "").strip()
    if len(v) == 0:
        return DEFAULT_PROBABILITY
    else:
        return float(v)


def handler(event, context):
    regions = get_regions(context)
    probability = get_default_probability()
    chaos_lambda(regions, probability)
