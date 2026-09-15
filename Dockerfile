FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Las credenciales se pasan como variables de entorno en tiempo de ejecución.
CMD ["python", "-u", "main.py"]
