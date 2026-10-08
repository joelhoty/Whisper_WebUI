"""Colab bootstrap regressions; run without downloading models or ML packages."""

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("colab_runtime", ROOT / "notebook" / "colab_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
NOTEBOOK = json.loads((ROOT / "notebook" / "whisper-webui.ipynb").read_text(encoding="utf-8"))


def cell_source(title):
    return next("".join(cell["source"]) for cell in NOTEBOOK["cells"]
                if cell["cell_type"] == "code" and title in cell["source"][0])


def installation_source(project, repository="", branch=""):
    source = cell_source("#Installation").replace("'/content/Whisper-WebUI'", repr(str(project)))
    for key, value in (("REPOSITORY_URL", repository), ("REPOSITORY_REF", branch)):
        source = re.sub(r"(?m)^" + key + r" = .*?(?= #@param)", key + " = " + repr(value), source)
    return source


class ColabNotebookTests(unittest.TestCase):
    def test_all_code_cells_compile(self):
        for cell in NOTEBOOK["cells"]:
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), cell["metadata"]["id"], "exec")

    def test_clone_uses_user_repository_and_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "checkout"
            source = installation_source(project, "https://github.com/example/fixed.git", "main")

            def clone(*args, **kwargs):
                if args[0][0:2] == ["git", "clone"]:
                    (project / "notebook").mkdir(parents=True)
                    (project / "notebook" / "colab_runtime.py").touch()

            with patch("subprocess.check_call", side_effect=clone) as call:
                exec(source, {})
            self.assertEqual(call.call_args_list[0].args[0], [
                "git", "clone", "--branch", "main", "--",
                "https://github.com/example/fixed.git", str(project),
            ])
            self.assertEqual(call.call_args_list[-1].args[0][-1], "install")

    def test_missing_repository_fails_before_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = installation_source(Path(directory) / "missing")
            with patch("subprocess.check_call") as call:
                with self.assertRaisesRegex(ValueError, "REPOSITORY_URL"):
                    exec(source, {})
            call.assert_not_called()

    def test_uploaded_checkout_is_reused_without_git(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "notebook").mkdir()
            (project / "notebook" / "colab_runtime.py").touch()
            source = installation_source(project)
            with patch("subprocess.check_call") as call:
                exec(source, {})
                exec(source, {})
            self.assertEqual(call.call_count, 2)
            self.assertTrue(all(item.args[0][-1] == "install" for item in call.call_args_list))

    def test_existing_checkout_from_another_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".git").mkdir()
            source = installation_source(directory, "https://github.com/example/fixed.git")
            with patch("subprocess.check_output", return_value="https://github.com/jhj0517/Whisper-WebUI.git\n"), \
                    patch("subprocess.check_call") as call:
                with self.assertRaisesRegex(ValueError, "Existing checkout"):
                    exec(source, {})
            call.assert_not_called()

    def test_credentials_are_passed_as_literal_arguments(self):
        source = cell_source("Configure arguments")
        password = "spaces ' quotes $() ; &"
        source = source.replace("PASSWORD = ''", "PASSWORD = " + repr(password))
        source = source.replace("WHISPER_TYPE = 'faster-whisper'", "WHISPER_TYPE = 'insanely-fast-whisper'")
        scope = {}
        exec(source, scope)
        self.assertEqual(scope["arguments"], [
            "--password", password, "--whisper_type", "insanely-fast-whisper",
        ])


class ColabRuntimeTests(unittest.TestCase):
    def test_cuda_libraries_precede_system_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            lib = Path(directory) / "venv/lib/python3.12/site-packages/nvidia/cudnn/lib"
            lib.mkdir(parents=True)
            with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/system/cuda/lib"}):
                env = runtime.runtime_environment(directory)
            self.assertEqual(env["LD_LIBRARY_PATH"].split(os.pathsep), [str(lib), "/system/cuda/lib"])
            self.assertEqual(env["PYTHONNOUSERSITE"], "1")

    def test_launch_uses_venv_and_absolute_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            python = runtime.environment_python(directory)
            python.parent.mkdir(parents=True)
            python.touch()
            with patch("subprocess.check_call") as call:
                runtime.launch(["--password", "a b;&"], directory)
            command = call.call_args.args[0]
            self.assertEqual(command[0], str(python))
            self.assertIn("--allowed_paths", command)
            self.assertEqual(command[-2:], ["--password", "a b;&"])
            self.assertEqual(call.call_args.kwargs["cwd"], Path(directory))

    def test_launch_without_installation_reports_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Installation"):
                runtime.launch([], directory)

    def test_failed_dependency_check_prevents_success(self):
        with tempfile.TemporaryDirectory() as directory:
            python = runtime.environment_python(directory)
            python.parent.mkdir(parents=True)
            python.touch()

            def check(command, **kwargs):
                if command[-2:] == ["pip", "check"]:
                    raise subprocess.CalledProcessError(1, command)

            with patch("subprocess.check_output", return_value="3.12\n"), \
                    patch("subprocess.check_call", side_effect=check) as call:
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.install(directory)
            self.assertTrue(any("--build-constraint" in item.args[0] for item in call.call_args_list))
            self.assertFalse(any("app.py" in item.args[0] for item in call.call_args_list))


if __name__ == "__main__":
    unittest.main()
