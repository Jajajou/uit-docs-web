FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy project files
COPY pyproject.toml README.md ./
COPY api/ ./api/

# Install dependencies
RUN uv pip install --system -e .

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 8001

# Run with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
