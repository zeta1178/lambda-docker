import json
import os
os.environ["GIT_PYTHON_REFRESH"] = "quiet"
import git
from git import Repo
import sys
import shutil
import boto3
import yaml
from datetime import datetime

def lambda_handler(event, context):
    git_user        ='git_user+1-at-670927383464'
    git_password    ='64gSqV5jXnDYu0rtlNW4Q9qeCjH9Ulg4gFri1HsBNXY='
    git_url_staging =f"https://{git_user}:{git_password}@git-codecommit.us-east-1.amazonaws.com/v1/repos/codecommit-codecommit-repo-staging"
    git_url_target  =f"https://{git_user}:{git_password}@git-codecommit.us-east-1.amazonaws.com/v1/repos/codecommit-codecommit-repo"
    if os.path.isdir('/tmp/pipeline'):
        shutil.rmtree('/tmp/pipeline')
    local_dir='/tmp/pipeline'
    repo = Repo.clone_from(git_url_staging, local_dir, branch='main')
    remote = repo.create_remote('target', url=git_url_target)
    input=(event['Yaml'])
    f = open(f"/tmp/pipeline/{input}.yaml", "w+")
    yaml.dump(input, f, allow_unicode=True)
    repo.git.add('--all')
    now = datetime.now()
    date_time = now.strftime("%m%d%Y%H%M%S")
    commit_message= f"code-added-{date_time}"
    repo.index.commit(commit_message)
    remote.push(refspec='{}:{}'.format('main', 'pipeline'))
    # repo.git.push("target", "HEAD:refs/for/pipeline")
