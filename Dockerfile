FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and newer CMake
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install CMake ≥ 3.26 and add it to PATH explicitly
RUN curl -L https://github.com/Kitware/CMake/releases/download/v3.26.4/cmake-3.26.4-linux-x86_64.tar.gz -o cmake.tar.gz \
    && tar -xzf cmake.tar.gz -C /opt \
    && mv /opt/cmake-3.26.4-linux-x86_64 /opt/cmake \
    && ln -s /opt/cmake/bin/cmake /usr/bin/cmake \
    && cmake --version \
    && rm cmake.tar.gz

# Pre-install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Streamlit settings
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV PYTHONUNBUFFERED=1

EXPOSE 8501
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
