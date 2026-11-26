# ChunkLab third-party notices

ChunkLab 1.0.0 is licensed under the MIT License by ChunkLab Authors. The project does not vendor third-party source code and does not claim ownership of upstream projects. Package installation resolves third-party dependencies from their normal distributions; keep their license files with any redistributed dependency artifacts.

## Direct runtime dependencies

These are used by ChunkLab at runtime, based on `pyproject.toml` and the versions exercised in the independently tested Linux/Python 3.12 release environment.

| Dependency | Tested version | Purpose | License metadata | Upstream reference |
| --- | ---: | --- | --- | --- |
| beautifulsoup4 | 4.15.0 | HTML text extraction | MIT License | https://www.crummy.com/software/BeautifulSoup/bs4/ |
| lxml | 6.1.3 | BeautifulSoup parser backend for HTML/XML parsing | BSD-3-Clause | https://lxml.de/ |
| markdown-it-py | 4.3.0 | Markdown block parsing | License file in upstream distribution | https://github.com/executablebooks/markdown-it-py |
| streamlit | 1.67.0 | Local GUI and AppTest-supported app surface | Apache-2.0 | https://streamlit.io/ |

## Test-only dependency

| Dependency | Tested version | Purpose | License metadata | Upstream reference |
| --- | ---: | --- | --- | --- |
| pytest | 9.2.0 | Test runner | MIT | https://docs.pytest.org/ |

## Reference material

The held-out Korean benchmark case uses ChunkLab-authored paraphrases, not copied legal excerpts. It is not legal advice. Source references named in benchmark output and release notes:

- E-Commerce Act effective 2026-07-21: https://www.law.go.kr/LSW/lsInfoP.do?ancNo=21312&ancYd=20260120&efYd=20260721&lsiSeq=282793
- Enforcement Decree effective 2026-07-21: https://www.law.go.kr/LSW/lsInfoP.do?efYd=20260721&lsiSeq=288143
