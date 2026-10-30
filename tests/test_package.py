import shopper


def test_package_reports_its_version() -> None:
    assert shopper.__version__ == "0.1.0"
