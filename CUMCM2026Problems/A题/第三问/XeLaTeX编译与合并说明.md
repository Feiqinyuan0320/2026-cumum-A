# 第三问 XeLaTeX 章节

第三问正文.tex 是可并入总论文的正文；main.tex 是独立预览入口。仅制作第三问，不生成全篇摘要、关键词或 Word，也不改动第一、二问。

预览沿用现有问题一二合并稿的 A4、11 pt、页边距和行距风格，采用 TeX Live 自带 Fandol 中文字体。由内置模板初始化，属于章节排版基线，不声称为当届官方完整模板。预览将节号从3开始、表号从5开始；合并时由总稿统一管理编号。

合并时复制第三问正文.tex、figs/ 和 tables/，在总稿中加入 \input{第三问正文.tex}。总稿需有 amsmath、amssymb、booktabs、graphicx、float、caption 宏包，并设置 \graphicspath{{figs/}}，或把该目录追加到已有图片搜索路径。章节标签均带 q3 前缀。

图使用已完成计算的数据。按用户后续要求，三张图的坐标轴、图例和图内标注已改为英文，正文及图题仍为中文，未重新运行数值模型。中文图留存在版本留存/中文图版；figures/ 中的 PDF、SVG 和 PNG 为英文标注版。

最新预览为第三问_完整章节_英文图版.pdf，配套源码包为第三问_XeLaTeX源码_英文图版.zip。本次沿用改图开始前的当前正文源稿。

进入本文件旁的 LaTeX 子目录后，可用以下命令编译：

    latexmk -norc -xelatex -interaction=nonstopmode -halt-on-error -outdir=build main.tex

本次交付通过技能工具在临时副本中以 XeLaTeX 实际构建，构建记录随预览 PDF 保存。仅章节范围的结构与版面核验不套用完整论文的摘要、关键词、总页数和图表数量要求。
