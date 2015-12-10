import json
from troposphere import Template, Ref, Parameter
from troposphere.logs import MetricFilter, MetricTransformation

METRIC_NAMESPACE = "BBC/LAMBDA-MONKEY"

t = Template()

log_group = t.add_parameter(
    Parameter(
        "LambdaLogGroupName",
        Description="The name of the log group for the lambda function.",
        Type="String",
    )
)

t.add_description(
    "Metrics and filters for Github Monitor"
)

lambda_metrics = {
    "liveliness": {
        "FilterPattern": (
            "[datetime, event=\"triggered\", ...]"
        ),
        "MetricTransformations": [
            MetricTransformation(
                MetricNamespace=METRIC_NAMESPACE,
                MetricName="triggered",
                MetricValue="1",
            )
        ]
    }
}

for name, metric in lambda_metrics.iteritems():
    metric["LogGroupName"] = Ref(log_group)
    t.add_resource(MetricFilter(name, **metric))

print t.to_json()
