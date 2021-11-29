FROM python:3.8

COPY src/ /app
RUN pip install -r /app/requirements.txt

CMD python /app/main.py