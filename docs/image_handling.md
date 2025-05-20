# Image Handling Guidelines

## Crop and Resize Operations

When working with images in our marketing image generator, understanding the proper scaling, cropping, and sizing is essential for ensuring consistent and professional results.

## Integration with Lambda Image Generation Process

This document describes the core image handling logic used by the `image_processor` module referenced in `lambda_overview.md`. The calculations and approaches outlined here are implemented in the `image_handler.py` module, which is used during the "generate" phase of the Lambda function workflow.

When the Lambda function receives a "generate" message type, it:
1. Retrieves the processed JSON payload from the database
2. Passes this JSON to the `ImageProcessor().combine_images()` method
3. The processor iterates through all elements in the JSON, including images
4. For image elements, it calls `process_image()` which applies the scaling and cropping logic described in this document

## Image and Figure Canvas Calculations

### Understanding Normalized Crop Parameters

In our system, both images and figures are specified with normalized crop parameters between 0 and 1, where:
- `cropX`: The starting X position as a percentage of the image width
- `cropY`: The starting Y position as a percentage of the image height
- `cropWidth`: The width of the crop as a percentage of the image width
- `cropHeight`: The height of the crop as a percentage of the image height

### Calculating Target Dimensions

To properly scale and crop elements, follow these steps:

1. Determine which crop dimension is constrained (less than 1)
   - If `cropWidth < 1`: Use width calculations
   - If `cropHeight < 1`: Use height calculations

2. For width-constrained crops (`cropWidth < 1`):
   ```
   targetWidth = finalWidth / cropWidth
   scaleFactor = targetWidth / originalWidth
   targetHeight = originalHeight × scaleFactor
   ```

3. For height-constrained crops (`cropHeight < 1`):
   ```
   targetHeight = finalHeight / cropHeight
   scaleFactor = targetHeight / originalHeight
   targetWidth = originalWidth × scaleFactor
   ```

### Example Calculation for Images

For an original image that is 800×1061 pixels:

```
Original dimensions: 800×1061
Desired output: 1080×1080 (square)
Crop parameters: cropWidth = 0.74537037, cropHeight = 1
```

Since `cropWidth < 1`, we use the width-constrained calculations:

1. Calculate target width:
   ```
   targetWidth = 1080 / 0.74537037 ≈ 1449 pixels
   ```

2. Calculate scale factor:
   ```
   scaleFactor = 1449 / 800 ≈ 1.81125
   ```

3. Calculate target height:
   ```
   targetHeight = 1061 × 1.81125 ≈ 1920 pixels
   ```

4. Apply the crop:
   - Start at X: 1449 × 0.1273148148148149 ≈ 184.5 pixels
   - Use width: 1449 × 0.74537037 ≈ 1080 pixels
   - Start at Y: 0 pixels (since cropY = 0)
   - Use full height: 1920 pixels (since cropHeight = 1)

### Figure Handling Considerations

For figure elements (such as circles, rectangles, etc.), the same general approach is used with a few considerations:

1. For square/circle figures where width equals height:
   - When both dimensions are constrained, use the larger dimension to ensure both constraints are met
   - When only one dimension is constrained, maintain the square aspect ratio
   
2. For non-square figures:
   - Handle each dimension independently when both are constrained
   - Otherwise, follow the same approach as with images

Example for a square figure with cropping:
```
Original dimensions: 200×200 (square)
Crop parameters: cropWidth = 0.8, cropHeight = 0.8
```

Since both dimensions are constrained and the figure is square:
1. Width calculation: 200 / 0.8 = 250
2. Height calculation: 200 / 0.8 = 250
3. Use target dimensions of 250×250 (maintains square aspect ratio)

## Implementation Guidelines

When implementing image processing:

1. Always scale the element to target dimensions first
2. Apply cropping based on normalized parameters
3. Ensure the final output matches the desired dimensions
4. Maintain the original aspect ratio during scaling where appropriate
5. Use high-quality interpolation algorithms for resizing

## Special Cases

### Square Output from Non-Square Input

When creating square output (like 1080×1080) from non-square input:
- If the original is wider than tall: `cropHeight` will likely be 1
- If the original is taller than wide: `cropWidth` will likely be 1

### Full Element Display

To display the full element without cropping, adjust the canvas size to match the aspect ratio of the original element after scaling.

## Quality Considerations

- Ensure images are scaled using high-quality algorithms (e.g., bicubic or Lanczos)
- Avoid multiple resize operations as they can degrade image quality
- Use appropriate image compression based on the output requirements 