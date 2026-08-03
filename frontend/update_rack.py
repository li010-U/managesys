import os
os.chdir('D:/managesys/frontend')

with open('src/views/room/RackView.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Add watch to onMounted for route changes
old_mounted = 'onMounted(async () => { await fetchRooms() })'
new_mounted = '''onMounted(async () => {
  await fetchRooms()
})

// 监听路由变化刷新数据
import { watch } from 'vue'
watch(() => route.path, async () => {
  await fetchRooms()
  if (viewRack.value) await fetchRackDevices(viewRack.value.id)
})'''

content = content.replace(old_mounted, new_mounted)

with open('src/views/room/RackView.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Added route watcher to RackView!')
