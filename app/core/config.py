import os

class Settings:
    APP_NAME = "Sentiric LTX-Video Expert Engine"
    APP_VERSION = "1.0.0"
    ENV = os.getenv("ENV", "production")
    DEVICE = os.getenv("LTX_SERVICE_DEVICE", "cuda")
    
    # ChatGPT'nin önerdiği repo ve model varyantı
    # Lightricks/LTX-Video reposunu kullanacağız
    MODEL_REPO_ID = os.getenv("LTX_MODEL_ID", "Lightricks/LTX-Video")
    
    # 6GB için en hafif varyant 'fp16' veya 'bf16'dır. 
    # Distilled modeller hızı 2x artırır.
    MODEL_REVISION = os.getenv("LTX_MODEL_REVISION", "main") 
    
    HTTP_PORT = int(os.getenv("LTX_SERVICE_HTTP_PORT", "16110"))
    GRPC_PORT = int(os.getenv("LTX_SERVICE_GRPC_PORT", "16111"))
    METRICS_PORT = int(os.getenv("LTX_SERVICE_METRICS_PORT", "16112"))

    # Storage & MQ
    S3_ENDPOINT = os.getenv("BUCKET_ENDPOINT_URL", "http://minio:9000")
    S3_REGION = os.getenv("BUCKET_REGION", "auto")
    S3_ACCESS_KEY = os.getenv("BUCKET_ACCESS_KEY_ID", "sentiric")
    S3_SECRET_KEY = os.getenv("BUCKET_SECRET_ACCESS_KEY", "sentiric-secret-key")
    S3_BUCKET = os.getenv("BUCKET_NAME", "sentiric")
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://sentiric:sentiric_pass@rabbitmq:5672/%2f")

    # mTLS Config (Aynı kalıyor)
    GRPC_TLS_CA_PATH = os.getenv("GRPC_TLS_CA_PATH", "/sentiric-certificates/certs/ca.crt")
    CERT_PATH = os.getenv("LTX_SERVICE_CERT_PATH", "/sentiric-certificates/certs/video-ltx-service-chain.crt")
    KEY_PATH = os.getenv("LTX_SERVICE_KEY_PATH", "/sentiric-certificates/certs/video-ltx-service.key")

settings = Settings()