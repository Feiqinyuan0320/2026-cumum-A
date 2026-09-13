"""Create portable Markdown and inspect the already-compiled Q4 chapter."""
from pathlib import Path
import importlib.util
import json
import re
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    src = (root/'LaTeX/第四问正文.tex').read_text()
    src = src.replace(r'\input{tables/table6.tex}', (root/'LaTeX/tables/table6.tex').read_text())
    refs = {}
    for kind, start, prefix in [('equation', 1, '4.'), ('figure', 1, ''), ('table', 6, '')]:
        for i, block in enumerate(re.findall(r'\\begin\{'+kind+r'\}(.*?)\\end\{'+kind+r'\}', src, re.S), start):
            for label in re.findall(r'\\label\{([^}]+)\}', block):
                refs[label] = prefix+str(i)
    src = re.sub(r'\\eqref\{([^}]+)\}', lambda m: '（'+refs[m[1]]+'）', src)
    src = re.sub(r'\\ref\{([^}]+)\}', lambda m: refs[m[1]], src)
    src = re.sub(r'\\label\{[^}]+\}', '', src)
    figures = []
    def take_figure(match):
        block = match[0]
        file = re.search(r'\\includegraphics\[[^]]*\]\{([^}]+)\}', block)[1]
        # Caption ends at its own newline, so nested math braces are preserved.
        cap = re.search(r'\\caption\{(.*)\}\s*\n', block)[1]
        i = len(figures)+1
        figures.append(f'![图{i}](figures/{Path(file).stem}.png)\n\n图{i}：{cap}')
        return f'QFOURFIGTOKEN{i}\n'
    src = re.sub(r'\\begin\{figure\}.*?\\end\{figure\}', take_figure, src, flags=re.S)
    result = subprocess.run(['/opt/anaconda3/bin/pandoc', '--from=latex', '--to=gfm+tex_math_dollars', '--wrap=none'],
                            input=src, text=True, capture_output=True, check=True).stdout
    result = re.sub(r'\$`(.*?)`\$', lambda m: '$'+m[1]+'$', result, flags=re.S)
    equation = 0
    def portable_math(match):
        nonlocal equation
        equation += 1
        body = match[1].replace(r'\begin{equation}', '').replace(r'\end{equation}', '').strip()
        return '\n$$\n'+body+f'\n\\tag{{4.{equation}}}\n$$\n'
    result = re.sub(r'``` math\n(.*?)\n```', portable_math, result, flags=re.S)
    for i, figure in enumerate(figures, 1):
        result = result.replace(f'QFOURFIGTOKEN{i}', figure)
    assert equation == 12 and len(figures) == 3
    assert not any(v in result for v in ['QFOURFIGTOKEN', '``` math', '<figure', r'\ref{'])
    (root/'第四问正文.md').write_text(result)

    tool = Path('/Users/baitutu/.codex/skills/math-modeling/tools/latex/scripts/latex_paper.py')
    spec = importlib.util.spec_from_file_location('latex_paper', tool)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    audit = mod.inspect_paper(root/'LaTeX/main.tex', contest='cumcm', pdf_path=root/'第四问.pdf', quality_checks=True,
                              min_content_units=1800, min_pages=3, min_equations=10, min_figures=3, min_tables=2,
                              body_start_page=1, questions=['q4'],
                              override_reason='用户要求第四问独立正文及3张英文图；不生成整篇摘要关键词，质量阈值按单章范围核对。')
    issues = [v for v in audit['issues'] if v not in ['缺少摘要环境', '缺少关键词命令']]
    report = {'scope': '第四问独立章节', 'chapter_passed': not issues, 'chapter_issues': issues,
              'raw_full_paper_audit': audit}
    (root/'检查记录/第四问PDF校验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if issues:
        raise RuntimeError(issues)
    preview = root/'检查记录/PDF最终预览'; preview.mkdir(exist_ok=True)
    subprocess.run(['/opt/homebrew/bin/pdftoppm', '-scale-to', '1400', '-png', str(root/'第四问.pdf'), str(preview/'page')], check=True)
    print(json.dumps({'status': 'PASS', 'pages': audit['rendered_pages'], 'metrics': audit['metrics'],
                      'Markdown_figures': len(figures), 'Markdown_equations': equation}, ensure_ascii=False))


if __name__ == '__main__':
    main()
