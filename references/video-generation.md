# 视频生成

## 准备图片

保留 imagegen 原图，再生成本轮提交图：

```bash
ffmpeg -y -i <item>/frames/last-frame-original.png \
  -vf "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" \
  <item>/frames/last-frame.png
```

## 动画 prompt

默认使用英文：

```text
Create a 5-second original stop-motion paper collage animation from the supplied single image. Keep the same vertical 9:16 composition, dark green #1E4F3D paper background, paper grain, halftone cutout texture, cream paper edges, colored cardstock accents, and soft paper shadows.

Animate [3-6 original paper objects] with crisp physical stop-motion timing. [按顺序描述元素如何 slide in / snap into place / unfold / settle]. Keep the final composition close to the supplied image.

Keep the camera locked. No scene cuts, no zoom, no morphing, no new objects, no readable text, no letters, no numbers, no logos, no watermark, no interface elements, no audio, no famous IP, no real person likeness, no brand marks, no protected characters, no copyrighted music.
```

## Yijia 批任务

任务格式：

```json
{
  "prompt": "<omni_flash_nowater prompt>",
  "image": "<item>/frames/last-frame.png",
  "output": "<item>/yijia/run-v01/final-6s.mp4",
  "model": "omni_flash_nowater",
  "size": "720x1280",
  "duration": 6
}
```

执行：

```bash
python3 <本 skill 目录>/scripts/generate_yijia_video.py \
  --batch <project>/yijia-jobs.json \
  --concurrency 1
```

脚本上传本地图片、创建任务、轮询状态，并在
`status=completed` 且 `quality=standard` 后下载 `url` 指向的无水印视频。脱敏结果写入对应 run 目录的 `run-result.json`。

## QA

使用 `ffprobe` 记录：

- 文件是否存在
- task id
- Provider 返回的 model、status、quality、seconds
- 本地真实 duration、width、height、fps
- 是否存在音轨

生成 contact sheet：

```bash
ffmpeg -y -i <run>/final-6s.mp4 \
  -vf "fps=1,scale=135:240,tile=10x1" \
  -frames:v 1 <run>/contact-sheet.jpg
```

通过标准：

- 能看到从空场或少量元素逐步组装，而非整图淡入。
- 没有切镜、缩放、3D 化或写实场景漂移。
- 没有假字、logo、水印或 UI。
- 最终帧接近确认静帧；不影响隐喻的轻微姿态或零件漂移可带瑕疵通过。
- 文件参数符合用户需求；若服务商返回不同参数，在 QA 中明确说明。

