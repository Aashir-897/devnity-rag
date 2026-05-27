"""One-time cleanup — deletes ALL documents, vector data, and stored PDFs."""
import os
import shutil
import json
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
TEMP_DIR = os.path.join(BASE_DIR, "storage", "temp")
IMAGES_DIR = os.path.join(BASE_DIR, "storage", "images")
PDFS_DIR = os.path.join(BASE_DIR, "storage", "pdfs")
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_db")

DATABASE_URL = os.getenv("DATABASE_URL", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = "pdf_chunks"
DO_SPACES_KEY = os.getenv("DO_SPACES_KEY", "")
DO_SPACES_SECRET = os.getenv("DO_SPACES_SECRET", "")
DO_SPACES_BUCKET = os.getenv("DO_SPACES_BUCKET", "devnity-rag-storage")
DO_SPACES_REGION = os.getenv("DO_SPACES_REGION", "nyc3")
DO_SPACES_ENDPOINT = f"https://{DO_SPACES_REGION}.digitaloceanspaces.com"


def clean_mysql():
    """Delete all Document records from MySQL."""
    if not DATABASE_URL:
        print("  → No DATABASE_URL set, skipping MySQL")
        return
    try:
        import pymysql
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            database=os.getenv("DB_NAME", "devnity_rag"),
            port=int(os.getenv("DB_PORT", 3306)),
        )
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents")
            deleted = cur.rowcount
            conn.commit()
        conn.close()
        print(f"  ✓ Deleted {deleted} document records from MySQL")
    except Exception as e:
        print(f"  ✗ MySQL error: {e}")


def clean_qdrant():
    """Delete all points from the Qdrant collection."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
        if not client.collection_exists(QDRANT_COLLECTION):
            print("  → Qdrant collection does not exist, skipping")
            return
        count_before = client.count(collection_name=QDRANT_COLLECTION).count
        client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=models.Filter(
                must=[models.FieldCondition(
                    key="pdf_id",
                    match=models.MatchValue(value="")
                )]
            ),
            wait=True,
        )
        print(f"  ✓ Deleted {count_before} points from Qdrant collection '{QDRANT_COLLECTION}'")
    except ImportError:
        print("  → qdrant_client not available, skipping Qdrant")
    except Exception as e:
        print(f"  ✗ Qdrant error: {e}")


def clean_qdrant_all():
    """Delete ALL points from Qdrant by using a scroll+delete approach."""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
        if not client.collection_exists(QDRANT_COLLECTION):
            print("  → Qdrant collection does not exist, skipping")
            return
        count_before = client.count(collection_name=QDRANT_COLLECTION).count
        if count_before == 0:
            print("  → Qdrant collection already empty")
            return
        scroll = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        ids = [p.id for p in scroll[0]]
        if ids:
            client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=ids,
                wait=True,
            )
        print(f"  ✓ Deleted {count_before} points from Qdrant")
    except ImportError:
        print("  → qdrant_client not available, skipping Qdrant")
    except Exception as e:
        print(f"  ✗ Qdrant error: {e}")


def clean_do_spaces():
    """Delete all objects with prefix 'pdfs/' from DO Spaces."""
    if not DO_SPACES_KEY or not DO_SPACES_SECRET:
        print("  → DO Spaces credentials not set, skipping")
        return
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=DO_SPACES_ENDPOINT,
            aws_access_key_id=DO_SPACES_KEY,
            aws_secret_access_key=DO_SPACES_SECRET,
            region_name=DO_SPACES_REGION,
        )
        objects = client.list_objects_v2(Bucket=DO_SPACES_BUCKET, Prefix="pdfs/")
        if "Contents" not in objects:
            print("  → No objects found in DO Spaces")
            return
        keys = [{"Key": obj["Key"]} for obj in objects["Contents"]]
        client.delete_objects(Bucket=DO_SPACES_BUCKET, Delete={"Objects": keys})
        print(f"  ✓ Deleted {len(keys)} objects from DO Spaces bucket '{DO_SPACES_BUCKET}'")
    except ImportError:
        print("  → boto3 not available, skipping DO Spaces")
    except Exception as e:
        print(f"  ✗ DO Spaces error: {e}")


def clean_local_dirs():
    """Clear local storage directories."""
    for d in [TEMP_DIR, IMAGES_DIR, PDFS_DIR]:
        if os.path.exists(d):
            for fname in os.listdir(d):
                fpath = os.path.join(d, fname)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                    elif os.path.isdir(fpath):
                        shutil.rmtree(fpath)
                except Exception as e:
                    print(f"  ✗ Failed to remove {fpath}: {e}")
            print(f"  ✓ Cleared {d}")
        else:
            print(f"  → {d} does not exist, skipping")
    if os.path.exists(VECTOR_DB_DIR):
        shutil.rmtree(VECTOR_DB_DIR)
        print(f"  ✓ Removed {VECTOR_DB_DIR}")
    else:
        print(f"  → {VECTOR_DB_DIR} does not exist, skipping")


if __name__ == "__main__":
    print("=" * 50)
    print("  Devnity — Full Data Cleanup")
    print("=" * 50)

    print("\n[1/4] MySQL Database...")
    clean_mysql()

    print("\n[2/4] Qdrant Vector DB...")
    clean_qdrant_all()

    print("\n[3/4] DigitalOcean Spaces...")
    clean_do_spaces()

    print("\n[4/4] Local Storage...")
    clean_local_dirs()

    print("\n" + "=" * 50)
    print("  Cleanup complete!")
    print("=" * 50)
