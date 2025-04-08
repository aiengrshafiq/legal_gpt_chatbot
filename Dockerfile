# Use a minimal base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Pre-install dependencies to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Optional: Environment variable to suppress Streamlit telemetry
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV PYTHONUNBUFFERED=1

# Expose Streamlit default port
EXPOSE 8501

# Streamlit entrypoint (use host networking)
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
