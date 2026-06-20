#!/usr/bin/env python3
"""Test runner for foundry-tools-skills.

Discovers and runs all tests under tests/. Uses only the standard library.

Usage:
    python3 run_tests.py              # run all tests
    python3 run_tests.py -v           # verbose
    python3 run_tests.py tests/test_openai_chat.py  # specific file
"""

# Requires: Python >= 3.8, standard library only

import sys
import unittest


def main():
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Run specific test file(s)
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for path in sys.argv[1:]:
            if path.startswith("-"):
                continue
            suite.addTests(loader.discover(".", pattern=path.split("/")[-1]))
        runner = unittest.TextTestRunner(verbosity=2)
    else:
        loader = unittest.TestLoader()
        suite = loader.discover("tests", pattern="test_*.py")
        verbosity = 2 if "-v" in sys.argv else 1
        runner = unittest.TextTestRunner(verbosity=verbosity)

    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
