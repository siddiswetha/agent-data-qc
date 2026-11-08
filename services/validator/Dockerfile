FROM python:3.12-slim
WORKDIR /app
COPY qc_core ./qc_core
COPY services/validator/app.py ./app.py
ENV PORT=8102
ENV QC_DB=/app/validator.db
EXPOSE 8102
CMD ["python", "app.py"]
