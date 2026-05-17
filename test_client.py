# test_client.py
import grpc, os, uuid, time
from sentiric.video.v1 import gateway_pb2, gateway_pb2_grpc

def run_test():
    base_cert_dir = "../sentiric-certificates/certs"
    with open(os.path.join(base_cert_dir, "ca.crt"), "rb") as f: ca = f.read()
    with open(os.path.join(base_cert_dir, "video-ltx-service-chain.crt"), "rb") as f: cert = f.read()
    with open(os.path.join(base_cert_dir, "video-ltx-service.key"), "rb") as f: key = f.read()
    
    creds = grpc.ssl_channel_credentials(ca, key, cert)
    with grpc.secure_channel("localhost:16111", creds) as channel:
        stub = gateway_pb2_grpc.VideoGatewayServiceStub(channel)
        
        prompt = "A cinematic shot of a futuristic robot walking through a cyberpunk city street, neon lights, rainy weather"
        print(f"🎬 Video Job Gönderiliyor: '{prompt}'")
        
        response = stub.SubmitVideoJob(gateway_pb2.SubmitVideoJobRequest(
            tenant_id="test-tenant",
            trace_id=str(uuid.uuid4()),
            prompt=prompt,
            preferred_model="ltx-video"
        ))
        
        if response.accepted:
            print(f"✅ KABUL EDİLDİ | Job ID: {response.job_id}")
            print(f"ℹ️ Mesaj: {response.status_message}")
        else:
            print("❌ REDDEDİLDİ")

if __name__ == "__main__":
    run_test()