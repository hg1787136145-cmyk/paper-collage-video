# Provider 配置

## 选择规则

`GBRO_VIDEO_PROVIDER` 决定 Gate 3 的视频链路，默认为 `yijia`。

| provider | 脚本 | 主要环境变量 | 使用条件 |
|---|---|---|---|
| `yijia` | `scripts/generate_yijia_video.py` | `YIJIA_API_KEY` | 默认 |
| `gemini` | `scripts/generate_video.py` | `GEMINI_API_KEY` | 用户明确要求官方 Gemini |

`scripts/generate_veo_first_last.py` 是旧 Veo 首尾帧链路，仅在用户明确要求 Veo 或首尾帧模型时使用。

## Yijia

推荐配置：

```bash
export GBRO_VIDEO_PROVIDER="yijia"
export YIJIA_API_BASE="https://api.yijiarj.cn"
export YIJIA_VIDEO_MODEL="omni_flash_nowater"
export YIJIA_VIDEO_SIZE="720x1280"
export YIJIA_VIDEO_DURATION="6"
export YIJIA_DURATION_FIELD="response_format.duration"
```

本地图片提交前必须转换成公网 URL。优先使用火山 TOS：

```bash
export TOS_ACCESS_KEY_ID="你的火山AK"
export TOS_SECRET_ACCESS_KEY="你的火山SK"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="你的桶名"
export TOS_URL_MODE="presign"
export TOS_PRESIGN_EXPIRES="86400"
```

`TOS_ENDPOINT` 可不填，脚本会按 region 推导。也可使用
`YIJIA_PUBLIC_ASSET_ROOT` 和 `YIJIA_PUBLIC_ASSET_BASE_URL` 映射公网目录。

Yijia 链路仅使用 Python 标准库与 TOS 上传依赖；官方 Gemini 链路需要 `google-genai >= 2.10.0`。

## 已知行为

服务商详情可能把请求的 `omni_flash_nowater` 返回为 `omni-fast`；请求
`response_format.duration="6"` 时，也可能返回约 10 秒的视频。

遇到这种情况：

- 保留原始视频。
- 用 `ffprobe` 记录真实时长、尺寸、帧率和音轨。
- 在 `gate3-qa.md` 同时记录请求参数与实际返回。
- 仅在用户明确要求时生成裁剪或无声衍生文件。

“输入视频 8–10 秒”的限制只适用于参考视频模式；默认图片输入模式不上传参考视频。

