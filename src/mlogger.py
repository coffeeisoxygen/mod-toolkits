# --- ADVANCED LOGURU RECIPES (DISABLED, UNCOMMENT TO USE) ---
#
# # 1. Dynamic filter per handler (e.g. only WARNING and above)
# def warn_only_filter(record):
#     return record["level"].no >= loguru_logger.level("WARNING").no
# # Example usage:
# # loguru_logger.add(sys.stderr, filter=warn_only_filter, level="DEBUG")
#
# # 2. Custom formatter with dynamic color
# # def color_formatter(record):
# #     return f"<cyan>{record['name']}</cyan>: {record['message']}"
# # loguru_logger.add(sys.stderr, format=color_formatter)
#
# # 3. Capture warnings as loguru WARNING
# # import warnings
# # showwarning_ = warnings.showwarning
# # def showwarning(message, *args, **kwargs):
# #     loguru_logger.opt(depth=2).warning(message)
# #     showwarning_(message, *args, **kwargs)
# # warnings.showwarning = showwarning
#
# # 4. Custom log level
# # from functools import partialmethod
# # loguru_logger.level("SECURITY", no=35, color="<red>")
# # loguru_logger.__class__.security = partialmethod(loguru_logger.__class__.log, "SECURITY")
# # loguru_logger.security("This is a security log!")
#
# # 5. Split log per task using bind and filter
# # loguru_logger.add("file_A.log", filter=lambda r: r["extra"].get("task") == "A")
# # loguru_logger.add("file_B.log", filter=lambda r: r["extra"].get("task") == "B")
# # loguru_logger.bind(task="A").info("Log for task A")
# # loguru_logger.bind(task="B").info("Log for task B")
#
# # 6. Custom serialization (if needed)
# # import json
# # def serialize(record):
# #     subset = {"timestamp": record["time"].timestamp(), "message": record["message"]}
# #     return json.dumps(subset)
# # def sink(message):
# #     serialized = serialize(message.record)
# #     print(serialized)
# # loguru_logger.add(sink)
#
# # 7. Patch logger to always colorize
# # from functools import partial
# # logger_colored = loguru_logger.opt(colors=True)
# # logger_colored.opt = partial(loguru_logger.opt, colors=True)
# # logger_colored.info("It <green>works</>!")
#
# --- END ADVANCED LOGURU RECIPES ---
"""Custom Loguru Logger Setup (OOP Refactor).

==========================================

Modul ini menyederhanakan integrasi Loguru ke dalam aplikasi Python,
baik synchronous maupun asynchronous. Dirancang agar mudah di-setup,
siap pakai di aplikasi FastAPI, testing (pytest), maupun script CLI.

Fitur:
- Logging ke terminal & file (rotasi size + daily)
- Intercept logging bawaan Python (`logging`, `uvicorn`, dll)
- Decorator `@timer`, `@logger_wraps`, context `log_block`, `LogContext`
- Stacktrace logging untuk debugging mendalam
- Siap pakai di `conftest.py`, support format simple/full
- Support unhandled exception handler untuk sync & async
- Support default `logger.bind()` context

Author: Maki & ChatGPT
"""

import asyncio
import functools
import inspect
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, ParamSpec, TypeVar

from loguru import logger as loguru_logger

Level = Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


@dataclass
class LogConfig:
    level: Level = "INFO"
    to_terminal: bool = True
    to_file: bool = False
    serialize: bool = False
    diagnose: bool = False
    enqueue: bool = True
    log_path: str = "logs"
    name_prefix: str = "app"
    size_mb: int = 10
    retention_days: int = 7
    override_stdout: bool = False
    format_style: Literal["simple", "full"] = "simple"
    bind_context: dict[str, Any] | None = None
    enable_exception_hooks: bool = True


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Add this line to intercept all standard logging
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


class LoggerManager:
    def __init__(self, config: LogConfig):
        self.config = config
        self.FORMAT_SIMPLE = "<level>{level}</level>: <magenta>{name}:{function}:{line}</magenta> | {message} | {extra}"
        self.FORMAT_FULL = (
            "<level>{level}</level>: {time:YYYY-MM-DD HH:mm:ss} | "
            "<cyan>{process.name}:{thread.name}</cyan> | "
            "<magenta>{name}:{function}:{line}</magenta> | "
            "<level>{message}</level> | {extra}"
        )

    def setup(self):
        loguru_logger.level("INFO", color="<cyan>")
        loguru_logger.remove()
        Path(self.config.log_path).mkdir(parents=True, exist_ok=True)

        logger_patched = loguru_logger
        if self.config.bind_context:
            logger_patched = logger_patched.bind(**self.config.bind_context)
        logger_patched = logger_patched.patch(self._filter_sensitive)

        if self.config.to_terminal:
            logger_patched.add(
                sink=sys.stderr,
                level=self.config.level,
                format=self._get_format(),
                colorize=True,
                backtrace=True,
                diagnose=self.config.diagnose,
                enqueue=self.config.enqueue,
                serialize=self.config.serialize,
            )
        if self.config.to_file:
            for level in ("INFO", "ERROR"):
                logger_patched.add(
                    sink=f"{self.config.log_path}/{self.config.name_prefix}_{level.lower()}.log",
                    level=level,
                    format=self.FORMAT_FULL,
                    diagnose=self.config.diagnose,
                    backtrace=True,
                    enqueue=self.config.enqueue,
                    serialize=self.config.serialize,
                    rotation=f"{self.config.size_mb} MB 00:00",
                    retention=f"{self.config.retention_days} days",
                    opener=LoggerManager._opener,
                )
        if self.config.override_stdout:
            self._patch_stdout()
        if self.config.enable_exception_hooks:
            self._setup_exception_hooks()
        logger_patched.info("Logging initialized")

    def _get_format(self) -> str:
        return (
            self.FORMAT_SIMPLE
            if self.config.format_style == "simple"
            else self.FORMAT_FULL
        )

    @staticmethod
    def _filter_sensitive(record: Any) -> None:
        msg = str(record["message"]).lower()
        if any(
            word in msg
            for word in ["password", "token", "secret", "apikey", "authorization"]
        ):
            record["message"] = "[REDACTED]"
        return None

    # _patch_logging removed: use Loguru's recommended InterceptHandler directly if needed

    def _patch_stdout(self) -> None:
        class StreamToLogger:
            def __init__(self, level: Level = "INFO"):
                self.level = level

            def write(self, buffer: str) -> None:
                for line in buffer.rstrip().splitlines():
                    loguru_logger.log(self.level, line.rstrip())

            def flush(self) -> None:
                pass

        sys.stdout = StreamToLogger("INFO")
        sys.stderr = StreamToLogger("ERROR")

    def _setup_exception_hooks(self) -> None:
        def global_exception_hook(
            exc_type: type, exc_value: Exception, exc_traceback: TracebackType
        ):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            loguru_logger.opt(exception=exc_value).critical("Unhandled exception")

        def handle_async_exception(
            loop: asyncio.AbstractEventLoop,
            context: dict[str, Any],
        ):
            msg = context.get("message", "Async exception")
            exception = context.get("exception")
            loguru_logger.opt(exception=exception).error(f"Async exception: {msg}")

        sys.excepthook = global_exception_hook
        try:
            loop = asyncio.get_event_loop()
            loop.set_exception_handler(handle_async_exception)
        except RuntimeError:
            pass

    # patch_uvicorn_loggers and patch_loggers removed: use Loguru's InterceptHandler if needed

    # _Rotator removed: use Loguru's built-in rotation string (e.g. '10 MB 00:00')

    @staticmethod
    def _opener(file: str, flags: int) -> int:
        return os.open(file, flags, 0o600)

    @staticmethod
    def logger_wraps(
        *, entry: bool = True, exit: bool = True, level: Level = "DEBUG"
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: Log entry, exit, arguments, and result of a function.

        Use case:
            - Tracing eksekusi fungsi (debugging, audit, monitoring)
            - Melihat argumen dan hasil return setiap pemanggilan fungsi

        Example:
            >>> @LoggerManager.logger_wraps(level="INFO")
            ... def foo(x, y):
            ...     return x + y
            >>> foo(1, 2)
            # INFO: → foo | args=(1, 2), kwargs={}
            # INFO: ← foo | result=3
        """
        function_params = ParamSpec("function_params")
        function_return = TypeVar("function_return")

        def wrapper(
            func: Callable[function_params, function_return],
        ) -> Callable[function_params, function_return]:
            @functools.wraps(func)
            def wrapped(
                *args: function_params.args, **kwargs: function_params.kwargs
            ) -> function_return:
                if entry:
                    loguru_logger.log(
                        level, f"→ {func.__name__} | args={args}, kwargs={kwargs}"
                    )
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    loguru_logger.exception(
                        f"Exception in function {func.__name__}: {e}"
                    )
                    raise
                if exit:
                    loguru_logger.log(level, f"← {func.__name__} | result={result}")
                return result

            return wrapped

        return wrapper

    @staticmethod
    def timer(
        operation: str | None = None, level: Level = "INFO"
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: Log waktu mulai, selesai, dan durasi eksekusi fungsi.

        Use case:
            - Profiling performa fungsi
            - Menemukan bottleneck

        Example:
            >>> @LoggerManager.timer(level="INFO")
            ... def process(): ...
            >>> process()
            # INFO: [process] Starting...
            # INFO: [process] Done in 0.123s
        """
        timer_params = ParamSpec("timer_params")
        timer_return = TypeVar("timer_return")

        def decorator(
            func: Callable[timer_params, timer_return],
        ) -> Callable[timer_params, timer_return]:
            @functools.wraps(func)
            def wrapper(
                *args: timer_params.args, **kwargs: timer_params.kwargs
            ) -> timer_return:
                op = operation or func.__name__

                start = time.perf_counter()
                try:
                    loguru_logger.log(level, f"[{op}] Starting...")
                    result = func(*args, **kwargs)
                    loguru_logger.log(
                        level, f"[{op}] Done in {time.perf_counter() - start:.3f}s"
                    )
                except Exception as e:
                    loguru_logger.exception(f"[{op}] Failed: {e}")
                    raise
                return result

            return wrapper

        return decorator

    @staticmethod
    def log_block(
        operation: str, level: Level = "INFO"
    ) -> AbstractContextManager[None]:
        """Context manager: Log waktu mulai, selesai, dan durasi blok kode."""

        @contextmanager
        def _block() -> Iterator[None]:
            start = time.perf_counter()
            loguru_logger.log(level, f"[{operation}] Starting...")
            try:
                yield
                loguru_logger.log(
                    level, f"[{operation}] Done in {time.perf_counter() - start:.3f}s"
                )
            except Exception as e:
                loguru_logger.exception(f"[{operation}] Failed: {e}")
                raise

        return _block()

    class LogContext:
        """Context manager (OOP): Log waktu mulai, selesai, dan durasi blok kode, bisa di-extend.

        Use case:
            - Profiling/monitoring blok kode dengan kebutuhan OOP atau custom state
            - Extend class ini untuk menambah perilaku logging

        Example:
            >>> with LoggerManager.LogContext("proses data"):
            ...     ...
            # INFO: [proses data] Starting...
            # INFO: [proses data] Done in 0.789s
        """

        def __init__(self, operation: str, level: Level = "INFO"):
            self.operation = operation
            self.level = level
            self.start_time = None
            self._time = time

        def __enter__(self):
            self.start_time = self._time.perf_counter()
            loguru_logger.log(self.level, f"[{self.operation}] Starting...")
            return self

        def __exit__(
            self,
            exc_type: type | None,
            exc_val: Exception | None,
            exc_tb: TracebackType | None,
        ) -> None:
            if self.start_time is not None:
                duration = self._time.perf_counter() - self.start_time
            else:
                duration = 0.0
            if exc_type:
                loguru_logger.error(
                    f"[{self.operation}] Failed after {duration:.3f}s: {exc_val}"
                )
            else:
                loguru_logger.log(
                    self.level, f"[{self.operation}] Done in {duration:.3f}s"
                )


logger = loguru_logger


def caller_info():
    """Return caller's filename, function name, and line number for logging context."""
    frame = inspect.currentframe()
    # Go back two frames: caller_info -> log_exception_with_caller -> actual caller
    if (
        frame is not None
        and frame.f_back is not None
        and frame.f_back.f_back is not None
    ):
        outer_frame = frame.f_back.f_back
        info = inspect.getframeinfo(outer_frame)
        return f"{info.filename}:{info.function}:{info.lineno}"
    return "unknown"


def log_exception_with_caller(exc: Exception):
    logger.bind(caller=caller_info()).opt(exception=exc).error(
        "Unhandled exception in service"
    )


def log_error(exc: Exception, msg: str = ""):
    """Log error with exception traceback.

    Example:
        >>> from utils.mlogger import log_error
        >>> try:
        ...     1 / 0
        ... except Exception as e:
        ...     log_error(e, "Division error")
    """
    loguru_logger.opt(exception=exc).error(msg or str(exc))


def request_id() -> str:
    """Generate a unique request ID (UUID).

    Example:
        >>> from utils.mlogger import request_id
        >>> rid = request_id()
        >>> print(rid)
    """
    return str(uuid.uuid4())


__all__ = [
    "LogConfig",
    "LoggerManager",
    "log_error",
    "logger",
    "request_id",
]
