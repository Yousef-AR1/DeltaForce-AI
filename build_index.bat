@echo off
call venv\Scripts\activate
python -m ingestion.indexer
pause
