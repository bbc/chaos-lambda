from __future__ import print_function

import json
import re

from unittest import mock

from base import mock_imports, PatchingTestCase

mock_imports([
    "boto3"
])  # noqa

import chaos


class TestGetASGTag(PatchingTestCase):

    def test_finds_tag_key_case_insensitively(self):
        asg = {"Tags": [{"Key": "name", "Value": "success"}]}
        self.assertEqual(chaos.get_asg_tag(asg, "NAME"), "success")
        self.assertEqual(chaos.get_asg_tag(asg, "name"), "success")
        self.assertEqual(chaos.get_asg_tag(asg, "NaMe"), "success")

    def test_returns_default_if_key_not_found(self):
        asg = {"Tags": []}
        self.assertEqual(chaos.get_asg_tag(asg, "blah"), None)
        self.assertEqual(chaos.get_asg_tag(asg, "blah", "abc"), "abc")

    def test_returns_empty_string_if_tag_has_no_value(self):
        # As far as I can tell this should never happen, but just in case...
        asg = {"Tags": [{"Key": "name"}]}
        self.assertEqual(chaos.get_asg_tag(asg, "name"), "")


class TestSafeFloat(PatchingTestCase):

    def test_returns_float_if_string_is_valid(self):
        self.assertEqual(chaos.safe_float("1.0", 0.5), 1.0)
        self.assertEqual(chaos.safe_float("0.0", 0.5), 0.0)
        self.assertEqual(chaos.safe_float(" 1.0 ", 0.5), 1.0)

    def test_returns_default_if_string_is_invalid(self):
        self.assertEqual(chaos.safe_float("not a number", 0.5), 0.5)


class TestGetASGProbability(PatchingTestCase):

    patch_list = (
        "chaos.PROBABILITY_TAG",
        "chaos.get_asg_tag",
        "chaos.log"
    )

    def get_log_lines(self, name):
        lines = []
        for args, kwargs in self.log.call_args_list:
            parts = re.findall(r"\[.*?\]|[^ ]+", " ".join(args))
            if parts[0] == name:
                lines.append(parts)
        return lines

    def test_returns_default_probability_if_no_tag_set(self):
        self.get_asg_tag.return_value = None
        p = chaos.get_asg_probability({}, mock.sentinel.default)
        self.assertEqual(p, mock.sentinel.default)

    def test_queries_probability_tag(self):
        self.get_asg_tag.return_value = "0.1"
        chaos.get_asg_probability(mock.sentinel.asg, None)
        self.get_asg_tag.assert_called_once_with(
            mock.sentinel.asg,
            self.PROBABILITY_TAG,
            mock.ANY
        )

    def test_returns_probability_from_tag_value_if_valid(self):
        self.get_asg_tag.return_value = "0.1"
        p = chaos.get_asg_probability({"AutoScalingGroupName": "x"}, None)
        self.assertEqual(p, 0.1)

    def test_returns_default_probability_if_tag_value_is_invalid(self):
        asg = {"AutoScalingGroupName": "x"}
        default = mock.sentinel.default
        self.get_asg_tag.return_value = "blah"
        p = chaos.get_asg_probability(asg, default)
        self.assertEqual(p, default)

    def test_returns_default_probability_if_tag_value_is_out_of_range(self):
        asg = {"AutoScalingGroupName": "x"}
        default = mock.sentinel.default
        for value in ("-42", "-1.2", "1.2", "9"):
            self.get_asg_tag.return_value = value
            p = chaos.get_asg_probability(asg, default)
            self.assertEqual(p, default)

    def test_logs_parseable_error_if_tag_value_is_invalid(self):
        asg = {"AutoScalingGroupName": "ASGNameHere"}
        for value in ("blah", "-42", "0.1 0.2"):
            self.log.reset_mock()
            self.get_asg_tag.return_value = value
            chaos.get_asg_probability(asg, None)
            lines = self.get_log_lines("bad-probability")
            self.assertEqual(set((p[1], p[3]) for p in lines), set([
                ("[" + value + "]", "ASGNameHere")
            ]))


class TestGetASGInstanceId(PatchingTestCase):

    patch_list = (
        "chaos.get_asg_probability",
        "random.choice",
        "random.random",
    )

    def test_returns_None_if_there_are_no_instances(self):
        self.random.return_value = 1.0
        asg = {"Instances": []}
        self.assertEqual(chaos.get_asg_instance_id(asg, 0), None)
        asg = {}
        self.assertEqual(chaos.get_asg_instance_id(asg, 0), None)

    def test_returns_None_if_probability_test_fails(self):
        self.choice.side_effect = lambda l: l[0]
        self.get_asg_probability.return_value = 0.5
        self.random.return_value = 1.0
        asg = {"Instances": [{"InstanceId": "i-1234abcd"}]}
        default = mock.sentinel.default
        self.assertEqual(chaos.get_asg_instance_id(asg, default), None)
        self.get_asg_probability.assert_called_once_with(asg, default)

    def test_returns_instance_id_if_probability_test_succeeds(self):
        self.choice.side_effect = lambda l: l[0]
        self.get_asg_probability.return_value = 0.5
        self.random.return_value = 0.0
        asg = {"Instances": [{"InstanceId": "i-1234abcd"}]}
        default = mock.sentinel.default
        self.assertEqual(chaos.get_asg_instance_id(asg, default), "i-1234abcd")
        self.get_asg_probability.assert_called_once_with(asg, default)

    def test_returns_random_choice_of_instance_ids(self):
        self.get_asg_probability.return_value = 0.5
        self.random.return_value = 0.0
        instances = [
            {"InstanceId": "i-00000000"},
            {"InstanceId": "i-11111111"},
            {"InstanceId": "i-22222222"}
        ]
        i = chaos.get_asg_instance_id({"Instances": instances}, 0)
        self.choice.assert_called_once_with(instances)
        self.assertEqual(i, self.choice.return_value.get.return_value)


class TestGetAllASGs(PatchingTestCase):

    def test_uses_paginator_for_describe_auto_scaling_groups(self):
        autoscaling = mock.Mock()
        paginator = autoscaling.get_paginator.return_value
        paginator.paginate.return_value = iter([])
        asgs = chaos.get_all_asgs(autoscaling)
        list(asgs)  # force evaluation of the generator
        autoscaling.get_paginator.assert_called_once_with(
            "describe_auto_scaling_groups"
        )
        paginator.paginate.assert_called_once_with()

    def test_yields_asgs_from_each_response(self):
        autoscaling = mock.Mock()
        paginator = autoscaling.get_paginator.return_value
        paginator.paginate.return_value = iter([
            {"AutoScalingGroups": [mock.sentinel.one, mock.sentinel.two]},
            {"AutoScalingGroups": [mock.sentinel.three]},
            {"AutoScalingGroups": [mock.sentinel.four, mock.sentinel.five]}
        ])
        asgs = chaos.get_all_asgs(autoscaling)
        self.assertEqual(set(asgs), set([
            mock.sentinel.one,
            mock.sentinel.two,
            mock.sentinel.three,
            mock.sentinel.four,
            mock.sentinel.five
        ]))

    def test_ignores_responses_with_missing_AutoScalingGroups_key(self):
        autoscaling = mock.Mock()
        paginator = autoscaling.get_paginator.return_value
        paginator.paginate.return_value = iter([
            {"AutoScalingGroups": [mock.sentinel.one]},
            {},
            {"AutoScalingGroups": [mock.sentinel.two]}
        ])
        asgs = chaos.get_all_asgs(autoscaling)
        self.assertEqual(set(asgs), set([
            mock.sentinel.one,
            mock.sentinel.two
        ]))


class TestGetTargets(PatchingTestCase):

    patch_list = (
        "chaos.get_all_asgs",
        "chaos.get_asg_instance_id",
    )

    def test_requests_all_auto_scaling_groups(self):
        autoscaling = mock.Mock()
        self.get_all_asgs.return_value = iter([])
        chaos.get_targets(autoscaling, 0)
        self.get_all_asgs.assert_called_once_with(autoscaling)

    def test_returns_empty_list_if_no_auto_scaling_groups(self):
        autoscaling = mock.Mock()
        self.get_all_asgs.return_value = iter([])
        self.assertEqual(chaos.get_targets(autoscaling, 0), [])

    def test_passes_default_probability_to_get_asg_instance_id(self):
        autoscaling = mock.Mock()
        asg = {"AutoScalingGroupName": "a", "Instances": ["i-11111111"]}
        default = mock.sentinel.default_probablity
        self.get_asg_instance_id.return_value = None
        self.get_all_asgs.return_value = iter([asg])
        chaos.get_targets(autoscaling, default)
        self.get_asg_instance_id.assert_called_once_with(asg, default)

    def test_gets_instance_from_each_asg(self):
        autoscaling = mock.Mock()
        self.get_asg_instance_id.side_effect = lambda asg, default: \
            asg["Instances"][0]
        self.get_all_asgs.return_value = iter([
            {"AutoScalingGroupName": "a", "Instances": ["i-11111111"]},
            {"AutoScalingGroupName": "b", "Instances": ["i-22222222"]},
            {"AutoScalingGroupName": "c", "Instances": ["i-33333333"]}
        ])
        targets = chaos.get_targets(autoscaling, 0)
        self.assertEqual(set(targets), set([
            ("a", "i-11111111"),
            ("b", "i-22222222"),
            ("c", "i-33333333")
        ]))

    def test_ignores_asgs_with_no_instances(self):
        autoscaling = mock.Mock()
        self.get_asg_instance_id.side_effect = lambda asg, default: \
            asg["Instances"][0] if len(asg["Instances"]) != 0 else None
        self.get_all_asgs.return_value = iter([
            {"AutoScalingGroupName": "a", "Instances": []},
            {"AutoScalingGroupName": "b", "Instances": ["i-22222222"]},
            {"AutoScalingGroupName": "c", "Instances": []}
        ])
        targets = chaos.get_targets(autoscaling, 0)
        self.assertEqual(targets, [("b", "i-22222222")])


class TestTerminateTargets(PatchingTestCase):

    patch_list = (
        "chaos.log",
        "chaos.os"
    )

    def get_log_lines(self, name):
        lines = []
        for args, kwargs in self.log.call_args_list:
            parts = re.findall(r"\[.*?\]|[^ ]+", " ".join(args))
            if parts[0] == name:
                lines.append(parts)
        return lines

    def test_terminates_target_instances(self):
        ec2 = mock.Mock()
        sns = mock.Mock()
        ec2.terminate_instances.return_value = {}
        chaos.terminate_targets(ec2, sns, [
            ("a", "i-11111111"),
            ("b", "i-22222222")
        ])
        ec2.terminate_instances.assert_called_once_with(
            InstanceIds=["i-11111111", "i-22222222"]
        )

    def test_parseable_log_line_for_each_targeted_instance(self):
        ec2 = mock.Mock()
        sns = mock.Mock()
        ec2.terminate_instances.return_value = {}
        chaos.terminate_targets(ec2, sns, [
            ("asg-name-one", "i-00000000"),
            ("second-asg", "i-11111111"),
            ("the-third-asg", "i-22222222")
        ])
        logged = self.get_log_lines("targeting")
        self.assertEqual(set((part[1], part[3]) for part in logged), set([
            ("i-00000000", "asg-name-one"),
            ("i-11111111", "second-asg"),
            ("i-22222222", "the-third-asg")
        ]))

    def test_parseable_log_line_for_each_termination_result(self):
        ec2 = mock.Mock()
        sns = mock.Mock()
        # We're cheating here and returning results that are unrelated to the
        # list passed to terminate_targets
        ec2.terminate_instances.return_value = {
            "TerminatingInstances": [
                {"InstanceId": "i-00000000", "CurrentState": {"Name": "s1"}},
                {"InstanceId": "i-11111111", "CurrentState": {"Name": "s2"}},
                {"InstanceId": "i-22222222", "CurrentState": {"Name": "s3"}}
            ]
        }
        chaos.terminate_targets(ec2, sns, [("a", "i-11111111")])
        logged = self.get_log_lines("result")
        self.assertEqual(set((part[1], part[3]) for part in logged), set([
            ("i-00000000", "s1"),
            ("i-11111111", "s2"),
            ("i-22222222", "s3")
        ]))

    def test_returns_termination_results(self):
        ec2 = mock.Mock()
        sns = mock.Mock()
        # We're cheating here and returning results that are unrelated to the
        # list passed to terminate_targets
        ec2.terminate_instances.return_value = {
            "TerminatingInstances": [
                {"InstanceId": "i-00000000", "CurrentState": {"Name": "s1"}},
                {"InstanceId": "i-11111111", "CurrentState": {"Name": "s2"}},
                {"InstanceId": "i-22222222", "CurrentState": {"Name": "s3"}}
            ]
        }
        results = chaos.terminate_targets(ec2, sns, [])
        self.assertEqual(set(results), set([
            ("i-00000000", "s1"),
            ("i-11111111", "s2"),
            ("i-22222222", "s3")
        ]))

    def test_sends_notification_per_instance(self):
        self.os.environ.get.return_value = "MyTestTopic"
        ec2 = mock.Mock()
        sns = mock.Mock()
        ec2.terminate_instances.return_value = {
            "TerminatingInstances": []
        }
        chaos.terminate_targets(ec2, sns, [("a1", "i1"), ("a2", "i2")])
        sns.publish.assert_any_call(
            TopicArn="MyTestTopic",
            Message=MatchJson({
                "event_name": "chaos_lambda.terminating",
                "asg_name": "a1",
                "instance_id": "i1"
            })
        )
        sns.publish.assert_any_call(
            TopicArn="MyTestTopic",
            Message=MatchJson({
                "event_name": "chaos_lambda.terminating",
                "asg_name": "a2",
                "instance_id": "i2"
            })
        )
        self.assertEqual(2, sns.publish.call_count)

    def test_handles_sns_exception(self):
        self.os.environ.get.return_value = "MyTestTopic"
        ec2 = mock.Mock()
        sns = mock.Mock()
        ec2.terminate_instances.return_value = {}

        sns.publish.side_effect = Exception("boom")
        chaos.terminate_targets(ec2, sns, [
            ("a", "i-11111111"),
            ("b", "i-22222222")
        ])
        ec2.terminate_instances.assert_called_once_with(
            InstanceIds=["i-11111111", "i-22222222"]
        )


class MatchJson:
    '''
    A JSON Matcher that takes a Dictionary as input, checking that those
    specified keys and values exist in the JSON string that is supplied. It
    does not check if there are any other keys in the JSON string.
    '''
    def __init__(self, expected):
        self.expected = expected

    def __repr__(self):
        return "'" + json.dumps(self.expected) + "'"

    def __eq__(self, json_string):
        try:
            parsed_json = json.loads(json_string)
            for key in self.expected.keys():
                try:
                    if self.expected[key] != parsed_json[key]:
                        return False
                except KeyError:
                    print("The key '" + key + "' does not exist")
                    return False
        except ValueError:
            print("Message passed to sns.publish was not valid JSON")
            return False
        return True


class TestChaosLambda(PatchingTestCase):

    patch_list = (
        "chaos.boto3",
        "chaos.get_targets",
        "chaos.log",
        "chaos.terminate_targets",
    )

    def setUp(self):
        super(TestChaosLambda, self).setUp()
        self.clients = {}
        self.boto3.client.side_effect = self.make_client

    def make_client(self, name, region_name):
        c = self.clients.get(name, None)
        if c is not None:
            self.assertEqual(c.region_name, region_name)
        else:
            c = self.clients[name] = mock.Mock(region_name=region_name)
        return c

    def test_parseable_log_line_for_trigger(self):
        self.get_targets.return_value = []
        chaos.chaos_lambda(["sp-moonbase-1"], 0)
        self.log.assert_called_once_with("triggered", "sp-moonbase-1")

    def test_does_nothing_if_no_targets(self):
        self.get_targets.return_value = []
        chaos.chaos_lambda(["sp-moonbase-1"], 0)
        self.assertEqual(self.terminate_targets.call_count, 0)

    def test_uses_autoscaling_service_in_correct_region(self):
        self.get_targets.return_value = []
        chaos.chaos_lambda(["sp-moonbase-1"], 0)
        autoscaling = self.get_targets.call_args[0][0]
        self.assertEqual(autoscaling, self.clients["autoscaling"])
        self.assertEqual(autoscaling.region_name, "sp-moonbase-1")

    def test_passes_default_probability_to_get_targets(self):
        default = mock.sentinel.default
        self.get_targets.return_value = []
        chaos.chaos_lambda(["sp-moonbase-1"], default)
        self.assertEqual(self.get_targets.call_args[0][1], default)

    def test_terminates_target_instances_in_correct_region(self):
        targets = [("a", "i-11111111"), ("b", "i-22222222")]
        self.get_targets.return_value = targets
        ec2 = self.make_client("ec2", region_name="sp-moonbase-1")
        sns = self.make_client("sns", region_name="sp-moonbase-1")
        chaos.chaos_lambda(["sp-moonbase-1"], 0)
        # Above triggers self.make_client, which checks the region name
        self.terminate_targets.assert_called_once_with(ec2, sns, targets)


class TestGetRegions(PatchingTestCase):

    patch_list = (
        "chaos.os",
    )

    def test_looks_for_a_regions_environment_variable(self):
        self.os.environ.get.return_value = ""
        context = mock.Mock()
        context.invoked_function_arn = "arn:aws:lambda:re-gion-1:..."
        chaos.get_regions(context)
        self.os.environ.get.assert_called_once_with("regions", "")

    def test_extracts_region_from_context_if_no_regions_variable(self):
        self.os.environ.get.return_value = ""
        context = mock.Mock()
        for region in ("eu-west-1", "sp-moonbase-1"):
            context.invoked_function_arn = "arn:aws:lambda:" + region + ":..."
            result = chaos.get_regions(context)
            self.assertEqual(result, [region])

    def test_reads_from_comma_separated_regions_variable_if_set(self):
        self.os.environ.get.return_value = "re-gion-1,sp-moonbase-1"
        result = chaos.get_regions(mock.Mock())
        self.assertEqual(result, ["re-gion-1", "sp-moonbase-1"])

    def test_ignores_whitespace_in_regions_variable(self):
        self.os.environ.get.return_value = "\n sp-moonbase-1\n, re-gion-1 "
        result = chaos.get_regions(mock.Mock())
        self.assertEqual(result, ["sp-moonbase-1", "re-gion-1"])


class TestGetDefaultProbability(PatchingTestCase):

    patch_list = (
        "chaos.os",
    )

    def test_looks_for_a_probability_environment_variable(self):
        self.os.environ.get.return_value = ""
        chaos.get_default_probability()
        self.os.environ.get.assert_called_once_with("probability", "")

    def test_returns_default_if_no_probability_variable(self):
        self.os.environ.get.return_value = ""
        p = chaos.get_default_probability()
        self.assertEqual(p, chaos.DEFAULT_PROBABILITY)

    def test_returns_float_value_of_probability_variable(self):
        for s in ("0.1", "0.2", "0.3"):
            self.os.environ.get.return_value = s
            p = chaos.get_default_probability()
            self.assertEqual(p, float(s))

    def test_ignores_whitespace_in_probability_variable(self):
        self.os.environ.get.return_value = " \n0.1 "
        p = chaos.get_default_probability()
        self.assertEqual(p, 0.1)


class TestHandler(PatchingTestCase):

    patch_list = (
        "chaos.chaos_lambda",
        "chaos.get_default_probability",
        "chaos.get_regions",
    )

    def test_passes_along_the_region_list(self):
        context = mock.sentinel.context
        chaos.handler(None, context)
        self.get_regions.assert_called_once_with(context)
        self.chaos_lambda.assert_called_once_with(
            self.get_regions.return_value,
            mock.ANY
        )

    def test_passes_along_the_default_probability(self):
        chaos.handler(None, mock.Mock())
        self.get_default_probability.assert_called_once_with()
        self.chaos_lambda.assert_called_once_with(
            mock.ANY,
            self.get_default_probability.return_value
        )
