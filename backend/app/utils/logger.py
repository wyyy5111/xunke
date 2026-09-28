"""轻量日志。"""
import logging
import sys

from app.utils.redaction import redact_sensitive


class _SensitiveDataFilter(logging.Filter):
    """Redact credential-shaped values before any handler formats a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            record.msg = redact_sensitive(rendered)
            record.args = ()
        except Exception:
            # Logging must never break the request path or emit the original,
            # potentially sensitive object when formatting itself failed.
            record.msg = "日志内容无法安全格式化"
            record.args = ()
        return True

def _build():
    logger = logging.getLogger("xunkeflow")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    h.addFilter(_SensitiveDataFilter())
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(h)
    return logger

logger = _build()
