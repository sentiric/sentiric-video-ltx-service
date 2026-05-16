import boto3, aio_pika, structlog
from botocore.config import Config
from app.core.config import settings
from sentiric.event.v1 import event_pb2
from google.protobuf.timestamp_pb2 import Timestamp

logger = structlog.get_logger()

class S3Uploader:
    def __init__(self):
        self.s3 = boto3.client('s3', endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY, config=Config(signature_version='s3v4'))
    def upload_file(self, file_path, job_id, trace_id):
        obj_name = f"media/{job_id}.mp4"
        self.s3.upload_file(file_path, settings.S3_BUCKET, obj_name)
        s3_uri = f"s3://{settings.S3_BUCKET}/{obj_name}"
        logger.info("File uploaded", event_id="S3_UPLOAD_SUCCESS", trace_id=trace_id, uri=s3_uri)
        return s3_uri

class RMQPublisher:
    async def publish_event(self, event_type, trace_id, tenant_id, job_id, success, result_uri="", error_msg=""):
        try:
            conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            async with conn:
                ch = await conn.channel()
                ex = await ch.declare_exchange("sentiric_events", aio_pika.ExchangeType.TOPIC, durable=True)
                ts = Timestamp(); ts.GetCurrentTime()
                evt = event_pb2.MediaGenerationCompletedEvent(event_type=event_type, trace_id=trace_id, job_id=job_id, tenant_id=tenant_id, media_type="video", success=success, result_uri=result_uri, error_message=error_msg, timestamp=ts)
                msg = aio_pika.Message(body=evt.SerializeToString(), content_type="application/protobuf", delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
                await ex.publish(msg, routing_key=event_type)
        except Exception as e:
            logger.error(f"RMQ Fail: {e}", event_id="RMQ_PUBLISH_FAIL", trace_id=trace_id)
