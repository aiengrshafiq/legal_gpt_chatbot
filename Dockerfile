# Use a minimal base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system build tools and updated CMake
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -L https://github.com/Kitware/CMake/releases/download/v3.26.4/cmake-3.26.4-linux-x86_64.tar.gz -o cmake.tar.gz \
    && tar -zxvf cmake.tar.gz --strip-components=1 -C /usr/local \
    && rm cmake.tar.gz

# Pre-install Python dependencies separately for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Optional: Streamlit telemetry off
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV PYTHONUNBUFFERED=1

# Expose Streamlit's default port
EXPOSE 8501

# Entrypoint for Streamlit app
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
