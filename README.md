# paper-collage-video

<p align="center">
  <img src="assets/demo-employee-starts-work.gif" width="220" alt="墨绿底：agent 员工开始工作">
  <img src="assets/demo-stop-vibe-loop.gif" width="220" alt="墨绿底：停止低效循环">
  <img src="assets/demo-real-value-path.gif" width="220" alt="墨绿底：通向真实价值的路径">
</p>

把口播稿、观点句或抽象概念做成高级编辑风半调纸拼贴 B-roll：先拆视觉隐喻，再生成静帧，最后调用 Yijia 视频 API 做图生视频。

## 当前能力

- 9:16 纸拼贴静帧：统一色场、halftone cut-out、奶油白纸边、卡纸点色。
- 三阶段审批：隐喻确认 -> 静帧确认 -> 视频生成。
- 视频 provider：默认 Yijia `/v1/videos`；官方 Gemini 保留为明确要求时才用的旧链路。
- 本地图片可自动上传到火山 TOS，生成 provider 可访问的临时 URL。
- 批量生成后输出 `gate3-qa.md`、逐条 `run-result.json`、contact sheet 和汇总视频文件夹。

## 工作流

1. **Gate 1 隐喻确认**
   只输出核心意思、情绪、视觉命题、关键物件、统一底色、组装顺序。不生成图片或视频。

2. **Gate 2 静帧确认**
   生成纸拼贴静帧和 contact sheet，写入 `gate2-qa.md`，等待确认。

3. **Gate 3 视频生成**
   使用当前 `GBRO_VIDEO_PROVIDER` 调用对应脚本。默认一张图一条 prompt，不上传参考视频，不传多图组合。

默认底色：墨绿 `#1E4F3D`。README 顶部示例 GIF 使用同一套默认底色；用户可以在 Gate 1 指定其他统一底色。

## 安装

把仓库克隆到 Codex skills 目录：

```bash
git clone https://github.com/<your-name>/paper-collage-video.git ~/.codex/skills/paper-collage-video
```

也可以把整个目录复制到：

```text
~/.codex/skills/paper-collage-video
```

复制示例配置并填入自己的密钥：

```bash
cp .env.example .env.local
```

`.env.local` 已被 `.gitignore` 忽略，不要提交。

## 配置

脚本会自动加载：

- `.env.local`
- `~/.config/paper-collage-video.env`

不要把真实密钥写进 `SKILL.md`、README、batch JSON 或项目文档。

### Provider

```bash
export GBRO_VIDEO_PROVIDER="yijia"   # yijia | gemini
```

Yijia 示例：

```bash
export YIJIA_API_BASE="https://api.yijiarj.cn"
export YIJIA_API_KEY="你的key"
export YIJIA_VIDEO_MODEL="omni_flash_nowater"
export YIJIA_VIDEO_SIZE="720x1280"
export YIJIA_VIDEO_DURATION="6"
export YIJIA_DURATION_FIELD="response_format.duration"
```

火山 TOS：

```bash
export TOS_ACCESS_KEY_ID="你的火山AK"
export TOS_SECRET_ACCESS_KEY="你的火山SK"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="你的桶名"
export TOS_URL_MODE="presign"
export TOS_PRESIGN_EXPIRES="86400"
```

检查环境：

```bash
bash scripts/check_setup.sh
```

依赖：

- Python 3.9+
- `ffmpeg` / `ffprobe`
- 火山 TOS 上传时需要 `tos`：`python3 -m pip install --user -r requirements.txt`

## 脚本

```text
scripts/
├── check_setup.sh              # 环境自检
├── upload_tos_asset.py         # 上传本地素材到火山 TOS
├── generate_yijia_video.py     # Yijia /v1/videos
├── generate_video.py           # 官方 Gemini 旧链路
├── generate_veo_first_last.py  # 旧 Veo 链路
└── upload_file.py              # Gemini Files API 上传辅助
```

## Yijia 注意事项

实测中，服务商可能出现这些行为：

- 请求 `omni_flash_nowater`，详情接口返回 `omni-fast`。
- 请求 `response_format.duration="6"`，实际下载视频约为 `10.005s`。
- 视频可能带音轨。

因此 Gate 3 会保留原始视频，用 `ffprobe` 记录真实参数。只有用户明确要求时，才额外生成精确时长或无声衍生文件。

## 项目输出

推荐项目目录：

```text
~/hyperframes-projects/YYYY-MM-DD-collage-broll-标题/
├── brief.md
├── visual-spec.json
├── imagegen-prompts.md
├── gate2-qa.md
├── gate3-qa.md
├── still-contact-sheet.jpg
├── yijia-jobs.json
├── <provider>-contact-sheet-all.jpg
├── <provider>-run-vXX-all-videos/
└── 01-concept/
    ├── frames/
    └── <provider>/run-vXX/
        ├── final-6s.mp4
        ├── run-result.json
        └── contact-sheet.jpg
```

## 使用

触发词：

- `collage b-roll`
- `纸拼贴 b-roll`
- `半调拼贴`
- `拼贴风格配画面`
- `paper-collage-video`

示例：

```text
用纸拼贴 b-roll 处理这段口播：很多人以为 AI 是来替你思考的，其实它更像一面镜子，会把你问题里的漏洞照出来。
```

然后按 Gate 1 -> Gate 2 -> Gate 3 逐步确认即可。

## 安全

- 不要提交 `.env.local`、真实 API key、火山 AK/SK、预签名 URL 或生成结果里的 provider 响应。
- `run-result.json` 会脱敏 API key，但仍可能包含任务 id 和 provider 元数据；公开示例前请人工检查。
- 发布前运行：

```bash
python3 scripts/scan_secrets.py .
```
