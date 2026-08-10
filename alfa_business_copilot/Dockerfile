FROM python:3.12-slim

WORKDIR /app

# Отдельным слоем — кэшируется, пока requirements.txt не меняется
COPY otbor/requirements.txt otbor/requirements.txt
RUN pip install --no-cache-dir -r otbor/requirements.txt

COPY . .

EXPOSE 8000

# Один воркер: состояние диалоговых сессий (acquisition/insurance) живёт
# в памяти процесса (api/sessions.py) — несколько воркеров растащили бы
# сессии по разным процессам и ломали многошаговый диалог.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
