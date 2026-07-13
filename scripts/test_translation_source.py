#!/usr/bin/env python3
"""WEB-C 번역 원문의 책·장·절·정규화 무결성을 검사한다."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CHAPTERS = {
    "GEN": 50, "EXO": 40, "LEV": 27, "NUM": 36, "DEU": 34, "JOS": 24,
    "JDG": 21, "RUT": 4, "1SA": 31, "2SA": 24, "1KI": 22, "2KI": 25,
    "1CH": 29, "2CH": 36, "EZR": 10, "NEH": 13, "TOB": 14, "JDT": 16,
    "ESG": 10, "1MA": 16, "2MA": 15, "JOB": 42, "PSA": 150, "PRO": 31,
    "ECC": 12, "SNG": 8, "WIS": 19, "SIR": 51, "ISA": 66, "JER": 52,
    "LAM": 5, "BAR": 6, "EZK": 48, "DAG": 14, "HOS": 14, "JOL": 4,
    "AMO": 9, "OBA": 1, "JON": 4, "MIC": 7, "NAM": 3, "HAB": 3,
    "ZEP": 3, "HAG": 2, "ZEC": 14, "MAL": 3, "MAT": 28, "MRK": 16,
    "LUK": 24, "JHN": 21, "ACT": 28, "ROM": 16, "1CO": 16, "2CO": 13,
    "GAL": 6, "EPH": 6, "PHP": 4, "COL": 4, "1TH": 5, "2TH": 3,
    "1TI": 6, "2TI": 4, "TIT": 3, "PHM": 1, "HEB": 13, "JAS": 5,
    "1PE": 5, "2PE": 3, "1JN": 5, "2JN": 1, "3JN": 1, "JUD": 1,
    "REV": 22,
}


def main() -> None:
    meta = json.loads((ROOT / "translation/source/web-c.meta.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (ROOT / "translation/source/web-c.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert meta["license"] == "Public Domain"
    assert meta["download_sha256"] == "b2807cd86cd2423214e5c51bc1b92217ceaf9420cfade84ff951766cd3e2aa4b"
    assert meta["books"] == 73
    assert meta["chapters"] == 1_328
    assert meta["verse_records"] == 35_408
    assert len(records) == 35_408
    assert len({item["id"] for item in records}) == len(records)
    assert len({item["code"] for item in records}) == 73
    assert all("\\" not in item["text"] and "strong=" not in item["text"] for item in records)
    actual_chapters = {
        code: max(item["chapter"] for item in records if item["code"] == code)
        for code in EXPECTED_CHAPTERS
    }
    assert actual_chapters == EXPECTED_CHAPTERS

    by_id = {item["id"]: item for item in records}
    assert by_id["GEN-1-1"]["text"] == "In the beginning, God created the heavens and the earth."
    assert "only born Son" in by_id["JHN-3-16"]["text"]
    assert by_id["TOB-1-1"]["book"] == "토빗기"
    assert by_id["WIS-1-1"]["book"] == "지혜서"
    assert by_id["SIR-1-1"]["book"] == "집회서"
    assert by_id["BAR-1-1"]["book"] == "바룩서"
    assert max(item["chapter"] for item in records if item["code"] == "ESG") == 10
    assert max(item["chapter"] for item in records if item["code"] == "DAG") == 14
    assert max(item["chapter"] for item in records if item["code"] == "1PE") == 5
    assert "pour out my Spirit" in by_id["JOL-3-1"]["text"]
    assert by_id["JOL-3-1"]["source_chapter"] == 2
    assert by_id["JOL-3-1"]["source_verse"] == "28"
    assert by_id["JOL-4-1"]["source_chapter"] == 3
    assert by_id["JOL-4-1"]["source_verse"] == "1"
    assert by_id["MAL-3-19"]["source_chapter"] == 4
    assert by_id["MAL-3-19"]["source_verse"] == "1"
    assert by_id["MAL-3-24"]["source_chapter"] == 4
    assert by_id["MAL-3-24"]["source_verse"] == "6"
    assert not any(item["code"] == "MAL" and item["chapter"] == 4 for item in records)

    omitted = [item for item in records if item["omitted_in_source"]]
    assert len(omitted) == 29
    assert {item["id"] for item in omitted} == {
        "SIR-1-5", "SIR-1-7", "SIR-1-21", "SIR-3-19", "SIR-10-21",
        "SIR-11-15-16", "SIR-13-14", "SIR-16-15-16", "SIR-17-5", "SIR-17-9",
        "SIR-17-16", "SIR-17-18", "SIR-17-21", "SIR-18-3", "SIR-19-18-19",
        "SIR-19-21", "SIR-20-3", "SIR-20-32", "SIR-22-9-10", "SIR-23-28",
        "SIR-24-18", "SIR-24-24", "SIR-25-12", "SIR-26-19-27", "LUK-17-36",
        "ACT-8-37", "ACT-15-34", "ACT-24-7", "ROM-16-25",
    }
    print("OK: WEB-C 가톨릭 정경 73권 · 1,328장 · 35,408개 절 레코드 검증 완료")


if __name__ == "__main__":
    main()
