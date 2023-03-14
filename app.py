#!/usr/bin/env python3
import os
import yaml

import aws_cdk as cdk
from aws_cdk import (
    App, Tags, Environment,Duration,Stack,RemovalPolicy,
) 

from lambda_docker.lambda_docker_stack import LambdaStack
# from lambda_docker.function_stack import FunctionStack
from lambda_docker.apprunner_stack import AppRunnerStack


config=yaml.safe_load(open('config.yaml'))

env_main = cdk.Environment(
    #account=config['env']['id'], 
    account=os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]),    
    region=config['env']['region']
    )

props={
    "namespace": f"{config['app']['namespace']}",
    "service": f"{config['app']['service']}",
}

app = cdk.App()

lambda_stack=LambdaStack(
    app, 
    f"{config['app']['namespace']}-lambda",
    props,
    env=env_main,  
)

# function_stack=FunctionStack(
#     app, 
#     f"{config['app']['namespace']}-function",
#     props,
#     env=env_main,  
# )

apprunner_stack=AppRunnerStack(
    app, 
    f"{config['app']['namespace']}-apprunner",
    lambda_stack.outputs,
    referenced_ecr_image_repo=lambda_stack.ecr_image_repo,
    env=env_main,  
)

app.synth()