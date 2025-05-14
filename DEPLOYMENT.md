# Deployment Instructions

This document outlines the steps required to deploy the Marketing Image Generator Serverless application to AWS.

## Prerequisites

1.  **AWS Account:** You need an active AWS account.
2.  **IAM User:** Create an IAM user in your AWS account with:
    -   **Programmatic Access** (Access Key ID and Secret Access Key).
    -   Sufficient permissions to manage Lambda, ECR, S3, IAM, CloudFormation, and CloudWatch Logs. For development, `AdministratorAccess` is the simplest, but scope down permissions for production.
3.  **AWS CLI:** Install and configure the AWS Command Line Interface.
    -   Installation: [AWS CLI Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
    -   Configuration: Run `aws configure` and provide the Access Key ID, Secret Access Key, and default region for your IAM user.
4.  **Node.js & npm:** Install Node.js (which includes npm), required for the Serverless Framework.
    -   Download: [Node.js Website](https://nodejs.org/)
5.  **Serverless Framework:** Install the Serverless Framework CLI globally.
    ```bash
    npm install -g serverless
    ```
6.  **Docker:** Install Docker Desktop or Docker Engine.
    -   Download: [Docker Website](https://www.docker.com/products/docker-desktop/)

## Deployment Steps

1.  **Clone the Repository (if necessary):**

    ```bash
    git clone <your-repository-url>
    cd marketingImageGen # Or your project directory
    ```

2.  **Update Configuration (`serverless.yml`):**

    -   Open the `serverless.yml` file.
    -   In the `provider.environment` section, update the default values for `INPUT_BUCKET` and `OUTPUT_BUCKET` with the names of your _actual_ S3 buckets.

    ```yaml
    provider:
        # ...
        environment:
            INPUT_BUCKET: ${env:INPUT_BUCKET, 'your-actual-s3-input-bucket'}
            OUTPUT_BUCKET: ${env:OUTPUT_BUCKET, 'your-actual-s3-output-bucket'}
        # ...
    ```

    -   _(Alternatively, set `INPUT_BUCKET` and `OUTPUT_BUCKET` as environment variables in your terminal before deploying)._

3.  **Build the Docker Image:**

    -   Ensure Docker is running.
    -   From the project root directory, run:

    ```bash
    docker build -t marketing-image-gen .
    ```

4.  **Authenticate Docker with AWS ECR:**

    -   Replace `<your-region>` and `<your-aws-account-id>` with your details.

    ```bash
    aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com
    ```

5.  **Tag the Docker Image for ECR:**

    -   The Serverless Framework will create an ECR repository named `serverless-<service>-<stage>` (e.g., `serverless-marketing-image-gen-dev`).
    -   Replace `<your-aws-account-id>` and `<your-region>`.

    ```bash
    docker tag marketing-image-gen:latest <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com/serverless-marketing-image-gen-dev:appimage
    ```

    -   _(Note: The `:appimage` tag matches the logical image name in `serverless.yml`)_

6.  **Push the Docker Image to ECR:**

    -   Replace `<your-aws-account-id>` and `<your-region>`.

    ```bash
    docker push <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com/serverless-marketing-image-gen-dev:appimage
    ```

7.  **Deploy using Serverless Framework:**
    -   Ensure your AWS CLI is configured correctly (`aws configure`).
    -   From the project root directory, run:
    ```bash
    serverless deploy
    ```
    -   _(Shorthand: `sls deploy`)_
    -   The command will provision the AWS resources defined in `serverless.yml` (Lambda function, IAM role, etc.) using the pushed ECR image. Monitor the output for success or errors.

## Post-Deployment

-   **S3 Trigger (Optional):** If you want the Lambda function to trigger automatically when a JSON file is uploaded to the input bucket, uncomment the `events` section under `functions.generateImage` in `serverless.yml` and run `serverless deploy` again.
-   **Testing:** You can test the deployed function by:
    -   Uploading a valid JSON file to the configured `INPUT_BUCKET` (if the S3 trigger is enabled).
    -   Invoking the function manually via the AWS Management Console or AWS CLI (`aws lambda invoke ...`).
    -   Using `serverless invoke -f generateImage --log` (this might require setting the `INPUT_KEY` environment variable for the function if not triggered by S3).
-   **Monitoring:** View logs using the AWS CloudWatch console or the Serverless Framework:
    ```bash
    serverless logs -f generateImage -t
    ```

## Removing the Stack

To remove all deployed resources, run:

```bash
serverless remove
```

**Note:** This will remove the Lambda function, IAM roles, and the ECR repository created by Serverless Framework. It usually _does not_ delete S3 buckets unless explicitly configured to do so.
