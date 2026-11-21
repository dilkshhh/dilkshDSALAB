FROM python:3.13-slim
WORKDIR /bot
COPY . .
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "-u", "/bot/bot.py"]
