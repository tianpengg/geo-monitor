import hashlib
import ipaddress
import re
from dataclasses import dataclass
from functools import lru_cache

RULE_VERSION = "2026-10-28.3"


@dataclass(frozen=True)
class Rule:
    token: str
    name: str
    operator: str
    attribution: str
    evidence_url: str | None = None
    documentation_url: str | None = None
    evidence_format: str = "json"
    match_token: str | None = None
    enabled: bool = True
    version: str = RULE_VERSION
    reviewed_at: str = "2026-10-28"


RULES = (
    Rule(
        "KimiBot",
        "Kimi 训练爬虫",
        "Moonshot AI",
        "Kimi",
        "https://www.kimi.ai/policies/kimibot.json",
    ),
    Rule(
        "Kimi-SearchBot",
        "Kimi 搜索爬虫",
        "Moonshot AI",
        "Kimi",
        "https://www.kimi.ai/policies/kimi-searchbot.json",
    ),
    Rule(
        "Kimi-User",
        "Kimi 用户触发访问",
        "Moonshot AI",
        "Kimi",
        "https://www.kimi.ai/policies/kimi-user.json",
    ),
    Rule("Bytespider", "字节跳动爬虫", "字节跳动", "产品归属未确认"),
    Rule(
        "HySpider",
        "腾讯混元训练爬虫",
        "腾讯",
        "产品归属未确认",
        "https://hy.tencent.com/policy/hyspider.json",
    ),
    Rule("GPTBot", "OpenAI 训练爬虫", "OpenAI", "OpenAI", "https://openai.com/gptbot.json"),
    Rule(
        "OAI-SearchBot",
        "ChatGPT 搜索爬虫",
        "OpenAI",
        "ChatGPT",
        "https://openai.com/searchbot.json",
    ),
    Rule(
        "ChatGPT-User",
        "ChatGPT 用户触发访问",
        "OpenAI",
        "ChatGPT",
        "https://openai.com/chatgpt-user.json",
    ),
    Rule(
        "ClaudeBot",
        "Claude 训练爬虫",
        "Anthropic",
        "Claude",
        "https://claude.com/crawling/bots.json",
    ),
    Rule(
        "Claude-SearchBot",
        "Claude 搜索爬虫",
        "Anthropic",
        "Claude",
        "https://claude.com/crawling/bots.json",
    ),
    Rule(
        "Claude-User",
        "Claude 用户触发访问",
        "Anthropic",
        "Claude",
        "https://claude.com/crawling/bots.json",
    ),
    Rule(
        "PerplexityBot",
        "Perplexity 搜索爬虫",
        "Perplexity",
        "Perplexity",
        "https://www.perplexity.ai/perplexitybot.json",
    ),
    Rule(
        "Perplexity-User",
        "Perplexity 用户触发访问",
        "Perplexity",
        "Perplexity",
        "https://www.perplexity.ai/perplexity-user.json",
    ),
    Rule(
        "MistralAI-User",
        "Mistral 用户触发访问",
        "Mistral AI",
        "Vibe",
        "https://mistral.ai/mistralai-user-ips.json",
        "https://docs.mistral.ai/robots",
    ),
    Rule(
        "MistralAI-Index",
        "Mistral 搜索索引爬虫",
        "Mistral AI",
        "Mistral 搜索",
        "https://mistral.ai/mistralai-index-ips.json",
        "https://docs.mistral.ai/robots",
    ),
    Rule(
        "MistralAI-Training",
        "Mistral 训练爬虫",
        "Mistral AI",
        "Mistral AI",
        documentation_url="https://docs.mistral.ai/robots",
    ),
    Rule(
        "Amazonbot",
        "Amazon 通用爬虫",
        "Amazon",
        "Amazon（可能用于模型训练，不代表已训练）",
        "https://developer.amazon.com/amazonbot/ip-addresses/",
        "https://developer.amazon.com/docs/amazonbot/amazonbot.html",
        "amazon-code",
    ),
    Rule(
        "Amzn-SearchBot",
        "Amazon 搜索爬虫",
        "Amazon",
        "Amazon 搜索",
        "https://developer.amazon.com/amazonbot/searchbot-ip-addresses/",
        "https://developer.amazon.com/docs/amazonbot/amazonbot.html",
        "amazon-code",
    ),
    Rule(
        "Amzn-User",
        "Amazon 用户触发访问",
        "Amazon",
        "Amazon 用户请求",
        "https://developer.amazon.com/amazonbot/live-ip-addresses/",
        "https://developer.amazon.com/docs/amazonbot/amazonbot.html",
        "amazon-code",
    ),
    Rule(
        "DuckAssistBot",
        "DuckDuckGo AI 辅助答案爬虫",
        "DuckDuckGo",
        "DuckDuckGo AI 辅助答案",
        "https://duckduckgo.com/duckassistbot.json",
        "https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot",
    ),
)


@lru_cache(maxsize=32)
def patterns(rules: tuple[Rule, ...]):
    return tuple(
        (
            rule,
            re.compile(
                rf"(?<![A-Za-z0-9_-]){re.escape(rule.match_token or rule.token)}(?![A-Za-z0-9_-])",
                re.I,
            ),
        )
        for rule in sorted(
            rules, key=lambda rule: (-len(rule.match_token or rule.token), rule.token.lower())
        )
        if rule.enabled
    )


def identify(user_agent: str, rules: tuple[Rule, ...] = RULES) -> Rule | None:
    product_tokens = re.sub(r"https?://[^\s)]+", "", user_agent, flags=re.I)
    return next((rule for rule, pattern in patterns(rules) if pattern.search(product_tokens)), None)


def mask_ip(address: str) -> str:
    ip = ipaddress.ip_address(address)
    if ip.version == 4:
        return ".".join(str(ip).split(".")[:3]) + ".*"
    return ":".join(ip.exploded.split(":")[:3]) + ":*:*:*:*:*"


def unknown_hint(user_agent: str) -> tuple[str, str] | None:
    tokens = re.findall(r"\b[A-Za-z][A-Za-z-]{1,48}(?:bot|spider|crawler)\b", user_agent, re.I)
    if not tokens:
        return None
    hint = " ".join(sorted({token.lower() for token in tokens}))[:200]
    return hashlib.sha256(hint.encode()).hexdigest(), hint


def coverage(rules: tuple[Rule, ...] = RULES) -> list[dict]:
    return [
        {
            "token": rule.token,
            "name": rule.name,
            "operator": rule.operator,
            "product_attribution": rule.attribution,
            "evidence_source": rule.evidence_url,
            "coverage": "已配置识别规则" if rule.enabled else "已停用",
            "enabled": rule.enabled,
            "documentation_url": rule.documentation_url or rule.evidence_url,
            "rule_version": rule.version,
            "reviewed_at": rule.reviewed_at,
        }
        for rule in rules
    ] + [
        {"token": None, "name": name, "coverage": "识别能力待完善"}
        for name in ["千问", "DeepSeek"]
        if not any(
            rule.enabled and rule.attribution.casefold() == name.casefold() for rule in rules
        )
    ]
