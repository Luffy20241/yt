FROM 5hojib/vegapunk:latest

WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# Copy your application files into the container
COPY . .

# Copy cookies.txt into the container
COPY cookies.txt /app/cookies.txt

# Set the default command to run your app (adjust this based on your app's startup script)
CMD ["bash", "start.sh"]
