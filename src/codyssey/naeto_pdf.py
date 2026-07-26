"""PDF → ask-stream 첨부 변환 (텍스트 우선, 페이지 단위 렌더 폴백).

**왜 필요한가**: 서버가 받아주는 첨부 타입은 `image` 와 `text` 뿐이다. `type:"pdf"` 는 프론트
분기에도 있지만 실제로 모델에 도달하지 않는다(모델 4종 교차 실측 — `naeto._attachment` 주석).
그래서 PDF 는 클라가 변환해서 보내야 한다.

**왜 렌더가 아니라 파싱이 기본인가**:
- 첨부 상한이 1 MiB 라 가독 DPI 렌더는 호출당 1~3페이지에서 막힌다. 텍스트는 30만자까지 들어간다.
- 숫자·금액·조항은 원문 문자열이 그대로 필요하다. 저해상도 렌더는 작은 글자를 오독한다.
- 변환 산출물이 로컬 파일로 남아 **사람도 같은 원문을 직접 읽을 수 있다**(모델만 보는 렌더와 대비).

**그래도 렌더가 필요한 경우 3가지** — 그래서 폴백을 페이지 단위로 둔다:
1. 스캔본(텍스트 레이어 없음) → 추출 0자
2. `ToUnicode` 없는 CID 서브셋 폰트(공공기관 한글→PDF 에 흔함) → 추출이 치환문자로 뭉개짐
3. 레이아웃 자체가 정보(도면·병합셀 표·도장 위치) → `--pdf-render` 로 강제

문서 통째로 한쪽을 고르지 않는 이유: 표지만 스캔인 문서에서 전부 렌더로 넘어가 상한에 걸린다.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

import pymupdf

from .config import PDF_DIR
from .naeto import ATTACH_MAX_BYTES

# 페이지가 "텍스트 없음" 으로 판정되는 하한. 머리말·페이지번호만 있는 스캔 페이지가 20~30자를
# 뱉는 경우가 있어 0 이 아니라 여유를 둔다.
MIN_CHARS_PER_PAGE = 50
# 치환문자(U+FFFD)·제어문자 비율 상한. CID 폰트 추출 실패는 글자수는 채우면서 내용이 깨진다.
MAX_GARBLED_RATIO = 0.10
# 렌더 DPI 사다리 — 상한 초과 시 위에서부터 낮춰 재시도. 80 이하는 본문 가독성이 무너져 안 내려간다.
_DPI_LADDER = (150, 110, 80)
# --pdf-dpi 수용 범위. 하한은 본문 판독 한계, 상한은 1 MiB 를 거의 확실히 넘기는 지점.
_MIN_DPI, _MAX_DPI = 40, 400
_GARBLED = re.compile(r"[�\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_pages(spec: str | None, total: int) -> list[int]:
    """"1-3,7" → [0,1,2,6] (0-based). None 이면 전체.

    사람이 세는 1-based 를 받아 0-based 로 돌려준다 — CLI 사용자와 pymupdf 인덱스 사이의 유일한 변환점.
    """
    if not spec:
        return list(range(total))
    out: list[int] = []
    for chunk in spec.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
        else:
            lo = hi = int(part)
        if lo < 1 or hi < lo:
            raise RuntimeError(f"잘못된 페이지 지정: {part!r} (1부터, 오름차순)")
        out.extend(range(lo - 1, min(hi, total)))
    seen: dict[int, None] = {}
    for i in out:
        if 0 <= i < total:
            seen[i] = None
    if not seen:
        raise RuntimeError(f"지정한 페이지가 문서 범위(1~{total}) 밖이다: {spec!r}")
    return list(seen)


def _effective(text: str) -> str:
    """판정 대상 문자 = 공백·개행을 뺀 나머지.

    공백을 세면 두 판정이 동시에 무력화된다: ① 좌표만 있는 스캔 페이지가 개행 수십 개로
    `MIN_CHARS_PER_PAGE` 를 넘겨 "텍스트 있음" 으로 통과하고 ② 분모가 부풀어 치환문자 비율이
    희석돼 깨진 페이지가 렌더로 안 넘어간다. 둘 다 빈 마크다운을 모델에 보내는 결과가 된다.
    """
    return "".join(text.split())


def _garbled_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(_GARBLED.findall(text)) / len(text)


def needs_render(text: str) -> bool:
    """이 페이지를 렌더로 보내야 하는가 — 추출 텍스트만 보고 판정(공백 제외 실효 문자 기준)."""
    eff = _effective(text)
    return len(eff) < MIN_CHARS_PER_PAGE or _garbled_ratio(eff) > MAX_GARBLED_RATIO


def _render_page(page, out: Path, dpi_ladder: Iterable[int] = _DPI_LADDER) -> Path:
    """페이지를 PNG 로 저장. 1 MiB 를 넘으면 DPI 를 낮춰 재시도.

    상한 초과분은 서버가 **에러 없이 버려서** 모델이 "첨부 없음" 이라 답한다 — 그 조용한 실패를
    여기서 막는 것이 이 루프의 목적이다.
    """
    last = 0
    for dpi in dpi_ladder:
        pix = page.get_pixmap(dpi=dpi)
        pix.save(out)
        last = out.stat().st_size
        if last <= ATTACH_MAX_BYTES:
            return out
    raise RuntimeError(
        f"{out.name}: 최저 DPI({min(dpi_ladder)})에서도 {last:,}B > 상한 {ATTACH_MAX_BYTES:,}B — "
        "페이지를 잘라 넣거나(--pdf-pages) 원본을 축소하라."
    )


def _out_dir(src: Path, out_dir: Path | None) -> Path:
    """산출물 디렉터리 = `media/pdf/<stem>-<경로해시8>/` (아직 비우지 않는다).

    해시를 붙이는 이유: `a/계약서.pdf` 와 `b/계약서.pdf` 는 stem 이 같아 한 디렉터리를 공유하게
    되고, 나중 호출이 앞 문서의 `.md` 를 덮어써 **엉뚱한 문서를 첨부**할 수 있다(원본 파일명이
    같으니 로그로도 구분이 안 된다). 절대경로 해시를 섞으면 문서마다 자리가 갈리고, 같은 문서를
    다시 변환하면 같은 자리를 재사용해 디렉터리가 무한히 늘지 않는다.
    """
    digest = hashlib.sha256(str(src.resolve()).encode()).hexdigest()[:8]
    d = (out_dir or PDF_DIR) / f"{src.stem}-{digest}"
    d.mkdir(parents=True, exist_ok=True)  # 쓰는 쪽에서 늦게 만든다(config 는 생성하지 않는다)
    return d


def _clear_stale(dest: Path) -> None:
    """이전 실행 산출물 제거 — **문서 검증을 통과한 뒤에만** 부른다.

    비우는 이유: 이전 실행이 `--pdf-pages 1-5`, 이번이 `1-2` 면 p003~005.png 가 남아
    "디렉터리에 있는 것 = 이번에 보낸 것" 이 깨진다. 반환 목록엔 안 들어가니 전송 자체는
    정확하지만, 사람이 산출물을 눈으로 확인할 때 오독한다.

    검증 뒤로 미루는 이유: 암호·0페이지·손상 PDF 로 재시도하면 지우기만 하고 새로 못 만들어
    **마지막 정상 산출물까지 잃는다**.
    """
    for stale in (*dest.glob("p*.png"), *dest.glob("*.md")):
        stale.unlink()


def pdf_attachments(
    path: str | Path,
    *,
    out_dir: Path | None = None,
    pages: str | None = None,
    force_render: bool = False,
    dpi: int | None = None,
) -> tuple[list[Path], list[str]]:
    """PDF → 첨부로 보낼 **파일 경로 목록** + 사람이 읽을 판정 로그.

    경로를 돌려주는 이유: 기존 첨부 배관(`naeto.chat(attachments=[경로])`)이 그대로 쓰이고,
    확장자로 mediaType 이 정해진다(`.md`→text/markdown, `.png`→image/png). 산출물이 디스크에
    남아 사람이 원문을 직접 읽을 수도 있다.

    - 텍스트로 판정된 페이지는 **하나의 `.md`** 로 합쳐 페이지 경계 마커(`--- p.3/12 ---`)를 남긴다
      (인용할 때 몇 페이지인지 말할 수 있어야 한다).
    - 렌더로 판정된 페이지는 **페이지당 PNG 1장**.
    """
    src = Path(path)
    if not src.is_file():
        raise RuntimeError(f"PDF 없음: {src}")
    if dpi is not None and not _MIN_DPI <= dpi <= _MAX_DPI:
        # 0·음수는 pixmap 단계에서 알아보기 힘든 예외로 터지고, 과대값은 상한 초과 렌더를 만든다.
        raise RuntimeError(f"--pdf-dpi 는 {_MIN_DPI}~{_MAX_DPI} 범위여야 한다(받은 값: {dpi}).")
    dest = _out_dir(src, out_dir)
    ladder = (dpi,) if dpi else _DPI_LADDER

    text_chunks: list[str] = []
    images: list[Path] = []
    log: list[str] = []
    # import 이름은 `pymupdf` 를 쓴다 — `fitz` 는 상류가 남겨둔 레거시 별칭이다.
    with pymupdf.open(src) as doc:
        # 암호 PDF 는 open 이 성공하고 needs_pass 만 True 다 — 그대로 두면 전 페이지 추출 0자로
        # 렌더 폴백에 흘러가 pixmap 단계에서 알 수 없는 예외가 되거나 빈 이미지가 나간다.
        if doc.needs_pass:
            raise RuntimeError(f"{src.name}: 암호가 걸린 PDF — 해제본으로 변환해 다시 시도하라.")
        total = doc.page_count
        if total == 0:
            raise RuntimeError(f"{src.name}: 페이지가 0개다(손상·빈 PDF).")
        targets = parse_pages(pages, total)  # 페이지 지정 오류도 지우기 전에 걸러낸다
        _clear_stale(dest)
        for idx in targets:
            page = doc[idx]
            # get_text 는 option 에 따라 str/list/dict 를 돌려주는 다형 API → "text" 만 str 이다.
            # 다른 옵션으로 바뀌면 빈 문자열 → 렌더 폴백으로 흘러 눈에 보인다.
            raw = "" if force_render else page.get_text("text")
            text = raw if isinstance(raw, str) else ""
            if force_render or needs_render(text):
                png = _render_page(page, dest / f"p{idx + 1:03d}.png", ladder)
                images.append(png)
                why = "강제" if force_render else "텍스트 없음/깨짐"
                log.append(f"p.{idx + 1}/{total} → 렌더({why}, {png.stat().st_size:,}B)")
            else:
                text_chunks.append(f"--- p.{idx + 1}/{total} ---\n{text.strip()}")
                log.append(f"p.{idx + 1}/{total} → 텍스트({len(text.strip()):,}자)")

    out: list[Path] = []
    if text_chunks:
        md = dest / f"{src.stem}.md"
        body = f"# {src.name} (텍스트 추출)\n\n" + "\n\n".join(text_chunks) + "\n"
        md.write_text(body, encoding="utf-8")
        size = md.stat().st_size
        if size > ATTACH_MAX_BYTES:
            raise RuntimeError(
                f"{md.name}: 추출 텍스트 {size:,}B > 상한 {ATTACH_MAX_BYTES:,}B — "
                "--pdf-pages 로 페이지를 나눠 여러 번 보내라."
            )
        log.append(f"텍스트 {len(text_chunks)}페이지 → {md.name} ({size:,}B)")
        out.append(md)
    out.extend(images)
    if not out:
        raise RuntimeError(f"{src.name}: 변환 결과가 비었다(페이지 지정 확인).")
    return out, log


def iter_attachment_paths(
    pdfs: Iterable[str],
    *,
    pages: str | None = None,
    force_render: bool = False,
    dpi: int | None = None,
) -> Iterator[tuple[Path, list[str]]]:
    """여러 PDF 를 순서대로 변환 — (경로, 판정로그) 를 흘린다. 로그는 PDF 별 첫 경로에만 붙는다."""
    for p in pdfs:
        paths, log = pdf_attachments(p, pages=pages, force_render=force_render, dpi=dpi)
        for i, path in enumerate(paths):
            yield path, (log if i == 0 else [])
