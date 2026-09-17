"""Regression tests for the portable Antislop plugin archive."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import zipfile


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SCRIPT = os.path.join(ROOT, "scripts", "build-plugin-archive.sh")


class TestPortablePluginArchive(unittest.TestCase):
    def test_builder_emits_one_plugin_with_exact_skill_roster(self):
        with tempfile.TemporaryDirectory() as output_dir:
            completed = subprocess.run(
                ["bash", BUILD_SCRIPT, output_dir],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr or completed.stdout,
            )

            archive = os.path.join(output_dir, "antislop-plugin-3.0.0.zip")
            checksum = archive + ".sha256"
            self.assertTrue(os.path.isfile(archive))
            self.assertTrue(os.path.isfile(checksum))

            with zipfile.ZipFile(archive) as package:
                names = package.namelist()
                manifest = json.loads(package.read("antislop/plugin.json"))
                codex_manifest = json.loads(
                    package.read("antislop/.codex-plugin/plugin.json")
                )
                claude_manifest = json.loads(
                    package.read("antislop/.claude-plugin/plugin.json")
                )

            skills = sorted(
                name.split("/")[2]
                for name in names
                if name.startswith("antislop/skills/") and name.endswith("/SKILL.md")
            )
            self.assertEqual(skills, ["antislop", "generate-slop"])
            self.assertEqual(manifest["name"], "antislop")
            self.assertEqual(manifest["version"], "3.0.0")
            for required in (
                "antislop/.claude-plugin/plugin.json",
                "antislop/.claude-plugin/marketplace.json",
                "antislop/.codex-plugin/plugin.json",
            ):
                self.assertIn(required, names)
            self.assertEqual(codex_manifest["skills"], "./skills/")
            self.assertNotIn("mcpServers", codex_manifest)
            self.assertEqual(codex_manifest["description"], manifest["description"])
            self.assertEqual(claude_manifest["description"], manifest["description"])

            source_references = sorted(
                name
                for name in os.listdir(
                    os.path.join(ROOT, "skills", "antislop", "references")
                )
                if name.endswith(".md")
            )
            archived_references = sorted(
                os.path.basename(name)
                for name in names
                if name.startswith("antislop/skills/antislop/references/")
                and name.endswith(".md")
            )
            self.assertEqual(archived_references, source_references)

            with open(checksum, encoding="utf-8") as checksum_file:
                recorded_digest, recorded_name = checksum_file.read().split()
            with open(archive, "rb") as archive_file:
                actual_digest = hashlib.sha256(archive_file.read()).hexdigest()
            self.assertEqual(recorded_digest, actual_digest)
            self.assertEqual(recorded_name, os.path.basename(archive))

    def test_ci_and_release_workflows_publish_the_plugin_archive(self):
        paths = (
            ".forgejo/workflows/lint-skills.yml",
            ".github/workflows/lint-skills.yml",
        )
        for path in paths:
            with self.subTest(path=path):
                with open(os.path.join(ROOT, path), encoding="utf-8") as workflow_file:
                    workflow = workflow_file.read()
                self.assertIn("bash scripts/build-plugin-archive.sh dist", workflow)
                self.assertIn("dist/antislop-plugin-*.zip", workflow)
                self.assertIn("dist/antislop-plugin-*.zip.sha256", workflow)

        release_paths = (
            ".forgejo/workflows/release-skills.yml",
            ".github/workflows/release-skills.yml",
        )
        for path in release_paths:
            with self.subTest(path=path):
                with open(os.path.join(ROOT, path), encoding="utf-8") as workflow_file:
                    workflow = workflow_file.read()
                self.assertIn("bash scripts/build-plugin-archive.sh .", workflow)

        with open(
            os.path.join(ROOT, ".forgejo/workflows/release-skills.yml"),
            encoding="utf-8",
        ) as workflow_file:
            forgejo_release = workflow_file.read()
        self.assertIn("antislop-plugin-${VERSION}.zip", forgejo_release)


if __name__ == "__main__":
    unittest.main()
