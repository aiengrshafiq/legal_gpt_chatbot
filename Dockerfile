# Use a minimal base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install build tools and curl to fetch latest CMake
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install CMake >= 3.5 from Kitware
RUN curl -L https://github.com/Kitware/CMake/releases/download/v3.26.4/cmake-3.26.4-linux-x86_64.tar.gz -o cmake.tar.gz \
    && tar -xzf cmake.tar.gz -C /opt \
    && mv /opt/cmake-3.26.4-linux-x86_64 /opt/cmake \
    && ln -sf /opt/cmake/bin/* /usr/local/bin/ \
    && cmake --version \
    && rm cmake.tar.gz

# Copy requirements and install camel-kenlm with custom cmake args
COPY requirements.txt .
RUN pip install --upgrade pip \
 && CMAKE_ARGS="-DCMAKE_POLICY_VERSION=3.5" pip install camel-kenlm \
 && pip install --no-deps -r requirements.txt

# Copy application code
COPY . .

# Streamlit and Python config
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV PYTHONUNBUFFERED=1

# Expose default Streamlit port
EXPOSE 8501

# Start Streamlit
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
