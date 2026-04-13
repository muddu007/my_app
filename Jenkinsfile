pipeline {
    agent any
    environment {
        IMAGE_TAG = 'latest'
        THE_BUTLER_SAYS_SO = credentials('afreen_user_aws_id')
    }

    stages {
        // ─── FETCH PARAMETERS FROM AWS SSM ───────────────────────────
        stage('Fetch SSM Parameters') {
            steps {
                    // withCredentials([aws(accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: 'afreen_user_aws_id', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                    script {
                        // Fetch each parameter from AWS SSM Parameter Store
                        env.ECS_SERVICE_NAME = sh(
                            script: "aws ssm get-parameter --name 'ecs_service_name' --query 'Parameter.Value' --output text",
                            returnStdout: true
                        ).trim()

                        echo "ECS Service Name: ${env.ECS_SERVICE_NAME}"
                        env.ECS_CLUSTER_NAME = sh(
                            script: "aws ssm get-parameter --name 'ecs_cluster_name' --query 'Parameter.Value' --output text",
                            returnStdout: true
                        ).trim()

                        env.AWS_DEFAULT_REGION = sh(
                            script: "aws ssm get-parameter --name 'default_region' --query 'Parameter.Value' --output text",
                            returnStdout: true
                        ).trim()

                        env.IMAGE_REPO_NAME = sh(
                            script: "aws ssm get-parameter --name 'image_repo' --query 'Parameter.Value' --output text",
                            returnStdout: true
                        ).trim()

                        env.ECS_TASK_FAMILY = sh(
                            script: "aws ssm get-parameter --name 'ecs_task_family' --query 'Parameter.Value' --output text",
                            returnStdout: true
                        ).trim()
                    }
                    }
            }

        // ─── PRE_BUILD ────────────────────────────────────────────────
        stage('Pre-Build') {
            steps {
                    script {
                        echo 'Logging in to Amazon ECR...'
                        env.AWS_ACCOUNT_ID = sh(
                            script: 'aws sts get-caller-identity --query Account --output text',
                            returnStdout: true
                        ).trim()

                        env.ECR_REGISTRY   = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_DEFAULT_REGION}.amazonaws.com"
                        env.IMAGE_URI      = "${env.ECR_REGISTRY}/${env.IMAGE_REPO_NAME}:${env.IMAGE_TAG}"
                        env.IMAGE_URI_COMMIT = "${env.ECR_REGISTRY}/${env.IMAGE_REPO_NAME}:${env.GIT_COMMIT}"

                        sh """
                            aws ecr get-login-password --region ${env.AWS_DEFAULT_REGION} \
                              | docker login --username AWS --password-stdin ${env.ECR_REGISTRY}
                        """

                        echo 'Pre-build phase complete.'
                    }
            }
        }

        // ─── BUILD ────────────────────────────────────────────────────
        stage('Build') {
            steps {
                script {
                    echo "Build started on ${new Date()}"
                    echo 'Building Docker image...'

                    sh """
                        docker build -t ${env.IMAGE_URI} .
                        docker tag ${env.IMAGE_URI} ${env.IMAGE_URI_COMMIT}
                    """
                }
            }
        }

        stage('Push & Deploy') {
            steps {
                script {
                    echo 'Pushing Docker image to ECR...'
                    sh """
                docker push ${env.IMAGE_URI}
                docker push ${env.IMAGE_URI_COMMIT}
            """

                    echo 'Registering new ECS Task Definition revision...'
                    sh """
                # Fetch current task definition (strip unneeded fields)
                TASK_DEF=\$(aws ecs describe-task-definition \
                    --task-definition ${env.ECS_TASK_FAMILY} \
                    --query 'taskDefinition' \
                    --output json | jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')

                # Swap the image URI to the new commit-tagged image
                NEW_TASK_DEF=\$(echo \$TASK_DEF | jq \
                    --arg IMAGE "${env.IMAGE_URI_COMMIT}" \
                    '.containerDefinitions[0].image = \$IMAGE')

                # Register the new revision and capture its ARN
                NEW_TASK_DEF_ARN=\$(aws ecs register-task-definition \
                    --cli-input-json "\$NEW_TASK_DEF" \
                    --query 'taskDefinition.taskDefinitionArn' \
                    --output text)

                echo "New Task Definition: \$NEW_TASK_DEF_ARN"

                # Update the service to use the new revision
                aws ecs update-service \
                    --cluster ${env.ECS_CLUSTER_NAME} \
                    --service ${env.ECS_SERVICE_NAME} \
                    --task-definition \$NEW_TASK_DEF_ARN \
                    --desired-count 1

                aws ecs wait services-stable \
                    --cluster ${env.ECS_CLUSTER_NAME} \
                    --services ${env.ECS_SERVICE_NAME}
            """
                }
            }
        }
        }

        // ─── POST (cleanup & notifications) ──────────────────────────────
        post {
            always {
                sh """
                docker rmi ${env.IMAGE_URI} || true
                docker rmi ${env.IMAGE_URI_COMMIT} || true
            """
            }
            success {
                echo 'Pipeline completed successfully!'
            }
            failure {
                echo 'Pipeline failed. Check logs above.'
            // Add email/Slack notification here
            }
        }
    }
