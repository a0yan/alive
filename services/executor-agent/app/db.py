import asyncpg
import os

_pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        user = os.getenv("POSTGRES_USER", "alive")
        password = os.getenv("POSTGRES_PASSWORD", "alive")
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "alive")
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        _pool = await asyncpg.create_pool(dsn)
    return _pool


async def write_execution_result(
    workflow_id: str,
    anomaly_id: str,
    source: str,
    action_taken: str,
    diffs: list[str],
    exec_status: str,
) -> None:
    pool = await get_pool()
    diff_summary = "; ".join(diffs) if diffs else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE audit_log
            SET action_taken = $1,
                action_status = $2,
                resolved_at   = now()
            WHERE workflow_id = $3
            """,
            action_taken,
            exec_status,
            workflow_id,
        )
        # Insert execution detail row if no existing row to update
        updated = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_log WHERE workflow_id = $1", workflow_id
        )
        if not updated:
            await conn.execute(
                """
                INSERT INTO audit_log
                  (workflow_id, anomaly_id, source, anomaly_type,
                   action_taken, action_status, resolved_at)
                VALUES ($1, $2, $3, 'unknown', $4, $5, now())
                """,
                workflow_id, anomaly_id, source, action_taken, exec_status,
            )
