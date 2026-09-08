"""One-pass report plan matching the supplied credit-review reference."""

from .registry import FACTORS


REPORT_SECTIONS = (
    {
        "number": 1,
        "title": "업체현황",
        "factor_ids": ("F01", "F02", "F03", "F04", "F05"),
        "blocks": ("업체개요", "주요연혁", "주요 주주 현황", "경영진 현황", "종속기업투자 현황"),
    },
    {
        "number": 2,
        "title": "여신 개요 및 신청 사유",
        "factor_ids": ("F27", "F28", "F23"),
        "blocks": (
            "신청내용", "신청배경", "자금용도", "자금 집행 및 상환 프로세스",
            "수익성 검토 의견", "기존 금융기관 차입 현황",
        ),
    },
    {
        "number": 3,
        "title": "사업 분석",
        "factor_ids": ("F06", "F07", "F10", "F12"),
        "blocks": (
            "사업영역", "제품 특성 및 성장성", "수요 및 공급", "가격 변동 추이",
            "생산능력 및 실적", "증설·가동 및 양산 계획", "주요 사업장과 제조공정",
        ),
    },
    {
        "number": 4,
        "title": "주요 리스크 분석",
        "factor_ids": ("F08", "F09", "F11", "F30"),
        "blocks": (
            "산업 수요 둔화 및 경쟁 심화", "원재료·공급망 위험", "종속기업 및 투자 리스크",
            "사업 포트폴리오와 주요 이벤트", "위험별 대응 및 잔존 위험",
        ),
    },
    {
        "number": 5,
        "title": "재무 분석",
        "factor_ids": ("F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20"),
        "blocks": (
            "주요 재무현황", "성장성 분석", "수익성 분석", "현금흐름 분석",
            "안정성 분석", "운전자본 및 자산의 질", "비경상손익·손상", "미래실적과 가정",
        ),
    },
    {
        "number": 6,
        "title": "상환재원",
        "factor_ids": ("F21", "F22", "F24"),
        "blocks": ("총 차입금 구조", "만기구조", "영업수익금에 의한 상환", "보유현금·대체상환재원", "상환능력 의견"),
    },
    {
        "number": 7,
        "title": "특이사항",
        "factor_ids": ("F26", "F29", "F25"),
        "blocks": (
            "신용등급 의견", "영업전략 의견", "담보보유 의견", "Exposure 관련 의견",
            "우발채무·파생상품·지급보증", "종합심사의견",
        ),
    },
)


REPORT_FACTOR_ORDER = tuple(fid for section in REPORT_SECTIONS for fid in section["factor_ids"])
if len(REPORT_SECTIONS) != 7:
    raise RuntimeError("The reference report contract requires seven report sections")
if len(REPORT_FACTOR_ORDER) != len(set(REPORT_FACTOR_ORDER)) or set(REPORT_FACTOR_ORDER) != set(FACTORS):
    raise RuntimeError("Every review factor must belong to exactly one report section")


# The rendered report keeps seven top-level sections.  Finance is deliberately
# inferred in two balanced calls so its tables, criteria, and structured output
# fit inside the served model's context window.  Both calls are projected back
# into the single ``5. 재무 분석`` report section below.
FINANCE_SECTION_CALLS = (
    {
        "call_id": "05a",
        "call_title": "재무 분석 — 손익·재무구조",
        "factor_ids": ("F13", "F14", "F16", "F19"),
        "blocks": ("주요 재무현황", "성장성 분석", "수익성 분석", "안정성 분석", "비경상손익·손상"),
    },
    {
        "call_id": "05b",
        "call_title": "재무 분석 — 현금·자산·전망",
        "factor_ids": ("F15", "F17", "F18", "F20"),
        "blocks": ("현금흐름 분석", "유동성 분석", "운전자본 및 자산의 질", "미래실적과 가정"),
    },
)


REPORT_SECTION_CALLS = tuple(
    {
        **section,
        "call_id": f"{section['number']:02d}",
        "call_title": section["title"],
    }
    for section in REPORT_SECTIONS
    if section["number"] != 5
) + tuple(
    {
        **next(section for section in REPORT_SECTIONS if section["number"] == 5),
        **finance_call,
    }
    for finance_call in FINANCE_SECTION_CALLS
)

# Keep execution and report order explicit after replacing one section with two
# calls.  This avoids the tuple concatenation order placing finance after section 7.
REPORT_SECTION_CALLS = tuple(sorted(
    REPORT_SECTION_CALLS,
    key=lambda call: (call["number"], call["call_id"]),
))
REPORT_CALL_FACTOR_ORDER = tuple(fid for call in REPORT_SECTION_CALLS for fid in call["factor_ids"])
if len(REPORT_SECTION_CALLS) != 8:
    raise RuntimeError("The review execution contract requires eight LLM calls")
if (len(REPORT_CALL_FACTOR_ORDER) != len(set(REPORT_CALL_FACTOR_ORDER))
        or set(REPORT_CALL_FACTOR_ORDER) != set(REPORT_FACTOR_ORDER)):
    raise RuntimeError("The eight-call plan must cover every report factor once")


FACTOR_HEADINGS = {
    "F01": "업체개요", "F02": "주요연혁", "F03": "주요 주주 현황", "F04": "경영진 현황",
    "F05": "종속기업투자 현황", "F27": "신청내용·신청배경·자금용도",
    "F28": "자금 집행 및 상환 프로세스", "F23": "기존 금융기관 차입 현황",
    "F06": "사업영역", "F07": "주요 제품 경쟁력", "F10": "매출처 및 수요처",
    "F12": "생산능력·가동 및 양산 계획", "F08": "산업 수요 및 전망",
    "F09": "시장지위와 경쟁구조", "F11": "원재료·공급망 위험",
    "F30": "주요 이벤트 및 종합 리스크", "F13": "성장성 분석", "F14": "수익성 분석",
    "F15": "현금흐름 분석", "F16": "안정성 분석", "F17": "유동성 분석",
    "F18": "운전자본 및 자산의 질", "F19": "비경상손익·손상 위험",
    "F20": "추정재무 및 미래실적", "F21": "총 차입금 구조", "F22": "차입금 만기구조",
    "F24": "상환재원 및 상환능력", "F26": "신용등급 의견",
    "F29": "당행 거래·수익성·Exposure 의견", "F25": "담보·우발채무·지급보증",
}
