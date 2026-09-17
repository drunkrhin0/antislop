#!/usr/bin/env python3
"""Tests for CI workflow credential and dependency-pin hardening.

Covers Forgejo issue #78. The checker reads the shipped workflow YAML files
under .forgejo/workflows and .github/workflows, parses them with a small
dependency-free loader, and proves the hardening properties:

- Credentials are never placed on a command line or in a Git remote URL.
- Temporary credential material (the GIT_ASKPASS helper) is removed after use.
- workflow_dispatch tag input is passed through env and validated as data.
- GitHub action references are full reviewed commit SHAs.
- Forgejo action references match the recorded platform policy.
- Python dependencies resolve to the recorded pinned version.

Recorded platform policy (issue #78): the Forgejo Actions runner cannot
execute SHA-pinned actions, so Forgejo workflows use tag references such as
actions/checkout@v4. GitHub workflows have no such limitation and must pin
every action to a full reviewed commit SHA. The recorded reviewed SHAs and
the recorded pyyaml version live in the constants below, so a bump updates
both the workflow and the check in one place.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FORGEJO_WORKFLOW_DIR = os.path.join(ROOT, ".forgejo", "workflows")
GITHUB_WORKFLOW_DIR = os.path.join(ROOT, ".github", "workflows")

# Recorded policy and dependency pins (issue #78).
GITHUB_ACTION_SHA_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
FORGEJO_ACTION_TAG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@v[0-9]+(\.[0-9]+)*$")
PYYAML_VERSION = "6.0.3"

REVIEWED_ACTION_SHAS = {
    "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",
    "softprops/action-gh-release": "3bb12739c298aeb8a4eeaf626c5b8d85266b0e65",
}

SENTINEL_TOKEN = "SENTINEL-CI-HARDENING-TOKEN"


# ---------------------------------------------------------------------------
# Minimal YAML loader for the workflow file subset.
# ---------------------------------------------------------------------------

def _scalar(s):
    s = s.strip()
    m = re.match(r"^(.*?)\s+#", s)
    if m and not (s.startswith('"') or s.startswith("'")):
        s = m.group(1).strip()
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1]
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1]
    if s in ("true", "True", "yes", "Yes"):
        return True
    if s in ("false", "False", "no", "No"):
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _block_scalar(lines, start, key_indent):
    vals = []
    i = start
    if i < len(lines) and lines[i][0] > key_indent:
        block_indent = lines[i][0]
        while i < len(lines) and lines[i][0] > key_indent:
            vals.append(lines[i][1][block_indent:])
            i += 1
    return "\n".join(vals), i


def _parse_mapping(lines, i, indent):
    result = {}
    while i < len(lines):
        ind, raw = lines[i]
        if ind < indent:
            break
        if ind > indent:
            i += 1
            continue
        line = raw.strip()
        if not line:
            i += 1
            continue
        if line.startswith("#") or line.startswith("- "):
            break
        key, sep, rest = line.partition(":")
        if not sep:
            i += 1
            continue
        key = key.strip().strip('"\'')
        rest = rest.strip()
        if rest == "|":
            val, ni = _block_scalar(lines, i + 1, ind)
            result[key] = val
            i = ni
        elif rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > ind:
                child, ni = _parse_block(lines, i + 1, lines[i + 1][0])
                result[key] = child
                i = ni
            else:
                result[key] = {}
                i += 1
        elif rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            result[key] = [_scalar(x) for x in inner.split(",") if x.strip()] if inner else []
            i += 1
        else:
            result[key] = _scalar(rest)
            i += 1
    return result, i


def _parse_sequence(lines, i, indent):
    result = []
    while i < len(lines):
        ind, raw = lines[i]
        if ind < indent:
            break
        if ind > indent:
            i += 1
            continue
        line = raw.strip()
        if not line:
            i += 1
            continue
        if not line.startswith("- "):
            break
        rest = line[2:].strip()
        if not rest:
            if i + 1 < len(lines) and lines[i + 1][0] > ind:
                child, ni = _parse_block(lines, i + 1, lines[i + 1][0])
                result.append(child)
                i = ni
            else:
                result.append(None)
                i += 1
            continue
        key, sep, val = rest.partition(":")
        if not sep:
            result.append(_scalar(rest))
            i += 1
            continue
        key = key.strip().strip('"\'')
        val = val.strip()
        item = {}
        if val == "|":
            item[key], i = _block_scalar(lines, i + 1, ind)
            result.append(item)
            continue
        if val == "":
            item[key] = {}
            i += 1
        else:
            item[key] = _scalar(val)
            i += 1
        if i < len(lines) and lines[i][0] > ind:
            child, ni = _parse_mapping(lines, i, lines[i][0])
            for k, v in child.items():
                item[k] = v
            i = ni
        result.append(item)
    return result, i


def _parse_block(lines, i, indent):
    if i >= len(lines):
        return {}, i
    if lines[i][1].lstrip().startswith("- "):
        return _parse_sequence(lines, i, indent)
    return _parse_mapping(lines, i, indent)


def load_workflow(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw))
    if not lines:
        return {}
    node, _ = _parse_block(lines, 0, lines[0][0])
    return node


def read_workflow(path):
    with open(path, encoding="utf-8") as f:
        return load_workflow(f.read())


def workflow_steps(workflow):
    jobs = workflow.get("jobs", {})
    for job in jobs.values():
        for step in job.get("steps", []):
            yield step


def step_by_name(workflow, name):
    for step in workflow_steps(workflow):
        if step.get("name") == name:
            return step
    raise AssertionError("step not found: %s" % name)


def run_blocks(workflow):
    for step in workflow_steps(workflow):
        if step.get("run"):
            yield step.get("name"), step["run"]


def uses_refs(workflow):
    refs = []
    for step in workflow_steps(workflow):
        if step.get("uses"):
            refs.append(step["uses"])
    return refs


# ---------------------------------------------------------------------------
# Shell snippet execution helpers.
# ---------------------------------------------------------------------------

def substitute_actions(script, **context):
    """Replace ${{ github.X }} template expressions with test values."""
    for key, value in context.items():
        script = script.replace("${{ github.%s }}" % key, value)
    script = re.sub(r"\$\{\{ github\.(\w+) \}\}", r"test-\1", script)
    return script


def write_fake_git(bin_dir):
    """Write a fake git that records argv and askpass state to a log file."""
    path = os.path.join(bin_dir, "git")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "#!/bin/bash\n"
            "echo \"GIT-ARGV: $*\" >> \"$GIT_LOG\"\n"
            "if [ -n \"${GIT_ASKPASS:-}\" ]; then\n"
            "  echo \"GIT-ASKPASS-PATH: $GIT_ASKPASS\" >> \"$GIT_LOG\"\n"
            "  if [ -f \"$GIT_ASKPASS\" ]; then\n"
            "    echo \"GIT-ASKPASS-PRESENT: yes\" >> \"$GIT_LOG\"\n"
            "  fi\n"
            "fi\n"
            "case \"$1\" in\n"
            "  init) mkdir -p .git ;;\n"
            "  remote)\n"
            "    if [ \"$2\" = \"add\" ]; then\n"
            "      mkdir -p .git\n"
            "      printf '[remote \"origin\"]\\n\\turl = %s\\n' \"$4\" >> .git/config\n"
            "    fi\n"
            "    ;;\n"
            "  fetch) : > FETCH_HEAD ;;\n"
            "  checkout) : ;;\n"
            "  config) : ;;\n"
            "  tag) : ;;\n"
            "  rev-parse) exit 1 ;;\n"
            "esac\n"
            "exit 0\n"
        )
    os.chmod(path, 0o700)
    return path


def write_fake_curl(bin_dir):
    """Write a fake curl that records argv and -K config fd content."""
    path = os.path.join(bin_dir, "curl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "#!/bin/bash\n"
            "{\n"
            "  echo \"CURL-ARGV: $*\"\n"
            "  prev=\"\"\n"
            "  for a in \"$@\"; do\n"
            "    if [ \"$prev\" = \"-K\" ]; then\n"
            "      echo \"CURL-CONFIG-FD: $a\"\n"
            "      cat \"$a\"\n"
            "    fi\n"
            "    prev=\"$a\"\n"
            "  done\n"
            "} >> \"$CURL_LOG\"\n"
            "if [[ \" $* \" == *\" -o /dev/null \"* ]]; then\n"
            "  [ -z \"${CURL_UPLOAD_FAILURE:-}\" ] || exit 22\n"
            "elif [[ \" $* \" == *\" -X POST \"* ]]; then\n"
            "  echo '{\"id\": 4243}'\n"
            "  [[ \" $* \" != *\" -w \"* ]] || echo 201\n"
            "else\n"
            "  echo '{\"id\": 4242}'\n"
            "  [[ \" $* \" != *\" -w \"* ]] || echo 200\n"
            "fi\n"
        )
    os.chmod(path, 0o700)
    return path


def run_snippet(script, cwd, env, log_path):
    """Run a bash snippet, capturing output and logs. Returns (rc, out)."""
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    log_text = ""
    if log_path and os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            log_text = f.read()
    return result.returncode, result.stdout + result.stderr, log_text


def read_env_file(path):
    """Parse a GITHUB_ENV-style KEY=VALUE file into a dict."""
    env = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# Checker helpers used by the shipped-file and fixture tests.
# ---------------------------------------------------------------------------

def floating_uses_violations(workflow, uses_checker):
    return [u for u in uses_refs(workflow) if not uses_checker(u)]


def assert_github_uses_policy(testcase, workflow, path):
    violations = floating_uses_violations(workflow, lambda u: bool(GITHUB_ACTION_SHA_RE.match(u)))
    testcase.assertEqual(
        violations, [],
        "%s: floating (non-SHA) action references: %s" % (path, violations),
    )


def assert_forgejo_uses_policy(testcase, workflow, path):
    violations = floating_uses_violations(workflow, lambda u: bool(FORGEJO_ACTION_TAG_RE.match(u)))
    testcase.assertEqual(
        violations, [],
        "%s: action references outside the recorded Forgejo tag policy: %s" % (path, violations),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestShippedWorkflowsParse(unittest.TestCase):
    """Every shipped workflow parses and yields the expected step structure."""

    def test_all_shipped_workflows_parse(self):
        for directory in (FORGEJO_WORKFLOW_DIR, GITHUB_WORKFLOW_DIR):
            for name in sorted(os.listdir(directory)):
                if not name.endswith(".yml"):
                    continue
                path = os.path.join(directory, name)
                workflow = read_workflow(path)
                self.assertTrue(workflow.get("jobs"), "no jobs in %s" % path)
                steps = list(workflow_steps(workflow))
                self.assertTrue(steps, "no steps in %s" % path)
                for step in steps:
                    self.assertTrue(
                        step.get("uses") or step.get("run"),
                        "step has neither uses nor run in %s" % path,
                    )

    def test_forgejo_workflows_never_send_credentials_to_plain_http(self):
        lint_path = os.path.join(FORGEJO_WORKFLOW_DIR, "lint-skills.yml")
        with open(lint_path, encoding="utf-8") as handle:
            lint = handle.read()
        self.assertIn("http://192.168.1.62:3000", lint)
        for credential_marker in (
                "GITHUB_TOKEN", "GIT_ASKPASS", "x-access-token",
                "Authorization:"):
            self.assertNotIn(credential_marker, lint)

        release_path = os.path.join(FORGEJO_WORKFLOW_DIR,
                                    "release-skills.yml")
        with open(release_path, encoding="utf-8") as handle:
            release = handle.read()
        self.assertIn("http://192.168.1.62:3000", release)
        self.assertIn("FORGEJO_URL", release)


class TestForgejoLintCheckoutCredentials(unittest.TestCase):
    """The public Forgejo lint checkout is anonymous on the internal route."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="antislop-wf-lint-")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.git_log = os.path.join(self.tmp, "git.log")
        write_fake_git(self.bin)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _lint_checkout_script(self):
        path = os.path.join(FORGEJO_WORKFLOW_DIR, "lint-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Checkout")
        return substitute_actions(step["run"], sha="deadbeefcafe1234fedcba9876543210abcdef01")

    def test_no_token_in_remote_url_or_git_config(self):
        work = os.path.join(self.tmp, "work")
        os.makedirs(work)
        env = dict(os.environ)
        env.update({
            "PATH": self.bin + os.pathsep + env["PATH"],
            "GIT_LOG": self.git_log,
            "GITHUB_TOKEN": SENTINEL_TOKEN,
            "EVENT_SHA": "deadbeefcafe1234fedcba9876543210abcdef01",
        })
        rc, out, log = run_snippet(self._lint_checkout_script(), work, env, self.git_log)
        self.assertEqual(rc, 0, "checkout snippet failed: %s" % out)
        self.assertNotIn(SENTINEL_TOKEN, log, "token appeared on a git command line")
        config_path = os.path.join(work, ".git", "config")
        with open(config_path, encoding="utf-8") as f:
            config = f.read()
        self.assertNotIn(SENTINEL_TOKEN, config, "token persisted in .git/config")
        self.assertIn(
            "http://192.168.1.62:3000/drunkrhin0/antislop.git",
            config)
        self.assertNotIn("x-access-token:", config, "credential embedded in remote URL")

    def test_checkout_never_uses_askpass(self):
        work = os.path.join(self.tmp, "work")
        os.makedirs(work)
        env = dict(os.environ)
        env.update({
            "PATH": self.bin + os.pathsep + env["PATH"],
            "GIT_LOG": self.git_log,
            "GITHUB_TOKEN": SENTINEL_TOKEN,
            "EVENT_SHA": "deadbeefcafe1234fedcba9876543210abcdef01",
        })
        rc, out, log = run_snippet(self._lint_checkout_script(), work, env, self.git_log)
        self.assertEqual(rc, 0, "checkout snippet failed: %s" % out)
        self.assertNotIn("GIT-ASKPASS-PATH:", log)
        self.assertNotIn(SENTINEL_TOKEN, log)


class TestForgejoReleaseCredentials(unittest.TestCase):
    """The Forgejo release workflow keeps tokens off the command line."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="antislop-wf-rel-")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.curl_log = os.path.join(self.tmp, "curl.log")
        self.git_log = os.path.join(self.tmp, "git.log")
        write_fake_curl(self.bin)
        write_fake_git(self.bin)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _release_workflow(self):
        return read_workflow(os.path.join(FORGEJO_WORKFLOW_DIR, "release-skills.yml"))

    def _release_step_script(self):
        workflow = self._release_workflow()
        step = step_by_name(workflow, "Create release and upload assets")
        return step["run"]

    def test_curl_header_uses_fd_config_not_command_argument(self):
        script = self._release_step_script()
        self.assertNotIn("Authorization: token ${RELEASE_TOKEN}", script)
        self.assertNotIn("-H \"${AUTH}\"", script)
        self.assertNotIn("AUTH=", script)
        self.assertIn(
            "-K <(printf 'header = \"Authorization: token %s\"\\n' \"$RELEASE_TOKEN\")",
            script,
            "release curl must read the Authorization header from a -K file descriptor",
        )
        self.assertEqual(script.count("-K <(printf 'header"), 3, "all three curl calls must use -K")

    def test_release_curl_argv_has_no_token(self):
        work = os.path.join(self.tmp, "work")
        os.makedirs(work)
        for name in (
            "antislop-2.0.3.zip",
            "antislop-plugin-2.0.3.zip",
            "antislop-kiro-2.0.3.zip",
        ):
            with open(os.path.join(work, name), "w", encoding="utf-8") as f:
                f.write("zip")
        env = dict(os.environ)
        env.update({
            "PATH": self.bin + os.pathsep + env["PATH"],
            "CURL_LOG": self.curl_log,
            "GITHUB_REPOSITORY": "drunkrhin0/antislop",
            "TAG": "antislop-v2.0.3",
            "VERSION": "2.0.3",
            "RELEASE_TOKEN": SENTINEL_TOKEN,
            "FORGEJO_URL": "https://forgejo.internal.example",
        })
        rc, out, log = run_snippet(self._release_step_script(), work, env, self.curl_log)
        self.assertEqual(rc, 0, "release snippet failed: %s" % out)
        for line in log.splitlines():
            if line.startswith("CURL-ARGV:"):
                self.assertNotIn(SENTINEL_TOKEN, line, "token appeared on a curl command line")
        config_lines = [line for line in log.splitlines() if line.startswith("CURL-CONFIG-FD:")]
        self.assertTrue(config_lines, "curl never read a -K config file descriptor")
        header_lines = [
            line for line in log.splitlines()
            if line.startswith("header = ")
        ]
        self.assertTrue(
            all(SENTINEL_TOKEN in line for line in header_lines),
            "the -K config fd must still carry the Authorization header",
        )
        self.assertGreaterEqual(len(header_lines), 4, "release lookup and uploads must use -K")
        self.assertIn("Release antislop v2.0.3 complete", out)
        self.assertIn("Found existing release", out, "release lookup should reuse an existing release")

    def test_askpass_removed_after_release_git_steps(self):
        workflow = self._release_workflow()
        prepare = substitute_actions(step_by_name(workflow, "Prepare git credentials")["run"])
        checkout = substitute_actions(step_by_name(workflow, "Checkout")["run"], ref="refs/tags/antislop-v2.0.3")
        remove = step_by_name(workflow, "Remove git credentials")["run"]

        work = os.path.join(self.tmp, "work2")
        os.makedirs(work)
        env_file = os.path.join(self.tmp, "env.out")
        base_env = dict(os.environ)
        base_env.update({
            "PATH": self.bin + os.pathsep + base_env["PATH"],
            "GIT_LOG": self.git_log,
            "GITHUB_ENV": env_file,
            "GITHUB_TOKEN": SENTINEL_TOKEN,
            "EVENT_REF": "refs/tags/antislop-v2.0.3",
            "FORGEJO_URL": "https://forgejo.internal.example",
        })

        rc, out, _ = run_snippet(prepare, work, base_env, None)
        self.assertEqual(rc, 0, "prepare step failed: %s" % out)

        env = dict(base_env)
        env.update(read_env_file(env_file))
        self.assertTrue(env.get("ASKPASS_PATH"), "prepare step must export ASKPASS_PATH")
        askpass_path = env["ASKPASS_PATH"]
        self.assertTrue(os.path.exists(askpass_path), "askpass must exist after prepare")

        rc, out, log = run_snippet(checkout, work, env, self.git_log)
        self.assertEqual(rc, 0, "checkout step failed: %s" % out)
        self.assertNotIn(SENTINEL_TOKEN, log, "token appeared on a git command line")
        config_path = os.path.join(work, ".git", "config")
        with open(config_path, encoding="utf-8") as f:
            config = f.read()
        self.assertNotIn(SENTINEL_TOKEN, config, "token persisted in .git/config")

        rc, out, _ = run_snippet(remove, work, env, None)
        self.assertEqual(rc, 0, "remove step failed: %s" % out)
        self.assertFalse(os.path.exists(askpass_path), "askpass must be removed by the cleanup step")

    def test_tag_push_steps_use_askpass(self):
        workflow = self._release_workflow()
        for name in ("Tag antislop",):
            step = step_by_name(workflow, name)
            script = step["run"]
            self.assertIn("GIT_ASKPASS=\"$ASKPASS_PATH\"", script)
            self.assertIn(
                'git push "${FORGEJO_URL%/}/drunkrhin0/antislop.git" "${TAG}"',
                script,
            )
            self.assertIn('https://*)', script)
            self.assertNotIn("GITHUB_TOKEN", script, "token must not appear on a command line")
            self.assertNotIn("x-access-token:", script)

    def test_release_candidate_gate_precedes_tagging_and_packaging(self):
        workflow = self._release_workflow()
        steps = list(workflow_steps(workflow))
        gate = step_by_name(workflow, "Verify release candidate")
        self.assertIsNotNone(gate)
        script = gate["run"]
        self.assertIn("git merge-base --is-ancestor", script)
        self.assertIn("python3 tools/generate.py --check", script)
        self.assertIn(
            "python3 tools/validate.py --skills-dir skills --expect-version-from rules.json",
            script)
        self.assertIn("bash check.sh", script)
        self.assertIn("python3 -m unittest discover -s tests -t . -v", script)
        self.assertLess(steps.index(gate),
                        steps.index(step_by_name(workflow, "Tag antislop")))
        self.assertLess(steps.index(gate),
                        steps.index(step_by_name(workflow, "Build release assets")))

    def test_release_tag_must_match_the_canonical_registry_version(self):
        workflow = self._release_workflow()
        script = step_by_name(workflow, "Verify release candidate")["run"]
        self.assertIn("rules.json", script)
        self.assertIn('EXPECTED_TAG="antislop-v${CANONICAL_VERSION}"', script)
        self.assertIn('"${GITHUB_REF_NAME}" != "${EXPECTED_TAG}"', script)

    def test_uploads_fail_for_missing_assets_and_http_errors(self):
        script = self._release_step_script()
        self.assertNotIn('[ -f "$ZIP" ] || continue', script)
        self.assertIn('Missing release asset: ${ZIP}', script)
        self.assertIn("--fail-with-body", script)

        base_env = dict(os.environ)
        base_env.update({
            "PATH": self.bin + os.pathsep + base_env["PATH"],
            "CURL_LOG": self.curl_log,
            "TAG": "antislop-v3.0.0",
            "VERSION": "3.0.0",
            "RELEASE_TOKEN": SENTINEL_TOKEN,
            "FORGEJO_URL": "https://forgejo.internal.example",
        })

        missing = os.path.join(self.tmp, "missing-assets")
        os.makedirs(missing)
        rc, out, _ = run_snippet(script, missing, base_env, self.curl_log)
        self.assertNotEqual(rc, 0)
        self.assertIn("Missing release asset", out)

        failing = os.path.join(self.tmp, "failed-upload")
        os.makedirs(failing)
        for name in (
                "antislop-3.0.0.zip",
                "antislop-plugin-3.0.0.zip",
                "antislop-kiro-3.0.0.zip"):
            with open(os.path.join(failing, name), "w", encoding="utf-8") as handle:
                handle.write("zip")
        failure_env = dict(base_env)
        failure_env["CURL_UPLOAD_FAILURE"] = "1"
        rc, _out, _ = run_snippet(script, failing, failure_env, self.curl_log)
        self.assertNotEqual(rc, 0)

    def test_release_checkout_remote_url_has_no_token(self):
        workflow = self._release_workflow()
        script = step_by_name(workflow, "Checkout")["run"]
        self.assertIn(
            'http://192.168.1.62:3000/drunkrhin0/antislop.git', script)
        self.assertNotIn("x-access-token:", script)
        self.assertNotIn("GITHUB_TOKEN", script, "token must not appear on a command line")
        self.assertNotIn("GIT_ASKPASS", script)

    def test_release_checkout_rejects_malicious_ref_before_git(self):
        workflow = self._release_workflow()
        script = step_by_name(workflow, "Checkout")["run"]
        sentinel = os.path.join(self.tmp, "checkout-sentinel")
        env = dict(os.environ)
        env.update({
            "PATH": self.bin + os.pathsep + env["PATH"],
            "GIT_LOG": self.git_log,
            "EVENT_REF": "refs/tags/antislop-v1.2.3$(touch %s)" % sentinel,
            "FORGEJO_URL": "https://forgejo.internal.example",
            "ASKPASS_PATH": os.path.join(self.tmp, "unused-askpass"),
            "GITHUB_TOKEN": SENTINEL_TOKEN,
        })
        work = os.path.join(self.tmp, "malicious-ref")
        os.makedirs(work)
        rc, _out, log = run_snippet(script, work, env, self.git_log)
        self.assertNotEqual(rc, 0)
        self.assertFalse(os.path.exists(sentinel))
        self.assertEqual(log, "")

    def test_authenticated_steps_reject_plain_http_origin(self):
        workflow = self._release_workflow()
        scripts = [
            step_by_name(workflow, "Create release and upload assets")["run"],
        ]
        for index, script in enumerate(scripts):
            with self.subTest(index=index):
                work = os.path.join(self.tmp, "http-%d" % index)
                os.makedirs(work)
                env = dict(os.environ)
                env.update({
                    "PATH": self.bin + os.pathsep + env["PATH"],
                    "GIT_LOG": self.git_log,
                    "CURL_LOG": self.curl_log,
                    "EVENT_REF": "refs/tags/antislop-v3.0.0",
                    "FORGEJO_URL": "http://192.168.1.62:3000",
                    "ASKPASS_PATH": os.path.join(self.tmp, "unused-askpass"),
                    "RELEASE_TOKEN": SENTINEL_TOKEN,
                    "TAG": "antislop-v3.0.0",
                    "VERSION": "3.0.0",
                })
                rc, _out, _log = run_snippet(script, work, env, None)
                self.assertNotEqual(rc, 0)


class TestPyyamlPinned(unittest.TestCase):
    """pyyaml resolves to the recorded version in every Forgejo install step."""

    def test_install_step_pins_recorded_version(self):
        path = os.path.join(FORGEJO_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Install PyYAML")
        env = step.get("env", {})
        self.assertEqual(env.get("PYYAML_VERSION"), PYYAML_VERSION)
        self.assertIn("pyyaml==${PYYAML_VERSION}", step["run"])
        self.assertNotIn("pip install --quiet pyyaml\n", step["run"])
        self.assertNotIn("pip install pyyaml", step["run"].replace("pyyaml==${PYYAML_VERSION}", ""))

    def test_no_unpinned_pip_installs_in_forgejo_workflows(self):
        for name in sorted(os.listdir(FORGEJO_WORKFLOW_DIR)):
            if not name.endswith(".yml"):
                continue
            path = os.path.join(FORGEJO_WORKFLOW_DIR, name)
            workflow = read_workflow(path)
            for _step_name, script in run_blocks(workflow):
                for line in script.splitlines():
                    stripped = line.strip()
                    if "pip install" in stripped and not stripped.startswith("#"):
                        self.assertIn("==", stripped, "%s: unpinned pip install: %s" % (path, stripped))


class TestGitHubReleaseTagInput(unittest.TestCase):
    """workflow_dispatch tag input is env data and cannot run shell code."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="antislop-wf-gh-")
        self.env_file = os.path.join(self.tmp, "env.out")
        self.sentinel = os.path.join(self.tmp, "sentinel")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _resolve_tag_script(self):
        path = os.path.join(GITHUB_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Resolve tag")
        return step, substitute_actions(step["run"], event_name="workflow_dispatch")

    def test_input_passed_through_env(self):
        step, _script = self._resolve_tag_script()
        self.assertEqual(step["env"]["MANUAL_TAG"], "${{ inputs.tag }}")
        script = step["run"]
        self.assertNotIn("${{ github.event.inputs.tag }}", script)
        self.assertIn("${MANUAL_TAG}", script)

    def test_malicious_tags_cannot_execute_sentinel(self):
        _step, script = self._resolve_tag_script()
        payloads = [
            "antislop-v1.2.3; touch %s",
            "antislop-v1.2.3$(touch %s)",
            "antislop-v1.2.3`touch %s`",
            "antislop-v1.2.3\\ntouch %s",
            "antislop-v1.2.3\"; touch %s; echo \"",
            "antislop-v1.2.3' && touch %s",
        ]
        for template in payloads:
            with self.subTest(template=template):
                tag = template % self.sentinel
                env = dict(os.environ)
                env.update({
                    "MANUAL_TAG": tag,
                    "GITHUB_ENV": self.env_file,
                })
                rc, out, _ = run_snippet(script, self.tmp, env, None)
                self.assertNotEqual(rc, 0, "malicious tag must be rejected: %r" % tag)
                self.assertFalse(
                    os.path.exists(self.sentinel),
                    "malicious tag executed a command: %r" % tag,
                )
                if os.path.exists(self.env_file):
                    os.remove(self.env_file)

    def test_unsafe_interpolation_would_execute_sentinel(self):
        tag = "antislop-v1.2.3\"; touch %s; echo \"" % self.sentinel
        unsafe = 'echo "TAG=%s" >> "$GITHUB_ENV"' % tag
        env = dict(os.environ)
        env.update({"GITHUB_ENV": self.env_file})
        rc, _out, _ = run_snippet(unsafe, self.tmp, env, None)
        self.assertTrue(
            os.path.exists(self.sentinel),
            "control failed: naive interpolation should execute the sentinel",
        )
        self.assertEqual(rc, 0)

    def test_valid_tag_reaches_env(self):
        _step, script = self._resolve_tag_script()
        env = dict(os.environ)
        env.update({
            "MANUAL_TAG": "antislop-v2.0.3",
            "GITHUB_ENV": self.env_file,
        })
        rc, out, _ = run_snippet(script, self.tmp, env, None)
        self.assertEqual(rc, 0, "valid tag rejected: %s" % out)
        parsed = read_env_file(self.env_file)
        self.assertEqual(parsed.get("TAG"), "antislop-v2.0.3")

    def test_valid_tag_reaches_checkout_and_release_steps(self):
        path = os.path.join(GITHUB_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        checkout = None
        release = None
        for step in workflow_steps(workflow):
            if step.get("uses", "").startswith("actions/checkout@"):
                checkout = step
            if step.get("uses", "").startswith("softprops/action-gh-release@"):
                release = step
        self.assertIsNotNone(checkout)
        self.assertIsNotNone(release)
        self.assertEqual(checkout["with"]["ref"], "${{ env.TAG }}")
        self.assertEqual(release["with"]["tag_name"], "${{ env.TAG }}")
        self.assertEqual(release["with"]["files"], "*.zip")


class TestActionReferences(unittest.TestCase):
    """GitHub workflows pin to full reviewed SHAs; Forgejo matches its policy."""

    def test_github_actions_are_full_reviewed_shas(self):
        for name in sorted(os.listdir(GITHUB_WORKFLOW_DIR)):
            if not name.endswith(".yml"):
                continue
            path = os.path.join(GITHUB_WORKFLOW_DIR, name)
            workflow = read_workflow(path)
            for ref in uses_refs(workflow):
                self.assertTrue(
                    GITHUB_ACTION_SHA_RE.match(ref),
                    "%s: floating action reference %r" % (path, ref),
                )
                owner, sep, rest = ref.partition("/")
                self.assertTrue(sep, "%s: malformed ref %r" % (path, ref))
                action, _, sha = rest.rpartition("@")
                expected = REVIEWED_ACTION_SHAS.get("%s/%s" % (owner, action))
                if expected:
                    self.assertEqual(
                        sha, expected,
                        "%s: %s/%s must use the recorded reviewed SHA" % (path, owner, action),
                    )

    def test_forgejo_actions_match_recorded_tag_policy(self):
        for name in sorted(os.listdir(FORGEJO_WORKFLOW_DIR)):
            if not name.endswith(".yml"):
                continue
            path = os.path.join(FORGEJO_WORKFLOW_DIR, name)
            workflow = read_workflow(path)
            assert_forgejo_uses_policy(self, workflow, path)

    def test_github_policy_rejects_tag_and_branch_refs(self):
        refs = ["actions/checkout@v4", "actions/checkout@main", "softprops/action-gh-release@v2"]
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertFalse(GITHUB_ACTION_SHA_RE.match(ref), "floating ref %r must fail" % ref)

    def test_forgejo_policy_accepts_tag_and_rejects_branch_refs(self):
        for ref in ["actions/checkout@v4", "actions/checkout@v4.2.2"]:
            with self.subTest(ref=ref):
                self.assertTrue(FORGEJO_ACTION_TAG_RE.match(ref))
        for ref in ["actions/checkout@main", "actions/checkout@master", "actions/checkout"]:
            with self.subTest(ref=ref):
                self.assertFalse(FORGEJO_ACTION_TAG_RE.match(ref), "branch ref %r must fail" % ref)


class TestWorkflowFixturePolicy(unittest.TestCase):
    """The checker enforces policy on synthetic workflow fixtures."""

    FORGEJO_FIXTURE_GOOD = (
        "name: X\n"
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  j:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: run\n"
        "        run: echo ok\n"
    )
    FORGEJO_FIXTURE_BAD = FORGEJO_FIXTURE_GOOD.replace("actions/checkout@v4", "actions/checkout@main")
    GITHUB_FIXTURE_GOOD = FORGEJO_FIXTURE_GOOD.replace(
        "actions/checkout@v4",
        "actions/checkout@%s" % REVIEWED_ACTION_SHAS["actions/checkout"],
    )
    GITHUB_FIXTURE_BAD = FORGEJO_FIXTURE_GOOD

    def _assert_no_forgejo_violations(self, text):
        workflow = load_workflow(text)
        assert_forgejo_uses_policy(self, workflow, "fixture")

    def _assert_forgejo_violations(self, text):
        workflow = load_workflow(text)
        self.assertTrue(
            floating_uses_violations(workflow, lambda u: bool(FORGEJO_ACTION_TAG_RE.match(u))),
            "expected a Forgejo policy violation",
        )

    def test_forgejo_fixture_good(self):
        self._assert_no_forgejo_violations(self.FORGEJO_FIXTURE_GOOD)

    def test_forgejo_fixture_bad(self):
        self._assert_forgejo_violations(self.FORGEJO_FIXTURE_BAD)

    def test_github_fixture_good(self):
        workflow = load_workflow(self.GITHUB_FIXTURE_GOOD)
        assert_github_uses_policy(self, workflow, "fixture")

    def test_github_fixture_bad(self):
        workflow = load_workflow(self.GITHUB_FIXTURE_BAD)
        violations = floating_uses_violations(workflow, lambda u: bool(GITHUB_ACTION_SHA_RE.match(u)))
        self.assertTrue(violations, "expected a GitHub SHA-pin violation")


class TestPushedTagValidation(unittest.TestCase):
    """Pushed release tags are validated before shell interpolation.

    The workflow_dispatch input is env-validated, but the push-tag path reads
    GITHUB_REF_NAME directly. A pushed tag (e.g. antislop-v$(touch ...)) must
    be rejected before its version string reaches any shell command.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="antislop-wf-tag-")
        self.env_file = os.path.join(self.tmp, "env.out")
        self.sentinel = os.path.join(self.tmp, "sentinel")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _github_resolve_script(self):
        path = os.path.join(GITHUB_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Resolve tag")
        return substitute_actions(step["run"], event_name="push")

    def test_pushed_malicious_tags_cannot_execute_sentinel(self):
        script = self._github_resolve_script()
        payloads = [
            "antislop-v1.2.3; touch %s",
            "antislop-v1.2.3$(touch %s)",
            "antislop-v1.2.3`touch %s`",
            "antislop-v1.2.3\\ntouch %s",
        ]
        for template in payloads:
            with self.subTest(template=template):
                tag = template % self.sentinel
                env = dict(os.environ)
                env.update({
                    "GITHUB_REF_NAME": tag,
                    "GITHUB_ENV": self.env_file,
                })
                rc, out, _ = run_snippet(script, self.tmp, env, None)
                self.assertNotEqual(rc, 0, "malicious pushed tag must be rejected: %r" % tag)
                self.assertFalse(
                    os.path.exists(self.sentinel),
                    "malicious pushed tag executed a command: %r" % tag,
                )
                if os.path.exists(self.env_file):
                    os.remove(self.env_file)

    def test_valid_pushed_tag_reaches_env(self):
        script = self._github_resolve_script()
        env = dict(os.environ)
        env.update({
            "GITHUB_REF_NAME": "antislop-v2.0.3",
            "GITHUB_ENV": self.env_file,
        })
        rc, out, _ = run_snippet(script, self.tmp, env, None)
        self.assertEqual(rc, 0, "valid pushed tag rejected: %s" % out)
        parsed = read_env_file(self.env_file)
        self.assertEqual(parsed.get("TAG"), "antislop-v2.0.3")

    def test_forgejo_pushed_tag_is_validated(self):
        path = os.path.join(FORGEJO_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Resolve version from tag")
        script = step["run"]
        for template in (
            "antislop-v1.2.3; touch %s",
            "antislop-v1.2.3$(touch %s)",
            "antislop-v1.2.3\\ntouch %s",
        ):
            with self.subTest(template=template):
                tag = template % self.sentinel
                env = dict(os.environ)
                env.update({
                    "GITHUB_REF_NAME": tag,
                    "GITHUB_ENV": self.env_file,
                })
                rc, out, _ = run_snippet(script, self.tmp, env, None)
                self.assertNotEqual(rc, 0, "malicious Forgejo tag must be rejected: %r" % tag)
                self.assertFalse(
                    os.path.exists(self.sentinel),
                    "malicious Forgejo tag executed a command: %r" % tag,
                )
                if os.path.exists(self.env_file):
                    os.remove(self.env_file)

    def test_forgejo_checkout_treats_event_ref_as_env_data(self):
        path = os.path.join(FORGEJO_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Checkout")
        self.assertEqual(step["env"]["EVENT_REF"], "${{ github.ref }}")
        self.assertNotIn("${{ github.ref }}", step["run"])
        self.assertIn('git fetch origin "${EVENT_REF}"', step["run"])

    def test_generated_versions_are_validated_before_tag_creation(self):
        path = os.path.join(FORGEJO_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        for name in ("Tag antislop",):
            script = step_by_name(workflow, name)["run"]
            validation = script.index(
                '[[ ! "$VERSION" =~ ^[0-9]+\\.[0-9]+\\.[0-9]+$ ]]')
            tag_creation = script.index('TAG="')
            self.assertLess(validation, tag_creation)

    def test_forgejo_valid_pushed_tag_resolves_version(self):
        path = os.path.join(FORGEJO_WORKFLOW_DIR, "release-skills.yml")
        workflow = read_workflow(path)
        step = step_by_name(workflow, "Resolve version from tag")
        env = dict(os.environ)
        env.update({
            "GITHUB_REF_NAME": "antislop-v2.0.3",
            "GITHUB_ENV": self.env_file,
        })
        rc, out, _ = run_snippet(step["run"], self.tmp, env, None)
        self.assertEqual(rc, 0, "valid Forgejo tag rejected: %s" % out)
        parsed = read_env_file(self.env_file)
        self.assertEqual(parsed.get("TAG"), "antislop-v2.0.3")
        self.assertEqual(parsed.get("VERSION"), "2.0.3")


if __name__ == "__main__":
    unittest.main()
