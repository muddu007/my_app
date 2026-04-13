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

                    // For SecureString parameters, add --with-decryption flag
                    // env.API_KEY = sh(
                    //     script: "aws ssm get-parameter --name '/your-app/api-key' --with-decryption --query 'Parameter.Value' --output text",
                    //     returnStdout: true
                    // ).trim()
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

        // ─── POST_BUILD / DEPLOY ──────────────────────────────────────
        stage('Push & Deploy') {
            steps {
                    script {
                        echo 'Pushing Docker image to ECR...'
                        sh """
                            docker push ${env.IMAGE_URI}
                            docker push ${env.IMAGE_URI_COMMIT}
                        """

                        echo 'Scaling up ECS service...'
                        sh """
                            aws ecs update-service \
                                --cluster ${env.ECS_CLUSTER_NAME} \
                                --service ${env.ECS_SERVICE_NAME} \
                                --desired-count 1

                            aws ecs wait services-stable \
                                --cluster ${env.ECS_CLUSTER_NAME} \
                                --services ${env.ECS_SERVICE_NAME}
                        """

                        echo 'Writing imagedefinitions.json...'
                        sh """
                            printf '[{"name":"%s","imageUri":"%s"}]' \
                                "${env.IMAGE_REPO_NAME}" "${env.IMAGE_URI}" > imagedefinitions.json
                            cat imagedefinitions.json
                        """

                        // Archive as Jenkins artifact (equivalent to CodeBuild artifacts)
                        archiveArtifacts artifacts: 'imagedefinitions.json', fingerprint: true
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
