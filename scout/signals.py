"""작업 신호 사전.

내 대화(한국어 위주)에서 찾을 단어와, 후보 설명(영어 위주)에서 찾을 단어를 한 쌍으로 묶는다.
같은 신호에 걸리면 "내가 자주 하는 일"과 "그 후보가 하는 일"이 겹친다고 본다.
"""

# key: (한국어 라벨, 내 대화에서 찾을 단어, 후보 설명에서 찾을 단어)
SIGNALS: dict[str, tuple[str, list[str], list[str]]] = {
    "pdf": ("PDF", ["pdf"], ["pdf"]),
    "slides": ("발표자료", ["ppt", "pptx", "발표", "슬라이드", "덱"], ["slide", "slides", "presentation", "pptx", "deck"]),
    "docs": ("문서·README", ["readme", "보고서", "문서", "docx", "워드"], ["docx", "word document", "documentation", "readme", "markdown", "technical writing"]),
    "sheet": ("엑셀·CSV", ["엑셀", "xlsx", "csv", "스프레드시트", "시트"], ["excel", "xlsx", "spreadsheet", "csv", "sheets"]),
    "python": ("파이썬·Streamlit", ["streamlit", "파이썬", "python"], ["python", "streamlit", "pyright", "pip"]),
    "git": ("Git·GitHub", ["커밋", "commit", "push", "github", "깃허브", "깃"], ["git", "github", "commit", "pull request", "commits"]),
    "review": ("코드 리뷰·버그", ["리뷰", "버그", "오류", "에러", "고쳐", "리팩"], ["code review", "bug", "bugs", "refactor", "refactoring", "simplify", "lint", "linting", "debugging"]),
    "frontend": ("웹 화면·디자인", ["html", "css", "디자인", "화면", "프론트", "웹사이트"], ["frontend", "front-end", "ui design", "web design", "css", "html", "tailwind", "landing page", "react"]),
    "deploy": ("배포", ["배포", "deploy", "render", "vercel", "pages"], ["deploy", "deployment", "vercel", "hosting", "netlify", "cloudflare"]),
    "db": ("DB", ["supabase", "sql", "데이터베이스", "tidb", "mysql", "db"], ["database", "sql", "supabase", "postgres", "postgresql", "mysql"]),
    "data": ("데이터 분석", ["데이터", "분석", "pandas", "시각화", "차트"], ["data analysis", "analytics", "chart", "charts", "visualization", "pandas", "notebook", "jupyter"]),
    "llm": ("LLM·에이전트", ["langchain", "langgraph", "rag", "에이전트", "llm", "프롬프트"], ["llm", "llms", "rag", "langchain", "langgraph", "prompt engineering", "ai agent", "ai agents", "agent sdk"]),
    "mcp": ("MCP", ["mcp"], ["mcp", "model context protocol"]),
    "browser": ("웹 자동화·크롤링", ["크롤링", "스크래핑", "브라우저", "playwright", "셀레니움", "크롤러"], ["browser", "playwright", "scraping", "scrape", "crawl", "crawler", "puppeteer"]),
    "notion": ("노션", ["노션", "notion"], ["notion"]),
    "chat": ("메신저 연동", ["디스코드", "discord", "슬랙", "slack", "텔레그램"], ["discord", "slack", "telegram"]),
    "blog": ("블로그·글쓰기", ["블로그", "티스토리", "회고"], ["blog", "writing", "copywriting", "seo"]),
    "test": ("테스트", ["테스트", "pytest", "검증"], ["unit test", "unit tests", "testing", "test coverage", "e2e", "pytest"]),
    "security": ("보안", ["보안", "security", "api key", "비밀값"], ["security", "secret", "secrets", "vulnerability", "owasp"]),
    "media": ("영상·이미지", ["영상", "동영상", "이미지", "video", "썸네일"], ["video", "videos", "image generation", "animation", "remotion"]),
    "game": ("게임", ["게임"], ["game", "games", "unity", "godot"]),
    "learning": ("공부·퀴즈", ["퀴즈", "공부", "시험", "자격증", "기출"], ["learning", "quiz", "education", "tutor", "flashcard"]),
    "schedule": ("일정·알림", ["일정", "캘린더", "예약", "알림"], ["calendar", "schedule", "scheduling", "reminder", "cron"]),
}
