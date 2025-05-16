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
7. **S3:** Create 2 S3 buckets. 1 for fonts and another for the output images 
    - Fonts will be stored in <font_bucket>/fonts/<font-name>.ttf 
    - Output image bucket will need public access and bucket policy 
    ```
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadForProcessedImages",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::upwork-marketing-image-output/processed_images/*"
            }
        ]
    }
    ```
8. DB table 
    ```
    CREATE TABLE generated_feeds (
        id                  UUID             PRIMARY KEY,
        generated_json      JSONB            NOT NULL,
        generated_img_url   TEXT,
        outfeed_id          UUID             NOT NULL,
        user_template_id    UUID             NOT NULL,
        status              VARCHAR(50)      NOT NULL DEFAULT 'pending',
        error_message       TEXT,
        created_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW()
    )
    ```

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

3.  **Authenticate Docker with AWS ECR:**

    -   Replace `<your-region>` and `<your-aws-account-id>` with your details.

    ```bash
    aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com
    ```

5.  **Build, Push Docker Image to ECR, and Deploy with Serverless Framework:**

    The following command combines building the Docker image, pushing it to ECR, and then deploying the Serverless stack. 
    Ensure you replace placeholders like `<your-aws-account-id>`, `<your-region>`, and potentially the ECR repository name (`serverless-marketing-image-gen-dev`) and image tag (`appimage`) if they differ from your setup. The repository name is typically derived from your service name (`marketing-image-gen`) and stage (`dev`) in `serverless.yml`.

    Example command (replace with your specific values):
    ```bash
    docker build --no-cache --platform linux/amd64 -t <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com/<your-ecr-repo-name>:<image-tag> . && docker push <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com/<your-ecr-repo-name>:<image-tag> && sls deploy
    ```

    Based on your provided command, this would look like (ensure these values match your environment):
    ```bash
    docker build --no-cache --platform linux/amd64 -t 481665127174.dkr.ecr.ap-south-1.amazonaws.com/serverless-marketing-image-gen-dev:appimage . && docker push 481665127174.dkr.ecr.ap-south-1.amazonaws.com/serverless-marketing-image-gen-dev:appimage && sls deploy
    ```

    **Explanation of the command components:**
    *   `docker build --no-cache --platform linux/amd64 -t <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<REPO_NAME>:<TAG> .`:
        *   Builds the Docker image from the `Dockerfile` in the current directory (`.`).
        *   `--no-cache`: Disables caching for the build.
        *   `--platform linux/amd64`: Specifies the platform, crucial for Lambda compatibility.
        *   `-t ...`: Tags the image with the full ECR repository URI and tag. The `<REPO_NAME>` should match what Serverless Framework expects (e.g., `serverless-<service-name>-<stage>`) and `<TAG>` should match the logical image name in `serverless.yml` (e.g., `appimage`).
    *   `&& docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<REPO_NAME>:<TAG>`:
        *   Pushes the tagged image to your AWS ECR repository.
    *   `&& sls deploy`:
        *   Deploys your service using the Serverless Framework. `serverless.yml` should be configured to use this ECR image.

    The `sls deploy` command will provision the AWS resources defined in `serverless.yml` (Lambda function, IAM role, etc.) using the pushed ECR image. Monitor the output for success or errors.

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
