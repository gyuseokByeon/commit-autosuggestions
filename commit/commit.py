# Copyright 2020-present Tae Hwan Jung
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import click
import json
import requests
import subprocess
import configparser
import whatthepatch
from os.path import expanduser, join, exists

def get_diff_from_project():
    proc = subprocess.Popen(["git", "diff", "--cached"], stdout=subprocess.PIPE)
    staged_files = proc.stdout.readlines()
    staged_files = [f.decode("utf-8") for f in staged_files]
    return staged_files

def commit_message_parser(messages, endline=1):
    message = ""
    for idx, (path, commit) in enumerate(messages.items()):
        click.echo("  - " + " ".join(commit["message"]))
        message += " ".join(commit["message"])
        if len(messages) - 1 != idx:
            message += ("\n" * endline)
    return message

def tokenizing(code):
    data = {"code": code }
    res = requests.post(
        'http://127.0.0.1:5000/tokenizer',
        data=json.dumps(data),
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    return json.loads(res.text)["tokens"]

def commit_autosuggestions(diffs):
    commit_message = {}
    for idx, example in enumerate(whatthepatch.parse_patch(diffs)):
        if not example.changes:
            continue

        isadded, isdeleted = False, False
        added, deleted = [], []
        for change in example.changes:
            if change.old == None and change.new != None:
                added.extend(tokenizing(change.line))
                isadded = True
            elif change.old != None and change.new == None:
                deleted.extend(tokenizing(change.line))
                isdeleted = True

        if isadded and isdeleted and example.header.new_path:
            data = {"idx": idx, "added" : added, "deleted" : deleted}
            res = requests.post(
                'http://127.0.0.1:5000/diff',
                data=json.dumps(data),
                headers={'Content-Type': 'application/json; charset=utf-8'}
            )
            commit = json.loads(res.text)
            commit_message[example.header.new_path] = commit
        else:
            data = {"idx": idx, "added": added, "deleted": deleted}
            res = requests.post(
                'http://127.0.0.1:5000/added',
                data=json.dumps(data),
                headers={'Content-Type': 'application/json; charset=utf-8'}
            )
            commit = json.loads(res.text)
            commit_message[example.header.new_path] = commit
    return commit_message

def commit(message):
    subprocess.Popen(["git", "commit", "-m", message], stdout=subprocess.PIPE)

@click.group(invoke_without_command=True)
@click.pass_context
@click.option('--file', '-f', type=click.File('r'),
    help='patch file containing git diff '
         '(e.g. file created by `git add` and `git diff --cached > test.diff`)')
@click.option('--verbose', '-v', is_flag=True,
    help='print suggested commit message more detail.')
@click.option('--autocommit', '-a', is_flag=True,
    help='automatically commit without asking if you want to commit')
@click.option('--endline', '-e', type=int, default=1,
    help='number of endlines for each commit message generated by the diff of each file')
def cli(ctx, file, verbose, autocommit, endline):
    if not ctx.invoked_subcommand:
        staged_files = file if file else get_diff_from_project()
        staged_files = [f.strip() for f in staged_files]
        diffs = "\n".join(staged_files)

        messages = commit_autosuggestions(diffs=diffs)
        if verbose:
            click.echo(
                json.dumps(messages, indent=4, sort_keys=True) + "\n"
            )

        click.echo(click.style('[INFO]', fg='green') + " The generated message is as follows:")
        message = commit_message_parser(messages, endline=endline)

        if autocommit or click.confirm('Do you want to commit this message?'):
            commit(message)


@cli.command()
@click.option('--profile', default='default', type=str,
    help='unique name for managing each independent settings')
@click.option('--endpoint', default='http://127.0.0.1:5000/', type=str,
    help='endpoint address accessible to the server (example:http://127.0.0.1:5000/)')

def configure(profile, endpoint):
    path = join(expanduser("~"), '.commit-autosuggestions.ini')
    config = configparser.ConfigParser()
    if exists(path):
        config.read(path)
    if profile not in config:
        config[profile] = {}
    if endpoint:
        config[profile]['endpoint'] = endpoint

    click.echo(f"configure of commit-autosuggestions is setted up in {path}.")
    for key in config[profile]:
        click.echo(click.style(key, fg='green') + config[profile][key])

if __name__ == '__main__':
    cli()