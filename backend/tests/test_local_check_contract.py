from pathlib import Path


def test_local_check_propagates_external_command_failures() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "local_check.ps1"
    ).read_text(encoding="utf-8")

    assert 'if ($LASTEXITCODE -ne 0)' in script
    assert 'throw "$Name failed with exit code $LASTEXITCODE"' in script
