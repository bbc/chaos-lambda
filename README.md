# About

EC2 instances are volatile and can be recycled at any time without warning.
Amazon recommends running them under Auto Scaling Groups to ensure overall
service availability, but it's easy to forget that instances can suddenly fail
until it happens in the early hours of the morning when everyone is on holiday.

Chaos Lambda increases the rate at which these failures occur during business
hours, helping teams to build services that handle them gracefully.


# Quick setup

Create the lambda function in the region you want it to target using the
`cloudformation/templates/lambda_standalone.json` CloudFormation template.
There are two parameters you may want to change:
* `Schedule`: change if the default run times don't suit you (once per hour
  between 10am UTC and 4pm UTC, Monday to Friday); see
  http://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html
  for documentation on the syntax.
* `DefaultProbability`: by default all Auto Scaling Groups in the region are
  targets; set this to `0.0` and only ASGs with a `chaos-lambda-termination`
  tag (see below) will be affected.


# Notifications

## Termination Topic

By deploying the `lambda_standalone.json` CloudFormation template, an SNS topic
will be created with the name `ChaosLambdaTerminationTopic`. For each instance
that gets terminated, a notification will be published using this structure:

```json
{
  "event_name": "chaos_lambda.terminating",
  "asg_name": "my-autoscaling-group",
  "instance_id": "i-00001234"
}
```

By default, no subscriptions are created to this topic, so it is up to you to
subscribe a queue or another lambda if you wish.

## Failure topic

To receive notifications if the lambda function fails for any reason, create
another stack using the `cloudformation/templates/alarms.json` template.  This
takes the lambda function name (something similar to
`chaos-lambda-ChaosLambdaFunction-EM2XNWWNZTPW`) and the email address to
send the alerts to.


# Probability of termination

Every time the lambda triggers it examines all the Auto Scaling Groups in the
region and potentially terminates one instance in each.  The probability of
termination can be changed at the ASG level with a tag, and at a global level
with the `DefaultProbability` stack parameter.

At the ASG level the probability can be controlled by adding a
`chaos-lambda-termination` tag with a value between `0.0` (never terminate) and
`1.0` (always terminate).  Typically this would be used to opt out a legacy
system (`0.0`).

The `DefaultProbability` parameter sets the probability of termination for any
ASG _without_ a valid `chaos-lambda-termination` tag.  If set to `0.0` the
system becomes "opt-in", where any ASG without this tag is ignored.  The
default is `0.166` (or 1 in 6).


# Enabling/disabling

The lambda is triggered by a CloudWatch Events rule, the name of which can be
found from the `ChaosLambdaFunctionOutput` output of the lambda stack.  Locate
this rule in the AWS console under the Rules section of the CloudWatch service,
and you can disable or enable it via the `Actions` button.


# Regions

By default the lambda will target ASGs running in the same region.  It's
generally a good idea to avoid cross-region actions, but if necessary an
alternative list of one or more region names can be specified in the `Regions`
stack parameter.

The value is a comma separated list of region names with optional whitespace,
so the following are all valid and equivalent:
* `ap-south-1,eu-west-1,us-east-1`
* `ap-south-1, eu-west-1, us-east-1`
* `ap-south-1 , eu-west-1 , us-east-1`


# Log messages

Chaos Lambda log lines always start with a timestamp and a word specifying the
event type.  The timestamp is of the form `YYYY-MM-DDThh:mm:ssZ`, eg
`2015-12-11T14:00:37Z`, and the timezone will always be `Z`.  The different
event types are described below.

## bad-probability

`<timestamp> bad-probability [<value>] in <asg name>`

Example:

`2015-12-11T14:07:21Z bad-probability [not often] in test-app-ASG-7LJI5SY4VX6T`

If the value of the `chaos-lambda-termination` tag isn't a number between `0.0`
and `1.0` inclusive then it will be logged in one of these lines.  The square
brackets around the value allow CloudWatch Logs to find the full value even if
it contains spaces.

## result

`<timestamp> result <instance id> is <state>`

Example:

`2015-12-11T14:00:40Z result i-fe705d77 is shutting-down`

After asking EC2 to terminate each of the targeted instances the new state of
each is logged with a `result` line.  The `<state>` value is taken from the
`code` property of the `InstanceState` AWS type described at
http://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_InstanceState.html

## targeting

`<timestamp> targeting <instance id> in <asg name>`

Example:

`2015-12-11T14:00:38Z targeting i-168f9eaf in test-app-ASG-1LOMEKEVBXXXS`

The `targeting` lines list all of the instances that are about to be
terminated, before the `TerminateInstances` call occurs.

## triggered

`<timestamp> triggered <region>`

Example:

`2015-12-11T14:00:37Z triggered eu-west-1`

Generated when the lambda is triggered, indicating the region that will be
affected.
