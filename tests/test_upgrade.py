import shutil
import subprocess

import pytest

from scripts import upgrade

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

FILES_SPEC = """    ModuleSpec(
        name="files",
        path="app.modules.files",
    ),
"""
REGISTRY = (
    "MODULES = [\n"
    + FILES_SPEC
    + """    ModuleSpec(
        name="tasks",
        path="app.modules.tasks",
    ),
]
"""
)

PYPROJECT = """[project]
name = "osnova"
version = "{version}"

[tool.ruff]
line-length = 100
"""

MAIN = """def first():
    return 1


def second():
    return 2
"""


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{who}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", "test@example.com")


def run(cwd, *args):
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout


def write(root, files):
    for path, text in files.items():
        target = root / path
        if text is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


def release(template, version, files):
    write(template, {**files, ".osnova-version": f"{version}\n"})
    run(template, "add", "-A")
    run(template, "commit", "-q", "-m", f"release {version}")
    run(template, "tag", version)


@pytest.fixture
def template(tmp_path):
    root = tmp_path / "template"
    root.mkdir()
    run(root, "init", "-q", "-b", "main")
    release(
        root,
        "v1.0.0",
        {
            "app/core/modules.py": REGISTRY,
            "app/main.py": MAIN,
            "app/modules/files/routes.py": "ROUTES = 1\n",
            "tests/test_files.py": 'pytestmark = pytest.mark.modules("files")\n',
            "pyproject.toml": PYPROJECT.format(version="1.0.0"),
            "README.md": "# Osnova\n",
            "CHANGELOG.md": "## 1.0.0\n",
        },
    )
    return root


@pytest.fixture
def project(tmp_path, template):
    """Made with "Use this template": the files of v1.0.0, a history of its own."""
    root = tmp_path / "project"
    root.mkdir()
    archive = subprocess.run(
        ["git", "archive", "v1.0.0"], cwd=template, check=True, capture_output=True
    ).stdout
    subprocess.run(["tar", "-x"], cwd=root, input=archive, check=True)
    run(root, "init", "-q", "-b", "main")
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", "Initial commit")
    return root


def strip_files(project):
    shutil.rmtree(project / "app/modules/files")
    write(
        project,
        {
            "tests/test_files.py": None,
            "app/core/modules.py": REGISTRY.replace(FILES_SPEC, ""),
        },
    )


def commit(root, message="project change"):
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", message)


def test_the_template_and_the_project_changes_are_merged(template, project):
    release(
        template,
        "v1.1.0",
        {
            "app/main.py": MAIN.replace("return 2", "return 22"),
            "app/modules/files/routes.py": "ROUTES = 2\n",
            "app/modules/files/storage.py": "STORAGE = 1\n",
            "tests/test_files_more.py": 'pytestmark = pytest.mark.modules("files", "tasks")\n',
            "app/core/new.py": "NEW = 1\n",
            "pyproject.toml": PYPROJECT.format(version="1.1.0").replace("100", "120"),
            "README.md": "# Osnova 1.1\n",
            "CHANGELOG.md": "## 1.1.0\n## 1.0.0\n",
        },
    )
    strip_files(project)
    write(
        project,
        {
            "app/main.py": MAIN.replace("return 1", "return 11"),
            "pyproject.toml": PYPROJECT.format(version="2.3.0"),
            "README.md": "# My shop\n",
            "CHANGELOG.md": "## 2.3.0\n",
        },
    )
    commit(project)

    start, left = upgrade.upgrade(project, "v1.1.0", str(template))

    assert left == []
    assert start != run(project, "rev-parse", "HEAD").strip()
    assert run(project, "status", "--porcelain") == ""
    assert "return 11" in (project / "app/main.py").read_text()
    assert "return 22" in (project / "app/main.py").read_text()
    assert (project / "app/core/new.py").exists()
    assert not (project / "app/modules/files").exists()
    assert not (project / "tests/test_files_more.py").exists()
    assert (project / "pyproject.toml").read_text() == PYPROJECT.format(version="2.3.0").replace(
        "100", "120"
    )
    assert (project / "README.md").read_text() == "# My shop\n"
    assert (project / "CHANGELOG.md").read_text() == "## 2.3.0\n"
    assert (project / ".osnova-version").read_text() == "v1.1.0\n"


def test_the_next_upgrade_needs_no_new_base(template, project):
    release(template, "v1.1.0", {"app/core/new.py": "NEW = 1\n"})
    upgrade.upgrade(project, "v1.1.0", str(template))
    release(template, "v1.2.0", {"app/core/new.py": "NEW = 2\n"})

    upgrade.upgrade(project, "v1.2.0", str(template))

    assert (project / "app/core/new.py").read_text() == "NEW = 2\n"
    log = run(project, "log", "--format=%s")
    assert log.count("as the base for upgrades") == 1
    assert "chore: upgrade Osnova to v1.2.0" in log


def test_a_line_changed_on_both_sides_is_left_to_resolve(template, project):
    release(template, "v1.1.0", {"app/main.py": MAIN.replace("return 2", "return 22")})
    write(project, {"app/main.py": MAIN.replace("return 2", "return 33")})
    commit(project)

    start, left = upgrade.upgrade(project, "v1.1.0", str(template))

    assert left == ["app/main.py"]
    assert "<<<<<<<" in (project / "app/main.py").read_text()
    run(project, "merge", "--abort")
    run(project, "reset", "-q", "--hard", start)
    assert "return 33" in (project / "app/main.py").read_text()


def test_changes_must_be_committed_first(template, project):
    release(template, "v1.1.0", {"app/core/new.py": "NEW = 1\n"})
    write(project, {"app/main.py": "changed = True\n"})

    with pytest.raises(upgrade.UpgradeError, match="commit them first"):
        upgrade.upgrade(project, "v1.1.0", str(template))


def test_the_same_version_is_refused(template, project):
    with pytest.raises(upgrade.UpgradeError, match="on v1.0.0 already"):
        upgrade.upgrade(project, "v1.0.0", str(template))


def test_only_version_lines_keep_ours():
    text = 'a\n<<<<<<< HEAD\nversion = "2.0"\n=======\nversion = "1.1"\n>>>>>>> v\nb\n'
    assert upgrade.keep_our_versions(text) == 'a\nversion = "2.0"\nb\n'
    other = "<<<<<<< HEAD\nx = 1\n=======\nx = 2\n>>>>>>> v\n"
    assert upgrade.keep_our_versions(other) == other
