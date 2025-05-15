# AWS Lambda: SQS-Driven Dynamic Marketing Image Generation Service

## 1. Overview

This AWS Lambda function orchestrates a two-phase process for dynamically generating marketing images. It is triggered by messages from an Amazon SQS (Simple Queue Service) queue and interacts with a PostgreSQL database, an Auth0 service for authentication, Amazon S3 for image storage, and an internal `image_processor` module for image rendering.

The process involves:

1.  **Processing Phase (`process` message type):** Authenticates a request, fetches data from various PostgreSQL tables, generates multiple product-specific JSON payloads based on a user template, stores these payloads in the database, and then enqueues messages for the generation phase.
2.  **Generation Phase (`generate` message type):** Retrieves a processed JSON payload (identified by an ID from the SQS message), uses the `image_processor` module to render an image, stores the image in S3, and updates the database with the image URL and status.

## 2. Core Functionality & SQS Message Types

The Lambda function handles two types of messages from the same SQS queue:

### 2.1. SQS Message Contracts

-   **Type 1: Process Request**

    ```json
    {
        "type": "process",
        "data": {
            "access_token": "<user_access_token>",
            "user_template_id": "<uuid_of_user_template>",
            "outfeed_id": "<uuid_of_outfeed>"
        }
    }
    ```

-   **Type 2: Generate Image Request**
    ```json
    {
        "type": "generate",
        "data": {
            "generated_feed_id": "<id_from_generated_feeds_table>"
        }
    }
    ```

### 2.2. "process" Message Handler Workflow

1.  **Receive Message:** Lambda polls the SQS queue.
2.  **Authentication & Authorization:**
    -   The `access_token` from `message.data` is validated using Auth0.
    -   The `user_sub` (user subject/ID) is extracted from the validated JWT.
    -   If authentication fails, the Lambda errors, and the SQS message is moved to a Dead Letter Queue (DLQ) with error details.
3.  **Fetch Base User Template:**
    -   Retrieves `template_json` from `facebook_test.user_templates` table using `user_sub` (from token) and `user_template_id` (from SQS message).
4.  **Fetch Field Mapping Definitions:**
    -   Retrieves all rows from `facebook_test.fields` table. This data contains mappings between template variables and product data columns (via `label_name` and `product_map`).
5.  **Fetch User's Products:**
    -   Retrieves all product rows from `facebook_test.products` table associated with the `user_sub`.
6.  **Generate Product-Specific JSONs (Loop per Product):**
    -   For each product fetched:
        -   A deep copy of the base `template_json` is created.
        -   Iterate through each `child` element in the `copied_template_json.pages[0].children`.
        -   The `child.custom.variable` is matched against `fields.label_name`.
        -   If a match is found and `fields.product_map` is non-empty:
            -   The value from `product_row[fields.product_map]` is retrieved.
            -   If `child.type == "text"`, `child.text` is updated with this value.
            -   If `child.type == "image"`, `child.src` is updated with this value.
        -   If no match is found or `product_map` is empty, the child element remains unmodified from the base template.
7.  **Store Generated JSONs & Enqueue "generate" Messages:**
    -   All successfully modified `template_json` variations (one for each product) are collected.
    -   For each of these collected items:
        -   A new row is inserted into the `facebook_test.generated_feeds` table. This row includes:
            -   `generated_json`: The newly modified JSON string.
            -   `outfeed_id`: From the original "process" SQS message.
            -   `user_template_id`: From the original "process" SQS message.
            -   `user_sub`: The user identifier associated with the process.
            -   `status`: Set to **`PROCESSED`**.
            -   `created_at`, `updated_at`: Current timestamps.
        -   Let the auto-generated `id` of this new row be `generated_feed_id`.
        -   A new SQS message `{type: "generate", data: {generated_feed_id: generated_feed_id}}` is then sent to the _same_ SQS queue.
    -   Database insertions are typically committed together, followed by sending all SQS messages.

### 2.3. "generate" Message Handler Workflow

1.  **Receive Message:** Lambda polls the SQS queue.
2.  **Fetch Processed JSON (if applicable):**
    -   Retrieves `generated_json` (and other details like `user_sub`, `outfeed_id`) from `facebook_test.generated_feeds` table using `generated_feed_id` from `message.data`, _only if the record's status is currently `PROCESSED`_.
    -   If the record is not found, not in `PROCESSED` state, or `generated_json` is missing, the generation for this message is skipped (logged appropriately). This prevents reprocessing.
3.  **Update Status to `GENERATING`:**
    -   If the record is suitable for generation, its `status` in `generated_feeds` is updated to **`GENERATING`** (this is an atomic update before image processing begins).
4.  **Image Generation:**
    -   The `image_processor.ImageProcessor().combine_images(generated_json)` method is called to render the image. (This sub-system handles font management, element rendering (including text with backgrounds, images, figures), etc., potentially fetching fonts from Google Fonts and caching them to S3 as per its own configuration).
5.  **Handle Generation Outcome:**
    -   **On Success:**
        -   The generated image (PNG format) is uploaded to the configured S3 output bucket.
        -   The `generated_feeds` table row is updated:
            -   `generated_img_url` is set to the S3 URL of the newly uploaded image.
            -   `status` is set to **`GENERATED`**.
            -   `updated_at` timestamp is refreshed.
    -   **On Failure (during image generation or S3 upload):**
        -   The `generated_feeds` table row is updated:
            -   `status` is set to **`GENERATION_FAIL`**.
            -   `error_message` column is populated with details of the failure.
            -   `updated_at` timestamp is refreshed.

## 3. Database Schema & State Management

The Lambda relies on a PostgreSQL database (`facebook_test` schema) for storing templates, product data, field mappings, and tracking the state of generated images.

### Key Tables:

-   **`user_templates`**: Stores base templates (`id`, `user_sub`, `template_json`, etc.).
-   **`fields`**: Defines mappings for dynamic content (`id`, `label_name`, `product_map`, `type`, etc.).
-   **`products`**: Contains product information linked to users (`id`, `user_sub`, various product attributes like `title`, `image_link`, etc.).
-   **`generated_feeds`**: Tracks each image generation task.
    -   `id` (Primary Key, auto-generated)
    -   `generated_json` (TEXT): The product-specific JSON used for image generation.
    -   `generated_img_url` (TEXT, nullable): URL of the image in S3 once generated.
    -   `outfeed_id` (UUID): From the initial "process" message.
    -   `user_template_id` (UUID): From the initial "process" message.
    -   `status` (VARCHAR): Tracks the current state. Values:
        -   **`PROCESSED`**: JSON generated and ready for image creation.
        -   **`GENERATING`**: Image generation is in progress.
        -   **`GENERATED`**: Image successfully generated and stored in S3.
        -   **`GENERATION_FAIL`**: Image generation failed.
    -   `error_message` (TEXT, nullable): Stores error details if generation fails.
    -   `created_at`, `updated_at` (TIMESTAMPTZ).

## 4. Image Generation Sub-System (`image_processor/` module)

The actual rendering of images from JSON is delegated to the `image_processor` module. This module is responsible for:

-   Parsing the `generated_json`.
-   Handling different element types (text with optional backgrounds featuring configurable color, padding, and corner radius; images; figures).
-   Managing fonts: This may include fetching fonts from Google Fonts, caching them locally (`/tmp`) and to an S3 bucket (`FONT_S3_CACHE_BUCKET`), and using fallback fonts, as detailed in its own documentation or previous versions of this overview.
-   Compositing elements onto a canvas and returning a Pillow image object.

## 5. Configuration

### Environment Variables:

-   **`SQS_QUEUE_URL` (Required):** URL of the main SQS queue (e.g., `MarketingImageGenerationQueue`).
-   **`DLQ_URL` (Optional but Recommended):** URL of the Dead Letter Queue.
-   **`DB_HOST` (Required):** Hostname of the PostgreSQL database.
-   **`DB_PORT` (Required, defaults to 5432 in code):** Port of the PostgreSQL database.
-   **`DB_NAME` (Required):** Name of the PostgreSQL database.
-   **`DB_USER` (Required):** Username for the PostgreSQL database.
-   **`DB_PASSWORD` (Required):** Password for the PostgreSQL database. (Ensure this is managed securely, e.g., via Lambda environment variable encryption or by injecting at deployment time rather than committing to version control if defaults are used in `serverless.yml`).
-   **`AUTH0_DOMAIN` (Required):** Your Auth0 domain for token validation.
-   **`AUTH0_AUDIENCE` (Required):** The audience for your Auth0 API.
-   **`AUTH0_CLIENT_SECRET_ARN` or `AUTH0_ISSUER` etc. (Potentially Required):** Depending on the Auth0 validation library and strategy, other Auth0 related variables might be needed, possibly stored in Secrets Manager.
-   **`S3_IMAGE_OUTPUT_BUCKET` (Required):** Name of the S3 bucket for storing final generated images.
-   **`GOOGLE_API_KEY` (Optional):** API key for Google Fonts Developer API, if the `image_processor.FontManager` uses it for fetching new fonts.
-   **`FONT_S3_CACHE_BUCKET` (Optional):** Name of the S3 bucket used by `image_processor.FontManager` for caching fonts (e.g., `upwork-fonts-assets`).
-   **AWS Region, Logging Level, etc.**

### S3 Path for Generated Images:

A structure like `s3://<S3_IMAGE_OUTPUT_BUCKET>/processed_images/<user_sub>/<outfeed_id>/<generated_feed_id>.png` is recommended.

## 6. IAM Permissions (Lambda Execution Role)

The Lambda's IAM execution role will need permissions for:

-   **SQS:**
    -   `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:SendMessage` for the main SQS queue.
    -   `sqs:GetQueueAttributes` for the main SQS queue.
    -   `sqs:SendMessage` for the DLQ.
-   **AWS Secrets Manager:**
    -   `secretsmanager:GetSecretValue` for secret(s) storing Auth0 client secrets/API keys _if applicable and stored in Secrets Manager_. This is no longer used for database credentials.
-   **S3:**
    -   `s3:PutObject` (and `s3:PutObjectAcl` if specific ACLs are needed) for the `S3_IMAGE_OUTPUT_BUCKET`.
    -   If font caching by `image_processor` is active: `s3:GetObject`, `s3:PutObject` for the `FONT_S3_CACHE_BUCKET`.
-   **CloudWatch Logs:**
    -   `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`.
-   **VPC Access (If DB is in a VPC):**
    -   Permissions like `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface` to allow the Lambda to connect to the VPC.
    -   The Lambda's security group must allow outbound traffic to the DB's security group on the PostgreSQL port.

## 7. Error Handling & Dead Letter Queue (DLQ)

-   **"process" phase critical errors:** Authentication failures, inability to connect to the database after retries, or failure to fetch essential base data (like the user template) will result in the original SQS message being sent to the DLQ. An error will be logged.
-   **"generate" phase fetch errors:** If the Lambda cannot fetch the `generated_json` from `generated_feeds` (e.g., invalid ID), the message may be sent to the DLQ after retries.
-   **Image Generation Failures:** If the `image_processor` fails to generate an image, or if the S3 upload of the generated image fails, the `status` in `generated_feeds` is set to `GENERATION_FAIL`, and an `error_message` is recorded in the table. The SQS message for this "generate" step is considered successfully processed (as the attempt was made), so it does not go to the DLQ for this reason.
-   The DLQ should be monitored for messages that could not be processed, indicating issues that need investigation.

## 8. Python Dependencies

-   `auth0-python`: For Auth0 JWT validation.
-   `psycopg2-binary`: PostgreSQL adapter for Python.
-   `boto3`: AWS SDK for Python (for SQS, S3, Secrets Manager).
-   `Pillow` (PIL Fork): Core image manipulation, used by `image_processor`.
-   `requests`: For HTTP requests, potentially used by `FontManager` or Auth0 interactions.
-   The internal `image_processor` module and its sub-modules.
