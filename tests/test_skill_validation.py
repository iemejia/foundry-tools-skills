#!/usr/bin/env python3
"""Validate all skills: syntax check scripts, verify --help, validate SKILL.md.

This test module discovers all skills under skills/ and performs static
validation that requires no API credentials.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")


def _find_skills():
    """Yield (skill_name, skill_dir) for each skill directory."""
    skills_root = os.path.abspath(SKILLS_DIR)
    if not os.path.isdir(skills_root):
        return
    for name in sorted(os.listdir(skills_root)):
        skill_dir = os.path.join(skills_root, name)
        if os.path.isdir(skill_dir) and not name.startswith("."):
            yield name, skill_dir


def _find_scripts(skill_dir):
    """Yield script paths under a skill's scripts/ directory."""
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return
    for fname in sorted(os.listdir(scripts_dir)):
        if fname.endswith(".py") and not fname.startswith("_"):
            yield os.path.join(scripts_dir, fname)


class TestSkillStructure(unittest.TestCase):
    """Validate that each skill has the required structure."""

    def test_all_skills_have_skill_md(self):
        for name, skill_dir in _find_skills():
            skill_md = os.path.join(skill_dir, "SKILL.md")
            self.assertTrue(
                os.path.isfile(skill_md),
                "Skill '{0}' is missing SKILL.md".format(name),
            )

    def test_all_skills_have_scripts_dir(self):
        for name, skill_dir in _find_skills():
            scripts_dir = os.path.join(skill_dir, "scripts")
            self.assertTrue(
                os.path.isdir(scripts_dir),
                "Skill '{0}' is missing scripts/ directory".format(name),
            )

    def test_all_skills_have_at_least_one_script(self):
        for name, skill_dir in _find_skills():
            scripts = list(_find_scripts(skill_dir))
            self.assertGreater(
                len(scripts), 0,
                "Skill '{0}' has no .py scripts under scripts/".format(name),
            )


class TestSkillMdFrontmatter(unittest.TestCase):
    """Validate SKILL.md YAML frontmatter."""

    def test_frontmatter_has_required_fields(self):
        for name, skill_dir in _find_skills():
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue
            with open(skill_md, "r") as f:
                content = f.read()

            # Check frontmatter delimiters
            self.assertTrue(
                content.startswith("---"),
                "SKILL.md in '{0}' must start with '---' frontmatter".format(name),
            )
            end = content.find("---", 3)
            self.assertGreater(
                end, 3,
                "SKILL.md in '{0}' is missing closing '---'".format(name),
            )

            frontmatter = content[3:end]
            # Check required keys exist (simple string check, no yaml dep)
            self.assertIn(
                "name:", frontmatter,
                "SKILL.md in '{0}' is missing 'name:' in frontmatter".format(name),
            )
            self.assertIn(
                "description:", frontmatter,
                "SKILL.md in '{0}' is missing 'description:'".format(name),
            )


class TestScriptCompilation(unittest.TestCase):
    """Verify all scripts compile without errors."""

    def test_all_scripts_compile(self):
        for name, skill_dir in _find_skills():
            for script_path in _find_scripts(skill_dir):
                with self.subTest(script=script_path):
                    result = subprocess.run(
                        [sys.executable, "-m", "py_compile", script_path],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(
                        result.returncode, 0,
                        "Compilation failed for {0}:\n{1}".format(
                            script_path, result.stderr
                        ),
                    )


class TestScriptHelp(unittest.TestCase):
    """Verify all scripts exit 0 on --help."""

    def test_all_scripts_help_exits_zero(self):
        for name, skill_dir in _find_skills():
            for script_path in _find_scripts(skill_dir):
                with self.subTest(script=script_path):
                    result = subprocess.run(
                        [sys.executable, script_path, "--help"],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(
                        result.returncode, 0,
                        "--help failed for {0}:\n{1}".format(
                            script_path, result.stderr
                        ),
                    )
                    self.assertIn(
                        "usage:", result.stdout.lower(),
                        "--help output for {0} missing usage info".format(
                            script_path
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
