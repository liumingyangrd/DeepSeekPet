# 小深 · DeepSeek 桌宠

常驻 Windows 桌面的 Q 版鲸鱼娘女仆桌宠（PySide6）。

## 功能

- 透明无边框窗口、始终置顶、可拖动、滚轮调大小
- 10 种表情（常驻 / 开心 / 生气 / 无语 / 委屈 / 惊讶 / 害羞 / 舒服 / 饥饿 / 吃饭），
  全部共用常驻的身体与发型，只换脸，切换自然
- **摸摸**：按住不动即进入摸摸模式，动一动就是一下，会切到舒服表情
- **底部偷窥**：把她拖到屏幕最底下松手，她会变成一颗小脑袋趴在任务栏上，
  带糯叽叽的 Q 弹落座动画；抓着脑袋往上拽或点一下就弹回全身
- **饭点感应**：到点自动饥饿，右键「喂饭」喂一碗大米饭
- 冒气泡说话、双击呼出输入框，接入 DeepSeek API 真聊天
- 右键菜单：聊天 / 说句话 / 摸摸 / 喂饭 / 表情 / 大小 / 设置 / 退出
- 系统托盘常驻，可开机自启（仅打包版可用）

## 运行

```bash
pip install -r requirements.txt
python src/main.py
```

首次启动她会提醒你去填 API Key：**右键她 → 设置 → 填 API Key**
（在 [platform.deepseek.com](https://platform.deepseek.com) 申请，只保存在本机）。

配置写在 `%APPDATA%\DeepSeekPet\config.json`。

调试用参数：

| 参数 | 作用 |
| --- | --- |
| `--diag` | 把屏幕 / DPI / 窗口几何信息写到 `%APPDATA%\DeepSeekPet\diag.txt` |
| `--demo` | 重置位置并演示一次说话 + 呼出输入框 |

## 打包

```bat
pip install -r requirements.txt pyinstaller
build.bat
```

产物在 `dist\DeepSeekPet.exe`（单文件、无控制台窗口，素材已内置）。

## 目录结构

```
.
├── src/main.py            # 全部源码（单文件）
├── assets/
│   ├── sprite.webp        # 常驻立绘
│   ├── expr/*.webp        # 9 张表情差分（只换脸）
│   ├── pet.ico            # 图标
│   └── ATTRIBUTION.md     # 素材版权与署名
├── requirements.txt
├── build.bat
└── LICENSE
```

## 关于本仓库：源码是逆向还原的

原始 `main.py` 丢失了，只剩 PyInstaller 打包出来的 `DeepSeekPet.exe`，
本仓库的源码是从这个 exe 里**反推回来**的：

1. exe 是 PyInstaller 打包的 Python 3.13 + PySide6 程序（单文件，素材内置）；
2. 用 pyinstxtractor 解出 CArchive，得到 `main.pyc` 与 `assets/`；
3. 用 Python 3.13 自带的 `dis` 把 `main.pyc` 展开成逐函数字节码清单；
4. 按清单逐个函数重写源码；
5. **校验**：把重写结果重新编译，与原 `main.pyc` 逐函数比对——
   81 个代码对象（含 `lambda` / 生成器）的指令序列、常量表、`co_names`、
   `co_varnames`、参数签名全部一致，仅源码行号（`__firstlineno__`）
   因排版习惯不同而略有偏移。

也就是说：逻辑是原版的逻辑，函数名、变量名、中文文案、样式表、魔数都保留了；
注释与排版是按代码行为补的（原注释不可恢复）。

## 素材版权

代码以 [MIT](LICENSE) 发布，但 `assets/` 下的图像素材是第三方二创作品，
**不适用 MIT**，详见 [assets/ATTRIBUTION.md](assets/ATTRIBUTION.md)。
角色形象以 **CC BY-NC-SA 4.0** 开放二创，仅限个人非商业使用。

本项目与 DeepSeek / 深度求索无任何隶属关系，也未获其背书。
