# 删除保护手册 (Delete Protection)

> 原则：**删除被子级引用的父级先存在时，统一返回 409 提示先清理后再删除**；对于“有意级联 / 置空 / 软删除”的场景，在本文档明确标注，不强行加拦截。

目的：
1. 修复“删除存在子级的父级时发生 500 崩溃”的隐患。
2. 避免“安静级联删除大量有意义数据而无警示”。
3. 将各删除入口的语义做到一致。

不硬套制：不对“数据无意义后必然随父级消失”的场景 强行加 409（如传感器历史数据），以免增加无效操作摩擦。

## 删除入口策略矩阵

| 删除入口 | 子级 | 外键行为 | 策略 | 实现位置 |
| --- | --- | --- | --- | --- |
| 数据中心 | 机房 | 非空外键、非级联(500) | **409 先删机房** | facility_service.DataCenterService.delete |
| 机房 | 机柜 | 非空外键、级联 | **409 先删设备** | facility_service.RoomService.delete |
| 机柜 | 设备 | 置空 SET NULL | **409 先下架** | facility_service.RackService.delete |
| 设备类型 | 设备 | RESTRICT(500) | **409 先移除** | device_service.DeviceTypeService.delete |
| 子网 | IP 地址 | 级联 CASCADE | **409 先清除** | ip_registry_service.delete_subnet |
| 传感器 | 传感器数据 | 级联 CASCADE | 有意级联（数据无意义） | sensor_service.delete |
| 角色 | 用户关联、权限关联 | 级联 CASCADE | 有意级联 | role_service.delete_role |
| 业务系统 | 部署明细 | 级联 CASCADE | 有意级联 | systems |
| 工单分类 | 工单 | 置空 SET NULL | 有意设为未分类 | work_orders.delete_category |
| 用户 | — | 软删除(停用) | 软删除 | user_service.delete_user |

## 已修复的 500 记录 (2026-08)

- 数据中心下有机房时删除：ORM 将 rooms.data_center_id 置空而非空列引发外键失败——现返回 409。
- 设备类型在用时删除：FK RESTRICT 触发「原本 500」——现返回 409。
- 子网下有分配地址时删除：现返回 409 防止安静级联丢失 IP。

## 维护约定

- 新增的“父级”删除入口，要么实现 409 先清理、要么在本表添加行并标注“有意”；不得默认“沉默级联”。
- 409 detail 统一为中文，前端通过 error.detail 展示。
- 除非有清晰属于级联的业务必要，最优先选择 409 先清理而非总默认级联删除。

