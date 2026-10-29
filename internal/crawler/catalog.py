"""Persisted rule configuration; immutable identifiers keep history addressable."""

import sqlite3
import time
from datetime import UTC, datetime

from internal.crawler.rules import RULE_VERSION, RULES, Rule
from internal.storage.database import Database


class RuleConflict(ValueError):
    pass


class RuleMissing(ValueError):
    pass


class RuleStore:
    def __init__(self, database: Database):
        self.database = database
        self.seeded = False

    def seed(self):
        if self.seeded:
            return
        with self.database.transaction() as conn:
            if not conn.execute("SELECT 1 FROM crawler_rules LIMIT 1").fetchone():
                for rule in RULES:
                    conn.execute(
                        "INSERT INTO crawler_rules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            rule.token,
                            rule.token,
                            rule.name,
                            rule.operator,
                            rule.attribution,
                            rule.evidence_url,
                            rule.documentation_url,
                            rule.evidence_format,
                            1,
                            "builtin",
                            1,
                            RULE_VERSION,
                            time.time(),
                        ),
                    )
        self.seeded = True

    def records(self):
        self.seed()
        with self.database.read() as conn:
            return [
                dict(row)
                for row in conn.execute("SELECT * FROM crawler_rules ORDER BY token COLLATE NOCASE")
            ]

    @staticmethod
    def rule(row):
        return Rule(
            token=row["token"],
            name=row["name"],
            operator=row["operator"],
            attribution=row["product_attribution"],
            evidence_url=row["evidence_url"],
            documentation_url=row["documentation_url"],
            evidence_format=row["evidence_format"],
            match_token=row["match_token"],
            enabled=bool(row["enabled"]),
            version=row["version"],
            reviewed_at=(
                "2026-10-28"
                if row["origin"] == "builtin" and row["revision"] == 1
                else datetime.fromtimestamp(row["updated_at"], UTC).date().isoformat()
            ),
        )

    def snapshot(self):
        return tuple(self.rule(row) for row in self.records())

    def get(self, token):
        return next((row for row in self.records() if row["token"] == token), None)

    def save(self, values: dict, expected_revision: int | None = None):
        self.seed()
        token = values["token"]
        fixed = {
            "Bytespider": ("字节跳动爬虫", "字节跳动"),
            "HySpider": ("腾讯混元训练爬虫", "腾讯"),
        }
        if token in fixed and (
            values["name"],
            values["operator"],
            values["product_attribution"],
        ) != (*fixed[token], "产品归属未确认"):
            raise ValueError("该身份须保留已确认名称、运营方及产品归属未确认口径")
        try:
            with self.database.transaction() as conn:
                current = conn.execute(
                    "SELECT * FROM crawler_rules WHERE token=?", (token,)
                ).fetchone()
                if expected_revision is None:
                    if current:
                        raise RuleConflict("规则标识已存在")
                    if conn.execute("SELECT COUNT(*) FROM crawler_rules").fetchone()[0] >= 256:
                        raise ValueError("最多支持 256 条规则，请编辑或停用已有规则")
                    origin, revision = "custom", 1
                else:
                    if not current:
                        raise RuleMissing("规则不存在")
                    if current["token"] != token or current["revision"] != expected_revision:
                        raise RuleConflict("规则已被其他操作更新，请重新载入后编辑")
                    origin, revision = current["origin"], current["revision"] + 1
                conn.execute(
                    "INSERT INTO crawler_rules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(token) DO UPDATE SET match_token=excluded.match_token,name=excluded.name,operator=excluded.operator,product_attribution=excluded.product_attribution,evidence_url=excluded.evidence_url,documentation_url=excluded.documentation_url,evidence_format=excluded.evidence_format,enabled=excluded.enabled,revision=excluded.revision,version=excluded.version,updated_at=excluded.updated_at",
                    (
                        token,
                        values["match_token"],
                        values["name"],
                        values["operator"],
                        values["product_attribution"],
                        values["evidence_url"],
                        values["documentation_url"],
                        values["evidence_format"],
                        int(values["enabled"]),
                        origin,
                        revision,
                        f"{token}@{revision}",
                        time.time(),
                    ),
                )
                if not current or any(
                    current[key] != values[key]
                    for key in (
                        "match_token",
                        "evidence_url",
                        "evidence_format",
                        "enabled",
                    )
                ):
                    conn.execute("DELETE FROM evidence WHERE crawler=?", (token,))
        except sqlite3.IntegrityError:
            raise RuleConflict("规则标识或 UA 匹配词已存在（不区分大小写）") from None
        return self.get(token)
