from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LogArchiveConfig:
    bucket: str
    prefix: str
    pack_path: Path
    storage_class: str = "STANDARD"

    @classmethod
    def from_runtime_config(cls, config: dict[str, Any]) -> "LogArchiveConfig":
        archive = config.get("log_archive", {})
        return cls(
            bucket=str(archive.get("bucket", "")).strip(),
            prefix=str(archive.get("prefix", "binance-bot/logs")).strip("/"),
            pack_path=Path(archive.get("pack_path", "logs/analysis_pack_full.txt")),
            storage_class=str(archive.get("storage_class", "STANDARD")).upper(),
        )

    def object_key(self) -> str:
        return "/".join(part for part in (self.prefix, self.pack_path.name) if part)


def build_analysis_pack(live_order_path: str | Path, event_path: str | Path, output_path: str | Path) -> Path:
    sources = (
        ("live_orders.csv", Path(live_order_path)),
        ("events.csv", Path(event_path)),
    )
    missing = [str(path) for _, path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required log file not found: {', '.join(missing)}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")

    try:
        with temporary.open("wb") as destination:
            for index, (label, source) in enumerate(sources):
                if index:
                    destination.write(b"\n")
                destination.write(f"### {label}\n".encode("utf-8"))
                with source.open("rb") as handle:
                    shutil.copyfileobj(handle, destination, length=1024 * 1024)
                destination.write(b"\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)

    return output


def upload_analysis_pack(config: LogArchiveConfig, live_order_path: str, event_path: str, s3_client=None) -> tuple[Path, str]:
    if not config.bucket:
        raise ValueError("S3 bucket is not configured. Set log_archive.bucket in config/live.yaml or pass --bucket.")

    pack_path = build_analysis_pack(live_order_path, event_path, config.pack_path)
    if s3_client is None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required. Install dependencies with: python3 -m pip install -r requirements.txt") from exc
        s3_client = boto3.client("s3")

    object_key = config.object_key()
    s3_client.upload_file(
        str(pack_path),
        config.bucket,
        object_key,
        ExtraArgs={
            "ContentType": "text/plain; charset=utf-8",
            "ServerSideEncryption": "AES256",
            "StorageClass": config.storage_class,
        },
    )
    return pack_path, object_key
