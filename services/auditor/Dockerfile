FROM python:3.12-slim
WORKDIR /app
COPY qc_core ./qc_core
COPY services/auditor/app.py ./app.py
ENV PORT=8103
ENV QC_DB=/app/auditor.db
EXPOSE 8103
CMD ["python", "app.py"]
