# @pi-investment/dsh-bundle

PI Investment 插件集**伞 bundle**：把 agent-dh 的全部投资插件行（21 行：17 个 host 工具插件 +
dsh-pmboard、web-liveness、quantsys-v2-manager、agent-os-manager 等）打包为一个标准 DSH bundle。

## 为什么存在

DSH 侧边栏「插件」页是 bundle 管理器：只列出 profile 清单 `dsh.profile.bundles` 里声明、
且 package.json 带 `dsh.bundle.patch` 元数据的包。此前我们的插件以 `- insert:` 裸条目写在
profile 的 cordis.patch.yml（用户层），插件页不可见、不可管理（标 `unaddressable`）。

## 结构

- `package.json` — `dsh.bundle.patch = ./cordis.patch.yml`（bundle 规范唯一硬性要求）
- `cordis.patch.yml` — 全部插件行（从 config/cordis.yml 迁入，唯一真身）

## 纪律

- **新增插件**：行加进本包的 cordis.patch.yml，不要加回 config/cordis.yml（用户层只放覆盖项）
- **GUI 开关某行**：插件管理器会往用户层 patch 写同 id 的 `disabled` 覆盖行（最后写入层生效），
  这会让用户层与 config/cordis.yml 模板产生差异——start.sh 会告警但不覆盖，属预期行为
- 本包**无代码、无 main**：bundle 只是 patch 载体，行里的 `name:` 仍指向各插件包
