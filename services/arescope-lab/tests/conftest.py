from pathlib import Path


def pytest_configure(config):
    # Keep fixture storage in this service even when pytest is launched from the
    # repository root. pytest may recursively clear its own basetemp directory.
    root = Path(__file__).resolve().parents[1]
    target = (root / ".tmp/pytest").resolve()
    if not target.is_relative_to(root):
        raise RuntimeError("Test storage must remain inside the service directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(target)
