import mock

from base import mock_imports, PatchingTestCase

mock_imports([
    "boto3"
])  # noqa

import lmonkey


class TestGetASGInstanceId(PatchingTestCase):

    patch_list = (
        "random.choice",
        "random.random",
    )

    def test_returns_None_if_there_are_no_instances(self):
        self.random.return_value = 1.0
        asg = {"Instances": []}
        self.assertEqual(lmonkey.get_asg_instance_id(asg), None)
        asg = {}
        self.assertEqual(lmonkey.get_asg_instance_id(asg), None)

    def test_returns_None_if_probability_test_fails(self):
        self.choice.side_effect = lambda l: l[0]
        self.random.return_value = 1.0
        asg = {"Instances": [{"InstanceId": "i-1234abcd"}]}
        self.assertEqual(lmonkey.get_asg_instance_id(asg), None)

    def test_returns_instance_id_if_probability_test_succeeds(self):
        self.choice.side_effect = lambda l: l[0]
        self.random.return_value = 0.0
        asg = {"Instances": [{"InstanceId": "i-1234abcd"}]}
        self.assertEqual(lmonkey.get_asg_instance_id(asg), "i-1234abcd")


class TestGetTargets(PatchingTestCase):

    patch_list = (
        "lmonkey.get_asg_instance_id",
    )

    def setUp(self):
        super(TestGetTargets, self).setUp()
        self.autoscaling = mock.Mock()
        self.describe = self.autoscaling.describe_auto_scaling_groups

    def test_returns_empty_list_if_no_auto_scaling_groups(self):
        self.describe.return_value = {"AutoScalingGroups": []}
        self.assertEqual(lmonkey.get_targets(self.autoscaling), [])
        self.describe.return_value = {}
        self.assertEqual(lmonkey.get_targets(self.autoscaling), [])

    def test_gets_instance_from_each_asg(self):
        self.get_asg_instance_id.side_effect = lambda asg: asg["Instances"][0]
        self.describe.return_value = {
            "AutoScalingGroups": [
                {"AutoScalingGroupName": "a", "Instances": ["i-11111111"]},
                {"AutoScalingGroupName": "b", "Instances": ["i-22222222"]},
                {"AutoScalingGroupName": "c", "Instances": ["i-33333333"]}
            ]
        }
        targets = lmonkey.get_targets(self.autoscaling)
        self.assertEqual(set(targets), set([
            ("a", "i-11111111"),
            ("b", "i-22222222"),
            ("c", "i-33333333")
        ]))

    def test_ignores_asgs_with_no_instances(self):
        self.get_asg_instance_id.side_effect = lambda asg: \
            asg["Instances"][0] if len(asg["Instances"]) != 0 else None
        self.describe.return_value = {
            "AutoScalingGroups": [
                {"AutoScalingGroupName": "a", "Instances": []},
                {"AutoScalingGroupName": "b", "Instances": ["i-22222222"]},
                {"AutoScalingGroupName": "c", "Instances": []}
            ]
        }
        targets = lmonkey.get_targets(self.autoscaling)
        self.assertEqual(targets, [("b", "i-22222222")])


class TestLambdaMonkey(PatchingTestCase):

    patch_list = (
        "lmonkey.boto3",
        "lmonkey.get_targets",
        "lmonkey.log",
    )

    def setUp(self):
        super(TestLambdaMonkey, self).setUp()
        self.clients = {}
        self.boto3.client.side_effect = self.make_client

    def make_client(self, name, region_name):
        c = self.clients.get(name, None)
        if c is not None:
            self.assertEqual(c.region_name, region_name)
        else:
            c = self.clients[name] = mock.Mock(region_name=region_name)
        return c

    def get_log_lines(self, name):
        lines = []
        for args, kwargs in self.log.call_args_list:
            parts = " ".join(args).split(" ")
            if parts[0] == name:
                lines.append(parts)
        return lines

    def test_does_nothing_if_no_targets(self):
        self.get_targets.return_value = []
        lmonkey.lambda_monkey("sp-moonbase-1")
        ec2 = self.clients.get("ec2", mock.Mock())
        self.assertEqual(ec2.terminate_instances.call_count, 0)

    def test_uses_autoscaling_service_in_correct_region(self):
        self.get_targets.return_value = []
        lmonkey.lambda_monkey("sp-moonbase-1")
        autoscaling = self.get_targets.call_args[0][0]
        self.assertEqual(autoscaling, self.clients["autoscaling"])
        self.assertEqual(autoscaling.region_name, "sp-moonbase-1")

    def test_terminates_target_instances(self):
        self.get_targets.return_value = [
            ("a", "i-11111111"),
            ("b", "i-22222222")
        ]
        ec2 = self.make_client("ec2", region_name="sp-moonbase-1")
        ec2.terminate_instances.return_value = {}
        lmonkey.lambda_monkey("sp-moonbase-1")
        ec2.terminate_instances.assert_called_once_with(
            InstanceIds=["i-11111111", "i-22222222"]
        )

    def test_uses_ec2_service_in_correct_region(self):
        self.get_targets.return_value = [("a", "i-11111111")]
        ec2 = self.make_client("ec2", region_name="sp-moonbase-1")
        ec2.terminate_instances.return_value = {}
        lmonkey.lambda_monkey("sp-moonbase-1")
        # Above triggers self.make_client, which checks the region name
        self.assertNotEqual(ec2.terminate_instances.call_count, 0)

    def test_parseable_log_line_for_each_targeted_instance(self):
        self.get_targets.return_value = [
            ("asg-name-one", "i-00000000"),
            ("second-asg", "i-11111111"),
            ("the-third-asg", "i-22222222")
        ]
        ec2 = self.make_client("ec2", region_name="sp-moonbase-1")
        ec2.terminate_instances.return_value = {}
        lmonkey.lambda_monkey("sp-moonbase-1")
        logged = self.get_log_lines("targeting")
        self.assertEqual(set((part[1], part[3]) for part in logged), set([
            ("i-00000000", "asg-name-one"),
            ("i-11111111", "second-asg"),
            ("i-22222222", "the-third-asg")
        ]))

    def test_parseable_log_line_for_each_termination_result(self):
        self.get_targets.return_value = [("a", "i-11111111")]
        ec2 = self.make_client("ec2", region_name="sp-moonbase-1")
        # We're cheating here and returning results that are unrelated to the
        # list in get_targets, to save duplication
        ec2.terminate_instances.return_value = {
            "TerminatingInstances": [
                {"InstanceId": "i-00000000", "CurrentState": {"Name": "s1"}},
                {"InstanceId": "i-11111111", "CurrentState": {"Name": "s2"}},
                {"InstanceId": "i-22222222", "CurrentState": {"Name": "s3"}}
            ]
        }
        lmonkey.lambda_monkey("sp-moonbase-1")
        logged = self.get_log_lines("result")
        self.assertEqual(set((part[1], part[3]) for part in logged), set([
            ("i-00000000", "s1"),
            ("i-11111111", "s2"),
            ("i-22222222", "s3")
        ]))


class TestHandler(PatchingTestCase):

    patch_list = (
        "lmonkey.lambda_monkey",
        "lmonkey.log",
    )

    def test_extracts_region_from_function_arn(self):
        context = mock.Mock()
        for region in ("eu-west-1", "sp-moonbase-1"):
            context.invoked_function_arn = "arn:aws:lambda:" + region + ":..."
            self.lambda_monkey.reset_mock()
            lmonkey.handler(None, context)
            self.lambda_monkey.assert_called_once_with(region)

    def test_parseable_log_line_for_trigger(self):
        context = mock.Mock()
        context.invoked_function_arn = "arn:aws:lambda:sp-moonbase-1:..."
        lmonkey.handler(None, context)
        self.log.assert_called_once_with("triggered", "sp-moonbase-1")
