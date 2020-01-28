FROM python:3.7-alpine
WORKDIR /
RUN apk add --no-cache gcc make musl-dev linux-headers bash
COPY requirements.txt ./
RUN pip3 install -r requirements.txt
COPY . .
CMD ["python3", "./server.py"]
