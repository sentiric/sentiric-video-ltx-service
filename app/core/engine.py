# [ARCH-COMPLIANCE] SOP-01: Eksiksiz Teslimat
import torch, gc, asyncio, os, uuid, structlog
from diffusers import DiffusionPipeline 
from diffusers.utils import export_to_video
from app.core.config import settings
from app.core.integrations import S3Uploader, RMQPublisher

logger = structlog.get_logger()

class LTXEngine:
    def __init__(self):
        self.pipe = None
        self.semaphore = asyncio.Semaphore(1)
        self.s3_uploader = S3Uploader()
        self.rmq_publisher = RMQPublisher()

    def initialize(self):
        logger.info(f"Loading LTX-Video from {settings.MODEL_REPO_ID}", event_id="MODEL_INIT")
        try:
            # --- [KRİTİK DÜZELTME] ---
            # device_map="auto" bazı LTX versiyonlarında hata veriyordu.
            # 6GB kartlarda en garantili yol: Önce modeli yükleyip sonra offload etmek.
            self.pipe = DiffusionPipeline.from_pretrained(
                settings.MODEL_REPO_ID,
                torch_dtype=torch.bfloat16, # RTX 3060 için BF16 en iyisidir
                low_cpu_mem_usage=True
            )

            if settings.DEVICE == "cuda":
                # [6GB VRAM CAN KURTARAN]: sequential_cpu_offload
                # Modeli GPU'ya doldurmaz, sadece o an hesaplanan katmanı (layer) GPU'ya alır.
                # Bu sayede hem RAM hem VRAM kullanımı minimize edilir.
                self.pipe.enable_sequential_cpu_offload()
                
                # Diğer bellek tasarrufu teknikleri
                if hasattr(self.pipe, "vae"):
                    self.pipe.vae.enable_slicing()
                    self.pipe.vae.enable_tiling()
                
            logger.info(f"Model Ready: {type(self.pipe).__name__}", event_id="MODEL_READY")
        except Exception as e:
            # Hata detayını loglayalım
            logger.error(f"Model Load Fail: {str(e)}", event_id="MODEL_INIT_FAIL")
            self.pipe = None # Hata durumunda pipe'ı None yap

    async def generate_and_upload(self, prompt: str, job_id: str, trace_id: str, tenant_id: str):
        if self.pipe is None:
            err_msg = "Model was not initialized correctly."
            logger.error(err_msg, event_id="VIDEO_RENDER_FAIL", trace_id=trace_id)
            await self.rmq_publisher.publish_event("media.generation.failed", trace_id, tenant_id, job_id, False, "", err_msg)
            return

        async with self.semaphore:
            logger.info(f"Render starting: {prompt[:50]}...", event_id="VIDEO_RENDER_START", trace_id=trace_id)
            try:
                frames = await asyncio.to_thread(self._render_sync, prompt)
                
                temp_path = f"/tmp/{job_id}.mp4"
                export_to_video(frames, temp_path, fps=24)
                
                s3_uri = await asyncio.to_thread(self.s3_uploader.upload_file, temp_path, job_id, trace_id)
                if os.path.exists(temp_path): os.remove(temp_path)
                
                await self.rmq_publisher.publish_event(
                    "media.generation.completed", trace_id, tenant_id, job_id, True, s3_uri
                )
            except Exception as e:
                logger.error(f"Render failed: {str(e)}", event_id="VIDEO_RENDER_FAIL", trace_id=trace_id)
                await self.rmq_publisher.publish_event(
                    "media.generation.failed", trace_id, tenant_id, job_id, False, "", str(e)
                )
            finally:
                if settings.DEVICE == "cuda":
                    gc.collect()
                    torch.cuda.empty_cache()

    def _render_sync(self, prompt: str):
        # 6GB VRAM / RTX 3060 için en stabil çözünürlük ve kare sayısı
        # num_frames = (8 * N) + 1 olmalı. 17 frame yaklaşık 0.7 saniyedir.
        with torch.inference_mode():
            output = self.pipe(
                prompt=prompt,
                num_frames=17, 
                num_inference_steps=20, # Hızlı sonuç için 20 step
                width=320,
                height=320,
                guidance_scale=3.0,
                output_type="np"
            )
        return output.frames[0]

ltx_engine = LTXEngine()