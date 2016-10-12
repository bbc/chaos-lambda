from troposphere import Output, Ref, Template, Parameter, GetAtt
from troposphere.awslambda import Function, Code
from troposphere.iam import Role, Policy
from troposphere.events import Rule, Target

t = Template()
t.add_description("CloudFormation template for the Chaos Lambda")

s3_bucket = t.add_parameter(Parameter(
    "S3Bucket",
    Description="S3Bucket Parameter",
    Type="String",
))

s3_key = t.add_parameter(Parameter(
    "S3Key",
    Description="S3Key Parameter",
    Type="String",
))

chaos_schedule = t.add_parameter(Parameter(
    "Schedule",
    Description="Schedule on which to run the Chaos Lambda",
    Default="cron(0 10-16 ? * MON-FRI *)",
    Type="String"
))

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
        Code=Code(
            S3Bucket=Ref(s3_bucket),
            S3Key=Ref(s3_key)
        ),
        Description="CloudFormation Lambda",
        Handler="chaos.handler",
        MemorySize=128,
        Role=GetAtt(lambda_role, "Arn"),
        Runtime="python2.7",
        Timeout=30
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

print(t.to_json())
