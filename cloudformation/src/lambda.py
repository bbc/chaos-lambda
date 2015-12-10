from troposphere import Output, Ref, Template, Parameter, GetAtt
from troposphere.iam import Role, Policy
from troposphere.awslambda import Function, Code

t = Template()
t.add_description("CloudFormation template for the Lambda Monkey")

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

lambda_policy = Policy(
    PolicyName="LambdaMonkeyPolicy",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:*",
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
    "LambdaMonkeyRole",
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
        "LambdaMonkeyFunction",
        Code=Code(
            S3Bucket=Ref(s3_bucket),
            S3Key=Ref(s3_key)
        ),
        Description="CloudFormation Lambda",
        Handler="lmonkey.handler",
        MemorySize=128,
        Role=GetAtt(lambda_role, "Arn"),
        Runtime="python2.7",
        Timeout=30
    )
)

t.add_output(Output(
    "LambdaMonkeyFunctionOutput",
    Value=Ref(lambda_function),
    Description="The Lambda Monkey Function"
))

print(t.to_json())
