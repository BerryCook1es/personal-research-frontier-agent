from __future__ import annotations

import re


ACADEMIC_GLOSSARY = {
    "scientific knowledge graph": "科学知识图谱",
    "scholarly knowledge graph": "学术知识图谱",
    "document-level information extraction": "文档级信息抽取",
    "entity alignment": "实体对齐",
    "relation extraction": "关系抽取",
    "knowledge graph construction": "知识图谱构建",
    "graph fusion": "图谱融合",
    "evidence grounding": "证据落地",
    "retrieval-augmented generation": "检索增强生成",
    "LLM-as-a-Judge": "LLM 评审器",
    "multi-agent system": "多智能体系统",
    "agentic workflow": "智能体工作流",
    "bibliometrics": "文献计量学",
    "bibliometric": "文献计量学",
    "scientometrics": "科学计量学",
    "informetrics": "信息计量学",
    "science of science": "科学学",
    "scientific information extraction": "科学信息抽取",
    "scientific text mining": "科学文本挖掘",
    "knowledge graph": "知识图谱",
    "GraphRAG": "GraphRAG",
    "factuality": "事实性",
    "hallucination": "幻觉",
    "open science": "开放科学",
    "research evaluation": "科研评价",
    "citation analysis": "引文分析",
}


def protect_terms(text: str) -> tuple[str, dict[str, str]]:
    markers: dict[str, str] = {}
    for index, (term, translation) in enumerate(sorted(ACADEMIC_GLOSSARY.items(), key=lambda item: -len(item[0]))):
        marker = f"__TERM_{index}__"
        pattern = re.compile(re.escape(term), re.I)
        if pattern.search(text):
            text = pattern.sub(marker, text)
            markers[marker] = translation
    return text, markers


def restore_terms(text: str, markers: dict[str, str]) -> str:
    for marker, translation in markers.items():
        text = text.replace(marker, translation)
    return text

