import re

with open('D:/managesys/frontend/src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Add el-container style fixes
old_main = """.main-container {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}"""

new_main = """.main-container {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

:deep(.el-container) {
  height: 100%;
  overflow: hidden;
}

:deep(.el-aside) {
  overflow-y: auto;
  overflow-x: hidden;
}"""

content = content.replace(old_main, new_main)

with open('D:/managesys/frontend/src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Added el-container style fixes')
