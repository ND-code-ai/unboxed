import pytest

from shopper.config import Tier


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--supervisor-tier",
        default="small",
        choices=("small", "medium"),
        help="the tier the supervisor evaluation runs on; the supervisor's own is small",
    )


@pytest.fixture
def supervisor_tier(request: pytest.FixtureRequest) -> Tier:
    return request.config.getoption("--supervisor-tier")
