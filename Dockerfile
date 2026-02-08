FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data static
# Ensure static directory has content so it doesn't crash if logic depends on it
RUN touch static/.gitkeep
EXPOSE 8000
CMD ["python", "app.py"]
