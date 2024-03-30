import subprocess


def check():
    for folder in ("main",):
        print("\n\nRUNNING FOR FOLDER: {}\n".format(folder))
        print("\n==> Running: isort")
        subprocess.run("isort --check {}".format(folder).split())
        print("\n==> Running: black")
        subprocess.run("black --check {}".format(folder).split())
        # Check errors in the code (and check that black respects pep8).
        # We could only use pyflakes if flake8 has too much false positive style errors.
        # Also check Cyclomatic Complexity and fail if > "moderate - slightly complex block".
        print("\n==> Running: flake8")
        subprocess.run(
            "flake8 --append-config=flake8.ini -v --radon-show-closures --radon-no-assert --radon-max-cc 20 {}".format(
                folder
            ).split()
        )
        print("\n==> Running: pylint")
        subprocess.run("pylint {}".format(folder).split())
        print("\n==> Running: mypy")
        subprocess.run("mypy {}".format(folder).split())
        print("\n==> Running: vulture")
        subprocess.run("vulture {} --min-confidence 70".format(folder).split())


def format():
    for folder in ("main",):
        print("\n\nRUNNING FOR FOLDER: {}\n".format(folder))
        # sort imports
        print("\n==> Running: isort")
        subprocess.run("isort {}".format(folder).split())
        # black doesn't read exclude directive in fake8 configuration
        print("\n==> Running: black")
        subprocess.run("black {}".format(folder).split())
        # rerun isort after black modifications
        print("\n==> Running: isort")
        subprocess.run("isort {}".format(folder).split())
