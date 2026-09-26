import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "scripts"


def test_cleanup_uses_oauth_for_runtime_sessions() -> None:
    gate2 = (SCRIPTS / "Remove-Gate2.ps1").read_text(encoding="utf-8")
    gate1_aws = (SCRIPTS / "Remove-Gate1Aws.ps1").read_text(encoding="utf-8")

    assert "stop-runtime-session" not in gate2
    assert "stop-runtime-session" not in gate1_aws
    assert "Stop-RuntimeSessions.ps1" in gate2
    assert "Stop-RuntimeSessions.ps1" in gate1_aws


def load_stop_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "stop_runtime_sessions",
        SCRIPTS / "stop_runtime_sessions.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_oauth_session_stop_uses_bearer_header() -> None:
    module = load_stop_module()

    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"{}"

    def open_request(request: object, timeout: int) -> Response:
        assert timeout == 30
        assert request.get_header("Authorization") == " ".join(
            ("Bearer", "test-token")
        )
        return Response()

    with patch.object(module.urllib.request, "urlopen", open_request):
        result = module.stop_session(
            "arn:aws:bedrock-agentcore:example",
            "example-region",
            "example-session",
            "test-token",
            60,
        )

    assert result == "stopped"
