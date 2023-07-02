"""Test ansible versions for slowness."""
from __future__ import annotations

import logging
import pathlib
import re
import subprocess
import sys
from collections import OrderedDict

ANSIBLE_VERSIONS_2_12 = [
    "2.12.0",
    "2.12.1",
    "2.12.2",
    "2.12.3",
    "2.12.4",
    "2.12.5",
    "2.12.6",
    "2.12.7",
    "2.12.8",
    "2.12.9",
    "2.12.10",
]
ANSIBLE_VERSIONS_2_13 = [
    "2.13.0",
    "2.13.1",
    "2.13.2",
    "2.13.3",
    "2.13.4",
    "2.13.5",
    "2.13.6",
    "2.13.7",
    "2.13.8",
    "2.13.9",
    "2.13.10",
]
ANSIBLE_VERSIONS_2_14 = [
    "2.14.0",
    "2.14.1",
    "2.14.2",
    "2.14.3",
    "2.14.4",
    "2.14.5",
    "2.14.6",
    "2.14.7",
]
ANSIBLE_VERSIONS_2_15 = [
    "2.15.0",
    "2.15.1",
]

VERSIONS = {
    "3.8": ANSIBLE_VERSIONS_2_12 + ANSIBLE_VERSIONS_2_13,
    "3.9": ANSIBLE_VERSIONS_2_12 + ANSIBLE_VERSIONS_2_13 +
    ANSIBLE_VERSIONS_2_14 + ANSIBLE_VERSIONS_2_15,
    "3.10": ANSIBLE_VERSIONS_2_12 + ANSIBLE_VERSIONS_2_13 +
    ANSIBLE_VERSIONS_2_14 + ANSIBLE_VERSIONS_2_15,
    "3.11": ANSIBLE_VERSIONS_2_12 + ANSIBLE_VERSIONS_2_13 +
    ANSIBLE_VERSIONS_2_14 + ANSIBLE_VERSIONS_2_15,
}

logging.basicConfig(
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%a %d %b %H:%M:%S",
    level=logging.INFO,
)


def _get_timing(value: str):
    ansible_pattern = re.compile(r"^(?P<n>.+?) *-+(?P<d>.+)$")

    result = []
    for line in reversed(value.splitlines()):
        if line.startswith("======="):
            break
        ansible_match = ansible_pattern.match(line)
        if ansible_match:
            result.append(ansible_match.groupdict())
            continue

    return result


def _run(cmds: list[str], cwd: pathlib.Path, env=None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            env=env,
            args=cmds,
            cwd=cwd,
            check=True,
            shell=False,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        logging.error(e.stdout)
        logging.error(e.stderr)
        raise


def _venv_name(python_version: str, ansible_core_version: str) -> str:
    return f"venv-p{python_version}-ansible{ansible_core_version}"


def _create_venv(
        venv_base: pathlib.Path, python_version: str, ansible_core_version: str
):
    venv_name = _venv_name(python_version, ansible_core_version)
    venv_python = venv_base / venv_name / "bin" / "python"

    if not venv_python.exists():
        logging.info("Creating Python %s venv", python_version)
        cmds = ["sudo", f"python{python_version}", "-m", "venv", venv_name]
        _run(cmds, venv_base)

        logging.info("Installing ansible %s", ansible_core_version)
        cmds = [
            venv_python,
            "-m",
            "pip",
            "install",
            "-U",
            "pip",
            "setuptools",
            "wheel",
        ]
        _run(cmds, venv_base)

        cmds = [
            venv_python,
            "-m",
            "pip",
            "install",
            "-U",
            f"ansible-core=={ansible_core_version}",
        ]
        _run(cmds, venv_base)

    return venv_name, venv_python


def _run_test(
        playbook_dir: pathlib.Path, ansible_playbook_path: pathlib.Path,
        python_version: str, ansible_core_version: str
):
    cmds = [
        "sudo",
        ansible_playbook_path,
        "playbook.yaml",
    ]

    output = _run(cmds, playbook_dir)
    timing_data = _get_timing(output.stdout)

    result = {"py": python_version, "ans": ansible_core_version}
    for i in timing_data:
        result[i['n'].strip()] = i['d'].strip()

    return OrderedDict(sorted(result.items()))


def main(args=None) -> None:
    """Run the tests."""
    if not args:
        args = sys.argv[1:]

    venv_dir = pathlib.Path(args[0])
    playbook_dir = pathlib.Path(args[1])
    collections_dir = pathlib.Path(args[2])

    # install python versions
    for python_version, ansible_core_versions in VERSIONS.items():
        logging.info("Using Python %s", python_version)

        # create venvs and install ansible for each python and ansible version
        for ansible_core_version in ansible_core_versions:
            _create_venv(venv_dir, python_version, ansible_core_version)

            if not collections_dir.exists():
                venv_name = _venv_name(python_version, ansible_core_version)
                ansible_galaxy_path = venv_dir / venv_name / "bin" / "ansible-galaxy"
                cmds = [
                    ansible_galaxy_path,
                    "collection",
                    "install",
                    "ansible.posix",
                ]
                _run(cmds, playbook_dir, {'ANSIBLE_ROLES_PATH': str(collections_dir)})

            venv_name = _venv_name(python_version, ansible_core_version)
            venv_ansible_playbook = venv_dir / venv_name / "bin" / "ansible-playbook"

            timing_data = _run_test(
                playbook_dir, venv_ansible_playbook,
                python_version, ansible_core_version
            )
            logging.info(timing_data)


if __name__ == "__main__":
    main()
