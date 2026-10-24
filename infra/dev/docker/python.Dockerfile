FROM python:3.11-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY context-public/repository/requirements.txt context-public/repository/requirements-test.txt context-public/repository/requirements-whatsapp.txt ./
RUN pip install --no-cache-dir -r requirements-test.txt
COPY context-public/repository/ ./
COPY docker/verify_environment.py /opt/bago/verify_environment.py
RUN useradd --create-home --uid 10001 developer && mkdir -p /data /results && chown -R developer:developer /workspace /data /results
USER developer
ENV HOME=/home/developer LOCALAPPDATA=/data/localapp BAGO_CONVERSATION_DB_PATH=/data/conversations/library.sqlite3
CMD ["python", "/opt/bago/verify_environment.py"]
