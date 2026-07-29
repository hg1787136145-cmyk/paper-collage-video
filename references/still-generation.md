# 静帧生成规范

## 视觉隐喻

提取核心意思、情绪、动作动词和可视化隐喻。优先使用打开、连接、装订、归档、点亮、压缩、分叉、组装等清晰动作，以及机器、时钟、胶片、档案柜、控制台、规则册、漏斗、轨道、棋子等易辨识物件。

不要逐字呈现文稿。每条只表达一个隐喻，并控制在 3–6 个关键物件。同一批形成前后叙事并保持统一底色，仅让局部点色随语义变化。

## `visual-spec.json`

```json
{
  "script_meaning": "",
  "visual_metaphor": "",
  "style_signature": "flat bold color field, mixed black-and-white halftone cut-outs and colored cardstock accents, crisp cut edges, cream keylines, soft paper shadows, editorial paper collage",
  "aspect_ratio": "9:16",
  "color_field": {
    "background_hex": "#1E4F3D",
    "accent_colors": [],
    "paper_grain": "fine uncoated-paper fiber"
  },
  "elements": [
    {
      "what": "",
      "role": "",
      "motion": "",
      "placement": ""
    }
  ],
  "composition": {
    "layout": "",
    "negative_space": "",
    "final_frame": ""
  },
  "motion_plan": "structure first, subject or cards second, action and result last",
  "avoid": "typography, readable letters, numerals, logos, watermark, UI, subtitles, glossy 3D, photoreal environment"
}
```

## Imagegen prompt

```text
Use case: ads-marketing
Asset type: final still frame for a 9:16 image-to-video B-roll clip
Primary request: Create a finished editorial paper-collage image expressing [一句话视觉命题].
Scene/backdrop: perfectly flat [颜色] paper field [hex] with subtle uncoated paper fiber.
Style/medium: premium editorial stop-motion paper collage; black-and-white halftone photographic cut-outs mixed with selective [点色] colored cardstock.
Composition/framing: vertical 9:16 locked poster frame; central subject within the middle 70 percent; generous clean color-field negative space; 3-6 large separable paper groups for later assemble-from-empty animation.
Materials/textures: visible printed halftone dots, crisp machine-cut edges, thin warm-cream paper keylines, soft low-opacity physical drop shadows.
Constraints: [本条隐喻必须一眼看懂的关系].
Avoid: no typography, no readable letters, no numerals, no logos, no watermark, no UI, no subtitles, no glossy 3D, no photoreal environment, no clutter.
```

## 静帧 QA

- 隐喻是否一眼看懂
- 主体是否集中
- 是否出现假字、logo、水印或 UI
- 是否保留足够纯色场，便于从空场组装
- 是否由 3–6 个清晰大组构成，而非满屏碎片
- 同一批是否统一质感和底色

