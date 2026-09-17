#!/usr/bin/env python3
# Fail-closed policy for agent-authored Forgejo file mutations.
#
# The policy is repository-local defense in depth. It does not replace
# Forgejo branch protection or a server-side MCP policy.

import re


DEFAULT_PROTECTED_BRANCHES = frozenset({"main"})
MUTATING_OPERATIONS = frozenset({"create_file", "update_file", "delete_file"})
NON_MUTATING_OPERATIONS = frozenset({"get_file_content", "create_pull_request"})
_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


class MutationPolicyError(ValueError):
    pass


def validate_branch_target(branch_name, *, default_branch="main",
                           protected_branches=DEFAULT_PROTECTED_BRANCHES):
    if not isinstance(branch_name, str) or not branch_name:
        raise MutationPolicyError("mutation requires an explicit branch name")
    if branch_name != branch_name.strip():
        raise MutationPolicyError("branch name must not contain surrounding whitespace")
    if branch_name.startswith("refs/") or branch_name.startswith("tags/"):
        raise MutationPolicyError("refs and tags are not branch mutation targets")
    if _COMMIT_SHA_RE.fullmatch(branch_name):
        raise MutationPolicyError("commit SHAs are not branch mutation targets")
    if not _BRANCH_NAME_RE.fullmatch(branch_name):
        raise MutationPolicyError("branch name contains unsupported characters")

    protected = set(DEFAULT_PROTECTED_BRANCHES)
    protected.update(protected_branches or ())
    if default_branch:
        protected.add(default_branch)
    if branch_name in protected:
        raise MutationPolicyError(
            "direct mutation of protected branch '%s' is forbidden" % branch_name
        )
    return branch_name


def verify_branch_head(expected_head, observed_head):
    if not isinstance(expected_head, str) or not expected_head:
        raise MutationPolicyError("mutation requires a recorded expected branch head")
    if not isinstance(observed_head, str) or observed_head != expected_head:
        raise MutationPolicyError("branch head changed before the mutation batch")
    return {"expected_head": expected_head, "observed_head": observed_head}


def authorize_operation(operation, branch_name=None, *, default_branch="main",
                        protected_branches=DEFAULT_PROTECTED_BRANCHES,
                        branch_created=False, expected_head=None,
                        observed_head=None):
    # Only explicitly classified non-mutating operations are returned unchanged.
    if operation in NON_MUTATING_OPERATIONS:
        return {"operation": operation, "mutation": False, "authorized": True}
    if operation not in MUTATING_OPERATIONS:
        raise MutationPolicyError(
            "operation is outside the explicitly classified Forgejo policy"
        )

    branch = validate_branch_target(
        branch_name,
        default_branch=default_branch,
        protected_branches=protected_branches,
    )
    if not branch_created:
        raise MutationPolicyError("create and verify the task branch before file mutation")
    head = verify_branch_head(expected_head, observed_head)
    return {
        "operation": operation,
        "mutation": True,
        "authorized": True,
        "branch": branch,
        **head,
    }

