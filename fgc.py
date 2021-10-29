#!/usr/bin/env python3
import argparse
import http.client
import importlib.util
import os.path
import re
import shutil
import tarfile
from typing import Dict
from urllib.parse import urlparse
import uuid


BUFFER_SIZE = 8192
COMPLETIONS_FILE = 'google-cloud-sdk/data/cli/gcloud_completions.py'
VERSION_REGEX = re.compile('Installing the latest Cloud SDK version \(([0-9]+\.[0-9]+\.[0-9]+)\)')


def generate(root, cmds, preceeding, completions, root_flags):
    subcmds = cmds['commands']
    subcmd_list = ' '.join(subcmds.keys())

    flags = cmds['flags']

    starts_with = ' '.join(preceeding)

    if root and subcmd_list:
        completions.append(f"complete -c gcloud -f -n '__gcloud_starts_with {starts_with}' -a '{subcmd_list}'")

    flags.update(root_flags)

    for flag in flags:
        flag = flag[2:]
        completions.append(f"complete -c gcloud -f -n '__gcloud_starts_with {starts_with}' -l {flag}")

    for sub, subval in subcmds.items():
        generate(sub, subval, preceeding + [sub], completions, root_flags)


def write_completion_file(completions_file, output):
    spec = importlib.util.spec_from_file_location('completions', completions_file)
    completions_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(completions_module)

    commands = completions_module.STATIC_COMPLETION_CLI_TREE
    root_commands = ' '.join(commands['commands'])
    root_flags = commands['flags']

    out = f"""function __gcloud_needs_command
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

    completions = []
    generate(None, commands, [], completions, root_flags)
    out = out + '\n'.join(completions)

    output_dir = os.path.dirname(output)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output, 'w') as o:
        o.write(out)


def get_latest_version():
    client = http.client.HTTPSConnection('cloud.google.com')
    client.request('GET', '/sdk/docs/quickstart')
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
    return f'https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-{version}-linux-x86_64.tar.gz'


def download() -> str:
    temp_archive = f'/tmp/{str(uuid.uuid4())}'

    sdk_link = get_sdk_link()
    url = urlparse(sdk_link)

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


def extract(tar_file) -> str:
    def completion_file(mems):
        for ti in mems:
            if ti.name == COMPLETIONS_FILE:
                yield ti

    tar = tarfile.open(tar_file)

    temp_completion_dir = f'/tmp/{str(uuid.uuid4())}'
    tar.extractall(members=completion_file(tar), path=temp_completion_dir)

    os.remove(tar_file)

    return temp_completion_dir


def process_completion_file(output: str):
    tar_file = download()
    completion_dir = extract(tar_file)
    completion_file = os.path.join(completion_dir, COMPLETIONS_FILE)

    write_completion_file(completion_file, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', default=os.path.expanduser('~/.local/share/chezmoi/dot_config/fish/completions/gcloud.fish'))
    args = parser.parse_args()

    process_completion_file(args.output)


if __name__ == '__main__':
    main()
