# About

EC2 instances are volatile and can be recycled at any time without warning.
Amazon recommends running them under Auto Scaling Groups to ensure overall
service availability, but it's easy to forget that instances can suddenly fail
until it happens in the early hours of the morning during a holiday.

Chaos Lambda increases the rate at which these failures occur during business
hours, helping teams to build services that handle them gracefully.

Whenever the lambda is triggered it will potentially terminate one instance per
Auto Scaling Group in the region.  By default the probability of terminating an
ASG's instance is 1 in 6.  This probability can be overridden by setting a
`chaos-lambda-termination` tag on the ASG with a value between 0.0 and 1.0,
where 0.0 means never terminate and 1.0 means always terminate.


# Quick setup

Run `make zip` to create a `chaos-lambda.zip` file containing the lambda
function.  Upload it to a S3 bucket in your account, taking note of the bucket
name (eg `my-bucket`) and the path (eg `lambdas/chaos-lambda.zip`).

Create the lambda function via CloudFormation using the
`cloudformation/templates/lambda.json` template, entering the bucket name and
path.

In the AWS console go to the `Lambda` service, select the newly created lambda
function, go into the `Event sources` tab, and click `Add event source`.
Choose `Scheduled Event` for the `Event source type`, then fill in the fields
as follows (enter the `Name` first as changing it resets the other fields):
* Name: `business-hours`
* Description: `Assume things fail`
* Schedule expression: `cron(0 10-16 ? * MON-FRI *)`

Ensure `Enable now` is selected and click the `Submit` button.  You can disable
or re-enable the hourly trigger at any time by clicking the
`Enabled`/`Disabled` link in the `State` column.

To receive notifications if the lambda function fails for any reason, create
another stack using the `cloudformation/templates/alarms.json` template.  This
takes the lambda function name (something similar to
`chaos-lambda-ChaosLambdaFunction-EM2XNWWNZTPW`) and the email address to
send the alerts to.
