import boto3
import aio_pika
import time
from botocore.config import Config
from app.core.config import settings
from sentiric.event.v1 import event_pb2
from google.protobuf.timestamp_pb2 import Timestamp
import structlog

logger = structlog.get_logger()

class S3Uploader:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(signature_version='s3v4')
        )

    def upload_file(self, file_path: str, job_id: str, trace_id: str) -> str:
        object_name = f"videos/{job_id}.mp4"
        try:
            self.s3.upload_file(file_path, settings.S3_BUCKET, object_name)
            s3_uri = f"s3://{settings.S3_BUCKET}/{object_name}"
            logger.info("File uploaded to S3", event_id="S3_UPLOAD_SUCCESS", trace_id=trace_id, uri=s3_uri)
            return s3_uri
        except Exception as e:
            logger.error(f"S3 Upload failed: {e}", event_id="S3_UPLOAD_FAIL", trace_id=trace_id)
            raise e

class RMQPublisher:
    async def publish_event(self, event_type: str, trace_id: str, tenant_id: str, job_id: str, success: bool, result_uri: str = "", error_msg: str = ""):
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            async with connection:
                channel = await connection.channel()
                exchange = await channel.declare_exchange("sentiric_events", aio_pika.ExchangeType.TOPIC, durable=True)
                
                ts = Timestamp()
                ts.GetCurrentTime()

                event = event_pb2.MediaGenerationCompletedEvent(
                    event_type=event_type,
                    trace_id=trace_id,
                    job_id=job_id,
                    tenant_id=tenant_id,
                    media_type="video",
                    success=success,
                    result_uri=result_uri,
                    error_message=error_msg,
                    timestamp=ts
                )
                
                message = aio_pika.Message(
                    body=event.SerializeToString(),
                    content_type="application/protobuf",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                )

                await exchange.publish(message, routing_key=event_type)
                logger.info("Event published to RMQ", event_id="RMQ_PUBLISH_SUCCESS", trace_id=trace_id, rmq_event=event_type)
        except Exception as e:
            logger.error(f"RMQ Publish failed: {e}", event_id="RMQ_PUBLISH_FAIL", trace_id=trace_id)
