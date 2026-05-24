"""DigitalOcean Spaces (S3-compatible) storage wrapper. Falls back to local filesystem if not configured."""
import os
import shutil
from config import DO_SPACES_KEY, DO_SPACES_SECRET, DO_SPACES_ENDPOINT, DO_SPACES_BUCKET, PDFS_DIR

_HAS_SPACES = bool(DO_SPACES_KEY and DO_SPACES_SECRET)

if _HAS_SPACES:
    import boto3
    from botocore.config import Config as BotoConfig

    _client = boto3.client(
        "s3",
        endpoint_url=DO_SPACES_ENDPOINT,
        aws_access_key_id=DO_SPACES_KEY,
        aws_secret_access_key=DO_SPACES_SECRET,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # Set CORS policy on the bucket (one-time setup)
    try:
        _client.put_bucket_cors(
            Bucket=DO_SPACES_BUCKET,
            CORSConfiguration={
                "CORSRules": [{
                    "AllowedOrigins": ["*"],
                    "AllowedMethods": ["GET", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "MaxAgeSeconds": 3600,
                }]
            }
        )
        print("CORS policy set on Spaces bucket")
    except Exception as e:
        print(f"CORS setup note: {e}")

    def _key(pdf_id):
        return f"pdfs/{pdf_id}.pdf"

    def upload_file(local_path, pdf_id):
        object_key = _key(pdf_id)
        _client.upload_file(local_path, DO_SPACES_BUCKET, object_key, ExtraArgs={"ACL": "private"})
        print(f"Uploaded {local_path} to Spaces: {object_key}")
        return object_key

    def get_presigned_url(pdf_id, expiration=3600):
        return _client.generate_presigned_url(
            "get_object",
            Params={"Bucket": DO_SPACES_BUCKET, "Key": _key(pdf_id)},
            ExpiresIn=expiration,
        )

    def delete_file(pdf_id):
        object_key = _key(pdf_id)
        _client.delete_object(Bucket=DO_SPACES_BUCKET, Key=object_key)
        print(f"Deleted Spaces object: {object_key}")

    def get_local_path(pdf_id):
        return None

    def cleanup(pdf_id):
        pass

else:
    print("DO Spaces not configured — falling back to local filesystem")

    def upload_file(local_path, pdf_id):
        dest = os.path.join(PDFS_DIR, f"{pdf_id}.pdf")
        os.makedirs(PDFS_DIR, exist_ok=True)
        shutil.copy2(local_path, dest)
        return dest

    def get_presigned_url(pdf_id, expiration=3600):
        return None

    def delete_file(pdf_id):
        path = os.path.join(PDFS_DIR, f"{pdf_id}.pdf")
        if os.path.exists(path):
            os.remove(path)

    def get_local_path(pdf_id):
        path = os.path.join(PDFS_DIR, f"{pdf_id}.pdf")
        if os.path.exists(path):
            return path
        return None

    def cleanup(pdf_id):
        pass
