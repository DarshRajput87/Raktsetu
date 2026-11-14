# RaktSetu API: FastAPI on uvicorn.
#
#   docker build -t raktsetu-api backend
#   docker run -p 8000:8000 -e MONGO_URI=... -e JWT_SECRET=... raktsetu-api
#
# One worker only: the API keeps its data structures in memory, so several
# workers would each hold a different copy of the stock and request queue.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"

# Hosts such as Render set $PORT; the proxy headers keep client IPs and https intact.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
