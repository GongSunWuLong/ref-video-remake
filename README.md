# ref-video-remake · 对标参考视频做口播短视频

一个 Claude Code skill。给它一条**参考视频**，再给一段**文案**，它会按参考视频的画面比例、剪辑节奏和字幕样式，做出一条新的竖屏口播短视频（抖音 / 视频号 / TikTok / Reels / Shorts）。

- **配音**：AI 配音（多种中文音色可以先试听），或者用你自己的录音（自动逐字对齐）
- **素材**：无版权网站（Pexels），或者你的本地素材库，也可以两者混用
- **字幕**：自动按语音切分、逐字对齐；内置多套抖音常见字幕样式，可以换颜色
- **图片**：带侧滑动画；素材里自带的字幕可以自动打码
- **校验**：成片交付前完整解码检查，杜绝音画不同步、跳帧、配音被加速

## 一句话安装

在 **Claude Code** 里直接发送这句话：

```
请帮我安装这个 skill：https://github.com/GongSunWuLong/ref-video-remake （按仓库 README 的安装方式执行）
```

也可以自己在终端里运行：

**Windows（PowerShell）**

```powershell
[Net.ServicePointManager]::SecurityProtocol = "Tls12"; irm https://raw.githubusercontent.com/GongSunWuLong/ref-video-remake/main/install.ps1 | iex
```

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/GongSunWuLong/ref-video-remake/main/install.sh | bash
```

**用 Claude Code 插件市场安装**

```
/plugin marketplace add GongSunWuLong/ref-video-remake
/plugin install ref-video-remake@ref-video-remake
```

需要 Python 3.9+ 和 ffmpeg。安装脚本会自动装好 Python 依赖（numpy、edge-tts），并检查环境；缺 ffmpeg 时会告诉你安装命令（Windows：`winget install Gyan.FFmpeg`，macOS：`brew install ffmpeg`）。

## 怎么用

装好后重启 Claude Code，对它说：

> 参考这个视频帮我做一条新的

它会引导你提供以下内容：

1. **参考视频**：上传文件，或者给出路径，比如 `D:\视频\参考.mp4`
2. **文案和标题**：标题是可选的，参考视频顶部有固定标题时，不给的话会自动从文案里提炼
3. **配音方式**：AI 配音（可以先试听选音色），或者你自己的录音文件
4. **素材来源**：无版权素材（Pexels），或者你的本地素材库文件夹路径，或者两者结合
5. 可选：字幕颜色、成片保存位置

之后它会依次完成：分析参考视频 → 生成或对齐配音 → 切分字幕 → 挑选素材 → 渲染 → 完整校验，最后把成片和镜头清单交给你。想改哪个镜头，直接说“第几句换成……”就行。

**示例**

> 参考 `D:\下载\参考.mp4` 帮我做一条新的。文案：今早7点，美国传来重磅好消息……想办理扣88。用云健配音，素材只用 `D:\素材库`，图片做侧滑动画。

## 工作流程

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 环境检查 | `check_env.py` | 检查 ffmpeg（含 libass、x264）、numpy、edge-tts |
| 分析参考 | `analyze_ref.py` | 分辨率、帧率、平均镜头时长、配音性别和语速、有没有背景音乐、截图 |
| 配音 | `tts.py` | AI 配音并输出逐词时间；加 `--samples` 生成多音色试听 |
| 录音对齐 | `align_recording.py` | 你自己的录音 → 逐词时间（DTW 对齐，不需要语音识别模型） |
| 切字幕 | `segment.py` | 按标点和语音停顿切成短句，过长自动拆分，太短自动合并 |
| 素材库 | `library_index.py` | 给本地素材编号（V01 / I01），生成预览图 |
| 无版权素材 | `pexels_download.py` | 只下载需要的前几秒，下载后完整校验 |
| 渲染 | `render.py` | 按 `plan.json` 出片：裁切、打码、侧滑、卡片合成、字幕、混音 |
| 校验 | `verify.py` | 完整解码：音画时长、时间戳断点、配音节奏是否一致 |

详细说明见 [`SKILL.md`](plugins/ref-video-remake/skills/ref-video-remake/SKILL.md)、[plan 格式](plugins/ref-video-remake/skills/ref-video-remake/references/plan-format.md) 和 [踩坑记录](plugins/ref-video-remake/skills/ref-video-remake/references/lessons.md)。

## 版权说明

- 这个仓库只包含代码，不包含任何视频、图片或音乐。
- Pexels 素材遵循 [Pexels License](https://www.pexels.com/license/)：可免费商用，无需署名。
- Mixkit 配乐遵循 Mixkit Free License。
- 本地素材库和参考视频的使用权由你自己负责。

## License

MIT
