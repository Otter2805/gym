 # Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your requirements file first (for faster builds)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your bot's code
COPY . .

# The command to start your bot
CMD ["python", "main.py"]
