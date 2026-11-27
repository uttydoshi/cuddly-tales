#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.github_deploy_stack import GithubDeployStack
from stacks.site_stack import SiteStack
from stacks.stage import LIVE

app = cdk.App()

# Everything lives in us-east-1: CloudFront only accepts ACM certificates from there.
env = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region="us-east-1")

# The live copy (cuddly-tales.ukdoshi.com). It adds its records to ukdoshi-site's
# ukdoshi.com zone (the UkdoshiDns stack), which must already exist.
SiteStack(app, LIVE.stack_name("Site"), stage=LIVE, env=env)

# Deployed by hand, once: lets GitHub Actions deploy the stack above on pushes to main.
# GitHub's token names the repo as owner@id/repo@id, so a renamed or recreated repo can't deploy.
GithubDeployStack(
    app,
    "CuddlyTalesGithubDeploy",
    repo="uttydoshi@83499703/cuddly-tales@1474185990",
    branches=["main"],
    role_name="cuddly-tales-github-deploy",
    env=env,
)

app.synth()
