# NekroAgent 抽老婆（命运签）

<img src="icon.png" width="128" alt="抽老婆（命运签）插件图标">

[更新日志](CHANGELOG.md) · 当前版本 **1.1.0**

从**当前 QQ 群成员列表**里随机抽一位群友当今日老婆。打指令立刻出结果；用自然语言说「帮我抽个老婆 / 去抢他老婆」时，AI 会走同一套逻辑并接梗。

## 玩法

- 用 OneBot `get_group_member_list` 拉本群成员，不抽别的群。
- 默认排除机器人、抽取者本人、配置里的黑名单。
- 每人每天第一抽锁定为「正缘」，再抽会被调侃；要换先「离婚」，也可「复婚」找回今日前任。
- 结果带稀有度（普通 / 稀有 / 传说 / 天命）、羁绊称号、契合度和趣味文案。
- 互相抽中会提示「天作之合」；抽到别人的正缘会提示「修罗场」。
- **抢老婆**：指定某人当你的正缘。没人认领则强娶；已是别人的正缘则按稀有度和契合度拼成功率（普通更容易被抢走，天命几乎抢不动）。对方「保护老婆」后今日必失败。抢成功会丢掉你原来的正缘。失败有小概率【反噬】，你的正缘先跑了。
- **送老婆 / 换妻**：过户或互换；收礼方若已有正缘会被挤走。
- **宠老婆 / 贴贴**：加契合度，冲恩爱榜。
- **查户口 / 姻缘榜**：看谁绑了谁，以及渣男榜、倒霉榜。
- 可带头像和 `@`。

## 指令

命令前缀以你的 NekroAgent 配置为准，下面以 `/` 为例：

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `/choulaopo` | `/抽老婆` `/今日老婆` `/抽老公` | 抽取今日正缘 |
| `/my_wife` | `/我的老婆` | 查看自己的今日正缘 |
| `/divorce` | `/离婚` | 解除绑定后可再抽 |
| `/remarry` | `/复婚` | 找回今日仍空窗的前任 |
| `/steal_wife` | `/抢老婆` | `@` 对方，抢来当正缘 |
| `/gift_wife` | `/送老婆` | `@` 对方，把正缘过户给 TA |
| `/swap_wife` | `/换妻` | `@` 对方，双方互换正缘 |
| `/protect_wife` | `/保护老婆` | 今日免疫被抢（每天一次） |
| `/pet_wife` | `/宠老婆` `/贴贴` | 加契合度 |
| `/household` | `/查户口` | `@` 查看对方姻缘；不填查自己 |
| `/wife_board` | `/姻缘榜` `/恩爱榜` `/渣男榜` `/倒霉榜` | 今日榜单 |
| `/group_bonds` | `/本群姻缘` | 今日花名册 |
| `/choulaopo_help` | `/抽老婆帮助` | 帮助 |
| `/reset_bonds` | `/重置姻缘` | 超管清空本群今日记录 |

## 安装

把仓库里的 **`choulaopo` 文件夹** 复制到 NekroAgent 工作插件目录，目录名必须是 `choulaopo`：

```text
<nekro-agent>/plugins/workdir/choulaopo/
  __init__.py
  plugin.py
  chat.py
  ...
```

不要把带连字符的整个仓库目录直接丢进 `workdir`，Python 无法导入 `nekro-plugin-choulaopo`。

```bash
git clone https://github.com/Akiyo-dayo/nekro-plugin-choulaopo.git
```

Linux / macOS：

```bash
cp -r nekro-plugin-choulaopo/choulaopo <nekro-agent>/plugins/workdir/choulaopo
```

Windows PowerShell：

```powershell
Copy-Item -Recurse .\nekro-plugin-choulaopo\choulaopo <nekro-agent>\plugins\workdir\choulaopo
```

然后在 WebUI 启用插件「抽老婆」。仅支持 `onebot_v11` 群聊。插件市场上传图标用仓库根目录的 `icon.png`（插件包内同名副本：`choulaopo/icon.png`）。

## 配置

| 项 | 默认 | 说明 |
| --- | --- | --- |
| 排除自己 | 开 | 不抽到自己 |
| 排除机器人 | 开 | 不抽到 Bot |
| @ 被抽中的人 | 开 | 文案里 @ 正缘 |
| 发送头像 | 开 | 发送 QQ 头像 |
| 每日抢婚次数 | 3 | 每人每天最多尝试抢老婆的次数 |
| 每日宠爱次数 | 5 | 每人每天最多贴贴的次数 |
| 黑名单 QQ | 空 | 这些号不会被抽中，也不能被抢 |

## 给 AI 的能力

群聊中 AI 可调用抽取、查看、离婚、抢、送、换、保护、宠、复婚、查户口和姻缘榜。本群今日姻缘会以短摘要注入提示词，方便接梗，但不会在没有记录时刷屏。

## 开发

```bash
python -m pytest tests -q
```

核心抽取、抢送换宠与文案逻辑不依赖 NekroAgent，可单独跑测试。
