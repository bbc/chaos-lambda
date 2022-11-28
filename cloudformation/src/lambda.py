import re
import sys

from troposphere import GetAtt, Output, Parameter, Ref, Template
from troposphere.awslambda import Code, Environment, Function, Permission
from troposphere.logs import LogGroup
from troposphere.iam import Role, Policy
from troposphere.events import Rule, Target
from troposphere.sns import Topic


if len(sys.argv) > 2:
    source = open(sys.argv[2], "r").read()
    # Reclaim a few bytes (maximum size is 4096!) by converting four space
    # indents to single space indents
    indent_re = re.compile(r"^((?:    ){1,})", re.MULTILINE)
    source = indent_re.sub(lambda m: " " * (len(m.group(1)) // 4), source)
else:
    source = None


t = Template()
t.set_description("Chaos Lambda")

if source is None:
    s3_bucket = t.add_parameter(Parameter(
        "S3Bucket",
        Description="Name of the S3 bucket containing the Lambda zip file",
        Type="String",
    ))
    s3_key = t.add_parameter(Parameter(
        "S3Key",
        Description="Path to the Lambda zip file under the bucket",
        Default="chaos-lambda.zip",
        Type="String",
    ))
    lambda_code = Code(S3Bucket=Ref(s3_bucket), S3Key=Ref(s3_key))
    module_name = "chaos"
else:
    lambda_code = Code(ZipFile=source)
    module_name = "index"

chaos_schedule = t.add_parameter(Parameter(
    "Schedule",
    Description="Schedule on which to run (UTC time zone)",
    Default="cron(0 10-16 ? * MON-FRI *)",
    Type="String"
))

default_probability = t.add_parameter(Parameter(
    "DefaultProbability",
    Description="Default termination probability",
    Default=1.0 / 6.0,
    MinValue=0.0,
    MaxValue=1.0,
    Type="Number"
))

regions = t.add_parameter(Parameter(
    "Regions",
    Description="Override default region with comma-separated list of regions",
    Type="String"
))

termination_topic = t.add_resource(
    Topic("ChaosLambdaTerminationTopic")
)

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
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sns:Publish"
                ],
                "Resource": Ref(termination_topic)
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

t.add_resource(LogGroup(
    "ChaosLambdaLogGroup",
    LogGroupName="aws/lambda/chaos-lambda",
    RetentionInDays=90,
))

lambda_function = t.add_resource(Function(
    "ChaosLambdaFunction",
    Description="CloudFormation Lambda",
    FunctionName="chaos-lambda",
    Code=lambda_code,
    Environment=Environment(Variables={
        "probability": Ref(default_probability),
        "regions": Ref(regions),
        "termination_topic_arn": Ref(termination_topic),
    }),
    Handler=module_name + ".handler",
    MemorySize=128,
    Role=GetAtt(lambda_role, "Arn"),
    Runtime="python3.8",
    Timeout=30,
))

chaos_lambda_rule = t.add_resource(Rule(
    "ChaosLambdaRule",
    Description="Trigger Chaos Lambda according to a schedule",
    State="ENABLED",
    ScheduleExpression=Ref(chaos_schedule),
    Targets=[
        Target(Arn=GetAtt(lambda_function, "Arn"), Id="ChaosLambdaRuleTarget")
    ]
))
t.add_resource(Permission(
    "ChaosLambdaRulePermission",
    FunctionName=GetAtt(lambda_function, "Arn"),
    SourceArn=GetAtt(chaos_lambda_rule, "Arn"),
    Principal="events.amazonaws.com",
    Action="lambda:InvokeFunction"
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
