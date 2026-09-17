#!/usr/bin/env python3
# Behavioral tests for the repository-local Forgejo write guard.

import unittest

from forgejo_write_policy import MutationPolicyError, authorize_operation


class TestMutationBranchTargets(unittest.TestCase):
    def assert_rejected(self, branch, **kwargs):
        with self.assertRaises(MutationPolicyError):
            authorize_operation(
                "update_file", branch, branch_created=True,
                expected_head="abc123", observed_head="abc123", **kwargs
            )

    def test_protected_and_ambiguous_targets_fail_closed(self):
        for branch in (
            "main", "refs/heads/codex/task", "refs/tags/v3.0.0",
            "tags/v3.0.0", "abc1234", "", "codex/task with spaces",
        ):
            with self.subTest(branch=branch):
                self.assert_rejected(branch)

    def test_named_protected_branch_is_rejected(self):
        self.assert_rejected("release", protected_branches={"release"})

    def test_task_branch_is_accepted(self):
        result = authorize_operation(
            "update_file", "codex/143-branch-guard", branch_created=True,
            expected_head="abc123", observed_head="abc123"
        )
        self.assertTrue(result["authorized"])
        self.assertEqual(result["branch"], "codex/143-branch-guard")


class TestMutationSequencing(unittest.TestCase):
    def test_file_mutation_requires_branch_creation(self):
        with self.assertRaises(MutationPolicyError):
            authorize_operation(
                "create_file", "codex/task", branch_created=False,
                expected_head="abc123", observed_head="abc123"
            )

    def test_head_must_be_unchanged_before_mutation(self):
        with self.assertRaises(MutationPolicyError):
            authorize_operation(
                "delete_file", "codex/task", branch_created=True,
                expected_head="abc123", observed_head="def456"
            )

    def test_read_only_and_pr_operations_do_not_gain_write_authority(self):
        for operation in ("get_file_content", "create_pull_request"):
            with self.subTest(operation=operation):
                result = authorize_operation(operation)
                self.assertTrue(result["authorized"])
                self.assertFalse(result["mutation"])

    def test_unclassified_operations_fail_closed(self):
        for operation in ("merge_pull_request", "submit_pull_review", "unknown_operation"):
            with self.subTest(operation=operation):
                with self.assertRaises(MutationPolicyError):
                    authorize_operation(operation)


if __name__ == "__main__":
    unittest.main()
