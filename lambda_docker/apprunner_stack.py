from aws_cdk import (
    # Duration,
    CfnOutput,
    Stack,
    aws_apprunner,
    aws_ecr,
    aws_ssm,
    aws_iam as iam,
)
import json
from constructs import Construct
 
class AppRunnerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, props, referenced_ecr_image_repo: aws_ecr.IRepository, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # lookup repo from prior stack in CDK
        ecr_image_repo = ((aws_ecr.Repository.from_repository_name(
            self,
            id='LambdaDockerCDK-AppRunner-ECR-Image-Repo',
            repository_name=referenced_ecr_image_repo.repository_name
            )
            ).repository_uri)+":latest"
       
        # create the ECR Access role with permissions to call ECR
        ecr_access_role = iam.Role(
            self,
            "LambdaDockerCDK-ECR Access Role",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_managed_policy_arn(
                self,
                id = "LambdaDockerCDK-ECR Access Policy",
                managed_policy_arn="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
            )
            ],
        )

        # create the ECR Instance role
        ecr_instance_role = iam.Role(
            self,
            "LambdaDockerCDK-ECR Instance Role",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
        )

        #native construct for AppRunner       
        apprun_serv = aws_apprunner.CfnService(
            self,
            "service",
            service_name="AppRunnerApp",
            source_configuration=aws_apprunner.CfnService.SourceConfigurationProperty(
            #comment out next 3 lines for public image   
                authentication_configuration=aws_apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=ecr_access_role.role_arn,
                    ),
                auto_deployments_enabled = False,
                image_repository=aws_apprunner.CfnService.ImageRepositoryProperty(
                        # image_identifier="public.ecr.aws/aws-containers/hello-app-runner:latest",
                        image_identifier=str(ecr_image_repo),
                        # image_repository_type="ECR_PUBLIC",
                        image_repository_type="ECR",
                        image_configuration= aws_apprunner.CfnService.ImageConfigurationProperty(
                            # port = "80", #Apache, or 8080
                            port = "8501", #Streamlit
                        ),
                       )
                ),
            instance_configuration = aws_apprunner.CfnService.InstanceConfigurationProperty(
                instance_role_arn=ecr_instance_role.role_arn,
                ) 
            )
 
        CfnOutput(
            self,
            "url",
            value="https://" + apprun_serv.attr_service_url,
        )