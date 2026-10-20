"""Install and launch Colab in an isolated environment, outside the notebook kernel."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]


def environment_python(project_dir=PROJECT_DIR):
    return Path(project_dir) / "venv" / "bin" / "python"


def runtime_environment(project_dir=PROJECT_DIR):
    env = os.environ.copy()
    # CTranslate2 and torch must load the same wheel-provided CUDA libraries.
    # Colab's system CUDA libraries may belong to a different cuDNN release (#540).
    libraries = sorted((Path(project_dir) / "venv" / "lib").glob(
        "python*/site-packages/nvidia/*/lib"
    ))
    library_paths = [str(path) for path in libraries]
    if env.get("LD_LIBRARY_PATH"):
        library_paths.append(env["LD_LIBRARY_PATH"])
    if library_paths:
        env["LD_LIBRARY_PATH"] = os.pathsep.join(library_paths)
    env["PYTHONNOUSERSITE"] = "1"
    # The Colab kernel exports its inline backend, which the venv does not have.
    env["MPLBACKEND"] = "Agg"
    env["USE_TF"] = "0"
    env["USE_FLAX"] = "0"
    return env


def install(project_dir=PROJECT_DIR):
    project_dir = Path(project_dir)
    python = environment_python(project_dir)
    if not python.exists():
        if (3, 10) <= sys.version_info[:2] <= (3, 12):
            subprocess.check_call([sys.executable, "-m", "venv", str(project_dir / "venv")])
        else:
            # Keep working when Colab upgrades its kernel beyond the supported range.
            subprocess.check_call([sys.executable, "-m", "pip", "install", "uv"])
            subprocess.check_call([
                sys.executable, "-m", "uv", "venv", "--python", "3.12", "--seed",
                str(project_dir / "venv"),
            ])

    version = subprocess.check_output([
        str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
    ], text=True).strip()
    if version not in {"3.10", "3.11", "3.12"}:
        raise RuntimeError(f"The existing venv uses unsupported Python {version}. Use a fresh runtime.")

    env = runtime_environment(project_dir)
    subprocess.check_call([
        str(python), "-m", "pip", "install", "--upgrade", "pip>=25.3", "setuptools<82",
    ], cwd=project_dir, env=env)
    subprocess.check_call([
        str(python), "-m", "pip", "install",
        "--build-constraint", str(project_dir / "notebook" / "constraints-build.txt"),
        "-r", str(project_dir / "notebook" / "requirements-colab.txt"),
    ], cwd=project_dir, env=env)
    subprocess.check_call([str(python), "-m", "pip", "check"], cwd=project_dir, env=env)
    # Catch import failures (including i18n and AudioMetaData) before reporting success.
    subprocess.check_call([str(python), "app.py", "--help"], cwd=project_dir,
                          env=runtime_environment(project_dir))
    print("Installation and startup import checks completed. Run the next cells.")


def launch(arguments, project_dir=PROJECT_DIR):
    project_dir = Path(project_dir)
    python = environment_python(project_dir)
    if not python.exists():
        raise RuntimeError("Run the Installation cell before starting the app.")
    subprocess.check_call([
        str(python), "app.py", "--share", "--colab", "--inbrowser", "False",
        "--allowed_paths", repr([str(project_dir / "outputs")]), *arguments,
    ], cwd=project_dir, env=runtime_environment(project_dir))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "run"])
    args, app_arguments = parser.parse_known_args()
    if args.action == "install":
        if app_arguments:
            parser.error("Unexpected installation arguments")
        install()
    else:
        launch(app_arguments)
