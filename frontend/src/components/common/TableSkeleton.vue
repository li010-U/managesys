<template>
  <div class="table-skeleton">
    <el-skeleton :rows="rows" animated>
      <template #template>
        <div class="skeleton-row">
          <el-skeleton-item variant="h3" style="width: 18%" />
          <el-skeleton-item variant="text" style="width: 12%" />
          <el-skeleton-item variant="text" style="width: 14%" />
          <el-skeleton-item variant="text" style="width: 10%" />
          <el-skeleton-item variant="text" style="width: 16%" />
          <el-skeleton-item variant="text" style="width: 8%" />
        </div>
      </template>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 6 })
</script>

<style scoped>
.table-skeleton {
  padding: 16px 8px;
}
.skeleton-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
</style>
