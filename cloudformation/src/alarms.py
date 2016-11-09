from troposphere import Parameter, Ref, Template
from troposphere.cloudwatch import Alarm, MetricDimension
from troposphere.sns import Subscription, Topic


METRIC_NAMESPACE = "BBC/CHAOS-LAMBDA"

t = Template()

t.add_description("Chaos Lambda alarms")

alarm_email = t.add_parameter(
    Parameter(
        "ChaosLambdaAlarmEmail",
        Description="Email address to notify if there are any "
                    "operational issues",
        Type="String",
    )
)

lambda_function_name = t.add_parameter(
    Parameter(
        "LambdaFunctionName",
        Description="The name of the lambda function",
        Type="String",
    )
)

alarm_topic = t.add_resource(
    Topic(
        "ChaosLambdaAlarmTopic",
        Subscription=[
            Subscription(
                Endpoint=Ref(alarm_email),
                Protocol="email"
            ),
        ],
    )
)

t.add_resource(
    Alarm(
        "ChaosLambdaErrorAlarm",
        AlarmName="chaosLambda/LambdaError",
        AlarmDescription="Enters ALARM state because we have received a "
                         "lamdba error. See 'Errors' section on the following "
                         "link: http://docs.aws.amazon.com/lambda/latest/dg/"
                         "monitoring-functions-metrics.html for more "
                         "information.",
        Namespace="AWS/Lambda",
        MetricName="Errors",
        Dimensions=[
            MetricDimension(
                Name="FunctionName",
                Value=Ref(lambda_function_name)
            ),
        ],
        Statistic="Sum",
        Period="60",
        EvaluationPeriods="1",
        Threshold="1",
        Unit="Count",
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        AlarmActions=[Ref(alarm_topic), ],
    )
)

t.add_resource(
    Alarm(
        "ChaosLambdaDurationAlarm",
        AlarmName="chaosLambda/LambdaDuration",
        AlarmDescription="Enters ALARM state because we have functions taking "
                         "longer than expected. Please adjust the available "
                         "lambda process time accordingly, then replay any "
                         " failed events. See 'Duration' section on the "
                         " following link: "
                         "http://docs.aws.amazon.com/lambda/latest/dg/"
                         "monitoring-functions-metrics.html for more "
                         "information.",
        Namespace="AWS/Lambda",
        MetricName="Duration",
        Dimensions=[
            MetricDimension(
                Name="FunctionName",
                Value=Ref(lambda_function_name)
            ),
        ],
        Statistic="Maximum",
        Period="60",
        EvaluationPeriods="1",
        Threshold="7000",
        Unit="Milliseconds",
        ComparisonOperator="GreaterThanThreshold",
        AlarmActions=[Ref(alarm_topic), ],
    )
)

'''
t.add_resource(
    Alarm(
        "Liveliness",
        AlarmName="chaosLambda/Liveliness",
        AlarmDescription="Enters ALARM state if the Chaos Lambda hasn't "
                         "triggered within a seven day window.",
        Namespace=METRIC_NAMESPACE,
        MetricName="triggered",
        EvaluationPeriods="1",
        Period="604800",
        Statistic="SampleCount",
        ComparisonOperator="LessThanThreshold",
        Threshold="1",
        Unit="None",
        AlarmActions=[Ref(alarm_topic)],
    )
)
'''

print(t.to_json())
