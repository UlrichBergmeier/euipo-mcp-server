FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd -r -g 10001 mcpuser && useradd -r -u 10001 -g mcpuser -d /app mcpuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=mcpuser:mcpuser server.py euipo.py core.py similarity.py auth0_verifier.py goods_services.py ./
USER mcpuser
EXPOSE 8000
CMD ["python", "server.py"]
