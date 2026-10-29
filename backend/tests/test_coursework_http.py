import pytest

from z5596858_tests import *  # noqa: F403

pytestmark = pytest.mark.usefixtures("isolated_http_server")
