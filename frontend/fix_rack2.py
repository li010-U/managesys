import os
os.chdir('D:/managesys/frontend')

with open('src/views/room/RackView.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add watch to import statement
old_import = \"import { ref, computed, onMounted } from 'vue'\"
new_import = \"import { ref, computed, onMounted, watch } from 'vue'\"
content = content.replace(old_import, new_import)

# 2. Add watch after onMounted block
old_mounted = '''onMounted(async () => {
    await fetchRooms()
  })'''

new_mounted = '''onMounted(async () => {
    await fetchRooms()
  })

  // Listen for route changes to refresh rack and device data
  watch(() => route.path, async () => {
    await fetchRacks()
    if (viewRack.value) {
      await fetchRackDevices(viewRack.value.id)
    }
  })'''

content = content.replace(old_mounted, new_mounted)

with open('src/views/room/RackView.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
