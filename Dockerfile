FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd -r mcpuser && useradd -r -g mcpuser -d /app mcpuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=mcpuser:mcpuser server.py euipo.py core.py similarity.py ./
USER mcpuser
EXPOSE 8000
CMD ["python", "server.py"]
