# About

EC2 instances are volatile and can be recycled at any time without warning.
Amazon recommends running them under Auto Scaling Groups to ensure overall
service availability, but it's easy to forget that instances can suddenly fail
until it happens in the early hours of the morning during a holiday.

Chaos Lambda increases the rate at which these failures occur during business
hours, helping teams to build services that handle them gracefully.


# Setup

Run `make zip` to create a `chaos-lambda.zip` file containing the lambda
function.  Upload it to a S3 bucket in your account, taking note of the bucket
name (eg `my-bucket`) and the path (eg `lambdas/chaos-lambda.zip`).

Create the lambda function via CloudFormation using the
`cloudformation/templates/lambda.json` template, entering the bucket name and
path.  Adjust the `Schedule` parameter if the default run times don't suit you
(once per hour between 10am and 4pm, Monday to Friday); see
http://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html
for documentation on the syntax.

By default all Auto Scaling Groups in the region are targets.  Set the
`DefaultMode` parameter to `off` to change this, so that only ASGs with a
`chaos-lambda-termination` tag (see below) are affected.

To receive notifications if the lambda function fails for any reason, create
another stack using the `cloudformation/templates/alarms.json` template.  This
takes the lambda function name (something similar to
`chaos-lambda-ChaosLambdaFunction-EM2XNWWNZTPW`) and the email address to
send the alerts to.


# Probability of termination

Whenever the lambda is triggered it will potentially terminate one instance per
Auto Scaling Group in the region.  By default the probability of terminating an
ASG's instance is 1 in 6.  This probability can be overridden by setting a
`chaos-lambda-termination` tag on the ASG with a value between 0.0 and 1.0,
where 0.0 means never terminate and 1.0 means always terminate.


# Enabling/disabling

The lambda is triggered by a CloudWatch Events rule, the name of which can be
found from the `ChaosLambdaFunctionOutput` output of the lambda stack.  Locate
this rule in the AWS console under the Rules section of the CloudWatch service,
and you can disable or enable it via the `Actions` button.


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
