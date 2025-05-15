# Product Requirements Document: Dynamic Image Generation Service

## 1. Introduction

**Purpose:** To provide an automated service that dynamically generates marketing images based on structured JSON input.
**Goal:** Enable users to create customized images by defining layers, text, figures, and other elements programmatically, with flexible font handling.

## 2. Core Functionality: Dynamic Image Generation

The primary function of this service is to accept a JSON file detailing the composition of an image and produce a final PNG image as output. This includes rendering text with specified fonts, drawing shapes, and compositing various elements.

## 3. System Architecture & Workflow

The service is implemented as an AWS Lambda function, triggered by events (typically S3 object creation) or direct invocation.

### 3.1. Lambda Handler (`main.lambda_handler`)

-   **Role:** Acts as the main entry point for the service, orchestrating the image generation process.
-   **Workflow:**
    1.  **Event Reception:** Receives an event (e.g., an S3 trigger when a JSON input file is uploaded).
    2.  **Input Parsing:** Retrieves and parses the input JSON file from the specified S3 bucket. This JSON contains the instructions for image generation.
    3.  **ImageProcessor Instantiation:** Initializes an `ImageProcessor` instance. The `ImageProcessor` is responsible for the actual image creation logic.
    4.  **Processing:** Invokes the `ImageProcessor` to generate the image based on the parsed JSON data.
    5.  **Output Storage:** Saves the resulting PNG image to a designated output S3 bucket.
    6.  **Response:** Returns a success or error message, including the S3 path to the generated image.

### 3.2. Image Processor (`image_processor.ImageProcessor`)

-   **Role:** Manages the core image manipulation and composition logic.
-   **Workflow:**
    1.  **Initialization:**
        -   Initializes a `FontManager` instance, providing it with necessary configurations (S3 bucket for fonts, Google API Key, and default font path).
    2.  **JSON Interpretation:** Parses the input JSON data to understand the layers, text elements (content, font family, variant, size, color), figures (shapes, colors), and other image properties.
    3.  **Element Rendering:**
        -   For text elements, it requests the required font from the `FontManager`.
        -   Uses the Pillow (PIL) library to draw text (including text with colored, rounded-corner backgrounds, if specified), shapes, and other graphical elements onto image layers.
    4.  **Image Composition:** Composites all rendered layers into a single final image.
    5.  **Return Image:** Returns the final PIL `Image` object to the Lambda handler.

### 3.3. Font Manager (`image_processor.FontManager`)

-   **Role:** Dynamically provides font files required for text rendering, abstracting the source of the font.
-   **Workflow (Order of Operations for Font Retrieval):**
    1.  **Local Cache (`/tmp`):** Checks if the requested font (family + variant) already exists in the Lambda's `/tmp` directory (from a previous download in a warm invocation). If yes, returns the local path.
    2.  **S3 Bucket:** If not in `/tmp`, checks a designated S3 bucket for the font file.
        -   If found, downloads the font to `/tmp`, caches it, and returns the local path.
    3.  **Google Fonts API:** If the font is not found in `/tmp` or S3:
        -   Queries the Google Fonts API using the provided `GOOGLE_API_KEY` for the font family.
        -   If the family and specific variant are found, it downloads the `.ttf` file.
        -   Saves the downloaded font to `/tmp` for immediate use.
        -   Uploads the downloaded font to the S3 font bucket for future, faster retrieval (effectively populating the S3 cache).
        -   Returns the local path from `/tmp`.
    4.  **Default Font Fallback:** If all previous methods fail:
        -   Falls back to a bundled default font (typically Roboto Regular) that is packaged with the Lambda deployment.
        -   This ensures text rendering can proceed even if external font sources are unavailable.
    5.  **PIL Default Font Last Resort:** If even the default font fails to load:
        -   As a last resort, uses PIL's built-in default font to ensure text can still be rendered.
-   **Font Loading:** The `get_font` method manages the entire font retrieval and loading process, returning a usable `PIL.ImageFont.FreeTypeFont` object at the specified size, with appropriate fallbacks at each level.

## 4. Key Features

-   **JSON-Driven Composition:** Images are defined entirely by a structured JSON input.
    -   **Text Backgrounds:** Supports rendering of configurable backgrounds behind text elements, including color, padding, and corner radius.
-   **Dynamic Font Handling:**
    -   Supports fonts from Google Fonts API.
    -   Supports fonts pre-loaded into an S3 bucket.
    -   Utilizes Lambda's `/tmp` directory for local caching of fonts within an invocation or across warm invocations.
    -   Provides reliable fallback to bundled default fonts when external sources fail.
-   **S3 Integration:** Uses S3 for both input (JSON definitions) and output (generated PNG images), as well as for an intermediary font cache.
-   **Serverless Architecture:** Leverages AWS Lambda for scalable, on-demand execution.

## 5. Input/Output

-   **Input:**
    -   A JSON file uploaded to a specified S3 input bucket. The schema of this JSON defines the elements, text, styles, and layout of the image to be generated.
    -   Environment Variables: `INPUT_BUCKET`, `OUTPUT_BUCKET`, `FONT_S3_BUCKET`, `GOOGLE_API_KEY`.
-   **Output:**
    -   A PNG image file saved to a specified S3 output bucket.

## 6. Dependencies & Environment

-   **Platform:** AWS Lambda (Python 3.11 runtime).
-   **Core Libraries:**
    -   `Pillow (PIL)`: For all image manipulation tasks.
    -   `boto3`: AWS SDK for Python, used for S3 interactions.
    -   `requests`: For making HTTP calls to the Google Fonts API.
-   **Configuration:**
    -   `GOOGLE_API_KEY`: An API key for accessing the Google Fonts Developer API, supplied as an environment variable to the Lambda function.
    -   S3 bucket names for input JSON, output images, and cached fonts, supplied as environment variables.
-   **Dockerfile:** Includes dependencies like `harfbuzz-devel`, `fribidi-devel`, `raqm-devel` to ensure Pillow has support for complex text layouts if/when needed, although the primary focus is on standard TrueType fonts.

## 7. Font Management Strategy

The system employs a multi-tiered approach to font handling to balance performance, flexibility, and reliability:

1. **Performance:** Local `/tmp` caching for fast repeated access
2. **Flexibility:** Dynamic fetching from Google Fonts API for wide font variety
3. **Persistence:** S3 storage of previously used fonts to reduce API calls
4. **Reliability:** Bundled default fonts to ensure text rendering works even when external services are unavailable
5. **Last Resort:** PIL's built-in default font as final fallback
