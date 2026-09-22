import os
import json
import asyncio
from prisma import Prisma

DATA_DIR = os.environ.get("DATA_DIR", "/data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

async def get_or_compute(source_hash: str, feature_type: str, compute_fn, is_large_payload=False):
    """
    Fetches feature from cache or computes it.
    - feature_type: transcript | frames | diarization | ocr | embedding
    - compute_fn: sync or async function returning the payload
    - is_large_payload: if True, saves payload to disk and stores path in DB.
    """
    if not source_hash:
        return await _run_compute(compute_fn)

    # Use the proxy client to avoid Prisma lifecycle issues
    from database.prisma_client import get_prisma
    db = await get_prisma()
    
    # Try fetching from DB
    cached = await db.featurecache.find_unique(
        where={
            "source_hash_feature_type": {
                "source_hash": source_hash,
                "feature_type": feature_type
            }
        }
    )

    if cached:
        print(f"   [CACHE HIT] {feature_type} for {source_hash[:8]}...", flush=True)
        if is_large_payload:
            path = cached.payload
            if os.path.exists(path):
                from database.prisma_client import disconnect_prisma
                await disconnect_prisma()
                if path.endswith(".npy"):
                    import numpy as np
                    return np.load(path)
                else:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
            else:
                print(f"   [CACHE MISS] {feature_type} path {path} not found on disk, recomputing...", flush=True)
                # Fall through to recompute
        else:
            from database.prisma_client import disconnect_prisma
            await disconnect_prisma()
            return json.loads(cached.payload)

    print(f"   [CACHE MISS] {feature_type} for {source_hash[:8]}...", flush=True)
    payload = await _run_compute(compute_fn)

    # Make sure we got something serializable and useful before caching
    if payload is None:
        return payload

    try:
        if is_large_payload:
            os.makedirs(os.path.join(CACHE_DIR, source_hash), exist_ok=True)
            import numpy as np
            if isinstance(payload, np.ndarray):
                path = os.path.join(CACHE_DIR, source_hash, f"{feature_type}.npy")
                np.save(path, payload)
            else:
                path = os.path.join(CACHE_DIR, source_hash, f"{feature_type}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
            db_payload = path
        else:
            db_payload = json.dumps(payload)
            
        await db.featurecache.upsert(
            where={
                "source_hash_feature_type": {
                    "source_hash": source_hash,
                    "feature_type": feature_type
                }
            },
            data={
                "create": {
                    "source_hash": source_hash,
                    "feature_type": feature_type,
                    "payload": db_payload
                },
                "update": {
                    "payload": db_payload
                }
            }
        )
    except Exception as e:
        print(f"   [CACHE WARN] Failed to cache {feature_type}: {e}", flush=True)
    finally:
        from database.prisma_client import disconnect_prisma
        await disconnect_prisma()

    return payload

async def _run_compute(compute_fn):
    if asyncio.iscoroutinefunction(compute_fn):
        return await compute_fn()
    else:
        return compute_fn()
