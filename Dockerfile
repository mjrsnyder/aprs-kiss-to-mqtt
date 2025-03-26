# Use an official Python runtime as the base image
FROM python:3.13-slim

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies specified in the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

CMD ["python", "-m", "src.main"]