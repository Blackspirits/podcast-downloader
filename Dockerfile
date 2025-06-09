# Use a modern Python version that matches your environment
FROM python:3.10-slim as base

# Set the working directory in the container
WORKDIR /app

# Prevent Python from writing .pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure Python output is sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED 1

# --- Dependency Installation Stage ---
# First, install pipenv itself
RUN pip install pipenv

# Copy only the files needed to install dependencies
# This allows Docker to cache this layer if the dependency files don't change
COPY Pipfile Pipfile.lock /app/

# Install all project dependencies (including development ones) from the lock file
# The --system flag installs them into the system's site-packages, which is
# standard practice for Docker, avoiding a nested virtual environment.
RUN pipenv install --dev --system --deploy --ignore-pipfile


# --- Application Code Stage ---
# Now copy the rest of your application code
COPY podcast_downloader /app/podcast_downloader
COPY tests /app/tests
COPY setup.py /app/
COPY version /app/
COPY README.md /app/

# The default command to run when the container starts
# This first checks formatting with Black and then runs all tests
CMD ["sh", "-c", "black . --check && python -m unittest discover -s tests -p '*_test.py'"]
