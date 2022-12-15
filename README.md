# fish-gcloud-completions

Create Fish shell completions for `gcloud` by processing the completions file from the latest Google Cloud SDK.

## Usage

```
usage: fgc.py [-h] [-f SDK] [-o OUTPUT] [-s SUBSET [SUBSET ...]]

options:
  -h, --help            show this help message and exit
  -f SDK, --sdk SDK
  -o OUTPUT, --output OUTPUT
  -s SUBSET [SUBSET ...], --subset SUBSET [SUBSET ...]
                        Subset of commands for which to generate completions
```

* `-f`: You can use this option to specify an already downloaded `google-cloud-cli-[...].tar.gz` file. If this is unset the latest CLI archive will be downloaded.
* `-o`: Where to put the resulting completions file, default is `$HOME/.local/share/chezmoi/dot_config/fish/completions`, which is the default [Chezmoi](https://www.chezmoi.io/) source directory.
* `-s`: `gcloud` has many subcommands and processing them naively takes some time, which causes longer wait times for command completions. Alternatively, you can use this argument to specify the top-level subcommands you are solely interested in, like `compute`, `dns` etc.

## Example

Use a locally available archive to output to `$HOME/.config/fish/completions` with only completions for `compute`, `dns`, `network-management` and `topic`:

```shell
$ ./fgc.py -f google-cloud-cli-411.0.0-linux-x86_64.tar.gz -o ~/.config/fish/completions/ -s compute dns network-management topic
```
