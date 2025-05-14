# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies
# Added: gcc for compiling C extensions (like Pillow from source)
# Added: pkg-config and make as potential build utilities for Pillow
# Added: harfbuzz-devel, fribidi-devel, raqm-devel for complex text layout with Pillow
# Added: freetype-devel, fontconfig-devel as they are common dependencies for font handling
# Added: libjpeg-turbo-devel for JPEG support when compiling Pillow
RUN yum update -y && \
    yum install -y gcc pkgconfig make cairo harfbuzz-devel fribidi-devel raqm-devel freetype-devel fontconfig-devel libjpeg-turbo-devel && \
    yum clean all

# Set the working directory in the container
WORKDIR /var/task

# Copy requirements first to leverage Docker cache
COPY requirements.txt ./

# Install Python dependencies
# Using --no-cache-dir to reduce image size.
# Reinstall Pillow from source to pick up system libraries like Raqm and JPEG.
# Added a comment to break cache for Pillow install step
RUN echo "Force recompile Pillow" && \
    pip install --no-cache-dir -r requirements.txt -t . && \
    pip uninstall -y Pillow && \
    pip install --no-cache-dir --no-binary :all: Pillow

# If Pillow is a direct dependency in requirements.txt and you want to ensure it's always compiled:
# You could modify your requirements.txt to include Pillow like: Pillow --no-binary :Pillow:
# Or, more generally, for all packages in requirements.txt (if appropriate):
# RUN pip install --no-cache-dir --no-binary :all: -r requirements.txt

# Create a directory for the default font if it doesn't exist
RUN mkdir -p ${LAMBDA_TASK_ROOT}/fonts

# Copy application code, assets, and fonts
# Ensure necessary directories and files are copied
COPY main.py ./
COPY lambda_src/ ./lambda_src/
COPY image_processor/ ./image_processor/
COPY utils/ ./utils/
COPY fonts/ ./fonts/

# Verify fonts were copied properly
RUN if [ -f "${LAMBDA_TASK_ROOT}/fonts/Roboto-Regular.ttf" ]; then \
    echo "Default font successfully bundled"; \
    else \
    echo "WARNING: Default font not found at ${LAMBDA_TASK_ROOT}/fonts/Roboto-Regular.ttf"; \
    ls -la ${LAMBDA_TASK_ROOT}/fonts/ || echo "fonts directory is empty or missing"; \
    fi

# Set the command to run when the container starts (Lambda handler)
CMD ["main.lambda_handler"] 