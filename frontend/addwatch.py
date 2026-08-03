with open('src/views/room/RackView.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'onMounted(async () => { await fetchRooms() })' in line:
        watch_code = '''
  watch(() => route.path, async () => {
    await fetchRacks()
    if (viewRack.value) await fetchRackDevices(viewRack.value.id)
  })
'''
        lines.insert(i+1, watch_code)
        break

for j, l in enumerate(lines):
    if 'import { ref, computed, onMounted } from' in l and 'watch' not in l:
        lines[j] = l.replace('onMounted }', 'onMounted, watch }')
        break

with open('src/views/room/RackView.vue', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Done')
