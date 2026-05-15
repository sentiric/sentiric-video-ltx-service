import logging
import sys
import os
from datetime import datetime
import structlog
from app.core.config import settings

def setup_logging():
    def suts_v4_formatter(logger, log_method, event_dict):
        event_dict["schema_v"] = "1.0.0"
        event_dict["ts"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        level = event_dict.pop("level", "info").upper()
        event_dict["severity"] = "FATAL" if level == "CRITICAL" else level
        
        event_dict["tenant_id"] = event_dict.get("tenant_id", "unknown")
        
        event_dict["resource"] = {
            "service.name": "video-ltx-service",
            "service.version": settings.APP_VERSION,
            "service.env": settings.ENV,
            "host.name": os.getenv("HOSTNAME", "unknown")
        }
        
        event_dict["trace_id"] = event_dict.get("trace_id", None)
        event_dict["span_id"] = event_dict.get("span_id", None)
        
        # Message handling
        event_msg = event_dict.pop("event", "LOG_EVENT")
        event_dict["event"] = event_dict.get("event_id", "LOG_EVENT")
        event_dict.pop("event_id", None)
        event_dict["message"] = event_msg
        
        return event_dict

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            suts_v4_formatter,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

logger = structlog.get_logger()
