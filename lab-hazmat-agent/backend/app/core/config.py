"""全局配置：pydantic-settings，从 .env 读取。

云数据库接入要点（本文件新增的能力）：
- 把 MYSQL_HOST 指向云厂商的内网/公网地址即可，其余参数不用改。
- 云 MySQL（阿里云 RDS / 腾讯云 CDB / 华为云 RDS）通常要求或建议走 TLS：
  置 MYSQL_SSL=true 即可；若厂商提供 CA 证书，把路径写进 MYSQL_SSL_CA。
- 公网访问的云实例首包握手比内网慢，默认 connect_timeout 由 5s 放宽到 10s，
  可用 MYSQL_CONNECT_TIMEOUT 覆盖。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- 大模型与向量（OpenAI 兼容协议）----
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    embed_model: str = "text-embedding-v3"
    llm_timeout: int = 60

    # ---- MySQL ----
    # 本地 Docker 默认值；接云数据库时改成云实例地址（内网地址更快且不计公网流量）
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_db: str = "lab_hazmat"
    mysql_user: str = "lab_readonly"
    mysql_password: str = ""
    mysql_charset: str = "utf8mb4"
    mysql_pool_min: int = 1
    mysql_pool_max: int = 10
    mysql_pool_recycle: int = 1800
    mysql_connect_timeout: int = 10
    # 云实例走 TLS。MYSQL_SSL=true 表示加密但不校验证书（云内网常见够用）；
    # 需要严格校验时给出 MYSQL_SSL_CA 指向厂商 CA 证书。
    mysql_ssl: bool = False
    mysql_ssl_ca: str = ""

    # 建表脚本位置（NL2SQL 的 DDL 上下文来源）。留空则自动按候选路径查找。
    mysql_ddl_path: str = ""

    # ---- 向量库 ----
    chroma_dir: str = "/data/chroma"

    # ---- 业务可调参数（不重新发版即可调整）----
    loss_threshold_ratio: float = 0.05
    loss_threshold_abs: float = 1.0
    access_check_concurrency: int = 5
    session_ttl_seconds: int = 3600

    # ---- 只读护栏 ----
    sql_max_rows: int = 200
    sql_timeout_ms: int = 8000

    # ---- RAG 检索 ----
    # 余弦相关度阈值（0~1）。Chroma 默认 l2 距离下相关度几乎没有区分度，
    # 因此检索器把向量空间显式固定为 cosine，阈值才有意义。
    rag_score_threshold: float = 0.30
    rag_fetch_k: int = 20
    rag_top_k: int = 4

    # ---- 运行 ----
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mysql_ssl_args(self) -> dict:
        """转成 aiomysql/PyMySQL 的 ssl 参数。"""
        if not self.mysql_ssl and not self.mysql_ssl_ca:
            return {}
        if self.mysql_ssl_ca:
            return {"ssl": {"ca": self.mysql_ssl_ca}}
        return {"ssl": {"check_hostname": False, "verify_mode": False}}

    @property
    def mysql_endpoint(self) -> str:
        """日志用的端点描述，不含口令。"""
        return f"{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"

    def _ddl_dirs(self) -> list[Path]:
        """建表脚本候选目录：本机仓库布局、容器挂载路径、相对 CWD。"""
        return [
            _PROJECT_ROOT / "mysql" / "init",   # 本机仓库布局
            Path("/app/mysql/init"),            # 容器挂载路径
            Path.cwd() / "mysql" / "init",
            Path.cwd().parent / "mysql" / "init",
        ]

    def resolve_ddl_paths(self) -> list[Path]:
        """定位**全部**建表脚本，供 NL2SQL 拼接表结构上下文。

        原实现只认单个 `01_schema.sql`，导致后来新增的 `05_equipment.sql`
        （equipment / equipment_loans）从未进入提示词——模型能猜列名却不知道
        这两张表存在。这里改成扫描 init 目录下所有含 CREATE TABLE 的 .sql，
        按文件名排序返回，今后新增建表脚本无需改代码即可自动纳入。

        MYSQL_DDL_PATH 仍可显式覆盖：指向文件则只用该文件，指向目录则扫描其中脚本。
        """
        if self.mysql_ddl_path:
            p = Path(self.mysql_ddl_path)
            if p.is_file():
                return [p]
            if p.is_dir():
                return _collect_ddl_scripts(p)
            return []
        for d in self._ddl_dirs():
            if d.is_dir():
                found = _collect_ddl_scripts(d)
                if found:
                    return found
        return []

    def resolve_ddl_path(self) -> Path | None:
        """首个建表脚本。保留旧接口：日志与启动自检按「主脚本」展示。"""
        paths = self.resolve_ddl_paths()
        return paths[0] if paths else None


def _collect_ddl_scripts(directory: Path) -> list[Path]:
    """挑出目录中的建表脚本：内容含 CREATE TABLE 的 .sql，按文件名排序。

    用内容判断而非文件名前缀：既能把 03_seed.sql / 07_lab_categories_seed.sql
    这类纯 INSERT 脚本排除在外（数据行会白白撑大提示词、且与表结构无关），
    也让未来任何新增的建表脚本自动生效。
    """
    found: list[Path] = []
    for p in sorted(directory.glob("*.sql")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "create table" in text.lower():
            found.append(p)
    return found


@lru_cache
def get_settings() -> Settings:
    return Settings()
