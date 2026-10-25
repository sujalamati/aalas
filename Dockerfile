FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Tectonic downloads LaTeX packages as needed; in production, sandbox compilation separately.
RUN curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.f/tectonic/install.sh | sh \
    && mv /root/.tectonic/bin/tectonic /usr/local/bin/tectonic
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /app/generated
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]