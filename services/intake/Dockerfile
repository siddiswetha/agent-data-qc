FROM python:3.12-slim
WORKDIR /app
COPY qc_core ./qc_core
COPY services/intake/app.py ./app.py
ENV PORT=8101
ENV QC_DB=/app/intake.db
EXPOSE 8101
CMD ["python", "app.py"]
