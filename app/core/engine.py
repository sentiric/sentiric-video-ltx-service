import torch
import gc
import asyncio
import os
import uuid
import structlog
from diffusers import LTXPipeline
from diffusers.utils import export_to_video
from app.core.config import settings
from app.core.integrations import S3Uploader, RMQPublisher

logger = structlog.get_logger()

class SmartMemoryManager:
    def __init__(self, device: str, threshold_mb: int = 4500):
        self.device = device
        self.threshold_mb = threshold_mb

    def check_and_clear(self):
        if self.device != "cuda":
            return
        allocated = torch.cuda.memory_allocated() / (1024 * 1024)
        # Sadece %85 dolulukta temizle (Performans için)
        if allocated > self.threshold_mb:
            gc.collect()
            torch.cuda.empty_cache()
            logger.info(f"VRAM Cleared ({int(allocated)} MB)", event_id="VRAM_CLEARED")

class LTXEngine:
    def __init__(self):
        self.pipe = None
        self.memory_manager = SmartMemoryManager(settings.DEVICE)
        self.s3_uploader = S3Uploader()
        self.rmq_publisher = RMQPublisher()

    def initialize(self):
        logger.info(f"Loading LTX-Video from {settings.MODEL_REPO_ID}", event_id="MODEL_INIT")
        try:
            self.pipe = LTXPipeline.from_pretrained(
                settings.MODEL_REPO_ID, 
                torch_dtype=torch.bfloat16
            ).to(settings.DEVICE)
            
            # [ARCH-COMPLIANCE]: 6GB VRAM Optimization
            self.pipe.enable_model_cpu_offload() # RAM/VRAM offloading
            if hasattr(self.pipe, 'enable_attention_slicing'):
                self.pipe.enable_attention_slicing()
                
            logger.info("LTX-Video Ready.", event_id="MODEL_READY")
        except Exception as e:
            logger.error(f"Model Load Fail: {e}", event_id="MODEL_INIT_FAIL")

    async def generate_and_upload(self, prompt: str, job_id: str, trace_id: str, tenant_id: str):
        logger.info(f"Starting rendering for job: {job_id}", event_id="VIDEO_RENDER_START", trace_id=trace_id, tenant_id=tenant_id)
        
        try:
            # CPU bloklamasını asenkron taska devret
            frames = await asyncio.to_thread(self._render_sync, prompt)
            
            temp_path = f"/tmp/{job_id}.mp4"
            export_to_video(frames, temp_path, fps=24)
            
            # Upload S3
            s3_uri = await asyncio.to_thread(self.s3_uploader.upload_file, temp_path, job_id, trace_id)
            os.remove(temp_path)
            
            # Publish Event
            await self.rmq_publisher.publish_event(
                event_type="media.generation.completed",
                trace_id=trace_id,
                tenant_id=tenant_id,
                job_id=job_id,
                success=True,
                result_uri=s3_uri
            )
            
        except Exception as e:
            logger.error(f"Render failed: {e}", event_id="VIDEO_RENDER_FAIL", trace_id=trace_id)
            await self.rmq_publisher.publish_event(
                event_type="media.generation.failed",
                trace_id=trace_id,
                tenant_id=tenant_id,
                job_id=job_id,
                success=False,
                error_msg=str(e)
            )
        finally:
            self.memory_manager.check_and_clear()

    def _render_sync(self, prompt: str):
        # 16 frame, kısa bir video (hızlı test ve düşük VRAM için)
        video = self.pipe(
            prompt=prompt,
            num_frames=17, 
            num_inference_steps=20,
            height=256,
            width=256,
            output_type="np"
        ).frames[0]
        return video

ltx_engine = LTXEngine()
