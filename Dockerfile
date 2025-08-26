# Use official Python 3.12.11 image
FROM python:3.12.11

# Set work directory
WORKDIR /app

# Copy requirements first (to leverage Docker layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose default uvicorn port
EXPOSE 8000

# Run uvicorn (expects `app` inside MainAPI.py)
CMD ["uvicorn", "MainAPI:app", "--host", "0.0.0.0", "--port", "8000"]
