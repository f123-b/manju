# Manju Character Asset Engine

## 目标

Manju 的人物资产不再只是 `assets.characters` 里的图片卡，而是一个能被剧本、Agent、分镜和生成任务共同引用的稳定领域模型：

```text
剧本 → Character Draft → Identity Anchors → 候选参考图
     → Canonical Reference → Master Sheet → Approved → Locked
     → CharacterLook → ShotCharacter → 结构化 Reference 注入 → 连续性影响分析
```

本设计基于四个固定 commit 的开源项目做能力吸收，但不复制它们的应用架构或 UI。

## 上游思想与 Manju 取舍

| 来源 | 固定 commit | 吸收内容 | Manju 处理方式 |
| --- | --- | --- | --- |
| LocalMiniDrama | `adaecf71a38277126fbe1e5e0d79664300f855c1` | 角色提取、外貌到结构化锚点、润色提示词、四视图与参考图注入 | 使用 `CharacterService` 的结构化锚点和候选流程；任务统一写入 Manju `generation_tasks`，不使用 `setImmediate()` 任务系统 |
| drama-skills | `b71cb3ca9343eaf6c0375725ccc9261a4e79021e` | Character 与 Look 分离、连续性锁、参考图生命周期和有效范围 | `CharacterLook` 只记录可变差异；只有 `approved` Reference 能进入生产请求 |
| Alibaba LumenX | `f2a02e23171447c939e7d8e1386b24d17049bbf1` | 单一 Master Reference Sheet、图片 variant、结构化参考图而非 prompt 私有语法 | `CharacterReference.reference_type=master_sheet` 为首选显示与生成参考；其他视图仍是独立 Reference |
| Jellyfish | `a9678194ddf2d9be3ccbe78d4287d87d5089e123` | Character / Costume / Prop / CharacterImage、视角、质量、Primary、多角色镜头关联 | V1 不增加 Actor/Performer；以 `CharacterLook` 表达服装/状态，以现有 Prop 表达道具，以 `shot_characters` 表达多角色绑定 |

## Manju 原生数据模型

### Character

稳定身份：姓名、别名、叙事角色、年龄区间、性别、稳定描述、性格、Identity Anchors、持续表演事实、声音方向、Canonical Reference、锁定状态。

Identity Anchors 只允许长期稳定的脸部结构、发质/发际、身体轮廓、永久标志、侧面/背面特征和相对尺度；服装、雨水、血迹、临时伤口、手持物、情绪和姿势必须留在 Look 或 ShotCharacter。

### CharacterLook

一个可复用且内部相容的外观版本。只记录相对基础身份的差异：服装、发妆、配饰、伤势、天气化、原因和有效场景范围。换装不创建新 Character。

### CharacterReference

具体图片的生命周期记录：`planned / generated / approved / rejected`。类型包括 `portrait / full_body / front / three_quarter / side / back / expression / master_sheet`。`Generated != Approved`；生成请求只有在 Reference 为 `approved` 时才能自动注入。

### ShotCharacter

一个镜头可以绑定多个 Character，各自选择 Look、Primary Reference、位置、情绪、动作和连续性状态。旧 `characterIds/outfitId` 只作为兼容读取和迁移来源，不再作为新写入模型。

### ContinuityLock

按 project / character / look / scene / shot 记录需要在有效场景范围内保持的可见事实。修改 Character、Look 或 Approved Reference 时，通过现有 `dependencies` 加上新绑定查询受影响镜头，标记 `potentially_stale`，不自动重新生成。

## 生成与 Provider Contract

所有人物候选图、Master Sheet、Look 参考图生成都创建现有 `generation_tasks`，由同一个 Worker 调度 Provider、记录 Version、Cost 和输出媒体；不新增第二套队列。

领域请求只携带结构化 references：

```json
{
  "prompt": "本镜动作与环境",
  "references": [
    {
      "asset_id": "REF-LIN-MASTER",
      "role": "identity",
      "character_id": "C001",
      "look_id": "LOOK-LIN-BASE",
      "may_control": ["face", "hair", "body_silhouette"],
      "must_not_control": ["pose", "background", "camera"]
    }
  ]
}
```

Provider Adapter 再把它转换为具体平台的参考槽位。Manju 领域层不出现 `@图片1` 等供应商私有语法。

## 迁移策略

- 现有 `characters.image` 迁移为 `generated` 的 `CharacterReference`；已有锁定角色按示例数据迁移为 `approved + is_primary`，未锁定则保持 `generated`。
- `character_outfits` 迁移为 `character_looks`，保留原 ID，旧表继续保留以支持老客户端读取。
- `shot_characters.outfit_id` 迁移为 `look_id`；`character_id` 迁移成带默认 position 的 ShotCharacter 关系。
- 旧项目 JSON/LocalStorage 仍可被前端读取，远端数据库是新流程的权威来源。

## V1 明确不做

- 不引入 Actor/Performer：当前没有“一名真人/虚拟演员扮演多个故事角色”的产品需求。
- 不复制上游 UI、Provider 或任务队列。
- 不因修改身份或 Look 自动烧钱重生成；只产生 stale/impact 预览和用户确认入口。

