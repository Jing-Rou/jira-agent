# Base image: The FROM python:3.13-slim line uses a minimal Python environment to keep the container lightweight. 
FROM python:3.13-slim

# PYTHONUNBUFFERED -> Makes Python print logs immediately instead of buffering them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \ 
    PIP_NO_CACHE_DIR=1

# The WORKDIR /app sets the working directory inside the container, ensuring that all subsequent commands run inside this folder.  
WORKDIR /app

# copy the context of the current directory into the /app directory inside the container.
COPY requirements.txt /tmp/requirements.txt
# Install dependencies inside container
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

COPY jiraAgent/ /app/

# Expose port 8000 for the Django application to be accessible from outside the container.
EXPOSE 8000
# command runs the Django application when the container starts.
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]