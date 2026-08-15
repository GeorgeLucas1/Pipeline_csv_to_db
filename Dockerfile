FROM python:3.12-slim

WORKDIR /app

COPY ETL_PIPELINE/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ETL_PIPELINE/streamlit ./streamlit
COPY ETL_PIPELINE/eda ./eda

EXPOSE 8501

CMD ["streamlit", "run", "streamlit/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
