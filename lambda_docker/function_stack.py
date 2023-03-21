from aws_cdk import (
    aws_lambda,
    aws_ecr,
    aws_ssm,
    Stack, Duration,
)
 
from constructs import Construct

class FunctionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, props, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        erc_repo=aws_ssm.StringParameter.value_from_lookup(
            self,
            f"{props['namespace']}-lambdadocker-ecr-repo",
        )

        lambdaFn = aws_lambda.Function(
            self,
            f"{props['namespace']}-function",
            # code=aws_lambda.Code.from_asset("lambda_zone"),
            code=aws_lambda.Code.from_ecr_image(
                repository=aws_ecr.Repository.from_repository_arn(
                    self,
                    id="private-repo",
                    repository_arn=erc_repo
                ),
            ),
            runtime=aws_lambda.Runtime.FROM_IMAGE,
            architecture=aws_lambda.Architecture.X86_64,
            handler=aws_lambda.Handler.FROM_IMAGE,
            timeout=Duration.seconds(300),
        )