FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV USER=workshop
ENV HOME=/home/$USER
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 

# Create non-root user with uid 1000 (required by SciLifeLab Serve)
RUN useradd -m -u 1000 $USER

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Python packages
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Set working directory
WORKDIR $HOME/app

# Workshop content
COPY ./ $HOME/app

# .env placeholder
RUN echo '# Set OPENAI_API_KEY via docker run -e OPENAI_API_KEY="sk-..."' > $HOME/app/.env

# Start script (required by SciLifeLab Serve)
RUN chmod +x $HOME/app/start-script.sh

# Fix ownership for non-root user
RUN chown -R $USER:$USER $HOME

USER $USER
EXPOSE 8888

ENTRYPOINT ["./start-script.sh"]