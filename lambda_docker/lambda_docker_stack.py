from aws_cdk import (
    aws_s3,
    aws_iam,
    aws_codecommit,
    aws_ecr,
    aws_codebuild,
    aws_codepipeline,
    aws_codepipeline_actions,
    aws_ssm,
    Aws,App, CfnOutput, Stack, Duration, RemovalPolicy,
)
 
from constructs import Construct

class LambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, props, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #create artifact bucket, pipeline requires versioned bucket
        artifact_bucket = aws_s3.Bucket(
            self, "LambdaDockerCDK-ArtifactBucket",
            # bucket_name=f"{Stack.of(self).stack_name}-artifact-bucket-{(str(Stack.of(self).get_logical_id))[-8:-2]}-{Aws.REGION}",
            versioned=True,
            enforce_ssl=True,
            object_ownership=aws_s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY
        )

        # create the codecommit repo
        codecommit_repo = aws_codecommit.Repository(
            self,
            "LambdaDockerCDK-CodeCommit_Repo",
            repository_name=f"{props['service']}-lambdadocker-repo",
            code=aws_codecommit.Code.from_directory(directory_path="asset", branch="main")
        )
 
        # ssm parameter to get bucket name later in the push.sh script to trigger CodePipeline
        bucket_param = aws_ssm.StringParameter(
            self, "LambdaDockerCDK-ArtifactBucketParameter",
            parameter_name=f"/{props['service']}-cdk/lambdadocker-artifactbucket",
            string_value=artifact_bucket.bucket_arn,
            description='LambdaDockerCDK-ArtifactBucketParameter'
        )

        # ssm parameter to get CodeCommit Repo arn
        repo_param = aws_ssm.StringParameter(
            self, "LambdaDockerCDK-CodeCommit Repo Parameter",
            parameter_name=f"/{props['service']}-cdk/lambdadocker-repository",
            string_value=codecommit_repo.repository_name,
            description='LambdaDockerCDK-CodeCommit Repository'
        )

        # note create KMS to encrypt codebuild
        
        # create ecr repo to push docker image into
        #Note: consider changing to registry
        ecr_image_repo = aws_ecr.Repository(
            self, "LambdaDockerCDK-ECR",
            repository_name=f"{props['service']}-lambdadocker-ecr",
            removal_policy=RemovalPolicy.DESTROY,
            image_scan_on_push=True,
            image_tag_mutability = aws_ecr.TagMutability.MUTABLE
        )

        # ssm parameter to get ecr uri
        ecr_param = aws_ssm.StringParameter(
            self, "LambdaDockerCDK-ECR URI Parameter",
            parameter_name=f"{props['namespace']}-lambdadocker-ecr-uri",
            string_value=ecr_image_repo.repository_uri,
            description='LambdaDockerCDK-ECR URI'
        )

        ecr_param_repo = aws_ssm.StringParameter(
            self, "LambdaDockerCDK-ECR REPO Parameter",
            parameter_name=f"{props['namespace']}-lambdadocker-ecr-repo",
            string_value=ecr_image_repo.repository_arn,
            description='LambdaDockerCDK-ECR REPO'
        )

        #define codebuild role
        codebuild_role = aws_iam.Role(
            self,
            "LambdaDockerCDK-Codebuild_Role",
          assumed_by=aws_iam.ServicePrincipal("codebuild.amazonaws.com")
          )
        codebuild_role.add_to_policy(aws_iam.PolicyStatement(
            effect=aws_iam.Effect.ALLOW,
            resources=["*"],
            actions=["ssm:*", "s3:*", "ecr:*", "codecommit:*" ],
            ))
           
        # codebuild project meant to run in pipeline
        codebuild_project = aws_codebuild.PipelineProject(
            self, "LambdaDockerCDK-CodeBuild Project",
            role=codebuild_role,
            project_name=f"{props['service']}-lambdadocker-cdk-build-project",
            build_spec=aws_codebuild.BuildSpec.from_object_to_yaml({
                "version": "0.2",
                "phases": {
                    "install":{
                        "runtime-versions":
                            {
                                "python" : 3.9,
                            }
                    },
                    "pre_build": {
                        "commands": [
                        "REPO_TAG=$(date '+%Y%m%d%H%M%S')",
                        "IMAGE_VERSION_TAG=$REPO_NAME-$(date '+%Y%m%d%H%M%S')",  
                        "echo Logging in to Amazon ECR...",
                        "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ACCT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Build started on `date`",
                            "echo Building the Docker image...",
                            "docker build -t $REPO_NAME:$REPO_TAG . --build-arg BASE_DATE=$REPO_TAG",
                            "docker build -t $REPO_NAME:latest .",
                            "docker tag $REPO_NAME:$REPO_TAG $ECR_URI:$REPO_TAG",
                            "docker tag $REPO_NAME:latest $ECR_URI:latest"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Build completed on `date`",                        
                            "echo Pushing the Docker image...",
                            "docker push $ECR_URI:$REPO_TAG",
                            "docker push $ECR_URI:latest",
                            "printf '[{\"name\":\"Docker-Image\",\"imageUri\":\"%s\"}]' \"$ECR_URI:$IMAGE_VERSION_TAG\" > image.json",
                            "cat image.json"                        
                        ]
                    }
                },
                "shell": "bash",
                "artifact": {
                    "files": "image.json"
                },
            }),
            environment=aws_codebuild.BuildEnvironment(
                privileged=True,
                compute_type=aws_codebuild.ComputeType.LARGE,
                build_image=aws_codebuild.LinuxBuildImage.AMAZON_LINUX_2_4
            ),
            # pass the ecr repo uri into the codebuild project so codebuild knows where to push
            environment_variables={
                'ECR_URI': aws_codebuild.BuildEnvironmentVariable(
                    value=ecr_image_repo.repository_uri),
                'ECR_NAME': aws_codebuild.BuildEnvironmentVariable(
                    value=ecr_image_repo.repository_name),
                'ACCT_ID': aws_codebuild.BuildEnvironmentVariable(
                    value=Aws.ACCOUNT_ID),
                'REPO_NAME': aws_codebuild.BuildEnvironmentVariable(
                    value=ecr_image_repo.repository_name ),
            },
            description='LambdaDockerCDK-Pipeline for CodeBuild',
            timeout=Duration.minutes(60),
            cache=aws_codebuild.Cache.local(aws_codebuild.LocalCacheMode.DOCKER_LAYER),
        )

        # codebuild iam permissions to read write codecommit
        codecommit_repo.grant_pull_push(codebuild_role)

        # codebuild permissions to interact with ecr
        ecr_image_repo.grant_pull_push(codebuild_role)

        # create codepipeline role
        codepipeline_role = aws_iam.Role(
            self,
            "LambdaDockerCDK-CodePipeline_role",
            assumed_by=aws_iam.ServicePrincipal("codepipeline.amazonaws.com")
        )

        # define the s3 artifact
        source_output = aws_codepipeline.Artifact(artifact_name="SourceArtifact")
 
        # create codepipeline source codecommit stage action
        source_action = aws_codepipeline_actions.CodeCommitSourceAction(
            action_name="LambdaDockerCDK-PipelineSourceStage",
            repository=codecommit_repo,
            output=source_output,
            trigger=aws_codepipeline_actions.CodeCommitTrigger.POLL,
            branch="main"
        )
 
        # create codepipeline build stage action
        build_action = aws_codepipeline_actions.CodeBuildAction(
            action_name="LambdaDockerCDK-PipelineCodeBuildStage",
            project=codebuild_project,
            input=source_output,
            outputs=[aws_codepipeline.Artifact()],
        )

        # create codepipeline
        pipeline = aws_codepipeline.Pipeline(
            self,
            "LambdaDockerCDK-Pipeline to create image",
            role=codepipeline_role,
            stages=[
                aws_codepipeline.StageProps(
                    stage_name="Source",
                    actions=[source_action]
                ),
                aws_codepipeline.StageProps(
                    stage_name="Build",
                    actions=[build_action]
                )
            ],
            artifact_bucket=artifact_bucket
        )    

        # codebuild to be able to push to the ecr image repo.
        ecr_image_repo.grant_pull_push(codebuild_role)

        # Prepares output attributes for bucket and codebuild
        self.output_props = props.copy()
        self.output_props['artifact_bucket']= artifact_bucket

        # Prepares output attributes for ECR
        self._ecr_image_repo = ecr_image_repo
 
    # pass objects to another stack
    @property
    def outputs(self):
        return self.output_props
 
    @property
    def ecr_image_repo(self) -> aws_ecr.IRepository:
        return self._ecr_image_repo