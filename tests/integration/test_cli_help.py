from typer.testing import CliRunner

from crewai_multicli_factory.cli import app


def test_cli_help_lists_all_subcommands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "run-issue",
        "deliver-project",
        "classify-input",
        "create-prd",
        "plan-project",
        "plan-milestones",
        "plan-tasks",
        "execute-milestone",
        "continue-run",
        "replay",
        "scan",
        "verify",
        "release-check",
        "report",
        "export-delivery",
    ):
        assert cmd in result.stdout
