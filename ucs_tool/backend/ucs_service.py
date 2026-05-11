import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import urlparse


HOST = os.environ.get("ENZ_UCS_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENZ_UCS_PORT", "8000"))
SERVICE_VERSION = "0.4.0-embedding-preview"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOOL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = TOOL_DIR / "config.json"
VENV_DIR = TOOL_DIR / ".venv-ucs"
MIN_SCORE = 7.0
HIGH_CONFIDENCE_SCORE = 22.0
MEDIUM_CONFIDENCE_SCORE = 12.0
SEMANTIC_MIN_SCORE = 5.0
SEMANTIC_TOP_LIMIT = 24
FTS_TOP_LIMIT = 64
FTS_SCORE_SCALE = 6.0
EMBEDDING_TOP_LIMIT = 24
EMBEDDING_MIN_SIMILARITY = 0.28
EMBEDDING_SCORE_SCALE = 28.0
FX_EMBEDDING_TOP_LIMIT = 3
FX_EMBEDDING_MIN_SIMILARITY = 0.48


TOKEN_ALIASES = {
    "石头": ["岩石", "石块", "石子", "rock", "stone"],
    "石块": ["岩石", "石头", "rock", "stone"],
    "石子": ["岩石", "石头", "gravel", "pebble"],
    "石": ["岩石", "rock", "stone"],
    "地面": ["地表", "地上", "ground", "floor"],
}


SEMANTIC_BOOSTS = [
    {
        "name": "元素魔法",
        "required": ["魔法", "法术", "施法", "咒语", "巫术"],
        "any": ["元素", "火", "水", "土", "电", "雷", "气", "风", "冰", "木", "树", "植物", "自然", "生长"],
        "cat_ids": ["MAGElem"],
        "score": 13.0,
    },
    {
        "name": "邪恶魔法",
        "required": ["魔法", "法术", "施法", "咒语", "巫术"],
        "any": ["邪恶", "恶魔", "黑暗", "死亡", "死灵", "诅咒", "禁术", "黑魔法"],
        "cat_ids": ["MAGEvil"],
        "score": 15.0,
    },
    {
        "name": "神圣魔法",
        "required": ["魔法", "法术", "施法", "咒语", "巫术"],
        "any": ["神圣", "天使", "祝福", "圣洁", "治愈", "天堂"],
        "cat_ids": ["MAGAngl"],
        "score": 14.0,
    },
    {
        "name": "飞行火焰",
        "required": ["火", "火焰", "火球"],
        "any": ["飞", "飞行", "划过", "呼啸", "掠过", "嗖", "快速"],
        "cat_ids": ["FIREWhsh"],
        "score": 8.0,
    },
    {
        "name": "金属摩擦",
        "required": ["金属", "铁", "钢", "铜", "铝"],
        "any": ["摩擦", "刮擦", "刮", "磨", "蹭", "划", "擦"],
        "cat_ids": ["METLFric"],
        "score": 18.0,
    },
    {
        "name": "刀具语境",
        "required": ["刀", "刀具", "刀片", "匕首", "菜刀"],
        "any": ["摩擦", "刮擦", "刮", "磨", "蹭", "划", "擦", "金属"],
        "cat_ids": ["METLFric", "WEAPKnif"],
        "score": 7.0,
    },
    {
        "name": "岩石撞击",
        "required": ["石头", "岩石", "石块", "石子"],
        "any": ["撞击", "碰撞", "击打", "砸", "撞", "碰", "掉落", "跌落", "地面"],
        "cat_ids": ["ROCKImpt"],
        "score": 24.0,
    },
    {
        "name": "植物生长",
        "required": ["植物", "树", "木", "木头", "藤蔓", "草"],
        "any": ["生长", "长出", "发芽", "蔓延", "伸展"],
        "cat_ids": ["VEGEMisc", "VEGETree"],
        "score": 8.0,
    },
]


def resource_dir():
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "data"
    env_dir = os.environ.get("ENZ_UCS_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parent / "data"


def load_json(name):
    path = resource_dir() / name
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_tool_config():
    if not CONFIG_PATH.exists():
        return {
            "embedding_enabled": False,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
        }
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        payload = {}
    return {
        "embedding_enabled": bool(payload.get("embedding_enabled")),
        "embedding_model": str(payload.get("embedding_model") or DEFAULT_EMBEDDING_MODEL),
    }


def save_tool_config(config):
    payload = load_tool_config()
    payload.update(config)
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return payload


def normalize_text(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[\s\t\r\n]+", "", text)
    return re.sub(r"[，。！？、,.!?;；:：\"'“”‘’（）()\[\]{}<>《》]", "", text)


def normalize_english(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def unique_keep_order(values):
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def english_label(value):
    words = re.findall(r"[A-Za-z0-9]+", value or "")
    return "".join(word[:1].upper() + word[1:].lower() for word in words)


def token_score(description, token, weight):
    token = normalize_text(token)
    if not token:
        return 0.0
    if token in description:
        # Longer terms are more intentional than one-character fragments.
        return weight + min(len(token), 8) * 0.45
    return 0.0


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_str(value):
    return str(value) if value is not None else ""


def zh_ngrams(value, sizes=(2, 3)):
    value = normalize_text(value)
    if not value:
        return []
    tokens = [value]
    for size in sizes:
        if len(value) < size:
            continue
        for index in range(0, len(value) - size + 1):
            tokens.append(value[index : index + size])
    return tokens


def en_tokens(value):
    return re.findall(r"\b[a-zA-Z0-9]+\b", (value or "").lower())


NOISE_TOKENS = {
    "sfx",
    "fx",
    "sound",
    "sounds",
    "audio",
    "take",
    "item",
    "track",
    "clip",
    "loop",
    "one",
    "two",
    "three",
    "new",
    "old",
    "final",
    "edit",
    "v1",
    "v2",
    "v3",
    "wav",
    "mp3",
    "aif",
    "aiff",
    "flac",
}


def filter_noise_keywords(tokens):
    filtered = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token.lower() in NOISE_TOKENS:
            continue
        filtered.append(token)
    return filtered


def expand_token_aliases(tokens):
    expanded = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(TOKEN_ALIASES.get(normalize_text(token), []))
    return expanded


def has_any_term(normalized, terms):
    return any(normalize_text(term) in normalized for term in terms if normalize_text(term))


def semantic_features(value, weight=1.0):
    features = Counter()
    normalized = normalize_text(value)
    if normalized:
        features[f"full:{normalized}"] += weight * 2.4
        for size, size_weight in ((1, 0.18), (2, 1.0), (3, 0.72), (4, 0.42)):
            if len(normalized) >= size:
                for index in range(0, len(normalized) - size + 1):
                    token = normalized[index : index + size]
                    if size == 1 and not re.match(r"[\u4e00-\u9fff]", token):
                        continue
                    features[f"zh{size}:{token}"] += weight * size_weight

    english = normalize_english(value)
    if english:
        words = english.split()
        for word in words:
            if len(word) > 1:
                features[f"en:{word}"] += weight * 0.9
        for index in range(len(words) - 1):
            features[f"en2:{words[index]} {words[index + 1]}"] += weight * 1.2

    return features


def merge_counter(target, source):
    for key, value in source.items():
        target[key] += value


def vector_norm(vector):
    return math.sqrt(sum(value * value for value in vector.values()))


def cosine_similarity(left, left_norm, right, right_norm):
    if not left_norm or not right_norm:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    return dot / (left_norm * right_norm)


class EmbeddingBackend:
    def __init__(self, entries, aliases):
        self.enabled = False
        config = load_tool_config()
        env_model = os.environ.get("ENZ_UCS_EMBEDDING_MODEL", "").strip()
        self.model_name = env_model
        if not self.model_name and config.get("embedding_enabled"):
            self.model_name = str(config.get("embedding_model") or DEFAULT_EMBEDDING_MODEL).strip()
        self.reason = "ENZ_UCS_EMBEDDING_MODEL not set"
        self.doc_count = 0
        self.model = None
        self.embeddings = None
        self.cat_ids = []
        self.texts = []

        if not self.model_name:
            return

        try:
            from sentence_transformers import SentenceTransformer

            alias_terms_by_cat_id = self.alias_terms_by_cat_id(aliases)
            self.cat_ids = [entry["cat_id"] for entry in entries]
            self.texts = [
                self.entry_text(entry, alias_terms_by_cat_id.get(entry["cat_id"], []))
                for entry in entries
            ]
            self.model = SentenceTransformer(self.model_name)
            self.embeddings = self.model.encode(
                self.texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            self.enabled = True
            self.reason = "ok"
            self.doc_count = len(self.cat_ids)
        except Exception as exc:
            self.enabled = False
            self.model = None
            self.embeddings = None
            self.reason = f"{exc.__class__.__name__}: {exc}"

    @staticmethod
    def alias_terms_by_cat_id(aliases):
        terms_by_cat_id = {}
        for alias in aliases:
            for cat_id in alias.get("cat_ids", []):
                terms_by_cat_id.setdefault(cat_id, []).extend(alias.get("terms", []))
        return terms_by_cat_id

    @staticmethod
    def entry_text(entry, alias_terms):
        parts = [
            f"UCS CatID: {entry.get('cat_id', '')}",
            f"英文分类: {entry.get('category', '')} {entry.get('subcategory', '')}",
            f"中文分类: {entry.get('zh_category', '')} / {entry.get('zh_subcategory', '')}",
            f"中文同义词: {'、'.join(entry.get('zh_synonyms', []))}",
            f"英文同义词: {', '.join(entry.get('en_synonyms', []))}",
            f"中文别名: {'、'.join(alias_terms)}",
            f"说明: {entry.get('explanation', '')}",
            (
                "这是声音素材的UCS分类说明，用来判断用户自然语言描述应该归入哪一个声音类别。"
            ),
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    @staticmethod
    def query_text(description, context):
        parts = [f"中文描述: {description or ''}"]
        for key, label in (
            ("filename", "文件名"),
            ("fxname", "FXName"),
            ("keywords", "关键词"),
            ("category", "已有分类"),
            ("subcategory", "已有子类"),
            ("notes", "备注"),
        ):
            value = context.get(key) if context else None
            if value:
                parts.append(f"{label}: {value}")
        return "\n".join(parts)

    def search(self, description, context=None):
        if not self.enabled:
            return {}, {}

        query = self.query_text(description, context or {})
        query_vector = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        similarities = self.embeddings @ query_vector
        indexed = sorted(
            enumerate(float(value) for value in similarities),
            key=lambda item: item[1],
            reverse=True,
        )[:EMBEDDING_TOP_LIMIT]

        results = {}
        reasons = {}
        for index, similarity in indexed:
            if similarity < EMBEDDING_MIN_SIMILARITY:
                continue
            score = (
                (similarity - EMBEDDING_MIN_SIMILARITY)
                / (1.0 - EMBEDDING_MIN_SIMILARITY)
                * EMBEDDING_SCORE_SCALE
            )
            cat_id = self.cat_ids[index]
            results[cat_id] = round(score, 4)
            reasons.setdefault(cat_id, []).append(f"模型相似 {similarity:.3f}")
        return results, reasons

    def status(self):
        return {
            "enabled": self.enabled,
            "model": self.model_name or None,
            "reason": self.reason,
            "doc_count": self.doc_count,
            "min_similarity": EMBEDDING_MIN_SIMILARITY,
        }


def canonical_fx_label(value):
    label = english_label(value)
    if not label:
        return ""
    aliases = {
        "Textured": "Texture",
        "Textural": "Texture",
        "Textures": "Texture",
        "Tones": "Tonal",
        "Tone": "Tonal",
    }
    return aliases.get(label, label)


class UCSMatcher:
    def __init__(self):
        ucs_payload = load_json("ucs_v8_2_1_zh.json")
        alias_payload = load_json("zh_aliases.json")
        fx_payload = load_json("fx_terms.json")

        self.entries = ucs_payload["entries"]
        self.entry_by_id = {entry["cat_id"]: entry for entry in self.entries}
        self.aliases = alias_payload.get("aliases", [])
        self.fx_terms = fx_payload.get("terms", [])
        self.fx_matchers = self.build_fx_matchers()
        self.semantic_docs = self.build_semantic_docs()
        self.fts_lock = Lock()
        self.fts_conn = self.build_fts_index()
        self.embedding_backend = EmbeddingBackend(self.entries, self.aliases)
        self.fx_embedding_docs = self.build_fx_embedding_docs()
        self.fx_embedding_vectors = self.build_fx_embedding_vectors()

        missing_aliases = sorted(
            {
                cat_id
                for alias in self.aliases
                for cat_id in alias.get("cat_ids", [])
                if cat_id not in self.entry_by_id
            }
        )
        if missing_aliases:
            raise RuntimeError(f"Aliases reference unknown CatID values: {missing_aliases}")

    def build_fts_index(self):
        alias_terms_by_cat_id = {}
        for alias in self.aliases:
            for cat_id in alias.get("cat_ids", []):
                alias_terms_by_cat_id.setdefault(cat_id, []).extend(alias.get("terms", []))

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("CREATE VIRTUAL TABLE ucs_fts USING fts5(cat_id UNINDEXED, category UNINDEXED, tokens)")

        for entry in self.entries:
            tokens = []
            for text in (
                entry.get("cat_id", ""),
                entry.get("category", ""),
                entry.get("subcategory", ""),
                entry.get("zh_category", ""),
                entry.get("zh_subcategory", ""),
            ):
                tokens.extend(zh_ngrams(text))
                tokens.extend(en_tokens(text))

            for term in entry.get("zh_synonyms", []):
                tokens.extend(zh_ngrams(term))
            for term in entry.get("en_synonyms", []):
                tokens.extend(en_tokens(term))
            for term in alias_terms_by_cat_id.get(entry["cat_id"], []):
                tokens.extend(zh_ngrams(term))

            tokens = filter_noise_keywords(unique_keep_order(tokens))
            conn.execute(
                "INSERT INTO ucs_fts(cat_id, category, tokens) VALUES (?,?,?)",
                (entry["cat_id"], entry["category"], " ".join(tokens)),
            )

        return conn

    def extract_weighted_tokens(self, payload):
        items = []
        for field, weight in (
            ("fxname", 1.5),
            ("keywords", 1.5),
            ("filename", 1.0),
            ("description", 1.0),
            ("category", 1.0),
            ("subcategory", 1.0),
            ("notes", 0.5),
        ):
            value = payload.get(field)
            if not value:
                continue
            value = str(value)
            if field == "filename":
                parts = re.split(r"[\s_\-]+", value)
                value = " ".join(parts)

            tokens = []
            tokens.extend(en_tokens(value))
            tokens.extend(zh_ngrams(value))
            tokens = expand_token_aliases(tokens)
            tokens = filter_noise_keywords(tokens)
            for token in tokens:
                if len(token) < 2:
                    continue
                items.append((token, float(weight)))

        combined = {}
        for token, weight in items:
            combined[token] = max(combined.get(token, 0.0), weight)

        normalized = [(token, combined[token]) for token in sorted(combined)]
        return normalized

    def fts_retrieval(self, weighted_tokens):
        if not weighted_tokens:
            return {}, {}

        query_terms = []
        for token, weight in weighted_tokens:
            token = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", token)
            if len(token) < 2:
                continue
            repeat = 1
            if weight >= 1.0:
                repeat = 3
            elif weight >= 0.8:
                repeat = 2
            query_terms.extend([token] * repeat)

        if not query_terms:
            return {}, {}

        query = " OR ".join(query_terms)
        results = {}
        reasons = {}

        with self.fts_lock:
            cursor = self.fts_conn.execute(
                "SELECT cat_id, category, rank FROM ucs_fts WHERE ucs_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, FTS_TOP_LIMIT),
            )
            for cat_id, category, rank in cursor.fetchall():
                score = math.log1p(abs(float(rank))) * FTS_SCORE_SCALE
                results[cat_id] = results.get(cat_id, 0.0) + score
                reasons.setdefault(cat_id, []).append(f"FTS {score:.1f}")

        return results, reasons

    def build_semantic_docs(self):
        alias_terms_by_cat_id = {}
        for alias in self.aliases:
            for cat_id in alias.get("cat_ids", []):
                alias_terms_by_cat_id.setdefault(cat_id, []).extend(alias.get("terms", []))

        docs = {}
        for entry in self.entries:
            vector = Counter()
            fields = [
                (entry.get("cat_id", ""), 7.0),
                (entry.get("category", ""), 3.0),
                (entry.get("subcategory", ""), 4.0),
                (entry.get("zh_category", ""), 6.0),
                (entry.get("zh_subcategory", ""), 7.0),
                (entry.get("explanation", ""), 1.0),
            ]
            for text, weight in fields:
                merge_counter(vector, semantic_features(text, weight))
            for term in entry.get("zh_synonyms", []):
                merge_counter(vector, semantic_features(term, 5.0))
            for term in entry.get("en_synonyms", []):
                merge_counter(vector, semantic_features(term, 2.2))
            if entry.get("category") == "ROCKS":
                for term in ["石头", "石块", "石子", "石"]:
                    merge_counter(vector, semantic_features(term, 5.0))
            for term in alias_terms_by_cat_id.get(entry["cat_id"], []):
                merge_counter(vector, semantic_features(term, 8.0))

            docs[entry["cat_id"]] = {
                "vector": vector,
                "norm": vector_norm(vector),
            }
        return docs

    def semantic_query_vector(self, description):
        vector = semantic_features(description, 1.0)
        normalized = normalize_text(description)

        for item in self.fx_terms:
            english = item.get("en", "")
            for term in item.get("zh", []):
                term_norm = normalize_text(term)
                if term_norm and term_norm in normalized:
                    merge_counter(vector, semantic_features(english, 1.2))

        return vector

    def semantic_scores(self, description):
        vector = self.semantic_query_vector(description)
        norm = vector_norm(vector)
        results = {}
        reasons = {}

        for cat_id, doc in self.semantic_docs.items():
            similarity = cosine_similarity(vector, norm, doc["vector"], doc["norm"])
            if similarity <= 0:
                continue
            score = similarity * 24.0
            if score >= SEMANTIC_MIN_SCORE:
                results[cat_id] = score
                reasons.setdefault(cat_id, []).append(f"语义相似 {score:.1f}")

        normalized = normalize_text(description)
        for boost in SEMANTIC_BOOSTS:
            if not has_any_term(normalized, boost["required"]):
                continue
            if not has_any_term(normalized, boost["any"]):
                continue
            for cat_id in boost["cat_ids"]:
                if cat_id in self.entry_by_id:
                    results[cat_id] = results.get(cat_id, 0.0) + float(boost["score"])
                    reasons.setdefault(cat_id, []).append(boost["name"])

        top_ids = sorted(results, key=lambda cat_id: (-results[cat_id], cat_id))[:SEMANTIC_TOP_LIMIT]
        return {cat_id: results[cat_id] for cat_id in top_ids}, reasons

    def build_fx_matchers(self):
        matchers = []
        manual_overrides = [
            {"zh": ["摩擦", "磨擦", "蹭", "擦"], "en": "Friction"},
            {"zh": ["刮擦", "刮", "划"], "en": "Scrape"},
            {"zh": ["刀", "刀具", "刀片", "匕首", "菜刀"], "en": "Knife"},
        ]

        for priority, item in enumerate(manual_overrides + self.fx_terms):
            english = item.get("en", "")
            for term in item.get("zh", []):
                term_norm = normalize_text(term)
                if len(term_norm) >= 2 or term_norm in {"刀", "刮", "划", "蹭", "擦"}:
                    matchers.append(
                        {
                            "term": term_norm,
                            "english": english,
                            "priority": 1000 - priority,
                            "source": "manual",
                        }
                    )

        generated = {}
        for entry in self.entries:
            generated[normalize_text(entry.get("zh_category", ""))] = english_label(
                entry.get("category", "")
            )
            generated[normalize_text(entry.get("zh_subcategory", ""))] = english_label(
                entry.get("subcategory", "")
            )

        for term, english in generated.items():
            if len(term) >= 2 and english and term not in {"其它", "其他"}:
                matchers.append(
                    {
                        "term": term,
                        "english": english,
                        "priority": 1,
                        "source": "ucs",
                    }
                )

        synonym_votes = {}
        for entry in self.entries:
            english = english_label(entry.get("subcategory", ""))
            if not english:
                continue
            for term in entry.get("zh_synonyms", []):
                term_norm = normalize_text(term)
                if len(term_norm) < 2:
                    continue
                synonym_votes.setdefault(term_norm, Counter())[english] += 1

        for term, votes in synonym_votes.items():
            total = sum(votes.values())
            english, count = votes.most_common(1)[0]
            if count < 2 or count / total < 0.65:
                continue
            matchers.append(
                {
                    "term": term,
                    "english": english,
                    "priority": 20,
                    "source": "ucs_synonym",
                }
            )

        matchers.sort(key=lambda item: (-len(item["term"]), -item["priority"], item["term"]))
        return matchers

    def build_fx_embedding_docs(self):
        docs = {}
        for item in self.fx_terms:
            label = canonical_fx_label(item.get("en", ""))
            if not label:
                continue
            docs.setdefault(label, []).append(
                "FXName描述词: "
                + label
                + "\n中文表达: "
                + "、".join(item.get("zh", []))
                + "\n用于声音素材命名中的修饰词、质感、动作或场景。"
            )

        for entry in self.entries:
            context = " / ".join(
                part
                for part in (
                    entry.get("category", ""),
                    entry.get("subcategory", ""),
                    entry.get("zh_category", ""),
                    entry.get("zh_subcategory", ""),
                )
                if part
            )
            zh_terms = "、".join(entry.get("zh_synonyms", []))
            explanation = entry.get("explanation", "")
            for term in entry.get("en_synonyms", []):
                label = canonical_fx_label(term)
                if len(label) < 3 or len(label) > 24:
                    continue
                docs.setdefault(label, []).append(
                    f"FXName描述词: {label}\nUCS上下文: {context}\n中文同义词: {zh_terms}\n说明: {explanation}"
                )

        return [
            {"english": english, "text": "\n---\n".join(parts[:8])}
            for english, parts in sorted(docs.items())
        ]

    def build_fx_embedding_vectors(self):
        if (
            os.environ.get("ENZ_UCS_FX_EMBEDDING", "").strip() != "1"
            or not self.embedding_backend.enabled
            or not self.fx_embedding_docs
        ):
            return None
        try:
            return self.embedding_backend.model.encode(
                [doc["text"] for doc in self.fx_embedding_docs],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception:
            return None

    def parse(self, description, context=None):
        context = context or {}
        normalized = normalize_text(description)
        english = normalize_english(description)
        magic_context = has_any_term(normalized, ["魔法", "法术", "施法", "咒语", "巫术", "魔力"])
        rain_context = has_any_term(normalized, ["雨", "下雨", "雨滴", "雨水", "雨声", "暴雨", "小雨", "阵雨"])

        if not normalized:
            return self.fallback(description, [])

        rule_scores = {}
        reasons = {}
        rule_details = {}
        for entry in self.entries:
            cat_id = entry["cat_id"]
            score = 0.0
            matched = []

            direct = token_score(normalized, cat_id, 28.0)
            if direct:
                score += direct
                matched.append(cat_id)
                rule_details.setdefault(cat_id, []).append({"src": "cat_id", "token": cat_id, "delta": round(direct, 2)})

            for field, weight in (
                ("zh_category", 5.0),
                ("zh_subcategory", 7.0),
            ):
                if entry.get("category") == "RAIN" and field == "zh_subcategory" and not rain_context:
                    continue
                value_score = token_score(normalized, entry.get(field, ""), weight)
                if value_score:
                    score += value_score
                    matched.append(entry[field])
                    rule_details.setdefault(cat_id, []).append(
                        {"src": field, "token": entry.get(field, ""), "delta": round(value_score, 2)}
                    )

            for term in entry.get("zh_synonyms", []):
                if cat_id == "MAGElem" and normalize_text(term) in {"火", "水", "土", "电", "气", "风"} and not magic_context:
                    continue
                if entry.get("category") == "RAIN" and normalize_text(term) not in {"雨", "雨滴", "雨水", "下雨"} and not rain_context:
                    continue
                value_score = token_score(normalized, term, 9.0)
                if value_score:
                    score += value_score
                    matched.append(term)
                    rule_details.setdefault(cat_id, []).append(
                        {"src": "zh_synonym", "token": term, "delta": round(value_score, 2)}
                    )

            if english:
                for term in entry.get("en_synonyms", []):
                    term_norm = normalize_english(term)
                    if term_norm and re.search(rf"\b{re.escape(term_norm)}\b", english):
                        score += 4.0
                        matched.append(term)
                        rule_details.setdefault(cat_id, []).append(
                            {"src": "en_synonym", "token": term, "delta": 4.0}
                        )

            if score:
                rule_scores[cat_id] = rule_scores.get(cat_id, 0.0) + score
                reasons.setdefault(cat_id, []).extend(matched)

        for alias in self.aliases:
            alias_weight = float(alias.get("weight", 10.0))
            matched_terms = []
            for term in alias.get("terms", []):
                value_score = token_score(normalized, term, alias_weight)
                if value_score:
                    matched_terms.append(term)
            if not matched_terms:
                continue
            for cat_id in alias.get("cat_ids", []):
                alias_delta = sum(
                    alias_weight + min(len(term), 8) * 0.45 for term in matched_terms
                )
                rule_scores[cat_id] = rule_scores.get(cat_id, 0.0) + alias_delta
                reasons.setdefault(cat_id, []).extend(matched_terms)
                rule_details.setdefault(cat_id, []).append(
                    {"src": "alias", "token": ",".join(matched_terms[:6]), "delta": round(alias_delta, 2)}
                )

        semantic_scores, semantic_reasons = self.semantic_scores(description)
        context_payload = {"description": description, **context}
        weighted_tokens = self.extract_weighted_tokens(context_payload)
        fts_scores, fts_reasons = self.fts_retrieval(weighted_tokens)
        embedding_scores, embedding_reasons = self.embedding_backend.search(description, context)
        combined_scores = {}
        for cat_id, score in rule_scores.items():
            combined_scores[cat_id] = combined_scores.get(cat_id, 0.0) + score
        for cat_id, score in semantic_scores.items():
            combined_scores[cat_id] = combined_scores.get(cat_id, 0.0) + score
            reasons.setdefault(cat_id, []).extend(semantic_reasons.get(cat_id, []))
        for cat_id, score in fts_scores.items():
            combined_scores[cat_id] = combined_scores.get(cat_id, 0.0) + score
            reasons.setdefault(cat_id, []).extend(fts_reasons.get(cat_id, []))
        for cat_id, score in embedding_scores.items():
            combined_scores[cat_id] = combined_scores.get(cat_id, 0.0) + score
            reasons.setdefault(cat_id, []).extend(embedding_reasons.get(cat_id, []))

        # Scope lock: if one main category is clearly dominant, penalize cross-category noise.
        main_best = {}
        for cat_id, score in combined_scores.items():
            entry = self.entry_by_id.get(cat_id)
            if not entry:
                continue
            category = entry.get("category")
            main_best[category] = max(main_best.get(category, 0.0), float(score))
        ordered_main = sorted(main_best.items(), key=lambda item: -item[1])
        if ordered_main:
            best_cat, best_score = ordered_main[0]
            second_score = ordered_main[1][1] if len(ordered_main) > 1 else 0.0
            if best_score >= 18.0 and best_score - second_score >= 6.0:
                for cat_id in list(combined_scores.keys()):
                    entry = self.entry_by_id.get(cat_id)
                    if not entry:
                        continue
                    if entry.get("category") != best_cat:
                        combined_scores[cat_id] *= 0.65
                        reasons.setdefault(cat_id, []).append(f"scope_lock:{best_cat}")

        candidates = self.build_candidates(
            combined_scores,
            reasons,
            rule_scores=rule_scores,
            semantic_scores=semantic_scores,
            fts_scores=fts_scores,
            embedding_scores=embedding_scores,
            rule_details=rule_details,
        )
        if not candidates or candidates[0]["score"] < MIN_SCORE:
            return self.fallback(description, candidates)

        best = candidates[0]
        entry = self.entry_by_id[best["ucs_prefix"]]
        fx_name = self.extract_fx_name(normalized, entry)
        confidence = self.confidence(candidates)
        return {
            "status": "success",
            "data": {
                "category": entry["category"],
                "subcategory": entry["subcategory"],
                "ucs_prefix": entry["cat_id"],
                "fx_name": fx_name,
                "confidence": confidence,
                "score": best["score"],
                "candidates": candidates[:3],
                "fallback": False,
            },
            "message": "",
        }

    def build_candidates(
        self,
        scores,
        reasons,
        rule_scores=None,
        semantic_scores=None,
        fts_scores=None,
        embedding_scores=None,
        rule_details=None,
    ):
        rule_scores = rule_scores or {}
        semantic_scores = semantic_scores or {}
        fts_scores = fts_scores or {}
        embedding_scores = embedding_scores or {}
        rule_details = rule_details or {}
        candidates = []
        for cat_id, score in scores.items():
            entry = self.entry_by_id[cat_id]
            candidates.append(
                {
                    "ucs_prefix": cat_id,
                    "category": entry["category"],
                    "subcategory": entry["subcategory"],
                    "zh_category": entry["zh_category"],
                    "zh_subcategory": entry["zh_subcategory"],
                    "score": round(score, 2),
                    "rule_score": round(rule_scores.get(cat_id, 0.0), 2),
                    "semantic_score": round(semantic_scores.get(cat_id, 0.0), 2),
                    "fts_score": round(fts_scores.get(cat_id, 0.0), 2),
                    "embedding_score": round(embedding_scores.get(cat_id, 0.0), 2),
                    "matched_terms": unique_keep_order(reasons.get(cat_id, []))[:8],
                    "explain": {
                        "rule_hits": sorted(rule_details.get(cat_id, []), key=lambda item: -float(item["delta"]))[:8],
                    },
                }
            )
        candidates.sort(key=lambda item: (-item["score"], item["ucs_prefix"]))
        return candidates

    def model_status(self):
        config = load_tool_config()
        return {
            "service_version": SERVICE_VERSION,
            "embedding": self.embedding_backend.status(),
            "config": config,
            "venv_python": str(VENV_DIR / "bin" / "python"),
            "venv_exists": (VENV_DIR / "bin" / "python").exists(),
        }

    def confidence(self, candidates):
        if not candidates:
            return "low"
        top = candidates[0]["score"]
        second = candidates[1]["score"] if len(candidates) > 1 else 0.0
        margin = top - second
        if top >= HIGH_CONFIDENCE_SCORE and margin >= 4.0:
            return "high"
        if top >= MEDIUM_CONFIDENCE_SCORE:
            return "medium"
        return "low"

    def excluded_fx_terms(self, entry):
        if not entry:
            return set()
        terms = {
            normalize_text(entry.get("zh_category", "")),
            normalize_text(entry.get("zh_subcategory", "")),
        }
        terms.update(normalize_text(term) for term in entry.get("zh_synonyms", []))
        if entry.get("category") == "MAGIC":
            terms.update(normalize_text(term) for term in ["魔法", "魔法感", "法术", "咒语", "施法", "巫术"])
        if entry.get("category") == "ROCKS":
            terms.update(normalize_text(term) for term in ["岩石", "石头", "石块", "石子", "石"])
        if entry.get("subcategory") == "FRICTION":
            terms.update(normalize_text(term) for term in ["摩擦", "磨擦", "刮擦", "刮", "划", "蹭", "擦"])
        return {term for term in terms if term}

    def extract_fx_name(self, normalized_description, selected_entry=None):
        excluded_terms = self.excluded_fx_terms(selected_entry)
        hits = []
        occupied = [False] * len(normalized_description)
        for term in sorted(excluded_terms, key=len, reverse=True):
            search_at = 0
            while term:
                pos = normalized_description.find(term, search_at)
                if pos < 0:
                    break
                for index in range(pos, pos + len(term)):
                    if 0 <= index < len(occupied):
                        occupied[index] = True
                search_at = pos + 1

        for item in self.fx_matchers:
            term = item["term"]
            if term in excluded_terms:
                continue
            search_at = 0
            while True:
                pos = normalized_description.find(term, search_at)
                if pos < 0:
                    break
                end = pos + len(term)
                if not any(occupied[pos:end]):
                    for index in range(pos, end):
                        occupied[index] = True
                    hits.append((pos, item["english"], term, item["source"]))
                search_at = pos + 1

        hits.sort(key=lambda value: (value[0], -len(value[2]), value[1]))
        ordered = unique_keep_order([english for _, english, _, _ in hits])
        residual = "".join(
            char for index, char in enumerate(normalized_description) if not occupied[index]
        )
        ordered.extend(self.extract_fx_name_with_model(residual, set(ordered)))
        ordered = unique_keep_order(ordered)
        return "_".join(clean_fx_token(value) for value in ordered if clean_fx_token(value))

    def extract_fx_name_with_model(self, residual, existing):
        residual = normalize_text(residual)
        if (
            not residual
            or len(residual) < 2
            or os.environ.get("ENZ_UCS_FX_EMBEDDING", "").strip() != "1"
            or not self.embedding_backend.enabled
            or self.fx_embedding_vectors is None
        ):
            return []

        query = f"把这个中文声音描述片段转换成简短英文FXName描述词: {residual}"
        query_vector = self.embedding_backend.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        similarities = self.fx_embedding_vectors @ query_vector
        results = []
        for index, similarity in sorted(
            enumerate(float(value) for value in similarities),
            key=lambda item: item[1],
            reverse=True,
        )[:FX_EMBEDDING_TOP_LIMIT]:
            if similarity < FX_EMBEDDING_MIN_SIMILARITY:
                continue
            english = self.fx_embedding_docs[index]["english"]
            if english not in existing:
                results.append(english)
        return results[:1]

    def fallback(self, description, candidates):
        fx_name = self.extract_fx_name(normalize_text(description))
        return {
            "status": "success",
            "data": {
                "category": "USER",
                "subcategory": "MISC",
                "ucs_prefix": "USERMisc",
                "fx_name": fx_name,
                "confidence": "low",
                "score": 0.0,
                "candidates": candidates[:3],
                "fallback": True,
            },
            "message": "No confident UCS category match; using USERMisc.",
        }


def clean_fx_token(value):
    return english_label(value)


MATCHER = UCSMatcher()
STATE_LOCK = Lock()
UI_STATE = {
    "description": "",
    "result": None,
    "selected_candidate": 1,
    "fx_name": "",
}
REAPER_STATUS = {
    "online": False,
    "selected_item_count": 0,
    "last_seen": None,
    "last_message": "",
}
TASK_STATE = {
    "next_id": 1,
    "pending": None,
    "last_completed": None,
}
MODEL_INSTALL_STATE = {
    "running": False,
    "installed": False,
    "ok": None,
    "message": "",
    "step": "idle",
    "model": DEFAULT_EMBEDDING_MODEL,
    "started_at": None,
    "finished_at": None,
    "needs_restart": False,
    "log_tail": "",
}


def now_seconds():
    return int(time.time())


def public_reaper_status():
    status = dict(REAPER_STATUS)
    last_seen = status.get("last_seen")
    status["online"] = bool(last_seen and time.time() - float(last_seen) < 5.0)
    return status


def append_install_log(line):
    with STATE_LOCK:
        current = MODEL_INSTALL_STATE.get("log_tail", "")
        current = (current + "\n" + str(line))[-4000:]
        MODEL_INSTALL_STATE["log_tail"] = current.strip()


def run_install_command(command, env=None):
    append_install_log("$ " + " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=str(TOOL_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    assert process.stdout is not None
    for line in process.stdout:
        append_install_log(line.rstrip())
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"command failed with exit code {code}: {' '.join(command)}")


def install_semantic_model_worker(model_name):
    with STATE_LOCK:
        MODEL_INSTALL_STATE.update(
            {
                "running": True,
                "installed": False,
                "ok": None,
                "message": "正在准备 Python 环境...",
                "step": "venv",
                "model": model_name,
                "started_at": now_seconds(),
                "finished_at": None,
                "needs_restart": False,
                "log_tail": "",
            }
        )

    try:
        python_bin = VENV_DIR / "bin" / "python"
        if not python_bin.exists():
            run_install_command([sys.executable, "-m", "venv", str(VENV_DIR)])

        with STATE_LOCK:
            MODEL_INSTALL_STATE["step"] = "pip"
            MODEL_INSTALL_STATE["message"] = "正在安装 sentence-transformers，体积较大，请等待..."
        run_install_command([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
        run_install_command([str(python_bin), "-m", "pip", "install", "sentence-transformers"])

        with STATE_LOCK:
            MODEL_INSTALL_STATE["step"] = "model"
            MODEL_INSTALL_STATE["message"] = "正在下载并缓存语义模型..."
        run_install_command(
            [
                str(python_bin),
                "-c",
                (
                    "from sentence_transformers import SentenceTransformer; "
                    f"SentenceTransformer({model_name!r})"
                ),
            ]
        )

        save_tool_config({"embedding_enabled": True, "embedding_model": model_name})
        with STATE_LOCK:
            MODEL_INSTALL_STATE.update(
                {
                    "running": False,
                    "installed": True,
                    "ok": True,
                    "message": "语义模型已安装。请关闭后端并重新运行启动器以启用模型。",
                    "step": "done",
                    "finished_at": now_seconds(),
                    "needs_restart": True,
                }
            )
    except Exception as exc:
        with STATE_LOCK:
            MODEL_INSTALL_STATE.update(
                {
                    "running": False,
                    "installed": False,
                    "ok": False,
                    "message": str(exc),
                    "step": "error",
                    "finished_at": now_seconds(),
                    "needs_restart": False,
                }
            )


UI_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ENZ UCS Auto Rename</title>
  <style>
    :root { color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #15181d; color: #f2f4f8; }
    main { max-width: 980px; margin: 0 auto; padding: 24px; }
    h1 { font-size: 24px; margin: 0 0 16px; }
    textarea, input { box-sizing: border-box; width: 100%; border: 1px solid #3a4658; border-radius: 6px; background: #101318; color: #f2f4f8; font-size: 18px; padding: 12px; }
    input[type="radio"] { width: auto; flex: 0 0 auto; margin: 3px 0 0; padding: 0; accent-color: #75a7ff; }
    textarea { min-height: 110px; resize: vertical; }
    button { border: 0; border-radius: 6px; background: #2f6fed; color: white; font-size: 16px; padding: 10px 14px; cursor: pointer; }
    button.secondary { background: #3a4658; }
    button.danger { background: #8f3545; }
    button:disabled { opacity: .5; cursor: default; }
    .row { display: flex; gap: 10px; align-items: center; margin: 12px 0; flex-wrap: wrap; }
    .panel { border: 1px solid #2b3340; border-radius: 8px; padding: 16px; margin-top: 16px; background: #1b2028; }
    .candidate { display: grid; grid-template-columns: 22px minmax(92px, 120px) 1fr minmax(60px, auto); gap: 10px; align-items: center; min-height: 48px; padding: 10px; border-radius: 6px; border: 1px solid transparent; }
    .candidate:hover { background: #202735; }
    .candidate.active { border-color: #2f6fed; background: #1f2a3d; }
    .candidate-title { font-weight: 700; }
    .candidate-score { text-align: right; }
    .candidate-terms { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .muted { color: #aab4c3; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .status { min-height: 24px; color: #9fd3ff; }
  </style>
</head>
<body>
  <main>
    <h1>ENZ UCS Auto Rename</h1>
    <label class="muted" for="description">中文描述</label>
    <textarea id="description" placeholder="例如：木头快速生长魔法"></textarea>
    <div class="row">
      <button id="parseBtn">生成候选</button>
      <button class="secondary" id="saveBtn" disabled>在 REAPER 重命名</button>
      <button class="secondary" id="clearBtn">清空</button>
      <button class="danger" id="shutdownBtn">关闭后端</button>
      <span class="status" id="status"></span>
    </div>
    <div class="panel">
      <div class="muted">REAPER 状态</div>
      <div id="reaperStatus">等待 REAPER 脚本连接</div>
    </div>
    <div class="panel">
      <div class="muted">语义模型</div>
      <div id="modelStatus">读取中</div>
      <div class="row">
        <button class="secondary" id="installModelBtn">安装语义模型</button>
        <button class="secondary" id="refreshModelBtn">刷新状态</button>
      </div>
      <div class="muted" id="modelInstallStatus"></div>
    </div>
    <div class="panel">
      <label class="muted" for="fxName">FXName</label>
      <input id="fxName" placeholder="生成后可手动编辑，例如 Wood_Fast_Growth">
    </div>
    <div class="panel">
      <div class="muted">UCS 候选</div>
      <div id="candidates"></div>
    </div>
    <div class="panel">
      <div class="muted">REAPER 预览基础名</div>
      <div class="mono" id="preview">(等待生成)</div>
    </div>
  </main>
  <script>
    const descriptionEl = document.getElementById('description');
    const fxNameEl = document.getElementById('fxName');
    const candidatesEl = document.getElementById('candidates');
    const previewEl = document.getElementById('preview');
    const statusEl = document.getElementById('status');
    const saveBtn = document.getElementById('saveBtn');
    let result = null;
    let selectedCandidate = 1;

    function setStatus(text) { statusEl.textContent = text || ''; }
    function activeCandidate() {
      if (!result) return null;
      return (result.candidates || [])[selectedCandidate - 1] || null;
    }
    function baseName() {
      const candidate = activeCandidate();
      if (!candidate) return '(等待生成)';
      const fx = fxNameEl.value.trim();
      return candidate.ucs_prefix + (fx ? '_' + fx : '') + '_01';
    }
    function render() {
      candidatesEl.innerHTML = '';
      if (!result) {
        previewEl.textContent = '(等待生成)';
        saveBtn.disabled = true;
        return;
      }
      (result.candidates || []).slice(0, 3).forEach((candidate, index) => {
        const number = index + 1;
        const hits = ((candidate.explain || {}).rule_hits || []).slice(0, 3).map(hit => `${hit.src}:${hit.token}(+${hit.delta})`).join(' | ');
        const div = document.createElement('div');
        div.className = 'candidate' + (number === selectedCandidate ? ' active' : '');
        div.innerHTML = `<input type="radio" name="candidate" ${number === selectedCandidate ? 'checked' : ''}>
          <div class="mono candidate-title">${candidate.ucs_prefix}</div>
          <div>
            <div>${candidate.zh_category || candidate.category}/${candidate.zh_subcategory || candidate.subcategory}</div>
            <div class="muted candidate-terms">规则 ${candidate.rule_score || 0} / 轻语义 ${candidate.semantic_score || 0} / FTS ${candidate.fts_score || 0} / 模型 ${candidate.embedding_score || 0}</div>
            <div class="muted candidate-terms">${hits}</div>
            <div class="muted candidate-terms">${(candidate.matched_terms || []).join(', ')}</div>
          </div>
          <div class="muted mono candidate-score">${candidate.score}</div>`;
        div.addEventListener('click', () => { selectedCandidate = number; render(); });
        candidatesEl.appendChild(div);
      });
      previewEl.textContent = baseName();
      saveBtn.disabled = false;
    }
    async function parseDescription() {
      const description = descriptionEl.value.trim();
      if (!description) { setStatus('请输入中文描述。'); return; }
      setStatus('解析中...');
      const response = await fetch('/api/v1/parse_ucs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json; charset=utf-8'},
        body: JSON.stringify({description})
      });
      const payload = await response.json();
      if (payload.status !== 'success') throw new Error(payload.message || '解析失败');
      result = payload.data;
      selectedCandidate = 1;
      fxNameEl.value = result.fx_name || '';
      setStatus('已生成候选，确认后点“在 REAPER 重命名”。');
      render();
    }
    async function saveState() {
      if (!result) return;
      const response = await fetch('/api/v1/rename_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json; charset=utf-8'},
        body: JSON.stringify({
          description: descriptionEl.value.trim(),
          result,
          selected_candidate: selectedCandidate,
          fx_name: fxNameEl.value.trim()
        })
      });
      const payload = await response.json();
      if (payload.status !== 'success') throw new Error(payload.message || '发送失败');
      setStatus('已发送给 REAPER，请保持 REAPER 脚本窗口打开。');
    }
    async function refreshReaperStatus() {
      const target = document.getElementById('reaperStatus');
      try {
        const [statusResponse, stateResponse] = await Promise.all([
          fetch('/api/v1/reaper_status'),
          fetch('/api/v1/task_state')
        ]);
        const statusPayload = await statusResponse.json();
        const statePayload = await stateResponse.json();
        const info = statusPayload.data || {};
        const task = statePayload.data || {};
        const parts = [
          info.online ? '已连接' : '未连接',
          `选中 item: ${info.selected_item_count || 0}`
        ];
        if (task.pending) parts.push(`待执行任务 #${task.pending.id}`);
        if (task.last_completed) parts.push(task.last_completed.message || `最近完成 #${task.last_completed.id}`);
        target.textContent = parts.join(' / ');
      } catch (err) {
        target.textContent = '状态读取失败';
      }
    }
    async function refreshModelStatus() {
      const target = document.getElementById('modelStatus');
      const installButton = document.getElementById('installModelBtn');
      try {
        const response = await fetch('/api/v1/model_status');
        const payload = await response.json();
        const embedding = ((payload.data || {}).embedding || {});
        const config = ((payload.data || {}).config || {});
        target.textContent = embedding.enabled
          ? `已启用 / ${embedding.model || 'local model'}`
          : `未启用 / ${embedding.reason || '未配置模型'}${config.embedding_enabled ? ' / 配置已启用，重启后生效' : ''}`;
        installButton.disabled = Boolean(embedding.enabled);
      } catch (err) {
        target.textContent = '状态读取失败';
      }
    }
    async function refreshInstallStatus() {
      const target = document.getElementById('modelInstallStatus');
      const button = document.getElementById('installModelBtn');
      try {
        const response = await fetch('/api/v1/model_install_status');
        const payload = await response.json();
        const info = payload.data || {};
        button.disabled = Boolean(info.running);
        if (info.running) {
          target.textContent = `${info.step || 'install'} / ${info.message || '安装中...'}`;
        } else if (info.message) {
          target.textContent = info.message;
        }
      } catch (err) {
        target.textContent = '安装状态读取失败';
      }
    }
    async function installSemanticModel() {
      if (!confirm('安装本地语义模型？需要下载约 1.3GB 的依赖和模型，时间取决于网络。')) return;
      const button = document.getElementById('installModelBtn');
      button.disabled = true;
      setStatus('已开始安装语义模型，请不要关闭后端。');
      const response = await fetch('/api/v1/install_semantic_model', {
        method: 'POST',
        headers: {'Content-Type': 'application/json; charset=utf-8'},
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (payload.status !== 'success') throw new Error(payload.message || '启动安装失败');
      refreshInstallStatus();
    }
    async function shutdownService() {
      if (!confirm('关闭本地 UCS 后端服务？关闭后需要重新运行启动器才能继续使用。')) return;
      try {
        await fetch('/api/v1/shutdown', {method: 'POST'});
        setStatus('后端正在关闭。');
      } catch (err) {
        setStatus('后端已关闭或连接中断。');
      }
    }
    document.getElementById('parseBtn').addEventListener('click', () => parseDescription().catch(err => setStatus(err.message)));
    document.getElementById('saveBtn').addEventListener('click', () => saveState().catch(err => setStatus(err.message)));
    document.getElementById('shutdownBtn').addEventListener('click', () => shutdownService());
    document.getElementById('installModelBtn').addEventListener('click', () => installSemanticModel().catch(err => setStatus(err.message)));
    document.getElementById('refreshModelBtn').addEventListener('click', () => { refreshModelStatus(); refreshInstallStatus(); });
    document.getElementById('clearBtn').addEventListener('click', () => {
      descriptionEl.value = ''; fxNameEl.value = ''; result = null; selectedCandidate = 1; setStatus(''); render();
    });
    fxNameEl.addEventListener('input', render);
    fetch('/api/v1/ui_state').then(r => r.json()).then(payload => {
      const data = payload.data || {};
      if (data.description) descriptionEl.value = data.description;
      if (data.result) {
        result = data.result;
        selectedCandidate = data.selected_candidate || 1;
        fxNameEl.value = data.fx_name || result.fx_name || '';
      }
      render();
    }).catch(() => render());
    setInterval(refreshReaperStatus, 1000);
    setInterval(refreshInstallStatus, 2000);
    refreshReaperStatus();
    refreshModelStatus();
    refreshInstallStatus();
  </script>
</body>
</html>"""


class UCSRequestHandler(BaseHTTPRequestHandler):
    server_version = "ENZUCS/0.1"

    def do_OPTIONS(self):
        self.send_response(204)
        self.write_common_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/ui"):
            self.write_html(200, UI_HTML)
            return
        if path == "/health":
            self.write_json(200, {"status": "ok", "version": SERVICE_VERSION})
            return
        if path == "/version":
            self.write_json(200, {"status": "ok", "version": SERVICE_VERSION})
            return
        if path == "/api/v1/model_status":
            self.write_json(200, {"status": "success", "data": MATCHER.model_status(), "message": ""})
            return
        if path == "/api/v1/model_install_status":
            with STATE_LOCK:
                data = dict(MODEL_INSTALL_STATE)
            self.write_json(200, {"status": "success", "data": data, "message": ""})
            return
        if path == "/api/v1/ui_state":
            with STATE_LOCK:
                data = dict(UI_STATE)
            self.write_json(200, {"status": "success", "data": data, "message": ""})
            return
        if path == "/api/v1/reaper_status":
            with STATE_LOCK:
                data = public_reaper_status()
            self.write_json(200, {"status": "success", "data": data, "message": ""})
            return
        if path == "/api/v1/task_state":
            with STATE_LOCK:
                data = {
                    "pending": TASK_STATE["pending"],
                    "last_completed": TASK_STATE["last_completed"],
                }
            self.write_json(200, {"status": "success", "data": data, "message": ""})
            return
        if path == "/api/v1/next_task":
            with STATE_LOCK:
                data = TASK_STATE["pending"]
            self.write_json(200, {"status": "success", "data": data, "message": ""})
            return
        self.write_json(404, {"status": "error", "message": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/v1/ui_state":
            self.handle_ui_state_post()
            return
        if path == "/api/v1/reaper_status":
            self.handle_reaper_status_post()
            return
        if path == "/api/v1/rename_task":
            self.handle_rename_task_post()
            return
        if path == "/api/v1/task_complete":
            self.handle_task_complete_post()
            return
        if path == "/api/v1/shutdown":
            self.handle_shutdown_post()
            return
        if path == "/api/v1/install_semantic_model":
            self.handle_install_semantic_model_post()
            return
        if path != "/api/v1/parse_ucs":
            self.write_json(404, {"status": "error", "message": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            description = payload.get("description", "")
            if not isinstance(description, str):
                raise ValueError("description must be a string")
            context = {}
            for key in ("filename", "fxname", "keywords", "category", "subcategory", "notes"):
                if key in payload:
                    context[key] = payload.get(key)
            self.write_json(200, MATCHER.parse(description, context=context))
        except Exception as exc:
            self.write_json(400, {"status": "error", "data": None, "message": str(exc)})

    def handle_install_semantic_model_post(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            model_name = str(payload.get("model") or DEFAULT_EMBEDDING_MODEL).strip()
            if not model_name:
                raise ValueError("model must not be empty")
            with STATE_LOCK:
                if MODEL_INSTALL_STATE.get("running"):
                    data = dict(MODEL_INSTALL_STATE)
                    self.write_json(200, {"status": "success", "data": data, "message": "Install already running."})
                    return
                MODEL_INSTALL_STATE.update(
                    {
                        "running": True,
                        "ok": None,
                        "message": "安装任务已启动...",
                        "step": "queued",
                        "model": model_name,
                        "started_at": now_seconds(),
                        "finished_at": None,
                        "needs_restart": False,
                        "log_tail": "",
                    }
                )
                data = dict(MODEL_INSTALL_STATE)
            Thread(target=install_semantic_model_worker, args=(model_name,), daemon=True).start()
            self.write_json(200, {"status": "success", "data": data, "message": ""})
        except Exception as exc:
            self.write_json(400, {"status": "error", "data": None, "message": str(exc)})

    def handle_ui_state_post(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = payload.get("result")
            if not isinstance(result, dict):
                raise ValueError("result must be an object")
            with STATE_LOCK:
                UI_STATE["description"] = str(payload.get("description") or "")
                UI_STATE["result"] = result
                UI_STATE["selected_candidate"] = int(payload.get("selected_candidate") or 1)
                UI_STATE["fx_name"] = str(payload.get("fx_name") or result.get("fx_name") or "")
                data = dict(UI_STATE)
            self.write_json(200, {"status": "success", "data": data, "message": ""})
        except Exception as exc:
            self.write_json(400, {"status": "error", "data": None, "message": str(exc)})

    def handle_reaper_status_post(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            with STATE_LOCK:
                REAPER_STATUS["online"] = True
                REAPER_STATUS["selected_item_count"] = int(payload.get("selected_item_count") or 0)
                REAPER_STATUS["last_seen"] = time.time()
                REAPER_STATUS["last_message"] = str(payload.get("message") or "")
                data = public_reaper_status()
            self.write_json(200, {"status": "success", "data": data, "message": ""})
        except Exception as exc:
            self.write_json(400, {"status": "error", "data": None, "message": str(exc)})

    def handle_rename_task_post(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = payload.get("result")
            if not isinstance(result, dict):
                raise ValueError("result must be an object")
            task = {
                "id": None,
                "created_at": now_seconds(),
                "description": str(payload.get("description") or ""),
                "result": result,
                "selected_candidate": int(payload.get("selected_candidate") or 1),
                "fx_name": str(payload.get("fx_name") or result.get("fx_name") or ""),
            }
            with STATE_LOCK:
                task["id"] = TASK_STATE["next_id"]
                TASK_STATE["next_id"] += 1
                TASK_STATE["pending"] = task
                UI_STATE["description"] = task["description"]
                UI_STATE["result"] = task["result"]
                UI_STATE["selected_candidate"] = task["selected_candidate"]
                UI_STATE["fx_name"] = task["fx_name"]
            self.write_json(200, {"status": "success", "data": task, "message": ""})
        except Exception as exc:
            self.write_json(400, {"status": "error", "data": None, "message": str(exc)})

    def handle_task_complete_post(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            task_id = int(payload.get("id") or 0)
            completed = {
                "id": task_id,
                "completed_at": now_seconds(),
                "ok": bool(payload.get("ok")),
                "message": str(payload.get("message") or ""),
            }
            with STATE_LOCK:
                pending = TASK_STATE["pending"]
                if pending and int(pending.get("id") or 0) == task_id:
                    TASK_STATE["pending"] = None
                TASK_STATE["last_completed"] = completed
                REAPER_STATUS["last_message"] = completed["message"]
                data = {
                    "pending": TASK_STATE["pending"],
                    "last_completed": TASK_STATE["last_completed"],
                }
            self.write_json(200, {"status": "success", "data": data, "message": ""})
        except Exception as exc:
            self.write_json(400, {"status": "error", "data": None, "message": str(exc)})

    def handle_shutdown_post(self):
        self.write_json(200, {"status": "success", "data": None, "message": "Shutting down."})

        def shutdown():
            time.sleep(0.2)
            self.server.shutdown()

        Thread(target=shutdown, daemon=True).start()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def write_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.write_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def write_html(self, status, html):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.write_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def write_common_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), UCSRequestHandler)
    print(f"ENZ UCS service listening on http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopping ENZ UCS service.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
