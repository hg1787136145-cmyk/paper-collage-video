---
name: paper-collage-video
description: 将口播稿、观点句或抽象概念制作成 editorial halftone paper-collage / 半调纸拼贴 B-roll。用户提到“collage b-roll”“纸拼贴 b-roll”“半调拼贴”“拼贴风格配画面”“用这段文稿做拼贴动画”“paper-collage-video”，或希望把文稿拆成纸拼贴静帧、图生视频时使用。严格执行三阶段审批：先确认视觉隐喻，再确认静帧，最后才调用视频 provider。默认使用 Yijia `/v1/videos`；仅在用户明确要求官方 Gemini 或 Veo 时切换旧链路。密钥只从环境变量读取。
---

# Paper Collage Video

把文稿压缩成清晰的视觉隐喻，再制作成统一风格的纸拼贴组装动画。

## 强制原则

- 一句话只承载一个视觉隐喻，使用 3–6 个关键物件。
- 严格依次执行 Gate 1、Gate 2、Gate 3，不跳过审批。
- 同一批画面使用统一底色；用户未指定时使用墨绿 `#1E4F3D`。
- Gate 3 默认一张确认静帧配一条 prompt，不上传参考视频或多图组合。
- 不显示、打印或写入 API key、AK/SK、完整环境文件或预签名 URL 查询参数。
- 不使用知名 IP、真实名人肖像、品牌标志、标志性服饰/道具、受版权保护音乐或近似复刻指令。

## 启动检查

每次触发后、进入 Gate 1 前运行：

```bash
bash <本 skill 目录>/scripts/check_setup.sh
```

脚本自动读取 `<本 skill 目录>/.env.local` 和
`~/.config/paper-collage-video.env`。缺少配置时只说明缺失项和配置方法，不展示已有值。

需要配置或切换视频服务时，读取 [references/providers.md](references/providers.md)。

## Gate 1：确认视觉隐喻

只输出方案，不生成图片，不调用视频模型。每条包含：

- 核心意思
- 情绪
- 一句话视觉命题
- 3–6 个关键物件
- 统一底色与局部点色
- 预期组装顺序

用户未指定底色时，明确写出“统一底色：墨绿 `#1E4F3D`”。用户回复“可以”“通过”或“全部通过”且未修改底色，视为接受默认底色。

只将明确通过的编号推进 Gate 2；其余条目留在 Gate 1 修改。

## Gate 2：生成并确认静帧

仅为 Gate 1 已通过的条目执行：

1. 写入自包含的 `visual-spec.json`。
2. 写入 imagegen prompt，并使用 Codex 内置 `image_gen` 生成最终静帧。
3. 保留原始静帧，生成带编号的 contact sheet。
4. 写入 `<project>/gate2-qa.md`。
5. 展示结果并停止，等待用户确认；不要调用视频 provider。

只将明确通过的静帧推进 Gate 3；需要修改的条目重新生成并再次确认。

生成规范、提示词模板和静帧 QA 见
[references/still-generation.md](references/still-generation.md)。

## Gate 3：生成视频

仅为 Gate 2 已通过的静帧执行。不要再次询问模型；使用当前环境配置的 provider。

1. 每个任务只提交一张确认静帧和一条对应 prompt。
2. 默认按编号顺序生成；小并发失败时停止并核对状态。
3. 已返回 task id 的失败先查询进度和结果，不要立即重复提交。
4. 保留 provider 原始视频，使用 `ffprobe` 记录真实参数。
5. 生成每条及批量 contact sheet，并写入 `gate3-qa.md`。
6. 若请求参数与服务商实际返回不一致，在 QA 中同时记录两者。
7. 仅在用户明确要求精确时长、无声或统一编码时生成衍生文件，不覆盖原始视频。

执行命令、动画 prompt、任务格式和 QA 标准见
[references/video-generation.md](references/video-generation.md)。

## 项目与交付

以北京时间 `Asia/Shanghai` 创建：

```text
~/hyperframes-projects/YYYY-MM-DD-collage-broll-标题/
```

推荐结构和命名见
[references/project-layout.md](references/project-layout.md)。

默认交付：

- 每条视频的本地绝对路径链接
- 批量 contact sheet
- `gate3-qa.md`
- Provider 异常行为的简短说明

用户要求“原始视频”时只交付原始文件；用户要求“剪辑可用版本”时再补充精确时长、无音轨或统一编码的衍生文件。

