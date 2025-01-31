FROM python:3.12.7-slim

ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

# gRPC
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    git \
    gcc \
    g++ \
    make \
    cmake \
    unzip \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

#Go
RUN curl -fsSL https://go.dev/dl/go1.21.5.linux-$(dpkg --print-architecture).tar.gz | tar -xz -C /usr/local

#  Go в PATH
ENV PATH="/usr/local/go/bin:${PATH}"

# grpcurl из исходников
RUN go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest && \
    mv /root/go/bin/grpcurl /usr/local/bin/grpcurl && \
    chmod +x /usr/local/bin/grpcurl


WORKDIR $APP_HOME

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
