<template>
  <div class="ip-edit-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">设备IP编辑</h3>
        <p class="page-desc" v-if="device">{{ device.name }} · {{ device.asset_number }}</p>
      </div>
      <el-button type="primary" :icon="Position" @click="locateRack">定位机柜</el-button>
    </div>

    <el-alert v-if="device && hasConflict" type="error" :closable="false" show-icon title="该设备存在IP冲突，请修改冲突字段后保存" style="margin-bottom:16px" />

    <el-card shadow="never" v-loading="loading" style="max-width:640px">
      <template #header><strong>IP配置</strong></template>
      <el-form label-width="90px" v-if="form">
        <el-form-item label="管理IP"><el-input v-model="form.management_ip" placeholder="管理IP" /></el-form-item>
        <el-form-item label="业务IP"><el-input v-model="form.business_ip" placeholder="业务IP（多个用逗号分隔）" /></el-form-item>
        <el-form-item label="带外IP"><el-input v-model="form.out_of_band_ip" placeholder="带外IP" /></el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button @click="back">返回</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'DeviceIpEdit' })
import { ref, computed, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import { Position } from "@element-plus/icons-vue"
import { getDeviceApi, updateDeviceApi, type DeviceInfo } from "@/api/device"

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const device = ref<DeviceInfo | null>(null)
const form = ref<{ management_ip?: string; business_ip?: string; out_of_band_ip?: string } | null>(null)

const hasConflict = computed(() => {
  if (!device.value) return false
  const ips = [device.value.management_ip, device.value.business_ip, device.value.out_of_band_ip].filter(Boolean)
  return new Set(ips).size !== ips.length
})

async function load() {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const r = await getDeviceApi(id)
    device.value = r.data
    form.value = { management_ip: r.data.management_ip || "", business_ip: r.data.business_ip || "", out_of_band_ip: r.data.out_of_band_ip || "" }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "设备不存在")
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await updateDeviceApi(device.value!.id, form.value || {})
    ElMessage.success("已保存")
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

function locateRack() {
  const d = device.value
  if (d && d.rack_id) router.push({ path: "/room/racks", query: { rack: String(d.rack_id) } })
  else ElMessage.warning("该设备未挂载到机柜")
}

function back() { router.back() }

onMounted(load)
</script>

<style scoped>
.ip-edit-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 20px; margin: 0 0 4px; color: #1e293b; }
.page-desc { margin: 0; color: #94a3b8; font-size: 13px; }
</style>
