"""Splits headings into word masks for the rolling text reveal (animations.css: .reveal-word).

    python tools/split_words.py

Targets every section headline (h2.h2 inside <main>) and the six benefit titles
(.bfact h3) in index.html. Each word becomes

    <span class="w" style="--w:N"><span>WORD</span></span>

and keeps its place in the text: spaces stay real spaces, so the headline wraps
exactly as before at every width (text-wrap: balance included). Inline markup such
as <em> is kept, with its words wrapped inside it. The heading gets aria-label with
its plain text, so assistive technology reads whole words, never fragments.

Re-running is safe: existing word wrappers are removed first. After editing a
headline's text, run this again.
"""
import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "index.html")

# opening tags of the elements to split (attributes may vary)
TARGETS = [
    re.compile(r'<h2 class="h2[^"]*"[^>]*>'),
    re.compile(r'(?<=<div>)<h3(?:\s[^>]*)?>'),   # .bfact h3: <li class="bfact">...<div><h3>
]
UNWRAP = re.compile(r'<span class="w" style="--w:\d+"><span>(.*?)</span></span>')
TAG = re.compile(r"(<[^>]+>)")


def split_inner(inner):
    inner = UNWRAP.sub(r"\1", inner)
    out, n = [], 0
    for part in TAG.split(inner):
        if not part:
            continue
        if part.startswith("<"):
            out.append(part)
            continue
        for tok in re.split(r"(\s+)", part):
            if not tok:
                continue
            if tok.isspace():
                out.append(" ")
            else:
                out.append(f'<span class="w" style="--w:{n}"><span>{tok}</span></span>')
                n += 1
    text = html.unescape(TAG.sub("", inner))
    return "".join(out), " ".join(text.split())


def process(page):
    count = 0
    for opener in TARGETS:
        pos = 0
        while True:
            m = opener.search(page, pos)
            if not m:
                break
            tag = m.group(0)
            name = re.match(r"<(h[23])", tag).group(1)
            end = page.index(f"</{name}>", m.end())
            inner, label = split_inner(page[m.end():end])
            # class reveal-word + aria-label on the opening tag (idempotent)
            new_tag = re.sub(r'\saria-label="[^"]*"', "", tag)
            if "class=" in new_tag:
                if "reveal-word" not in new_tag:
                    new_tag = re.sub(r'class="([^"]*)"', r'class="\1 reveal-word"', new_tag, count=1)
            else:
                new_tag = new_tag[:-1] + ' class="reveal-word">'
            new_tag = new_tag[:-1] + f' aria-label="{html.escape(label, quote=True)}">'
            page = page[:m.start()] + new_tag + inner + page[end:]
            pos = m.start() + len(new_tag) + len(inner)
            count += 1
    return page, count


def main():
    with open(PAGE, encoding="utf-8", newline="") as f:
        page = f.read()
    page, n = process(page)
    with open(PAGE, "w", encoding="utf-8", newline="") as f:
        f.write(page)
    print(f"split {n} headings into word masks")


if __name__ == "__main__":
    main()
