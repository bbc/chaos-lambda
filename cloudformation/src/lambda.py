import re
import sys

from troposphere import Equals, GetAtt, If, Output, Parameter, Ref, Template
from troposphere.awslambda import Function, Code
from troposphere.iam import Role, Policy
from troposphere.events import Rule, Target


if len(sys.argv) > 2:
    source = open(sys.argv[2], "r").read()
    # Reclaim a few bytes (maximum size is 4096!) by converting four space
    # indents to single space indents
    indent_re = re.compile(r"^((?:    ){1,})", re.MULTILINE)
    source = indent_re.sub(lambda m: " " * (len(m.group(1)) / 4), source)
else:
    source = None


t = Template()
t.add_description("Chaos Lambda")

if source is None:
    s3_bucket = t.add_parameter(Parameter(
        "S3Bucket",
        Description="Name of the S3 bucket containing the Lambda zip file",
        Type="String",
    ))
    s3_key = t.add_parameter(Parameter(
        "S3Key",
        Description="Path to the Lambda zip file under the bucket",
        Type="String",
    ))
    lambda_code = Code(S3Bucket=Ref(s3_bucket), S3Key=Ref(s3_key))
    module_name = "chaos"
else:
    lambda_code = Code(ZipFile=source)
    module_name = "index"

chaos_schedule = t.add_parameter(Parameter(
    "Schedule",
    Description="Schedule on which to run",
    Default="cron(0 10-16 ? * MON-FRI *)",
    Type="String"
))

default_mode = t.add_parameter(Parameter(
    "DefaultMode",
    Description="Default mode for untagged ASGs",
    AllowedValues=["on", "off"],
    Default="on",
    Type="String"
))

default_on_condition = "DefaultOnCondition"
t.add_condition(default_on_condition, Equals(Ref(default_mode), "on"))

lambda_policy = Policy(
    PolicyName="ChaosLambdaPolicy",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ses:SendEmail",
                    "ec2:TerminateInstances",
                    "autoscaling:DescribeAutoScalingGroups"
                ],
                "Resource": "*"
            }
        ]
    }
)

lambda_role = Role(
    "ChaosLambdaRole",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Service": ["lambda.amazonaws.com"]
            },
            "Action": ["sts:AssumeRole"]
        }]
    },
    Path="/lambda/",
    Policies=[lambda_policy]
)
t.add_resource(lambda_role)

lambda_function = t.add_resource(
    Function(
        "ChaosLambdaFunction",
        Description="CloudFormation Lambda",
        Code=lambda_code,
        Handler=If(
            default_on_condition,
            module_name + ".handler",
            module_name + ".handler_default_off"
        ),
        MemorySize=128,
        Role=GetAtt(lambda_role, "Arn"),
        Runtime="python2.7",
        Timeout=30,
    )
)

chaos_lambda_rule = t.add_resource(Rule(
    "ChaosLambdaRule",
    Description="Trigger Chaos Lambda according to a schedule",
    State="ENABLED",
    ScheduleExpression=Ref(chaos_schedule),
    Targets=[
        Target(Arn=GetAtt(lambda_function, "Arn"), Id="ChaosLambdaRuleTarget")
    ]
))

t.add_output(Output(
    "ChaosLambdaFunctionOutput",
    Value=Ref(lambda_function),
    Description="The Chaos Lambda Function"
))
t.add_output(Output(
    "ChaosLambdaRuleOutput",
    Value=Ref(chaos_lambda_rule),
    Description="Rule used to trigger the Chaos Lambda"
))

template = t.to_json()
if len(sys.argv) > 1:
    open(sys.argv[1], "w").write(template + "\n")
else:
    print(template)
