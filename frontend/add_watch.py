import os
os.chdir('D:/managesys/frontend')

with open('src/views/room/RackView.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    # Add watch to import
    if "import { ref, computed, onMounted } from 'vue'" in line:
        new_lines.append(line.replace('onMounted', 'onMounted, watch'))
    # Add watch after onMounted block
    if 'await fetchRooms()' in line and i > 0 and 'onMounted' in lines[i-1]:
        # Found the fetchRooms inside onMounted, add watch after the closing of onMounted
        pass

# Actually, let's do it line by line more carefully
with open('src/views/room/RackView.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

result = []
i = 0
while i < len(lines):
    line = lines[i]
    result.append(line)
    
    # Modify import line
    if "import { ref, computed, onMounted } from 'vue'" in line:
        result[-1] = line.replace('onMounted', 'onMounted, watch')
    
    # Find onMounted block and add watch after it
    if 'onMounted(async () => {' in line:
        # Skip until we find the closing brace of onMounted
        brace_count = 1
        i += 1
        while i < len(lines) and brace_count > 0:
            result.append(lines[i])
            if '{' in lines[i]:
                brace_count += 1
            if '}' in lines[i]:
                brace_count -= 1
            i += 1
        # Add watch after onMounted
        result.append('\n')
        result.append('  // Refresh data when route changes\n')
        result.append('  watch(() => route.path, async () => {\n')
        result.append('    await fetchRacks()\n')
        result.append('    if (viewRack.value) {\n')
        result.append('      await fetchRackDevices(viewRack.value.id)\n')
        result.append('    }\n')
        result.append('  })\n')
        continue
    
    i += 1

with open('src/views/room/RackView.vue', 'w', encoding='utf-8') as f:
    f.writelines(result)

print('Done!')
