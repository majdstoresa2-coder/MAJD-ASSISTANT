#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MAJD ASSISTANT
MAJD-ASSISTANT-AUTONOMOUS-RUNTIME-02.py
============================================================

AUTONOMOUS RUNTIME / SELF-MAINTENANCE / SELF-DEVELOPMENT LAYER

Version: 1.1.0

CHAIN
-----
01 CORE
    ↓
02 AUTONOMOUS RUNTIME
    ↓
03 AI ENGINE
    ↓
OLLAMA / llama3.2:3b
    ↓
GENERATE / REPAIR
    ↓
VALIDATE
    ↓
ACTIVATE OR ROLLBACK
    ↓
RECORD PROGRESS
    ↓
SELECT NEXT OBJECTIVE
    ↓
REPEAT

DESIGN
------
01 remains the sovereign protected core.

02:
- boots the project
- monitors health
- repairs failures
- discovers development work
- asks 03 to generate one complete component
- validates generated source
- activates valid work
- rolls back invalid work
- records progress
- prevents endless duplicate objectives
- continues autonomous development while healthy
- runs continuously without routine owner intervention

03 remains the local AI development engine.

No fourth bootstrap file is required.

SECURITY
--------
The runtime does not:
- disable CORE-01 security
- expose secrets
- execute model-generated shell strings
- overwrite itself autonomously
- overwrite CORE-01 autonomously
- grant itself external privileges
- perform financial/legal/identity authorization
- claim successful validation without performing validation
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import enum
import hashlib
import importlib.util
import json
import logging
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


# ============================================================
# IDENTITY
# ============================================================

APP_NAME = "MAJD Assistant"
APP_NAME_AR = "مساعد مجد"

RUNTIME_NAME = "MAJD Assistant Autonomous Runtime"
RUNTIME_VERSION = "1.1.0"

CORE_FILENAME = "MAJD-ASSISTANT-CORE-01.py"
RUNTIME_FILENAME = "MAJD-ASSISTANT-AUTONOMOUS-RUNTIME-02.py"
AI_ENGINE_FILENAME = "MAJD-ASSISTANT-AI-ENGINE-03.py"

PROJECT_ROOT = Path(
    os.environ.get(
        "MAJD_ASSISTANT_ROOT",
        str(Path(__file__).resolve().parent),
    )
).resolve()

CORE_PATH = PROJECT_ROOT / CORE_FILENAME
RUNTIME_PATH = PROJECT_ROOT / RUNTIME_FILENAME
AI_ENGINE_PATH = PROJECT_ROOT / AI_ENGINE_FILENAME

DATA_DIR = Path(
    os.environ.get(
        "MAJD_ASSISTANT_DATA_DIR",
        str(PROJECT_ROOT / "data"),
    )
).resolve()

LOG_DIR = Path(
    os.environ.get(
        "MAJD_ASSISTANT_LOG_DIR",
        str(PROJECT_ROOT / "logs"),
    )
).resolve()

STATE_DIR = Path(
    os.environ.get(
        "MAJD_ASSISTANT_STATE_DIR",
        str(PROJECT_ROOT / ".majd-runtime"),
    )
).resolve()

BACKUP_DIR = STATE_DIR / "backups"
STAGING_DIR = STATE_DIR / "staging"
GENERATED_DIR = PROJECT_ROOT / "majd_generated"
TEST_DIR = PROJECT_ROOT / "tests"

RUNTIME_DB = STATE_DIR / "runtime.sqlite3"

MANIFEST_PATH = STATE_DIR / "runtime-manifest.json"
CAPABILITY_PATH = STATE_DIR / "capabilities.json"
HEALTH_PATH = STATE_DIR / "health.json"
DEVELOPMENT_STATE_PATH = STATE_DIR / "development-state.json"

HEARTBEAT_SECONDS = max(
    15,
    int(os.environ.get("MAJD_RUNTIME_HEARTBEAT", "60")),
)

MAINTENANCE_SECONDS = max(
    60,
    int(os.environ.get("MAJD_RUNTIME_MAINTENANCE", "900")),
)

DEVELOPMENT_SECONDS = max(
    60,
    int(os.environ.get("MAJD_RUNTIME_DEVELOPMENT", "900")),
)

MAX_REPAIR_ATTEMPTS = max(
    1,
    min(
        10,
        int(os.environ.get("MAJD_MAX_REPAIR_ATTEMPTS", "3")),
    ),
)

MAX_OBJECTIVE_FAILURES = max(
    1,
    min(
        20,
        int(os.environ.get("MAJD_MAX_OBJECTIVE_FAILURES", "3")),
    ),
)

COMMAND_TIMEOUT = max(
    5,
    int(os.environ.get("MAJD_COMMAND_TIMEOUT", "180")),
)

DEVELOPMENT_GATEWAY_TIMEOUT = max(
    60,
    min(
        3600,
        int(
            os.environ.get(
                "MAJD_DEVELOPMENT_GATEWAY_TIMEOUT",
                "600",
            )
        ),
    ),
)

DEVELOPMENT_HEALTH_TIMEOUT = max(
    2,
    min(
        60,
        int(
            os.environ.get(
                "MAJD_DEVELOPMENT_HEALTH_TIMEOUT",
                "10",
            )
        ),
    ),
)

MAX_GENERATED_FILE_BYTES = max(
    4096,
    int(
        os.environ.get(
            "MAJD_MAX_GENERATED_FILE_BYTES",
            "2000000",
        )
    ),
)

AUTO_INSTALL_DEPENDENCIES = (
    os.environ.get(
        "MAJD_AUTO_INSTALL_DEPENDENCIES",
        "0",
    ).strip().lower()
    in {"1", "true", "yes", "on"}
)

AUTO_GIT_COMMIT = (
    os.environ.get(
        "MAJD_AUTO_GIT_COMMIT",
        "0",
    ).strip().lower()
    in {"1", "true", "yes", "on"}
)

AUTO_DEPLOY = (
    os.environ.get(
        "MAJD_AUTO_DEPLOY",
        "0",
    ).strip().lower()
    in {"1", "true", "yes", "on"}
)

AUTO_DEVELOP = (
    os.environ.get(
        "MAJD_AUTO_DEVELOP",
        "1",
    ).strip().lower()
    in {"1", "true", "yes", "on"}
)

STOP_EVENT = threading.Event()


# ============================================================
# DIRECTORIES / LOGGING
# ============================================================

for directory in (
    DATA_DIR,
    LOG_DIR,
    STATE_DIR,
    BACKUP_DIR,
    STAGING_DIR,
    GENERATED_DIR,
    TEST_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=os.environ.get(
        "MAJD_RUNTIME_LOG_LEVEL",
        "INFO",
    ).upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            LOG_DIR / "majd-assistant-runtime.log",
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger("majd.assistant.runtime")


# ============================================================
# UTILITIES
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()


def safe_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
    )

    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_path, path)

    finally:
        with contextlib.suppress(FileNotFoundError):
            temp_path.unlink()


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        ) + "\n",
    )


def relative_path(path: Path) -> str:
    try:
        return str(
            path.resolve().relative_to(PROJECT_ROOT.resolve())
        )
    except Exception:
        return str(path.resolve())


def objective_key(objective: str) -> str:
    normalized = " ".join(
        (objective or "").strip().lower().split()
    )
    return sha256_bytes(normalized.encode("utf-8"))


# ============================================================
# SECRET PROTECTION
# ============================================================

SECRET_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|authorization)"
        r"\s*[:=]\s*['\"]?([^\s'\";,]+)"
    ),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        r"[\s\S]*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
)


class SecretGuard:
    @staticmethod
    def redact(value: str) -> str:
        output = value or ""

        for pattern in SECRET_PATTERNS:
            if pattern.groups >= 2:
                output = pattern.sub(
                    lambda match: f"{match.group(1)}=[REDACTED]",
                    output,
                )
            else:
                output = pattern.sub(
                    "[REDACTED_SECRET]",
                    output,
                )

        return output

    @staticmethod
    def contains_secret(value: str) -> bool:
        return any(
            pattern.search(value or "")
            for pattern in SECRET_PATTERNS
        )


# ============================================================
# ENUMS / MODELS
# ============================================================

class Risk(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ChangeType(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class CommandResult:
    success: bool
    argv: List[str]
    returncode: Optional[int]
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_ms: int = 0


@dataclass
class ValidationResult:
    success: bool
    checks: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ChangeProposal:
    proposal_id: str
    change_type: ChangeType
    relative_path: str
    content: str
    reason: str
    source: str
    created_at: str = field(default_factory=utc_now)


@dataclass
class BackupRecord:
    backup_id: str
    source_path: str
    backup_path: str
    sha256: str
    created_at: str


# ============================================================
# DATABASE
# ============================================================

class RuntimeDatabase:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")

        return connection

    def initialize(self) -> None:
        with self._lock, self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backups (
                    id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS generated_files (
                    path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS development_objectives (
                    objective_key TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    last_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def event(
        self,
        event_type: str,
        risk: Risk,
        details: Mapping[str, Any],
    ) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO runtime_events
                (id,event_type,risk,details,created_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    new_id("event"),
                    event_type,
                    risk.value,
                    SecretGuard.redact(
                        safe_json(dict(details))
                    ),
                    utc_now(),
                ),
            )

    def create_job(
        self,
        job_type: str,
        details: Mapping[str, Any],
    ) -> str:
        job_id = new_id("job")
        now = utc_now()

        with self._lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO jobs
                (id,job_type,status,details,created_at,updated_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    job_id,
                    job_type,
                    JobStatus.PENDING.value,
                    SecretGuard.redact(
                        safe_json(dict(details))
                    ),
                    now,
                    now,
                ),
            )

        return job_id

    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        details: Mapping[str, Any],
    ) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                """
                UPDATE jobs
                SET status=?,details=?,updated_at=?
                WHERE id=?
                """,
                (
                    status.value,
                    SecretGuard.redact(
                        safe_json(dict(details))
                    ),
                    utc_now(),
                    job_id,
                ),
            )

    def save_backup(self, record: BackupRecord) -> None:
        with self._lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO backups
                (id,source_path,backup_path,sha256,created_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    record.backup_id,
                    record.source_path,
                    record.backup_path,
                    record.sha256,
                    record.created_at,
                ),
            )

    def record_generated_file(
        self,
        path: Path,
        source: str,
        status: str,
        metadata: Mapping[str, Any],
    ) -> None:
        digest = sha256_file(path) if path.exists() else ""

        with self._lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO generated_files
                (path,sha256,source,status,metadata,updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET
                    sha256=excluded.sha256,
                    source=excluded.source,
                    status=excluded.status,
                    metadata=excluded.metadata,
                    updated_at=excluded.updated_at
                """,
                (
                    relative_path(path),
                    digest,
                    source,
                    status,
                    SecretGuard.redact(
                        safe_json(dict(metadata))
                    ),
                    utc_now(),
                ),
            )

    def objective_status(
        self,
        objective: str,
    ) -> Optional[Dict[str, Any]]:
        key = objective_key(objective)

        with self._lock, self.connect() as db:
            row = db.execute(
                """
                SELECT *
                FROM development_objectives
                WHERE objective_key=?
                """,
                (key,),
            ).fetchone()

        return dict(row) if row else None

    def objective_start(self, objective: str) -> None:
        key = objective_key(objective)
        now = utc_now()

        with self._lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO development_objectives
                (
                    objective_key,objective,status,
                    attempts,successes,failures,
                    created_at,updated_at
                )
                VALUES (?,?,'RUNNING',1,0,0,?,?)
                ON CONFLICT(objective_key) DO UPDATE SET
                    status='RUNNING',
                    attempts=attempts+1,
                    updated_at=excluded.updated_at
                """,
                (key, objective, now, now),
            )

    def objective_complete(
        self,
        objective: str,
        path: str,
    ) -> None:
        key = objective_key(objective)

        with self._lock, self.connect() as db:
            db.execute(
                """
                UPDATE development_objectives
                SET status='COMPLETED',
                    successes=successes+1,
                    last_error=NULL,
                    last_path=?,
                    updated_at=?
                WHERE objective_key=?
                """,
                (
                    path,
                    utc_now(),
                    key,
                ),
            )

    def objective_fail(
        self,
        objective: str,
        error: str,
    ) -> None:
        key = objective_key(objective)

        with self._lock, self.connect() as db:
            db.execute(
                """
                UPDATE development_objectives
                SET status='FAILED',
                    failures=failures+1,
                    last_error=?,
                    updated_at=?
                WHERE objective_key=?
                """,
                (
                    SecretGuard.redact(error),
                    utc_now(),
                    key,
                ),
            )

    def completed_objectives(self) -> List[str]:
        with self._lock, self.connect() as db:
            rows = db.execute(
                """
                SELECT objective
                FROM development_objectives
                WHERE status='COMPLETED'
                ORDER BY updated_at
                """
            ).fetchall()

        return [str(row["objective"]) for row in rows]


# ============================================================
# COMMAND RUNNER
# ============================================================

class CommandRunner:
    def __init__(self, timeout: int = COMMAND_TIMEOUT):
        self.timeout = timeout

    def run(
        self,
        argv: Sequence[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        if not argv:
            return CommandResult(
                False,
                [],
                None,
                stderr="EMPTY_COMMAND",
            )

        safe_argv = [str(item) for item in argv]
        started = time.monotonic()

        try:
            process = subprocess.run(
                safe_argv,
                cwd=str(cwd or PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                shell=False,
                check=False,
            )

            return CommandResult(
                success=process.returncode == 0,
                argv=safe_argv,
                returncode=process.returncode,
                stdout=SecretGuard.redact(
                    process.stdout or ""
                ),
                stderr=SecretGuard.redact(
                    process.stderr or ""
                ),
                duration_ms=int(
                    (time.monotonic() - started) * 1000
                ),
            )

        except subprocess.TimeoutExpired:
            return CommandResult(
                False,
                safe_argv,
                None,
                timed_out=True,
                stderr="COMMAND_TIMEOUT",
                duration_ms=int(
                    (time.monotonic() - started) * 1000
                ),
            )

        except Exception as exc:
            return CommandResult(
                False,
                safe_argv,
                None,
                stderr=SecretGuard.redact(
                    f"{type(exc).__name__}: {exc}"
                ),
            )


# ============================================================
# CORE
# ============================================================

class CoreLoader:
    def __init__(self, path: Path):
        self.path = path
        self.module: Optional[Any] = None

    def load(self) -> Any:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Required core missing: {self.path}"
            )

        spec = importlib.util.spec_from_file_location(
            "majd_assistant_core_01",
            self.path,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError("CORE_IMPORT_SPEC_FAILED")

        module = importlib.util.module_from_spec(spec)
        sys.modules["majd_assistant_core_01"] = module
        spec.loader.exec_module(module)

        self.module = module
        return module

    def constitution_fingerprint(self) -> str:
        module = self.module or self.load()

        constitution = getattr(
            module,
            "SOVEREIGN_CONSTITUTION",
            None,
        )

        if not constitution:
            raise RuntimeError(
                "CORE_SOVEREIGN_CONSTITUTION_MISSING"
            )

        return sha256_bytes(
            safe_json(list(constitution)).encode("utf-8")
        )

    def self_check(self) -> Dict[str, Any]:
        module = self.module or self.load()

        function = getattr(
            module,
            "startup_self_check",
            None,
        )

        if not callable(function):
            raise RuntimeError(
                "CORE_STARTUP_SELF_CHECK_MISSING"
            )

        result = function()

        if not isinstance(result, dict):
            raise RuntimeError(
                "INVALID_CORE_SELF_CHECK"
            )

        return result


# ============================================================
# PATH POLICY
# ============================================================

class ProtectedPathPolicy:
    PROTECTED_FILES = {
        CORE_FILENAME,
        RUNTIME_FILENAME,
        AI_ENGINE_FILENAME,
    }

    @classmethod
    def safe_target(
        cls,
        relative: str,
    ) -> Tuple[bool, str]:
        candidate = Path(relative)

        if candidate.is_absolute():
            return False, "ABSOLUTE_PATH_BLOCKED"

        if ".." in candidate.parts:
            return False, "PATH_TRAVERSAL_BLOCKED"

        if not candidate.parts:
            return False, "EMPTY_PATH"

        if candidate.parts[0] != "majd_generated":
            return False, "OUTSIDE_GENERATED_ROOT"

        if candidate.name in cls.PROTECTED_FILES:
            return False, "PROTECTED_FILE"

        if candidate.name.startswith(".env"):
            return False, "SECRET_FILE_BLOCKED"

        return True, "ALLOWED"


# ============================================================
# BACKUP
# ============================================================

class BackupManager:
    def __init__(self, db: RuntimeDatabase):
        self.db = db

    def backup(
        self,
        path: Path,
    ) -> Optional[BackupRecord]:
        if not path.exists():
            return None

        backup_id = new_id("backup")
        destination = (
            BACKUP_DIR
            / backup_id
            / relative_path(path)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(path, destination)

        record = BackupRecord(
            backup_id=backup_id,
            source_path=str(path),
            backup_path=str(destination),
            sha256=sha256_file(destination),
            created_at=utc_now(),
        )

        self.db.save_backup(record)
        return record

    def restore(self, record: BackupRecord) -> bool:
        source = Path(record.backup_path)
        destination = Path(record.source_path)

        if not source.exists():
            return False

        if sha256_file(source) != record.sha256:
            return False

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(source, destination)

        return (
            destination.exists()
            and sha256_file(destination)
            == record.sha256
        )


# ============================================================
# SOURCE VALIDATION
# ============================================================

class SourceValidator:
    @staticmethod
    def validate_python_source(
        content: str,
    ) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if len(content.encode("utf-8")) > MAX_GENERATED_FILE_BYTES:
            errors.append("GENERATED_FILE_TOO_LARGE")

        if SecretGuard.contains_secret(content):
            errors.append("POSSIBLE_SECRET_IN_SOURCE")

        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return ValidationResult(
                False,
                errors=[
                    f"SYNTAX_ERROR:{exc.lineno}:{exc.msg}"
                ],
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in {"eval", "exec"}
                ):
                    warnings.append(
                        f"REVIEW_CALL:{node.func.id}"
                    )

        return ValidationResult(
            success=not errors,
            checks={"ast_parse": True},
            errors=errors,
            warnings=warnings,
        )


# ============================================================
# PROJECT VALIDATION
# ============================================================

class ProjectValidator:
    def __init__(self, runner: CommandRunner):
        self.runner = runner

    def compile_file(self, path: Path) -> ValidationResult:
        result = self.runner.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(path),
            ]
        )

        return ValidationResult(
            result.success,
            checks={"py_compile": result.success},
            errors=[] if result.success else [
                result.stderr or result.stdout
            ],
        )

    def compile_project(self) -> ValidationResult:
        errors: List[str] = []
        compiled = 0
        total = 0

        for path in PROJECT_ROOT.rglob("*.py"):
            if (
                ".git" in path.parts
                or ".majd-runtime" in path.parts
                or "__pycache__" in path.parts
            ):
                continue

            total += 1
            result = self.compile_file(path)

            if result.success:
                compiled += 1
            else:
                errors.extend(
                    f"{relative_path(path)}:{error}"
                    for error in result.errors
                )

        return ValidationResult(
            not errors,
            checks={
                "python_files": total,
                "compiled": compiled,
            },
            errors=errors,
        )

    def core_self_check(self) -> ValidationResult:
        result = self.runner.run(
            [
                sys.executable,
                str(CORE_PATH),
                "--self-check",
            ]
        )

        if not result.success:
            return ValidationResult(
                False,
                errors=[
                    result.stderr
                    or result.stdout
                    or "CORE_SELF_CHECK_FAILED"
                ],
            )

        try:
            payload = json.loads(result.stdout)

            return ValidationResult(
                bool(payload.get("ok")),
                checks={"core": payload},
                errors=[] if payload.get("ok") else [
                    "CORE_SELF_CHECK_FAILED"
                ],
            )

        except Exception:
            return ValidationResult(
                False,
                errors=["CORE_SELF_CHECK_INVALID_JSON"],
            )

    def run_tests(self) -> ValidationResult:
        if not list(TEST_DIR.glob("test_*.py")):
            return ValidationResult(
                True,
                checks={
                    "tests_present": False,
                    "tests_run": 0,
                },
                warnings=["NO_TEST_FILES_PRESENT"],
            )

        result = self.runner.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(TEST_DIR),
                "-p",
                "test_*.py",
            ]
        )

        return ValidationResult(
            result.success,
            checks={"tests_present": True},
            errors=[] if result.success else [
                result.stderr or result.stdout
            ],
        )

    def full_validation(self) -> ValidationResult:
        compile_result = self.compile_project()
        core_result = self.core_self_check()
        tests_result = self.run_tests()

        return ValidationResult(
            success=(
                compile_result.success
                and core_result.success
                and tests_result.success
            ),
            checks={
                "compile": compile_result.checks,
                "core": core_result.checks,
                "tests": tests_result.checks,
            },
            errors=(
                compile_result.errors
                + core_result.errors
                + tests_result.errors
            ),
            warnings=(
                compile_result.warnings
                + core_result.warnings
                + tests_result.warnings
            ),
        )


# ============================================================
# AI DEVELOPMENT GATEWAY
# ============================================================

class DevelopmentGateway:
    def __init__(self):
        self.base_url = os.environ.get(
            "MAJD_DEVELOPMENT_GATEWAY_URL",
            "http://127.0.0.1:8766",
        ).rstrip("/")

        self.token = os.environ.get(
            "MAJD_DEVELOPMENT_GATEWAY_TOKEN",
            "",
        )

        self.last_error: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                f"MAJD-Autonomous-Runtime/{RUNTIME_VERSION}"
            ),
        }

        if self.token:
            headers["Authorization"] = (
                f"Bearer {self.token}"
            )

        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = DEVELOPMENT_GATEWAY_TIMEOUT,
    ) -> Dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=(
                safe_json(payload).encode("utf-8")
                if payload is not None
                else None
            ),
            headers=self._headers(),
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:
                raw = response.read(
                    MAX_GENERATED_FILE_BYTES + 500001
                )

        except Exception as exc:
            raise RuntimeError(
                SecretGuard.redact(
                    f"{type(exc).__name__}:{exc}"
                )
            ) from exc

        if len(raw) > MAX_GENERATED_FILE_BYTES + 500000:
            raise RuntimeError(
                "DEVELOPMENT_RESPONSE_TOO_LARGE"
            )

        result = json.loads(raw.decode("utf-8"))

        if not isinstance(result, dict):
            raise RuntimeError(
                "DEVELOPMENT_JSON_OBJECT_REQUIRED"
            )

        return result

    def healthy(self) -> bool:
        self.last_error = None

        try:
            response = self._request(
                "GET",
                "/health",
                timeout=DEVELOPMENT_HEALTH_TIMEOUT,
            )

            if response.get("ok"):
                return True

            self.last_error = "AI_ENGINE_HEALTH_FALSE"
            return False

        except Exception as exc:
            self.last_error = str(exc)
            return False

    @staticmethod
    def normalize_path(raw: str) -> Optional[str]:
        value = str(raw or "").strip().replace("\\", "/")

        if not value:
            return None

        candidate = Path(value)

        if candidate.is_absolute() or ".." in candidate.parts:
            return None

        if (
            not candidate.parts
            or candidate.parts[0] != "majd_generated"
        ):
            candidate = Path("majd_generated") / candidate

        return candidate.as_posix()

    def propose(
        self,
        objective: str,
        manifest: Mapping[str, Any],
        errors: Sequence[str],
    ) -> Optional[ChangeProposal]:
        self.last_error = None

        if not self.healthy():
            return None

        payload = {
            "operation": "generate_code",
            "objective": (
                objective
                + "\n\n"
                "Inspect the supplied MAJD project state. "
                "Generate exactly one complete production-quality "
                "Python component that materially advances the objective. "
                "Return a complete file, never a patch. "
                "The file belongs under majd_generated/. "
                "Preserve CORE-01 authority and security. "
                "Do not modify CORE-01, RUNTIME-02 or AI-ENGINE-03."
            ),
            "language": "python",
            "write": False,
            "context": {
                "project_manifest": dict(manifest),
                "errors": list(errors),
                "constraints": {
                    "allowed_root": "majd_generated",
                    "complete_files_only": True,
                    "no_secrets": True,
                    "no_security_bypass": True,
                },
            },
        }

        try:
            response = self._request(
                "POST",
                "/v1/develop",
                payload,
            )
        except Exception as exc:
            self.last_error = str(exc)
            return None

        # Supports:
        # 02-compatible top-level response
        # AND
        # 03 nested result response.
        containers: List[Dict[str, Any]] = []

        current: Any = response

        for _ in range(4):
            if not isinstance(current, dict):
                break

            containers.append(current)

            next_result = current.get("result")

            if not isinstance(next_result, dict):
                break

            current = next_result

        success_seen = any(
            item.get("success") is True
            or item.get("ok") is True
            for item in containers
        )

        if not success_seen:
            self.last_error = (
                str(response.get("error"))
                if response.get("error")
                else "AI_ENGINE_RETURNED_FAILURE"
            )
            return None

        raw_path = ""
        content: Optional[str] = None
        reason = objective
        provider = "MAJD-AI-ENGINE-03"

        for item in containers:
            if not raw_path:
                raw_path = str(
                    item.get("relative_path")
                    or item.get("filename")
                    or ""
                )

            if content is None and isinstance(
                item.get("content"),
                str,
            ):
                content = item["content"]

            if item.get("summary"):
                reason = str(item["summary"])

            if item.get("model"):
                provider = str(item["model"])

        path = self.normalize_path(raw_path)

        if not path:
            self.last_error = "AI_ENGINE_INVALID_PATH"
            return None

        if not content or not content.strip():
            self.last_error = "AI_ENGINE_MISSING_CONTENT"
            return None

        return ChangeProposal(
            proposal_id=new_id("proposal"),
            change_type=ChangeType.CREATE,
            relative_path=path,
            content=content,
            reason=reason,
            source=provider,
        )


# ============================================================
# CHANGE MANAGER
# ============================================================

class ChangeManager:
    def __init__(
        self,
        db: RuntimeDatabase,
        backups: BackupManager,
        validator: ProjectValidator,
    ):
        self.db = db
        self.backups = backups
        self.validator = validator

    def apply(
        self,
        proposal: ChangeProposal,
    ) -> ValidationResult:
        allowed, reason = ProtectedPathPolicy.safe_target(
            proposal.relative_path
        )

        if not allowed:
            return ValidationResult(
                False,
                errors=[reason],
            )

        target = (
            PROJECT_ROOT / proposal.relative_path
        ).resolve()

        try:
            target.relative_to(PROJECT_ROOT)
        except ValueError:
            return ValidationResult(
                False,
                errors=["TARGET_OUTSIDE_PROJECT"],
            )

        source_validation = (
            SourceValidator.validate_python_source(
                proposal.content
            )
            if target.suffix == ".py"
            else ValidationResult(True)
        )

        if not source_validation.success:
            return source_validation

        existed = target.exists()
        backup = self.backups.backup(target)

        try:
            atomic_write_text(
                target,
                proposal.content,
            )

            validation = self.validator.full_validation()

            if validation.success:
                self.db.record_generated_file(
                    target,
                    proposal.source,
                    "ACTIVE",
                    {
                        "proposal": proposal.proposal_id,
                        "reason": proposal.reason,
                    },
                )

                self.db.event(
                    "CHANGE_ACTIVATED",
                    Risk.MEDIUM,
                    {
                        "path": proposal.relative_path,
                        "proposal": proposal.proposal_id,
                    },
                )

                return validation

            if backup:
                restored = self.backups.restore(backup)
            elif not existed:
                with contextlib.suppress(FileNotFoundError):
                    target.unlink()
                restored = not target.exists()
            else:
                restored = False

            validation.errors.append(
                "ROLLED_BACK"
                if restored
                else "ROLLBACK_FAILED"
            )

            return validation

        except Exception as exc:
            if backup:
                self.backups.restore(backup)
            elif not existed:
                with contextlib.suppress(FileNotFoundError):
                    target.unlink()

            return ValidationResult(
                False,
                errors=[
                    f"{type(exc).__name__}:{exc}"
                ],
            )


# ============================================================
# PROJECT MANIFEST
# ============================================================

class ProjectManifest:
    @staticmethod
    def build(
        core_loader: CoreLoader,
    ) -> Dict[str, Any]:
        files: List[Dict[str, Any]] = []

        for path in PROJECT_ROOT.rglob("*"):
            if not path.is_file():
                continue

            if (
                ".git" in path.parts
                or ".majd-runtime" in path.parts
                or "__pycache__" in path.parts
            ):
                continue

            try:
                size = path.stat().st_size
            except OSError:
                continue

            files.append(
                {
                    "path": relative_path(path),
                    "size": size,
                    "sha256": (
                        sha256_file(path)
                        if size <= 5_000_000
                        else None
                    ),
                }
            )

        return {
            "project": "MAJD-ASSISTANT",
            "runtime_version": RUNTIME_VERSION,
            "generated_at": utc_now(),
            "core": {
                "file": CORE_FILENAME,
                "sha256": sha256_file(CORE_PATH),
                "constitution": (
                    core_loader.constitution_fingerprint()
                ),
            },
            "runtime": {
                "file": RUNTIME_FILENAME,
            },
            "ai_engine": {
                "file": AI_ENGINE_FILENAME,
                "exists": AI_ENGINE_PATH.exists(),
            },
            "files": files,
        }


# ============================================================
# AUTONOMOUS DEVELOPER
# ============================================================

class AutonomousDeveloper:
    def __init__(
        self,
        db: RuntimeDatabase,
        gateway: DevelopmentGateway,
        changes: ChangeManager,
        validator: ProjectValidator,
        core_loader: CoreLoader,
    ):
        self.db = db
        self.gateway = gateway
        self.changes = changes
        self.validator = validator
        self.core_loader = core_loader

    def develop(
        self,
        objective: str,
        allow_completed: bool = False,
    ) -> ValidationResult:
        existing = self.db.objective_status(objective)

        if (
            existing
            and existing.get("status") == "COMPLETED"
            and not allow_completed
        ):
            return ValidationResult(
                True,
                checks={
                    "already_completed": True,
                    "path": existing.get("last_path"),
                },
            )

        if (
            existing
            and int(existing.get("failures", 0))
            >= MAX_OBJECTIVE_FAILURES
        ):
            return ValidationResult(
                False,
                errors=[
                    "OBJECTIVE_FAILURE_LIMIT_REACHED"
                ],
            )

        self.db.objective_start(objective)

        job_id = self.db.create_job(
            "AUTONOMOUS_DEVELOPMENT",
            {"objective": objective},
        )

        self.db.update_job(
            job_id,
            JobStatus.RUNNING,
            {"objective": objective},
        )

        baseline = self.validator.full_validation()
        errors = list(baseline.errors)

        for attempt in range(
            1,
            MAX_REPAIR_ATTEMPTS + 1,
        ):
            manifest = ProjectManifest.build(
                self.core_loader
            )

            proposal = self.gateway.propose(
                objective,
                manifest,
                errors,
            )

            if proposal is None:
                error = (
                    self.gateway.last_error
                    or "DEVELOPMENT_GATEWAY_NO_PROPOSAL"
                )

                self.db.objective_fail(
                    objective,
                    error,
                )

                self.db.update_job(
                    job_id,
                    JobStatus.BLOCKED,
                    {
                        "attempt": attempt,
                        "error": error,
                    },
                )

                return ValidationResult(
                    False,
                    errors=[error],
                )

            result = self.changes.apply(proposal)

            if result.success:
                self.db.objective_complete(
                    objective,
                    proposal.relative_path,
                )

                self.db.update_job(
                    job_id,
                    JobStatus.PASSED,
                    {
                        "attempt": attempt,
                        "path": proposal.relative_path,
                    },
                )

                return result

            errors = list(result.errors)

        final_error = (
            " | ".join(errors)
            if errors
            else "MAX_REPAIR_ATTEMPTS_REACHED"
        )

        self.db.objective_fail(
            objective,
            final_error,
        )

        self.db.update_job(
            job_id,
            JobStatus.FAILED,
            {"errors": errors},
        )

        return ValidationResult(
            False,
            errors=errors or [
                "MAX_REPAIR_ATTEMPTS_REACHED"
            ],
        )


# ============================================================
# AUTONOMOUS ROADMAP
# ============================================================

class AutonomousRoadmap:
    """
    Stable bootstrap roadmap.

    The runtime completes one objective at a time.
    Completed objectives are persisted and not repeated.
    """

    OBJECTIVES: Tuple[str, ...] = (
        (
            "Build the MAJD Assistant application service layer that "
            "connects user requests to CORE-01 policy and the approved "
            "assistant capabilities."
        ),
        (
            "Build the MAJD Assistant conversation orchestration component "
            "with Arabic and English request handling and safe capability routing."
        ),
        (
            "Build persistent conversation and operational state management "
            "for MAJD Assistant using local safe storage."
        ),
        (
            "Build the MAJD Assistant capability registry and routing layer "
            "for available local and configured external capabilities."
        ),
        (
            "Build the MAJD Assistant task planning component for decomposing "
            "approved user objectives into controlled executable tasks."
        ),
        (
            "Build the MAJD Assistant execution coordination component with "
            "validation, failure reporting and safe retry semantics."
        ),
        (
            "Build the MAJD Assistant internal diagnostics component for "
            "detecting application failures and producing structured repair context."
        ),
        (
            "Build production-ready tests for generated MAJD Assistant "
            "application components without modifying protected core files."
        ),
        (
            "Build the MAJD Assistant public API integration component needed "
            "to expose approved assistant functions to a future user interface."
        ),
        (
            "Review the generated MAJD Assistant application components and "
            "create one missing integration component required for a coherent "
            "operational assistant while preserving CORE-01 authority."
        ),
    )

    def __init__(self, db: RuntimeDatabase):
        self.db = db

    def next_objective(self) -> Optional[str]:
        completed = set(
            self.db.completed_objectives()
        )

        for objective in self.OBJECTIVES:
            if objective not in completed:
                status = self.db.objective_status(
                    objective
                )

                if (
                    status
                    and int(status.get("failures", 0))
                    >= MAX_OBJECTIVE_FAILURES
                ):
                    continue

                return objective

        return None

    def state(self) -> Dict[str, Any]:
        completed = set(
            self.db.completed_objectives()
        )

        return {
            "time": utc_now(),
            "total": len(self.OBJECTIVES),
            "completed": sum(
                1
                for objective in self.OBJECTIVES
                if objective in completed
            ),
            "remaining": sum(
                1
                for objective in self.OBJECTIVES
                if objective not in completed
            ),
            "next_objective": self.next_objective(),
        }


# ============================================================
# CAPABILITIES
# ============================================================

class CapabilityDiscovery:
    @staticmethod
    def discover() -> Dict[str, Any]:
        development_url = os.environ.get(
            "MAJD_DEVELOPMENT_GATEWAY_URL",
            "http://127.0.0.1:8766",
        )

        return {
            "time": utc_now(),
            "capabilities": {
                "conversation": True,
                "multilingual": True,
                "coding_contract": True,
                "local_ai_engine_present": (
                    AI_ENGINE_PATH.exists()
                ),
                "autonomous_development": bool(
                    development_url
                    and AI_ENGINE_PATH.exists()
                ),
                "automatic_repair": True,
                "automatic_validation": True,
                "automatic_rollback": True,
                "persistent_development_state": True,
                "continuous_development": AUTO_DEVELOP,
            },
            "development_gateway": {
                "configured": bool(development_url),
                "url": development_url,
                "timeout_seconds": (
                    DEVELOPMENT_GATEWAY_TIMEOUT
                ),
            },
        }


# ============================================================
# HEALTH
# ============================================================

class HealthEngine:
    def __init__(
        self,
        validator: ProjectValidator,
        core_loader: CoreLoader,
        gateway: DevelopmentGateway,
        db: RuntimeDatabase,
    ):
        self.validator = validator
        self.core_loader = core_loader
        self.gateway = gateway
        self.db = db

    def check(self) -> Dict[str, Any]:
        started = time.monotonic()

        validation = self.validator.full_validation()
        gateway_ok = self.gateway.healthy()

        result = {
            "ok": validation.success,
            "time": utc_now(),
            "runtime": {
                "name": RUNTIME_NAME,
                "version": RUNTIME_VERSION,
            },
            "core": {
                "exists": CORE_PATH.exists(),
                "constitution_fingerprint": (
                    self.core_loader
                    .constitution_fingerprint()
                ),
            },
            "ai_engine": {
                "exists": AI_ENGINE_PATH.exists(),
                "reachable": gateway_ok,
                "error": (
                    None
                    if gateway_ok
                    else self.gateway.last_error
                ),
            },
            "validation": {
                "success": validation.success,
                "checks": validation.checks,
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
            "capabilities": (
                CapabilityDiscovery.discover()
            ),
            "duration_ms": int(
                (time.monotonic() - started) * 1000
            ),
        }

        write_json(HEALTH_PATH, result)

        self.db.event(
            "HEALTH_CHECK",
            Risk.LOW if result["ok"] else Risk.HIGH,
            {
                "ok": result["ok"],
                "ai_engine": gateway_ok,
                "errors": validation.errors,
            },
        )

        return result


# ============================================================
# MAINTENANCE + CONTINUOUS DEVELOPMENT
# ============================================================

class MaintenanceEngine:
    def __init__(
        self,
        db: RuntimeDatabase,
        health: HealthEngine,
        developer: AutonomousDeveloper,
        roadmap: AutonomousRoadmap,
    ):
        self.db = db
        self.health = health
        self.developer = developer
        self.roadmap = roadmap

    def repair_if_required(
        self,
        health_before: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if health_before["ok"]:
            return None

        errors = health_before[
            "validation"
        ]["errors"]

        objective = (
            "Repair the current MAJD Assistant generated application "
            "validation failures without modifying CORE-01, RUNTIME-02 "
            "or AI-ENGINE-03. Failures: "
            + " | ".join(errors[:20])
        )

        result = self.developer.develop(
            objective,
            allow_completed=True,
        )

        return {
            "action": "automatic_repair",
            "success": result.success,
            "errors": result.errors,
        }

    def develop_next(self) -> Dict[str, Any]:
        if not AUTO_DEVELOP:
            return {
                "action": "autonomous_development",
                "success": True,
                "skipped": "AUTO_DEVELOP_DISABLED",
            }

        objective = self.roadmap.next_objective()

        if objective is None:
            return {
                "action": "autonomous_development",
                "success": True,
                "complete": True,
                "message": "BOOTSTRAP_ROADMAP_COMPLETE",
            }

        result = self.developer.develop(
            objective
        )

        return {
            "action": "autonomous_development",
            "objective": objective,
            "success": result.success,
            "errors": result.errors,
        }

    def cycle(
        self,
        include_development: bool = True,
    ) -> Dict[str, Any]:
        cycle_id = new_id("cycle")
        started = time.monotonic()
        actions: List[Dict[str, Any]] = []

        health_before = self.health.check()

        repair = self.repair_if_required(
            health_before
        )

        if repair:
            actions.append(repair)

        health_after_repair = self.health.check()

        if (
            include_development
            and health_after_repair["ok"]
        ):
            actions.append(
                self.develop_next()
            )

        health_final = self.health.check()
        roadmap_state = self.roadmap.state()

        write_json(
            DEVELOPMENT_STATE_PATH,
            roadmap_state,
        )

        result = {
            "cycle_id": cycle_id,
            "ok": health_final["ok"],
            "health_before": health_before["ok"],
            "health_after": health_final["ok"],
            "actions": actions,
            "roadmap": roadmap_state,
            "duration_ms": int(
                (time.monotonic() - started) * 1000
            ),
            "time": utc_now(),
        }

        self.db.event(
            "AUTONOMOUS_CYCLE_COMPLETE",
            Risk.LOW if result["ok"] else Risk.HIGH,
            result,
        )

        return result


# ============================================================
# RUNTIME
# ============================================================

class MajdAutonomousRuntime:
    def __init__(self):
        self.db = RuntimeDatabase(RUNTIME_DB)
        self.runner = CommandRunner()

        self.core_loader = CoreLoader(CORE_PATH)
        self.core_loader.load()

        self.initial_constitution = (
            self.core_loader.constitution_fingerprint()
        )

        self.validator = ProjectValidator(
            self.runner
        )

        self.gateway = DevelopmentGateway()

        self.backups = BackupManager(
            self.db
        )

        self.changes = ChangeManager(
            self.db,
            self.backups,
            self.validator,
        )

        self.developer = AutonomousDeveloper(
            self.db,
            self.gateway,
            self.changes,
            self.validator,
            self.core_loader,
        )

        self.roadmap = AutonomousRoadmap(
            self.db
        )

        self.health_engine = HealthEngine(
            self.validator,
            self.core_loader,
            self.gateway,
            self.db,
        )

        self.maintenance = MaintenanceEngine(
            self.db,
            self.health_engine,
            self.developer,
            self.roadmap,
        )

        self._write_manifest()

    def _assert_constitution(self) -> None:
        current = (
            self.core_loader.constitution_fingerprint()
        )

        if current != self.initial_constitution:
            raise RuntimeError(
                "SOVEREIGN_CONSTITUTION_CHANGED"
            )

    def _write_manifest(self) -> None:
        write_json(
            MANIFEST_PATH,
            ProjectManifest.build(
                self.core_loader
            ),
        )

        write_json(
            CAPABILITY_PATH,
            CapabilityDiscovery.discover(),
        )

        write_json(
            DEVELOPMENT_STATE_PATH,
            self.roadmap.state(),
        )

    def bootstrap(self) -> Dict[str, Any]:
        self._assert_constitution()

        core = self.core_loader.self_check()
        validation = self.validator.full_validation()
        gateway = self.gateway.healthy()

        self._write_manifest()

        result = {
            "ok": (
                bool(core.get("ok"))
                and validation.success
            ),
            "runtime": RUNTIME_NAME,
            "version": RUNTIME_VERSION,
            "core": bool(core.get("ok")),
            "ai_engine": gateway,
            "ai_engine_error": (
                None
                if gateway
                else self.gateway.last_error
            ),
            "autonomous": True,
            "continuous_development": AUTO_DEVELOP,
            "development_timeout": (
                DEVELOPMENT_GATEWAY_TIMEOUT
            ),
            "roadmap": self.roadmap.state(),
            "time": utc_now(),
        }

        self.db.event(
            "RUNTIME_BOOTSTRAP",
            Risk.LOW if result["ok"] else Risk.HIGH,
            result,
        )

        return result

    def health(self) -> Dict[str, Any]:
        self._assert_constitution()
        return self.health_engine.check()

    def develop(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        self._assert_constitution()

        result = self.developer.develop(
            objective
        )

        self._assert_constitution()
        self._write_manifest()

        return {
            "ok": result.success,
            "checks": result.checks,
            "errors": result.errors,
            "warnings": result.warnings,
            "time": utc_now(),
        }

    def maintenance_once(self) -> Dict[str, Any]:
        self._assert_constitution()

        result = self.maintenance.cycle(
            include_development=True
        )

        self._assert_constitution()
        self._write_manifest()

        return result

    def run_forever(self) -> int:
        bootstrap = self.bootstrap()

        logger.info(
            "MAJD autonomous runtime started "
            "version=%s bootstrap=%s",
            RUNTIME_VERSION,
            bootstrap["ok"],
        )

        last_maintenance = 0.0
        last_development = 0.0

        while not STOP_EVENT.is_set():
            try:
                self._assert_constitution()

                now = time.monotonic()

                maintenance_due = (
                    now - last_maintenance
                    >= MAINTENANCE_SECONDS
                )

                development_due = (
                    AUTO_DEVELOP
                    and (
                        now - last_development
                        >= DEVELOPMENT_SECONDS
                    )
                )

                if maintenance_due:
                    result = self.maintenance.cycle(
                        include_development=development_due
                    )

                    logger.info(
                        "Autonomous cycle complete ok=%s",
                        result["ok"],
                    )

                    last_maintenance = now

                    if development_due:
                        last_development = now

                elif development_due:
                    health = self.health()

                    if health["ok"]:
                        action = (
                            self.maintenance.develop_next()
                        )

                        logger.info(
                            "Development cycle success=%s",
                            action.get("success"),
                        )

                        self._write_manifest()

                    last_development = now

                else:
                    health = self.health()

                    logger.info(
                        "Heartbeat ok=%s ai_engine=%s",
                        health["ok"],
                        health["ai_engine"]["reachable"],
                    )

                STOP_EVENT.wait(
                    HEARTBEAT_SECONDS
                )

            except KeyboardInterrupt:
                STOP_EVENT.set()

            except Exception as exc:
                logger.error(
                    "Runtime cycle failure: %s\n%s",
                    SecretGuard.redact(str(exc)),
                    SecretGuard.redact(
                        traceback.format_exc()
                    ),
                )

                self.db.event(
                    "RUNTIME_CYCLE_FAILURE",
                    Risk.HIGH,
                    {
                        "error": (
                            f"{type(exc).__name__}:{exc}"
                        )
                    },
                )

                STOP_EVENT.wait(
                    HEARTBEAT_SECONDS
                )

        logger.info(
            "MAJD autonomous runtime stopped."
        )

        return 0


# ============================================================
# SIGNALS
# ============================================================

def handle_stop_signal(
    signum: int,
    frame: Any,
) -> None:
    del frame

    logger.info(
        "Stop signal received: %s",
        signum,
    )

    STOP_EVENT.set()


def install_signal_handlers() -> None:
    for sig in (
        signal.SIGINT,
        signal.SIGTERM,
    ):
        with contextlib.suppress(Exception):
            signal.signal(
                sig,
                handle_stop_signal,
            )


# ============================================================
# SELF CHECK
# ============================================================

def runtime_self_check() -> Dict[str, Any]:
    checks: Dict[str, Any] = {
        "runtime_file": RUNTIME_PATH.exists(),
        "core_file": CORE_PATH.exists(),
        "ai_engine_file": AI_ENGINE_PATH.exists(),
        "directories": all(
            path.exists()
            for path in (
                DATA_DIR,
                LOG_DIR,
                STATE_DIR,
                BACKUP_DIR,
                STAGING_DIR,
                GENERATED_DIR,
                TEST_DIR,
            )
        ),
        "secret_redaction": False,
        "database": False,
        "core_import": False,
        "constitution": False,
        "development_timeout": (
            DEVELOPMENT_GATEWAY_TIMEOUT >= 60
        ),
        "continuous_development": AUTO_DEVELOP,
    }

    checks["secret_redaction"] = (
        "THIS_VALUE_MUST_HIDE"
        not in SecretGuard.redact(
            "api_key=THIS_VALUE_MUST_HIDE"
        )
    )

    try:
        db = RuntimeDatabase(RUNTIME_DB)

        with db.connect() as connection:
            connection.execute(
                "SELECT 1"
            ).fetchone()

        checks["database"] = True

    except Exception:
        pass

    try:
        loader = CoreLoader(CORE_PATH)
        loader.load()

        checks["core_import"] = True

        checks["constitution"] = (
            len(
                loader.constitution_fingerprint()
            )
            == 64
        )

    except Exception:
        pass

    checks["ok"] = all(
        bool(value)
        for key, value in checks.items()
        if key != "ok"
    )

    return checks


# ============================================================
# CLI
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=RUNTIME_FILENAME,
        description=RUNTIME_NAME,
    )

    parser.add_argument(
        "--self-check",
        action="store_true",
    )

    parser.add_argument(
        "--health",
        action="store_true",
    )

    parser.add_argument(
        "--bootstrap",
        action="store_true",
    )

    parser.add_argument(
        "--maintenance-once",
        action="store_true",
    )

    parser.add_argument(
        "--develop",
        metavar="OBJECTIVE",
    )

    parser.add_argument(
        "--capabilities",
        action="store_true",
    )

    parser.add_argument(
        "--roadmap",
        action="store_true",
    )

    parser.add_argument(
        "--run",
        action="store_true",
    )

    return parser


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    install_signal_handlers()

    args = build_parser().parse_args()

    try:
        if args.self_check:
            result = runtime_self_check()

            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            return 0 if result["ok"] else 1

        runtime = MajdAutonomousRuntime()

        if args.health:
            result = runtime.health()

        elif args.bootstrap:
            result = runtime.bootstrap()

        elif args.maintenance_once:
            result = runtime.maintenance_once()

        elif args.develop:
            result = runtime.develop(
                args.develop
            )

        elif args.capabilities:
            result = (
                CapabilityDiscovery.discover()
            )

        elif args.roadmap:
            result = runtime.roadmap.state()

        else:
            return runtime.run_forever()

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

        return (
            0
            if result.get("ok", True)
            else 1
        )

    except KeyboardInterrupt:
        return 130

    except Exception as exc:
        logger.critical(
            "Fatal autonomous runtime error: %s\n%s",
            SecretGuard.redact(str(exc)),
            SecretGuard.redact(
                traceback.format_exc()
            ),
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
