"""추천 후보마다 '무엇을 하는지, 언제 쓰는지, 어떻게 말하면 되는지'를 한국어로 붙인다.

자주 나오는 도구는 직접 쓴 설명(KNOWN)을 쓰고, 처음 보는 도구는 겹치는 작업 신호로 문장을 만든다.
"""
from .signals import SIGNALS

# tier: 필수 · 추천 · 필요할 때 · 겹침
KNOWN: dict[str, dict] = {
    "webapp-testing": {
        "summary": "Claude가 브라우저를 직접 열어 내 웹앱을 눌러 보고, 스크린샷과 콘솔 오류를 확인해요.",
        "cases": ["게임·Streamlit·HTML을 만든 뒤 버튼이 잘 되는지 확인할 때", "발표 전에 데모 화면을 점검할 때"],
        "example": "오피스 화면 열어서 점검 버튼 눌러 보고 오류 있는지 webapp-testing으로 확인해 줘",
        "caveat": "Playwright가 필요해요 (pip install playwright → playwright install chromium).",
        "tier": "필수",
    },
    "security-guidance": {
        "summary": "코드를 고칠 때 API 키 노출 같은 위험한 패턴을 경고하고, 작업이 끝나면 바뀐 내용을 검토해요.",
        "cases": ["API 키를 코드나 파일에 넣는 실수를 막고 싶을 때", "공개 저장소에 올리거나 배포하기 전"],
        "example": "(따로 말하지 않아도 코드를 고칠 때 자동으로 경고해요)",
        "caveat": "작업 끝 검토에 LLM을 써서 토큰이 조금 더 들어요.",
        "tier": "필수",
    },
    "theme-factory": {
        "summary": "발표자료·문서·HTML에 미리 만든 테마 10종 중 하나를 골라 일관되게 입혀요.",
        "cases": ["팀 보고서·PDF 디자인을 통일할 때", "motion-deck 발표자료 색을 맞출 때"],
        "example": "이 보고서에 theme-factory로 깔끔한 테마 입혀 줘",
        "tier": "추천",
    },
    "hyperframes": {
        "summary": "HTML로 만든 화면을 영상으로 렌더링해요.",
        "cases": ["프로젝트 소개 영상이 필요할 때", "발표용 데모 영상을 만들 때"],
        "example": "이 프로젝트 30초 소개 영상 hyperframes로 만들어 줘",
        "caveat": "영상 렌더링 도구를 추가로 설치해야 할 수 있어요.",
        "tier": "필요할 때",
    },
    "desktop-commander": {
        "summary": "터미널 명령·파일 작업을 해 주는 MCP 서버예요.",
        "cases": ["Claude 데스크톱 채팅(Code 탭이 아닌 곳)에서 파일·터미널 작업을 시킬 때"],
        "example": "desktop-commander로 다운로드 폴더 정리해 줘",
        "caveat": "Claude Code에는 같은 기능이 이미 있어서 겹쳐요.",
        "tier": "겹침",
    },
    "playwright": {
        "summary": "브라우저 자동화 MCP예요. Claude가 웹페이지를 열고 클릭·입력해요.",
        "cases": ["웹사이트 동작을 자동으로 테스트할 때", "로그인이 필요 없는 페이지를 크롤링할 때"],
        "example": "이 사이트 회원가입 화면 playwright로 테스트해 줘",
        "caveat": "webapp-testing과 하는 일이 비슷해요. 하나만 써도 충분해요.",
        "tier": "추천",
    },
    "frontend-design": {
        "summary": "흔한 AI 느낌이 아닌, 완성도 높은 웹 화면 디자인을 만들도록 도와요.",
        "cases": ["랜딩 페이지나 대시보드 화면을 만들 때", "기존 화면을 더 세련되게 바꿀 때"],
        "example": "frontend-design으로 이 페이지 다시 디자인해 줘",
        "tier": "추천",
    },
    "mcp-builder": {
        "summary": "MCP 서버를 제대로 만드는 방법을 단계별로 안내해요.",
        "cases": ["노션·디스코드 같은 서비스를 Claude에 연결하는 MCP를 만들 때"],
        "example": "mcp-builder로 내 API를 MCP 서버로 만들어 줘",
        "tier": "필요할 때",
    },
    "session-report": {
        "summary": "Claude Code 사용 내역(토큰, 캐시 효율, 서브에이전트)을 HTML 리포트로 보여 줘요.",
        "cases": ["토큰을 어디에 많이 쓰는지 확인할 때", "월간 AI 회고 자료를 만들 때"],
        "example": "/session-report",
        "tier": "추천",
    },
    "commit-commands": {
        "summary": "커밋 메시지 작성, 푸시, PR 만들기를 명령 하나로 해요.",
        "cases": ["작업 끝나고 커밋·푸시를 한 번에 하고 싶을 때"],
        "example": "/commit",
        "tier": "추천",
    },
    "claude-md-management": {
        "summary": "CLAUDE.md(Claude에게 주는 프로젝트 규칙 파일)를 점검하고 정리해요.",
        "cases": ["프로젝트 규칙이 길어지고 엉켰을 때"],
        "example": "CLAUDE.md 점검해서 정리해 줘",
        "tier": "추천",
    },
    "firecrawl": {
        "summary": "웹사이트를 LLM이 읽기 좋은 마크다운으로 바꿔 가져와요.",
        "cases": ["문서 사이트를 통째로 수집할 때", "크롤링 결과를 깔끔하게 받고 싶을 때"],
        "example": "firecrawl로 이 문서 사이트 마크다운으로 가져와 줘",
        "caveat": "Firecrawl API 키가 필요해요 (유료 요금제가 있어요).",
        "tier": "필요할 때",
    },
    "carbone-skill": {
        "summary": "문서 템플릿 엔진 Carbone의 문법을 알려 줘요.",
        "cases": ["Carbone으로 보고서·계약서 템플릿을 만들 때"],
        "example": "carbone 템플릿으로 견적서 양식 만들어 줘",
        "caveat": "Carbone을 쓰지 않으면 필요 없어요.",
        "tier": "필요할 때",
    },
}

# 처음 보는 도구용: 신호별 '이럴 때 쓰세요' 문장과 예시 말투
SIGNAL_CASES: dict[str, tuple[str, str]] = {
    "pdf": ("PDF를 읽거나 만들 때", "이 PDF {name}로 정리해 줘"),
    "slides": ("발표자료를 만들 때", "{name}로 발표자료 만들어 줘"),
    "docs": ("README·보고서 같은 문서를 쓸 때", "{name}로 이 문서 다듬어 줘"),
    "sheet": ("엑셀·CSV를 다룰 때", "{name}로 이 엑셀 정리해 줘"),
    "python": ("파이썬·Streamlit 앱을 만들 때", "{name}로 이 파이썬 코드 봐 줘"),
    "git": ("커밋·GitHub 작업을 할 때", "{name}로 커밋 정리해 줘"),
    "review": ("코드를 리뷰하거나 버그를 고칠 때", "{name}로 이 코드 리뷰해 줘"),
    "frontend": ("웹 화면·HTML을 만들거나 다듬을 때", "{name}로 이 화면 다듬어 줘"),
    "deploy": ("앱을 배포할 때", "{name}로 배포해 줘"),
    "db": ("DB를 설계하거나 다룰 때", "{name}로 DB 구조 봐 줘"),
    "data": ("데이터를 분석하고 차트를 그릴 때", "{name}로 이 데이터 분석해 줘"),
    "llm": ("LLM·에이전트를 만들 때", "{name}로 에이전트 구조 잡아 줘"),
    "mcp": ("MCP로 서비스를 연결할 때", "{name}로 MCP 연결해 줘"),
    "browser": ("웹 자동화·크롤링을 할 때", "{name}로 이 사이트 자동화해 줘"),
    "notion": ("노션과 연동할 때", "{name}로 노션에 정리해 줘"),
    "chat": ("디스코드·슬랙과 연동할 때", "{name}로 디스코드 알림 붙여 줘"),
    "blog": ("블로그·회고 글을 쓸 때", "{name}로 블로그 글 다듬어 줘"),
    "test": ("테스트를 만들거나 검증할 때", "{name}로 테스트 만들어 줘"),
    "security": ("보안을 점검할 때", "{name}로 보안 점검해 줘"),
    "media": ("영상·이미지를 만들 때", "{name}로 소개 영상 만들어 줘"),
    "game": ("게임을 만들 때", "{name}로 게임 기능 추가해 줘"),
    "learning": ("공부·퀴즈 자료를 만들 때", "{name}로 퀴즈 만들어 줘"),
    "schedule": ("일정·알림을 다룰 때", "{name}로 알림 예약해 줘"),
}

STEPS = {
    "스킬": ["터미널(Git Bash)에서 아래 설치 명령 실행", "설치 위치를 물어보면 'Claude Code' 선택", "새 대화(세션)를 열면 적용"],
    "플러그인": ["터미널에서 claude 실행", "아래 설치 명령을 입력", "새 대화(세션)를 열면 적용"],
}


def guide_for(item: dict) -> dict:
    known = KNOWN.get(item["name"].lower(), {})
    sig = [k for k in item.get("signals", []) if k in SIGNAL_CASES]
    cases = known.get("cases") or [SIGNAL_CASES[k][0] for k in sig[:2]] or ["관련 작업을 할 때"]
    example = known.get("example") or (SIGNAL_CASES[sig[0]][1].format(name=item["name"]) if sig else f"{item['name']} 써서 해 줘")
    summary = known.get("summary") or f"{', '.join(SIGNALS[k][0] for k in sig[:2]) or '관련'} 작업을 돕는 {item['kind']}예요. (자세한 내용은 '자세히 보기')"
    tier = known.get("tier") or ("추천" if item.get("official") and item.get("verdict") == "PASS" else "확인 후")
    return {"summary": summary, "cases": cases, "example": example, "caveat": known.get("caveat", ""),
            "tier": tier, "steps": STEPS.get(item["kind"], STEPS["스킬"]), "known": bool(known)}
