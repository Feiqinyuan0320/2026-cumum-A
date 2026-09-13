# 第一问结构稿编译状态

用户已转入第三问计算，本结构稿留待后续 Sol 生成正文。

- 结构交接：`第一问结构调整_交接给Sol.md`；独立结构审查通过。
- 源码：`LaTeX结构稿/main.tex`；正文与附录分别在 `sections/`、`appendices/`。
- 已用随附 Tectonic 0.17.0 试编译，退出码0，得到 `LaTeX结构稿/build/main.pdf`（6页）。这只是结构预览，正文尚未补齐。
- 本机未发现 XeLaTeX/MacTeX/TeX Live。Tectonic 的实际小样本编译成功，可继续用于这个简单项目。
- 试编译最后一轮仍有系统字体 STSong、STFangsong 的 CJK script 警告；尚未做最终字体修正与版面验收，不能称为正式论文排版通过。
- 记录：`LaTeX试编译记录.json`。切换模型后先补正文，再从源码重新编译并处理字体警告，不直接使用当前预览作为正式稿。

编译命令（在任何工作目录均可运行）：

```sh
/Users/baitutu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  /Users/baitutu/.codex/plugins/cache/openai-bundled/latex/0.2.6/scripts/compile_latex.py \
  '/Users/baitutu/大学资料/数模/CUMCM2026Problems/A题/第一问/LaTeX结构稿/main.tex' \
  --compiler tectonic \
  --output-directory '/Users/baitutu/大学资料/数模/CUMCM2026Problems/A题/第一问/LaTeX结构稿/build'
```
