#!/usr/bin/env python3
import argparse
import http.client
import importlib.util
import logging
import os.path
import re
import tarfile
from typing import List
from urllib.parse import urlparse
import uuid

ARCHIVE_URL = 'https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-{version}-linux-x86_64.tar.gz'
BUFFER_SIZE = 8192
COMPLETIONS_FILE = 'google-cloud-sdk/data/cli/gcloud_completions.py'
DEFAULT_OUTPUT_FILE = 'gcloud.fish'
DEFAULT_OUTPUT_PATH = os.path.expanduser('~/.local/share/chezmoi/dot_config/fish/completions')
VERSION_REGEX = re.compile(r'Installing the latest gcloud CLI version \(([0-9]+\.[0-9]+\.[0-9]+)\)')

BASE_COMPLETIONS = """function __gcloud_needs_command
    set -l tokens (commandline -opc)
    set -e tokens[1]
    contains $tokens {root_commands}
    and return 1
    return 0
end

function __gcloud_starts_with
    set -l subcommand $argv
    set -l current_cmd (commandline -opc)
    string match -r -- "^gcloud $subcommand\$" "$current_cmd"
end

complete -c gcloud -f -n __gcloud_needs_command -a '{root_commands}'
"""


def get_logger():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(message)s', '%F %T')
    ch.setFormatter(formatter)

    logger = logging.getLogger('fish-gcloud-completions')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    return logger


logger = get_logger()


def generate(root, cmds, preceeding, completions, root_flags):
    subcmds = cmds['commands']
    subcmd_list = ' '.join(subcmds.keys())

    flags = cmds['flags']

    starts_with = ' '.join(preceeding)

    if root and subcmd_list:
        completions.append(f"complete -c gcloud -f -n '__gcloud_starts_with {starts_with}' -a '{subcmd_list}'")

    flags.update(root_flags)

    flags_list = ' '.join([f'-l {flag[2:]}' for flag in flags])
    completions.append(f"complete -c gcloud -f -n '__gcloud_starts_with {starts_with}' {flags_list}")

    for sub, subval in subcmds.items():
        generate(sub, subval, preceeding + [sub], completions, root_flags)


def get_output_file(output: str) -> str:
    if os.path.isdir(output):
        return os.path.join(output, DEFAULT_OUTPUT_FILE)

    output_dir = os.path.dirname(output)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output


def write_completion_file(completions_file: str, output: str, subset: List[str]):
    spec = importlib.util.spec_from_file_location('completions', completions_file)
    completions_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(completions_module)

    commands = completions_module.STATIC_COMPLETION_CLI_TREE
    if subset:
        commands = {
            'commands': {c: v
                         for c, v in commands['commands'].items() if c in subset},
            'flags': commands['flags']
        }
    all_commands = commands['commands']

    logger.debug('Generating completions')

    root_commands = ' '.join(all_commands)
    root_flags = commands['flags']
    completions = []

    generate(None, commands, [], completions, root_flags)

    out = BASE_COMPLETIONS.format(root_commands=root_commands)
    out = out + '\n'.join(completions)

    output = get_output_file(output)
    with open(output, 'w') as o:
        o.write(out)


def get_latest_version():
    logger.debug('Determining latest version')

    client = http.client.HTTPSConnection('cloud.google.com')
    client.request('GET', '/sdk/docs/install-sdk')
    response = client.getresponse()

    match = None

    for line in response:
        line = line.decode('utf-8')
        match = VERSION_REGEX.search(line)
        if match:
            break

    if not match:
        raise Exception('Cannot determine latest version')

    response.close()
    client.close()

    return match.group(1)


def get_sdk_link() -> str:
    version = get_latest_version()
    return ARCHIVE_URL.format(version=version)


def download() -> str:
    temp_archive = f'/tmp/{str(uuid.uuid4())}'

    sdk_link = get_sdk_link()
    url = urlparse(sdk_link)

    logger.debug('Downloading latest version')
    client = http.client.HTTPSConnection(url.netloc)
    client.request('GET', url.path)
    response = client.getresponse()

    with open(temp_archive, 'wb') as archive:
        while True:
            buffer = response.read(BUFFER_SIZE)
            if not buffer:
                break
            archive.write(buffer)

    response.close()
    client.close()

    return temp_archive


def extract(tar_file, remove_archive) -> str:
    logger.debug('Extracting completions file')

    def completion_file(mems):
        for ti in mems:
            if ti.name == COMPLETIONS_FILE:
                yield ti

    tar = tarfile.open(tar_file)

    temp_completion_dir = f'/tmp/{str(uuid.uuid4())}'
    tar.extractall(members=completion_file(tar), path=temp_completion_dir)

    if remove_archive:
        os.remove(tar_file)

    return temp_completion_dir


def process_completion_file(tar_file: str, output: str, subset: List[str]):
    remove_archive = tar_file is None
    if tar_file is None:
        tar_file = download()

    completion_dir = extract(tar_file, remove_archive)
    completion_file = os.path.join(completion_dir, COMPLETIONS_FILE)

    write_completion_file(completion_file, output, subset)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--sdk', help='gcloud archive file')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT_PATH)
    parser.add_argument('-s', '--subset', nargs='+', help='Subset of commands for which to generate completions')
    args = parser.parse_args()

    process_completion_file(args.sdk, args.output, args.subset)


if __name__ == '__main__':
    main()
