# 项目结构与命名

```text
<project>/
├── brief.md
├── visual-spec.json
├── imagegen-prompts.md
├── gate2-qa.md
├── gate3-qa.md
├── still-contact-sheet.jpg
├── yijia-jobs.json
├── <provider>-contact-sheet-all.jpg
├── <provider>-run-vXX-all-videos/
├── 01-concept/
│   ├── frames/
│   │   ├── last-frame-original.png
│   │   └── last-frame.png
│   └── <provider>/run-vXX/
│       ├── final-6s.mp4
│       ├── run-result.json
│       └── contact-sheet.jpg
└── 02-concept/...
```

命名规则：

- `final-6s.mp4` 表示请求的目标时长，仍须用 `ffprobe` 核对真实时长。
- 无声衍生文件命名为 `final-noaudio.mp4` 或 `final-6s-noaudio.mp4`，不要覆盖原始视频。
- 汇总时创建 `<provider>-run-vXX-all-videos/`，按 `01-...mp4`、`02-...mp4` 顺序复制。
- 批量项目生成 `<provider>-contact-sheet-all.jpg` 和统一的 `gate3-qa.md`。
